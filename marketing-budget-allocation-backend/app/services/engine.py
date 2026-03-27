from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import threading
import time
import uuid
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest
from typing import Any, Literal

import numpy as np
import pandas as pd
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from scipy.optimize import minimize

BASE_DIR = Path(__file__).resolve().parents[3]
RESULTS_DIR = Path(os.getenv("MBA_RESULTS_DIR", BASE_DIR / "results"))
_AUTO_CONFIG_CACHE: dict | None = None
_AUTO_CONFIG_SIGNATURE: tuple[tuple[str, int, int], ...] | None = None
SCENARIO_JOB_TTL_SECONDS = 24 * 60 * 60
SCENARIO_TARGET_TOTAL = 1000
SCENARIO_TARGET_DEFAULT = 1000
SCENARIO_TARGET_NEAR_OPT = 100
SCENARIO_NEAR_OPT_MIN_DISTANCE = 0.04
SCENARIO_DEFAULT_MIN_DISTANCE = 0.04
SCENARIO_MAX_ATTEMPTS = 65000
SCENARIO_PAGE_SIZE_DEFAULT = 25
SCENARIO_PAGE_SIZE_MAX = 200
_SCENARIO_JOBS: dict[str, dict[str, Any]] = {}
_SCENARIO_JOBS_LOCK = threading.Lock()


class OptimizeAutoRequest(BaseModel):
    selected_brand: str
    selected_markets: list[str] = Field(default_factory=list)
    budget_increase_type: Literal["percentage", "absolute"] = "percentage"
    budget_increase_value: float = 5.0
    market_overrides: dict[str, dict[str, float]] = Field(default_factory=dict)


class BrandAllocationRequest(BaseModel):
    budget_increase_type: Literal["percentage", "absolute"] = "percentage"
    budget_increase_value: float = 5.0
    selected_brands: list[str] = Field(default_factory=list)
    include_halo: bool = True
    halo_scale: float = 1.0


class ScenarioJobCreateRequest(BaseModel):
    selected_brand: str
    selected_markets: list[str] = Field(default_factory=list)
    budget_increase_type: Literal["percentage", "absolute"] = "percentage"
    budget_increase_value: float = 5.0
    market_overrides: dict[str, dict[str, float]] = Field(default_factory=dict)
    intent_prompt: str = ""
    target_scenarios: int = SCENARIO_TARGET_DEFAULT
    max_runtime_seconds: int = 900


class SCurveAutoRequest(BaseModel):
    selected_brand: str
    selected_markets: list[str] = Field(default_factory=list)
    points: int = 41
    min_scale: float = 0.2
    max_scale: float = 2.5


class ContributionAutoRequest(BaseModel):
    selected_brand: str
    selected_market: str = ""
    top_n: int = 8


class YoyGrowthRequest(BaseModel):
    selected_brand: str
    selected_market: str = ""


class InsightsAIRequest(BaseModel):
    selected_brand: str
    selected_markets: list[str] = Field(default_factory=list)
    budget_increase_type: Literal["percentage", "absolute"] = "percentage"
    budget_increase_value: float = 0.0
    market_overrides: dict[str, dict[str, float]] = Field(default_factory=dict)
    focus_prompt: str = ""


def _stable_score(value: str) -> int:
    digest = hashlib.md5(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _list_result_files() -> list[Path]:
    if not RESULTS_DIR.exists() or not RESULTS_DIR.is_dir():
        return []
    return [p for p in RESULTS_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".csv", ".xlsx"}]


def _results_signature(candidates: list[Path]) -> tuple[tuple[str, int, int], ...]:
    out: list[tuple[str, int, int]] = []
    for path in sorted(candidates, key=lambda x: x.name.lower()):
        st = path.stat()
        out.append((path.name, st.st_mtime_ns, st.st_size))
    return tuple(out)


def _pick_file(candidates: list[Path], hints: tuple[str, ...], exts: set[str]) -> Path | None:
    filtered = [c for c in candidates if c.suffix.lower() in exts]
    for c in filtered:
        n = c.name.lower()
        if any(h in n for h in hints):
            return c
    return filtered[0] if filtered else None


def _detect_input_files() -> dict[str, Path | None]:
    c = _list_result_files()
    return {
        "model_data": _pick_file(c, ("modeling", "model_master", "modeling_master", "master"), {".csv", ".xlsx"}),
        "market_weights": _pick_file(c, ("allbrands", "constraint_vol_converted_models", "final model"), {".csv", ".xlsx"}),
        "max_reach": _pick_file(c, ("max reach", "max_reach"), {".xlsx"}),
    }


def _detect_national_learnings_file() -> Path | None:
    c = _list_result_files()
    return _pick_file(c, ("india_level", "national", "elasticities", "all_brand_combined"), {".xlsx"})


def _read_brand_market_map(market_weights_path: Path) -> dict[str, list[str]]:
    brand_to_markets: dict[str, set[str]] = {}
    if market_weights_path.suffix.lower() == ".csv":
        frames = [pd.read_csv(market_weights_path, usecols=lambda c: str(c).strip() in {"Brand", "Region"})]
    else:
        xls = pd.ExcelFile(market_weights_path)
        frames = [pd.read_excel(xls, sheet_name=s, usecols=lambda c: str(c).strip() in {"Brand", "Region"}) for s in xls.sheet_names]

    for frame in frames:
        frame.columns = [str(c).strip() for c in frame.columns]
        if "Region" not in frame.columns:
            continue
        if "Brand" in frame.columns and frame["Brand"].notna().any():
            clean = frame[["Brand", "Region"]].dropna().copy()
            clean["Brand"] = clean["Brand"].astype(str).str.strip()
            clean["Region"] = clean["Region"].astype(str).str.strip()
            for b, g in clean.groupby("Brand"):
                if b:
                    brand_to_markets.setdefault(b, set()).update(g["Region"].tolist())
        else:
            regions = frame["Region"].dropna().astype(str).str.strip().tolist()
            if regions:
                brand_to_markets.setdefault("Default", set()).update(regions)

    return {b: sorted(m) for b, m in brand_to_markets.items() if m}


def _build_auto_config() -> dict:
    global _AUTO_CONFIG_CACHE, _AUTO_CONFIG_SIGNATURE
    candidates = _list_result_files()
    sig = _results_signature(candidates)
    if _AUTO_CONFIG_CACHE is not None and _AUTO_CONFIG_SIGNATURE == sig:
        return _AUTO_CONFIG_CACHE

    files = _detect_input_files()
    if files["model_data"] is None or files["market_weights"] is None:
        raise HTTPException(status_code=400, detail="Could not auto-detect required files in results/.")

    bm = _read_brand_market_map(files["market_weights"])
    brands = sorted(bm.keys())
    default_brand = brands[0] if brands else ""
    out = {
        "status": "ok",
        "files": {
            "model_data": files["model_data"].name if files["model_data"] else None,
            "market_weights": files["market_weights"].name if files["market_weights"] else None,
            "max_reach": files["max_reach"].name if files["max_reach"] else None,
        },
        "brands": brands,
        "markets_by_brand": bm,
        "default_brand": default_brand,
        "default_markets": bm.get(default_brand, []),
    }
    _AUTO_CONFIG_CACHE = out
    _AUTO_CONFIG_SIGNATURE = sig
    return out


def _read_model_data(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    xls = pd.ExcelFile(path)
    sheet = "Sheet1" if "Sheet1" in xls.sheet_names else xls.sheet_names[0]
    return pd.read_excel(path, sheet_name=sheet)


def _read_market_weights(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        xls = pd.ExcelFile(path)
        df = pd.concat([pd.read_excel(path, sheet_name=s) for s in xls.sheet_names], ignore_index=True, sort=False)
    df.columns = [str(c).strip() for c in df.columns]
    rename_map = {
        c: c.replace("beta_", "").replace("_transformed", "_adjusted")
        for c in df.columns
        if c.startswith("beta_") and c.endswith("_transformed")
    }
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def _read_max_reach(path: Path | None, brand: str) -> pd.DataFrame | None:
    if path is None or path.suffix.lower() != ".xlsx":
        return None
    xls = pd.ExcelFile(path)
    sheet = "updated constraint" if "updated constraint" in xls.sheet_names else xls.sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet)
    df.columns = [str(c).strip() for c in df.columns]
    if "Brand" in df.columns:
        df = df[df["Brand"].astype(str).str.strip() == brand]
    return df


def _as_float_list(raw: Any, n: int, default: float) -> list[float]:
    vals: list[float] = []
    for p in str(raw).split(","):
        p = p.strip()
        if not p:
            continue
        try:
            vals.append(float(p))
        except Exception:
            pass
    if not vals:
        vals = [default]
    if len(vals) == 1:
        vals *= max(1, n)
    if len(vals) < n:
        vals += [vals[-1]] * (n - len(vals))
    return vals[:n]


def _scale_series(series: pd.Series, method: str) -> pd.Series:
    s = series.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if method == "none":
        return s
    if method == "minmax":
        mn, mx = float(s.min()), float(s.max())
        den = mx - mn
        if abs(den) < 1e-12:
            return pd.Series(np.zeros(len(s)), index=s.index)
        return (s - mn) / den
    m, st = float(s.mean()), float(s.std(ddof=0))
    if abs(st) < 1e-12:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - m) / st


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
    except Exception:
        return default
    if np.isfinite(f):
        return f
    return default


def logistic_function(x: np.ndarray, growth_rate: float, midpoint: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-growth_rate * (x - midpoint)))


def adstock_function(x: np.ndarray, carryover_rate: float) -> np.ndarray:
    arr = np.array(x, dtype=float)
    if len(arr) == 0:
        return arr
    result = np.zeros_like(arr)
    result[0] = arr[0]
    for i in range(1, len(arr)):
        result[i] = arr[i] + carryover_rate * result[i - 1]
    return result


def apply_transformations_with_contributions(df: pd.DataFrame, region_weight_df: pd.DataFrame) -> pd.DataFrame:
    out: list[pd.DataFrame] = []
    regions = region_weight_df["Region"].dropna().astype(str).unique()
    allowed_brands = region_weight_df["Brand"].dropna().astype(str).unique() if "Brand" in region_weight_df.columns else None
    media_variables = [c.replace("_adjusted", "") for c in region_weight_df.columns if str(c).endswith("_adjusted")]
    other_variables = [c.replace("beta_scaled_", "") for c in region_weight_df.columns if str(c).startswith("beta_scaled_")]

    for region in regions:
        mask = df["Region"].astype(str) == str(region)
        if allowed_brands is not None and "Brand" in df.columns:
            mask = mask & df["Brand"].astype(str).isin(allowed_brands)
        region_df = df[mask].copy()
        if region_df.empty:
            continue
        region_row = region_weight_df[region_weight_df["Region"].astype(str) == str(region)].iloc[0]

        ttype = str(region_row.get("Transformation_type", "logistic")).strip().lower()
        smethod = str(region_row.get("Standardization_method", "zscore")).strip().lower()
        if smethod not in {"minmax", "zscore", "none"}:
            smethod = "zscore"
        growth_rates = _as_float_list(region_row.get("Growth_rate", "3.5"), len(media_variables), 3.5)
        carryovers = _as_float_list(region_row.get("Carryover", "0.3"), len(media_variables), 0.3)
        mid_points = _as_float_list(region_row.get("Mid_point", "0"), len(media_variables), 0.0)
        powers = _as_float_list(region_row.get("Power", "1.0"), len(media_variables), 1.0)

        if "beta0" in region_weight_df.columns:
            region_df["beta0"] = float(region_row.get("beta0", 0.0))

        for var in other_variables:
            if var in region_df.columns:
                region_df[f"scaled_{var}"] = _scale_series(region_df[var], smethod)

        for idx, media_var in enumerate(media_variables):
            if media_var not in region_df.columns:
                continue
            adstocked = adstock_function(region_df[media_var].values, carryovers[idx])
            region_df[f"{media_var}_Adstock"] = adstocked
            st = float(np.std(adstocked, ddof=0))
            standardized = np.zeros_like(adstocked) if abs(st) < 1e-12 else (adstocked - float(np.mean(adstocked))) / st
            region_df[f"{media_var}_Ad_Std"] = standardized
            if ttype == "power":
                base = np.power(np.maximum(standardized, 0), powers[idx])
            else:
                base = logistic_function(standardized, growth_rates[idx], mid_points[idx])
            base = np.nan_to_num(base)
            region_df[f"{media_var}_Transformed_Base"] = base
            region_df[f"{media_var}_transformed"] = _scale_series(pd.Series(base, index=region_df.index), smethod)
            bcol = f"{media_var}_adjusted"
            if bcol in region_row.index:
                region_df[f"{media_var}_contribution"] = float(region_row.get(bcol, 0.0)) * region_df[f"{media_var}_transformed"]

        for var in other_variables:
            bcol = f"beta_scaled_{var}"
            scol = f"scaled_{var}"
            if bcol in region_row.index and scol in region_df.columns:
                region_df[f"{var}_contribution"] = float(region_row.get(bcol, 0.0)) * region_df[scol]
        out.append(region_df)

    return pd.concat(out, axis=0).reset_index(drop=True) if out else pd.DataFrame()


def _parse_carry_mid(mw_row: pd.Series) -> tuple[float, float, float, float]:
    media_vars = [c for c in mw_row.index if str(c).endswith("_adjusted")]
    carr = _as_float_list(mw_row.get("Carryover", "0.3"), len(media_vars), 0.3)
    mids = _as_float_list(mw_row.get("Mid_point", "0"), len(media_vars), 0.0)
    def idx(name: str) -> int:
        try:
            return media_vars.index(name)
        except Exception:
            return 0
    itv, idg = idx("TV_Reach_adjusted"), idx("Digital_Reach_adjusted")
    return carr[itv], carr[idg], mids[itv], mids[idg]


def _fiscal_key(v: Any) -> int:
    d = "".join(ch for ch in str(v) if ch.isdigit())
    return int(d) if d else -1


def _normalize_brand_name(name: str) -> str:
    raw = str(name).strip()
    key = raw.lower()
    mapping = {
        "aer power pocket": "Aer PP",
        "aer pp": "Aer PP",
        "aer matic": "Aer Matic",
        "aer spray": "Aer Spray",
        "aer o": "Aer O",
    }
    return mapping.get(key, raw)


def _read_national_brand_elasticities(path: Path) -> dict[str, float]:
    xls = pd.ExcelFile(path)
    sheet = "National level learnings" if "National level learnings" in xls.sheet_names else xls.sheet_names[0]
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    if raw.empty or raw.shape[1] < 3:
        return {}

    elasticities: dict[str, float] = {}
    for _, row in raw.iterrows():
        brand_raw = row.iloc[1] if len(row) > 1 else None
        elasticity_raw = row.iloc[2] if len(row) > 2 else None
        if pd.isna(brand_raw) or pd.isna(elasticity_raw):
            continue
        try:
            elasticity = float(elasticity_raw)
        except Exception:
            continue
        brand = _normalize_brand_name(str(brand_raw))
        if not brand:
            continue
        elasticities[brand] = elasticity
    return elasticities


def _read_national_halo_matrix(path: Path) -> dict[str, dict[str, float]]:
    xls = pd.ExcelFile(path)
    sheet = "National level learnings" if "National level learnings" in xls.sheet_names else xls.sheet_names[0]
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    if raw.empty:
        return {}

    header_row_idx = None
    for i in range(min(len(raw), 20)):
        row_vals = [str(v).strip() for v in raw.iloc[i].tolist() if not pd.isna(v)]
        if any(v.startswith("On ") for v in row_vals):
            header_row_idx = i
            break
    if header_row_idx is None:
        return {}

    headers = raw.iloc[header_row_idx]
    target_cols: list[tuple[int, str]] = []
    for col_idx, val in enumerate(headers):
        if pd.isna(val):
            continue
        txt = str(val).strip()
        if txt.startswith("On "):
            target_brand = _normalize_brand_name(txt.replace("On ", "", 1).strip())
            target_cols.append((col_idx, target_brand))

    halo: dict[str, dict[str, float]] = {}
    for i in range(header_row_idx + 1, len(raw)):
        src_raw = raw.iat[i, 1] if raw.shape[1] > 1 else None
        if pd.isna(src_raw):
            continue
        src_brand = _normalize_brand_name(str(src_raw))
        for col_idx, dst_brand in target_cols:
            if src_brand == dst_brand:
                continue
            if col_idx >= raw.shape[1]:
                continue
            v = raw.iat[i, col_idx]
            if pd.isna(v):
                continue
            try:
                f = float(v)
            except Exception:
                continue
            if np.isfinite(f):
                halo.setdefault(src_brand, {})[dst_brand] = f
    return halo


def _compute_brand_baseline_budgets(model_df: pd.DataFrame, brands: list[str]) -> dict[str, float]:
    if not {"Brand", "TV_Spends", "Digital_Spends"}.issubset(model_df.columns):
        raise HTTPException(status_code=400, detail="Model data must contain Brand, TV_Spends, Digital_Spends columns.")

    work = model_df.copy()
    work.columns = [str(c).strip() for c in work.columns]
    if "Region" in work.columns:
        work = work[work["Region"].astype(str).str.strip().str.lower() != "all india"]

    out: dict[str, float] = {}
    for brand in brands:
        bdf = work[work["Brand"].astype(str).str.strip() == brand].copy()
        if bdf.empty:
            continue
        if "Fiscal Year" in bdf.columns and bdf["Fiscal Year"].notna().any():
            fy = sorted(bdf["Fiscal Year"].dropna().unique(), key=_fiscal_key)
            if fy:
                bdf = bdf[bdf["Fiscal Year"] == fy[-1]]
        spend = _finite(bdf["TV_Spends"].sum(), 0.0) + _finite(bdf["Digital_Spends"].sum(), 0.0)
        if spend > 0:
            out[brand] = float(spend)
    return out


def _compute_brand_baseline_volumes(model_df: pd.DataFrame, brands: list[str]) -> dict[str, float]:
    if "Brand" not in model_df.columns:
        raise HTTPException(status_code=400, detail="Model data must contain Brand column.")

    work = model_df.copy()
    work.columns = [str(c).strip() for c in work.columns]
    if "Region" in work.columns:
        work = work[work["Region"].astype(str).str.strip().str.lower() != "all india"]

    out: dict[str, float] = {}
    for brand in brands:
        bdf = work[work["Brand"].astype(str).str.strip() == brand].copy()
        if bdf.empty:
            continue
        if "Fiscal Year" in bdf.columns and bdf["Fiscal Year"].notna().any():
            fy = sorted(bdf["Fiscal Year"].dropna().unique(), key=_fiscal_key)
            if fy:
                bdf = bdf[bdf["Fiscal Year"] == fy[-1]]

        if "Sales_Qty_Total" in bdf.columns:
            vol = _finite(bdf["Sales_Qty_Total"].sum(), 0.0)
        elif "Volume" in bdf.columns:
            vol = _finite(bdf["Volume"].sum(), 0.0)
        else:
            vol = 0.0
        out[brand] = float(max(0.0, vol))
    return out


def _compute_brand_avg_price_last_points(model_df: pd.DataFrame, brands: list[str], points: int = 3) -> dict[str, float]:
    work = model_df.copy()
    work.columns = [str(c).strip() for c in work.columns]
    if "Region" in work.columns:
        work = work[work["Region"].astype(str).str.strip().str.lower() != "all india"]

    out: dict[str, float] = {}
    for brand in brands:
        bdf = work[work["Brand"].astype(str).str.strip() == brand].copy()
        if bdf.empty:
            continue
        if "Fiscal Year" in bdf.columns and bdf["Fiscal Year"].notna().any():
            fy = sorted(bdf["Fiscal Year"].dropna().unique(), key=_fiscal_key)
            if fy:
                bdf = bdf[bdf["Fiscal Year"] == fy[-1]]

        if "Price" in bdf.columns:
            price_series = pd.to_numeric(bdf["Price"], errors="coerce")
        elif {"Sales", "Volume"}.issubset(bdf.columns):
            den = pd.to_numeric(bdf["Volume"], errors="coerce").replace(0.0, np.nan)
            num = pd.to_numeric(bdf["Sales"], errors="coerce")
            price_series = num / den
        elif {"GSV_Total", "Sales_Qty_Total"}.issubset(bdf.columns):
            den = pd.to_numeric(bdf["Sales_Qty_Total"], errors="coerce").replace(0.0, np.nan)
            num = pd.to_numeric(bdf["GSV_Total"], errors="coerce")
            price_series = num / den
        else:
            price_series = pd.Series(np.nan, index=bdf.index)

        if "Date" in bdf.columns:
            dt = pd.to_datetime(bdf["Date"], errors="coerce")
            tdf = pd.DataFrame({"date": dt, "price": price_series})
            tdf = tdf.dropna(subset=["date", "price"])
            tdf = tdf[tdf["price"] > 0]
            if not tdf.empty:
                series = tdf.groupby("date", as_index=False)["price"].mean().sort_values("date")["price"]
                tail = series.tail(max(1, int(points)))
                p = float(np.nanmean(tail.to_numpy()))
            else:
                p = float("nan")
        else:
            series = pd.to_numeric(price_series, errors="coerce")
            series = series[series > 0]
            if not series.empty:
                tail = series.tail(max(1, int(points)))
                p = float(np.nanmean(tail.to_numpy()))
            else:
                p = float("nan")

        if not np.isfinite(p) or p <= 0:
            p = 1.0
        out[brand] = float(p)
    return out


def _optimize_revenue_allocation_with_brand_bounds(
    baselines: dict[str, float],
    baseline_volumes: dict[str, float],
    avg_prices: dict[str, float],
    effective_elasticities: dict[str, float],
    target_total: float,
    max_change_pct: float = 0.25,
) -> tuple[dict[str, float], float, float, float]:
    brands = list(baselines.keys())
    if not brands:
        return {}, 0.0, 0.0, 0.0

    w_raw = {
        b: max(0.0, _finite(baseline_volumes.get(b, 0.0), 0.0) * _finite(avg_prices.get(b, 0.0), 0.0) * max(0.0, _finite(effective_elasticities.get(b, 0.0), 0.0)))
        for b in brands
    }
    wsum = float(sum(w_raw.values()))
    if wsum <= 1e-12:
        shares = {b: 1.0 / len(brands) for b in brands}
    else:
        shares = {b: w_raw[b] / wsum for b in brands}

    mins = np.array([baselines[b] * (1.0 - max_change_pct) for b in brands], dtype=float)
    maxs = np.array([baselines[b] * (1.0 + max_change_pct) for b in brands], dtype=float)
    feasible_min = float(np.sum(mins))
    feasible_max = float(np.sum(maxs))
    bounded_total = float(min(max(float(target_total), feasible_min), feasible_max))

    raw = np.array([bounded_total * shares[b] for b in brands], dtype=float)
    x0 = np.clip(raw, mins, maxs)
    if float(np.sum(x0)) <= 1e-12:
        x0 = np.array([bounded_total / len(brands)] * len(brands), dtype=float)
    else:
        x0 *= bounded_total / float(np.sum(x0))
        x0 = np.clip(x0, mins, maxs)

    def objective(x: np.ndarray) -> float:
        total_revenue = 0.0
        for i, b in enumerate(brands):
            base_b = float(baselines[b])
            base_v = float(_finite(baseline_volumes.get(b, 0.0), 0.0))
            price = float(_finite(avg_prices.get(b, 0.0), 0.0))
            e = max(0.0, float(_finite(effective_elasticities.get(b, 0.0), 0.0)))
            if base_b > 1e-12:
                new_v = base_v * (1.0 + e * ((float(x[i]) - base_b) / base_b))
            else:
                new_v = base_v
            new_v = max(0.0, new_v)
            total_revenue += new_v * price
        return -float(total_revenue)

    cons = [{"type": "eq", "fun": lambda x: float(np.sum(x) - bounded_total)}]
    bnds = [(float(lo), float(hi)) for lo, hi in zip(mins, maxs)]
    sol = minimize(
        objective,
        x0,
        method="SLSQP",
        bounds=bnds,
        constraints=cons,
        options={"maxiter": 400, "ftol": 1e-9},
    )

    if not sol.success or sol.x is None or not np.all(np.isfinite(sol.x)):
        x = np.clip(raw, mins, maxs)
        for _ in range(300):
            diff = bounded_total - float(np.sum(x))
            if abs(diff) <= 1e-6:
                break
            if diff > 0:
                room = maxs - x
            else:
                room = x - mins
            mask = room > 1e-12
            if not np.any(mask):
                break
            take = room[mask]
            x[mask] += diff * (take / float(np.sum(take)))
            x = np.clip(x, mins, maxs)
        alloc = x
    else:
        alloc = np.array(sol.x, dtype=float)

    residual = bounded_total - float(np.sum(alloc))
    if abs(residual) > 1e-4:
        if residual > 0:
            room = maxs - alloc
        else:
            room = alloc - mins
        idxs = np.where(room > 1e-9)[0]
        if len(idxs) > 0:
            i = int(idxs[0])
            alloc[i] += residual
            alloc = np.clip(alloc, mins, maxs)

    out = {b: float(v) for b, v in zip(brands, alloc.tolist())}
    return out, bounded_total, feasible_min, feasible_max


def _brand_allocation_step1(payload: BrandAllocationRequest) -> dict[str, Any]:
    files = _detect_input_files()
    model_path = files["model_data"]
    national_path = _detect_national_learnings_file()
    if model_path is None:
        raise HTTPException(status_code=400, detail="Could not auto-detect model data file in results/.")
    if national_path is None:
        raise HTTPException(status_code=400, detail="Could not auto-detect India-level national learnings file in results/.")

    model_df = _read_model_data(model_path)
    model_df.columns = [str(c).strip() for c in model_df.columns]
    elasticities = _read_national_brand_elasticities(national_path)
    halo_matrix = _read_national_halo_matrix(national_path)
    if not elasticities:
        raise HTTPException(status_code=400, detail="National learnings sheet did not provide usable brand elasticities.")

    aer_candidates = sorted([b for b in elasticities if b.lower().startswith("aer")])
    requested = [_normalize_brand_name(b) for b in payload.selected_brands] if payload.selected_brands else aer_candidates
    selected = [b for b in requested if b in elasticities]
    if not selected:
        raise HTTPException(status_code=400, detail="No valid brands available for Step-1 allocation.")

    baselines = _compute_brand_baseline_budgets(model_df, selected)
    selected = [b for b in selected if b in baselines]
    if not selected:
        raise HTTPException(status_code=400, detail="No baseline spend found for selected brands in model data.")
    baseline_volumes = _compute_brand_baseline_volumes(model_df, selected)
    avg_prices = _compute_brand_avg_price_last_points(model_df, selected, points=3)

    baseline_total = float(sum(baselines[b] for b in selected))
    target_total_requested = (
        baseline_total * (1.0 + payload.budget_increase_value / 100.0)
        if payload.budget_increase_type == "percentage"
        else baseline_total + payload.budget_increase_value
    )
    target_total_requested = max(0.0, float(target_total_requested))
    base_elasticities = {b: float(elasticities.get(b, 0.0)) for b in selected}
    effective_elasticities = dict(base_elasticities)
    halo_uplift = {b: 0.0 for b in selected}

    raw_weights = {b: baselines[b] * max(0.0, base_elasticities[b]) for b in selected}
    wsum = float(sum(raw_weights.values()))
    if wsum <= 1e-12:
        raw_weights = {b: baselines[b] for b in selected}
        wsum = float(sum(raw_weights.values()))
    shares = {b: (raw_weights[b] / wsum) if wsum > 0 else (1.0 / len(selected)) for b in selected}

    if payload.include_halo and halo_matrix:
        for _ in range(12):
            for brand in selected:
                h = 0.0
                for src in selected:
                    if src == brand:
                        continue
                    h += float(shares.get(src, 0.0)) * float(halo_matrix.get(src, {}).get(brand, 0.0))
                halo_uplift[brand] = float(payload.halo_scale) * h
                effective_elasticities[brand] = max(0.0, base_elasticities[brand] + halo_uplift[brand])
            raw_weights = {b: baselines[b] * max(0.0, effective_elasticities[b]) for b in selected}
            wsum = float(sum(raw_weights.values()))
            if wsum <= 1e-12:
                raw_weights = {b: baselines[b] for b in selected}
                wsum = float(sum(raw_weights.values()))
            shares = {b: (raw_weights[b] / wsum) if wsum > 0 else (1.0 / len(selected)) for b in selected}

    allocations, target_total, feasible_min_total, feasible_max_total = _optimize_revenue_allocation_with_brand_bounds(
        baselines=baselines,
        baseline_volumes=baseline_volumes,
        avg_prices=avg_prices,
        effective_elasticities=effective_elasticities,
        target_total=target_total_requested,
        max_change_pct=0.25,
    )
    rows: list[dict[str, Any]] = []
    baseline_total_volume = float(sum(_finite(baseline_volumes.get(b, 0.0), 0.0) for b in selected))
    estimated_total_new_volume = 0.0
    baseline_total_revenue = 0.0
    estimated_total_new_revenue = 0.0
    for brand in selected:
        allocated = float(allocations.get(brand, 0.0))
        share = (allocated / target_total) if target_total > 1e-12 else (1.0 / len(selected))
        baseline_budget = float(baselines[brand])
        baseline_volume = float(_finite(baseline_volumes.get(brand, 0.0), 0.0))
        avg_price = float(_finite(avg_prices.get(brand, 1.0), 1.0))
        spend_change_ratio = ((allocated - baseline_budget) / baseline_budget) if baseline_budget > 1e-12 else 0.0
        vol_uplift_abs = baseline_volume * float(effective_elasticities[brand]) * spend_change_ratio
        vol_uplift_abs = max(-baseline_volume, vol_uplift_abs)
        est_new_volume = baseline_volume + vol_uplift_abs
        vol_uplift_pct = (vol_uplift_abs / baseline_volume * 100.0) if baseline_volume > 1e-12 else 0.0
        baseline_revenue = baseline_volume * avg_price
        est_new_revenue = est_new_volume * avg_price
        rev_uplift_abs = est_new_revenue - baseline_revenue
        rev_uplift_pct = (rev_uplift_abs / baseline_revenue * 100.0) if baseline_revenue > 1e-12 else 0.0
        estimated_total_new_volume += est_new_volume
        baseline_total_revenue += baseline_revenue
        estimated_total_new_revenue += est_new_revenue
        rows.append({
            "brand": brand,
            "baseline_budget": round(baselines[brand], 2),
            "baseline_volume": round(baseline_volume, 2),
            "avg_price_last_3_points": round(avg_price, 6),
            "base_elasticity": round(float(base_elasticities[brand]), 6),
            "halo_uplift": round(float(halo_uplift.get(brand, 0.0)), 6),
            "effective_elasticity": round(float(effective_elasticities[brand]), 6),
            "elasticity": round(float(effective_elasticities[brand]), 6),
            "weight": round(float(raw_weights[brand]), 6),
            "share": round(float(share), 6),
            "allocated_budget": round(float(allocated), 2),
            "uplift_amount": round(float(allocated - baselines[brand]), 2),
            "estimated_new_volume": round(float(est_new_volume), 2),
            "estimated_volume_uplift_abs": round(float(vol_uplift_abs), 2),
            "estimated_volume_uplift_pct": round(float(vol_uplift_pct), 2),
            "baseline_revenue": round(float(baseline_revenue), 2),
            "estimated_new_revenue": round(float(est_new_revenue), 2),
            "estimated_revenue_uplift_abs": round(float(rev_uplift_abs), 2),
            "estimated_revenue_uplift_pct": round(float(rev_uplift_pct), 2),
        })

    rows = sorted(rows, key=lambda r: r["allocated_budget"], reverse=True)
    estimated_total_volume_uplift_abs = estimated_total_new_volume - baseline_total_volume
    estimated_total_volume_uplift_pct = (
        (estimated_total_volume_uplift_abs / baseline_total_volume * 100.0) if baseline_total_volume > 1e-12 else 0.0
    )
    estimated_total_revenue_uplift_abs = estimated_total_new_revenue - baseline_total_revenue
    estimated_total_revenue_uplift_pct = (
        (estimated_total_revenue_uplift_abs / baseline_total_revenue * 100.0) if baseline_total_revenue > 1e-12 else 0.0
    )
    return {
        "status": "ok",
        "message": "Step-1 brand allocation generated (objective: maximize estimated revenue)",
        "files": {
            "model_data": model_path.name,
            "national_learnings": national_path.name,
        },
        "selection": {
            "budget_increase_type": payload.budget_increase_type,
            "budget_increase_value": payload.budget_increase_value,
            "selected_brands": selected,
            "include_halo": payload.include_halo,
            "halo_scale": payload.halo_scale,
            "per_brand_budget_change_limit_pct": 25.0,
        },
        "summary": {
            "baseline_total_budget": round(baseline_total, 2),
            "requested_target_total_budget": round(target_total_requested, 2),
            "target_total_budget": round(target_total, 2),
            "incremental_budget": round(target_total - baseline_total, 2),
            "feasible_min_total_budget": round(feasible_min_total, 2),
            "feasible_max_total_budget": round(feasible_max_total, 2),
            "baseline_total_revenue": round(float(baseline_total_revenue), 2),
            "estimated_total_new_revenue": round(float(estimated_total_new_revenue), 2),
            "estimated_total_revenue_uplift_abs": round(float(estimated_total_revenue_uplift_abs), 2),
            "estimated_total_revenue_uplift_pct": round(float(estimated_total_revenue_uplift_pct), 2),
            "baseline_total_volume": round(float(baseline_total_volume), 2),
            "estimated_total_new_volume": round(float(estimated_total_new_volume), 2),
            "estimated_total_volume_uplift_abs": round(float(estimated_total_volume_uplift_abs), 2),
            "estimated_total_volume_uplift_pct": round(float(estimated_total_volume_uplift_pct), 2),
        },
        "allocation_rows": rows,
    }


def _build_market_data(transformed_df: pd.DataFrame, bw: pd.DataFrame, brand: str, selected_markets: list[str]) -> dict[str, dict[str, Any]]:
    market_data: dict[str, dict[str, Any]] = {}
    for region in selected_markets:
        rows = bw[(bw["Region"].astype(str) == str(region)) & (bw["Brand"].astype(str) == str(brand))]
        if rows.empty:
            continue
        mw_row = rows.iloc[0]
        mdf = transformed_df[(transformed_df["Region"].astype(str) == str(region)) & (transformed_df["Brand"].astype(str) == str(brand))].copy()
        if mdf.empty:
            continue
        fy = sorted(mdf["Fiscal Year"].dropna().unique(), key=_fiscal_key)
        if not fy:
            continue
        recent = mdf[mdf["Fiscal Year"] == fy[-1]].copy()
        if recent.empty:
            continue

        tv_sp, dg_sp = _finite(recent["TV_Spends"].sum()), _finite(recent["Digital_Spends"].sum())
        tv_re, dg_re = _finite(recent["TV_Reach"].sum()), _finite(recent["Digital_Reach"].sum())
        tv_cpr = (tv_sp / tv_re) if tv_re > 0 else 0.0
        dg_cpr = (dg_sp / dg_re) if dg_re > 0 else 0.0
        beta_tv, beta_dg = _finite(mw_row.get("TV_Reach_adjusted", 0.0)), _finite(mw_row.get("Digital_Reach_adjusted", 0.0))

        base_c = _finite(mw_row.get("beta0", 0.0))
        for col in bw.columns:
            if str(col).startswith("beta_scaled_"):
                var = str(col).replace("beta_scaled_", "")
                scol = f"scaled_{var}"
                if scol in mdf.columns:
                    base_c += _finite(mw_row.get(col, 0.0)) * _finite(mdf[scol].mean())
        for col in mw_row.index:
            if str(col).endswith("_adjusted") and col not in {"TV_Reach_adjusted", "Digital_Reach_adjusted"}:
                tcol = f"{str(col).replace('_adjusted', '')}_transformed"
                if tcol in mdf.columns:
                    base_c += _finite(mw_row.get(col, 0.0)) * _finite(mdf[tcol].mean())

        carry_tv, carry_dg, mid_tv, mid_dg = _parse_carry_mid(mw_row)
        safe_mean = lambda c: _finite(recent[c].mean(), 0.0) if c in recent.columns else 0.0
        safe_std = lambda c: _finite(recent[c].std(ddof=0), 1.0) if c in recent.columns else 1.0
        safe_min = lambda c: _finite(recent[c].min(), 0.0) if c in recent.columns else 0.0
        safe_max = lambda c: _finite(recent[c].max(), 1.0) if c in recent.columns else 1.0

        mu_x, sigma_x = safe_mean("TV_Reach_Adstock"), safe_std("TV_Reach_Adstock")
        mu_y, sigma_y = safe_mean("Digital_Reach_Adstock"), safe_std("Digital_Reach_Adstock")
        min_x, max_x = safe_min("TV_Reach_Transformed_Base"), safe_max("TV_Reach_Transformed_Base")
        min_y, max_y = safe_min("Digital_Reach_Transformed_Base"), safe_max("Digital_Reach_Transformed_Base")
        x_log = 1.0 / (1.0 + np.exp(-(3.5 * (0.0 - mid_tv))))
        y_log = 1.0 / (1.0 + np.exp(-(3.5 * (0.0 - mid_dg))))
        x_fin = (x_log - min_x) / (max_x - min_x) if abs(max_x - min_x) > 1e-12 else 0.0
        y_fin = (y_log - min_y) / (max_y - min_y) if abs(max_y - min_y) > 1e-12 else 0.0
        prev_vol = _finite(base_c + beta_tv * x_fin + beta_dg * y_fin, 0.0)
        if brand == "Aer O" and "Sales_Qty_Total" in recent.columns:
            total_fy_volume = _finite(recent["Sales_Qty_Total"].sum(), 0.0)
        elif "Volume" in recent.columns:
            total_fy_volume = _finite(recent["Volume"].sum(), 0.0)
        else:
            total_fy_volume = 0.0

        market_data[region] = {
            "Region": region,
            "beta_tv": beta_tv,
            "beta_digital": beta_dg,
            "C": base_c,
            "prev_vol": prev_vol,
            "mu_x": mu_x, "sigma_x": sigma_x, "min_x": min_x, "max_x": max_x,
            "mu_y": mu_y, "sigma_y": sigma_y, "min_y": min_y, "max_y": max_y,
            "r_tv_list": recent["TV_Reach"].astype(float).tolist(),
            "r_dig_list": recent["Digital_Reach"].astype(float).tolist(),
            "r_tv_spend": recent["TV_Spends"].astype(float).tolist(),
            "r_dig_spend": recent["Digital_Spends"].astype(float).tolist(),
            "carryover_tv": carry_tv,
            "carryover_digital": carry_dg,
            "mid_point_tv": mid_tv,
            "mid_point_digital": mid_dg,
            "tv_cpr": _finite(tv_cpr, 0.0),
            "digital_cpr": _finite(dg_cpr, 0.0),
            "current_spend": _finite(tv_sp + dg_sp, 0.0),
            "total_fy_volume": total_fy_volume,
        }
    return market_data


def _sanitize_market_overrides(raw: dict[str, dict[str, float]] | None) -> dict[str, dict[str, float]]:
    cleaned: dict[str, dict[str, float]] = {}
    if not raw:
        return cleaned
    for market, values in raw.items():
        m = str(market).strip()
        if not m or not isinstance(values, dict):
            continue
        out: dict[str, float] = {}
        for key, value in values.items():
            try:
                f = float(value)
            except Exception:
                continue
            if np.isfinite(f):
                out[str(key).strip()] = f
        if out:
            cleaned[m] = out
    return cleaned


def _apply_cpr_overrides(market_data: dict[str, dict[str, Any]], overrides: dict[str, dict[str, float]]) -> None:
    for region, vals in overrides.items():
        if region not in market_data:
            continue
        md = market_data[region]
        tv_cpr = vals.get("tv_cpr")
        dg_cpr = vals.get("digital_cpr")
        if tv_cpr is not None and tv_cpr > 0:
            md["tv_cpr"] = float(tv_cpr)
        if dg_cpr is not None and dg_cpr > 0:
            md["digital_cpr"] = float(dg_cpr)
        tv_sp = float(np.sum(md["r_tv_list"])) * float(md["tv_cpr"])
        dg_sp = float(np.sum(md["r_dig_list"])) * float(md["digital_cpr"])
        md["current_spend"] = tv_sp + dg_sp


def _resolve_market_limits(
    region: str,
    md: dict[str, Any],
    max_reach_df: pd.DataFrame | None,
    override: dict[str, float] | None,
) -> dict[str, float | None]:
    tv_base = float(np.sum(md["r_tv_list"]))
    dg_base = float(np.sum(md["r_dig_list"]))
    tv_cpr = float(md["tv_cpr"])
    dg_cpr = float(md["digital_cpr"])

    tv_min = tv_base * 0.001
    tv_max = tv_base * 3.0
    dg_min = dg_base * 0.001
    dg_max = dg_base * 3.0

    if max_reach_df is not None and not max_reach_df.empty:
        row_tv = max_reach_df[
            (max_reach_df["Region"].astype(str) == str(region))
            & (max_reach_df["Media_variables"].astype(str) == "TV_Reach")
        ]
        row_dg = max_reach_df[
            (max_reach_df["Region"].astype(str) == str(region))
            & (max_reach_df["Media_variables"].astype(str) == "Digital_Reach")
        ]
        if not row_tv.empty:
            if "Max_reach" in row_tv.columns and not pd.isna(row_tv["Max_reach"].iloc[0]):
                tv_max = float(row_tv["Max_reach"].iloc[0])
            if "Min_reach" in row_tv.columns and not pd.isna(row_tv["Min_reach"].iloc[0]):
                tv_min = float(min(tv_base, row_tv["Min_reach"].iloc[0]))
        if not row_dg.empty:
            if "Max_reach" in row_dg.columns and not pd.isna(row_dg["Max_reach"].iloc[0]):
                dg_max = float(row_dg["Max_reach"].iloc[0])
            if "Min_reach" in row_dg.columns and not pd.isna(row_dg["Min_reach"].iloc[0]):
                dg_min = float(min(dg_base, row_dg["Min_reach"].iloc[0]))

    ov = override or {}
    if "min_annual_tv_reach" in ov:
        tv_min = float(ov["min_annual_tv_reach"])
    if "max_annual_tv_reach" in ov:
        tv_max = float(ov["max_annual_tv_reach"])
    if "min_annual_digital_reach" in ov:
        dg_min = float(ov["min_annual_digital_reach"])
    if "max_annual_digital_reach" in ov:
        dg_max = float(ov["max_annual_digital_reach"])

    if "min_tv_spend" in ov and tv_cpr > 0:
        tv_min = float(ov["min_tv_spend"]) / tv_cpr
    if "max_tv_spend" in ov and tv_cpr > 0:
        tv_max = float(ov["max_tv_spend"]) / tv_cpr
    if "min_digital_spend" in ov and dg_cpr > 0:
        dg_min = float(ov["min_digital_spend"]) / dg_cpr
    if "max_digital_spend" in ov and dg_cpr > 0:
        dg_max = float(ov["max_digital_spend"]) / dg_cpr

    tv_min = max(0.0, tv_min)
    dg_min = max(0.0, dg_min)
    tv_max = max(tv_min, tv_max)
    dg_max = max(dg_min, dg_max)

    return {
        "tv_min_reach": tv_min,
        "tv_max_reach": tv_max,
        "dg_min_reach": dg_min,
        "dg_max_reach": dg_max,
        "min_tv_spend": tv_min * tv_cpr,
        "max_tv_spend": tv_max * tv_cpr,
        "min_digital_spend": dg_min * dg_cpr,
        "max_digital_spend": dg_max * dg_cpr,
    }


def _build_market_limits_map(
    market_data: dict[str, dict[str, Any]],
    regions: list[str],
    max_reach_df: pd.DataFrame | None,
    overrides: dict[str, dict[str, float]],
) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = {}
    for region in regions:
        out[region] = _resolve_market_limits(region, market_data[region], max_reach_df, overrides.get(region))
    return out


def _objective(v: np.ndarray, market_data: dict[str, dict[str, Any]], regions: list[str]) -> float:
    total_vol = 0.0
    for i, region in enumerate(regions):
        md = market_data[region]
        x, y = float(v[2 * i]), float(v[2 * i + 1])
        vol = _predict_region_volume(md, x, y)
        if not np.isfinite(vol):
            return 1e12
        total_vol += vol
    if not np.isfinite(total_vol):
        return 1e12
    return -total_vol


def _predict_region_volume(md: dict[str, Any], tv_change: float, digital_change: float) -> float:
    new_tv = np.array(md["r_tv_list"], dtype=float) * (1.0 + tv_change)
    new_dg = np.array(md["r_dig_list"], dtype=float) * (1.0 + digital_change)
    ad_tv, ad_dg = adstock_function(new_tv, md["carryover_tv"]), adstock_function(new_dg, md["carryover_digital"])
    x_ad = float(np.mean(ad_tv)) if len(ad_tv) else 0.0
    y_ad = float(np.mean(ad_dg)) if len(ad_dg) else 0.0
    x_std = (x_ad - md["mu_x"]) / md["sigma_x"] if abs(md["sigma_x"]) > 1e-12 else 0.0
    y_std = (y_ad - md["mu_y"]) / md["sigma_y"] if abs(md["sigma_y"]) > 1e-12 else 0.0
    x_log = 1.0 / (1.0 + np.exp(-3.5 * (x_std - md["mid_point_tv"])))
    y_log = 1.0 / (1.0 + np.exp(-3.5 * (y_std - md["mid_point_digital"])))
    x_fin = (x_log - md["min_x"]) / (md["max_x"] - md["min_x"]) if abs(md["max_x"] - md["min_x"]) > 1e-12 else 0.0
    y_fin = (y_log - md["min_y"]) / (md["max_y"] - md["min_y"]) if abs(md["max_y"] - md["min_y"]) > 1e-12 else 0.0
    return _finite(md["beta_tv"] * x_fin + md["beta_digital"] * y_fin + md["C"], np.nan)


def _objective_revenue(
    v: np.ndarray,
    market_data: dict[str, dict[str, Any]],
    regions: list[str],
    region_prices: dict[str, float],
) -> float:
    total_revenue = 0.0
    for i, region in enumerate(regions):
        md = market_data[region]
        x, y = float(v[2 * i]), float(v[2 * i + 1])
        volume = _predict_region_volume(md, x, y)
        if not np.isfinite(volume):
            return 1e12
        price = max(0.0, float(_finite(region_prices.get(region, 1.0), 1.0)))
        total_revenue += max(0.0, volume) * price
    if not np.isfinite(total_revenue):
        return 1e12
    return -total_revenue


def _budget_constraint(v: np.ndarray, market_data: dict[str, dict[str, Any]], regions: list[str], B: float) -> float:
    total_spend = 0.0
    for i, region in enumerate(regions):
        md = market_data[region]
        x, y = float(v[2 * i]), float(v[2 * i + 1])
        total_spend += md["tv_cpr"] * float(np.sum(md["r_tv_list"])) * (1.0 + x) + md["digital_cpr"] * float(np.sum(md["r_dig_list"])) * (1.0 + y)
    return B - total_spend


def _build_constraints(
    market_data: dict[str, dict[str, Any]],
    regions: list[str],
    B: float,
    limits_map: dict[str, dict[str, float | None]],
) -> list[dict[str, Any]]:
    cons: list[dict[str, Any]] = [{"type": "eq", "fun": lambda v: _budget_constraint(v, market_data, regions, B)}]
    tv_low, tv_high, dg_low, dg_high = 0.001, 3.0, 0.001, 4.0
    for i, region in enumerate(regions):
        md = market_data[region]
        tv_base, dg_base = float(np.sum(md["r_tv_list"])), float(np.sum(md["r_dig_list"]))
        tv_cpr, dg_cpr = float(md["tv_cpr"]), float(md["digital_cpr"])
        cons.append({"type": "ineq", "fun": lambda v, i=i, b=tv_base, c=tv_cpr: (b * (1.0 + v[2 * i]) * c) - (b * c * tv_low)})
        cons.append({"type": "ineq", "fun": lambda v, i=i, b=tv_base, c=tv_cpr: (b * c * tv_high) - (b * (1.0 + v[2 * i]) * c)})
        cons.append({"type": "ineq", "fun": lambda v, i=i, b=dg_base, c=dg_cpr: (b * (1.0 + v[2 * i + 1]) * c) - (b * c * dg_low)})
        cons.append({"type": "ineq", "fun": lambda v, i=i, b=dg_base, c=dg_cpr: (b * c * dg_high) - (b * (1.0 + v[2 * i + 1]) * c)})
        lim = limits_map.get(region, {})
        tv_min = float(lim.get("tv_min_reach", tv_base * 0.001) or 0.0)
        tv_max = float(lim.get("tv_max_reach", tv_base * 3.0) or (tv_base * 3.0))
        dg_min = float(lim.get("dg_min_reach", dg_base * 0.001) or 0.0)
        dg_max = float(lim.get("dg_max_reach", dg_base * 3.0) or (dg_base * 3.0))
        cons.append({"type": "ineq", "fun": lambda v, i=i, b=tv_base, ub=tv_max: ub - (b * (1.0 + v[2 * i])) + 1e-3})
        cons.append({"type": "ineq", "fun": lambda v, i=i, b=tv_base, lb=tv_min: (b * (1.0 + v[2 * i])) - lb + 1e-3})
        cons.append({"type": "ineq", "fun": lambda v, i=i, b=dg_base, ub=dg_max: ub - (b * (1.0 + v[2 * i + 1])) + 1e-3})
        cons.append({"type": "ineq", "fun": lambda v, i=i, b=dg_base, lb=dg_min: (b * (1.0 + v[2 * i + 1])) - lb + 1e-3})
    return cons


def _run_solver_with_objective(
    market_data: dict[str, dict[str, Any]],
    regions: list[str],
    B: float,
    limits_map: dict[str, dict[str, float | None]],
    objective_fn: Any,
    objective_args: tuple[Any, ...] = (),
) -> tuple[np.ndarray, dict[str, Any]]:
    n_vars = 2 * len(regions)
    x0 = np.zeros(n_vars, dtype=float)
    bounds = [(-0.999, 4.0)] * n_vars
    cons = _build_constraints(market_data, regions, B, limits_map)
    args = (market_data, regions, *objective_args)
    res = minimize(
        objective_fn,
        x0,
        args=args,
        method="trust-constr",
        bounds=bounds,
        constraints=cons,
        options={"maxiter": 1500, "gtol": 1e-3, "xtol": 1e-3, "barrier_tol": 1e-3},
    )
    if (not res.success) or (res.x is None):
        res2 = minimize(
            objective_fn,
            x0,
            args=args,
            method="SLSQP",
            bounds=bounds,
            constraints=cons,
            options={"maxiter": 2000, "ftol": 1e-6},
        )
        if res2.success and res2.x is not None:
            return np.array(res2.x, dtype=float), {"solver": "SLSQP", "success": True, "message": str(res2.message)}
    if res.x is not None:
        return np.array(res.x, dtype=float), {"solver": "trust-constr", "success": bool(res.success), "message": str(res.message)}
    return x0, {"solver": "fallback-baseline", "success": False, "message": "Solver did not return a point."}


def _run_solver(
    market_data: dict[str, dict[str, Any]],
    regions: list[str],
    B: float,
    limits_map: dict[str, dict[str, float | None]],
) -> tuple[np.ndarray, dict[str, Any]]:
    return _run_solver_with_objective(
        market_data=market_data,
        regions=regions,
        B=B,
        limits_map=limits_map,
        objective_fn=_objective,
    )


def _load_optimization_context(payload: OptimizeAutoRequest) -> dict[str, Any]:
    cfg = _build_auto_config()
    files = _detect_input_files()
    model_path, weights_path, max_path = files["model_data"], files["market_weights"], files["max_reach"]
    if model_path is None or weights_path is None:
        raise HTTPException(status_code=400, detail="Missing required files in results folder.")

    brand = payload.selected_brand.strip()
    if brand not in cfg["markets_by_brand"]:
        raise HTTPException(status_code=400, detail="Selected brand is not available in model results.")
    available_markets = cfg["markets_by_brand"][brand]
    selected_markets = payload.selected_markets or available_markets
    selected_markets = [m for m in selected_markets if m in available_markets]
    if not selected_markets:
        raise HTTPException(status_code=400, detail="Please select at least one valid market.")

    model_df = _read_model_data(model_path)
    model_df.columns = [str(c).strip() for c in model_df.columns]
    req = {"Region", "Brand", "Date", "Fiscal Year", "TV_Spends", "Digital_Spends", "TV_Reach", "Digital_Reach"}
    missing = req - set(model_df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Model data missing columns: {sorted(missing)}")

    weights_df = _read_market_weights(weights_path)
    if "Brand" not in weights_df.columns or "Region" not in weights_df.columns:
        raise HTTPException(status_code=400, detail="Final model results must contain Brand and Region columns.")
    bw = weights_df[weights_df["Brand"].astype(str).str.strip() == brand].copy()
    if bw.empty:
        raise HTTPException(status_code=400, detail="No rows found for selected brand in model results.")

    transformed = apply_transformations_with_contributions(model_df, bw)
    if transformed.empty:
        raise HTTPException(status_code=400, detail="Transformation returned no rows.")
    market_data = _build_market_data(transformed, bw, brand, selected_markets)
    if not market_data:
        raise HTTPException(status_code=400, detail="No valid market data constructed.")

    overrides = _sanitize_market_overrides(payload.market_overrides)
    _apply_cpr_overrides(market_data, overrides)

    baseline_budget = float(sum(md["current_spend"] for md in market_data.values()))
    target_budget = (
        baseline_budget * (1.0 + payload.budget_increase_value / 100.0)
        if payload.budget_increase_type == "percentage"
        else baseline_budget + payload.budget_increase_value
    )
    max_reach_df = _read_max_reach(max_path, brand)
    regions = list(market_data.keys())
    limits_map = _build_market_limits_map(market_data, regions, max_reach_df, overrides)

    return {
        "files": files,
        "brand": brand,
        "regions": regions,
        "model_df": model_df,
        "market_data": market_data,
        "baseline_budget": baseline_budget,
        "target_budget": target_budget,
        "max_reach_df": max_reach_df,
        "limits_map": limits_map,
        "overrides": overrides,
        "payload": payload,
    }


def _compute_region_prices_last_3_months(model_df: pd.DataFrame, brand: str, regions: list[str]) -> dict[str, float]:
    def _compute_price_for_frame(df: pd.DataFrame) -> float:
        if df.empty:
            return 1.0
        work = df.copy()
        work.columns = [str(c).strip() for c in work.columns]
        if {"GSV_Total", "Sales_Qty_Total"}.issubset(work.columns):
            den = pd.to_numeric(work["Sales_Qty_Total"], errors="coerce")
            num = pd.to_numeric(work["GSV_Total"], errors="coerce")
        elif {"Sales", "Volume"}.issubset(work.columns):
            den = pd.to_numeric(work["Volume"], errors="coerce")
            num = pd.to_numeric(work["Sales"], errors="coerce")
        else:
            return 1.0

        den = den.replace(0.0, np.nan)
        price = num / den
        if "Date" in work.columns:
            dates = pd.to_datetime(work["Date"], errors="coerce")
        elif {"Year", "Month"}.issubset(work.columns):
            dates = pd.to_datetime(
                {
                    "year": pd.to_numeric(work["Year"], errors="coerce"),
                    "month": pd.to_numeric(work["Month"], errors="coerce"),
                    "day": 1,
                },
                errors="coerce",
            )
        else:
            dates = pd.Series(np.arange(len(work), dtype=float), index=work.index)
        tdf = pd.DataFrame({"date": dates, "price": price})
        tdf = tdf.dropna(subset=["date", "price"])
        tdf = tdf[tdf["price"] > 0]
        if tdf.empty:
            return 1.0
        by_period = tdf.groupby("date", as_index=False)["price"].mean().sort_values("date")
        tail = by_period["price"].tail(3)
        val = float(np.nanmean(tail.to_numpy()))
        if not np.isfinite(val) or val <= 0:
            return 1.0
        return val

    base = model_df.copy()
    base.columns = [str(c).strip() for c in base.columns]
    if "Brand" not in base.columns:
        return {region: 1.0 for region in regions}
    bdf = base[base["Brand"].astype(str).str.strip() == brand].copy()
    if bdf.empty:
        return {region: 1.0 for region in regions}
    brand_fallback = _compute_price_for_frame(bdf)
    out: dict[str, float] = {}
    for region in regions:
        rdf = bdf[bdf["Region"].astype(str).str.strip() == str(region)].copy() if "Region" in bdf.columns else pd.DataFrame()
        out[region] = _compute_price_for_frame(rdf) if not rdf.empty else brand_fallback
    return out


def _budget_epsilon(target_budget: float) -> float:
    return max(1.0, 1e-8 * abs(float(target_budget)))


def _build_variable_bounds_and_coeffs(
    market_data: dict[str, dict[str, Any]],
    regions: list[str],
    limits_map: dict[str, dict[str, float | None]],
) -> tuple[list[tuple[float, float]], np.ndarray, float]:
    bounds: list[tuple[float, float]] = []
    coeffs: list[float] = []
    baseline_budget = 0.0
    tv_low, tv_high, dg_low, dg_high = 0.001, 3.0, 0.001, 4.0

    for region in regions:
        md = market_data[region]
        lim = limits_map.get(region, {})
        tv_base = float(np.sum(md["r_tv_list"]))
        dg_base = float(np.sum(md["r_dig_list"]))
        tv_cpr = float(md["tv_cpr"])
        dg_cpr = float(md["digital_cpr"])

        baseline_budget += tv_base * tv_cpr + dg_base * dg_cpr

        tv_min_reach = float(lim.get("tv_min_reach", tv_base * tv_low) or 0.0)
        tv_max_reach = float(lim.get("tv_max_reach", tv_base * tv_high) or (tv_base * tv_high))
        dg_min_reach = float(lim.get("dg_min_reach", dg_base * dg_low) or 0.0)
        dg_max_reach = float(lim.get("dg_max_reach", dg_base * dg_high) or (dg_base * dg_high))

        x_min = max(-0.999, tv_low - 1.0, (tv_min_reach / tv_base - 1.0) if tv_base > 1e-12 else -0.999)
        x_max = min(4.0, tv_high - 1.0, (tv_max_reach / tv_base - 1.0) if tv_base > 1e-12 else 4.0)
        y_min = max(-0.999, dg_low - 1.0, (dg_min_reach / dg_base - 1.0) if dg_base > 1e-12 else -0.999)
        y_max = min(4.0, dg_high - 1.0, (dg_max_reach / dg_base - 1.0) if dg_base > 1e-12 else 4.0)

        if x_max < x_min:
            x_max = x_min
        if y_max < y_min:
            y_max = y_min

        bounds.append((float(x_min), float(x_max)))
        bounds.append((float(y_min), float(y_max)))
        coeffs.append(float(tv_base * tv_cpr))
        coeffs.append(float(dg_base * dg_cpr))

    return bounds, np.array(coeffs, dtype=float), float(baseline_budget)


def _project_vector_to_budget(
    vector: np.ndarray,
    target_budget: float,
    bounds: list[tuple[float, float]],
    coeffs: np.ndarray,
    baseline_budget: float,
) -> np.ndarray | None:
    v = np.array(vector, dtype=float)
    if len(v) != len(bounds):
        return None
    for i, (lo, hi) in enumerate(bounds):
        v[i] = min(max(v[i], lo), hi)

    eps = _budget_epsilon(target_budget)
    curr = baseline_budget + float(np.dot(coeffs, v))
    diff = float(target_budget - curr)
    if abs(diff) <= eps:
        return v

    if diff > 0:
        idx_order = np.argsort(-coeffs)
    else:
        idx_order = np.argsort(coeffs)

    for idx in idx_order:
        c = float(coeffs[idx])
        if abs(c) < 1e-12:
            continue
        lo, hi = bounds[idx]
        if diff > 0:
            room = hi - v[idx]
            if room <= 1e-12:
                continue
            step = min(room, diff / c) if c > 0 else 0.0
            if step > 0:
                v[idx] += step
                diff -= c * step
        else:
            room = v[idx] - lo
            if room <= 1e-12:
                continue
            step = min(room, (-diff) / c) if c > 0 else 0.0
            if step > 0:
                v[idx] -= step
                diff += c * step
        if abs(diff) <= eps:
            return v

    curr = baseline_budget + float(np.dot(coeffs, v))
    if abs(curr - target_budget) <= eps:
        return v
    return None


def _is_vector_feasible(
    vector: np.ndarray,
    target_budget: float,
    bounds: list[tuple[float, float]],
    coeffs: np.ndarray,
    baseline_budget: float,
) -> bool:
    if len(vector) != len(bounds):
        return False
    for i, (lo, hi) in enumerate(bounds):
        if vector[i] < lo - 1e-9 or vector[i] > hi + 1e-9:
            return False
    total_spend = baseline_budget + float(np.dot(coeffs, vector))
    return abs(total_spend - float(target_budget)) <= _budget_epsilon(target_budget)


def _evaluate_solution_vector(
    v: np.ndarray,
    market_data: dict[str, dict[str, Any]],
    regions: list[str],
    limits_map: dict[str, dict[str, float | None]],
    region_prices: dict[str, float] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_prev, total_new, total_spend = 0.0, 0.0, 0.0
    weighted_tv, weighted_dg = 0.0, 0.0
    total_baseline_revenue = 0.0
    total_new_revenue = 0.0
    market_new_spend: dict[str, float] = {}

    for i, region in enumerate(regions):
        md = market_data[region]
        x, y = float(v[2 * i]), float(v[2 * i + 1])
        base_tv = np.array(md["r_tv_list"], dtype=float)
        base_dg = np.array(md["r_dig_list"], dtype=float)
        new_tv = base_tv * (1.0 + x)
        new_dg = base_dg * (1.0 + y)
        new_tv_total, new_dg_total = float(np.sum(new_tv)), float(np.sum(new_dg))
        old_tv_total, old_dg_total = float(np.sum(base_tv)), float(np.sum(base_dg))
        new_tv_sp = new_tv_total * float(md["tv_cpr"])
        new_dg_sp = new_dg_total * float(md["digital_cpr"])
        new_sp = new_tv_sp + new_dg_sp
        market_new_spend[region] = new_sp

        prev_vol = float(md["prev_vol"])
        new_vol = _predict_region_volume(md, x, y)
        new_vol = float(_finite(new_vol, 0.0))
        prev_vol = float(max(0.0, prev_vol))
        new_vol = float(max(0.0, new_vol))

        tv_split = new_tv_total / (new_tv_total + new_dg_total) if (new_tv_total + new_dg_total) > 0 else 0.0
        dg_split = 1.0 - tv_split
        old_tv_share = old_tv_total / (old_tv_total + old_dg_total) if (old_tv_total + old_dg_total) > 0 else 0.0
        old_dg_share = 1.0 - old_tv_share
        tv_delta = ((new_tv_total - old_tv_total) / old_tv_total * 100.0) if old_tv_total > 0 else 0.0
        dg_delta = ((new_dg_total - old_dg_total) / old_dg_total * 100.0) if old_dg_total > 0 else 0.0
        old_total_spend = float(md["current_spend"])
        uplift_abs = new_vol - prev_vol
        uplift_pct = (uplift_abs / prev_vol * 100.0) if abs(prev_vol) > 1e-12 else 0.0

        price = max(0.0, float(_finite((region_prices or {}).get(region, 1.0), 1.0)))
        baseline_revenue = prev_vol * price
        new_revenue = new_vol * price
        revenue_uplift_abs = new_revenue - baseline_revenue
        revenue_uplift_pct = (revenue_uplift_abs / baseline_revenue * 100.0) if baseline_revenue > 1e-12 else 0.0

        lim = limits_map.get(region, {})
        rows.append(
            {
                "market": region,
                "new_budget_share": 0.0,
                "tv_split": round(tv_split, 4),
                "digital_split": round(dg_split, 4),
                "tv_delta_reach_pct": round(tv_delta, 2),
                "digital_delta_reach_pct": round(dg_delta, 2),
                "tv_change_pct_var": round(x * 100.0, 2),
                "digital_change_pct_var": round(y * 100.0, 2),
                "new_annual_tv_reach": round(new_tv_total, 2),
                "new_annual_digital_reach": round(new_dg_total, 2),
                "fy25_tv_reach": round(old_tv_total, 2),
                "fy25_digital_reach": round(old_dg_total, 2),
                "new_tv_share": round(tv_split, 4),
                "new_digital_share": round(dg_split, 4),
                "fy25_tv_share": round(old_tv_share, 4),
                "fy25_digital_share": round(old_dg_share, 4),
                "max_annual_tv_reach": None if lim.get("tv_max_reach") is None else round(float(lim["tv_max_reach"]), 2),
                "min_annual_tv_reach": None if lim.get("tv_min_reach") is None else round(float(lim["tv_min_reach"]), 2),
                "max_annual_digital_reach": None if lim.get("dg_max_reach") is None else round(float(lim["dg_max_reach"]), 2),
                "min_annual_digital_reach": None if lim.get("dg_min_reach") is None else round(float(lim["dg_min_reach"]), 2),
                "max_tv_spend": None if lim.get("max_tv_spend") is None else round(float(lim["max_tv_spend"]), 2),
                "min_tv_spend": None if lim.get("min_tv_spend") is None else round(float(lim["min_tv_spend"]), 2),
                "max_digital_spend": None if lim.get("max_digital_spend") is None else round(float(lim["max_digital_spend"]), 2),
                "min_digital_spend": None if lim.get("min_digital_spend") is None else round(float(lim["min_digital_spend"]), 2),
                "tv_cpr": round(float(md["tv_cpr"]), 4),
                "digital_cpr": round(float(md["digital_cpr"]), 4),
                "new_total_tv_spend": round(new_tv_sp, 2),
                "new_total_digital_spend": round(new_dg_sp, 2),
                "old_total_spend": round(old_total_spend, 2),
                "new_total_spend": round(new_sp, 2),
                "pct_change_total_spend": round(((new_sp - old_total_spend) / old_total_spend * 100.0) if abs(old_total_spend) > 1e-12 else 0.0, 2),
                "total_fy_volume": round(float(md.get("total_fy_volume", 0.0)), 2),
                "prev_volume": round(prev_vol, 2),
                "new_volume": round(new_vol, 2),
                "uplift_abs": round(uplift_abs, 2),
                "uplift_pct": round(uplift_pct, 2),
                "baseline_revenue": round(baseline_revenue, 2),
                "new_revenue": round(new_revenue, 2),
                "revenue_uplift_abs": round(revenue_uplift_abs, 2),
                "revenue_uplift_pct": round(revenue_uplift_pct, 2),
            }
        )
        total_prev += prev_vol
        total_new += new_vol
        total_spend += new_sp
        weighted_tv += new_sp * tv_split
        weighted_dg += new_sp * dg_split
        total_baseline_revenue += baseline_revenue
        total_new_revenue += new_revenue

    if total_spend > 0:
        for row in rows:
            row["new_budget_share"] = round(market_new_spend[row["market"]] / total_spend, 4)
            old_sp = float(row["old_total_spend"])
            row["extra_budget_share"] = round(
                ((row["new_total_spend"] - old_sp) / (total_spend - sum(float(market_data[r]["current_spend"]) for r in regions)))
                if abs(total_spend - sum(float(market_data[r]["current_spend"]) for r in regions)) > 1e-12
                else 0.0,
                4,
            )

    uplift_pct = ((total_new - total_prev) / total_prev * 100.0) if abs(total_prev) > 1e-12 else 0.0
    revenue_uplift_abs = total_new_revenue - total_baseline_revenue
    revenue_uplift_pct = (revenue_uplift_abs / total_baseline_revenue * 100.0) if total_baseline_revenue > 1e-12 else 0.0
    return {
        "rows": rows,
        "total_prev_volume": float(total_prev),
        "total_new_volume": float(total_new),
        "total_spend": float(total_spend),
        "weighted_tv_share": float((weighted_tv / total_spend) if total_spend > 0 else 0.0),
        "weighted_digital_share": float((weighted_dg / total_spend) if total_spend > 0 else 0.0),
        "total_volume_uplift": float(total_new - total_prev),
        "total_volume_uplift_pct": float(uplift_pct),
        "baseline_revenue": float(total_baseline_revenue),
        "new_revenue": float(total_new_revenue),
        "revenue_uplift_abs": float(revenue_uplift_abs),
        "revenue_uplift_pct": float(revenue_uplift_pct),
    }


def _optimize_real(payload: OptimizeAutoRequest) -> dict[str, Any]:
    ctx = _load_optimization_context(payload)
    files = ctx["files"]
    model_path, weights_path, max_path = files["model_data"], files["market_weights"], files["max_reach"]
    brand = ctx["brand"]
    regions = ctx["regions"]
    market_data = ctx["market_data"]
    limits_map = ctx["limits_map"]
    baseline_budget = float(ctx["baseline_budget"])
    B = float(ctx["target_budget"])
    sol, meta = _run_solver(market_data, regions, B, limits_map)

    rows: list[dict[str, Any]] = []
    total_prev, total_new, total_spend = 0.0, 0.0, 0.0
    weighted_tv, weighted_dg = 0.0, 0.0
    market_new_spend: dict[str, float] = {}
    market_new_tv_spend: dict[str, float] = {}
    market_new_dg_spend: dict[str, float] = {}
    total_new_reach = 0.0

    for i, region in enumerate(regions):
        md = market_data[region]
        x, y = float(sol[2 * i]), float(sol[2 * i + 1])
        base_tv = np.array(md["r_tv_list"], dtype=float)
        base_dg = np.array(md["r_dig_list"], dtype=float)
        new_tv = base_tv * (1.0 + x)
        new_dg = base_dg * (1.0 + y)
        new_tv_total, new_dg_total = float(np.sum(new_tv)), float(np.sum(new_dg))
        old_tv_total, old_dg_total = float(np.sum(base_tv)), float(np.sum(base_dg))
        new_tv_sp = new_tv_total * float(md["tv_cpr"])
        new_dg_sp = new_dg_total * float(md["digital_cpr"])
        new_sp = new_tv_sp + new_dg_sp
        market_new_spend[region] = new_sp
        market_new_tv_spend[region] = new_tv_sp
        market_new_dg_spend[region] = new_dg_sp

        ad_tv, ad_dg = adstock_function(new_tv, md["carryover_tv"]), adstock_function(new_dg, md["carryover_digital"])
        x_ad, y_ad = float(np.mean(ad_tv)) if len(ad_tv) else 0.0, float(np.mean(ad_dg)) if len(ad_dg) else 0.0
        x_std = (x_ad - md["mu_x"]) / md["sigma_x"] if abs(md["sigma_x"]) > 1e-12 else 0.0
        y_std = (y_ad - md["mu_y"]) / md["sigma_y"] if abs(md["sigma_y"]) > 1e-12 else 0.0
        x_log = 1.0 / (1.0 + np.exp(-3.5 * (x_std - md["mid_point_tv"])))
        y_log = 1.0 / (1.0 + np.exp(-3.5 * (y_std - md["mid_point_digital"])))
        x_fin = (x_log - md["min_x"]) / (md["max_x"] - md["min_x"]) if abs(md["max_x"] - md["min_x"]) > 1e-12 else 0.0
        y_fin = (y_log - md["min_y"]) / (md["max_y"] - md["min_y"]) if abs(md["max_y"] - md["min_y"]) > 1e-12 else 0.0
        prev_vol = float(md["prev_vol"])
        new_vol = float(md["beta_tv"] * x_fin + md["beta_digital"] * y_fin + md["C"])

        tv_split = new_tv_total / (new_tv_total + new_dg_total) if (new_tv_total + new_dg_total) > 0 else 0.0
        dg_split = 1.0 - tv_split
        old_tv_share = old_tv_total / (old_tv_total + old_dg_total) if (old_tv_total + old_dg_total) > 0 else 0.0
        old_dg_share = 1.0 - old_tv_share
        tv_delta = ((new_tv_total - old_tv_total) / old_tv_total * 100.0) if old_tv_total > 0 else 0.0
        dg_delta = ((new_dg_total - old_dg_total) / old_dg_total * 100.0) if old_dg_total > 0 else 0.0
        old_total_spend = float(md["current_spend"])
        uplift_abs = new_vol - prev_vol
        uplift_pct = (uplift_abs / prev_vol * 100.0) if abs(prev_vol) > 1e-12 else 0.0

        lim = limits_map.get(region, {})
        tv_min_reach = lim.get("tv_min_reach")
        tv_max_reach = lim.get("tv_max_reach")
        dg_min_reach = lim.get("dg_min_reach")
        dg_max_reach = lim.get("dg_max_reach")
        tv_min_spend = lim.get("min_tv_spend")
        tv_max_spend = lim.get("max_tv_spend")
        dg_min_spend = lim.get("min_digital_spend")
        dg_max_spend = lim.get("max_digital_spend")

        rows.append({
            "market": region,
            "new_budget_share": 0.0,
            "tv_split": round(tv_split, 4),
            "digital_split": round(dg_split, 4),
            "tv_delta_reach_pct": round(tv_delta, 2),
            "digital_delta_reach_pct": round(dg_delta, 2),
            "tv_change_pct_var": round(x * 100.0, 2),
            "digital_change_pct_var": round(y * 100.0, 2),
            "new_annual_tv_reach": round(new_tv_total, 2),
            "new_annual_digital_reach": round(new_dg_total, 2),
            "fy25_tv_reach": round(old_tv_total, 2),
            "fy25_digital_reach": round(old_dg_total, 2),
            "new_tv_share": round(tv_split, 4),
            "new_digital_share": round(dg_split, 4),
            "fy25_tv_share": round(old_tv_share, 4),
            "fy25_digital_share": round(old_dg_share, 4),
            "max_annual_tv_reach": None if tv_max_reach is None else round(float(tv_max_reach), 2),
            "min_annual_tv_reach": None if tv_min_reach is None else round(float(tv_min_reach), 2),
            "max_annual_digital_reach": None if dg_max_reach is None else round(float(dg_max_reach), 2),
            "min_annual_digital_reach": None if dg_min_reach is None else round(float(dg_min_reach), 2),
            "max_tv_spend": None if tv_max_spend is None else round(float(tv_max_spend), 2),
            "min_tv_spend": None if tv_min_spend is None else round(float(tv_min_spend), 2),
            "max_digital_spend": None if dg_max_spend is None else round(float(dg_max_spend), 2),
            "min_digital_spend": None if dg_min_spend is None else round(float(dg_min_spend), 2),
            "tv_cpr": round(float(md["tv_cpr"]), 4),
            "digital_cpr": round(float(md["digital_cpr"]), 4),
            "new_total_tv_spend": round(new_tv_sp, 2),
            "new_total_digital_spend": round(new_dg_sp, 2),
            "old_total_spend": round(old_total_spend, 2),
            "new_total_spend": round(new_sp, 2),
            "pct_change_total_spend": round(((new_sp - old_total_spend) / old_total_spend * 100.0) if abs(old_total_spend) > 1e-12 else 0.0, 2),
            "total_fy_volume": round(float(md.get("total_fy_volume", 0.0)), 2),
            "prev_volume": round(prev_vol, 2),
            "new_volume": round(new_vol, 2),
            "uplift_abs": round(uplift_abs, 2),
            "uplift_pct": round(uplift_pct, 2),
        })
        total_prev += prev_vol
        total_new += new_vol
        total_spend += new_sp
        total_new_reach += new_tv_total + new_dg_total
        weighted_tv += new_sp * tv_split
        weighted_dg += new_sp * dg_split

    if total_spend > 0:
        for r in rows:
            r["new_budget_share"] = round(market_new_spend[r["market"]] / total_spend, 4)
            old_sp = r["old_total_spend"]
            r["extra_budget_share"] = round(((r["new_total_spend"] - old_sp) / (total_spend - baseline_budget)) if abs(total_spend - baseline_budget) > 1e-12 else 0.0, 4)

    uplift_pct = ((total_new - total_prev) / total_prev * 100.0) if abs(total_prev) > 1e-12 else 0.0
    budget_constraint_val = _budget_constraint(sol, market_data, regions, B)
    return {
        "status": "ok",
        "message": f"Optimization completed using {meta['solver']}",
        "files": {
            "model_data": model_path.name,
            "market_weights": weights_path.name,
            "max_reach": max_path.name if max_path else None,
        },
        "selection": {
            "brand": brand,
            "markets": regions,
            "budget_increase_type": payload.budget_increase_type,
            "budget_increase_value": payload.budget_increase_value,
        },
        "summary": {
            "estimated_uplift_pct": round(uplift_pct, 2),
            "weighted_tv_share": round((weighted_tv / total_spend) if total_spend > 0 else 0.0, 4),
            "weighted_digital_share": round((weighted_dg / total_spend) if total_spend > 0 else 0.0, 4),
            "baseline_budget": round(baseline_budget, 2),
            "optimized_budget": round(total_spend, 2),
            "budget_constraint_value": round(float(budget_constraint_val), 6),
            "total_new_spend": round(total_spend, 2),
            "total_volume_uplift": round(total_new - total_prev, 2),
            "total_volume_uplift_pct": round(uplift_pct, 2),
            "solver_success": meta["success"],
            "solver_message": meta["message"],
        },
        "allocation_rows": rows,
    }


def _constraints_preview(payload: OptimizeAutoRequest) -> dict[str, Any]:
    ctx = _load_optimization_context(payload)
    files = ctx["files"]
    model_path, weights_path, max_path = files["model_data"], files["market_weights"], files["max_reach"]
    brand = ctx["brand"]
    regions = ctx["regions"]
    market_data = ctx["market_data"]
    limits_map = ctx["limits_map"]
    baseline_budget = float(ctx["baseline_budget"])
    target_budget = float(ctx["target_budget"])

    rows: list[dict[str, Any]] = []
    total_spend = 0.0
    weighted_tv = 0.0
    weighted_dg = 0.0

    for region in regions:
        md = market_data[region]
        tv_reach = float(np.sum(md["r_tv_list"]))
        dg_reach = float(np.sum(md["r_dig_list"]))
        tv_sp = tv_reach * float(md["tv_cpr"])
        dg_sp = dg_reach * float(md["digital_cpr"])
        total = tv_sp + dg_sp
        tv_split = tv_reach / (tv_reach + dg_reach) if (tv_reach + dg_reach) > 0 else 0.0
        dg_split = 1.0 - tv_split
        lim = limits_map.get(region, {})

        rows.append({
            "market": region,
            "new_budget_share": 0.0,
            "tv_split": round(tv_split, 4),
            "digital_split": round(dg_split, 4),
            "tv_delta_reach_pct": 0.0,
            "digital_delta_reach_pct": 0.0,
            "tv_change_pct_var": 0.0,
            "digital_change_pct_var": 0.0,
            "new_annual_tv_reach": round(tv_reach, 2),
            "new_annual_digital_reach": round(dg_reach, 2),
            "fy25_tv_reach": round(tv_reach, 2),
            "fy25_digital_reach": round(dg_reach, 2),
            "new_tv_share": round(tv_split, 4),
            "new_digital_share": round(dg_split, 4),
            "fy25_tv_share": round(tv_split, 4),
            "fy25_digital_share": round(dg_split, 4),
            "max_annual_tv_reach": round(float(lim["tv_max_reach"]), 2) if lim.get("tv_max_reach") is not None else None,
            "min_annual_tv_reach": round(float(lim["tv_min_reach"]), 2) if lim.get("tv_min_reach") is not None else None,
            "max_annual_digital_reach": round(float(lim["dg_max_reach"]), 2) if lim.get("dg_max_reach") is not None else None,
            "min_annual_digital_reach": round(float(lim["dg_min_reach"]), 2) if lim.get("dg_min_reach") is not None else None,
            "max_tv_spend": round(float(lim["max_tv_spend"]), 2) if lim.get("max_tv_spend") is not None else None,
            "min_tv_spend": round(float(lim["min_tv_spend"]), 2) if lim.get("min_tv_spend") is not None else None,
            "max_digital_spend": round(float(lim["max_digital_spend"]), 2) if lim.get("max_digital_spend") is not None else None,
            "min_digital_spend": round(float(lim["min_digital_spend"]), 2) if lim.get("min_digital_spend") is not None else None,
            "tv_cpr": round(float(md["tv_cpr"]), 4),
            "digital_cpr": round(float(md["digital_cpr"]), 4),
            "new_total_tv_spend": round(tv_sp, 2),
            "new_total_digital_spend": round(dg_sp, 2),
            "old_total_spend": round(total, 2),
            "new_total_spend": round(total, 2),
            "pct_change_total_spend": 0.0,
            "total_fy_volume": round(float(md.get("total_fy_volume", 0.0)), 2),
            "prev_volume": round(float(md.get("prev_vol", 0.0)), 2),
            "new_volume": round(float(md.get("prev_vol", 0.0)), 2),
            "uplift_abs": 0.0,
            "uplift_pct": 0.0,
            "extra_budget_share": 0.0,
        })
        total_spend += total
        weighted_tv += total * tv_split
        weighted_dg += total * dg_split

    if total_spend > 0:
        for r in rows:
            r["new_budget_share"] = round(r["new_total_spend"] / total_spend, 4)

    return {
        "status": "ok",
        "message": "Constraints preview ready",
        "files": {
            "model_data": model_path.name if model_path else "",
            "market_weights": weights_path.name if weights_path else "",
            "max_reach": max_path.name if max_path else None,
        },
        "selection": {
            "brand": brand,
            "markets": regions,
            "budget_increase_type": payload.budget_increase_type,
            "budget_increase_value": payload.budget_increase_value,
        },
        "summary": {
            "estimated_uplift_pct": 0.0,
            "weighted_tv_share": round((weighted_tv / total_spend) if total_spend > 0 else 0.0, 4),
            "weighted_digital_share": round((weighted_dg / total_spend) if total_spend > 0 else 0.0, 4),
            "baseline_budget": round(baseline_budget, 2),
            "optimized_budget": round(target_budget, 2),
            "budget_constraint_value": round(float(target_budget - total_spend), 6),
            "total_new_spend": round(total_spend, 2),
            "total_volume_uplift": 0.0,
            "total_volume_uplift_pct": 0.0,
            "solver_success": None,
            "solver_message": "Preview mode",
        },
        "allocation_rows": rows,
    }


def _build_s_curves(payload: SCurveAutoRequest) -> dict[str, Any]:
    """
    Build diminishing-return S-curves using the same transformed response mechanics as optimization.
    Mirrors Streamlit post-model logic by varying one channel at a time while holding the other fixed.
    """
    ctx = _load_optimization_context(
        OptimizeAutoRequest(
            selected_brand=payload.selected_brand,
            selected_markets=payload.selected_markets,
            budget_increase_type="percentage",
            budget_increase_value=0.0,
            market_overrides={},
        )
    )
    brand = ctx["brand"]
    regions = ctx["regions"]
    market_data = ctx["market_data"]
    limits_map = ctx["limits_map"]

    points = max(21, min(int(payload.points), 201))
    min_scale = float(_finite(payload.min_scale, 0.2))
    max_scale = float(_finite(payload.max_scale, 2.5))
    min_scale = max(0.05, min(min_scale, 10.0))
    max_scale = max(0.1, min(max_scale, 10.0))
    if max_scale <= min_scale:
        max_scale = min_scale + 0.5

    baseline_volume = float(sum(_finite(market_data[r].get("prev_vol", 0.0), 0.0) for r in regions))
    baseline_spend = float(sum(_finite(market_data[r].get("current_spend", 0.0), 0.0) for r in regions))
    baseline_tv_reach = float(sum(float(np.sum(np.array(market_data[r]["r_tv_list"], dtype=float))) for r in regions))
    baseline_digital_reach = float(sum(float(np.sum(np.array(market_data[r]["r_dig_list"], dtype=float))) for r in regions))
    equation_markets: list[dict[str, Any]] = []
    for region in regions:
        md = market_data.get(region)
        if not md:
            continue
        equation_markets.append(
            {
                "market": region,
                "c": round(float(_finite(md.get("C", 0.0), 0.0)), 6),
                "beta_tv": round(float(_finite(md.get("beta_tv", 0.0), 0.0)), 6),
                "beta_digital": round(float(_finite(md.get("beta_digital", 0.0), 0.0)), 6),
                "carryover_tv": round(float(_finite(md.get("carryover_tv", 0.0), 0.0)), 6),
                "carryover_digital": round(float(_finite(md.get("carryover_digital", 0.0), 0.0)), 6),
                "midpoint_tv": round(float(_finite(md.get("mid_point_tv", 0.0), 0.0)), 6),
                "midpoint_digital": round(float(_finite(md.get("mid_point_digital", 0.0), 0.0)), 6),
                "mu_tv": round(float(_finite(md.get("mu_x", 0.0), 0.0)), 6),
                "sigma_tv": round(float(_finite(md.get("sigma_x", 1.0), 1.0)), 6),
                "mu_digital": round(float(_finite(md.get("mu_y", 0.0), 0.0)), 6),
                "sigma_digital": round(float(_finite(md.get("sigma_y", 1.0), 1.0)), 6),
                "min_tv": round(float(_finite(md.get("min_x", 0.0), 0.0)), 6),
                "max_tv": round(float(_finite(md.get("max_x", 1.0), 1.0)), 6),
                "min_digital": round(float(_finite(md.get("min_y", 0.0), 0.0)), 6),
                "max_digital": round(float(_finite(md.get("max_y", 1.0), 1.0)), 6),
            }
        )

    def _sum_limit(limit_key: str, baseline: float, fallback_scale: float) -> float:
        total = 0.0
        found = False
        for region in regions:
            lim = limits_map.get(region, {})
            raw = lim.get(limit_key)
            val = float(_finite(raw, 0.0))
            if val > 0:
                total += val
                found = True
        if found and total > 0:
            return total
        return max(1e-6, baseline * fallback_scale)

    tv_min_target = _sum_limit("tv_min_reach", baseline_tv_reach, min_scale)
    tv_max_target = _sum_limit("tv_max_reach", baseline_tv_reach, max_scale)
    dg_min_target = _sum_limit("dg_min_reach", baseline_digital_reach, min_scale)
    dg_max_target = _sum_limit("dg_max_reach", baseline_digital_reach, max_scale)

    if tv_max_target <= tv_min_target:
        tv_max_target = tv_min_target + max(1e-6, baseline_tv_reach * 0.1)
    if dg_max_target <= dg_min_target:
        dg_max_target = dg_min_target + max(1e-6, baseline_digital_reach * 0.1)

    tv_targets = np.linspace(tv_min_target, tv_max_target, points)
    dg_targets = np.linspace(dg_min_target, dg_max_target, points)

    def _aggregate_for_scale(tv_scale: float, dg_scale: float) -> tuple[float, float, float, float]:
        total_volume = 0.0
        total_spend = 0.0
        total_tv_reach = 0.0
        total_digital_reach = 0.0
        for region in regions:
            md = market_data[region]
            tv_change = float(tv_scale - 1.0)
            dg_change = float(dg_scale - 1.0)
            pred = float(_predict_region_volume(md, tv_change, dg_change))
            total_volume += max(0.0, pred)
            tv_base = float(np.sum(np.array(md["r_tv_list"], dtype=float)))
            dg_base = float(np.sum(np.array(md["r_dig_list"], dtype=float)))
            total_tv_reach += tv_base * tv_scale
            total_digital_reach += dg_base * dg_scale
            total_spend += tv_base * float(md["tv_cpr"]) * tv_scale + dg_base * float(md["digital_cpr"]) * dg_scale
        return float(total_volume), float(total_spend), float(total_tv_reach), float(total_digital_reach)

    tv_curve: list[dict[str, float]] = []
    dg_curve: list[dict[str, float]] = []

    for tv_target in tv_targets:
        tv_scale = float(tv_target / baseline_tv_reach) if baseline_tv_reach > 1e-12 else 1.0
        tv_scale = float(np.clip(tv_scale, 0.01, 10.0))
        tv_vol, tv_sp, tv_reach, tv_dg_reach = _aggregate_for_scale(tv_scale, 1.0)
        tv_curve.append(
            {
                "scale": round(float(tv_scale), 6),
                "pct_change_input": round(((float(tv_target) - baseline_tv_reach) / baseline_tv_reach * 100.0) if baseline_tv_reach > 1e-12 else 0.0, 2),
                "predicted_volume": round(tv_vol, 4),
                "predicted_spend": round(tv_sp, 4),
                "tv_reach": round(tv_reach, 4),
                "digital_reach": round(tv_dg_reach, 4),
                "volume_uplift_abs": round(tv_vol - baseline_volume, 4),
                "volume_uplift_pct": round(((tv_vol - baseline_volume) / baseline_volume * 100.0) if baseline_volume > 1e-12 else 0.0, 4),
                "spend_change_pct": round(((tv_sp - baseline_spend) / baseline_spend * 100.0) if baseline_spend > 1e-12 else 0.0, 4),
            }
        )
    for dg_target in dg_targets:
        dg_scale = float(dg_target / baseline_digital_reach) if baseline_digital_reach > 1e-12 else 1.0
        dg_scale = float(np.clip(dg_scale, 0.01, 10.0))
        dg_vol, dg_sp, dg_tv_reach, dg_reach = _aggregate_for_scale(1.0, dg_scale)
        dg_curve.append(
            {
                "scale": round(float(dg_scale), 6),
                "pct_change_input": round(((float(dg_target) - baseline_digital_reach) / baseline_digital_reach * 100.0) if baseline_digital_reach > 1e-12 else 0.0, 2),
                "predicted_volume": round(dg_vol, 4),
                "predicted_spend": round(dg_sp, 4),
                "tv_reach": round(dg_tv_reach, 4),
                "digital_reach": round(dg_reach, 4),
                "volume_uplift_abs": round(dg_vol - baseline_volume, 4),
                "volume_uplift_pct": round(((dg_vol - baseline_volume) / baseline_volume * 100.0) if baseline_volume > 1e-12 else 0.0, 4),
                "spend_change_pct": round(((dg_sp - baseline_spend) / baseline_spend * 100.0) if baseline_spend > 1e-12 else 0.0, 4),
            }
        )

    return {
        "status": "ok",
        "message": "S-curves generated using transformed model response.",
        "selection": {
            "brand": brand,
            "markets": regions,
        },
        "summary": {
            "baseline_volume": round(baseline_volume, 4),
            "baseline_spend": round(baseline_spend, 4),
            "baseline_tv_reach": round(baseline_tv_reach, 4),
            "baseline_digital_reach": round(baseline_digital_reach, 4),
            "tv_min_reach": round(tv_min_target, 4),
            "tv_max_reach": round(tv_max_target, 4),
            "digital_min_reach": round(dg_min_target, 4),
            "digital_max_reach": round(dg_max_target, 4),
            "points": points,
            "min_scale": round(min_scale, 4),
            "max_scale": round(max_scale, 4),
        },
        "equation_map": {
            "formula": "V = C + beta_tv * norm(logistic(z_tv)) + beta_digital * norm(logistic(z_digital))",
            "notes": [
                "z_tv and z_digital are standardized adstocked reach series.",
                "logistic(z) = 1 / (1 + exp(-3.5 * (z - midpoint))).",
                "norm(value) rescales with transformed-base min/max used in the fitted model.",
            ],
            "markets": equation_markets,
        },
        "curves": {
            "tv": tv_curve,
            "digital": dg_curve,
        },
    }


def _friendly_contribution_name(raw: str) -> str:
    name = str(raw).replace("_contribution", "").strip()
    if not name:
        return "Unknown"
    if name == "TV_Reach":
        return "TV Reach"
    if name == "Digital_Reach":
        return "Digital Reach"
    return name.replace("_", " ").strip()


def _build_contribution_insights(payload: ContributionAutoRequest) -> dict[str, Any]:
    cfg = _build_auto_config()
    files = _detect_input_files()
    model_path, weights_path = files["model_data"], files["market_weights"]
    if model_path is None or weights_path is None:
        raise HTTPException(status_code=400, detail="Missing required files in results folder.")

    brand = payload.selected_brand.strip()
    if brand not in cfg["markets_by_brand"]:
        raise HTTPException(status_code=400, detail="Selected brand is not available in model results.")
    brand_markets = cfg["markets_by_brand"][brand]
    selected_market = payload.selected_market.strip() if payload.selected_market else ""
    if selected_market and selected_market not in brand_markets:
        raise HTTPException(status_code=400, detail="Selected market is not available for the brand.")
    if not selected_market:
        selected_market = brand_markets[0] if brand_markets else ""
    if not selected_market:
        raise HTTPException(status_code=400, detail="No markets available for selected brand.")

    model_df = _read_model_data(model_path)
    model_df.columns = [str(c).strip() for c in model_df.columns]
    weights_df = _read_market_weights(weights_path)
    weights_df.columns = [str(c).strip() for c in weights_df.columns]
    bw = weights_df[weights_df["Brand"].astype(str).str.strip() == brand].copy()
    if bw.empty:
        raise HTTPException(status_code=400, detail="No rows found for selected brand in model results.")

    transformed = apply_transformations_with_contributions(model_df, bw)
    if transformed.empty:
        raise HTTPException(status_code=400, detail="Contribution transformation returned no rows.")
    transformed.columns = [str(c).strip() for c in transformed.columns]
    tdf = transformed[
        (transformed["Brand"].astype(str).str.strip() == brand)
        & (transformed["Region"].astype(str).str.strip() == selected_market)
    ].copy()
    if tdf.empty:
        raise HTTPException(status_code=400, detail="No contribution rows found for selected market.")

    fiscal_values = sorted(tdf["Fiscal Year"].dropna().unique(), key=_fiscal_key)
    if fiscal_values:
        latest_fy = fiscal_values[-1]
        tdf = tdf[tdf["Fiscal Year"] == latest_fy].copy()
    else:
        latest_fy = ""

    contribution_cols = [c for c in tdf.columns if str(c).endswith("_contribution")]
    if not contribution_cols:
        raise HTTPException(status_code=400, detail="No contribution columns were found in transformed data.")
    tdf[contribution_cols] = tdf[contribution_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)

    beta0_total = float(pd.to_numeric(tdf.get("beta0", 0.0), errors="coerce").fillna(0.0).sum()) if "beta0" in tdf.columns else 0.0
    contribution_totals = tdf[contribution_cols].sum(axis=0)
    prediction_total = float(beta0_total + float(contribution_totals.sum()))

    items: list[dict[str, Any]] = []
    if abs(beta0_total) > 1e-12:
        items.append(
            {
                "variable": "base",
                "label": "Base",
                "absolute_contribution": round(beta0_total, 6),
                "share_pct": round((beta0_total / prediction_total * 100.0) if abs(prediction_total) > 1e-12 else 0.0, 4),
            }
        )

    for col, value in contribution_totals.items():
        val = float(_finite(value, 0.0))
        if abs(val) <= 1e-12:
            continue
        items.append(
            {
                "variable": str(col).replace("_contribution", ""),
                "label": _friendly_contribution_name(str(col)),
                "absolute_contribution": round(val, 6),
                "share_pct": round((val / prediction_total * 100.0) if abs(prediction_total) > 1e-12 else 0.0, 4),
            }
        )

    items_sorted = sorted(items, key=lambda x: abs(float(x.get("absolute_contribution", 0.0))), reverse=True)
    top_n = max(3, min(int(payload.top_n), 20))
    top_items = items_sorted[:top_n]
    other_items = items_sorted[top_n:]
    if other_items:
        other_abs = float(sum(float(x.get("absolute_contribution", 0.0)) for x in other_items))
        other_share = float(sum(float(x.get("share_pct", 0.0)) for x in other_items))
        top_items.append(
            {
                "variable": "other",
                "label": "Other",
                "absolute_contribution": round(other_abs, 6),
                "share_pct": round(other_share, 4),
            }
        )

    return {
        "status": "ok",
        "message": "Contribution insights generated.",
        "selection": {
            "brand": brand,
            "market": selected_market,
            "fiscal_year": str(latest_fy),
        },
        "summary": {
            "prediction_total": round(prediction_total, 6),
            "component_count": len(top_items),
        },
        "items": top_items,
    }


def _build_yoy_growth_insights(payload: YoyGrowthRequest) -> dict[str, Any]:
    cfg = _build_auto_config()
    files = _detect_input_files()
    model_path, weights_path = files["model_data"], files["market_weights"]
    if model_path is None or weights_path is None:
        raise HTTPException(status_code=400, detail="Missing required files in results folder.")

    brand = payload.selected_brand.strip()
    if brand not in cfg["markets_by_brand"]:
        raise HTTPException(status_code=400, detail="Selected brand is not available in model results.")
    brand_markets = cfg["markets_by_brand"][brand]
    selected_market = payload.selected_market.strip() if payload.selected_market else ""
    if selected_market and selected_market not in brand_markets:
        raise HTTPException(status_code=400, detail="Selected market is not available for the brand.")
    if not selected_market:
        selected_market = brand_markets[0] if brand_markets else ""
    if not selected_market:
        raise HTTPException(status_code=400, detail="No markets available for selected brand.")

    model_df = _read_model_data(model_path)
    model_df.columns = [str(c).strip() for c in model_df.columns]
    weights_df = _read_market_weights(weights_path)
    weights_df.columns = [str(c).strip() for c in weights_df.columns]
    bw = weights_df[weights_df["Brand"].astype(str).str.strip() == brand].copy()
    if bw.empty:
        raise HTTPException(status_code=400, detail="No rows found for selected brand in model results.")

    transformed = apply_transformations_with_contributions(model_df, bw)
    if transformed.empty:
        raise HTTPException(status_code=400, detail="YoY transformation returned no rows.")
    transformed.columns = [str(c).strip() for c in transformed.columns]
    req_cols = {"Brand", "Region", "Fiscal Year"}
    if not req_cols.issubset(set(transformed.columns)):
        raise HTTPException(status_code=400, detail="Transformed data missing Brand/Region/Fiscal Year columns.")

    tdf = transformed[
        (transformed["Brand"].astype(str).str.strip() == brand)
        & (transformed["Region"].astype(str).str.strip() == selected_market)
    ].copy()
    if tdf.empty:
        raise HTTPException(status_code=400, detail="No transformed rows found for selected market.")

    y_candidates = bw["Y"].dropna().astype(str).str.strip().tolist() if "Y" in bw.columns else []
    y_col = next((c for c in y_candidates if c in tdf.columns), "")
    if not y_col:
        for fallback in ("Volume", "Sales_Qty_Total", "MainMedia_predY"):
            if fallback in tdf.columns:
                y_col = fallback
                break
    if not y_col:
        raise HTTPException(status_code=400, detail="Could not identify target volume column for YoY.")

    contribution_cols = [c for c in tdf.columns if str(c).endswith("_contribution")]
    numeric_cols = [y_col, "TV_Reach", "Digital_Reach", "beta0", *contribution_cols]
    for col in numeric_cols:
        if col not in tdf.columns:
            tdf[col] = 0.0
        tdf[col] = pd.to_numeric(tdf[col], errors="coerce").fillna(0.0)

    fiscal_values = sorted(tdf["Fiscal Year"].dropna().astype(str).unique().tolist(), key=_fiscal_key)
    if not fiscal_values:
        raise HTTPException(status_code=400, detail="Unable to compute YoY series.")

    items: list[dict[str, Any]] = []
    per_fy_components: dict[str, dict[str, float]] = {}
    prev_actual = None
    prev_pred = None

    for fy in fiscal_values:
        fy_df = tdf[tdf["Fiscal Year"].astype(str) == fy].copy()
        actual_volume = float(_finite(fy_df[y_col].sum(), 0.0))
        tv_reach = float(_finite(fy_df["TV_Reach"].sum(), 0.0))
        digital_reach = float(_finite(fy_df["Digital_Reach"].sum(), 0.0))
        beta0_total = float(_finite(fy_df["beta0"].sum(), 0.0))
        contribution_totals = fy_df[contribution_cols].sum(axis=0) if contribution_cols else pd.Series(dtype=float)
        predicted_volume = float(beta0_total + float(contribution_totals.sum()))

        yoy_actual = 0.0
        if prev_actual is not None and abs(prev_actual) > 1e-12:
            yoy_actual = ((actual_volume - prev_actual) / prev_actual) * 100.0
        yoy_pred = 0.0
        if prev_pred is not None and abs(prev_pred) > 1e-12:
            yoy_pred = ((predicted_volume - prev_pred) / prev_pred) * 100.0
        prev_actual = actual_volume
        prev_pred = predicted_volume

        comp_map: dict[str, float] = {"Base": beta0_total}
        for col, value in contribution_totals.items():
            comp_map[_friendly_contribution_name(str(col))] = float(_finite(value, 0.0))
        per_fy_components[fy] = comp_map

        items.append(
            {
                "fiscal_year": str(fy),
                "volume_mn": round(actual_volume / 1_000_000.0, 4),
                "predicted_volume_mn": round(predicted_volume / 1_000_000.0, 4),
                "reach_mn": round((tv_reach + digital_reach) / 1_000_000.0, 4),
                "yoy_growth_pct": round(float(yoy_actual), 4),
                "predicted_yoy_growth_pct": round(float(yoy_pred), 4),
            }
        )

    waterfall_payload: dict[str, Any] | None = None
    if len(fiscal_values) >= 2:
        from_fy = str(fiscal_values[-2])
        to_fy = str(fiscal_values[-1])
        from_map = per_fy_components.get(from_fy, {})
        to_map = per_fy_components.get(to_fy, {})
        keys = sorted(set(from_map.keys()) | set(to_map.keys()))
        raw_items: list[dict[str, float | str]] = []
        for key in keys:
            delta = float(_finite(to_map.get(key, 0.0), 0.0) - _finite(from_map.get(key, 0.0), 0.0))
            if abs(delta) <= 1e-12:
                continue
            raw_items.append(
                {
                    "label": key,
                    "delta_abs": delta,
                    "delta_mn": delta / 1_000_000.0,
                }
            )

        raw_items = sorted(raw_items, key=lambda x: abs(float(x["delta_abs"])), reverse=True)
        top_n = 8
        top = raw_items[:top_n]
        rest = raw_items[top_n:]
        if rest:
            other_abs = float(sum(float(x["delta_abs"]) for x in rest))
            top.append({"label": "Other Drivers", "delta_abs": other_abs, "delta_mn": other_abs / 1_000_000.0})

        fy_lookup = {str(item["fiscal_year"]): item for item in items}
        from_item = fy_lookup.get(from_fy, {})
        to_item = fy_lookup.get(to_fy, {})
        total_change_mn = float(_finite(to_item.get("volume_mn", 0.0), 0.0) - _finite(from_item.get("volume_mn", 0.0), 0.0))
        total_change_abs = total_change_mn * 1_000_000.0
        out_items: list[dict[str, Any]] = []
        for row in top:
            delta_abs = float(_finite(row.get("delta_abs", 0.0), 0.0))
            out_items.append(
                {
                    "label": str(row.get("label", "")),
                    "delta_mn": round(float(_finite(row.get("delta_mn", 0.0), 0.0)), 4),
                    "share_of_total_change_pct": round((delta_abs / total_change_abs * 100.0) if abs(total_change_abs) > 1e-12 else 0.0, 2),
                }
            )
        waterfall_payload = {
            "from_fiscal_year": from_fy,
            "to_fiscal_year": to_fy,
            "total_change_mn": round(total_change_mn, 4),
            "items": out_items,
        }

    latest_item = items[-1]
    return {
        "status": "ok",
        "message": "YoY growth insights generated.",
        "selection": {
            "brand": brand,
            "market": selected_market,
        },
        "summary": {
            "latest_fiscal_year": latest_item["fiscal_year"],
            "latest_volume_mn": latest_item["volume_mn"],
            "latest_reach_mn": latest_item["reach_mn"],
            "latest_yoy_growth_pct": latest_item["yoy_growth_pct"],
            "latest_predicted_volume_mn": latest_item.get("predicted_volume_mn", 0.0),
            "latest_predicted_yoy_growth_pct": latest_item.get("predicted_yoy_growth_pct", 0.0),
            "points": len(items),
        },
        "items": items,
        "waterfall": waterfall_payload,
    }


def _detect_volume_column(df: pd.DataFrame) -> str | None:
    for col in ("Volume", "Sales_Qty_Total"):
        if col in df.columns:
            return col
    return None


def _region_latest_yoy_from_raw(model_df: pd.DataFrame, brand: str, region: str) -> dict[str, Any]:
    df = model_df[
        (model_df["Brand"].astype(str).str.strip() == brand)
        & (model_df["Region"].astype(str).str.strip() == region)
    ].copy()
    if df.empty:
        return {"latest_fiscal_year": "", "latest_volume_mn": 0.0, "yoy_growth_pct": 0.0}
    vcol = _detect_volume_column(df)
    if not vcol or "Fiscal Year" not in df.columns:
        return {"latest_fiscal_year": "", "latest_volume_mn": 0.0, "yoy_growth_pct": 0.0}

    df[vcol] = pd.to_numeric(df[vcol], errors="coerce").fillna(0.0)
    grouped = df.groupby("Fiscal Year", as_index=False)[vcol].sum()
    grouped = grouped.sort_values("Fiscal Year", key=lambda s: s.map(_fiscal_key))
    if grouped.empty:
        return {"latest_fiscal_year": "", "latest_volume_mn": 0.0, "yoy_growth_pct": 0.0}

    latest_fy = str(grouped.iloc[-1]["Fiscal Year"])
    latest_vol = float(_finite(grouped.iloc[-1][vcol], 0.0))
    yoy = 0.0
    if len(grouped) >= 2:
        prev = float(_finite(grouped.iloc[-2][vcol], 0.0))
        yoy = ((latest_vol - prev) / prev * 100.0) if abs(prev) > 1e-12 else 0.0
    return {
        "latest_fiscal_year": latest_fy,
        "latest_volume_mn": latest_vol / 1_000_000.0,
        "yoy_growth_pct": float(yoy),
    }


def _fallback_ai_insights_text(
    brand: str,
    leaders: list[str],
    core: list[str],
    recovery: list[str],
    rows: list[dict[str, Any]],
) -> str:
    top_inc = [r for r in rows if str(r.get("recommendation_action", "")).startswith("Increase")]
    top_red = [r for r in rows if str(r.get("recommendation_action", "")).startswith("Reduce")]
    top_inc = sorted(top_inc, key=lambda r: float(r.get("headroom_pct", 0.0)), reverse=True)[:3]
    top_red = sorted(top_red, key=lambda r: float(r.get("headroom_pct", 0.0)))[:3]
    fmt = lambda rs: ", ".join([str(r.get("market")) for r in rs]) if rs else "None"
    return (
        f"Subject: {brand} State Performance Note\n\n"
        "Executive Summary\n"
        f"- Growth Leaders: {', '.join(leaders) if leaders else 'None'}\n"
        f"- Stable Core: {', '.join(core) if core else 'None'}\n"
        f"- Recovery Priority: {', '.join(recovery) if recovery else 'None'}\n\n"
        "Where To Increase\n"
        f"- {fmt(top_inc)}\n\n"
        "Where To Protect / Reduce\n"
        f"- {fmt(top_red)}\n\n"
        "Action Focus\n"
        "- Scale in high-headroom states with positive momentum.\n"
        "- Rebalance spend in low-headroom or negative-momentum states.\n"
        "- Keep core states stable and optimize channel mix quality.\n"
    )


def _clip_text(value: str, max_len: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _compact_market_for_ai(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "state": str(row.get("market", "")),
        "yoy_growth_pct": round(float(_finite(row.get("yoy_growth_pct", 0.0), 0.0)), 2),
        "headroom_pct": round(float(_finite(row.get("headroom_pct", 0.0), 0.0)), 2),
        "tv_share_pct": round(float(_finite(row.get("tv_share_pct", 0.0), 0.0)), 2),
        "digital_share_pct": round(float(_finite(row.get("digital_share_pct", 0.0), 0.0)), 2),
        "action": str(row.get("recommendation_action", "Hold and optimize mix")),
    }


def _build_ai_insights_prompt(
    brand: str,
    rows: list[dict[str, Any]],
    leaders: list[str],
    core: list[str],
    recovery: list[str],
    focus_prompt: str,
) -> str:
    parsed_focus = _extract_json_object(focus_prompt)
    if isinstance(parsed_focus, dict):
        compact_focus: dict[str, Any] = {
            "insights_brand": _clip_text(str(parsed_focus.get("insights_brand", "")), 40),
            "insights_market": _clip_text(str(parsed_focus.get("insights_market", "")), 40),
            "s_curve": parsed_focus.get("s_curve", {}),
            "contribution_top": parsed_focus.get("contribution_top", []),
            "yoy": parsed_focus.get("yoy", {}),
        }
    else:
        compact_focus = {"user_note": _clip_text(focus_prompt, 220)}

    if not rows:
        compact_payload: dict[str, Any] = {"brand": brand, "markets_count": 0, "insights_snapshot": compact_focus}
    else:
        by_yoy_desc = sorted(rows, key=lambda r: float(_finite(r.get("yoy_growth_pct", 0.0), 0.0)), reverse=True)
        by_yoy_asc = sorted(rows, key=lambda r: float(_finite(r.get("yoy_growth_pct", 0.0), 0.0)))
        by_headroom_desc = sorted(rows, key=lambda r: float(_finite(r.get("headroom_pct", 0.0), 0.0)), reverse=True)
        yoy_vals = np.array([float(_finite(r.get("yoy_growth_pct", 0.0), 0.0)) for r in rows], dtype=float)
        head_vals = np.array([float(_finite(r.get("headroom_pct", 0.0), 0.0)) for r in rows], dtype=float)
        action_counts: dict[str, int] = {}
        for r in rows:
            k = str(r.get("recommendation_action", "Hold and optimize mix"))
            action_counts[k] = action_counts.get(k, 0) + 1
        compact_payload = {
            "brand": brand,
            "markets_count": len(rows),
            "insights_snapshot": compact_focus,
            "cluster_names": {
                "growth_leaders": leaders,
                "stable_core": core,
                "recovery_priority": recovery,
            },
            "portfolio_stats": {
                "avg_yoy_growth_pct": round(float(np.mean(yoy_vals)) if yoy_vals.size else 0.0, 2),
                "median_yoy_growth_pct": round(float(np.median(yoy_vals)) if yoy_vals.size else 0.0, 2),
                "min_yoy_growth_pct": round(float(np.min(yoy_vals)) if yoy_vals.size else 0.0, 2),
                "max_yoy_growth_pct": round(float(np.max(yoy_vals)) if yoy_vals.size else 0.0, 2),
                "avg_headroom_pct": round(float(np.mean(head_vals)) if head_vals.size else 0.0, 2),
                "median_headroom_pct": round(float(np.median(head_vals)) if head_vals.size else 0.0, 2),
            },
            "action_counts": action_counts,
            "top_growth_states": [_compact_market_for_ai(r) for r in by_yoy_desc[:5]],
            "top_risk_states": [_compact_market_for_ai(r) for r in by_yoy_asc[:5]],
            "top_headroom_states": [_compact_market_for_ai(r) for r in by_headroom_desc[:5]],
        }

    return (
        "You are an expert MMM business advisor for brand-state planning.\n"
        "You must produce strict JSON summary fields using only provided data.\n"
        "Do not invent states, metrics, or causal claims.\n"
        "Keep language concise, practical, and business-facing.\n"
        "\n"
        "Return strict JSON only with this exact schema and keys:\n"
        "{\n"
        "  \"headline\": \"string\",\n"
        "  \"portfolio_takeaway\": \"string\",\n"
        "  \"increase_markets\": [{\"state\":\"string\",\"channel\":\"TV|Digital|Mix\",\"reason\":\"string\",\"action\":\"string\"}],\n"
        "  \"decrease_markets\": [{\"state\":\"string\",\"channel\":\"TV|Digital|Mix\",\"reason\":\"string\",\"action\":\"string\"}],\n"
        "  \"channel_notes\": {\"tv\":\"string\",\"digital\":\"string\"},\n"
        "  \"risks\": [\"string\"],\n"
        "  \"evidence\": [\"string\"]\n"
        "}\n"
        "Rules:\n"
        "- No markdown. No prose outside JSON.\n"
        "- Use only states present in DATA.\n"
        "- `increase_markets` and `decrease_markets` should be distinct state sets where possible.\n"
        "- Max 6 entries per market list.\n"
        "- `portfolio_takeaway` should be analytical and not a copy of list items.\n"
        "- `evidence` should cite concrete portfolio facts from DATA (YoY/headroom/effectiveness patterns).\n"
        f"DATA:\n{json.dumps(compact_payload, ensure_ascii=True)}"
    )


def _normalize_ai_action_list(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw[:4]:
        if not isinstance(item, dict):
            continue
        state = _clip_text(str(item.get("state", "")).strip(), 40)
        why = _clip_text(str(item.get("why", "")).strip(), 120)
        action = _clip_text(str(item.get("action", "")).strip(), 120)
        if not state:
            continue
        out.append({"state": state, "why": why or "N/A", "action": action or "N/A"})
    return out


def _sanitize_channel_name(raw: Any) -> str:
    val = str(raw or "").strip().lower()
    if val in {"tv", "television"}:
        return "TV"
    if val in {"digital", "dig"}:
        return "Digital"
    return "Mix"


def _normalize_summary_market_rows(raw: Any, max_items: int = 6) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        state = _clip_text(str(item.get("state", "")).strip(), 40)
        if not state:
            continue
        key = state.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "state": state,
                "channel": _sanitize_channel_name(item.get("channel")),
                "reason": _clip_text(str(item.get("reason", "")).strip() or "State-level signal requires review.", 260),
                "action": _clip_text(str(item.get("action", "")).strip() or "Adjust spend and channel mix in a controlled range.", 260),
            }
        )
        if len(out) >= max_items:
            break
    return out


def _normalize_string_list(raw: Any, max_items: int, item_max_len: int) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        text = _clip_text(str(item or "").strip(), item_max_len)
        if text:
            out.append(text)
        if len(out) >= max_items:
            break
    return out


def _parse_ai_insights_summary_json(text: str) -> dict[str, Any] | None:
    raw_obj = _extract_json_object(text or "")
    if not isinstance(raw_obj, dict):
        return None
    raw = dict(raw_obj)
    for wrapper_key in ("summary", "output", "result", "data"):
        nested = raw.get(wrapper_key)
        if isinstance(nested, dict):
            raw = nested
            break

    def _pick(*keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in raw:
                return raw.get(key)
        return default

    has_any = any(
        k in raw
        for k in (
            "headline",
            "portfolio_takeaway",
            "increase_markets",
            "decrease_markets",
            "channel_notes",
            "risks",
            "evidence",
        )
    )
    if not has_any and not any(
        k in raw
        for k in (
            "title",
            "takeaway",
            "executive_summary",
            "increase",
            "increase_states",
            "decrease",
            "decrease_states",
            "channel_summary",
            "key_risks",
            "proof_points",
        )
    ):
        return None
    channel_notes_raw = _pick("channel_notes", "channel_summary", default={})
    if isinstance(channel_notes_raw, list):
        channel_notes_raw = {"tv": " ".join([str(x) for x in channel_notes_raw[:2]])}
    channel_notes = channel_notes_raw if isinstance(channel_notes_raw, dict) else {}
    headline = _clip_text(str(_pick("headline", "title", default="")).strip(), 180)
    takeaway = _clip_text(str(_pick("portfolio_takeaway", "takeaway", "executive_summary", default="")).strip(), 1600)
    if not headline:
        headline = "Portfolio Performance Snapshot"
    if not takeaway:
        takeaway = "Portfolio shows mixed momentum across states and requires selective allocation adjustments."
    increase_raw = _pick("increase_markets", "increase", "increase_states", default=[])
    decrease_raw = _pick("decrease_markets", "decrease", "decrease_states", default=[])
    risks_raw = _pick("risks", "key_risks", default=[])
    evidence_raw = _pick("evidence", "proof_points", default=[])
    if isinstance(risks_raw, str):
        risks_raw = [s.strip("- ").strip() for s in str(risks_raw).split("\n") if s.strip()]
    if isinstance(evidence_raw, str):
        evidence_raw = [s.strip("- ").strip() for s in str(evidence_raw).split("\n") if s.strip()]
    return {
        "headline": headline,
        "portfolio_takeaway": takeaway,
        "increase_markets": _normalize_summary_market_rows(increase_raw, max_items=6),
        "decrease_markets": _normalize_summary_market_rows(decrease_raw, max_items=6),
        "channel_notes": {
            "tv": _clip_text(str(channel_notes.get("tv", channel_notes.get("television", ""))).strip(), 600),
            "digital": _clip_text(str(channel_notes.get("digital", channel_notes.get("dig", ""))).strip(), 600),
        },
        "risks": _normalize_string_list(risks_raw, max_items=6, item_max_len=220),
        "evidence": _normalize_string_list(evidence_raw, max_items=8, item_max_len=220),
    }


def _parse_ai_insights_sections(text: str) -> dict[str, Any] | None:
    payload = str(text or "").strip()
    if not payload:
        return None
    normalized = payload.replace("\r\n", "\n")
    if normalized.startswith("```"):
        normalized = re.sub(r"^```[a-zA-Z]*\n", "", normalized)
        normalized = re.sub(r"\n```$", "", normalized).strip()

    heading_alias: dict[str, str] = {
        "q1 executive summary": "q1_executive_summary",
        "q2 yoy position": "q2_yoy_position",
        "q3 channel effectiveness (tv vs digital)": "q3_channel_effectiveness",
        "q4 where to increase": "q4_where_to_increase",
        "q5 where to decrease / rebalance": "q5_where_to_decrease_rebalance",
        "q6 immediate actions": "q6_immediate_actions",
        "executive summary": "executive_summary",
        "portfolio position": "portfolio_position",
        "state clusters": "state_clusters",
        "where to increase": "where_to_increase",
        "where to protect / reduce": "where_to_protect_reduce",
        "where to protect/reduce": "where_to_protect_reduce",
        "immediate actions": "immediate_actions",
        "action focus": "action_focus",
    }
    heading_pattern = (
        r"Q1 Executive Summary|Q2 YoY Position|Q3 Channel Effectiveness \(TV vs Digital\)|"
        r"Q4 Where To Increase|Q5 Where To Decrease\s*/\s*Rebalance|Q6 Immediate Actions|"
        r"Executive Summary|Portfolio Position|State Clusters|Where To Increase|"
        r"Where To Protect\s*/\s*Reduce|Where To Protect/Reduce|Immediate Actions|Action Focus"
    )
    heading_regex = re.compile(
        rf"^\s*(?:[#>\-\*]+\s*)?(?:\*\*)?({heading_pattern})(?:\*\*)?\s*:?\s*(.*)$",
        flags=re.IGNORECASE,
    )

    sections_lines: dict[str, list[str]] = {}
    current_key = ""
    matched_heading = False
    for raw_line in normalized.split("\n"):
        line = str(raw_line).rstrip()
        match = heading_regex.match(line.strip())
        if match:
            matched_heading = True
            heading_raw = re.sub(r"\s+", " ", str(match.group(1)).strip().lower())
            key = heading_alias.get(heading_raw, heading_raw.replace(" ", "_"))
            current_key = key
            if current_key not in sections_lines:
                sections_lines[current_key] = []
            tail = str(match.group(2)).strip()
            if tail:
                sections_lines[current_key].append(tail)
            continue
        if current_key:
            sections_lines[current_key].append(line)

    if not matched_heading:
        return None

    sections: dict[str, str] = {k: "\n".join(v).strip() for k, v in sections_lines.items()}

    for key, target in (
        ("q1_executive_summary", "executive_summary"),
        ("q2_yoy_position", "portfolio_position"),
        ("q4_where_to_increase", "where_to_increase"),
    ):
        if key in sections and target not in sections:
            sections[target] = sections[key]

    if "state_clusters" not in sections:
        q3_key = next((k for k in sections if k.startswith("q3_channel_effectiveness")), "")
        if q3_key:
            sections["state_clusters"] = sections[q3_key]
    if "where_to_protect_reduce" not in sections:
        q5_key = next((k for k in sections if k.startswith("q5_where_to_decrease")), "")
        if q5_key:
            sections["where_to_protect_reduce"] = sections[q5_key]

    clusters_text = sections.get("state_clusters", "")
    cluster_lines = [line.strip("- ").strip() for line in clusters_text.split("\n") if line.strip()]
    cluster_map = {"growth_leaders": "", "stable_core": "", "recovery_priority": ""}
    for line in cluster_lines:
        low = line.lower()
        if "growth" in low and "leader" in low:
            cluster_map["growth_leaders"] = line.split(":", 1)[-1].strip() if ":" in line else line
        elif "stable" in low and "core" in low:
            cluster_map["stable_core"] = line.split(":", 1)[-1].strip() if ":" in line else line
        elif "recovery" in low:
            cluster_map["recovery_priority"] = line.split(":", 1)[-1].strip() if ":" in line else line

    def _simple_action_rows(section_text: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for line in section_text.split("\n"):
            s = line.strip()
            if not s:
                continue
            s = s.lstrip("- ").strip()
            if not s or s.lower() == "none":
                continue
            if ":" in s:
                state, why = s.split(":", 1)
                rows.append(
                    {
                        "state": _clip_text(state.strip(), 40),
                        "why": _clip_text(why.strip() or "N/A", 120),
                        "action": "Review allocation and optimize media mix.",
                    }
                )
            else:
                rows.append(
                    {
                        "state": _clip_text(s, 40),
                        "why": "State flagged by model summary.",
                        "action": "Review allocation and optimize media mix.",
                    }
                )
        return rows[:4]

    return {
        "executive_summary": _clip_text(sections.get("executive_summary", "").strip(), 1200),
        "portfolio_position": _clip_text(sections.get("portfolio_position", "").strip(), 700),
        "state_clusters": {
            "growth_leaders": _clip_text(cluster_map["growth_leaders"], 300),
            "stable_core": _clip_text(cluster_map["stable_core"], 300),
            "recovery_priority": _clip_text(cluster_map["recovery_priority"], 300),
        },
        "where_to_increase": _simple_action_rows(sections.get("where_to_increase", "")),
        "where_to_protect_reduce": _simple_action_rows(
            sections.get("where_to_protect_reduce", sections.get("where_to_protect__reduce", ""))
        ),
    }


def _parse_ai_insights_response(text: str) -> dict[str, Any] | None:
    summary_json = _parse_ai_insights_summary_json(text)
    if isinstance(summary_json, dict):
        inc_rows = [
            {
                "state": row.get("state", ""),
                "why": f"{row.get('channel', 'Mix')}: {row.get('reason', '')}",
                "action": row.get("action", ""),
            }
            for row in summary_json.get("increase_markets", [])
        ]
        dec_rows = [
            {
                "state": row.get("state", ""),
                "why": f"{row.get('channel', 'Mix')}: {row.get('reason', '')}",
                "action": row.get("action", ""),
            }
            for row in summary_json.get("decrease_markets", [])
        ]
        channel_notes = summary_json.get("channel_notes", {})
        tv_note = str(channel_notes.get("tv", "")).strip()
        dg_note = str(channel_notes.get("digital", "")).strip()
        return {
            "headline": _clip_text(str(summary_json.get("headline", "")).strip(), 180),
            "portfolio_takeaway": _clip_text(str(summary_json.get("portfolio_takeaway", "")).strip(), 1600),
            "executive_summary": _clip_text(str(summary_json.get("portfolio_takeaway", "")).strip(), 1200),
            "portfolio_position": _clip_text(
                f"TV: {tv_note or 'No specific channel note.'} Digital: {dg_note or 'No specific channel note.'}",
                700,
            ),
            "state_clusters": {"growth_leaders": "", "stable_core": "", "recovery_priority": ""},
            "where_to_increase": _normalize_ai_action_list(inc_rows),
            "where_to_protect_reduce": _normalize_ai_action_list(dec_rows),
            "channel_notes": {"tv": _clip_text(tv_note, 600), "digital": _clip_text(dg_note, 600)},
            "risks": _normalize_string_list(summary_json.get("risks"), max_items=6, item_max_len=220),
            "evidence": _normalize_string_list(summary_json.get("evidence"), max_items=8, item_max_len=220),
            "summary_json": summary_json,
        }

    raw = _extract_json_object(text or "")
    if not isinstance(raw, dict):
        return _parse_ai_insights_sections(text)
    clusters = raw.get("state_clusters", {})
    if not isinstance(clusters, dict):
        clusters = {}
    return {
        "executive_summary": _clip_text(str(raw.get("executive_summary", "")).strip(), 1200),
        "portfolio_position": _clip_text(str(raw.get("portfolio_position", "")).strip(), 700),
        "state_clusters": {
            "growth_leaders": _clip_text(str(clusters.get("growth_leaders", "")).strip(), 300),
            "stable_core": _clip_text(str(clusters.get("stable_core", "")).strip(), 300),
            "recovery_priority": _clip_text(str(clusters.get("recovery_priority", "")).strip(), 300),
        },
        "where_to_increase": _normalize_ai_action_list(raw.get("where_to_increase")),
        "where_to_protect_reduce": _normalize_ai_action_list(raw.get("where_to_protect_reduce")),
    }


def _format_ai_insights_structured_text(data: dict[str, Any]) -> str:
    inc = data.get("where_to_increase", [])
    red = data.get("where_to_protect_reduce", [])
    cluster = data.get("state_clusters", {})

    def _fmt_items(items: list[dict[str, str]]) -> str:
        if not items:
            return "- None"
        lines: list[str] = []
        for row in items:
            lines.append(
                f"- {row.get('state', 'N/A')}: {row.get('why', 'N/A')} | Action: {row.get('action', 'N/A')}"
            )
        return "\n".join(lines)

    return (
        "Executive Summary\n"
        f"{data.get('executive_summary', 'N/A')}\n\n"
        "Portfolio Position\n"
        f"{data.get('portfolio_position', 'N/A')}\n\n"
        "State Clusters\n"
        f"- Growth Leaders: {cluster.get('growth_leaders', 'N/A')}\n"
        f"- Stable Core: {cluster.get('stable_core', 'N/A')}\n"
        f"- Recovery Priority: {cluster.get('recovery_priority', 'N/A')}\n\n"
        "Where To Increase\n"
        f"{_fmt_items(inc)}\n\n"
        "Where To Protect / Reduce\n"
        f"{_fmt_items(red)}\n"
    )


def _build_exec_summary_insight(rows: list[dict[str, Any]], brand: str = "") -> str:
    if not rows:
        return "Portfolio-level insight is unavailable because no valid state rows were found."

    yoy_vals = np.array([float(_finite(r.get("yoy_growth_pct", 0.0), 0.0)) for r in rows], dtype=float)
    head_vals = np.array([float(_finite(r.get("headroom_pct", 0.0), 0.0)) for r in rows], dtype=float)
    tv_eff_vals = np.array([float(_finite(r.get("tv_effectiveness_pct", 0.0), 0.0)) for r in rows], dtype=float)
    dg_eff_vals = np.array([float(_finite(r.get("digital_effectiveness_pct", 0.0), 0.0)) for r in rows], dtype=float)
    tv_share_vals = np.array([float(_finite(r.get("tv_share_pct", 0.0), 0.0)) for r in rows], dtype=float)

    pos_count = int(np.sum(yoy_vals >= 0.0))
    neg_count = max(0, len(rows) - pos_count)
    avg_yoy = float(np.mean(yoy_vals)) if yoy_vals.size else 0.0
    yoy_p75 = float(np.percentile(yoy_vals, 75)) if yoy_vals.size else 0.0
    yoy_p25 = float(np.percentile(yoy_vals, 25)) if yoy_vals.size else 0.0
    yoy_iqr = yoy_p75 - yoy_p25
    median_headroom = float(np.median(head_vals)) if head_vals.size else 0.0
    avg_tv_eff = float(np.mean(tv_eff_vals)) if tv_eff_vals.size else 0.0
    avg_dg_eff = float(np.mean(dg_eff_vals)) if dg_eff_vals.size else 0.0
    avg_tv_share = float(np.mean(tv_share_vals)) if tv_share_vals.size else 0.0

    runway_count = sum(
        1
        for r in rows
        if float(_finite(r.get("yoy_growth_pct", 0.0), 0.0)) >= avg_yoy
        and float(_finite(r.get("headroom_pct", 0.0), 0.0)) >= median_headroom
    )
    conversion_gap_count = sum(
        1
        for r in rows
        if float(_finite(r.get("yoy_growth_pct", 0.0), 0.0)) >= 0.0
        and (
            float(_finite(r.get("tv_effectiveness_pct", 0.0), 0.0)) < 40.0
            or float(_finite(r.get("digital_effectiveness_pct", 0.0), 0.0)) < 40.0
        )
    )
    saturation_drag_count = sum(
        1
        for r in rows
        if float(_finite(r.get("yoy_growth_pct", 0.0), 0.0)) < 0.0
        and (str(r.get("tv_zone", "")).lower() == "saturated" or str(r.get("digital_zone", "")).lower() == "saturated")
    )
    dispersion_label = "tight" if yoy_iqr <= 8.0 else ("moderate" if yoy_iqr <= 18.0 else "wide")
    channel_tilt = "TV-led" if avg_tv_share >= 55.0 else ("Digital-led" if avg_tv_share <= 45.0 else "balanced")
    brand_prefix = f"{brand} portfolio" if brand else "The portfolio"

    return (
        f"{brand_prefix} shows {pos_count} growth states and {neg_count} declining states, with average YoY at {avg_yoy:.1f}% and {dispersion_label} cross-state dispersion (IQR {yoy_iqr:.1f} pp). "
        f"{runway_count} states currently combine above-average momentum with usable headroom (median headroom {median_headroom:.1f}%), forming the primary scale-up runway. "
        f"Channel efficiency is presently {channel_tilt}: average TV effectiveness is {avg_tv_eff:.1f}% and Digital effectiveness is {avg_dg_eff:.1f}%. "
        f"{conversion_gap_count} states are growth-positive but still show efficiency gaps, indicating optimization potential before heavy spend acceleration. "
        f"{saturation_drag_count} declining states also appear channel-saturated, so recovery should prioritize mix correction and spend quality rather than blanket budget increase."
    )


def _is_redundant_exec_summary(text: str) -> bool:
    s = str(text or "").strip()
    if len(s) < 140:
        return True
    low = s.lower()
    redundant_markers = [
        "growth leaders",
        "stable core",
        "recovery priority",
        "where to increase",
        "where to protect",
    ]
    if any(marker in low for marker in redundant_markers):
        return True
    return False


def _finalize_ai_structured(
    data: dict[str, Any],
    leaders: list[str],
    core: list[str],
    recovery: list[str],
    rows: list[dict[str, Any]],
    brand: str = "",
) -> dict[str, Any]:
    out = dict(data)
    clusters = dict(out.get("state_clusters", {}))
    clusters["growth_leaders"] = _clip_text(
        str(clusters.get("growth_leaders", "")).strip() or (", ".join(leaders) if leaders else "None"),
        300,
    )
    clusters["stable_core"] = _clip_text(
        str(clusters.get("stable_core", "")).strip() or (", ".join(core) if core else "None"),
        300,
    )
    clusters["recovery_priority"] = _clip_text(
        str(clusters.get("recovery_priority", "")).strip() or (", ".join(recovery) if recovery else "None"),
        300,
    )
    out["state_clusters"] = clusters

    inc = out.get("where_to_increase", [])
    red = out.get("where_to_protect_reduce", [])
    if not isinstance(inc, list) or len(inc) == 0:
        top_inc = [r for r in rows if str(r.get("recommendation_action", "")).startswith("Increase")]
        top_inc = sorted(top_inc, key=lambda r: float(r.get("headroom_pct", 0.0)), reverse=True)[:4]
        inc = [
            {
                "state": _clip_text(str(r.get("market", "N/A")), 40),
                "why": "High headroom with positive momentum.",
                "action": "Increase spend in a controlled range.",
            }
            for r in top_inc
        ]
    if not isinstance(red, list) or len(red) == 0:
        top_red = [r for r in rows if str(r.get("recommendation_action", "")).startswith("Reduce")]
        top_red = sorted(top_red, key=lambda r: float(r.get("headroom_pct", 0.0)))[:4]
        red = [
            {
                "state": _clip_text(str(r.get("market", "N/A")), 40),
                "why": "Low headroom and/or negative momentum risk.",
                "action": "Protect spend and optimize channel mix.",
            }
            for r in top_red
        ]
    out["where_to_increase"] = _normalize_ai_action_list(inc)
    out["where_to_protect_reduce"] = _normalize_ai_action_list(red)

    diagnostic_summary = _build_exec_summary_insight(rows=rows, brand=brand)
    exec_summary = str(out.get("executive_summary", "")).strip()
    if _is_redundant_exec_summary(exec_summary):
        exec_summary = diagnostic_summary
    out["executive_summary"] = _clip_text(exec_summary, 1200)
    headline = _clip_text(str(out.get("headline", "")).strip(), 180)
    if not headline:
        headline = f"{brand or 'Portfolio'} Strategic Signal"
    out["headline"] = headline
    takeaway = _clip_text(str(out.get("portfolio_takeaway", "")).strip(), 1600)
    if not takeaway:
        takeaway = out["executive_summary"]
    out["portfolio_takeaway"] = takeaway
    out["portfolio_position"] = _clip_text(
        str(out.get("portfolio_position", "")).strip() or "Use headroom and YoY momentum to prioritize allocation shifts by state.",
        700,
    )
    channel_notes = out.get("channel_notes", {})
    if not isinstance(channel_notes, dict):
        channel_notes = {}
    out["channel_notes"] = {
        "tv": _clip_text(str(channel_notes.get("tv", "")).strip(), 600),
        "digital": _clip_text(str(channel_notes.get("digital", "")).strip(), 600),
    }
    out["risks"] = _normalize_string_list(out.get("risks"), max_items=6, item_max_len=220)
    out["evidence"] = _normalize_string_list(out.get("evidence"), max_items=8, item_max_len=220)
    out["summary_json"] = {
        "headline": out["headline"],
        "portfolio_takeaway": out["portfolio_takeaway"],
        "increase_markets": [
            {
                "state": row.get("state", ""),
                "channel": _sanitize_channel_name((str(row.get("why", "")).split(":", 1)[0] if ":" in str(row.get("why", "")) else "Mix")),
                "reason": _clip_text((str(row.get("why", "")).split(":", 1)[1].strip() if ":" in str(row.get("why", "")) else str(row.get("why", ""))), 260),
                "action": _clip_text(str(row.get("action", "")), 260),
            }
            for row in out["where_to_increase"][:6]
        ],
        "decrease_markets": [
            {
                "state": row.get("state", ""),
                "channel": _sanitize_channel_name((str(row.get("why", "")).split(":", 1)[0] if ":" in str(row.get("why", "")) else "Mix")),
                "reason": _clip_text((str(row.get("why", "")).split(":", 1)[1].strip() if ":" in str(row.get("why", "")) else str(row.get("why", ""))), 260),
                "action": _clip_text(str(row.get("action", "")), 260),
            }
            for row in out["where_to_protect_reduce"][:6]
        ],
        "channel_notes": out["channel_notes"],
        "risks": out["risks"],
        "evidence": out["evidence"],
    }
    return out


def _call_gemini_for_insights_text(prompt: str) -> tuple[str | None, list[str]]:
    notes: list[str] = []
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        notes.append("Gemini API key missing; fallback insights applied.")
        return None, notes
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.9,
            "maxOutputTokens": 900,
            "responseMimeType": "application/json",
        },
        "contents": [{"parts": [{"text": prompt}]}],
    }
    req = urlrequest.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    retries = 2
    for attempt in range(retries + 1):
        try:
            with urlrequest.urlopen(req, timeout=25) as resp:
                raw = resp.read().decode("utf-8")
            parsed = json.loads(raw)
            candidates = parsed.get("candidates", [])
            if not candidates or not isinstance(candidates, list):
                notes.append("Gemini returned empty output; fallback insights applied.")
                return None, notes
            parts = candidates[0].get("content", {}).get("parts", [])
            text = str(parts[0].get("text", "")).strip() if parts and isinstance(parts, list) else ""
            if not text:
                notes.append("Gemini returned empty text; fallback insights applied.")
                return None, notes
            return text, notes
        except urlerror.HTTPError as exc:
            retry_after_s = 0.0
            if exc.headers:
                retry_after_raw = str(exc.headers.get("Retry-After", "")).strip()
                try:
                    retry_after_s = float(retry_after_raw) if retry_after_raw else 0.0
                except Exception:
                    retry_after_s = 0.0
            if exc.code == 429 and attempt < retries:
                delay = max(0.8 * (2 ** attempt), retry_after_s)
                time.sleep(delay)
                continue
            if exc.code == 429:
                notes.append("Gemini rate limit reached (HTTP 429); deterministic insights applied.")
            elif exc.code == 404:
                notes.append("Gemini model not found (HTTP 404); deterministic insights applied.")
            elif exc.code == 400:
                notes.append("Gemini request invalid (HTTP 400); deterministic insights applied.")
            else:
                notes.append(f"Gemini HTTP error ({exc.code}); deterministic insights applied.")
            return None, notes
        except Exception as exc:
            if attempt < retries:
                time.sleep(0.8 * (2 ** attempt))
            else:
                if isinstance(exc, urlerror.URLError):
                    notes.append(f"Gemini request failed ({exc.reason}); deterministic insights applied.")
                else:
                    notes.append("Gemini request failed; deterministic insights applied.")
    return None, notes


def _call_gemini_repair_insights_json(raw_text: str) -> tuple[str | None, list[str]]:
    notes: list[str] = []
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None, notes
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    prompt = (
        "Convert the following model output into strict JSON with keys: "
        "headline, portfolio_takeaway, increase_markets, decrease_markets, channel_notes, risks, evidence.\n"
        "Rules:\n"
        "- JSON only.\n"
        "- Keep only supported keys.\n"
        "- Use channel values TV/Digital/Mix.\n"
        "- If missing data, use empty arrays/empty strings.\n"
        f"RAW_OUTPUT:\n{_clip_text(raw_text, 6000)}"
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "generationConfig": {
            "temperature": 0.0,
            "topP": 0.9,
            "maxOutputTokens": 700,
            "responseMimeType": "application/json",
        },
        "contents": [{"parts": [{"text": prompt}]}],
    }
    req = urlrequest.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
        parsed = json.loads(raw)
        candidates = parsed.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates and isinstance(candidates, list) else []
        text = str(parts[0].get("text", "")).strip() if parts and isinstance(parts, list) else ""
        return (text if text else None), notes
    except Exception:
        return None, notes


def _build_ai_insights_summary(payload: InsightsAIRequest) -> dict[str, Any]:
    cfg = _build_auto_config()
    brand = str(payload.selected_brand).strip()
    if brand not in cfg["markets_by_brand"]:
        raise HTTPException(status_code=400, detail="Selected brand is not available in model results.")
    allowed = cfg["markets_by_brand"][brand]
    selected_markets = [m for m in (payload.selected_markets or allowed) if m in allowed]
    if not selected_markets:
        selected_markets = allowed
    if not selected_markets:
        raise HTTPException(status_code=400, detail="No valid markets available for selected brand.")

    ctx = _load_optimization_context(
        OptimizeAutoRequest(
            selected_brand=brand,
            selected_markets=selected_markets,
            budget_increase_type=payload.budget_increase_type,
            budget_increase_value=payload.budget_increase_value,
            market_overrides=payload.market_overrides,
        )
    )
    market_data: dict[str, dict[str, Any]] = ctx["market_data"]
    limits_map: dict[str, dict[str, float | None]] = ctx["limits_map"]
    model_df: pd.DataFrame = ctx["model_df"].copy()
    model_df.columns = [str(c).strip() for c in model_df.columns]

    def _channel_zone(position_pct: float) -> str:
        if position_pct < 35.0:
            return "under-utilized"
        if position_pct <= 70.0:
            return "effective"
        return "saturated"

    rows: list[dict[str, Any]] = []
    for region in ctx["regions"]:
        md = market_data[region]
        lim = limits_map.get(region, {})
        tv = float(np.sum(np.array(md.get("r_tv_list", []), dtype=float)))
        dg = float(np.sum(np.array(md.get("r_dig_list", []), dtype=float)))
        total = max(1e-9, tv + dg)
        tv_min = float(_finite(lim.get("tv_min_reach", 0.0), 0.0))
        tv_max = float(_finite(lim.get("tv_max_reach", max(tv, 1.0)), max(tv, 1.0)))
        dg_min = float(_finite(lim.get("dg_min_reach", 0.0), 0.0))
        dg_max = float(_finite(lim.get("dg_max_reach", max(dg, 1.0)), max(dg, 1.0)))

        tv_util = ((tv - tv_min) / max(1e-9, tv_max - tv_min)) * 100.0
        dg_util = ((dg - dg_min) / max(1e-9, dg_max - dg_min)) * 100.0
        headroom_tv = ((tv_max - tv) / max(1e-9, tv_max)) * 100.0
        headroom_dg = ((dg_max - dg) / max(1e-9, dg_max)) * 100.0
        headroom = max(0.0, (headroom_tv + headroom_dg) / 2.0)
        tv_position_pct = max(0.0, min(100.0, tv_util))
        digital_position_pct = max(0.0, min(100.0, dg_util))
        tv_effectiveness_pct = max(0.0, 100.0 - abs(tv_position_pct - 50.0) * 2.0)
        digital_effectiveness_pct = max(0.0, 100.0 - abs(digital_position_pct - 50.0) * 2.0)
        tv_zone = _channel_zone(tv_position_pct)
        digital_zone = _channel_zone(digital_position_pct)
        raw_yoy = _region_latest_yoy_from_raw(model_df, brand, region)
        yoy = float(_finite(raw_yoy["yoy_growth_pct"], 0.0))
        latest_vol_mn = float(_finite(raw_yoy["latest_volume_mn"], 0.0))
        action = "Hold and optimize mix"
        if yoy >= 0:
            if tv_zone == "under-utilized" and digital_zone != "under-utilized":
                action = "Increase TV selectively"
            elif digital_zone == "under-utilized" and tv_zone != "under-utilized":
                action = "Increase Digital selectively"
            elif tv_zone == "saturated" and digital_zone != "saturated":
                action = "Shift from TV to Digital"
            elif digital_zone == "saturated" and tv_zone != "saturated":
                action = "Shift from Digital to TV"
            elif headroom >= 25:
                action = "Increase investment"
        else:
            if tv_zone == "saturated" or digital_zone == "saturated":
                action = "Reduce saturated channel and rebalance"
            else:
                action = "Fix effectiveness first"

        rows.append(
            {
                "market": region,
                "latest_fiscal_year": raw_yoy["latest_fiscal_year"],
                "latest_volume_mn": round(latest_vol_mn, 4),
                "latest_volume_lakh": round(latest_vol_mn * 10.0, 3),
                "yoy_growth_pct": round(yoy, 3),
                "tv_share_pct": round((tv / total) * 100.0, 2),
                "digital_share_pct": round((dg / total) * 100.0, 2),
                "tv_utilization_pct": round(tv_util, 2),
                "digital_utilization_pct": round(dg_util, 2),
                "headroom_pct": round(headroom, 2),
                "tv_position_pct": round(tv_position_pct, 2),
                "digital_position_pct": round(digital_position_pct, 2),
                "tv_effectiveness_pct": round(tv_effectiveness_pct, 2),
                "digital_effectiveness_pct": round(digital_effectiveness_pct, 2),
                "tv_zone": tv_zone,
                "digital_zone": digital_zone,
                "recommendation_action": action,
            }
        )

    yoy_vals = np.array([float(r["yoy_growth_pct"]) for r in rows], dtype=float)
    head_vals = np.array([float(r["headroom_pct"]) for r in rows], dtype=float)
    q_hi = float(np.percentile(yoy_vals, 67)) if len(yoy_vals) > 0 else 0.0
    q_lo = float(np.percentile(yoy_vals, 33)) if len(yoy_vals) > 0 else 0.0
    head_mid = float(np.percentile(head_vals, 50)) if len(head_vals) > 0 else 0.0

    leaders: list[str] = []
    core: list[str] = []
    recovery: list[str] = []
    for row in rows:
        yoy = float(row["yoy_growth_pct"])
        head = float(row["headroom_pct"])
        if yoy >= q_hi and head >= max(8.0, 0.8 * head_mid):
            leaders.append(str(row["market"]))
        elif yoy <= q_lo or head < 10.0:
            recovery.append(str(row["market"]))
        else:
            core.append(str(row["market"]))

    leaders = sorted(leaders)
    core = sorted(core)
    recovery = sorted(recovery)

    tv_working = sorted(
        [r for r in rows if str(r.get("tv_zone")) == "effective" and float(r.get("yoy_growth_pct", 0.0)) >= 0.0],
        key=lambda r: float(r.get("yoy_growth_pct", 0.0)),
        reverse=True,
    )
    tv_attention = sorted(
        [r for r in rows if str(r.get("tv_zone")) != "effective" or float(r.get("yoy_growth_pct", 0.0)) < 0.0],
        key=lambda r: (float(r.get("tv_effectiveness_pct", 0.0)), float(r.get("yoy_growth_pct", 0.0))),
    )
    dg_working = sorted(
        [r for r in rows if str(r.get("digital_zone")) == "effective" and float(r.get("yoy_growth_pct", 0.0)) >= 0.0],
        key=lambda r: float(r.get("yoy_growth_pct", 0.0)),
        reverse=True,
    )
    dg_attention = sorted(
        [r for r in rows if str(r.get("digital_zone")) != "effective" or float(r.get("yoy_growth_pct", 0.0)) < 0.0],
        key=lambda r: (float(r.get("digital_effectiveness_pct", 0.0)), float(r.get("yoy_growth_pct", 0.0))),
    )
    computed_executive_summary = _build_exec_summary_insight(rows=rows, brand=brand)

    prompt = _build_ai_insights_prompt(
        brand=brand,
        rows=rows,
        leaders=leaders,
        core=core,
        recovery=recovery,
        focus_prompt=str(payload.focus_prompt or "").strip(),
    )
    ai_text, notes = _call_gemini_for_insights_text(prompt)
    provider = "gemini"
    ai_structured: dict[str, Any] | None = None
    ai_summary_json: dict[str, Any] | None = None
    if ai_text is not None:
        ai_structured = _parse_ai_insights_response(ai_text)
        if ai_structured is None:
            repaired_text, repair_notes = _call_gemini_repair_insights_json(ai_text)
            notes.extend(repair_notes)
            if repaired_text:
                ai_structured = _parse_ai_insights_response(repaired_text)
                if ai_structured is not None:
                    ai_text = repaired_text
            if ai_structured is None:
                provider = "fallback"
                notes.append("Gemini response schema invalid; deterministic summary applied.")
        else:
            ai_structured = _finalize_ai_structured(
                data=ai_structured,
                leaders=leaders,
                core=core,
                recovery=recovery,
                rows=rows,
                brand=brand,
            )
            ai_summary_json = ai_structured.get("summary_json") if isinstance(ai_structured.get("summary_json"), dict) else None
            ai_text = _format_ai_insights_structured_text(ai_structured)
    if ai_text is None or ai_structured is None:
        ai_structured = _finalize_ai_structured(
            data={
                "headline": f"{brand} Portfolio Intelligence",
                "portfolio_takeaway": computed_executive_summary,
                "executive_summary": computed_executive_summary,
                "portfolio_position": "Recommendations are based on YoY momentum and channel position versus state reach bounds.",
                "state_clusters": {},
                "where_to_increase": [],
                "where_to_protect_reduce": [],
                "channel_notes": {
                    "tv": f"Working: {', '.join([str(r.get('market')) for r in tv_working[:3]]) or 'None'}. Attention: {', '.join([str(r.get('market')) for r in tv_attention[:3]]) or 'None'}.",
                    "digital": f"Working: {', '.join([str(r.get('market')) for r in dg_working[:3]]) or 'None'}. Attention: {', '.join([str(r.get('market')) for r in dg_attention[:3]]) or 'None'}.",
                },
                "risks": [
                    "Declining states with channel saturation may absorb incremental spend inefficiently.",
                    "Wide YoY dispersion indicates uneven state-level conversion quality.",
                ],
                "evidence": [
                    f"Average YoY across selected states is {float(np.mean(yoy_vals)) if len(yoy_vals) > 0 else 0.0:.1f}%.",
                    f"TV effective-zone count: {sum(1 for r in rows if str(r.get('tv_zone')) == 'effective')}.",
                    f"Digital effective-zone count: {sum(1 for r in rows if str(r.get('digital_zone')) == 'effective')}.",
                ],
            },
            leaders=leaders,
            core=core,
            recovery=recovery,
            rows=rows,
            brand=brand,
        )
        ai_summary_json = ai_structured.get("summary_json") if isinstance(ai_structured.get("summary_json"), dict) else None
        ai_text = _format_ai_insights_structured_text(ai_structured)
        provider = "fallback"

    rows_sorted = sorted(rows, key=lambda r: (float(r["yoy_growth_pct"]), float(r["headroom_pct"])), reverse=True)
    return {
        "status": "ok",
        "message": "AI insights summary generated.",
        "selection": {
            "brand": brand,
            "markets": ctx["regions"],
            "markets_count": len(ctx["regions"]),
        },
        "summary": {
            "provider": provider,
            "leaders_count": len(leaders),
            "core_count": len(core),
            "recovery_count": len(recovery),
        },
        "analysis_basis": {
            "primary_metric": "YoY growth is computed as latest fiscal year volume vs previous fiscal year.",
            "channel_logic": "TV/Digital effectiveness is highest near midpoint of min-max reach bounds; lower/upper extremes are less efficient.",
        },
        "computed_executive_summary": computed_executive_summary,
        "channel_diagnostics": {
            "tv": {
                "working_states": [str(r.get("market")) for r in tv_working[:5]],
                "attention_states": [str(r.get("market")) for r in tv_attention[:5]],
            },
            "digital": {
                "working_states": [str(r.get("market")) for r in dg_working[:5]],
                "attention_states": [str(r.get("market")) for r in dg_attention[:5]],
            },
        },
        "state_clusters": {
            "growth_leaders": leaders,
            "stable_core": core,
            "recovery_priority": recovery,
        },
        "market_cards": rows_sorted,
        "ai_brief": ai_text,
        "ai_structured": ai_structured,
        "ai_summary_json": ai_summary_json,
        "notes": notes,
    }


def _default_strategy_controls() -> dict[str, Any]:
    return {
        "family_mix_weights": {"volume": 0.4, "revenue": 0.4, "balanced": 0.2},
        "pace_preference": "steady",
        "coverage_preference": "broad",
        "diversity_preference": "medium",
    }


def _normalize_family_weights(raw: dict[str, Any] | None) -> dict[str, float]:
    base = {"volume": 0.4, "revenue": 0.4, "balanced": 0.2}
    if not isinstance(raw, dict):
        return base
    out: dict[str, float] = {}
    for key in ("volume", "revenue", "balanced"):
        out[key] = float(_finite(raw.get(key, base[key]), base[key]))
        out[key] = max(0.0, min(1.0, out[key]))
    s = float(sum(out.values()))
    if s <= 1e-12:
        return base
    return {k: (v / s) for k, v in out.items()}


def _extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n", "", stripped).strip()
        stripped = re.sub(r"\n```$", "", stripped).strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    decoder = json.JSONDecoder()
    for i, ch in enumerate(stripped):
        if ch != "{":
            continue
        try:
            parsed, _end = decoder.raw_decode(stripped[i:])
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _sanitize_strategy_controls(raw: dict[str, Any] | None) -> dict[str, Any]:
    default = _default_strategy_controls()
    if not isinstance(raw, dict):
        return default
    pace = str(raw.get("pace_preference", default["pace_preference"])).strip().lower()
    coverage = str(raw.get("coverage_preference", default["coverage_preference"])).strip().lower()
    diversity = str(raw.get("diversity_preference", default["diversity_preference"])).strip().lower()
    if pace not in {"steady", "fast"}:
        pace = default["pace_preference"]
    if coverage not in {"few", "broad"}:
        coverage = default["coverage_preference"]
    if diversity not in {"low", "medium", "high"}:
        diversity = default["diversity_preference"]
    return {
        "family_mix_weights": _normalize_family_weights(raw.get("family_mix_weights")),
        "pace_preference": pace,
        "coverage_preference": coverage,
        "diversity_preference": diversity,
    }


def _call_gemini_for_strategy(intent_prompt: str, constraints_context: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    notes: list[str] = []
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        notes.append("Gemini API key missing; fallback strategy applied.")
        return None, notes

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    prompt = (
        "You are a strategy translator for marketing scenario generation.\n"
        "Return strict JSON only with keys:\n"
        "family_mix_weights (volume/revenue/balanced numbers in [0,1]), "
        "pace_preference (steady|fast), coverage_preference (few|broad), diversity_preference (low|medium|high).\n"
        "Do not return scenario values.\n"
        f"Intent: {intent_prompt}\n"
        f"Constraint context: {json.dumps(constraints_context)}\n"
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
        "contents": [{"parts": [{"text": prompt}]}],
    }
    payload = json.dumps(body).encode("utf-8")
    req = urlrequest.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    retries = 2
    for attempt in range(retries + 1):
        try:
            with urlrequest.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
            parsed = json.loads(raw)
            candidates = parsed.get("candidates", [])
            text = ""
            if candidates and isinstance(candidates, list):
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts and isinstance(parts, list):
                    text = str(parts[0].get("text", "")).strip()
            candidate_obj = _extract_json_object(text)
            if candidate_obj is None:
                notes.append("Gemini returned non-JSON strategy; fallback strategy applied.")
                return None, notes
            return _sanitize_strategy_controls(candidate_obj), notes
        except urlerror.HTTPError as exc:
            retry_after_s = 0.0
            if exc.headers:
                retry_after_raw = str(exc.headers.get("Retry-After", "")).strip()
                try:
                    retry_after_s = float(retry_after_raw) if retry_after_raw else 0.0
                except Exception:
                    retry_after_s = 0.0
            if exc.code == 429 and attempt < retries:
                delay = max(0.8 * (2 ** attempt), retry_after_s)
                time.sleep(delay)
                continue
            if exc.code == 429:
                notes.append("Gemini rate limit reached (HTTP 429); fallback strategy applied.")
            elif exc.code == 404:
                notes.append("Gemini model not found (HTTP 404); fallback strategy applied.")
            elif exc.code == 400:
                notes.append("Gemini request invalid (HTTP 400); fallback strategy applied.")
            else:
                notes.append(f"Gemini HTTP error ({exc.code}); fallback strategy applied.")
            return None, notes
        except Exception as exc:
            if attempt < retries:
                time.sleep(0.8 * (2 ** attempt))
            else:
                if isinstance(exc, urlerror.URLError):
                    notes.append(f"Gemini request failed ({exc.reason}); fallback strategy applied.")
                else:
                    notes.append("Gemini request failed; fallback strategy applied.")
    return None, notes


def _translate_intent_to_strategy(intent_prompt: str, constraints_context: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """
    Use-case note for AI review:
    This step converts user intent into strategy controls only. The controls guide Monte Carlo sampling,
    but hard constraints remain enforced by the optimization engine and cannot be overridden by AI output.
    """
    prompt = str(intent_prompt or "").strip()
    if not prompt:
        return _default_strategy_controls(), ["No intent prompt provided; default strategy applied."]
    strategy, notes = _call_gemini_for_strategy(prompt, constraints_context)
    if strategy is None:
        return _default_strategy_controls(), notes
    return _sanitize_strategy_controls(strategy), notes


def _normalized_l2_distance(a: np.ndarray, b: np.ndarray, bounds: list[tuple[float, float]]) -> float:
    if len(a) != len(b) or len(a) != len(bounds):
        return 0.0
    if len(a) == 0:
        return 0.0
    acc = 0.0
    for i, (lo, hi) in enumerate(bounds):
        den = max(1e-9, float(hi - lo))
        diff = (float(a[i]) - float(b[i])) / den
        acc += diff * diff
    return float(math.sqrt(acc / len(a)))


def _vector_key(v: np.ndarray) -> tuple[float, ...]:
    return tuple(float(round(x, 6)) for x in v.tolist())


def _derive_sampling_params(strategy: dict[str, Any]) -> dict[str, float]:
    pace = strategy.get("pace_preference", "steady")
    coverage = strategy.get("coverage_preference", "broad")
    diversity = strategy.get("diversity_preference", "medium")
    near_sigma = 0.04 if pace == "steady" else 0.08
    broad_sigma = 0.20 if pace == "steady" else 0.35
    active_fraction = 1.0 if coverage == "broad" else 0.35
    distance_scale = {"low": 0.75, "medium": 1.0, "high": 1.3}.get(str(diversity), 1.0)
    return {
        "near_sigma": near_sigma,
        "broad_sigma": broad_sigma,
        "active_fraction": active_fraction,
        "min_distance": SCENARIO_DEFAULT_MIN_DISTANCE * distance_scale,
    }


def _sample_family(weights: dict[str, float], rng: random.Random) -> str:
    r = rng.random()
    if r < weights.get("volume", 0.0):
        return "volume"
    if r < weights.get("volume", 0.0) + weights.get("revenue", 0.0):
        return "revenue"
    return "balanced"


def _sample_candidate_vector(
    center: np.ndarray,
    family: str,
    near_opt: bool,
    bounds: list[tuple[float, float]],
    regions: list[str],
    params: dict[str, float],
    rng: random.Random,
) -> np.ndarray:
    v = np.array(center, dtype=float)
    sigma = params["near_sigma"] if near_opt else params["broad_sigma"]
    market_count = max(1, len(regions))
    active_fraction = params["active_fraction"] if not near_opt else 1.0
    active_markets = max(1, int(round(market_count * active_fraction)))
    active_idx = set(rng.sample(range(market_count), active_markets)) if active_markets < market_count else set(range(market_count))
    for m_idx in range(market_count):
        if m_idx not in active_idx:
            continue
        tv_i = 2 * m_idx
        dg_i = 2 * m_idx + 1
        tv_noise = rng.gauss(0.0, sigma)
        dg_noise = rng.gauss(0.0, sigma)
        if family == "volume":
            tv_noise += abs(rng.gauss(0.0, sigma * 0.3))
            dg_noise += abs(rng.gauss(0.0, sigma * 0.2))
        elif family == "revenue":
            tv_noise -= abs(rng.gauss(0.0, sigma * 0.15))
            dg_noise += abs(rng.gauss(0.0, sigma * 0.15))
        v[tv_i] += tv_noise
        v[dg_i] += dg_noise
    for i, (lo, hi) in enumerate(bounds):
        v[i] = min(max(v[i], lo), hi)
    return v


def _apply_balanced_scores(scenarios: list[dict[str, Any]]) -> None:
    if not scenarios:
        return
    vols = [float(s["volume_uplift_pct"]) for s in scenarios]
    revs = [float(s["revenue_uplift_pct"]) for s in scenarios]
    vmin, vmax = min(vols), max(vols)
    rmin, rmax = min(revs), max(revs)
    for sc in scenarios:
        v_norm = 0.0 if abs(vmax - vmin) < 1e-12 else (float(sc["volume_uplift_pct"]) - vmin) / (vmax - vmin)
        r_norm = 0.0 if abs(rmax - rmin) < 1e-12 else (float(sc["revenue_uplift_pct"]) - rmin) / (rmax - rmin)
        sc["balanced_score"] = round(0.5 * v_norm + 0.5 * r_norm, 6)


def _pick_best_balanced_anchor(scenarios: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not scenarios:
        return None
    return max(
        scenarios,
        key=lambda s: (
            float(s.get("balanced_score", 0.0)),
            float(s.get("revenue_uplift_pct", 0.0)),
            float(s.get("volume_uplift_pct", 0.0)),
            -int(s.get("scenario_index", 10**9)),
        ),
    )


def _pick_best_anchor(scenarios: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    if not scenarios:
        return None
    return max(
        scenarios,
        key=lambda s: (
            float(s.get(key, 0.0)),
            float(s.get("revenue_uplift_pct", 0.0)),
            float(s.get("volume_uplift_pct", 0.0)),
            -int(s.get("scenario_index", 10**9)),
        ),
    )


def _rank_scenarios(scenarios: list[dict[str, Any]]) -> None:
    vol_sorted = sorted(
        scenarios,
        key=lambda s: (
            float(s.get("volume_uplift_pct", 0.0)),
            float(s.get("revenue_uplift_pct", 0.0)),
            -int(s.get("scenario_index", 10**9)),
        ),
        reverse=True,
    )
    for idx, sc in enumerate(vol_sorted, start=1):
        sc["volume_rank"] = idx

    rev_sorted = sorted(
        scenarios,
        key=lambda s: (
            float(s.get("revenue_uplift_pct", 0.0)),
            float(s.get("volume_uplift_pct", 0.0)),
            -int(s.get("scenario_index", 10**9)),
        ),
        reverse=True,
    )
    for idx, sc in enumerate(rev_sorted, start=1):
        sc["revenue_rank"] = idx


def _serialize_anchor(anchor: dict[str, Any] | None) -> dict[str, Any] | None:
    if anchor is None:
        return None
    return {
        "scenario_id": anchor.get("scenario_id"),
        "family": anchor.get("family"),
        "seed_source": anchor.get("seed_source"),
        "volume_uplift_pct": anchor.get("volume_uplift_pct"),
        "revenue_uplift_pct": anchor.get("revenue_uplift_pct"),
        "volume_uplift_abs": anchor.get("volume_uplift_abs"),
        "revenue_uplift_abs": anchor.get("revenue_uplift_abs"),
        "balanced_score": anchor.get("balanced_score"),
        "weighted_tv_share": anchor.get("weighted_tv_share"),
        "weighted_digital_share": anchor.get("weighted_digital_share"),
    }


def _cleanup_expired_scenario_jobs() -> None:
    now = time.time()
    with _SCENARIO_JOBS_LOCK:
        for job in _SCENARIO_JOBS.values():
            if now <= float(job.get("expires_at", now + 1)):
                continue
            if job.get("status") != "expired":
                job["status"] = "expired"
                job["ready"] = False
                job["progress"] = 100
                job["error_reason"] = "Scenario job expired after TTL."
                job.pop("result", None)


def _update_scenario_job(job_id: str, **updates: Any) -> None:
    with _SCENARIO_JOBS_LOCK:
        job = _SCENARIO_JOBS.get(job_id)
        if not job:
            return
        job.update(updates)
        job["updated_at"] = time.time()


def _read_scenario_job(job_id: str) -> dict[str, Any]:
    _cleanup_expired_scenario_jobs()
    with _SCENARIO_JOBS_LOCK:
        job = _SCENARIO_JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Scenario job not found.")
        return dict(job)


def _generate_scenarios_for_context(
    ctx: dict[str, Any],
    strategy: dict[str, Any],
    set_progress: Any,
    target_total_requested: int,
    max_runtime_seconds: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Use-case note for AI review:
    Monte Carlo generates candidate TV/Digital market adjustments guided by strategy controls,
    then strictly enforces existing Step-2 constraints. AI guidance influences diversity and family
    exploration only; hard constraints remain authoritative.
    """
    regions = ctx["regions"]
    market_data = ctx["market_data"]
    limits_map = ctx["limits_map"]
    target_budget = float(ctx["target_budget"])
    region_prices = _compute_region_prices_last_3_months(ctx["model_df"], ctx["brand"], regions)
    bounds, coeffs, baseline_budget = _build_variable_bounds_and_coeffs(market_data, regions, limits_map)
    rng = random.Random(_stable_score(f"{ctx['brand']}|{','.join(regions)}|{target_budget}"))

    set_progress(20, "Computing deterministic seed scenarios...")
    volume_seed, _ = _run_solver(market_data, regions, target_budget, limits_map)
    revenue_seed, _ = _run_solver_with_objective(
        market_data=market_data,
        regions=regions,
        B=target_budget,
        limits_map=limits_map,
        objective_fn=_objective_revenue,
        objective_args=(region_prices,),
    )
    balanced_seed = (np.array(volume_seed, dtype=float) + np.array(revenue_seed, dtype=float)) / 2.0
    for i, (lo, hi) in enumerate(bounds):
        balanced_seed[i] = min(max(balanced_seed[i], lo), hi)

    seeds = {"volume": np.array(volume_seed, dtype=float), "revenue": np.array(revenue_seed, dtype=float), "balanced": balanced_seed}
    params = _derive_sampling_params(strategy)
    min_distance = max(SCENARIO_NEAR_OPT_MIN_DISTANCE, float(params["min_distance"]))
    target_total = max(50, min(int(target_total_requested), SCENARIO_TARGET_TOTAL))
    target_near = min(SCENARIO_TARGET_NEAR_OPT, max(20, int(round(target_total * 0.1))))
    runtime_limit = max(10, int(max_runtime_seconds))
    started_at = time.time()
    timeout_hit = False

    accepted: list[dict[str, Any]] = []
    accepted_vectors: list[np.ndarray] = []
    low = np.array([lo for lo, _ in bounds], dtype=float)
    span = np.array([max(1e-9, hi - lo) for lo, hi in bounds], dtype=float)
    accepted_scaled = np.empty((0, len(bounds)), dtype=float)
    exact_keys: set[tuple[float, ...]] = set()
    near_count = 0
    attempts = 0
    notes: list[str] = []

    def try_accept_candidate(vec: np.ndarray, family: str, seed_source: str, near_opt: bool) -> bool:
        nonlocal near_count, accepted_scaled
        projected = _project_vector_to_budget(vec, target_budget, bounds, coeffs, baseline_budget)
        if projected is None:
            return False
        if not _is_vector_feasible(projected, target_budget, bounds, coeffs, baseline_budget):
            return False
        key = _vector_key(projected)
        if key in exact_keys:
            return False
        scaled = (projected - low) / span
        if accepted_scaled.shape[0] > 0:
            dists = np.linalg.norm(accepted_scaled - scaled, axis=1)
            if float(np.min(dists)) < min_distance:
                return False
        evaluated = _evaluate_solution_vector(projected, market_data, regions, limits_map, region_prices)
        scenario = {
            "scenario_index": len(accepted) + 1,
            "scenario_id": f"SCN-{len(accepted) + 1:04d}",
            "family": family.capitalize(),
            "seed_source": seed_source,
            "tv_digital_vector": [round(float(x), 6) for x in projected.tolist()],
            "volume_uplift_abs": round(float(evaluated["total_volume_uplift"]), 4),
            "volume_uplift_pct": round(float(evaluated["total_volume_uplift_pct"]), 4),
            "revenue_uplift_abs": round(float(evaluated["revenue_uplift_abs"]), 4),
            "revenue_uplift_pct": round(float(evaluated["revenue_uplift_pct"]), 4),
            "baseline_revenue": round(float(evaluated["baseline_revenue"]), 4),
            "new_revenue": round(float(evaluated["new_revenue"]), 4),
            "total_new_spend": round(float(evaluated["total_spend"]), 4),
            "weighted_tv_share": round(float(evaluated["weighted_tv_share"]), 6),
            "weighted_digital_share": round(float(evaluated["weighted_digital_share"]), 6),
            "markets": evaluated["rows"],
        }
        accepted.append(scenario)
        accepted_vectors.append(projected)
        accepted_scaled = np.vstack((accepted_scaled, scaled.reshape(1, -1)))
        exact_keys.add(key)
        if near_opt:
            near_count += 1
        return True

    def timed_out() -> bool:
        return (time.time() - started_at) >= runtime_limit

    set_progress(32, "Generating near-optimum scenarios...")
    while len(accepted) < target_total and near_count < target_near and attempts < SCENARIO_MAX_ATTEMPTS:
        if timed_out():
            timeout_hit = True
            break
        attempts += 1
        fam = "volume" if rng.random() < 0.5 else "revenue"
        base = seeds[fam]
        candidate = _sample_candidate_vector(base, fam, True, bounds, regions, params, rng)
        try_accept_candidate(candidate, family=fam, seed_source=f"near_{fam}_seed", near_opt=True)
        if attempts % 1200 == 0:
            set_progress(32 + int(min(18, 18 * near_count / max(1, target_near))), "Generating near-optimum scenarios...")

    if near_count < target_near:
        notes.append(f"Near-opt scenario target reduced by feasibility/diversity checks: {near_count} accepted out of requested {target_near}.")

    set_progress(52, "Generating diverse strategy scenarios...")
    family_weights = _normalize_family_weights(strategy.get("family_mix_weights"))
    while len(accepted) < target_total and attempts < SCENARIO_MAX_ATTEMPTS:
        if timed_out():
            timeout_hit = True
            break
        attempts += 1
        fam = _sample_family(family_weights, rng)
        base = seeds[fam]
        candidate = _sample_candidate_vector(base, fam, False, bounds, regions, params, rng)
        try_accept_candidate(candidate, family=fam, seed_source=f"{fam}_strategy", near_opt=False)
        if attempts % 2000 == 0:
            span = max(1, target_total - target_near)
            done = max(0, len(accepted) - near_count)
            set_progress(52 + int(min(33, 33 * done / span)), "Generating diverse strategy scenarios...")

    if len(accepted) < target_total:
        notes.append(
            f"Returned {len(accepted)} feasible unique scenarios (requested up to {target_total}); strict constraints and diversity threshold reduced feasible space."
        )
    if timeout_hit:
        notes.append(f"Generation stopped at runtime cap ({runtime_limit}s) to keep UI responsive.")

    _apply_balanced_scores(accepted)
    _rank_scenarios(accepted)
    anchors = {
        "best_volume": _serialize_anchor(_pick_best_anchor(accepted, "volume_uplift_pct")),
        "best_revenue": _serialize_anchor(_pick_best_anchor(accepted, "revenue_uplift_pct")),
        "best_balanced": _serialize_anchor(_pick_best_balanced_anchor(accepted)),
    }
    summary = {
        "scenario_count": len(accepted),
        "target_count": target_total,
        "requested_target_count": target_total_requested,
        "near_opt_count": near_count,
        "near_opt_target": target_near,
        "min_distance": round(float(min_distance), 4),
        "budget_tolerance": _budget_epsilon(target_budget),
        "runtime_seconds": round(float(time.time() - started_at), 2),
        "runtime_cap_seconds": runtime_limit,
        "selected_brand": ctx["brand"],
        "selected_markets": regions,
        "target_budget": round(target_budget, 4),
        "baseline_budget": round(float(ctx["baseline_budget"]), 4),
        "strategy": strategy,
    }
    return accepted, {"anchors": anchors, "summary": summary, "notes": notes}


def _run_scenario_job(job_id: str, payload: ScenarioJobCreateRequest) -> None:
    try:
        _update_scenario_job(job_id, status="running", progress=5, message="Loading optimization context...")
        ctx = _load_optimization_context(
            OptimizeAutoRequest(
                selected_brand=payload.selected_brand,
                selected_markets=payload.selected_markets,
                budget_increase_type=payload.budget_increase_type,
                budget_increase_value=payload.budget_increase_value,
                market_overrides=payload.market_overrides,
            )
        )
        constraints_context = {
            "brand": ctx["brand"],
            "market_count": len(ctx["regions"]),
            "target_budget": round(float(ctx["target_budget"]), 4),
            "baseline_budget": round(float(ctx["baseline_budget"]), 4),
            "markets": ctx["regions"],
        }
        _update_scenario_job(job_id, progress=15, message="Translating intent into strategy controls...")
        strategy, strategy_notes = _translate_intent_to_strategy(payload.intent_prompt, constraints_context)

        def set_progress(progress: int, message: str) -> None:
            _update_scenario_job(job_id, progress=max(0, min(99, int(progress))), message=message)

        scenarios, artifacts = _generate_scenarios_for_context(
            ctx,
            strategy,
            set_progress,
            target_total_requested=payload.target_scenarios,
            max_runtime_seconds=payload.max_runtime_seconds,
        )
        result_payload = {
            "summary": artifacts["summary"],
            "anchors": artifacts["anchors"],
            "generation_notes": [*strategy_notes, *artifacts["notes"]],
            "scenarios": scenarios,
        }
        _update_scenario_job(
            job_id,
            status="completed",
            progress=100,
            ready=True,
            message="Scenario generation completed.",
            result=result_payload,
        )
    except Exception as exc:
        _update_scenario_job(
            job_id,
            status="failed",
            progress=100,
            ready=False,
            message="Scenario generation failed.",
            error_reason=str(exc),
        )


def _paginate_scenario_results(
    scenarios: list[dict[str, Any]],
    page: int,
    page_size: int,
    sort_key: str,
    sort_dir: str,
    family: str | None,
    min_volume_uplift_pct: float | None,
    max_volume_uplift_pct: float | None,
    min_revenue_uplift_pct: float | None,
    max_revenue_uplift_pct: float | None,
) -> dict[str, Any]:
    allowed_sort = {
        "balanced_score",
        "volume_uplift_pct",
        "revenue_uplift_pct",
        "volume_uplift_abs",
        "revenue_uplift_abs",
        "weighted_tv_share",
        "weighted_digital_share",
        "scenario_id",
    }
    if sort_key not in allowed_sort:
        sort_key = "balanced_score"
    sort_dir = "asc" if str(sort_dir).lower() == "asc" else "desc"
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), SCENARIO_PAGE_SIZE_MAX))

    items = scenarios
    if family:
        fam = str(family).strip().lower()
        items = [s for s in items if str(s.get("family", "")).strip().lower() == fam]
    if min_volume_uplift_pct is not None:
        items = [s for s in items if float(s.get("volume_uplift_pct", 0.0)) >= float(min_volume_uplift_pct)]
    if max_volume_uplift_pct is not None:
        items = [s for s in items if float(s.get("volume_uplift_pct", 0.0)) <= float(max_volume_uplift_pct)]
    if min_revenue_uplift_pct is not None:
        items = [s for s in items if float(s.get("revenue_uplift_pct", 0.0)) >= float(min_revenue_uplift_pct)]
    if max_revenue_uplift_pct is not None:
        items = [s for s in items if float(s.get("revenue_uplift_pct", 0.0)) <= float(max_revenue_uplift_pct)]

    reverse = sort_dir == "desc"
    if sort_key == "scenario_id":
        items = sorted(items, key=lambda s: int(s.get("scenario_index", 10**9)), reverse=reverse)
    else:
        if reverse:
            items = sorted(
                items,
                key=lambda s: (
                    float(s.get(sort_key, 0.0)),
                    -int(s.get("scenario_index", 10**9)),
                ),
                reverse=True,
            )
        else:
            items = sorted(
                items,
                key=lambda s: (
                    float(s.get(sort_key, 0.0)),
                    int(s.get("scenario_index", 10**9)),
                ),
            )

    total_count = len(items)
    total_pages = max(1, int(math.ceil(total_count / page_size))) if total_count > 0 else 1
    page = min(page, total_pages)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    return {
        "total_count": total_count,
        "total_pages": total_pages,
        "page": page,
        "page_size": page_size,
        "sort_key": sort_key,
        "sort_dir": sort_dir,
        "items": page_items,
    }


def service_create_scenario_job(payload: ScenarioJobCreateRequest) -> dict[str, Any]:
    """
    Starts async AI-guided scenario generation for Step-2 brand-market planning.
    """
    _cleanup_expired_scenario_jobs()
    job_id = str(uuid.uuid4())
    now = time.time()
    record = {
        "job_id": job_id,
        "status": "queued",
        "ready": False,
        "progress": 0,
        "message": "Scenario job queued.",
        "error_reason": None,
        "created_at": now,
        "updated_at": now,
        "expires_at": now + SCENARIO_JOB_TTL_SECONDS,
        "result": None,
    }
    with _SCENARIO_JOBS_LOCK:
        _SCENARIO_JOBS[job_id] = record
    worker = threading.Thread(target=_run_scenario_job, args=(job_id, payload), daemon=True)
    worker.start()
    return {
        "job_id": job_id,
        "status": "queued",
        "ready": False,
        "progress": 0,
        "message": "Scenario generation started.",
        "expires_at": record["expires_at"],
    }


def service_get_scenario_job_status(job_id: str) -> dict[str, Any]:
    job = _read_scenario_job(job_id)
    return {
        "job_id": job["job_id"],
        "ready": bool(job.get("ready", False)),
        "status": str(job.get("status", "queued")),
        "progress": int(job.get("progress", 0)),
        "message": str(job.get("message", "")),
        "error_reason": job.get("error_reason"),
        "expires_at": job.get("expires_at"),
        "updated_at": job.get("updated_at"),
    }


def service_get_scenario_job_results(
    job_id: str,
    page: int = 1,
    page_size: int = SCENARIO_PAGE_SIZE_DEFAULT,
    sort_key: str = "balanced_score",
    sort_dir: str = "desc",
    family: str | None = None,
    min_volume_uplift_pct: float | None = None,
    max_volume_uplift_pct: float | None = None,
    min_revenue_uplift_pct: float | None = None,
    max_revenue_uplift_pct: float | None = None,
) -> Any:
    job = _read_scenario_job(job_id)
    status = str(job.get("status", "queued"))
    if status in {"queued", "running"}:
        return JSONResponse(
            status_code=202,
            content={
                "ready": False,
                "job_id": job_id,
                "status": status,
                "progress": int(job.get("progress", 0)),
                "message": str(job.get("message", "")),
            },
        )
    if status == "failed":
        return JSONResponse(
            status_code=409,
            content={
                "ready": False,
                "job_id": job_id,
                "status": "failed",
                "error_reason": str(job.get("error_reason", "Scenario generation failed.")),
            },
        )
    if status == "expired":
        return JSONResponse(
            status_code=410,
            content={
                "ready": False,
                "job_id": job_id,
                "status": "expired",
                "error_reason": str(job.get("error_reason", "Scenario job expired.")),
            },
        )
    if status != "completed":
        raise HTTPException(status_code=500, detail="Scenario job state is invalid.")

    result = job.get("result") or {}
    scenarios = list(result.get("scenarios", []))
    pagination = _paginate_scenario_results(
        scenarios=scenarios,
        page=page,
        page_size=page_size,
        sort_key=sort_key,
        sort_dir=sort_dir,
        family=family,
        min_volume_uplift_pct=min_volume_uplift_pct,
        max_volume_uplift_pct=max_volume_uplift_pct,
        min_revenue_uplift_pct=min_revenue_uplift_pct,
        max_revenue_uplift_pct=max_revenue_uplift_pct,
    )
    return {
        "ready": True,
        "job_id": job_id,
        "status": "completed",
        "summary": result.get("summary", {}),
        "anchors": result.get("anchors", {}),
        "generation_notes": result.get("generation_notes", []),
        "pagination": {
            "total_count": pagination["total_count"],
            "total_pages": pagination["total_pages"],
            "page": pagination["page"],
            "page_size": pagination["page_size"],
            "sort_key": pagination["sort_key"],
            "sort_dir": pagination["sort_dir"],
        },
        "items": pagination["items"],
    }


def service_health() -> dict[str, str]:
    return {"status": "ok"}


def service_auto_config() -> dict:
    return _build_auto_config()


def service_optimize_auto(payload: OptimizeAutoRequest) -> dict:
    try:
        return _optimize_real(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {exc}") from exc


def service_constraints_auto(payload: OptimizeAutoRequest) -> dict:
    try:
        return _constraints_preview(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Constraints preview failed: {exc}") from exc


def service_s_curves_auto(payload: SCurveAutoRequest) -> dict:
    try:
        return _build_s_curves(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"S-curve generation failed: {exc}") from exc


def service_contributions_auto(payload: ContributionAutoRequest) -> dict:
    try:
        return _build_contribution_insights(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Contribution insights failed: {exc}") from exc


def service_yoy_growth_auto(payload: YoyGrowthRequest) -> dict:
    try:
        return _build_yoy_growth_insights(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"YoY growth insights failed: {exc}") from exc


def service_insights_ai_summary(payload: InsightsAIRequest) -> dict:
    try:
        return _build_ai_insights_summary(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI insights summary failed: {exc}") from exc


def service_brand_allocation(payload: BrandAllocationRequest) -> dict:
    try:
        return _brand_allocation_step1(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Brand allocation failed: {exc}") from exc
