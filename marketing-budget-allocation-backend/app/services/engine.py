from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import os
import random
import re
import threading
import time
import uuid
import unicodedata
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
_INSIGHTS_CACHE_SIGNATURE: tuple[tuple[str, int, int], ...] | None = None
_INSIGHTS_CACHE: dict[str, Any] = {}
_INSIGHTS_CACHE_ORDER: list[str] = []
_INSIGHTS_CACHE_MAX_ENTRIES = max(50, int(os.getenv("MBA_INSIGHTS_CACHE_MAX_ENTRIES", "600")))
_INSIGHTS_CACHE_LOCK = threading.Lock()
_INSIGHTS_WARMUP_ON_START = os.getenv("MBA_INSIGHTS_WARMUP_ON_START", "1").strip().lower() not in {"0", "false", "no"}
_INSIGHTS_WARMUP_LOCK = threading.Lock()
_INSIGHTS_WARMUP_THREAD: threading.Thread | None = None
_INSIGHTS_WARMUP_STATUS: dict[str, Any] = {
    "enabled": _INSIGHTS_WARMUP_ON_START,
    "state": "idle",  # idle | queued | running | completed | failed | disabled
    "started_at": None,
    "completed_at": None,
    "duration_seconds": None,
    "total_pairs": 0,
    "completed_pairs": 0,
    "failed_pairs": 0,
    "last_error": None,
}
SCENARIO_JOB_TTL_SECONDS = 24 * 60 * 60
SCENARIO_TARGET_TOTAL = 5000
SCENARIO_TARGET_DEFAULT = 1000
SCENARIO_TARGET_NEAR_OPT = 100
SCENARIO_NEAR_OPT_MIN_DISTANCE = 0.04
SCENARIO_DEFAULT_MIN_DISTANCE = 0.04
# Legacy fallback only when explicit scenario band is not supplied by client.
SCENARIO_BUDGET_BAND_LOWER_RATIO = 0.85
SCENARIO_MAX_ATTEMPTS = 65000
SCENARIO_PAGE_SIZE_DEFAULT = 25
SCENARIO_PAGE_SIZE_MAX = 200
REACH_SHARE_TARGET_TOLERANCE_PCT = 15.0
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
    resolved_intent: dict[str, Any] | None = None
    strategy_override: dict[str, Any] | None = None
    scenario_budget_lower: float | None = None
    scenario_budget_upper: float | None = None
    scenario_label_prefix: str | None = None
    target_scenarios: int = SCENARIO_TARGET_DEFAULT
    max_runtime_seconds: int = 900


ScenarioMarketAction = Literal["increase", "decrease", "protect", "hold", "deprioritize", "rebalance", "recover"]
ScenarioObjectivePreference = Literal["volume", "revenue", "balanced", "efficiency", "practical_mix"]


class ScenarioIntentQuestion(BaseModel):
    id: str
    question: str
    options: list[str] = Field(default_factory=list)
    allow_free_text: bool = False


class ScenarioInterpretedCondition(BaseModel):
    metric_key: str
    metric_label: str
    qualifier_type: Literal["band", "trend"]
    requested_direction: Literal["high", "low", "increasing", "decreasing"]
    source_text: str = ""
    matched_markets: list[str] = Field(default_factory=list)


class ScenarioPlanEntity(BaseModel):
    grain: str = "market"
    scope: list[str] = Field(default_factory=list)
    brand: str = ""


class ScenarioMetricMapping(BaseModel):
    prompt_term: str
    metric_key: str
    metric_label: str
    source_column: str
    match_type: str = "inferred"
    interpretation: str = ""
    confidence: float = 0.0


class ScenarioLogicRule(BaseModel):
    kind: str
    label: str
    metric_key: str = ""
    operator: str = ""
    value: str = ""
    markets: list[str] = Field(default_factory=list)
    rationale: str = ""


class ScenarioOutputSpec(BaseModel):
    output_type: str = "ranked_market_recommendations"
    fields: list[str] = Field(default_factory=list)


class ScenarioAnalysisPlan(BaseModel):
    task_types: list[str] = Field(default_factory=list)
    goal: str = ""
    entity: ScenarioPlanEntity = Field(default_factory=ScenarioPlanEntity)
    metric_mappings: list[ScenarioMetricMapping] = Field(default_factory=list)
    qualification_logic: list[ScenarioLogicRule] = Field(default_factory=list)
    prioritization_logic: list[ScenarioLogicRule] = Field(default_factory=list)
    derived_metrics: list[str] = Field(default_factory=list)
    grouping: list[str] = Field(default_factory=list)
    segmentation: list[str] = Field(default_factory=list)
    output: ScenarioOutputSpec = Field(default_factory=ScenarioOutputSpec)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    needs_review: bool = False
    review_reason: list[str] = Field(default_factory=list)


class ScenarioResolvedIntent(BaseModel):
    analysis_plan: ScenarioAnalysisPlan = Field(default_factory=ScenarioAnalysisPlan)
    primary_anchor_metrics: list[str] = Field(default_factory=list)
    secondary_anchor_metrics: list[str] = Field(default_factory=list)
    interpreted_conditions: list[ScenarioInterpretedCondition] = Field(default_factory=list)
    interpretation_summary: str = ""
    negative_filters: list[str] = Field(default_factory=list)
    target_markets: list[str] = Field(default_factory=list)
    protected_markets: list[str] = Field(default_factory=list)
    held_markets: list[str] = Field(default_factory=list)
    deprioritized_markets: list[str] = Field(default_factory=list)
    action_preferences_by_market: dict[str, ScenarioMarketAction] = Field(default_factory=dict)
    market_action_explanations: dict[str, str] = Field(default_factory=dict)
    global_action_preference: ScenarioMarketAction = "hold"
    objective_preference: ScenarioObjectivePreference = "balanced"
    aggressiveness_level: Literal["low", "medium", "high"] = "medium"
    practicality_level: Literal["high", "medium", "low"] = "medium"
    confidence_score: float = 0.0
    readiness_for_generation: bool = False
    confirmation_required: bool = False
    explanation_notes: list[str] = Field(default_factory=list)


class ScenarioIntentResolveRequest(BaseModel):
    selected_brand: str
    selected_markets: list[str] = Field(default_factory=list)
    budget_increase_type: Literal["percentage", "absolute"] = "percentage"
    budget_increase_value: float = 5.0
    market_overrides: dict[str, dict[str, float]] = Field(default_factory=dict)
    intent_prompt: str = ""


class ScenarioIntentClarifyRequest(ScenarioIntentResolveRequest):
    clarification_round: int = 1
    clarification_answers: dict[str, str] = Field(default_factory=dict)


class ScenarioIntentDebugRequest(ScenarioIntentResolveRequest):
    pass


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


class DriverAnalysisRequest(BaseModel):
    selected_brand: str
    selected_market: str = ""
    months_back: int = 3
    top_n: int = 8


class InsightsAIRequest(BaseModel):
    selected_brand: str
    selected_markets: list[str] = Field(default_factory=list)
    budget_increase_type: Literal["percentage", "absolute"] = "percentage"
    budget_increase_value: float = 0.0
    market_overrides: dict[str, dict[str, float]] = Field(default_factory=dict)
    focus_prompt: str = ""


class ScenarioSummaryRequest(BaseModel):
    selected_brand: str
    scenario_id: str
    revenue_uplift_pct: float = 0.0
    total_new_spend: float = 0.0
    target_budget: float = 0.0
    markets: list[dict[str, Any]] = Field(default_factory=list)
    state_change_rows: list[dict[str, Any]] = Field(default_factory=list)
    user_prompt: str = ""


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


def _insights_payload_cache_key(prefix: str, payload: BaseModel) -> str:
    serialized = json.dumps(payload.model_dump(mode="json"), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return f"{prefix}:{serialized}"


def _refresh_insights_cache_if_stale_locked() -> None:
    global _INSIGHTS_CACHE_SIGNATURE
    signature = _results_signature(_list_result_files())
    if _INSIGHTS_CACHE_SIGNATURE == signature:
        return
    _INSIGHTS_CACHE.clear()
    _INSIGHTS_CACHE_ORDER.clear()
    _INSIGHTS_CACHE_SIGNATURE = signature


def _get_cached_insights_response(cache_key: str) -> Any | None:
    with _INSIGHTS_CACHE_LOCK:
        _refresh_insights_cache_if_stale_locked()
        value = _INSIGHTS_CACHE.get(cache_key)
        if value is None:
            return None
        try:
            _INSIGHTS_CACHE_ORDER.remove(cache_key)
        except ValueError:
            pass
        _INSIGHTS_CACHE_ORDER.append(cache_key)
        return value


def _set_cached_insights_response(cache_key: str, value: Any) -> None:
    with _INSIGHTS_CACHE_LOCK:
        _refresh_insights_cache_if_stale_locked()
        _INSIGHTS_CACHE[cache_key] = value
        try:
            _INSIGHTS_CACHE_ORDER.remove(cache_key)
        except ValueError:
            pass
        _INSIGHTS_CACHE_ORDER.append(cache_key)
        while len(_INSIGHTS_CACHE_ORDER) > _INSIGHTS_CACHE_MAX_ENTRIES:
            evicted = _INSIGHTS_CACHE_ORDER.pop(0)
            _INSIGHTS_CACHE.pop(evicted, None)


def _insights_warmup_status_snapshot() -> dict[str, Any]:
    with _INSIGHTS_WARMUP_LOCK:
        return dict(_INSIGHTS_WARMUP_STATUS)


def _set_insights_warmup_status(**updates: Any) -> None:
    with _INSIGHTS_WARMUP_LOCK:
        _INSIGHTS_WARMUP_STATUS.update(updates)


def _iter_brand_market_pairs_for_warmup(cfg: dict[str, Any]) -> list[tuple[str, str]]:
    markets_by_brand = cfg.get("markets_by_brand", {}) or {}
    default_brand = str(cfg.get("default_brand", "") or "")
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _append_pair(brand: str, market: str) -> None:
        key = (brand, market)
        if key in seen:
            return
        seen.add(key)
        pairs.append(key)

    if default_brand and default_brand in markets_by_brand:
        for market in markets_by_brand.get(default_brand, []) or []:
            _append_pair(default_brand, str(market))

    for brand in sorted(markets_by_brand.keys()):
        for market in markets_by_brand.get(brand, []) or []:
            _append_pair(str(brand), str(market))
    return pairs


def _warm_insights_cache_worker() -> None:
    started_at = time.time()
    _set_insights_warmup_status(
        state="running",
        started_at=started_at,
        completed_at=None,
        duration_seconds=None,
        completed_pairs=0,
        failed_pairs=0,
        last_error=None,
    )
    failed_pairs = 0
    completed_pairs = 0
    try:
        cfg = _build_auto_config()
        pairs = _iter_brand_market_pairs_for_warmup(cfg)
        _set_insights_warmup_status(total_pairs=len(pairs))
        for brand, market in pairs:
            try:
                service_s_curves_auto(
                    SCurveAutoRequest(selected_brand=brand, selected_markets=[market], points=41, min_scale=0.2, max_scale=2.5)
                )
                service_contributions_auto(ContributionAutoRequest(selected_brand=brand, selected_market=market, top_n=8))
                service_yoy_growth_auto(YoyGrowthRequest(selected_brand=brand, selected_market=market))
                service_driver_analysis_auto(DriverAnalysisRequest(selected_brand=brand, selected_market=market, months_back=3, top_n=8))
            except Exception as exc:  # noqa: BLE001
                failed_pairs += 1
                if failed_pairs <= 5:
                    _set_insights_warmup_status(last_error=f"{brand} / {market}: {exc}")
            finally:
                completed_pairs += 1
                _set_insights_warmup_status(completed_pairs=completed_pairs, failed_pairs=failed_pairs)
        completed_at = time.time()
        _set_insights_warmup_status(
            state="completed" if failed_pairs == 0 else "completed",
            completed_at=completed_at,
            duration_seconds=round(completed_at - started_at, 3),
            failed_pairs=failed_pairs,
        )
    except Exception as exc:  # noqa: BLE001
        completed_at = time.time()
        _set_insights_warmup_status(
            state="failed",
            completed_at=completed_at,
            duration_seconds=round(completed_at - started_at, 3),
            last_error=str(exc),
        )
    finally:
        global _INSIGHTS_WARMUP_THREAD
        with _INSIGHTS_WARMUP_LOCK:
            _INSIGHTS_WARMUP_THREAD = None


def trigger_insights_cache_warmup() -> dict[str, Any]:
    """
    Trigger non-blocking warmup for insights cache.
    Used on app startup and auto-config calls so first user experience is faster.
    """
    if not _INSIGHTS_WARMUP_ON_START:
        _set_insights_warmup_status(state="disabled", enabled=False)
        return _insights_warmup_status_snapshot()

    current_signature = _results_signature(_list_result_files())
    global _INSIGHTS_WARMUP_THREAD
    with _INSIGHTS_WARMUP_LOCK:
        thread_alive = _INSIGHTS_WARMUP_THREAD is not None and _INSIGHTS_WARMUP_THREAD.is_alive()
        current_state = str(_INSIGHTS_WARMUP_STATUS.get("state", "idle"))
        if thread_alive or current_state in {"queued", "running"}:
            return dict(_INSIGHTS_WARMUP_STATUS)
        if current_state == "completed" and _INSIGHTS_CACHE_SIGNATURE == current_signature:
            return dict(_INSIGHTS_WARMUP_STATUS)
        _INSIGHTS_WARMUP_STATUS.update(
            {
                "enabled": True,
                "state": "queued",
                "started_at": None,
                "completed_at": None,
                "duration_seconds": None,
                "total_pairs": 0,
                "completed_pairs": 0,
                "failed_pairs": 0,
                "last_error": None,
            }
        )
        worker = threading.Thread(target=_warm_insights_cache_worker, name="insights-cache-warmup", daemon=True)
        _INSIGHTS_WARMUP_THREAD = worker
        worker.start()
        return dict(_INSIGHTS_WARMUP_STATUS)


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


def _normalize_name_key(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = unicodedata.normalize("NFKD", raw)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def _elasticity_responsiveness_label(overall: float | None, tv: float | None, digital: float | None) -> str:
    candidates = [v for v in [overall, tv, digital] if v is not None and np.isfinite(v)]
    if not candidates:
        return "Unknown"
    score = float(np.nanmean(np.array(candidates, dtype=float)))
    if score >= 0.2:
        return "High"
    if score >= 0.08:
        return "Medium"
    return "Low"


def _build_market_elasticity_guidance(
    national_path: Path | None,
    brand: str,
    selected_markets: list[str],
) -> dict[str, Any]:
    guidance: dict[str, Any] = {
        "source_file": national_path.name if national_path else None,
        "sheet_name": None,
        "brand": brand,
        "matched_row_count": 0,
        "rows": [],
        "notes": [],
    }
    if national_path is None:
        guidance["notes"] = ["National elasticity file not found in results."]
        return guidance

    try:
        xls = pd.ExcelFile(national_path)
    except Exception:
        guidance["notes"] = ["Could not open national elasticity file."]
        return guidance

    target_brand_key = _normalize_name_key(brand)
    candidate_sheets = [s for s in xls.sheet_names if _normalize_name_key(s) != _normalize_name_key("National level learnings")]
    matched_sheet = next((s for s in candidate_sheets if _normalize_name_key(s) == target_brand_key), None)
    if matched_sheet is None and candidate_sheets:
        matched_sheet = next(
            (s for s in candidate_sheets if target_brand_key and target_brand_key in _normalize_name_key(s)),
            None,
        )
    if not matched_sheet:
        guidance["notes"] = [f"No elasticity sheet found for brand '{brand}'."]
        return guidance

    guidance["sheet_name"] = matched_sheet
    try:
        df = pd.read_excel(national_path, sheet_name=matched_sheet)
    except Exception:
        guidance["notes"] = [f"Could not read sheet '{matched_sheet}'."]
        return guidance

    df.columns = [str(c).strip() for c in df.columns]
    market_col = next((c for c in df.columns if _normalize_name_key(c) == _normalize_name_key("Market")), "")
    overall_col = next((c for c in df.columns if _normalize_name_key(c) == _normalize_name_key("Overall media elasticity")), "")
    tv_col = next((c for c in df.columns if _normalize_name_key(c) == _normalize_name_key("TV_Reach_Elasticity")), "")
    digital_col = next((c for c in df.columns if _normalize_name_key(c) == _normalize_name_key("Digital_Reach_Elasticity")), "")

    if not market_col:
        guidance["notes"] = [f"Sheet '{matched_sheet}' does not contain Market column."]
        return guidance

    selected_market_map = {_normalize_name_key(m): str(m).strip() for m in selected_markets if str(m).strip()}
    rows: list[dict[str, Any]] = []
    work = df.copy()
    work["_market_key"] = work[market_col].astype(str).map(_normalize_name_key)
    for _, row in work.iterrows():
        mkey = str(row.get("_market_key", "")).strip()
        if not mkey or mkey not in selected_market_map:
            continue
        market_name = selected_market_map[mkey]
        overall = float(_finite(row.get(overall_col, np.nan), np.nan)) if overall_col else np.nan
        tv = float(_finite(row.get(tv_col, np.nan), np.nan)) if tv_col else np.nan
        digital = float(_finite(row.get(digital_col, np.nan), np.nan)) if digital_col else np.nan
        overall_val = overall if np.isfinite(overall) else None
        tv_val = tv if np.isfinite(tv) else None
        digital_val = digital if np.isfinite(digital) else None
        rows.append(
            {
                "market": market_name,
                "overall_media_elasticity": None if overall_val is None else round(overall_val, 6),
                "tv_reach_elasticity": None if tv_val is None else round(tv_val, 6),
                "digital_reach_elasticity": None if digital_val is None else round(digital_val, 6),
                "responsiveness_label": _elasticity_responsiveness_label(overall_val, tv_val, digital_val),
            }
        )

    if rows:
        order = {m: i for i, m in enumerate(selected_markets)}
        rows = sorted(rows, key=lambda r: order.get(str(r.get("market", "")), 10**6))
        guidance["matched_row_count"] = len(rows)
        guidance["rows"] = rows
        missing_markets = [m for m in selected_markets if m not in {str(r.get("market", "")) for r in rows}]
        if missing_markets:
            guidance["notes"] = [f"Elasticity guidance missing for {len(missing_markets)} selected markets."]
    else:
        guidance["notes"] = [f"No elasticity rows matched selected markets for brand '{brand}'."]
    return guidance


def _detect_market_intelligence_file() -> Path | None:
    preferred = BASE_DIR / "MMM (1).xlsx"
    if preferred.exists() and preferred.is_file():
        return preferred
    candidates = [BASE_DIR / "MMM.xlsx", BASE_DIR / "MMM 1.xlsx"]
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def _normalize_percent_like(value: Any) -> float | None:
    try:
        raw = float(value)
    except Exception:
        return None
    if not np.isfinite(raw):
        return None
    if abs(raw) <= 1.5:
        raw *= 100.0
    return float(raw)


def _compute_relative_metric_bands(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    arr = np.array(values, dtype=float)
    return float(np.percentile(arr, 33.3333)), float(np.percentile(arr, 66.6667))


def _assign_relative_band(value: float | None, low_cut: float, high_cut: float) -> str:
    if value is None or not np.isfinite(value):
        return "unknown"
    if value <= low_cut:
        return "low"
    if value >= high_cut:
        return "high"
    return "medium"


def _compute_momentum_band(value: float | None, abs_values: list[float]) -> str:
    if value is None or not np.isfinite(value):
        return "unknown"
    magnitude = abs(float(value))
    non_zero = [v for v in abs_values if np.isfinite(v) and abs(v) > 1e-9]
    if not non_zero:
        return "neutral"
    mild_cut = float(np.percentile(np.array(non_zero, dtype=float), 33.3333))
    strong_cut = float(np.percentile(np.array(non_zero, dtype=float), 66.6667))
    neutral_cut = max(0.1, mild_cut * 0.5)
    if magnitude < neutral_cut:
        return "neutral"
    if value > 0:
        return "strong_positive" if magnitude >= strong_cut else "mild_positive"
    if value < 0:
        return "strong_negative" if magnitude >= strong_cut else "mild_negative"
    return "neutral"


def _build_market_intelligence_guidance(
    brand: str,
    selected_markets: list[str],
    market_data: dict[str, dict[str, Any]],
    elasticity_guidance: dict[str, Any] | None = None,
    overrides: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    guidance: dict[str, Any] = {
        "source_file": None,
        "sheet_name": "GERC Market-Level",
        "brand": brand,
        "matched_row_count": 0,
        "rows": [],
        "notes": [],
    }
    path = _detect_market_intelligence_file()
    if path is None:
        guidance["notes"] = ["Market intelligence workbook not found."]
        return guidance
    guidance["source_file"] = path.name
    try:
        df = pd.read_excel(path, sheet_name="GERC Market-Level")
    except Exception:
        guidance["notes"] = ["Could not read market intelligence workbook sheet 'GERC Market-Level'."]
        return guidance

    df.columns = [str(c).strip() for c in df.columns]
    required_cols = {
        "brand": next((c for c in df.columns if _normalize_name_key(c) == _normalize_name_key("Brand")), ""),
        "market": next((c for c in df.columns if _normalize_name_key(c) == _normalize_name_key("Market")), ""),
        "category_salience": next((c for c in df.columns if _normalize_name_key(c) == _normalize_name_key("Category salience")), ""),
        "brand_salience": next((c for c in df.columns if _normalize_name_key(c) == _normalize_name_key("Brand salience")), ""),
        "market_share": next((c for c in df.columns if _normalize_name_key(c) == _normalize_name_key("Market share")), ""),
        "change_in_market_share": next((c for c in df.columns if _normalize_name_key(c) == _normalize_name_key("Change in market share")), ""),
        "change_in_brand_equity": next((c for c in df.columns if _normalize_name_key(c) == _normalize_name_key("Change in brand equity")), ""),
    }
    if not required_cols["market"]:
        guidance["notes"] = ["Market intelligence sheet is missing Market column."]
        return guidance

    work = df.copy()
    work["_market_key"] = work[required_cols["market"]].astype(str).map(_normalize_name_key)
    selected_market_map = {_normalize_name_key(m): str(m).strip() for m in selected_markets if str(m).strip()}
    filtered = work[work["_market_key"].isin(set(selected_market_map.keys()))].copy()
    if not filtered.empty:
        filtered = filtered.drop_duplicates(subset=["_market_key"], keep="first")
    if filtered.empty:
        guidance["notes"] = ["No market intelligence rows matched the selected markets in the shared market-level MMM sheet."]
        return guidance

    elasticity_map = {
        str(row.get("market", "")).strip(): row
        for row in (elasticity_guidance or {}).get("rows", [])
        if isinstance(row, dict) and str(row.get("market", "")).strip()
    }
    rows: list[dict[str, Any]] = []
    for _, row in filtered.iterrows():
        market_name = selected_market_map.get(str(row.get("_market_key", "")).strip(), "")
        if not market_name:
            continue
        md = market_data.get(market_name, {})
        elasticity_row = elasticity_map.get(market_name, {})
        avg_cpr = float(
            np.nanmean(
                np.array(
                    [
                        float(_finite(md.get("tv_cpr", np.nan), np.nan)),
                        float(_finite(md.get("digital_cpr", np.nan), np.nan)),
                    ],
                    dtype=float,
                )
            )
        ) if md else np.nan
        target_reach_share_raw = _finite(((overrides or {}).get(market_name, {}) or {}).get("target_reach_share_pct"), np.nan)
        target_reach_share_pct = float(target_reach_share_raw) if np.isfinite(target_reach_share_raw) else None
        rows.append(
            {
                "market": market_name,
                "category_salience": _normalize_percent_like(row.get(required_cols["category_salience"])),
                "brand_salience": _normalize_percent_like(row.get(required_cols["brand_salience"])),
                "market_share": _normalize_percent_like(row.get(required_cols["market_share"])),
                "change_in_market_share": _normalize_percent_like(row.get(required_cols["change_in_market_share"])),
                "change_in_brand_equity": _normalize_percent_like(row.get(required_cols["change_in_brand_equity"])),
                "overall_media_elasticity": _finite(elasticity_row.get("overall_media_elasticity", np.nan), np.nan),
                "tv_reach_elasticity": _finite(elasticity_row.get("tv_reach_elasticity", np.nan), np.nan),
                "digital_reach_elasticity": _finite(elasticity_row.get("digital_reach_elasticity", np.nan), np.nan),
                "responsiveness_label": str(elasticity_row.get("responsiveness_label", "Unknown")),
                "tv_cpr": float(_finite(md.get("tv_cpr", np.nan), np.nan)),
                "digital_cpr": float(_finite(md.get("digital_cpr", np.nan), np.nan)),
                "avg_cpr": avg_cpr if np.isfinite(avg_cpr) else None,
                "target_reach_share_pct": target_reach_share_pct,
            }
        )

    order = {m: i for i, m in enumerate(selected_markets)}
    rows = sorted(rows, key=lambda r: order.get(str(r.get("market", "")), 10**6))
    if not rows:
        guidance["notes"] = ["No market intelligence rows matched the selected markets in the shared market-level MMM sheet."]
        return guidance

    for metric_key in ("category_salience", "brand_salience", "market_share"):
        metric_vals = [float(v) for v in [r.get(metric_key) for r in rows] if v is not None and np.isfinite(v)]
        low_cut, high_cut = _compute_relative_metric_bands(metric_vals)
        for item in rows:
            item[f"{metric_key}_band"] = _assign_relative_band(
                float(item[metric_key]) if item.get(metric_key) is not None else None,
                low_cut,
                high_cut,
            )

    for metric_key in ("change_in_market_share", "change_in_brand_equity"):
        abs_vals = [abs(float(v)) for v in [r.get(metric_key) for r in rows] if v is not None and np.isfinite(v)]
        for item in rows:
            metric_val = float(item[metric_key]) if item.get(metric_key) is not None else None
            item[f"{metric_key}_band"] = _compute_momentum_band(metric_val, abs_vals)

    avg_cpr_vals = [float(v) for v in [r.get("avg_cpr") for r in rows] if v is not None and np.isfinite(v)]
    low_cut, high_cut = _compute_relative_metric_bands(avg_cpr_vals)
    for item in rows:
        avg_cpr = float(item["avg_cpr"]) if item.get("avg_cpr") is not None else None
        band = _assign_relative_band(avg_cpr, low_cut, high_cut)
        if band == "high":
            item["avg_cpr_band"] = "high_cost"
        elif band == "low":
            item["avg_cpr_band"] = "low_cost"
        else:
            item["avg_cpr_band"] = "mid_cost" if band == "medium" else "unknown"

    guidance["matched_row_count"] = len(rows)
    guidance["rows"] = rows
    missing_markets = [m for m in selected_markets if m not in {str(r.get("market", "")) for r in rows}]
    guidance["notes"] = ["Using shared market-level MMM guidance across brands."]
    if missing_markets:
        guidance["notes"].append(f"Market intelligence missing for {len(missing_markets)} selected markets.")
    return guidance


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
    brand_mins: dict[str, float] | None = None,
    brand_maxs: dict[str, float] | None = None,
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

    mins_arr: list[float] = []
    maxs_arr: list[float] = []
    for b in brands:
        fallback_min = baselines[b] * (1.0 - max_change_pct)
        fallback_max = baselines[b] * (1.0 + max_change_pct)
        bmin = float(_finite((brand_mins or {}).get(b, fallback_min), fallback_min))
        bmax = float(_finite((brand_maxs or {}).get(b, fallback_max), fallback_max))
        bmin = max(0.0, bmin)
        bmax = max(bmin, bmax)
        mins_arr.append(bmin)
        maxs_arr.append(bmax)
    mins = np.array(mins_arr, dtype=float)
    maxs = np.array(maxs_arr, dtype=float)
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


def _compute_brand_capacity_bounds(selected_brands: list[str]) -> dict[str, tuple[float, float]]:
    """
    Compute Step-1 brand min/max spend from market capacity bounds using all markets per brand.
    """
    out: dict[str, tuple[float, float]] = {}
    for brand in selected_brands:
        try:
            ctx = _load_optimization_context(
                OptimizeAutoRequest(
                    selected_brand=brand,
                    selected_markets=[],
                    budget_increase_type="percentage",
                    budget_increase_value=0.0,
                    market_overrides={},
                )
            )
        except Exception:
            continue
        limits_map: dict[str, dict[str, float | None]] = ctx.get("limits_map", {})
        regions: list[str] = ctx.get("regions", [])
        if not regions:
            continue
        brand_min = 0.0
        brand_max = 0.0
        for region in regions:
            lim = limits_map.get(region, {})
            min_tv = max(0.0, float(_finite(lim.get("min_tv_spend", 0.0), 0.0)))
            min_dg = max(0.0, float(_finite(lim.get("min_digital_spend", 0.0), 0.0)))
            max_tv_raw = float(_finite(lim.get("max_tv_spend", min_tv), min_tv))
            max_dg_raw = float(_finite(lim.get("max_digital_spend", min_dg), min_dg))
            max_tv = max(min_tv, max_tv_raw)
            max_dg = max(min_dg, max_dg_raw)
            brand_min += min_tv + min_dg
            brand_max += max_tv + max_dg
        out[brand] = (float(brand_min), float(brand_max))
    return out


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

    brand_capacity_bounds = _compute_brand_capacity_bounds(selected)
    brand_mins: dict[str, float] = {}
    brand_maxs: dict[str, float] = {}
    for b in selected:
        fallback_min = baselines[b] * 0.75
        fallback_max = baselines[b] * 1.25
        bmin, bmax = brand_capacity_bounds.get(b, (fallback_min, fallback_max))
        bmin = max(0.0, float(_finite(bmin, fallback_min)))
        bmax = max(bmin, float(_finite(bmax, fallback_max)))
        brand_mins[b] = bmin
        brand_maxs[b] = bmax

    allocations, target_total, feasible_min_total, feasible_max_total = _optimize_revenue_allocation_with_brand_bounds(
        baselines=baselines,
        baseline_volumes=baseline_volumes,
        avg_prices=avg_prices,
        effective_elasticities=effective_elasticities,
        target_total=target_total_requested,
        brand_mins=brand_mins,
        brand_maxs=brand_maxs,
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
            "min_allowed_budget": round(float(brand_mins.get(brand, baselines[brand] * 0.75)), 2),
            "max_allowed_budget": round(float(brand_maxs.get(brand, baselines[brand] * 1.25)), 2),
            "min_change_pct": round(
                float(
                    ((brand_mins.get(brand, baselines[brand] * 0.75) - baselines[brand]) / baselines[brand] * 100.0)
                    if baselines[brand] > 1e-12
                    else 0.0
                ),
                2,
            ),
            "max_change_pct": round(
                float(
                    ((brand_maxs.get(brand, baselines[brand] * 1.25) - baselines[brand]) / baselines[brand] * 100.0)
                    if baselines[brand] > 1e-12
                    else 0.0
                ),
                2,
            ),
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
            "brand_bounds_mode": "market_capacity_derived",
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


def _build_fast_seed_vector(
    market_data: dict[str, dict[str, Any]],
    regions: list[str],
    bounds: list[tuple[float, float]],
    baseline_budget: float,
    target_budget: float,
    region_prices: dict[str, float],
    objective: str = "volume",
    elasticity_map: dict[str, dict[str, Any]] | None = None,
) -> np.ndarray:
    vector = np.zeros(2 * len(regions), dtype=float)
    increasing_budget = float(target_budget) >= float(baseline_budget)

    for idx, region in enumerate(regions):
        md = market_data[region]
        tv_i = 2 * idx
        dg_i = tv_i + 1
        tv_lo, tv_hi = bounds[tv_i]
        dg_lo, dg_hi = bounds[dg_i]

        tv_probe = min(max(0.12, min(0.3, tv_hi)), tv_hi) if increasing_budget else max(min(-0.12, max(-0.3, tv_lo)), tv_lo)
        dg_probe = min(max(0.12, min(0.3, dg_hi)), dg_hi) if increasing_budget else max(min(-0.12, max(-0.3, dg_lo)), dg_lo)

        # Use TV/Digital elasticity ratio from the India-level file to guide within-market split.
        # For increasing budgets: allocate proportional to elasticity (higher elasticity → more spend).
        # For decreasing budgets: protect the more elastic channel (cut proportional to the other's elasticity).
        el_row = (elasticity_map or {}).get(region, {})
        tv_el = float(_finite(el_row.get("tv_reach_elasticity", 0.0), 0.0)) if el_row else 0.0
        dg_el = float(_finite(el_row.get("digital_reach_elasticity", 0.0), 0.0)) if el_row else 0.0
        el_sum = max(0.0, tv_el) + max(0.0, dg_el)
        use_elasticity_split = el_sum > 1e-9 and tv_el > 0.0 and dg_el > 0.0

        if use_elasticity_split:
            tv_el_share = max(0.0, tv_el) / el_sum
            dg_el_share = 1.0 - tv_el_share
            if increasing_budget:
                vector[tv_i] = min(tv_hi, max(0.0, tv_hi * tv_el_share))
                vector[dg_i] = min(dg_hi, max(0.0, dg_hi * dg_el_share))
            else:
                # Protect more elastic channel: cut it less (inverse share)
                tv_cut_share = dg_el_share
                dg_cut_share = tv_el_share
                vector[tv_i] = max(tv_lo, min(0.0, tv_lo * tv_cut_share))
                vector[dg_i] = max(dg_lo, min(0.0, dg_lo * dg_cut_share))
        else:
            base_volume = float(_predict_region_volume(md, 0.0, 0.0))
            tv_volume = float(_predict_region_volume(md, tv_probe, 0.0)) if abs(tv_probe) > 1e-9 else base_volume
            dg_volume = float(_predict_region_volume(md, 0.0, dg_probe)) if abs(dg_probe) > 1e-9 else base_volume

            price = max(0.0, float(_finite(region_prices.get(region, 1.0), 1.0)))
            metric_scale = price if objective == "revenue" else 1.0
            tv_metric_gain = (tv_volume - base_volume) * metric_scale
            dg_metric_gain = (dg_volume - base_volume) * metric_scale

            tv_cost = max(1.0, abs(float(np.sum(md["r_tv_list"])) * float(md["tv_cpr"]) * tv_probe))
            dg_cost = max(1.0, abs(float(np.sum(md["r_dig_list"])) * float(md["digital_cpr"]) * dg_probe))
            tv_roi = float(tv_metric_gain / tv_cost) if np.isfinite(tv_metric_gain) else 0.0
            dg_roi = float(dg_metric_gain / dg_cost) if np.isfinite(dg_metric_gain) else 0.0

            if increasing_budget:
                tv_score = max(0.0, tv_roi)
                dg_score = max(0.0, dg_roi)
                score_sum = tv_score + dg_score
                if score_sum <= 1e-12:
                    vector[tv_i] = min(tv_hi, max(0.0, tv_probe))
                    vector[dg_i] = min(dg_hi, max(0.0, dg_probe))
                else:
                    vector[tv_i] = min(tv_hi, max(0.0, tv_hi * (tv_score / score_sum)))
                    vector[dg_i] = min(dg_hi, max(0.0, dg_hi * (dg_score / score_sum)))
            else:
                tv_score = max(0.0, -tv_roi)
                dg_score = max(0.0, -dg_roi)
                score_sum = tv_score + dg_score
                if score_sum <= 1e-12:
                    vector[tv_i] = max(tv_lo, min(0.0, tv_probe))
                    vector[dg_i] = max(dg_lo, min(0.0, dg_probe))
                else:
                    vector[tv_i] = max(tv_lo, min(0.0, tv_lo * (tv_score / score_sum)))
                    vector[dg_i] = max(dg_lo, min(0.0, dg_lo * (dg_score / score_sum)))

    return vector


def _budget_constraint(v: np.ndarray, market_data: dict[str, dict[str, Any]], regions: list[str], B: float) -> float:
    total_spend = 0.0
    for i, region in enumerate(regions):
        md = market_data[region]
        x, y = float(v[2 * i]), float(v[2 * i + 1])
        total_spend += md["tv_cpr"] * float(np.sum(md["r_tv_list"])) * (1.0 + x) + md["digital_cpr"] * float(np.sum(md["r_dig_list"])) * (1.0 + y)
    return B - total_spend


def _extract_target_reach_share_overrides(
    regions: list[str],
    overrides: dict[str, dict[str, float]] | None,
) -> dict[str, float]:
    out: dict[str, float] = {}
    if not overrides:
        return out
    region_set = {str(r).strip() for r in regions}
    for region, values in overrides.items():
        r = str(region).strip()
        if r not in region_set or not isinstance(values, dict):
            continue
        raw = _finite(values.get("target_reach_share_pct"), np.nan)
        if not np.isfinite(raw):
            continue
        out[r] = float(min(max(raw, 0.0), 100.0))
    return out


def _is_reach_share_targets_satisfied(
    vector: np.ndarray,
    market_data: dict[str, dict[str, Any]],
    regions: list[str],
    overrides: dict[str, dict[str, float]] | None,
    tolerance_pct: float = REACH_SHARE_TARGET_TOLERANCE_PCT,
) -> bool:
    target_map = _extract_target_reach_share_overrides(regions, overrides)
    if not target_map:
        return True
    reaches: list[float] = []
    total_reach = 0.0
    for idx, region in enumerate(regions):
        md = market_data[region]
        tv_base = float(np.sum(md["r_tv_list"]))
        dg_base = float(np.sum(md["r_dig_list"]))
        reach = tv_base * (1.0 + float(vector[2 * idx])) + dg_base * (1.0 + float(vector[2 * idx + 1]))
        reach = max(0.0, float(reach))
        reaches.append(reach)
        total_reach += reach
    if total_reach <= 1e-12:
        return False
    tol = max(0.0, float(tolerance_pct)) / 100.0
    for idx, region in enumerate(regions):
        if region not in target_map:
            continue
        target = float(target_map[region]) / 100.0
        lower = max(0.0, target - tol)
        upper = min(1.0, target + tol)
        share = reaches[idx] / total_reach
        if share < lower - 1e-6 or share > upper + 1e-6:
            return False
    return True


def _build_constraints(
    market_data: dict[str, dict[str, Any]],
    regions: list[str],
    B: float,
    limits_map: dict[str, dict[str, float | None]],
    overrides: dict[str, dict[str, float]] | None = None,
) -> list[dict[str, Any]]:
    cons: list[dict[str, Any]] = [{"type": "eq", "fun": lambda v: _budget_constraint(v, market_data, regions, B)}]
    tv_low, tv_high, dg_low, dg_high = 0.001, 3.0, 0.001, 4.0
    tv_bases = [float(np.sum(market_data[region]["r_tv_list"])) for region in regions]
    dg_bases = [float(np.sum(market_data[region]["r_dig_list"])) for region in regions]

    def _total_reach(v: np.ndarray, tv_vals: list[float], dg_vals: list[float]) -> float:
        total = 0.0
        for idx in range(len(tv_vals)):
            total += tv_vals[idx] * (1.0 + float(v[2 * idx])) + dg_vals[idx] * (1.0 + float(v[2 * idx + 1]))
        return float(total)

    def _market_reach(v: np.ndarray, idx: int, tv_vals: list[float], dg_vals: list[float]) -> float:
        return float(tv_vals[idx] * (1.0 + float(v[2 * idx])) + dg_vals[idx] * (1.0 + float(v[2 * idx + 1])))

    for i, region in enumerate(regions):
        md = market_data[region]
        tv_base, dg_base = tv_bases[i], dg_bases[i]
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

    target_share_map = _extract_target_reach_share_overrides(regions, overrides)
    if target_share_map:
        tol = max(0.0, REACH_SHARE_TARGET_TOLERANCE_PCT) / 100.0
        region_index = {region: idx for idx, region in enumerate(regions)}
        for region, target_pct in target_share_map.items():
            idx = region_index.get(region)
            if idx is None:
                continue
            target = float(target_pct) / 100.0
            lower = max(0.0, target - tol)
            upper = min(1.0, target + tol)
            cons.append(
                {
                    "type": "ineq",
                    "fun": lambda v, idx=idx, lb=lower, tv_vals=tv_bases, dg_vals=dg_bases: _market_reach(v, idx, tv_vals, dg_vals)
                    - (lb * _total_reach(v, tv_vals, dg_vals))
                    + 1e-6,
                }
            )
            cons.append(
                {
                    "type": "ineq",
                    "fun": lambda v, idx=idx, ub=upper, tv_vals=tv_bases, dg_vals=dg_bases: (ub * _total_reach(v, tv_vals, dg_vals))
                    - _market_reach(v, idx, tv_vals, dg_vals)
                    + 1e-6,
                }
            )
    return cons


def _run_solver_with_objective(
    market_data: dict[str, dict[str, Any]],
    regions: list[str],
    B: float,
    limits_map: dict[str, dict[str, float | None]],
    overrides: dict[str, dict[str, float]] | None,
    objective_fn: Any,
    objective_args: tuple[Any, ...] = (),
) -> tuple[np.ndarray, dict[str, Any]]:
    n_vars = 2 * len(regions)
    x0 = np.zeros(n_vars, dtype=float)
    bounds = [(-0.999, 4.0)] * n_vars
    cons = _build_constraints(market_data, regions, B, limits_map, overrides=overrides)
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
    overrides: dict[str, dict[str, float]] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    return _run_solver_with_objective(
        market_data=market_data,
        regions=regions,
        B=B,
        limits_map=limits_map,
        overrides=overrides,
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
    national_path = _detect_national_learnings_file()
    market_elasticity_guidance = _build_market_elasticity_guidance(
        national_path=national_path,
        brand=brand,
        selected_markets=regions,
    )
    market_intelligence_guidance = _build_market_intelligence_guidance(
        brand=brand,
        selected_markets=regions,
        market_data=market_data,
        elasticity_guidance=market_elasticity_guidance,
        overrides=overrides,
    )

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
        "market_elasticity_guidance": market_elasticity_guidance,
        "market_intelligence_guidance": market_intelligence_guidance,
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


SCENARIO_MARKET_LIMIT_ROUNDING = 1_000_000.0
SCENARIO_MARKET_CHANGE_STEP = 2_500_000.0


def _round_to_unit(value: float, unit: float) -> float:
    if unit <= 0:
        return float(value)
    return float(round(float(value) / float(unit)) * float(unit))


def _clamp(value: float, lower: float, upper: float) -> float:
    return float(min(max(float(value), float(lower)), float(upper)))


def _quantize_market_total_spend(
    current_spend: float,
    proposed_spend: float,
    min_spend: float,
    max_spend: float,
    step: float = SCENARIO_MARKET_CHANGE_STEP,
) -> float:
    min_spend = float(min(min_spend, max_spend))
    max_spend = float(max(min_spend, max_spend))
    proposed_spend = _clamp(proposed_spend, min_spend, max_spend)
    delta = float(proposed_spend - current_spend)
    quantized_delta = _round_to_unit(delta, step)
    quantized_total = _clamp(current_spend + quantized_delta, min_spend, max_spend)
    return float(quantized_total)


def _allocate_two_channel_spend(
    target_total: float,
    proposed_tv_spend: float,
    proposed_digital_spend: float,
    min_tv_spend: float,
    max_tv_spend: float,
    min_digital_spend: float,
    max_digital_spend: float,
) -> tuple[float, float] | None:
    target_total = float(target_total)
    min_tv_spend = float(min_tv_spend)
    max_tv_spend = float(max(max_tv_spend, min_tv_spend))
    min_digital_spend = float(min_digital_spend)
    max_digital_spend = float(max(max_digital_spend, min_digital_spend))
    feasible_min = min_tv_spend + min_digital_spend
    feasible_max = max_tv_spend + max_digital_spend
    if target_total < feasible_min - 1e-6 or target_total > feasible_max + 1e-6:
        return None

    total_proposed = float(max(0.0, proposed_tv_spend) + max(0.0, proposed_digital_spend))
    tv_share = (float(max(0.0, proposed_tv_spend)) / total_proposed) if total_proposed > 1e-9 else 0.5
    tv_spend = _clamp(target_total * tv_share, min_tv_spend, max_tv_spend)
    digital_spend = target_total - tv_spend

    if digital_spend < min_digital_spend:
        digital_spend = min_digital_spend
        tv_spend = target_total - digital_spend
    elif digital_spend > max_digital_spend:
        digital_spend = max_digital_spend
        tv_spend = target_total - digital_spend

    tv_spend = _clamp(tv_spend, min_tv_spend, max_tv_spend)
    digital_spend = target_total - tv_spend
    if digital_spend < min_digital_spend:
        digital_spend = min_digital_spend
        tv_spend = target_total - digital_spend
    elif digital_spend > max_digital_spend:
        digital_spend = max_digital_spend
        tv_spend = target_total - digital_spend

    if tv_spend < min_tv_spend - 1e-6 or tv_spend > max_tv_spend + 1e-6:
        return None
    if digital_spend < min_digital_spend - 1e-6 or digital_spend > max_digital_spend + 1e-6:
        return None
    return float(tv_spend), float(digital_spend)


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

        tv_min_spend_raw = float(lim.get("min_tv_spend", tv_base * tv_cpr * tv_low) or 0.0)
        tv_max_spend_raw = float(lim.get("max_tv_spend", tv_base * tv_cpr * tv_high) or (tv_base * tv_cpr * tv_high))
        dg_min_spend_raw = float(lim.get("min_digital_spend", dg_base * dg_cpr * dg_low) or 0.0)
        dg_max_spend_raw = float(lim.get("max_digital_spend", dg_base * dg_cpr * dg_high) or (dg_base * dg_cpr * dg_high))

        tv_min_spend = max(0.0, _round_to_unit(tv_min_spend_raw, SCENARIO_MARKET_LIMIT_ROUNDING))
        tv_max_spend = max(tv_min_spend, _round_to_unit(tv_max_spend_raw, SCENARIO_MARKET_LIMIT_ROUNDING))
        dg_min_spend = max(0.0, _round_to_unit(dg_min_spend_raw, SCENARIO_MARKET_LIMIT_ROUNDING))
        dg_max_spend = max(dg_min_spend, _round_to_unit(dg_max_spend_raw, SCENARIO_MARKET_LIMIT_ROUNDING))

        tv_min_reach = (tv_min_spend / tv_cpr) if tv_cpr > 1e-12 else float(lim.get("tv_min_reach", tv_base * tv_low) or 0.0)
        tv_max_reach = (tv_max_spend / tv_cpr) if tv_cpr > 1e-12 else float(lim.get("tv_max_reach", tv_base * tv_high) or (tv_base * tv_high))
        dg_min_reach = (dg_min_spend / dg_cpr) if dg_cpr > 1e-12 else float(lim.get("dg_min_reach", dg_base * dg_low) or 0.0)
        dg_max_reach = (dg_max_spend / dg_cpr) if dg_cpr > 1e-12 else float(lim.get("dg_max_reach", dg_base * dg_high) or (dg_base * dg_high))

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


def _quantize_vector_to_market_budget_steps(
    vector: np.ndarray,
    market_data: dict[str, dict[str, Any]],
    regions: list[str],
    limits_map: dict[str, dict[str, float | None]],
    bounds: list[tuple[float, float]],
) -> np.ndarray | None:
    v = np.array(vector, dtype=float)
    if len(v) != len(bounds):
        return None

    for i, region in enumerate(regions):
        md = market_data[region]
        lim = limits_map.get(region, {})
        tv_base = float(np.sum(md["r_tv_list"]))
        dg_base = float(np.sum(md["r_dig_list"]))
        tv_cpr = float(md["tv_cpr"])
        dg_cpr = float(md["digital_cpr"])
        old_tv_spend = tv_base * tv_cpr
        old_digital_spend = dg_base * dg_cpr
        current_total_spend = float(md["current_spend"])

        proposed_tv_spend = old_tv_spend * (1.0 + float(v[2 * i]))
        proposed_digital_spend = old_digital_spend * (1.0 + float(v[2 * i + 1]))
        proposed_total_spend = proposed_tv_spend + proposed_digital_spend

        min_tv_spend = max(0.0, _round_to_unit(float(lim.get("min_tv_spend", 0.0) or 0.0), SCENARIO_MARKET_LIMIT_ROUNDING))
        max_tv_spend = max(min_tv_spend, _round_to_unit(float(lim.get("max_tv_spend", old_tv_spend * 3.0) or (old_tv_spend * 3.0)), SCENARIO_MARKET_LIMIT_ROUNDING))
        min_digital_spend = max(0.0, _round_to_unit(float(lim.get("min_digital_spend", 0.0) or 0.0), SCENARIO_MARKET_LIMIT_ROUNDING))
        max_digital_spend = max(min_digital_spend, _round_to_unit(float(lim.get("max_digital_spend", old_digital_spend * 3.0) or (old_digital_spend * 3.0)), SCENARIO_MARKET_LIMIT_ROUNDING))

        min_total_spend = min_tv_spend + min_digital_spend
        max_total_spend = max_tv_spend + max_digital_spend
        target_total_spend = _quantize_market_total_spend(
            current_spend=current_total_spend,
            proposed_spend=proposed_total_spend,
            min_spend=min_total_spend,
            max_spend=max_total_spend,
            step=SCENARIO_MARKET_CHANGE_STEP,
        )

        allocated = _allocate_two_channel_spend(
            target_total=target_total_spend,
            proposed_tv_spend=proposed_tv_spend,
            proposed_digital_spend=proposed_digital_spend,
            min_tv_spend=min_tv_spend,
            max_tv_spend=max_tv_spend,
            min_digital_spend=min_digital_spend,
            max_digital_spend=max_digital_spend,
        )
        if allocated is None:
            return None
        tv_target_spend, dg_target_spend = allocated

        x = ((tv_target_spend / old_tv_spend) - 1.0) if old_tv_spend > 1e-12 else 0.0
        y = ((dg_target_spend / old_digital_spend) - 1.0) if old_digital_spend > 1e-12 else 0.0
        x_lo, x_hi = bounds[2 * i]
        y_lo, y_hi = bounds[2 * i + 1]
        v[2 * i] = _clamp(x, x_lo, x_hi)
        v[2 * i + 1] = _clamp(y, y_lo, y_hi)

    return v


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


def _project_vector_to_budget_band(
    vector: np.ndarray,
    lower_budget: float,
    upper_budget: float,
    bounds: list[tuple[float, float]],
    coeffs: np.ndarray,
    baseline_budget: float,
) -> np.ndarray | None:
    """
    Scenario-generation helper:
    Projects candidate vector into variable bounds and then nudges spend into [lower_budget, upper_budget].
    """
    v = np.array(vector, dtype=float)
    if len(v) != len(bounds):
        return None
    for i, (lo, hi) in enumerate(bounds):
        v[i] = min(max(v[i], lo), hi)

    low_target = float(min(lower_budget, upper_budget))
    high_target = float(max(lower_budget, upper_budget))
    eps = max(_budget_epsilon(low_target), _budget_epsilon(high_target))
    curr = baseline_budget + float(np.dot(coeffs, v))
    if (low_target - eps) <= curr <= (high_target + eps):
        return v

    # If above upper bound, spend must be reduced; if below lower bound, spend must be increased.
    if curr > high_target:
        diff = float(curr - high_target)
        idx_order = np.argsort(coeffs)  # lower coeffs first for minimal distortion
        for idx in idx_order:
            c = float(coeffs[idx])
            if abs(c) < 1e-12:
                continue
            lo, _ = bounds[idx]
            room = v[idx] - lo
            if room <= 1e-12:
                continue
            step = min(room, diff / c) if c > 0 else 0.0
            if step > 0:
                v[idx] -= step
                diff -= c * step
            if diff <= eps:
                return v
    else:
        diff = float(low_target - curr)
        idx_order = np.argsort(-coeffs)  # higher coeffs first to reach lower band faster
        for idx in idx_order:
            c = float(coeffs[idx])
            if abs(c) < 1e-12:
                continue
            _, hi = bounds[idx]
            room = hi - v[idx]
            if room <= 1e-12:
                continue
            step = min(room, diff / c) if c > 0 else 0.0
            if step > 0:
                v[idx] += step
                diff -= c * step
            if diff <= eps:
                return v

    curr = baseline_budget + float(np.dot(coeffs, v))
    if (low_target - eps) <= curr <= (high_target + eps):
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


def _is_vector_feasible_in_budget_band(
    vector: np.ndarray,
    lower_budget: float,
    upper_budget: float,
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
    low_target = float(min(lower_budget, upper_budget))
    high_target = float(max(lower_budget, upper_budget))
    eps = max(_budget_epsilon(low_target), _budget_epsilon(high_target))
    return (low_target - eps) <= total_spend <= (high_target + eps)


def _evaluate_solution_vector(
    v: np.ndarray,
    market_data: dict[str, dict[str, Any]],
    regions: list[str],
    limits_map: dict[str, dict[str, float | None]],
    region_prices: dict[str, float] | None = None,
    overrides: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_prev, total_new, total_spend = 0.0, 0.0, 0.0
    weighted_tv, weighted_dg = 0.0, 0.0
    total_baseline_revenue = 0.0
    total_new_revenue = 0.0
    market_new_spend: dict[str, float] = {}
    market_old_reach: dict[str, float] = {}
    market_new_reach: dict[str, float] = {}
    total_old_reach = 0.0
    total_new_reach = 0.0

    for i, region in enumerate(regions):
        md = market_data[region]
        x, y = float(v[2 * i]), float(v[2 * i + 1])
        base_tv = np.array(md["r_tv_list"], dtype=float)
        base_dg = np.array(md["r_dig_list"], dtype=float)
        new_tv = base_tv * (1.0 + x)
        new_dg = base_dg * (1.0 + y)
        new_tv_total, new_dg_total = float(np.sum(new_tv)), float(np.sum(new_dg))
        old_tv_total, old_dg_total = float(np.sum(base_tv)), float(np.sum(base_dg))
        old_total_reach = old_tv_total + old_dg_total
        new_total_reach = new_tv_total + new_dg_total
        new_tv_sp = new_tv_total * float(md["tv_cpr"])
        new_dg_sp = new_dg_total * float(md["digital_cpr"])
        new_sp = new_tv_sp + new_dg_sp
        market_new_spend[region] = new_sp
        market_old_reach[region] = old_total_reach
        market_new_reach[region] = new_total_reach
        total_old_reach += old_total_reach
        total_new_reach += new_total_reach

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
        ov = (overrides or {}).get(region, {}) if isinstance(overrides, dict) else {}
        target_reach_share_raw = _finite((ov or {}).get("target_reach_share_pct"), np.nan)
        target_reach_share_pct = float(min(max(target_reach_share_raw, 0.0), 100.0)) if np.isfinite(target_reach_share_raw) else None
        target_reach_share_min_pct = max(0.0, target_reach_share_pct - REACH_SHARE_TARGET_TOLERANCE_PCT) if target_reach_share_pct is not None else None
        target_reach_share_max_pct = min(100.0, target_reach_share_pct + REACH_SHARE_TARGET_TOLERANCE_PCT) if target_reach_share_pct is not None else None
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
                "new_total_reach": round(new_total_reach, 2),
                "fy25_total_reach": round(old_total_reach, 2),
                "new_reach_share_pct": 0.0,
                "fy25_reach_share_pct": 0.0,
                "new_tv_share": round(tv_split, 4),
                "new_digital_share": round(dg_split, 4),
                "fy25_tv_share": round(old_tv_share, 4),
                "fy25_digital_share": round(old_dg_share, 4),
                "target_reach_share_pct": None if target_reach_share_pct is None else round(target_reach_share_pct, 2),
                "target_reach_share_min_pct": None if target_reach_share_min_pct is None else round(target_reach_share_min_pct, 2),
                "target_reach_share_max_pct": None if target_reach_share_max_pct is None else round(target_reach_share_max_pct, 2),
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
    if total_old_reach > 1e-12 or total_new_reach > 1e-12:
        for row in rows:
            region = str(row["market"])
            old_reach = float(_finite(market_old_reach.get(region, 0.0), 0.0))
            new_reach = float(_finite(market_new_reach.get(region, 0.0), 0.0))
            row["fy25_reach_share_pct"] = round((old_reach / total_old_reach) * 100.0, 2) if total_old_reach > 1e-12 else 0.0
            row["new_reach_share_pct"] = round((new_reach / total_new_reach) * 100.0, 2) if total_new_reach > 1e-12 else 0.0
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
    overrides = ctx.get("overrides", {})
    baseline_budget = float(ctx["baseline_budget"])
    B = float(ctx["target_budget"])
    sol, meta = _run_solver(market_data, regions, B, limits_map, overrides=ctx.get("overrides", {}))

    rows: list[dict[str, Any]] = []
    total_prev, total_new, total_spend = 0.0, 0.0, 0.0
    weighted_tv, weighted_dg = 0.0, 0.0
    market_new_spend: dict[str, float] = {}
    market_new_tv_spend: dict[str, float] = {}
    market_new_dg_spend: dict[str, float] = {}
    market_old_reach: dict[str, float] = {}
    market_new_reach: dict[str, float] = {}
    total_old_reach = 0.0
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
        old_total_reach = old_tv_total + old_dg_total
        new_total_reach_market = new_tv_total + new_dg_total
        new_tv_sp = new_tv_total * float(md["tv_cpr"])
        new_dg_sp = new_dg_total * float(md["digital_cpr"])
        new_sp = new_tv_sp + new_dg_sp
        market_new_spend[region] = new_sp
        market_new_tv_spend[region] = new_tv_sp
        market_new_dg_spend[region] = new_dg_sp
        market_old_reach[region] = old_total_reach
        market_new_reach[region] = new_total_reach_market
        total_old_reach += old_total_reach

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
        ov = overrides.get(region, {}) if isinstance(overrides, dict) else {}
        target_reach_share_raw = _finite((ov or {}).get("target_reach_share_pct"), np.nan)
        target_reach_share_pct = float(min(max(target_reach_share_raw, 0.0), 100.0)) if np.isfinite(target_reach_share_raw) else None
        target_reach_share_min_pct = max(0.0, target_reach_share_pct - REACH_SHARE_TARGET_TOLERANCE_PCT) if target_reach_share_pct is not None else None
        target_reach_share_max_pct = min(100.0, target_reach_share_pct + REACH_SHARE_TARGET_TOLERANCE_PCT) if target_reach_share_pct is not None else None

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
            "new_total_reach": round(new_total_reach_market, 2),
            "fy25_total_reach": round(old_total_reach, 2),
            "new_reach_share_pct": 0.0,
            "fy25_reach_share_pct": 0.0,
            "new_tv_share": round(tv_split, 4),
            "new_digital_share": round(dg_split, 4),
            "fy25_tv_share": round(old_tv_share, 4),
            "fy25_digital_share": round(old_dg_share, 4),
            "target_reach_share_pct": None if target_reach_share_pct is None else round(target_reach_share_pct, 2),
            "target_reach_share_min_pct": None if target_reach_share_min_pct is None else round(target_reach_share_min_pct, 2),
            "target_reach_share_max_pct": None if target_reach_share_max_pct is None else round(target_reach_share_max_pct, 2),
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
        total_new_reach += new_total_reach_market
        weighted_tv += new_sp * tv_split
        weighted_dg += new_sp * dg_split

    if total_spend > 0:
        for r in rows:
            r["new_budget_share"] = round(market_new_spend[r["market"]] / total_spend, 4)
            old_sp = r["old_total_spend"]
            r["extra_budget_share"] = round(((r["new_total_spend"] - old_sp) / (total_spend - baseline_budget)) if abs(total_spend - baseline_budget) > 1e-12 else 0.0, 4)
    if total_old_reach > 1e-12 or total_new_reach > 1e-12:
        for r in rows:
            region = str(r["market"])
            old_reach = float(_finite(market_old_reach.get(region, 0.0), 0.0))
            new_reach = float(_finite(market_new_reach.get(region, 0.0), 0.0))
            r["fy25_reach_share_pct"] = round((old_reach / total_old_reach) * 100.0, 2) if total_old_reach > 1e-12 else 0.0
            r["new_reach_share_pct"] = round((new_reach / total_new_reach) * 100.0, 2) if total_new_reach > 1e-12 else 0.0

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
    overrides = ctx.get("overrides", {})
    market_elasticity_guidance = dict(ctx.get("market_elasticity_guidance", {}) or {})
    baseline_budget = float(ctx["baseline_budget"])
    target_budget = float(ctx["target_budget"])
    bounds, coeffs, baseline_from_bounds = _build_variable_bounds_and_coeffs(market_data, regions, limits_map)
    low_vector = np.array([lo for lo, _ in bounds], dtype=float)
    high_vector = np.array([hi for _, hi in bounds], dtype=float)
    feasible_min_budget = float(baseline_from_bounds + float(np.dot(coeffs, low_vector)))
    feasible_max_budget = float(baseline_from_bounds + float(np.dot(coeffs, high_vector)))
    adjusted_target_budget = float(min(max(target_budget, feasible_min_budget), feasible_max_budget))
    target_within_feasible = abs(adjusted_target_budget - target_budget) <= _budget_epsilon(target_budget)

    rows: list[dict[str, Any]] = []
    total_spend = 0.0
    weighted_tv = 0.0
    weighted_dg = 0.0
    total_baseline_reach = 0.0

    for region in regions:
        md = market_data[region]
        tv_reach = float(np.sum(md["r_tv_list"]))
        dg_reach = float(np.sum(md["r_dig_list"]))
        tv_sp = tv_reach * float(md["tv_cpr"])
        dg_sp = dg_reach * float(md["digital_cpr"])
        total = tv_sp + dg_sp
        total_reach = tv_reach + dg_reach
        tv_split = tv_reach / (tv_reach + dg_reach) if (tv_reach + dg_reach) > 0 else 0.0
        dg_split = 1.0 - tv_split
        lim = limits_map.get(region, {})
        ov = overrides.get(region, {}) if isinstance(overrides, dict) else {}
        target_reach_share_raw = _finite((ov or {}).get("target_reach_share_pct"), np.nan)
        target_reach_share_pct = float(min(max(target_reach_share_raw, 0.0), 100.0)) if np.isfinite(target_reach_share_raw) else None
        target_reach_share_min_pct = max(0.0, target_reach_share_pct - REACH_SHARE_TARGET_TOLERANCE_PCT) if target_reach_share_pct is not None else None
        target_reach_share_max_pct = min(100.0, target_reach_share_pct + REACH_SHARE_TARGET_TOLERANCE_PCT) if target_reach_share_pct is not None else None

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
            "fy25_total_reach": round(total_reach, 2),
            "fy25_reach_share_pct": 0.0,
            "new_tv_share": round(tv_split, 4),
            "new_digital_share": round(dg_split, 4),
            "fy25_tv_share": round(tv_split, 4),
            "fy25_digital_share": round(dg_split, 4),
            "target_reach_share_pct": None if target_reach_share_pct is None else round(target_reach_share_pct, 2),
            "target_reach_share_min_pct": None if target_reach_share_min_pct is None else round(target_reach_share_min_pct, 2),
            "target_reach_share_max_pct": None if target_reach_share_max_pct is None else round(target_reach_share_max_pct, 2),
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
        total_baseline_reach += total_reach

    if total_spend > 0:
        for r in rows:
            r["new_budget_share"] = round(r["new_total_spend"] / total_spend, 4)
    if total_baseline_reach > 1e-12:
        for r in rows:
            reach_val = float(_finite(r.get("fy25_total_reach", 0.0), 0.0))
            r["fy25_reach_share_pct"] = round((reach_val / total_baseline_reach) * 100.0, 2)

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
            "requested_target_budget": round(target_budget, 2),
            "adjusted_target_budget": round(adjusted_target_budget, 2),
            "target_within_feasible": bool(target_within_feasible),
            "feasible_min_budget": round(feasible_min_budget, 2),
            "feasible_max_budget": round(feasible_max_budget, 2),
            "budget_constraint_value": round(float(target_budget - total_spend), 6),
            "total_new_spend": round(total_spend, 2),
            "total_volume_uplift": 0.0,
            "total_volume_uplift_pct": 0.0,
            "solver_success": None,
            "solver_message": "Preview mode",
        },
        "allocation_rows": rows,
        "market_elasticity_guidance": market_elasticity_guidance,
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


def _format_month_label(date_value: pd.Timestamp) -> str:
    if pd.isna(date_value):
        return ""
    return date_value.strftime("%b %Y")


def _find_existing_column(columns: list[str], candidates: list[str]) -> str:
    if not columns:
        return ""
    lower_map = {str(col).strip().lower(): str(col) for col in columns}
    for candidate in candidates:
        key = str(candidate).strip().lower()
        if key in lower_map:
            return lower_map[key]
    return ""


def _resolve_driver_source_column(driver_variable: str, columns: list[str]) -> str:
    raw = str(driver_variable or "").strip()
    if not raw:
        return ""
    candidates: list[str] = [raw]
    if raw.startswith("scaled_"):
        candidates.append(raw[len("scaled_") :])
    for suffix in ("_Adstock", "_Ad_Std", "_transformed", "_Transformed_Base"):
        if raw.endswith(suffix):
            candidates.append(raw[: -len(suffix)])
    col = _find_existing_column(columns, candidates)
    if col:
        return col
    lower_map = {str(col).strip().lower(): str(col) for col in columns}
    raw_key = raw.lower()
    for key, original in lower_map.items():
        if key == raw_key or key.endswith(f"_{raw_key}") or raw_key.endswith(f"_{key}"):
            return original
    return ""


def _aggregate_driver_feature_value(frame: pd.DataFrame, column: str) -> float | None:
    if frame.empty or column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    if values.empty:
        return None
    col_key = str(column).strip().lower()
    mean_tokens = ("price", "asp", "cpr", "ratio", "share", "pct", "percent", "rate", "index")
    if any(token in col_key for token in mean_tokens):
        return float(values.mean())
    return float(values.sum())


def _feature_value_meta(column_name: str) -> tuple[str, float]:
    col_key = str(column_name or "").strip().lower()
    if any(token in col_key for token in ("tv_spend", "digital_spend", "spends", "sales", "revenue", "gsv")):
        return "INR Mn", 1_000_000.0
    if any(token in col_key for token in ("volume", "reach", "qty")):
        return "Mn", 1_000_000.0
    if any(token in col_key for token in ("pct", "percent", "share", "rate")):
        return "%", 1.0
    if any(token in col_key for token in ("price", "asp")):
        return "INR", 1.0
    return "Index", 1.0


def _classify_driver(driver_variable: str, label: str) -> tuple[str, str]:
    key = f"{driver_variable} {label}".lower()
    if str(driver_variable).strip().lower() == "base":
        return "Baseline", "baseline"
    if any(token in key for token in ("tv", "digital", "media", "reach", "spend", "price", "distribution", "promo", "discount")):
        if "competition" in key or "competitor" in key:
            return "Competition", "external"
        if "price" in key:
            return "Price", "controllable"
        if "tv" in key:
            return "TV Media", "controllable"
        if "digital" in key:
            return "Digital Media", "controllable"
        return "Commercial Lever", "controllable"
    if any(token in key for token in ("competition", "competitor", "season", "macro", "festival", "weather", "inflation")):
        return "External", "external"
    return "External", "external"


def _pick_driver_impact(driver_rows: list[dict[str, Any]], keywords: list[str]) -> float:
    keys = [str(k).strip().lower() for k in keywords if str(k).strip()]
    if not keys:
        return 0.0
    for row in driver_rows:
        txt = f"{row.get('variable', '')} {row.get('label', '')}".lower()
        if any(k in txt for k in keys):
            return float(_finite(row.get("delta_contribution_mn", 0.0), 0.0))
    return 0.0


def _build_driver_analysis(payload: DriverAnalysisRequest) -> dict[str, Any]:
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

    months_back = max(1, min(int(payload.months_back), 36))
    top_n = max(3, min(int(payload.top_n), 20))

    model_df = _read_model_data(model_path)
    model_df.columns = [str(c).strip() for c in model_df.columns]
    weights_df = _read_market_weights(weights_path)
    weights_df.columns = [str(c).strip() for c in weights_df.columns]
    bw = weights_df[weights_df["Brand"].astype(str).str.strip() == brand].copy()
    if bw.empty:
        raise HTTPException(status_code=400, detail="No rows found for selected brand in model results.")

    transformed = apply_transformations_with_contributions(model_df, bw)
    if transformed.empty:
        raise HTTPException(status_code=400, detail="Driver analysis transformation returned no rows.")
    transformed.columns = [str(c).strip() for c in transformed.columns]
    if "Date" not in transformed.columns:
        raise HTTPException(status_code=400, detail="Transformed data does not contain Date for month-level analysis.")

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
        raise HTTPException(status_code=400, detail="Could not identify target volume column for driver analysis.")

    contribution_cols = [c for c in tdf.columns if str(c).endswith("_contribution")]
    numeric_cols = [y_col, "beta0", *contribution_cols]
    for col in numeric_cols:
        if col not in tdf.columns:
            tdf[col] = 0.0
        tdf[col] = pd.to_numeric(tdf[col], errors="coerce").fillna(0.0)

    tdf["_date"] = pd.to_datetime(tdf["Date"], errors="coerce")
    tdf = tdf.dropna(subset=["_date"]).copy()
    if tdf.empty:
        raise HTTPException(status_code=400, detail="No valid Date rows available for driver analysis.")

    grouped = (
        tdf.groupby("_date", as_index=False)[numeric_cols]
        .sum(numeric_only=True)
        .sort_values("_date")
        .reset_index(drop=True)
    )
    if grouped.empty:
        raise HTTPException(status_code=400, detail="Unable to build monthly grouped data for driver analysis.")

    if len(grouped) < 2:
        raise HTTPException(status_code=400, detail="At least two months are required for driver analysis.")

    now_idx = len(grouped) - 1
    then_idx = max(0, now_idx - months_back)
    if then_idx == now_idx and now_idx > 0:
        then_idx = now_idx - 1

    then_row = grouped.iloc[then_idx]
    now_row = grouped.iloc[now_idx]

    volume_then = float(_finite(then_row.get(y_col, 0.0), 0.0))
    volume_now = float(_finite(now_row.get(y_col, 0.0), 0.0))
    volume_delta = volume_now - volume_then
    volume_delta_pct = (volume_delta / volume_then * 100.0) if abs(volume_then) > 1e-12 else 0.0

    predicted_then = float(_finite(then_row.get("beta0", 0.0), 0.0)) + float(
        sum(float(_finite(then_row.get(col, 0.0), 0.0)) for col in contribution_cols)
    )
    predicted_now = float(_finite(now_row.get("beta0", 0.0), 0.0)) + float(
        sum(float(_finite(now_row.get(col, 0.0), 0.0)) for col in contribution_cols)
    )
    predicted_delta = predicted_now - predicted_then
    predicted_delta_pct = (predicted_delta / predicted_then * 100.0) if abs(predicted_then) > 1e-12 else 0.0

    then_date_ts = pd.to_datetime(then_row["_date"], errors="coerce")
    now_date_ts = pd.to_datetime(now_row["_date"], errors="coerce")

    then_slice = tdf[tdf["_date"] == then_date_ts].copy()
    now_slice = tdf[tdf["_date"] == now_date_ts].copy()

    driver_items: list[dict[str, Any]] = []
    base_then = float(_finite(then_row.get("beta0", 0.0), 0.0))
    base_now = float(_finite(now_row.get("beta0", 0.0), 0.0))
    base_delta = base_now - base_then
    if abs(base_then) > 1e-12 or abs(base_now) > 1e-12 or abs(base_delta) > 1e-12:
        group, cls = _classify_driver("base", "Base")
        driver_items.append(
            {
                "variable": "base",
                "label": "Base",
                "then_contribution": round(base_then, 6),
                "now_contribution": round(base_now, 6),
                "delta_contribution": round(base_delta, 6),
                "source_column": "",
                "value_then": None,
                "value_now": None,
                "value_delta": None,
                "value_change_pct": None,
                "value_display_unit": "Index",
                "value_scale_divisor": 1.0,
                "driver_group": group,
                "driver_class": cls,
            }
        )

    for col in contribution_cols:
        then_val = float(_finite(then_row.get(col, 0.0), 0.0))
        now_val = float(_finite(now_row.get(col, 0.0), 0.0))
        delta_val = now_val - then_val
        if abs(then_val) <= 1e-12 and abs(now_val) <= 1e-12 and abs(delta_val) <= 1e-12:
            continue
        variable_name = str(col).replace("_contribution", "")
        source_col = _resolve_driver_source_column(variable_name, tdf.columns.tolist())
        value_then = _aggregate_driver_feature_value(then_slice, source_col) if source_col else None
        value_now = _aggregate_driver_feature_value(now_slice, source_col) if source_col else None
        value_delta = (
            float(value_now) - float(value_then)
            if value_then is not None and value_now is not None
            else None
        )
        value_change_pct = (
            (float(value_delta) / float(value_then) * 100.0)
            if value_delta is not None and value_then is not None and abs(float(value_then)) > 1e-12
            else None
        )
        display_unit, scale_divisor = _feature_value_meta(source_col or variable_name)
        group, cls = _classify_driver(variable_name, _friendly_contribution_name(str(col)))
        driver_items.append(
            {
                "variable": variable_name,
                "label": _friendly_contribution_name(str(col)),
                "then_contribution": round(then_val, 6),
                "now_contribution": round(now_val, 6),
                "delta_contribution": round(delta_val, 6),
                "source_column": source_col,
                "value_then": value_then,
                "value_now": value_now,
                "value_delta": value_delta,
                "value_change_pct": value_change_pct,
                "value_display_unit": display_unit,
                "value_scale_divisor": scale_divisor,
                "driver_group": group,
                "driver_class": cls,
            }
        )

    driver_items = sorted(driver_items, key=lambda row: abs(float(row.get("delta_contribution", 0.0))), reverse=True)
    top_items = driver_items[:top_n]
    residual_items = driver_items[top_n:]
    if residual_items:
        other_then = float(sum(float(_finite(item.get("then_contribution", 0.0), 0.0)) for item in residual_items))
        other_now = float(sum(float(_finite(item.get("now_contribution", 0.0), 0.0)) for item in residual_items))
        other_delta = float(sum(float(_finite(item.get("delta_contribution", 0.0), 0.0)) for item in residual_items))
        top_items.append(
            {
                "variable": "other_drivers",
                "label": "Other Drivers",
                "then_contribution": round(other_then, 6),
                "now_contribution": round(other_now, 6),
                "delta_contribution": round(other_delta, 6),
                "source_column": "",
                "value_then": None,
                "value_now": None,
                "value_delta": None,
                "value_change_pct": None,
                "value_display_unit": "Index",
                "value_scale_divisor": 1.0,
                "driver_group": "External",
                "driver_class": "external",
            }
        )

    denominator = predicted_delta if abs(predicted_delta) > 1e-12 else volume_delta
    for item in top_items:
        delta_val = float(_finite(item.get("delta_contribution", 0.0), 0.0))
        item["share_of_change_pct"] = round((delta_val / denominator * 100.0) if abs(denominator) > 1e-12 else 0.0, 2)
        item["delta_contribution_mn"] = round(delta_val / 1_000_000.0, 4)
        item["then_contribution_mn"] = round(float(_finite(item.get("then_contribution", 0.0), 0.0)) / 1_000_000.0, 4)
        item["now_contribution_mn"] = round(float(_finite(item.get("now_contribution", 0.0), 0.0)) / 1_000_000.0, 4)
        value_then = item.get("value_then")
        value_now = item.get("value_now")
        value_delta = item.get("value_delta")
        scale_divisor = float(_finite(item.get("value_scale_divisor", 1.0), 1.0))
        if abs(scale_divisor) <= 1e-12:
            scale_divisor = 1.0
        item["value_then_display"] = (
            round(float(_finite(value_then, 0.0)) / scale_divisor, 4)
            if value_then is not None
            else None
        )
        item["value_now_display"] = (
            round(float(_finite(value_now, 0.0)) / scale_divisor, 4)
            if value_now is not None
            else None
        )
        item["value_delta_display"] = (
            round(float(_finite(value_delta, 0.0)) / scale_divisor, 4)
            if value_delta is not None
            else None
        )

    timeline_df = grouped.iloc[then_idx : now_idx + 1].copy()
    timeline: list[dict[str, Any]] = []
    for _, row in timeline_df.iterrows():
        point_date = pd.to_datetime(row["_date"], errors="coerce")
        point_actual = float(_finite(row.get(y_col, 0.0), 0.0))
        point_pred = float(_finite(row.get("beta0", 0.0), 0.0)) + float(
            sum(float(_finite(row.get(col, 0.0), 0.0)) for col in contribution_cols)
        )
        timeline.append(
            {
                "date": point_date.strftime("%Y-%m-%d") if not pd.isna(point_date) else "",
                "date_label": _format_month_label(point_date) if not pd.isna(point_date) else "",
                "volume_mn": round(point_actual / 1_000_000.0, 4),
                "predicted_volume_mn": round(point_pred / 1_000_000.0, 4),
            }
        )

    from_date = then_date_ts
    to_date = now_date_ts
    controllable_items = [row for row in top_items if str(row.get("driver_class", "")).lower() == "controllable"]
    external_items = [row for row in top_items if str(row.get("driver_class", "")).lower() == "external"]
    positive_items = [row for row in top_items if float(_finite(row.get("delta_contribution_mn", 0.0), 0.0)) > 0]
    negative_items = [row for row in top_items if float(_finite(row.get("delta_contribution_mn", 0.0), 0.0)) < 0]

    tv_spend_col = _find_existing_column(tdf.columns.tolist(), ["TV_Spends", "TV_Spend", "TV Spend"])
    digital_spend_col = _find_existing_column(tdf.columns.tolist(), ["Digital_Spends", "Digital_Spend", "Digital Spend"])
    price_col = _find_existing_column(tdf.columns.tolist(), ["Price", "Avg_Price", "ASP"])

    def _snapshot_entry(key: str, label: str, source_col: str, keywords: list[str]) -> dict[str, Any]:
        then_value = _aggregate_driver_feature_value(then_slice, source_col) if source_col else None
        now_value = _aggregate_driver_feature_value(now_slice, source_col) if source_col else None
        delta_value = (
            float(now_value) - float(then_value)
            if then_value is not None and now_value is not None
            else None
        )
        change_pct = (
            (float(delta_value) / float(then_value) * 100.0)
            if delta_value is not None and then_value is not None and abs(float(then_value)) > 1e-12
            else None
        )
        display_unit, divisor = _feature_value_meta(source_col or key)
        impact_mn = _pick_driver_impact(top_items, keywords)
        return {
            "key": key,
            "label": label,
            "source_column": source_col,
            "then_value": then_value,
            "now_value": now_value,
            "delta_value": delta_value,
            "change_pct": change_pct,
            "display_unit": display_unit,
            "display_divisor": divisor,
            "then_value_display": round(float(_finite(then_value, 0.0)) / divisor, 4) if then_value is not None else None,
            "now_value_display": round(float(_finite(now_value, 0.0)) / divisor, 4) if now_value is not None else None,
            "delta_value_display": round(float(_finite(delta_value, 0.0)) / divisor, 4) if delta_value is not None else None,
            "impact_on_volume_change_mn": round(impact_mn, 4),
        }

    controllable_snapshot = [
        _snapshot_entry("tv_spend", "TV Spend", tv_spend_col, ["tv_reach", "tv reach", "tv"]),
        _snapshot_entry("digital_spend", "Digital Spend", digital_spend_col, ["digital_reach", "digital reach", "digital"]),
        _snapshot_entry("price", "Price", price_col, ["price"]),
    ]

    return {
        "status": "ok",
        "message": "Driver analysis generated.",
        "selection": {
            "brand": brand,
            "market": selected_market,
            "months_back": months_back,
            "from_date": from_date.strftime("%Y-%m-%d") if not pd.isna(from_date) else "",
            "to_date": to_date.strftime("%Y-%m-%d") if not pd.isna(to_date) else "",
            "from_label": _format_month_label(from_date) if not pd.isna(from_date) else "",
            "to_label": _format_month_label(to_date) if not pd.isna(to_date) else "",
        },
        "summary": {
            "volume_then_mn": round(volume_then / 1_000_000.0, 4),
            "volume_now_mn": round(volume_now / 1_000_000.0, 4),
            "volume_change_mn": round(volume_delta / 1_000_000.0, 4),
            "volume_change_pct": round(volume_delta_pct, 4),
            "predicted_then_mn": round(predicted_then / 1_000_000.0, 4),
            "predicted_now_mn": round(predicted_now / 1_000_000.0, 4),
            "predicted_change_mn": round(predicted_delta / 1_000_000.0, 4),
            "predicted_change_pct": round(predicted_delta_pct, 4),
            "driver_count": len(top_items),
            "timeline_points": len(timeline),
            "controllable_driver_count": len(controllable_items),
            "external_driver_count": len(external_items),
            "top_positive_drivers": [str(item.get("label", "")) for item in positive_items[:3]],
            "top_negative_drivers": [str(item.get("label", "")) for item in negative_items[:3]],
            "controllable_snapshot": controllable_snapshot,
        },
        "drivers": top_items,
        "timeline": timeline,
    }


def _detect_volume_column(df: pd.DataFrame) -> str | None:
    for col in ("Volume", "Sales_Qty_Total", "Vol", "Filtered_Sales_Qty_Total", "Filtered_Secondary sales Qty(CS)", "Secondary sales Qty(CS)"):
        if col in df.columns:
            return col
    return None


def _detect_price_column(df: pd.DataFrame) -> str | None:
    for col in ("Price", "Avg_Price", "ASP"):
        if col in df.columns:
            return col
    return None


def _compute_revenue_series(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)
    vcol = _detect_volume_column(df)
    pcol = _detect_price_column(df)
    volume = pd.to_numeric(df[vcol], errors="coerce") if vcol else pd.Series(np.nan, index=df.index)
    if pcol:
        price = pd.to_numeric(df[pcol], errors="coerce")
    elif "Sales" in df.columns and vcol:
        num = pd.to_numeric(df["Sales"], errors="coerce")
        den = pd.to_numeric(df[vcol], errors="coerce")
        price = num / den.replace(0, np.nan)
    elif "GSV_Total" in df.columns and vcol:
        num = pd.to_numeric(df["GSV_Total"], errors="coerce")
        den = pd.to_numeric(df[vcol], errors="coerce")
        price = num / den.replace(0, np.nan)
    else:
        price = pd.Series(np.nan, index=df.index)

    revenue = volume * price
    if "Sales" in df.columns:
        sales = pd.to_numeric(df["Sales"], errors="coerce")
        revenue = revenue.where(np.isfinite(revenue), sales)
    if "GSV_Total" in df.columns:
        gsv = pd.to_numeric(df["GSV_Total"], errors="coerce")
        revenue = revenue.where(np.isfinite(revenue), gsv)
    revenue = revenue.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    revenue = revenue.clip(lower=0.0)
    return revenue


def _compute_market_salience_signals(
    model_df: pd.DataFrame,
    selected_brand: str,
    regions: list[str],
) -> dict[str, dict[str, Any]]:
    if model_df.empty or not regions:
        return {region: {} for region in regions}
    if "Brand" not in model_df.columns or "Region" not in model_df.columns:
        return {region: {} for region in regions}

    work = model_df.copy()
    work.columns = [str(c).strip() for c in work.columns]
    work["Brand"] = work["Brand"].astype(str).str.strip()
    work["Region"] = work["Region"].astype(str).str.strip()
    work = work[work["Region"].isin([str(r).strip() for r in regions])].copy()
    if work.empty:
        return {region: {} for region in regions}

    if "Fiscal Year" in work.columns and work["Fiscal Year"].notna().any():
        fy_values = sorted(work["Fiscal Year"].dropna().astype(str).unique().tolist(), key=_fiscal_key)
        if fy_values:
            work = work[work["Fiscal Year"].astype(str) == fy_values[-1]].copy()

    work["_revenue"] = _compute_revenue_series(work)
    grouped = work.groupby(["Region", "Brand"], as_index=False)["_revenue"].sum()
    if grouped.empty:
        return {region: {} for region in regions}

    selected_brand_revenue_by_region: dict[str, float] = {}
    region_total_revenue: dict[str, float] = {}
    leader_brand_by_region: dict[str, str] = {}
    leader_rank_by_region: dict[str, int] = {}
    market_share_by_region: dict[str, float] = {}

    for region in regions:
        reg = str(region).strip()
        rg = grouped[grouped["Region"] == reg].copy()
        rg = rg.sort_values(["_revenue", "Brand"], ascending=[False, True]).reset_index(drop=True)
        total_rev = float(_finite(rg["_revenue"].sum(), 0.0))
        region_total_revenue[reg] = max(0.0, total_rev)
        leader_brand_by_region[reg] = str(rg.iloc[0]["Brand"]) if len(rg) > 0 else ""

        brand_rev = float(_finite(rg.loc[rg["Brand"] == selected_brand, "_revenue"].sum(), 0.0))
        selected_brand_revenue_by_region[reg] = max(0.0, brand_rev)
        market_share_by_region[reg] = (brand_rev / total_rev * 100.0) if total_rev > 1e-12 else 0.0

        rank = len(rg) + 1
        if len(rg) > 0:
            match = rg[rg["Brand"] == selected_brand]
            if not match.empty:
                rank = int(match.index[0]) + 1
        leader_rank_by_region[reg] = rank

    total_selected_brand_revenue = float(sum(selected_brand_revenue_by_region.values()))
    out: dict[str, dict[str, Any]] = {}
    for region in regions:
        reg = str(region).strip()
        brand_rev = float(_finite(selected_brand_revenue_by_region.get(reg, 0.0), 0.0))
        salience = (brand_rev / total_selected_brand_revenue * 100.0) if total_selected_brand_revenue > 1e-12 else 0.0
        rank = int(_finite(leader_rank_by_region.get(reg, 0), 0))
        out[reg] = {
            "category_salience_pct": round(float(salience), 2),
            "brand_market_share_pct": round(float(_finite(market_share_by_region.get(reg, 0.0), 0.0)), 2),
            "leader_rank": rank,
            "leader_position": "Leader" if rank == 1 else f"Rank {rank}",
            "leader_brand": str(leader_brand_by_region.get(reg, "")),
            "is_market_leader": bool(rank == 1),
            "brand_revenue": round(brand_rev, 2),
            "region_total_revenue": round(float(_finite(region_total_revenue.get(reg, 0.0), 0.0)), 2),
        }
    return out


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
        "category_salience_pct": round(float(_finite(row.get("category_salience_pct", 0.0), 0.0)), 2),
        "brand_market_share_pct": round(float(_finite(row.get("brand_market_share_pct", 0.0), 0.0)), 2),
        "leader_position": str(row.get("leader_position", "")),
        "media_responsiveness_pct": round(float(_finite(row.get("media_responsiveness_pct", 0.0), 0.0)), 2),
        "investment_quadrant": str(row.get("investment_quadrant", "")),
        "action": str(row.get("recommendation_action", "Hold and optimize mix")),
    }


def _build_trinity_signal_snapshot(focus_prompt: str) -> dict[str, Any]:
    parsed_focus = _extract_json_object(focus_prompt or "")
    if not isinstance(parsed_focus, dict):
        return {
            "insights_brand": "",
            "insights_market": "",
            "yoy": {"latest_fiscal_year": "", "latest_yoy_growth_pct": 0.0, "latest_volume_mn": 0.0},
            "s_curve": {
                "tv_points": 0,
                "digital_points": 0,
                "tv_first_uplift_pct": 0.0,
                "tv_last_uplift_pct": 0.0,
                "dg_first_uplift_pct": 0.0,
                "dg_last_uplift_pct": 0.0,
            },
            "contribution_top": [],
        }

    s_curve_raw = parsed_focus.get("s_curve", {})
    yoy_raw = parsed_focus.get("yoy", {})
    contribution_raw = parsed_focus.get("contribution_top", [])
    s_curve = s_curve_raw if isinstance(s_curve_raw, dict) else {}
    yoy = yoy_raw if isinstance(yoy_raw, dict) else {}

    contribution_top: list[dict[str, Any]] = []
    if isinstance(contribution_raw, list):
        for item in contribution_raw[:6]:
            if not isinstance(item, dict):
                continue
            variable = _clip_text(str(item.get("variable", "")).strip(), 80)
            if not variable:
                continue
            contribution_top.append(
                {
                    "variable": variable,
                    "abs": float(_finite(item.get("abs", 0.0), 0.0)),
                    "share_pct": float(_finite(item.get("share_pct", 0.0), 0.0)),
                }
            )

    return {
        "insights_brand": _clip_text(str(parsed_focus.get("insights_brand", "")).strip(), 40),
        "insights_market": _clip_text(str(parsed_focus.get("insights_market", "")).strip(), 40),
        "yoy": {
            "latest_fiscal_year": _clip_text(str(yoy.get("latest_fiscal_year", "")).strip(), 20),
            "latest_yoy_growth_pct": float(_finite(yoy.get("latest_yoy_growth_pct", 0.0), 0.0)),
            "latest_volume_mn": float(_finite(yoy.get("latest_volume_mn", 0.0), 0.0)),
        },
        "s_curve": {
            "tv_points": int(_finite(s_curve.get("tv_points", 0), 0)),
            "digital_points": int(_finite(s_curve.get("digital_points", 0), 0)),
            "tv_first_uplift_pct": float(_finite(s_curve.get("tv_first_uplift_pct", 0.0), 0.0)),
            "tv_last_uplift_pct": float(_finite(s_curve.get("tv_last_uplift_pct", 0.0), 0.0)),
            "dg_first_uplift_pct": float(_finite(s_curve.get("dg_first_uplift_pct", 0.0), 0.0)),
            "dg_last_uplift_pct": float(_finite(s_curve.get("dg_last_uplift_pct", 0.0), 0.0)),
        },
        "contribution_top": contribution_top,
    }


def _build_trinity_portfolio_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "avg_yoy_growth_pct": 0.0,
            "median_yoy_growth_pct": 0.0,
            "positive_yoy_states": 0,
            "negative_yoy_states": 0,
            "median_headroom_pct": 0.0,
            "avg_tv_effectiveness_pct": 0.0,
            "avg_digital_effectiveness_pct": 0.0,
            "tv_effective_states": 0,
            "digital_effective_states": 0,
            "avg_category_salience_pct": 0.0,
            "market_leader_states": 0,
            "top_opportunity_states": [],
            "top_risk_states": [],
        }

    yoy_vals = np.array([float(_finite(r.get("yoy_growth_pct", 0.0), 0.0)) for r in rows], dtype=float)
    head_vals = np.array([float(_finite(r.get("headroom_pct", 0.0), 0.0)) for r in rows], dtype=float)
    tv_eff_vals = np.array([float(_finite(r.get("tv_effectiveness_pct", 0.0), 0.0)) for r in rows], dtype=float)
    dg_eff_vals = np.array([float(_finite(r.get("digital_effectiveness_pct", 0.0), 0.0)) for r in rows], dtype=float)
    salience_vals = np.array([float(_finite(r.get("category_salience_pct", 0.0), 0.0)) for r in rows], dtype=float)

    def _opp_score(r: dict[str, Any]) -> float:
        yoy = float(_finite(r.get("yoy_growth_pct", 0.0), 0.0))
        head = float(_finite(r.get("headroom_pct", 0.0), 0.0))
        tv_eff = float(_finite(r.get("tv_effectiveness_pct", 0.0), 0.0))
        dg_eff = float(_finite(r.get("digital_effectiveness_pct", 0.0), 0.0))
        return yoy * 0.45 + head * 0.35 + ((tv_eff + dg_eff) / 2.0) * 0.20

    def _risk_score(r: dict[str, Any]) -> float:
        yoy = float(_finite(r.get("yoy_growth_pct", 0.0), 0.0))
        head = float(_finite(r.get("headroom_pct", 0.0), 0.0))
        tv_eff = float(_finite(r.get("tv_effectiveness_pct", 0.0), 0.0))
        dg_eff = float(_finite(r.get("digital_effectiveness_pct", 0.0), 0.0))
        return (-yoy) * 0.50 + (100.0 - head) * 0.20 + (100.0 - ((tv_eff + dg_eff) / 2.0)) * 0.30

    top_opportunity_states = [
        str(r.get("market", ""))
        for r in sorted(rows, key=_opp_score, reverse=True)
        if str(r.get("market", ""))
    ][:6]
    top_risk_states = [
        str(r.get("market", ""))
        for r in sorted(rows, key=_risk_score, reverse=True)
        if str(r.get("market", ""))
    ][:6]

    return {
        "avg_yoy_growth_pct": round(float(np.mean(yoy_vals)) if yoy_vals.size else 0.0, 2),
        "median_yoy_growth_pct": round(float(np.median(yoy_vals)) if yoy_vals.size else 0.0, 2),
        "positive_yoy_states": int(np.sum(yoy_vals >= 0.0)),
        "negative_yoy_states": int(np.sum(yoy_vals < 0.0)),
        "median_headroom_pct": round(float(np.median(head_vals)) if head_vals.size else 0.0, 2),
        "avg_tv_effectiveness_pct": round(float(np.mean(tv_eff_vals)) if tv_eff_vals.size else 0.0, 2),
        "avg_digital_effectiveness_pct": round(float(np.mean(dg_eff_vals)) if dg_eff_vals.size else 0.0, 2),
        "tv_effective_states": int(sum(1 for r in rows if str(r.get("tv_zone", "")) == "effective")),
        "digital_effective_states": int(sum(1 for r in rows if str(r.get("digital_zone", "")) == "effective")),
        "avg_category_salience_pct": round(float(np.mean(salience_vals)) if salience_vals.size else 0.0, 2),
        "market_leader_states": int(sum(1 for r in rows if bool(r.get("is_market_leader", False)))),
        "top_opportunity_states": top_opportunity_states,
        "top_risk_states": top_risk_states,
    }


def _build_ai_insights_prompt(
    brand: str,
    rows: list[dict[str, Any]],
    leaders: list[str],
    core: list[str],
    recovery: list[str],
    focus_prompt: str,
) -> str:
    compact_focus = _build_trinity_signal_snapshot(focus_prompt)
    if not compact_focus.get("insights_brand") and not compact_focus.get("insights_market"):
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
        "- Use category_salience_pct, brand_market_share_pct, leader_position, and investment_quadrant while recommending increase/decrease.\n"
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
    leader_set = {x.lower() for x in leaders}

    def _opp_score(r: dict[str, Any]) -> float:
        yoy = float(_finite(r.get("yoy_growth_pct", 0.0), 0.0))
        head = float(_finite(r.get("headroom_pct", 0.0), 0.0))
        tv_eff = float(_finite(r.get("tv_effectiveness_pct", 0.0), 0.0))
        dg_eff = float(_finite(r.get("digital_effectiveness_pct", 0.0), 0.0))
        tv_zone = str(r.get("tv_zone", "")).lower()
        dg_zone = str(r.get("digital_zone", "")).lower()
        zone_bonus = 0.0
        if tv_zone == "under-utilized":
            zone_bonus += 4.0
        if dg_zone == "under-utilized":
            zone_bonus += 4.0
        if str(r.get("market", "")).lower() in leader_set:
            zone_bonus += 3.0
        return yoy * 0.45 + head * 0.35 + ((tv_eff + dg_eff) / 2.0) * 0.20 + zone_bonus

    def _risk_score(r: dict[str, Any]) -> float:
        yoy = float(_finite(r.get("yoy_growth_pct", 0.0), 0.0))
        head = float(_finite(r.get("headroom_pct", 0.0), 0.0))
        tv_eff = float(_finite(r.get("tv_effectiveness_pct", 0.0), 0.0))
        dg_eff = float(_finite(r.get("digital_effectiveness_pct", 0.0), 0.0))
        tv_zone = str(r.get("tv_zone", "")).lower()
        dg_zone = str(r.get("digital_zone", "")).lower()
        sat_penalty = 0.0
        if tv_zone == "saturated":
            sat_penalty += 7.0
        if dg_zone == "saturated":
            sat_penalty += 7.0
        return (-yoy) * 0.50 + (100.0 - head) * 0.20 + (100.0 - ((tv_eff + dg_eff) / 2.0)) * 0.30 + sat_penalty

    def _inc_action(r: dict[str, Any]) -> str:
        tv_zone = str(r.get("tv_zone", "")).lower()
        dg_zone = str(r.get("digital_zone", "")).lower()
        if tv_zone == "under-utilized" and dg_zone != "under-utilized":
            return "Increase TV in a controlled range while holding Digital."
        if dg_zone == "under-utilized" and tv_zone != "under-utilized":
            return "Increase Digital in a controlled range while holding TV."
        if tv_zone == "under-utilized" and dg_zone == "under-utilized":
            return "Increase both TV and Digital gradually; keep guardrails on spend."
        return "Increase spend selectively with balanced TV-Digital mix optimization."

    def _red_action(r: dict[str, Any]) -> str:
        tv_zone = str(r.get("tv_zone", "")).lower()
        dg_zone = str(r.get("digital_zone", "")).lower()
        if tv_zone == "saturated" and dg_zone != "saturated":
            return "Protect TV spend and rebalance toward higher-efficiency Digital."
        if dg_zone == "saturated" and tv_zone != "saturated":
            return "Protect Digital spend and rebalance toward higher-efficiency TV."
        if tv_zone == "saturated" and dg_zone == "saturated":
            return "Protect total spend and correct both channel mixes before scaling."
        return "Protect spend and optimize channel mix before incremental investment."

    if not isinstance(inc, list) or len(inc) == 0:
        inc_target = min(4, max(2, int(math.ceil(max(1, len(rows)) * 0.5))))
        inc_candidates = sorted(rows, key=_opp_score, reverse=True)
        chosen_inc: list[dict[str, Any]] = []
        for r in inc_candidates:
            yoy = float(_finite(r.get("yoy_growth_pct", 0.0), 0.0))
            head = float(_finite(r.get("headroom_pct", 0.0), 0.0))
            if yoy >= 0.0 or head >= 20.0:
                chosen_inc.append(r)
            if len(chosen_inc) >= inc_target:
                break
        if not chosen_inc:
            chosen_inc = inc_candidates[:inc_target]
        inc = [
            {
                "state": _clip_text(str(r.get("market", "N/A")), 40),
                "why": (
                    f"YoY {float(_finite(r.get('yoy_growth_pct', 0.0), 0.0)):.1f}%, "
                    f"headroom {float(_finite(r.get('headroom_pct', 0.0), 0.0)):.1f}%, "
                    f"TV {str(r.get('tv_zone', ''))}, Digital {str(r.get('digital_zone', ''))}."
                ),
                "action": _inc_action(r),
            }
            for r in chosen_inc
        ]

    if not isinstance(red, list) or len(red) == 0:
        inc_states = {str(x.get("state", "")).strip().lower() for x in inc if isinstance(x, dict)}
        red_target = min(4, max(1, len(rows) - len(inc_states)))
        red_candidates = [r for r in sorted(rows, key=_risk_score, reverse=True) if str(r.get("market", "")).strip().lower() not in inc_states]
        chosen_red: list[dict[str, Any]] = []
        for r in red_candidates:
            yoy = float(_finite(r.get("yoy_growth_pct", 0.0), 0.0))
            avg_eff = (
                float(_finite(r.get("tv_effectiveness_pct", 0.0), 0.0))
                + float(_finite(r.get("digital_effectiveness_pct", 0.0), 0.0))
            ) / 2.0
            tv_zone = str(r.get("tv_zone", "")).lower()
            dg_zone = str(r.get("digital_zone", "")).lower()
            if yoy < 0.0 or avg_eff < 45.0 or tv_zone == "saturated" or dg_zone == "saturated":
                chosen_red.append(r)
            if len(chosen_red) >= red_target:
                break
        if not chosen_red:
            chosen_red = red_candidates[:red_target]
        if not chosen_red and rows:
            chosen_red = sorted(rows, key=_risk_score, reverse=True)[:red_target]
        red = [
            {
                "state": _clip_text(str(r.get("market", "N/A")), 40),
                "why": (
                    f"YoY {float(_finite(r.get('yoy_growth_pct', 0.0), 0.0)):.1f}%, "
                    f"headroom {float(_finite(r.get('headroom_pct', 0.0), 0.0)):.1f}%, "
                    f"TV {str(r.get('tv_zone', ''))}, Digital {str(r.get('digital_zone', ''))}."
                ),
                "action": _red_action(r),
            }
            for r in chosen_red
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
    signal_snapshot = _build_trinity_signal_snapshot(str(payload.focus_prompt or "").strip())
    salience_signals = _compute_market_salience_signals(model_df=model_df, selected_brand=brand, regions=ctx["regions"])

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

    salience_vals = np.array(
        [float(_finite(salience_signals.get(str(r.get("market")), {}).get("category_salience_pct", 0.0), 0.0)) for r in rows],
        dtype=float,
    )
    responsiveness_vals = np.array(
        [float((_finite(r.get("tv_effectiveness_pct", 0.0), 0.0) + _finite(r.get("digital_effectiveness_pct", 0.0), 0.0)) / 2.0) for r in rows],
        dtype=float,
    )
    salience_mid = float(np.percentile(salience_vals, 50)) if salience_vals.size > 0 else 0.0
    responsiveness_mid = float(np.percentile(responsiveness_vals, 50)) if responsiveness_vals.size > 0 else 0.0

    framework_counts = {
        "increase_media_investments": 0,
        "maintain_high_salience": 0,
        "maintain_selective": 0,
        "scale_back": 0,
    }
    for row in rows:
        market = str(row.get("market", ""))
        sig = salience_signals.get(market, {})
        category_salience_pct = float(_finite(sig.get("category_salience_pct", 0.0), 0.0))
        brand_market_share_pct = float(_finite(sig.get("brand_market_share_pct", 0.0), 0.0))
        leader_rank = int(_finite(sig.get("leader_rank", 0), 0))
        is_market_leader = bool(sig.get("is_market_leader", False))
        leader_position = str(sig.get("leader_position", f"Rank {leader_rank}" if leader_rank > 0 else "Unranked"))
        leader_brand = str(sig.get("leader_brand", ""))
        brand_revenue = float(_finite(sig.get("brand_revenue", 0.0), 0.0))
        region_total_revenue = float(_finite(sig.get("region_total_revenue", 0.0), 0.0))

        media_responsiveness_pct = float(
            (_finite(row.get("tv_effectiveness_pct", 0.0), 0.0) + _finite(row.get("digital_effectiveness_pct", 0.0), 0.0))
            / 2.0
        )
        high_salience = category_salience_pct >= salience_mid
        high_responsiveness = media_responsiveness_pct >= responsiveness_mid

        if high_salience and high_responsiveness:
            investment_quadrant = "increase_media_investments"
            row_action = (
                "Increase media investments to maximum-impact range and build category growth."
                if not is_market_leader
                else "Increase media investments to defend leadership and expand category."
            )
        elif high_salience and (not high_responsiveness):
            investment_quadrant = "maintain_high_salience"
            row_action = "Maintain spend in this high-salience market; improve conversion quality before scaling."
        elif (not high_salience) and high_responsiveness:
            investment_quadrant = "maintain_selective"
            row_action = "Maintain selective investments; prioritize efficient bursts over broad scaling."
        else:
            investment_quadrant = "scale_back"
            row_action = "Scale back to minimum effective level and re-allocate funds to stronger markets."

        framework_counts[investment_quadrant] += 1

        row["category_salience_pct"] = round(category_salience_pct, 2)
        row["brand_market_share_pct"] = round(brand_market_share_pct, 2)
        row["leader_rank"] = leader_rank
        row["leader_position"] = leader_position
        row["leader_brand"] = leader_brand
        row["is_market_leader"] = is_market_leader
        row["brand_revenue"] = round(brand_revenue, 2)
        row["region_total_revenue"] = round(region_total_revenue, 2)
        row["media_responsiveness_pct"] = round(media_responsiveness_pct, 2)
        row["investment_quadrant"] = investment_quadrant
        row["recommendation_action"] = row_action

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
    portfolio_metrics = _build_trinity_portfolio_metrics(rows)
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

    if ai_structured is not None:
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
        "signal_snapshot": signal_snapshot,
        "portfolio_metrics": portfolio_metrics,
        "investment_framework": {
            "salience_threshold_pct": round(float(salience_mid), 2),
            "responsiveness_threshold_pct": round(float(responsiveness_mid), 2),
            "quadrant_counts": framework_counts,
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


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _combined_intent_text(prompt: str, answers: dict[str, str] | None = None) -> str:
    base = str(prompt or "").strip()
    if not isinstance(answers, dict) or not answers:
        return base
    answer_text = " ".join(str(v or "").strip() for v in answers.values() if str(v or "").strip())
    return f"{base}\n{answer_text}".strip()


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    lower = str(text or "").lower()
    return any(p in lower for p in patterns)


def _metric_label(metric_key: str) -> str:
    labels = {
        "category_salience": "Category Salience",
        "brand_salience": "Brand Salience",
        "market_share": "Market Share",
        "change_in_market_share": "Change In Market Share",
        "change_in_brand_equity": "Change In Brand Equity",
    }
    raw = str(metric_key or "").strip()
    return labels.get(raw, raw.replace("_", " ").title())


def _condition_phrase_catalog() -> list[dict[str, Any]]:
    return [
        {
            "metric_key": "market_share",
            "metric_label": "Market Share",
            "qualifier_type": "band",
            "requested_direction": "low",
            "patterns": (
                "smaller markets",
                "small markets",
                "smaller states",
                "small states",
                "lower share markets",
                "low share markets",
                "markets with low share",
                "markets with lower share",
                "minor markets",
                "smaller presence",
                "low presence",
                "weak presence",
            ),
        },
        {
            "metric_key": "market_share",
            "metric_label": "Market Share",
            "qualifier_type": "band",
            "requested_direction": "high",
            "patterns": (
                "bigger markets",
                "large markets",
                "larger markets",
                "bigger states",
                "larger states",
                "high share markets",
                "markets with high share",
                "major markets",
                "core markets",
                "bigger presence",
                "strong presence",
                "high presence",
            ),
        },
        {
            "metric_key": "market_share",
            "metric_label": "Market Share",
            "qualifier_type": "band",
            "requested_direction": "low",
            "patterns": (
                "low market share",
                "lower market share",
                "weak market share",
                "small market share",
            ),
        },
        {
            "metric_key": "market_share",
            "metric_label": "Market Share",
            "qualifier_type": "band",
            "requested_direction": "high",
            "patterns": (
                "high market share",
                "higher market share",
                "strong market share",
                "big market share",
            ),
        },
        {
            "metric_key": "change_in_market_share",
            "metric_label": "Change In Market Share",
            "qualifier_type": "trend",
            "requested_direction": "decreasing",
            "patterns": (
                "losing market share",
                "losing share",
                "share loss",
                "declining share",
                "where i am losing",
                "where we are losing",
                "share is declining",
                "market share is declining",
                "share erosion",
                "eroding share",
                "share has decreased",
                "share decreased",
                "share has declined",
                "share declined",
                "share has reduced",
                "share reduced",
                "market share has decreased",
                "market share decreased",
                "market share has declined",
                "market share declined",
                "market share has reduced",
                "market share reduced",
                "decreased share",
                "declined share",
                "reduced share",
            ),
        },
        {
            "metric_key": "change_in_market_share",
            "metric_label": "Change In Market Share",
            "qualifier_type": "trend",
            "requested_direction": "increasing",
            "patterns": (
                "gaining market share",
                "gaining share",
                "share gain",
                "growing share",
                "where i am gaining",
                "where we are gaining",
                "share is growing",
                "share is increasing",
                "market share is growing",
                "market share is increasing",
                "positive share",
                "share has increased",
                "share increased",
                "market share has increased",
                "market share increased",
            ),
        },
        {
            "metric_key": "category_salience",
            "metric_label": "Category Salience",
            "qualifier_type": "band",
            "requested_direction": "low",
            "patterns": (
                "low category salience",
                "weak category salience",
                "category salience is low",
                "category salience is weak",
            ),
        },
        {
            "metric_key": "category_salience",
            "metric_label": "Category Salience",
            "qualifier_type": "band",
            "requested_direction": "high",
            "patterns": (
                "high category salience",
                "strong category salience",
                "category salience is high",
                "category salience is strong",
            ),
        },
        {
            "metric_key": "brand_salience",
            "metric_label": "Brand Salience",
            "qualifier_type": "band",
            "requested_direction": "low",
            "patterns": (
                "low brand salience",
                "weak brand salience",
                "brand salience is low",
                "brand salience is weak",
            ),
        },
        {
            "metric_key": "brand_salience",
            "metric_label": "Brand Salience",
            "qualifier_type": "band",
            "requested_direction": "high",
            "patterns": (
                "high brand salience",
                "strong brand salience",
                "brand salience is high",
                "brand salience is strong",
            ),
        },
        {
            "metric_key": "change_in_brand_equity",
            "metric_label": "Change In Brand Equity",
            "qualifier_type": "trend",
            "requested_direction": "decreasing",
            "patterns": (
                "declining brand equity",
                "brand equity is declining",
                "brand equity has declined",
                "brand equity declined",
                "brand equity has decreased",
                "brand equity decreased",
                "losing brand equity",
                "weakening brand equity",
                "negative equity momentum",
                "equity is falling",
            ),
        },
        {
            "metric_key": "change_in_brand_equity",
            "metric_label": "Change In Brand Equity",
            "qualifier_type": "trend",
            "requested_direction": "increasing",
            "patterns": (
                "increasing brand equity",
                "brand equity is increasing",
                "brand equity has increased",
                "brand equity increased",
                "brand equity is growing",
                "growing brand equity",
                "gaining brand equity",
                "positive equity momentum",
                "equity is improving",
            ),
        },
    ]


def _match_markets_for_metric_condition(
    metric_key: str,
    requested_direction: str,
    selected_markets: list[str],
    market_rows: list[dict[str, Any]],
) -> list[str]:
    market_row_map = {str(row.get("market", "")).strip(): row for row in market_rows if str(row.get("market", "")).strip()}
    matched: list[str] = []
    for market in selected_markets:
        row = market_row_map.get(market)
        if not row:
            continue
        if metric_key in {"category_salience", "brand_salience", "market_share"}:
            band_value = str(row.get(f"{metric_key}_band", "unknown")).strip().lower()
            if requested_direction == "high" and band_value == "high":
                matched.append(market)
            elif requested_direction == "low" and band_value == "low":
                matched.append(market)
            continue
        if metric_key in {"change_in_market_share", "change_in_brand_equity"}:
            band_value = str(row.get(f"{metric_key}_band", "neutral")).strip().lower()
            if requested_direction == "increasing" and band_value in {"mild_positive", "strong_positive"}:
                matched.append(market)
            elif requested_direction == "decreasing" and band_value in {"mild_negative", "strong_negative"}:
                matched.append(market)
    return matched


def _extract_interpreted_conditions(
    text: str,
    selected_markets: list[str],
    market_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    lower = str(text or "").lower()
    conditions: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    structured_condition_detected = False

    def _append_condition(
        metric_key: str,
        metric_label: str,
        qualifier_type: Literal["band", "trend"],
        requested_direction: Literal["high", "low", "increasing", "decreasing"],
        source_text: str,
    ) -> None:
        nonlocal structured_condition_detected
        key = (metric_key, requested_direction)
        if key in seen:
            return
        seen.add(key)
        structured_condition_detected = True
        conditions.append(
            {
                "metric_key": metric_key,
                "metric_label": metric_label,
                "qualifier_type": qualifier_type,
                "requested_direction": requested_direction,
                "source_text": source_text,
                "matched_markets": _match_markets_for_metric_condition(
                    metric_key,
                    requested_direction,
                    selected_markets,
                    market_rows,
                ),
            }
        )

    for item in _condition_phrase_catalog():
        matched_source = next((pattern for pattern in item["patterns"] if pattern in lower), "")
        if matched_source:
            _append_condition(
                metric_key=item["metric_key"],
                metric_label=item["metric_label"],
                qualifier_type=item["qualifier_type"],
                requested_direction=item["requested_direction"],
                source_text=matched_source,
            )

    if "low salience" in lower or "weak salience" in lower or "underdeveloped markets" in lower:
        _append_condition("category_salience", "Category Salience", "band", "low", "low salience")
        _append_condition("brand_salience", "Brand Salience", "band", "low", "low salience")
    if "high salience" in lower or "strong salience" in lower or "developed markets" in lower:
        _append_condition("category_salience", "Category Salience", "band", "high", "high salience")
        _append_condition("brand_salience", "Brand Salience", "band", "high", "high salience")

    return conditions, structured_condition_detected


def _intersect_condition_matches(conditions: list[dict[str, Any]], selected_markets: list[str]) -> list[str]:
    if not conditions:
        return []
    matched_sets: list[set[str]] = []
    for item in conditions:
        markets = [str(m).strip() for m in item.get("matched_markets", []) if str(m).strip()]
        if not markets:
            return []
        matched_sets.append(set(markets))
    return [market for market in selected_markets if all(market in market_set for market_set in matched_sets)]


def _resolve_clause_action(clause: str) -> ScenarioMarketAction | None:
    action_lookup: list[tuple[ScenarioMarketAction, tuple[str, ...]]] = [
        ("protect", ("protect", "defend", "preserve", "hold on to", "do not lose")),
        ("deprioritize", ("deprioritize", "pull back", "pull out", "minimize", "avoid", "ignore")),
        ("decrease", ("reduce", "cut", "decrease", "downweight", "scale down")),
        ("recover", ("recover", "repair", "turn around", "improve")),
        ("rebalance", ("rebalance", "re-balance", "shift", "redistribute", "practical mix")),
        ("increase", ("increase", "push", "grow", "scale", "prioritize", "focus")),
        ("hold", ("hold", "maintain", "keep steady")),
    ]
    for action_name, patterns in action_lookup:
        if _contains_any(clause, patterns):
            return action_name
    return None


def _build_interpretation_summary(
    interpreted_conditions: list[dict[str, Any]],
    explicit_market_actions: dict[str, ScenarioMarketAction],
    global_action_preference: ScenarioMarketAction,
) -> str:
    if interpreted_conditions:
        phrases = []
        for item in interpreted_conditions:
            direction = str(item.get("requested_direction", "")).strip().lower()
            if direction == "high":
                qualifier = "high"
            elif direction == "low":
                qualifier = "low"
            elif direction == "increasing":
                qualifier = "increasing"
            else:
                qualifier = "decreasing"
            phrases.append(f"{item.get('metric_label', _metric_label(item.get('metric_key', '')))} is {qualifier}")
        condition_text = " and ".join(phrases[:3])
        if explicit_market_actions:
            unique_actions = _dedupe_strings([str(value) for value in explicit_market_actions.values()])
            action_text = unique_actions[0].replace("_", " ") if len(unique_actions) == 1 else "mixed actions"
            return f"I understood: {action_text} the markets where {condition_text}."
        return f"I understood these prompt conditions: {condition_text}."
    if explicit_market_actions:
        named_markets = _dedupe_strings(list(explicit_market_actions.keys()))
        return f"I understood explicit market instructions for {', '.join(named_markets[:4])}."
    return f"I understood a broad {str(global_action_preference).replace('_', ' ')} preference across the selected markets."


def _call_gemini_extract_market_conditions(
    prompt: str,
    selected_markets: list[str],
    market_rows: list[dict[str, Any]],
) -> tuple[dict[str, ScenarioMarketAction], list[str]]:
    """Use Gemini AI to extract which markets match the user's conditions."""
    notes: list[str] = []
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    
    if not api_key:
        notes.append("Gemini API key missing; using rule-based condition matching.")
        return {}, notes
    
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    
    # Build market data summary for AI
    market_summary = []
    for row in market_rows:
        market = str(row.get("market", "")).strip()
        if not market:
            continue
        market_summary.append({
            "market": market,
            "category_salience": row.get("category_salience"),
            "brand_salience": row.get("brand_salience"),
            "market_share": row.get("market_share"),
            "change_in_market_share": row.get("change_in_market_share"),
            "change_in_brand_equity": row.get("change_in_brand_equity"),
        })
    
    ai_prompt = f"""You are analyzing a marketing budget allocation intent.

USER INTENT: "{prompt}"

AVAILABLE MARKETS AND DATA:
{json.dumps(market_summary, indent=2)}

TASK: Identify which markets match the user's criteria and what action they want.

RULES:
- "smaller markets" / "low share" = markets with BELOW median market_share
- "bigger markets" / "high share" = markets with ABOVE median market_share  
- "losing share" / "declined" / "decreased" = markets with NEGATIVE change_in_market_share
- "gaining share" / "increased" / "grown" = markets with POSITIVE change_in_market_share
- "low salience" = markets with BELOW median category_salience or brand_salience
- "high salience" = markets with ABOVE median category_salience or brand_salience

ACTIONS:
- increase, decrease, protect, recover, hold, deprioritize, rebalance

Return ONLY a JSON object with this structure:
{{
  "matched_markets": {{"market_name": "action", ...}},
  "reasoning": "brief explanation of what you understood"
}}

If the user mentions ALL markets or no specific condition, return empty matched_markets.
"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": ai_prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 800},
    }
    
    for attempt in range(2):
        try:
            req = urlrequest.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urlrequest.urlopen(req, timeout=15) as response:
                parsed = json.loads(response.read().decode("utf-8"))
            
            candidates = parsed.get("candidates", [])
            if not candidates:
                notes.append("Gemini returned empty response; using rule-based matching.")
                return {}, notes
            
            parts = candidates[0].get("content", {}).get("parts", [])
            text = str(parts[0].get("text", "")).strip() if parts else ""
            
            if not text:
                notes.append("Gemini returned empty text; using rule-based matching.")
                return {}, notes
            
            # Extract JSON from response
            result = _extract_json_object(text)
            if result and isinstance(result.get("matched_markets"), dict):
                matched = result["matched_markets"]
                reasoning = result.get("reasoning", "")
                if reasoning:
                    notes.append(f"AI understood: {reasoning}")
                return matched, notes
            
            notes.append("Gemini returned invalid format; using rule-based matching.")
            return {}, notes
            
        except urlerror.HTTPError as exc:
            if attempt < 1:
                time.sleep(0.5)
                continue
            notes.append(f"Gemini API error ({exc.code}); using rule-based matching.")
            return {}, notes
        except Exception:
            if attempt < 1:
                time.sleep(0.5)
            else:
                notes.append("Gemini request failed; using rule-based matching.")
    
    return {}, notes


def _call_gemini_intent_debug(
    prompt: str,
    selected_markets: list[str],
    market_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    notes: list[str] = []
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"

    market_summary = []
    for row in market_rows:
        market = str(row.get("market", "")).strip()
        if not market:
            continue
        market_summary.append(
            {
                "market": market,
                "category_salience": row.get("category_salience"),
                "brand_salience": row.get("brand_salience"),
                "market_share": row.get("market_share"),
                "change_in_market_share": row.get("change_in_market_share"),
                "change_in_brand_equity": row.get("change_in_brand_equity"),
            }
        )

    ai_prompt = f"""You are analyzing a marketing budget allocation intent.

USER INTENT: "{prompt}"

SELECTED MARKETS:
{json.dumps(selected_markets, indent=2)}

AVAILABLE MARKETS AND DATA:
{json.dumps(market_summary, indent=2)}

TASK:
Interpret the user prompt as clearly as possible.

Return ONLY a JSON object with this structure:
{{
  "goal": "one-line restatement of the business objective in your own words",
  "task_types": [],
  "metrics_referenced": [],
  "conditions": [],
  "entity": "market",
  "action_direction": "",
  "matched_markets": [],
  "assumptions": [],
  "reasoning": "2-3 sentences explaining in plain English what strategy you understood, why those markets were selected based on the data, and what trade-offs or signals drove the recommendation. Do NOT repeat the user prompt verbatim. Explain the logic as if briefing a marketing manager."
}}
"""

    result: dict[str, Any] = {
        "provider": "gemini",
        "model": model,
        "ai_prompt": ai_prompt,
        "raw_text": "",
        "parsed_json": None,
        "notes": notes,
    }

    if not api_key:
        notes.append("Gemini API key missing; debug call was not sent.")
        return result

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": ai_prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1200},
    }

    for attempt in range(2):
        try:
            req = urlrequest.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urlrequest.urlopen(req, timeout=20) as response:
                parsed = json.loads(response.read().decode("utf-8"))
            candidates = parsed.get("candidates", [])
            if not candidates:
                notes.append("Gemini returned empty response.")
                return result
            parts = candidates[0].get("content", {}).get("parts", [])
            text = str(parts[0].get("text", "")).strip() if parts else ""
            result["raw_text"] = text
            parsed_obj = _extract_json_object(text)
            if parsed_obj is not None:
                result["parsed_json"] = parsed_obj
            else:
                notes.append("Gemini returned text that could not be parsed as JSON.")
            return result
        except urlerror.HTTPError as exc:
            if attempt < 1:
                time.sleep(0.5)
                continue
            notes.append(f"Gemini API error ({exc.code}).")
            return result
        except Exception as exc:  # noqa: BLE001
            if attempt < 1:
                time.sleep(0.5)
                continue
            notes.append(f"Gemini request failed: {exc}")
            return result
    return result


def _filter_markets_by_condition(
    clause: str,
    selected_markets: list[str],
    market_rows: list[dict[str, Any]],
) -> list[str]:
    """Filter markets based on conditional phrases like 'where I am losing market share'."""
    clause_lower = clause.lower()
    market_row_map = {str(row.get("market", "")).strip(): row for row in market_rows if str(row.get("market", "")).strip()}
    
    # Detect conditional patterns
    losing_share_patterns = (
        "losing market share", "losing share", "share loss", "declining share",
        "where i am losing", "where we are losing", "share is declining",
        "market share is declining", "share erosion", "eroding share",
        "share has decreased", "share decreased", "share has declined", "share declined",
        "market share has decreased", "market share decreased", "market share has declined",
        "market share declined", "decreased share", "declined share"
    )
    gaining_share_patterns = (
        "gaining market share", "gaining share", "share gain", "growing share",
        "where i am gaining", "where we are gaining", "share is growing",
        "market share is growing", "share momentum", "positive share"
    )
    high_cpr_patterns = (
        "high cpr", "poor cpr", "weak cpr", "expensive cpr", "inefficient",
        "high cost per reach", "where cpr is high", "where cost is high"
    )
    low_elasticity_patterns = (
        "low elasticity", "weak elasticity", "poor responsiveness",
        "low responsiveness", "where elasticity is low", "unresponsive"
    )
    high_elasticity_patterns = (
        "high elasticity", "strong elasticity", "good responsiveness",
        "high responsiveness", "where elasticity is high", "responsive"
    )
    smaller_market_patterns = (
        "smaller markets", "small markets", "lower share markets", "low share markets",
        "markets with low share", "markets with lower share", "minor markets",
        "smaller presence", "low presence", "weak presence"
    )
    bigger_market_patterns = (
        "bigger markets", "large markets", "larger markets", "high share markets",
        "markets with high share", "major markets", "core markets",
        "bigger presence", "strong presence", "high presence"
    )
    low_salience_patterns = (
        "low salience", "weak salience", "low category salience", "low brand salience",
        "weak category", "weak brand", "underdeveloped markets"
    )
    high_salience_patterns = (
        "high salience", "strong salience", "high category salience", "high brand salience",
        "strong category", "strong brand", "developed markets"
    )
    
    filtered_markets: list[str] = []
    
    # Check for losing market share condition
    if _contains_any(clause_lower, losing_share_patterns):
        for market in selected_markets:
            row = market_row_map.get(market)
            if row:
                share_change_band = str(row.get("change_in_market_share_band", "neutral"))
                if share_change_band in {"mild_negative", "strong_negative"}:
                    filtered_markets.append(market)
        return filtered_markets
    
    # Check for gaining market share condition
    if _contains_any(clause_lower, gaining_share_patterns):
        for market in selected_markets:
            row = market_row_map.get(market)
            if row:
                share_change_band = str(row.get("change_in_market_share_band", "neutral"))
                if share_change_band in {"mild_positive", "strong_positive"}:
                    filtered_markets.append(market)
        return filtered_markets
    
    # Check for smaller markets condition (lower 50% by market share)
    if _contains_any(clause_lower, smaller_market_patterns):
        # Get all market shares and calculate median
        market_shares = []
        for market in selected_markets:
            row = market_row_map.get(market)
            if row:
                share = row.get("market_share")
                if share is not None and np.isfinite(share):
                    market_shares.append((market, float(share)))
        
        if market_shares:
            # Sort by market share
            market_shares.sort(key=lambda x: x[1])
            # Take lower 50% (smaller markets)
            median_idx = len(market_shares) // 2
            filtered_markets = [m for m, _ in market_shares[:median_idx]]
        return filtered_markets
    
    # Check for bigger markets condition (upper 50% by market share)
    if _contains_any(clause_lower, bigger_market_patterns):
        # Get all market shares and calculate median
        market_shares = []
        for market in selected_markets:
            row = market_row_map.get(market)
            if row:
                share = row.get("market_share")
                if share is not None and np.isfinite(share):
                    market_shares.append((market, float(share)))
        
        if market_shares:
            # Sort by market share
            market_shares.sort(key=lambda x: x[1])
            # Take upper 50% (bigger markets)
            median_idx = len(market_shares) // 2
            filtered_markets = [m for m, _ in market_shares[median_idx:]]
        return filtered_markets
    
    # Check for low salience condition (lower 50% by category or brand salience)
    if _contains_any(clause_lower, low_salience_patterns):
        # Calculate based on category salience or brand salience
        salience_values = []
        for market in selected_markets:
            row = market_row_map.get(market)
            if row:
                cat_sal = row.get("category_salience")
                brand_sal = row.get("brand_salience")
                # Use average of both if available
                if cat_sal is not None and brand_sal is not None:
                    avg_sal = (float(cat_sal) + float(brand_sal)) / 2
                    salience_values.append((market, avg_sal))
                elif cat_sal is not None:
                    salience_values.append((market, float(cat_sal)))
                elif brand_sal is not None:
                    salience_values.append((market, float(brand_sal)))
        
        if salience_values:
            salience_values.sort(key=lambda x: x[1])
            median_idx = len(salience_values) // 2
            filtered_markets = [m for m, _ in salience_values[:median_idx]]
        return filtered_markets
    
    # Check for high salience condition (upper 50% by category or brand salience)
    if _contains_any(clause_lower, high_salience_patterns):
        # Calculate based on category salience or brand salience
        salience_values = []
        for market in selected_markets:
            row = market_row_map.get(market)
            if row:
                cat_sal = row.get("category_salience")
                brand_sal = row.get("brand_salience")
                # Use average of both if available
                if cat_sal is not None and brand_sal is not None:
                    avg_sal = (float(cat_sal) + float(brand_sal)) / 2
                    salience_values.append((market, avg_sal))
                elif cat_sal is not None:
                    salience_values.append((market, float(cat_sal)))
                elif brand_sal is not None:
                    salience_values.append((market, float(brand_sal)))
        
        if salience_values:
            salience_values.sort(key=lambda x: x[1])
            median_idx = len(salience_values) // 2
            filtered_markets = [m for m, _ in salience_values[median_idx:]]
        return filtered_markets
    
    # Check for high CPR condition
    if _contains_any(clause_lower, high_cpr_patterns):
        for market in selected_markets:
            row = market_row_map.get(market)
            if row:
                cpr_band = str(row.get("avg_cpr_band", "unknown"))
                if cpr_band == "high_cost":
                    filtered_markets.append(market)
        return filtered_markets
    
    # Check for low elasticity condition
    if _contains_any(clause_lower, low_elasticity_patterns):
        for market in selected_markets:
            row = market_row_map.get(market)
            if row:
                responsiveness = str(row.get("responsiveness_label", "Unknown")).lower()
                if responsiveness in {"low", "weak", "poor"}:
                    filtered_markets.append(market)
        return filtered_markets
    
    # Check for high elasticity condition
    if _contains_any(clause_lower, high_elasticity_patterns):
        for market in selected_markets:
            row = market_row_map.get(market)
            if row:
                responsiveness = str(row.get("responsiveness_label", "Unknown")).lower()
                if responsiveness in {"high", "strong", "good"}:
                    filtered_markets.append(market)
        return filtered_markets
    
    return []


def _extract_prompt_market_actions(
    prompt: str,
    selected_markets: list[str],
    market_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    actions: dict[str, ScenarioMarketAction] = {}
    notes: list[str] = []
    clauses = [c.strip() for c in re.split(r"[.;\n]+", str(prompt or "")) if c.strip()]
    market_key_map = {_normalize_name_key(m): str(m).strip() for m in selected_markets if str(m).strip()}
    interpreted_conditions: list[dict[str, Any]] = []
    condition_seen: set[tuple[str, str]] = set()
    structured_condition_detected = False
    zero_match_condition_detected = False

    def _record_conditions(items: list[dict[str, Any]]) -> None:
        for item in items:
            key = (
                str(item.get("metric_key", "")).strip(),
                str(item.get("requested_direction", "")).strip(),
            )
            if not key[0] or key in condition_seen:
                continue
            condition_seen.add(key)
            interpreted_conditions.append(item)

    for clause in clauses:
        clause_key = _normalize_name_key(clause)
        clause_action = _resolve_clause_action(clause)
        clause_conditions, clause_has_structured_condition = _extract_interpreted_conditions(
            clause,
            selected_markets,
            market_rows or [],
        )
        if clause_has_structured_condition:
            structured_condition_detected = True
        _record_conditions(clause_conditions)

        matched_markets = [market_name for market_key, market_name in market_key_map.items() if market_key and market_key in clause_key]
        if not matched_markets and clause_conditions:
            matched_markets = _intersect_condition_matches(clause_conditions, selected_markets)
            if matched_markets:
                notes.append(
                    f"Structured prompt parsing matched {len(matched_markets)} markets for clause based on market-intelligence columns."
                )
            else:
                zero_match_condition_detected = True
                notes.append("A prompt condition was understood, but no selected markets matched it exactly.")

        if matched_markets and clause_action is not None:
            for market_name in matched_markets:
                actions[market_name] = clause_action

    if not actions and market_rows and str(prompt or "").strip() and not structured_condition_detected:
        ai_actions, ai_notes = _call_gemini_extract_market_conditions(prompt, selected_markets, market_rows)
        notes.extend(ai_notes)
        for market_name, action in ai_actions.items():
            canonical_market = market_key_map.get(_normalize_name_key(market_name), str(market_name).strip())
            if canonical_market in selected_markets and action in {
                "increase",
                "decrease",
                "protect",
                "hold",
                "deprioritize",
                "rebalance",
                "recover",
            }:
                actions[canonical_market] = action

    global_action = _resolve_global_action_preference(prompt, _resolve_objective_preference(prompt))
    interpretation_summary = _build_interpretation_summary(interpreted_conditions, actions, global_action)
    return {
        "actions": actions,
        "notes": notes,
        "interpreted_conditions": interpreted_conditions,
        "interpretation_summary": interpretation_summary,
        "structured_condition_detected": structured_condition_detected,
        "zero_match_condition_detected": zero_match_condition_detected,
    }


def _resolve_objective_preference(text: str) -> ScenarioObjectivePreference:
    lower = str(text or "").lower()
    if _contains_any(lower, ("efficiency", "efficient", "cpr", "practical roi", "cost-effective")):
        return "efficiency"
    if _contains_any(lower, ("revenue", "value growth", "premium", "profit")):
        return "revenue"
    if _contains_any(lower, ("volume", "penetration", "reach growth", "scale distribution")):
        return "volume"
    if _contains_any(lower, ("practical", "realistic", "pragmatic", "steady", "balanced but practical")):
        return "practical_mix"
    return "balanced"


def _resolve_anchor_metrics(text: str, objective: ScenarioObjectivePreference) -> tuple[list[str], list[str]]:
    lower = str(text or "").lower()
    metric_patterns = [
        ("category_salience", ("category salience", "salience", "opportunity")),
        ("brand_salience", ("brand salience", "brand presence", "brand pull", "activation")),
        (
            "change_in_market_share",
            (
                "change in market share",
                "share gain",
                "share growth",
                "share momentum",
                "gaining share",
                "losing market share",
                "lose market share",
                "losing share",
                "share loss",
                "market share loss",
                "declining share",
                "falling share",
                "share erosion",
                "eroding share",
            ),
        ),
        ("market_share", ("market share", "share", "franchise", "core market", "core markets")),
        ("change_in_brand_equity", ("change in brand equity", "brand equity", "equity momentum", "brand momentum")),
    ]
    matched = [metric_name for metric_name, patterns in metric_patterns if _contains_any(lower, patterns)]
    if len(matched) >= 2:
        return _dedupe_strings(matched[:2]), _dedupe_strings(matched[2:4])
    if len(matched) == 1:
        defaults = {
            "volume": ["category_salience", "change_in_market_share"],
            "revenue": ["market_share", "brand_salience"],
            "balanced": ["category_salience", "market_share"],
            "efficiency": ["brand_salience", "change_in_brand_equity"],
            "practical_mix": ["market_share", "category_salience"],
        }
        secondary = [m for m in defaults.get(objective, []) if m != matched[0]]
        return [matched[0]], secondary[:1]
    defaults = {
        "volume": (["category_salience"], ["change_in_market_share"]),
        "revenue": (["market_share"], ["brand_salience"]),
        "balanced": (["category_salience"], ["market_share"]),
        "efficiency": (["brand_salience"], ["change_in_brand_equity"]),
        "practical_mix": (["market_share"], ["category_salience"]),
    }
    return defaults.get(objective, (["category_salience"], ["market_share"]))


def _resolve_global_action_preference(text: str, objective: ScenarioObjectivePreference) -> ScenarioMarketAction:
    lower = str(text or "").lower()
    if _contains_any(lower, ("rebalance", "re-balance", "redistribute", "reallocate", "practical mix")):
        return "rebalance"
    if _contains_any(lower, ("protect", "defend", "preserve")):
        return "protect"
    if _contains_any(lower, ("recover", "repair", "turn around")):
        return "recover"
    if _contains_any(lower, ("deprioritize", "avoid", "pull back", "minimize")):
        return "deprioritize"
    if _contains_any(lower, ("reduce", "cut", "decrease")):
        return "decrease"
    if _contains_any(lower, ("hold", "maintain", "keep steady")):
        return "hold"
    if _contains_any(lower, ("increase", "push", "grow", "scale", "prioritize")):
        return "increase"
    if objective in {"balanced", "practical_mix"}:
        return "rebalance"
    return "increase"


def _resolve_practicality_level(text: str) -> Literal["high", "medium", "low"]:
    lower = str(text or "").lower()
    if _contains_any(lower, ("practical", "realistic", "conservative", "careful", "protect")):
        return "high"
    if _contains_any(lower, ("aggressive", "stretch", "maximize", "hard push")):
        return "low"
    return "medium"


def _resolve_aggressiveness_level(text: str, objective: ScenarioObjectivePreference) -> Literal["low", "medium", "high"]:
    lower = str(text or "").lower()
    if _contains_any(lower, ("aggressive", "hard push", "maximize", "go big")):
        return "high"
    if _contains_any(lower, ("protect", "practical", "careful", "conservative", "efficient")):
        return "low"
    if objective in {"volume", "revenue"}:
        return "medium"
    return "medium"


def _default_market_action_from_intelligence(row: dict[str, Any]) -> ScenarioMarketAction:
    cat_band = str(row.get("category_salience_band", "unknown"))
    brand_band = str(row.get("brand_salience_band", "unknown"))
    share_band = str(row.get("market_share_band", "unknown"))
    share_change_band = str(row.get("change_in_market_share_band", "neutral"))
    equity_change_band = str(row.get("change_in_brand_equity_band", "neutral"))
    high_salience = cat_band == "high" or brand_band == "high"
    low_salience = cat_band == "low" and brand_band == "low"
    high_share = share_band == "high"
    weak_momentum = share_change_band in {"mild_negative", "strong_negative"} or equity_change_band in {"mild_negative", "strong_negative"}
    strong_negative = share_change_band == "strong_negative" or equity_change_band == "strong_negative"
    positive_momentum = share_change_band in {"mild_positive", "strong_positive"} or equity_change_band in {"mild_positive", "strong_positive"}
    if high_share and weak_momentum:
        return "recover"
    if low_salience and strong_negative:
        return "deprioritize"
    if high_salience and weak_momentum:
        return "recover"
    if high_salience and positive_momentum:
        return "increase"
    if high_salience or high_share:
        return "protect"
    if weak_momentum:
        return "deprioritize" if low_salience else "recover"
    return "hold"


def _normalize_metric_token(metric_name: str) -> str:
    mapping = {
        "category salience": "category_salience",
        "brand salience": "brand_salience",
        "market share": "market_share",
        "change in market share": "change_in_market_share",
        "change in brand equity": "change_in_brand_equity",
        "use a mix": "metric_mix",
        "mix": "metric_mix",
    }
    raw = str(metric_name or "").strip().lower()
    return mapping.get(raw, raw.replace(" ", "_"))


def _resolve_task_types(
    prompt: str,
    interpreted_conditions: list[dict[str, Any]],
    explicit_market_actions: dict[str, ScenarioMarketAction],
    objective: ScenarioObjectivePreference,
) -> list[str]:
    lower = str(prompt or "").lower()
    task_types: list[str] = []
    if interpreted_conditions or explicit_market_actions:
        task_types.append("filter")
    if explicit_market_actions:
        task_types.append("recommend")
    if _contains_any(lower, ("prioritize", "rank", "top", "best", "where should", "which markets")):
        task_types.append("rank")
    if _contains_any(lower, ("compare", "versus", "vs", "against")):
        task_types.append("compare")
    if _contains_any(lower, ("identify", "diagnose", "why", "underperform", "declining performance")):
        task_types.append("diagnose")
    if _contains_any(lower, ("segment", "cluster", "group")):
        task_types.append("segment")
    if not task_types:
        task_types.extend(["recommend", "summarize"] if objective in {"volume", "revenue", "balanced", "efficiency", "practical_mix"} else ["summarize"])
    return _dedupe_strings(task_types)


def _build_metric_mappings(
    interpreted_conditions: list[dict[str, Any]],
    primary_anchor_metrics: list[str],
    secondary_anchor_metrics: list[str],
) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _append_mapping(
        metric_key: str,
        prompt_term: str,
        match_type: str,
        interpretation: str,
        confidence: float,
        qualifier_type: str = "",
    ) -> None:
        normalized_key = str(metric_key or "").strip()
        if not normalized_key or normalized_key in seen:
            return
        seen.add(normalized_key)
        source_column = normalized_key
        if qualifier_type == "band":
            source_column = f"{normalized_key}_band"
        elif qualifier_type == "trend":
            source_column = f"{normalized_key}_band"
        mappings.append(
            ScenarioMetricMapping(
                prompt_term=prompt_term or _metric_label(normalized_key),
                metric_key=normalized_key,
                metric_label=_metric_label(normalized_key),
                source_column=source_column,
                match_type=match_type,
                interpretation=interpretation,
                confidence=round(float(confidence), 4),
            ).model_dump(mode="json")
        )

    for item in interpreted_conditions:
        metric_key = str(item.get("metric_key", "")).strip()
        requested_direction = str(item.get("requested_direction", "")).strip()
        qualifier_type = str(item.get("qualifier_type", "")).strip()
        interpretation = f"Treat {metric_key} as {requested_direction}"
        _append_mapping(
            metric_key=metric_key,
            prompt_term=str(item.get("source_text", "")).strip() or _metric_label(metric_key),
            match_type="phrase_catalog",
            interpretation=interpretation,
            confidence=0.88,
            qualifier_type=qualifier_type,
        )

    for metric_key in [*primary_anchor_metrics, *secondary_anchor_metrics]:
        _append_mapping(
            metric_key=metric_key,
            prompt_term=_metric_label(metric_key),
            match_type="anchor_metric",
            interpretation="Used as an anchor metric for the analytical plan.",
            confidence=0.72,
        )
    return mappings


def _build_qualification_logic(
    interpreted_conditions: list[dict[str, Any]],
    explicit_market_actions: dict[str, ScenarioMarketAction],
) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for item in interpreted_conditions:
        metric_key = str(item.get("metric_key", "")).strip()
        requested_direction = str(item.get("requested_direction", "")).strip()
        qualifier_type = str(item.get("qualifier_type", "")).strip()
        rules.append(
            ScenarioLogicRule(
                kind="qualification",
                label=f"{_metric_label(metric_key)} must be {requested_direction}",
                metric_key=metric_key,
                operator="band_equals" if qualifier_type == "band" else "trend_equals",
                value=requested_direction,
                markets=list(item.get("matched_markets", []) or []),
                rationale=f"Derived from prompt phrase '{str(item.get('source_text', '')).strip() or _metric_label(metric_key)}'.",
            ).model_dump(mode="json")
        )
    if explicit_market_actions:
        rules.append(
            ScenarioLogicRule(
                kind="qualification",
                label="Explicit market scope from prompt",
                metric_key="market",
                operator="in",
                value="explicit_markets",
                markets=_dedupe_strings(list(explicit_market_actions.keys())),
                rationale="Named or condition-matched markets qualify for action assignment.",
            ).model_dump(mode="json")
        )
    return rules


def _build_prioritization_logic(
    objective: ScenarioObjectivePreference,
    global_action_preference: ScenarioMarketAction,
    action_preferences_by_market: dict[str, ScenarioMarketAction],
) -> list[dict[str, Any]]:
    action_markets: dict[str, list[str]] = {}
    for market, action in action_preferences_by_market.items():
        action_markets.setdefault(str(action), []).append(str(market))
    rules: list[dict[str, Any]] = [
        ScenarioLogicRule(
            kind="prioritization",
            label="Primary objective preference",
            metric_key="objective_preference",
            operator="equals",
            value=str(objective),
            rationale="Used to translate the interpreted business goal into execution weighting.",
        ).model_dump(mode="json"),
        ScenarioLogicRule(
            kind="prioritization",
            label="Default market action",
            metric_key="global_action_preference",
            operator="equals",
            value=str(global_action_preference),
            rationale="Acts as the default direction when no stronger market-specific instruction is available.",
        ).model_dump(mode="json"),
    ]
    for action, markets in sorted(action_markets.items()):
        rules.append(
            ScenarioLogicRule(
                kind="prioritization",
                label=f"{action.replace('_', ' ').title()} markets",
                metric_key="action_preferences_by_market",
                operator="assign_action",
                value=action,
                markets=_dedupe_strings(markets),
                rationale="Deterministic market action bucket generated from interpreted rules and market intelligence.",
            ).model_dump(mode="json")
        )
    return rules


def _build_analysis_plan(
    prompt: str,
    brand: str,
    selected_markets: list[str],
    interpreted_conditions: list[dict[str, Any]],
    primary_anchor_metrics: list[str],
    secondary_anchor_metrics: list[str],
    explicit_market_actions: dict[str, ScenarioMarketAction],
    action_preferences_by_market: dict[str, ScenarioMarketAction],
    objective: ScenarioObjectivePreference,
    global_action_preference: ScenarioMarketAction,
    negative_filters: list[str],
    confidence_score: float,
    readiness_for_generation: bool,
    confirmation_required: bool,
    explanation_notes: list[str],
) -> dict[str, Any]:
    task_types = _resolve_task_types(prompt, interpreted_conditions, explicit_market_actions, objective)
    metric_mappings = _build_metric_mappings(interpreted_conditions, primary_anchor_metrics, secondary_anchor_metrics)
    qualification_logic = _build_qualification_logic(interpreted_conditions, explicit_market_actions)
    prioritization_logic = _build_prioritization_logic(objective, global_action_preference, action_preferences_by_market)
    derived_metrics: list[str] = []
    for item in interpreted_conditions:
        metric_key = str(item.get("metric_key", "")).strip()
        if metric_key and metric_key not in derived_metrics:
            derived_metrics.append(metric_key)
    derived_metrics.extend([item for item in negative_filters if item not in derived_metrics])

    assumptions = _dedupe_strings(
        [
            "Prompt interpretation is converted into a plan first and executed deterministically downstream.",
            "Ambiguous business terms are resolved against available market-intelligence columns and metric bands.",
            "Qualification logic determines which markets match; prioritization logic determines which matching markets matter most.",
            *[
                note
                for note in explanation_notes
                if "understood" not in str(note).lower() and "matched" not in str(note).lower()
            ],
        ]
    )
    review_reason: list[str] = []
    if confirmation_required:
        review_reason.append("Confidence is below the auto-run threshold, so explicit review is required.")
    if not readiness_for_generation:
        review_reason.append("The system still needs clarification before deterministic execution.")
    if interpreted_conditions and any(len(item.get("matched_markets", []) or []) == 0 for item in interpreted_conditions):
        review_reason.append("At least one interpreted condition did not match any selected markets.")
    if not metric_mappings:
        review_reason.append("The prompt did not map cleanly to known business metrics.")

    output_fields = [
        "market",
        "action",
        "market_action_explanation",
        "matched_rules",
        "rank",
    ]
    if primary_anchor_metrics:
        output_fields.extend(primary_anchor_metrics[:2])
    output_fields = _dedupe_strings(output_fields)

    goal = str(prompt or "").strip() or "Interpret the business prompt and produce market-level recommendations."
    plan = ScenarioAnalysisPlan(
        task_types=task_types,
        goal=goal,
        entity=ScenarioPlanEntity(grain="market", scope=_dedupe_strings(selected_markets), brand=str(brand or "")),
        metric_mappings=metric_mappings,
        qualification_logic=qualification_logic,
        prioritization_logic=prioritization_logic,
        derived_metrics=_dedupe_strings(derived_metrics),
        grouping=[],
        segmentation=["action_preferences_by_market"] if action_preferences_by_market else [],
        output=ScenarioOutputSpec(output_type="ranked_market_recommendations", fields=output_fields),
        assumptions=assumptions,
        confidence=round(float(confidence_score), 4),
        needs_review=bool(confirmation_required or not readiness_for_generation),
        review_reason=_dedupe_strings(review_reason),
    )
    return plan.model_dump(mode="json")


def _build_clarification_questions(
    prompt: str,
    clarification_round: int,
    answers: dict[str, str],
    objective: ScenarioObjectivePreference,
    primary_anchor_metrics: list[str],
    explicit_market_actions: dict[str, ScenarioMarketAction],
    selected_markets: list[str],
    market_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    if not str(prompt or "").strip():
        questions.append(
            {
                "id": "q_business_objective",
                "question": "What should this scenario run optimize first?",
                "options": ["Grow volume", "Grow revenue", "Balanced growth", "Maximize efficiency", "Keep it practical"],
                "allow_free_text": False,
            }
        )
    if not primary_anchor_metrics:
        questions.append(
            {
                "id": "q_anchor_metric",
                "question": "Which market signal should guide the allocation most?",
                "options": ["Category salience", "Brand salience", "Market share", "Change in market share", "Change in brand equity", "Use a mix"],
                "allow_free_text": False,
            }
        )
    if not explicit_market_actions:
        questions.append(
            {
                "id": "q_market_direction",
                "question": "How should the generator treat the priority markets by default?",
                "options": ["Increase in priority markets", "Protect core markets", "Rebalance within current markets", "Reduce weaker markets"],
                "allow_free_text": False,
            }
        )
    if clarification_round < 1 and not answers.get("q_protect_core_markets", "").strip():
        high_share_markets = [str(row.get("market", "")) for row in market_rows if str(row.get("market_share_band", "")) == "high"]
        if high_share_markets:
            questions.append(
                {
                    "id": "q_protect_core_markets",
                    "question": "Should the strongest share markets be protected while we search for growth elsewhere?",
                    "options": ["Yes protect core markets", "Only protect the strongest markets", "No let every market move"],
                    "allow_free_text": False,
                }
            )
    if clarification_round < 2 and not answers.get("q_tradeoff_preference", "").strip():
        questions.append(
            {
                "id": "q_tradeoff_preference",
                "question": "When opportunity and efficiency disagree, what should win by default?",
                "options": ["Opportunity first, but practical", "Efficiency first", "Defend core share first", "Momentum first"],
                "allow_free_text": False,
            }
        )
    return questions[:3]


def _generate_market_action_explanation(
    market: str,
    action: ScenarioMarketAction,
    row: dict[str, Any],
    was_explicit: bool,
    prompt: str,
) -> str:
    """Generate a human-readable explanation for why a market got a specific action."""
    if was_explicit:
        # Check what condition matched
        prompt_lower = prompt.lower()
        share_change_band = str(row.get("change_in_market_share_band", "neutral"))
        cpr_band = str(row.get("avg_cpr_band", "unknown"))
        responsiveness = str(row.get("responsiveness_label", "Unknown"))
        market_share = row.get("market_share")
        cat_salience = row.get("category_salience")
        brand_salience = row.get("brand_salience")
        
        reasons = []
        
        # Check for losing share condition
        if any(phrase in prompt_lower for phrase in ["losing", "share loss", "declining share"]):
            if share_change_band in {"mild_negative", "strong_negative"}:
                change_val = row.get("change_in_market_share", 0)
                reasons.append(f"losing market share ({change_val:+.1f}%)")
        
        # Check for gaining share condition
        if any(phrase in prompt_lower for phrase in ["gaining", "share gain", "growing share"]):
            if share_change_band in {"mild_positive", "strong_positive"}:
                change_val = row.get("change_in_market_share", 0)
                reasons.append(f"gaining market share ({change_val:+.1f}%)")
        
        # Check for smaller markets condition
        if any(phrase in prompt_lower for phrase in ["smaller market", "small market", "lower share", "low share", "smaller presence", "low presence"]):
            if market_share is not None:
                reasons.append(f"smaller market with {market_share:.1f}% share")
        
        # Check for bigger markets condition
        if any(phrase in prompt_lower for phrase in ["bigger market", "large market", "larger market", "high share", "bigger presence", "strong presence"]):
            if market_share is not None:
                reasons.append(f"bigger market with {market_share:.1f}% share")
        
        # Check for low salience condition
        if any(phrase in prompt_lower for phrase in ["low salience", "weak salience", "underdeveloped"]):
            if cat_salience is not None or brand_salience is not None:
                reasons.append(f"low salience (cat: {cat_salience:.1f}%, brand: {brand_salience:.1f}%)")
        
        # Check for high salience condition
        if any(phrase in prompt_lower for phrase in ["high salience", "strong salience", "developed market"]):
            if cat_salience is not None or brand_salience is not None:
                reasons.append(f"high salience (cat: {cat_salience:.1f}%, brand: {brand_salience:.1f}%)")
        
        # Check for CPR condition
        if any(phrase in prompt_lower for phrase in ["high cpr", "poor cpr", "expensive"]):
            if cpr_band == "high_cost":
                cpr_val = row.get("avg_cpr")
                if cpr_val:
                    reasons.append(f"high CPR (₹{cpr_val:.0f})")
        
        # Check for elasticity condition
        if any(phrase in prompt_lower for phrase in ["low elasticity", "weak elasticity"]):
            if responsiveness.lower() in {"low", "weak", "poor"}:
                reasons.append(f"low elasticity ({responsiveness})")
        
        if any(phrase in prompt_lower for phrase in ["high elasticity", "strong elasticity"]):
            if responsiveness.lower() in {"high", "strong", "good"}:
                reasons.append(f"high elasticity ({responsiveness})")
        
        if reasons:
            return f"Matched your criteria: {', '.join(reasons)}"
        else:
            return "Explicitly mentioned in your prompt"
    
    # Intelligence-based explanation
    cat_band = str(row.get("category_salience_band", "unknown"))
    brand_band = str(row.get("brand_salience_band", "unknown"))
    share_band = str(row.get("market_share_band", "unknown"))
    share_change_band = str(row.get("change_in_market_share_band", "neutral"))
    equity_change_band = str(row.get("change_in_brand_equity_band", "neutral"))
    
    if action == "increase":
        if cat_band == "high" or brand_band == "high":
            return f"High opportunity ({cat_band} category salience, {brand_band} brand salience)"
        return "Growth opportunity identified"
    
    elif action == "protect":
        if share_band == "high":
            return f"Core market with {share_band} market share - protecting position"
        return "Stable market worth protecting"
    
    elif action == "recover":
        if share_change_band in {"mild_negative", "strong_negative"}:
            change_val = row.get("change_in_market_share", 0)
            return f"Declining performance ({change_val:+.1f}% share change) - needs recovery"
        if equity_change_band in {"mild_negative", "strong_negative"}:
            return "Weakening brand equity - needs attention"
        return "Recovery opportunity"
    
    elif action == "deprioritize":
        reasons = []
        if cat_band == "low" and brand_band == "low":
            reasons.append("low salience")
        if share_change_band == "strong_negative":
            reasons.append("steep decline")
        if reasons:
            return f"Lower priority: {', '.join(reasons)}"
        return "Lower priority market"
    
    elif action == "hold":
        return "Stable market - maintain current allocation"
    
    elif action == "rebalance":
        return "Rebalancing allocation across channels"
    
    elif action == "decrease":
        return "Reducing allocation based on efficiency"
    
    return "Intelligence-based recommendation"


def _build_resolved_intent_from_context(
    prompt: str,
    brand: str,
    selected_markets: list[str],
    market_rows: list[dict[str, Any]],
    clarification_round: int = 0,
    answers: dict[str, str] | None = None,
) -> dict[str, Any]:
    answers = answers or {}
    combined_text = _combined_intent_text(prompt, answers)
    explanation_notes: list[str] = []
    objective = _resolve_objective_preference(
        answers.get("q_business_objective", combined_text) if answers.get("q_business_objective") else combined_text
    )
    primary_anchor_metrics, secondary_anchor_metrics = _resolve_anchor_metrics(
        answers.get("q_anchor_metric", combined_text) if answers.get("q_anchor_metric") else combined_text,
        objective,
    )
    global_action_preference = _resolve_global_action_preference(
        answers.get("q_market_direction", combined_text) if answers.get("q_market_direction") else combined_text,
        objective,
    )
    extraction = _extract_prompt_market_actions(combined_text, selected_markets, market_rows)
    explicit_market_actions = dict(extraction.get("actions", {}) or {})
    interpreted_conditions = list(extraction.get("interpreted_conditions", []) or [])
    explanation_notes.extend(list(extraction.get("notes", []) or []))
    interpretation_summary = str(extraction.get("interpretation_summary", "") or "").strip()
    structured_condition_detected = bool(extraction.get("structured_condition_detected"))
    zero_match_condition_detected = bool(extraction.get("zero_match_condition_detected"))
    practicality_level = _resolve_practicality_level(
        answers.get("q_tradeoff_preference", combined_text) if answers.get("q_tradeoff_preference") else combined_text
    )
    aggressiveness_level = _resolve_aggressiveness_level(combined_text, objective)
    action_preferences_by_market: dict[str, ScenarioMarketAction] = {}

    if answers.get("q_market_direction"):
        lower = answers["q_market_direction"].lower()
        if "protect" in lower:
            global_action_preference = "protect"
        elif "rebalance" in lower:
            global_action_preference = "rebalance"
        elif "reduce" in lower:
            global_action_preference = "decrease"
        else:
            global_action_preference = "increase"

    if answers.get("q_anchor_metric"):
        metric_token = _normalize_metric_token(answers["q_anchor_metric"])
        if metric_token == "metric_mix":
            primary_anchor_metrics = _dedupe_strings(primary_anchor_metrics)
        else:
            if metric_token not in primary_anchor_metrics:
                secondary_anchor_metrics = _dedupe_strings(primary_anchor_metrics + secondary_anchor_metrics)
                primary_anchor_metrics = [metric_token]
    elif interpreted_conditions:
        interpreted_metric_keys = [
            str(item.get("metric_key", "")).strip()
            for item in interpreted_conditions
            if str(item.get("metric_key", "")).strip()
        ]
        if interpreted_metric_keys:
            primary_anchor_metrics = _dedupe_strings(interpreted_metric_keys[:2])
            secondary_anchor_metrics = _dedupe_strings(interpreted_metric_keys[2:4] + secondary_anchor_metrics)

    negative_filters: list[str] = []
    if _contains_any(combined_text, ("poor cpr", "weak cpr", "avoid inefficient", "efficiency first")):
        negative_filters.append("avoid_high_cpr_markets")
    if _contains_any(combined_text, ("weak elasticity", "low elasticity", "avoid weak responsiveness")):
        negative_filters.append("avoid_low_elasticity_markets")
    if _contains_any(combined_text, ("declining equity", "negative equity", "avoid weak equity")):
        negative_filters.append("avoid_declining_brand_equity")
    if _contains_any(combined_text, ("declining share", "share loss", "avoid weak share")):
        negative_filters.append("avoid_declining_market_share")

    target_markets: list[str] = []
    protected_markets: list[str] = []
    held_markets: list[str] = []
    deprioritized_markets: list[str] = []
    market_action_explanations: dict[str, str] = {}

    apply_global_broadly = len(explicit_market_actions) == 0 and not structured_condition_detected

    for row in market_rows:
        market = str(row.get("market", "")).strip()
        if not market:
            continue
        action = explicit_market_actions.get(market)
        was_explicit = action is not None
        
        if action is None:
            action = _default_market_action_from_intelligence(row)
            # Only override with global preference if we should apply it broadly
            # AND the intelligence-based action is "hold"
            if apply_global_broadly and global_action_preference in {"increase", "decrease", "rebalance"} and action == "hold":
                action = global_action_preference
        if answers.get("q_protect_core_markets", "").lower().startswith("yes") and str(row.get("market_share_band", "")) == "high":
            action = "protect" if action not in {"deprioritize", "decrease"} else action
        
        action_preferences_by_market[market] = action
        
        # Generate explanation for this market's action
        explanation = _generate_market_action_explanation(market, action, row, was_explicit, combined_text)
        market_action_explanations[market] = explanation
        
        if action in {"increase", "recover"}:
            target_markets.append(market)
        elif action == "protect":
            protected_markets.append(market)
        elif action == "deprioritize":
            deprioritized_markets.append(market)
        elif action == "hold":
            held_markets.append(market)

    if explicit_market_actions:
        if structured_condition_detected:
            explanation_notes.append(
                f"Conditional market filtering applied: {len(explicit_market_actions)} markets matched the specified criteria from your prompt."
            )
        else:
            explanation_notes.append("Explicit market instructions from the prompt were given precedence over inferred rankings.")
    elif zero_match_condition_detected:
        explanation_notes.append("The prompt referred to a specific market condition, but no selected markets matched it, so no blanket increase/decrease was applied.")
    if answers.get("q_tradeoff_preference"):
        explanation_notes.append(f"Trade-off preference applied: {answers['q_tradeoff_preference']}.")
    if answers.get("q_protect_core_markets"):
        explanation_notes.append(f"Core-market protection setting: {answers['q_protect_core_markets']}.")
    if answers.get("q_interpretation_feedback"):
        explanation_notes.append("User feedback was incorporated into the latest interpretation.")
    if interpretation_summary:
        explanation_notes.insert(0, interpretation_summary)

    confidence_score = 0.2
    if str(prompt or "").strip():
        confidence_score += 0.15
    if primary_anchor_metrics:
        confidence_score += 0.2
    if objective:
        confidence_score += 0.2
    if explicit_market_actions or global_action_preference not in {"hold", "rebalance"}:
        confidence_score += 0.15
    if interpreted_conditions:
        confidence_score += min(0.12, 0.04 * len(interpreted_conditions))
    if answers:
        confidence_score += min(0.2, 0.08 * len([v for v in answers.values() if str(v or "").strip()]))
    if len(selected_markets) <= 2 and not explicit_market_actions:
        confidence_score -= 0.05
    if zero_match_condition_detected:
        confidence_score -= 0.08
    confidence_score = max(0.05, min(0.98, confidence_score))

    questions = _build_clarification_questions(
        prompt=prompt,
        clarification_round=clarification_round,
        answers=answers,
        objective=objective,
        primary_anchor_metrics=primary_anchor_metrics,
        explicit_market_actions=explicit_market_actions,
        selected_markets=selected_markets,
        market_rows=market_rows,
    )
    readiness_for_generation = bool(confidence_score >= 0.8 or clarification_round >= 2 or len(questions) == 0)
    confirmation_required = bool(readiness_for_generation and confidence_score < 0.8)
    if confirmation_required:
        explanation_notes.append("Confidence remained below the auto-run threshold after the clarification limit; explicit user confirmation is required.")
    analysis_plan = _build_analysis_plan(
        prompt=prompt,
        brand=brand,
        selected_markets=selected_markets,
        interpreted_conditions=interpreted_conditions,
        primary_anchor_metrics=_dedupe_strings(primary_anchor_metrics),
        secondary_anchor_metrics=_dedupe_strings(secondary_anchor_metrics),
        explicit_market_actions=explicit_market_actions,
        action_preferences_by_market=action_preferences_by_market,
        objective=objective,
        global_action_preference=global_action_preference,
        negative_filters=_dedupe_strings(negative_filters),
        confidence_score=confidence_score,
        readiness_for_generation=readiness_for_generation,
        confirmation_required=confirmation_required,
        explanation_notes=_dedupe_strings(explanation_notes),
    )

    resolved_intent = ScenarioResolvedIntent(
        analysis_plan=analysis_plan,
        primary_anchor_metrics=_dedupe_strings(primary_anchor_metrics),
        secondary_anchor_metrics=_dedupe_strings(secondary_anchor_metrics),
        interpreted_conditions=interpreted_conditions,
        interpretation_summary=interpretation_summary,
        negative_filters=_dedupe_strings(negative_filters),
        target_markets=_dedupe_strings(target_markets),
        protected_markets=_dedupe_strings(protected_markets),
        held_markets=_dedupe_strings(held_markets),
        deprioritized_markets=_dedupe_strings(deprioritized_markets),
        action_preferences_by_market=action_preferences_by_market,
        market_action_explanations=market_action_explanations,
        global_action_preference=global_action_preference,
        objective_preference=objective,
        aggressiveness_level=aggressiveness_level,
        practicality_level=practicality_level,
        confidence_score=round(float(confidence_score), 4),
        readiness_for_generation=readiness_for_generation,
        confirmation_required=confirmation_required,
        explanation_notes=_dedupe_strings(explanation_notes),
    ).model_dump(mode="json")
    return {
        "status": "ready" if readiness_for_generation else "needs_clarification",
        "clarification_round": int(max(0, clarification_round)),
        "confidence_score": round(float(confidence_score), 4),
        "readiness_for_generation": readiness_for_generation,
        "confirmation_required": confirmation_required,
        "questions": questions if not readiness_for_generation else [],
        "partial_interpretation": None if readiness_for_generation else resolved_intent,
        "resolved_intent": resolved_intent if readiness_for_generation else None,
        "notes": resolved_intent.get("explanation_notes", []),
    }


def _resolve_scenario_intent_payload(
    payload: ScenarioIntentResolveRequest,
    clarification_round: int = 0,
    clarification_answers: dict[str, str] | None = None,
) -> dict[str, Any]:
    ctx = _load_optimization_context(
        OptimizeAutoRequest(
            selected_brand=payload.selected_brand,
            selected_markets=payload.selected_markets,
            budget_increase_type=payload.budget_increase_type,
            budget_increase_value=payload.budget_increase_value,
            market_overrides=payload.market_overrides,
        )
    )
    market_guidance = dict(ctx.get("market_intelligence_guidance", {}) or {})
    market_rows = market_guidance.get("rows", [])
    if not isinstance(market_rows, list):
        market_rows = []
    if not market_rows:
        market_rows = [{"market": region} for region in ctx.get("regions", []) if str(region).strip()]
        notes = list(market_guidance.get("notes", []) or [])
        notes.append("Market intelligence rows were unavailable for intent resolution; fallback region rows were used.")
        market_guidance["notes"] = _dedupe_strings(notes)
    result = _build_resolved_intent_from_context(
        prompt=payload.intent_prompt,
        brand=ctx["brand"],
        selected_markets=ctx["regions"],
        market_rows=market_rows,
        clarification_round=clarification_round,
        answers=clarification_answers,
    )
    result["market_intelligence_guidance"] = {
        "source_file": market_guidance.get("source_file"),
        "matched_row_count": int(market_guidance.get("matched_row_count", 0) or 0),
        "notes": market_guidance.get("notes", []),
    }
    return result


def _default_strategy_controls() -> dict[str, Any]:
    return {
        "family_mix_weights": {"volume": 0.4, "revenue": 0.4, "balanced": 0.2},
        "pace_preference": "steady",
        "coverage_preference": "broad",
        "diversity_preference": "medium",
        "budget_zone_preference": "mixed",
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
    budget_zone = str(raw.get("budget_zone_preference", default["budget_zone_preference"])).strip().lower()
    if pace not in {"steady", "fast"}:
        pace = default["pace_preference"]
    if coverage not in {"few", "broad"}:
        coverage = default["coverage_preference"]
    if diversity not in {"low", "medium", "high"}:
        diversity = default["diversity_preference"]
    if budget_zone not in {"low", "mid", "high", "mixed"}:
        budget_zone = default["budget_zone_preference"]
    return {
        "family_mix_weights": _normalize_family_weights(raw.get("family_mix_weights")),
        "pace_preference": pace,
        "coverage_preference": coverage,
        "diversity_preference": diversity,
        "budget_zone_preference": budget_zone,
    }


def _merge_strategy_override(base_strategy: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    if not override:
        return dict(base_strategy)
    cleaned = _sanitize_strategy_controls(override)
    merged = dict(base_strategy)
    for key in ("family_mix_weights", "pace_preference", "coverage_preference", "diversity_preference", "budget_zone_preference"):
        merged[key] = cleaned[key]
    return merged


def _derive_plan_market_state(
    intent: ScenarioResolvedIntent,
    regions: list[str],
) -> tuple[dict[str, ScenarioMarketAction], set[str], set[str], set[str], list[str]]:
    analysis_plan = ScenarioAnalysisPlan.model_validate(intent.analysis_plan or {})
    action_preferences: dict[str, ScenarioMarketAction] = {}
    target_markets: set[str] = set()
    protected_markets: set[str] = set()
    deprioritized_markets: set[str] = set()
    notes: list[str] = []

    for rule in analysis_plan.prioritization_logic:
        if str(rule.operator).strip() != "assign_action":
            continue
        action_value = str(rule.value).strip()
        if action_value not in {"increase", "decrease", "protect", "hold", "deprioritize", "rebalance", "recover"}:
            continue
        for market in rule.markets:
            market_name = str(market).strip()
            if not market_name or market_name not in regions:
                continue
            action_preferences[market_name] = action_value  # type: ignore[assignment]
            if action_value in {"increase", "recover"}:
                target_markets.add(market_name)
            elif action_value == "protect":
                protected_markets.add(market_name)
            elif action_value in {"decrease", "deprioritize"}:
                deprioritized_markets.add(market_name)

    for rule in analysis_plan.qualification_logic:
        operator = str(rule.operator).strip()
        if operator == "in":
            for market in rule.markets:
                market_name = str(market).strip()
                if market_name and market_name in regions and market_name not in action_preferences:
                    action_preferences[market_name] = intent.global_action_preference
        if operator in {"band_equals", "trend_equals"} and rule.markets:
            for market in rule.markets:
                market_name = str(market).strip()
                if not market_name or market_name not in regions:
                    continue
                if market_name not in action_preferences and intent.global_action_preference in {
                    "increase",
                    "decrease",
                    "protect",
                    "recover",
                    "deprioritize",
                    "rebalance",
                }:
                    action_preferences[market_name] = intent.global_action_preference

    if action_preferences:
        notes.append("Deterministic strategy controls were derived from the canonical analysis plan.")
    return action_preferences, target_markets, protected_markets, deprioritized_markets, notes


def _build_generation_strategy_from_resolved_intent(
    resolved_intent: dict[str, Any] | None,
    ctx: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    intent = ScenarioResolvedIntent.model_validate(resolved_intent or {})
    objective = str(intent.objective_preference)
    objective_weights = {
        "volume": {"volume": 0.65, "revenue": 0.15, "balanced": 0.20},
        "revenue": {"volume": 0.15, "revenue": 0.65, "balanced": 0.20},
        "balanced": {"volume": 0.25, "revenue": 0.25, "balanced": 0.50},
        "efficiency": {"volume": 0.20, "revenue": 0.50, "balanced": 0.30},
        "practical_mix": {"volume": 0.25, "revenue": 0.25, "balanced": 0.50},
    }
    family_mix_weights = objective_weights.get(objective, objective_weights["balanced"])
    aggressiveness = str(intent.aggressiveness_level)
    practicality = str(intent.practicality_level)
    if aggressiveness == "high":
        pace_preference = "fast"
        diversity_preference = "high"
    elif aggressiveness == "low":
        pace_preference = "steady"
        diversity_preference = "low"
    else:
        pace_preference = "steady"
        diversity_preference = "medium"
    if practicality == "high":
        coverage_preference = "few"
    else:
        coverage_preference = "broad"
    if objective == "efficiency":
        budget_zone_preference = "low"
    elif objective == "volume":
        budget_zone_preference = "high" if aggressiveness == "high" else "mid"
    elif objective == "revenue":
        budget_zone_preference = "mid"
    elif objective == "practical_mix":
        budget_zone_preference = "mid"
    else:
        budget_zone_preference = "mixed"

    action_bias_map: dict[str, float] = {
        "increase": 0.55,
        "recover": 0.30,
        "protect": 0.18,
        "hold": 0.0,
        "rebalance": 0.10,
        "decrease": -0.30,
        "deprioritize": -0.50,
    }
    responsiveness_multiplier = {"High": 1.0, "Medium": 0.85, "Low": 0.7, "Unknown": 0.82}
    cpr_multiplier = {"low_cost": 1.0, "mid_cost": 0.86, "high_cost": 0.72, "unknown": 0.82}
    intelligence_map = {
        str(row.get("market", "")).strip(): row
        for row in (ctx.get("market_intelligence_guidance", {}) or {}).get("rows", [])
        if isinstance(row, dict) and str(row.get("market", "")).strip()
    }

    plan_action_preferences, plan_target_markets, plan_protected_markets, plan_deprioritized_markets, plan_notes = _derive_plan_market_state(
        intent,
        list(ctx["regions"]),
    )
    effective_action_preferences = dict(intent.action_preferences_by_market)
    effective_action_preferences.update(plan_action_preferences)
    target_markets = set(intent.target_markets) | plan_target_markets
    protected_markets = set(intent.protected_markets) | plan_protected_markets
    deprioritized_markets = set(intent.deprioritized_markets) | plan_deprioritized_markets

    market_bias_scores: dict[str, float] = {}
    notes: list[str] = list(plan_notes)
    for region in ctx["regions"]:
        action = effective_action_preferences.get(region, intent.global_action_preference if region in plan_action_preferences else "hold")
        base_bias = float(action_bias_map.get(str(action), 0.0))
        row = intelligence_map.get(region, {})
        resp_mult = float(responsiveness_multiplier.get(str(row.get("responsiveness_label", "Unknown")), 0.82))
        cpr_mult = float(cpr_multiplier.get(str(row.get("avg_cpr_band", "unknown")), 0.82))
        if base_bias > 0:
            if action == "protect":
                adjusted = base_bias * max(0.68, 0.75 * resp_mult + 0.25)
            else:
                adjusted = base_bias * resp_mult * cpr_mult
        else:
            adjusted = base_bias
        if region in target_markets and adjusted >= 0:
            adjusted += 0.08
        if region in protected_markets and adjusted >= 0:
            adjusted = max(adjusted, 0.15)
        if region in deprioritized_markets and adjusted <= 0:
            adjusted -= 0.05
        market_bias_scores[region] = round(float(max(-0.9, min(0.9, adjusted))), 4)

    if any(v > 0 for v in market_bias_scores.values()):
        notes.append("Positive market bias weights were dampened by elasticity and CPR where efficiency signals were weak.")
    strategy = {
        "family_mix_weights": family_mix_weights,
        "pace_preference": pace_preference,
        "coverage_preference": coverage_preference,
        "diversity_preference": diversity_preference,
        "budget_zone_preference": budget_zone_preference,
        "objective_preference": objective,
        "market_action_preferences": effective_action_preferences,
        "market_bias_scores": market_bias_scores,
    }
    return _sanitize_strategy_controls(strategy) | {
        "objective_preference": objective,
        "market_action_preferences": effective_action_preferences,
        "market_bias_scores": market_bias_scores,
    }, notes


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
        "pace_preference (steady|fast), coverage_preference (few|broad), diversity_preference (low|medium|high), "
        "budget_zone_preference (low|mid|high|mixed).\n"
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


def _derive_sampling_params(strategy: dict[str, Any]) -> dict[str, Any]:
    pace = strategy.get("pace_preference", "steady")
    coverage = strategy.get("coverage_preference", "broad")
    diversity = strategy.get("diversity_preference", "medium")
    budget_zone = str(strategy.get("budget_zone_preference", "mixed")).strip().lower()
    objective = str(strategy.get("objective_preference", "balanced")).strip().lower()
    if budget_zone not in {"low", "mid", "high", "mixed"}:
        budget_zone = "mixed"
    near_sigma = 0.04 if pace == "steady" else 0.08
    broad_sigma = 0.20 if pace == "steady" else 0.35
    active_fraction = 1.0 if coverage == "broad" else 0.35
    distance_scale = {"low": 0.75, "medium": 1.0, "high": 1.3}.get(str(diversity), 1.0)
    if objective == "volume":
        channel_tilt = {"tv": 1.15, "digital": 1.0}
    elif objective == "revenue":
        channel_tilt = {"tv": 0.95, "digital": 1.1}
    elif objective == "efficiency":
        channel_tilt = {"tv": 0.9, "digital": 1.15}
    else:
        channel_tilt = {"tv": 1.0, "digital": 1.0}
    return {
        "near_sigma": near_sigma,
        "broad_sigma": broad_sigma,
        "active_fraction": active_fraction,
        "min_distance": SCENARIO_DEFAULT_MIN_DISTANCE * distance_scale,
        "budget_zone_preference": budget_zone,
        "market_bias_scores": dict(strategy.get("market_bias_scores", {}) or {}),
        "market_action_preferences": dict(strategy.get("market_action_preferences", {}) or {}),
        "channel_tilt": channel_tilt,
    }


def _sample_budget_target_in_band(
    lower_budget: float,
    upper_budget: float,
    budget_zone_preference: str,
    near_opt: bool,
    rng: random.Random,
) -> float:
    lower = float(min(lower_budget, upper_budget))
    upper = float(max(lower_budget, upper_budget))
    if upper - lower <= max(_budget_epsilon(upper), 1e-6):
        return upper
    span = upper - lower
    third = span / 3.0
    zone = str(budget_zone_preference or "mixed").strip().lower()
    if zone not in {"low", "mid", "high", "mixed"}:
        zone = "mixed"

    if zone == "low":
        zone_lo, zone_hi = lower, lower + third
    elif zone == "mid":
        zone_lo, zone_hi = lower + third, lower + 2.0 * third
    elif zone == "high":
        zone_lo, zone_hi = lower + 2.0 * third, upper
    else:
        zone_lo, zone_hi = lower, upper

    zone_lo = max(lower, min(zone_lo, upper))
    zone_hi = max(zone_lo, min(zone_hi, upper))

    if near_opt:
        if zone == "mixed":
            hi_bias_lo = max(lower, upper - 0.2 * span)
            return float(rng.uniform(hi_bias_lo, upper))
        return float(rng.uniform(zone_lo, zone_hi))

    if zone == "mixed":
        return float(rng.uniform(lower, upper))

    if rng.random() < 0.7:
        return float(rng.uniform(zone_lo, zone_hi))
    return float(rng.uniform(lower, upper))


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
    params: dict[str, Any],
    rng: random.Random,
) -> np.ndarray:
    v = np.array(center, dtype=float)
    sigma = params["near_sigma"] if near_opt else params["broad_sigma"]
    market_count = max(1, len(regions))
    active_fraction = params["active_fraction"] if not near_opt else 1.0
    active_markets = max(1, int(round(market_count * active_fraction)))
    active_idx = set(rng.sample(range(market_count), active_markets)) if active_markets < market_count else set(range(market_count))
    market_bias_scores = dict(params.get("market_bias_scores", {}) or {})
    market_action_preferences = dict(params.get("market_action_preferences", {}) or {})
    channel_tilt = dict(params.get("channel_tilt", {}) or {})
    mandatory_idx = {
        idx
        for idx, region in enumerate(regions)
        if abs(float(_finite(market_bias_scores.get(region, 0.0), 0.0))) >= 0.2
    }
    active_idx.update(mandatory_idx)
    for m_idx in range(market_count):
        if m_idx not in active_idx:
            continue
        region = regions[m_idx]
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
        bias = float(_finite(market_bias_scores.get(region, 0.0), 0.0))
        action = str(market_action_preferences.get(region, "hold"))
        tv_bias = bias * sigma * float(_finite(channel_tilt.get("tv", 1.0), 1.0))
        dg_bias = bias * sigma * float(_finite(channel_tilt.get("digital", 1.0), 1.0))
        if action == "rebalance":
            tv_bias += rng.gauss(0.0, sigma * 0.18)
            dg_bias -= tv_bias * 0.75
        tv_noise += tv_bias
        dg_noise += dg_bias
        v[tv_i] += tv_noise
        v[dg_i] += dg_noise
        if action == "protect":
            v[tv_i] = max(v[tv_i], center[tv_i] - (sigma * 0.2))
            v[dg_i] = max(v[dg_i], center[dg_i] - (sigma * 0.2))
        elif action == "recover":
            v[tv_i] = max(v[tv_i], center[tv_i] - (sigma * 0.12))
            v[dg_i] = max(v[dg_i], center[dg_i] - (sigma * 0.12))
        elif action in {"deprioritize", "decrease"}:
            v[tv_i] = min(v[tv_i], center[tv_i] + (sigma * 0.15))
            v[dg_i] = min(v[dg_i], center[dg_i] + (sigma * 0.15))
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
    requested_scenario_budget_lower: float | None = None,
    requested_scenario_budget_upper: float | None = None,
    scenario_label_prefix: str | None = None,
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
    region_prices = _compute_region_prices_last_3_months(ctx["model_df"], ctx["brand"], regions)
    bounds, coeffs, baseline_budget = _build_variable_bounds_and_coeffs(market_data, regions, limits_map)
    requested_target_budget = float(ctx["target_budget"])
    low_vector = np.array([lo for lo, _ in bounds], dtype=float)
    high_vector = np.array([hi for _, hi in bounds], dtype=float)
    feasible_budget_min = float(baseline_budget + float(np.dot(coeffs, low_vector)))
    feasible_budget_max = float(baseline_budget + float(np.dot(coeffs, high_vector)))
    target_budget = float(min(max(requested_target_budget, feasible_budget_min), feasible_budget_max))
    fallback_lower = float(max(feasible_budget_min, target_budget * SCENARIO_BUDGET_BAND_LOWER_RATIO))
    requested_band_upper = float(
        _finite(requested_scenario_budget_upper, target_budget)
        if requested_scenario_budget_upper is not None
        else target_budget
    )
    requested_band_lower = float(
        _finite(requested_scenario_budget_lower, fallback_lower)
        if requested_scenario_budget_lower is not None
        else fallback_lower
    )
    if requested_band_upper <= 0:
        requested_band_upper = target_budget
    if requested_band_lower < 0:
        requested_band_lower = 0.0
    if requested_band_lower > requested_band_upper:
        requested_band_lower, requested_band_upper = requested_band_upper, requested_band_lower

    scenario_budget_upper = float(min(max(requested_band_upper, feasible_budget_min), feasible_budget_max))
    scenario_budget_lower = float(max(requested_band_lower, feasible_budget_min))
    if scenario_budget_lower > scenario_budget_upper:
        scenario_budget_lower = scenario_budget_upper

    seed_budget = float(scenario_budget_upper)
    budget_adjust_note: str | None = None
    if abs(target_budget - requested_target_budget) > _budget_epsilon(requested_target_budget):
        budget_adjust_note = (
            "Requested target budget was outside feasible bounds for current market constraints. "
            f"Adjusted from {round(requested_target_budget, 2)} to {round(target_budget, 2)}."
        )
    rng = random.Random(_stable_score(f"{ctx['brand']}|{','.join(regions)}|{seed_budget}|{scenario_budget_lower}|{scenario_budget_upper}"))

    # Build per-market elasticity lookup from India-level all-brand file for TV/Digital split guidance.
    market_elasticity_rows = (ctx.get("market_elasticity_guidance") or {}).get("rows", [])
    seed_elasticity_map: dict[str, dict[str, Any]] = {
        str(r.get("market", "")).strip(): r
        for r in market_elasticity_rows
        if isinstance(r, dict) and str(r.get("market", "")).strip()
    }

    set_progress(20, "Computing deterministic seed scenarios...")
    volume_seed = _build_fast_seed_vector(
        market_data=market_data,
        regions=regions,
        bounds=bounds,
        baseline_budget=baseline_budget,
        target_budget=seed_budget,
        region_prices=region_prices,
        objective="volume",
        elasticity_map=seed_elasticity_map,
    )
    revenue_seed = _build_fast_seed_vector(
        market_data=market_data,
        regions=regions,
        bounds=bounds,
        baseline_budget=baseline_budget,
        target_budget=seed_budget,
        region_prices=region_prices,
        objective="revenue",
        elasticity_map=seed_elasticity_map,
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
    low = np.array([lo for lo, _ in bounds], dtype=float)
    span = np.array([max(1e-9, hi - lo) for lo, hi in bounds], dtype=float)
    near_count = 0
    attempts = 0
    notes: list[str] = []
    if budget_adjust_note:
        notes.append(budget_adjust_note)
    notes.append("Used fast deterministic seed builder to avoid slow optimization stalls during scenario generation.")
    if scenario_budget_upper - scenario_budget_lower > _budget_epsilon(scenario_budget_upper):
        notes.append(
            f"Scenario budget band active: {round(scenario_budget_lower, 2)} to {round(scenario_budget_upper, 2)}."
        )

    budget_zone_preference = str(params.get("budget_zone_preference", "mixed"))

    def timed_out() -> bool:
        return (time.time() - started_at) >= runtime_limit

    family_weights = _normalize_family_weights(strategy.get("family_mix_weights"))
    active_families = [fam for fam, weight in family_weights.items() if float(weight) > 1e-9 and fam in seeds]
    if not active_families:
        active_families = [fam for fam in seeds.keys()]
    family_weight_sum = float(sum(family_weights.get(fam, 0.0) for fam in active_families)) or float(len(active_families))

    family_targets: dict[str, int] = {}
    remaining_target = int(target_total)
    for idx, fam in enumerate(active_families):
        if idx == len(active_families) - 1:
            family_targets[fam] = max(0, remaining_target)
            break
        fam_weight = float(family_weights.get(fam, 0.0)) / family_weight_sum
        fam_target = int(round(target_total * fam_weight))
        fam_target = max(1, min(remaining_target, fam_target))
        family_targets[fam] = fam_target
        remaining_target -= fam_target

    family_near_targets: dict[str, int] = {}
    remaining_near = int(target_near)
    for idx, fam in enumerate(active_families):
        if idx == len(active_families) - 1:
            family_near_targets[fam] = max(0, min(family_targets.get(fam, 0), remaining_near))
            break
        fam_weight = float(family_weights.get(fam, 0.0)) / family_weight_sum
        fam_near = int(round(target_near * fam_weight))
        fam_near = max(0, min(family_targets.get(fam, 0), fam_near))
        family_near_targets[fam] = fam_near
        remaining_near -= fam_near

    def generate_family_batch(fam: str, target_count: int, near_target_count: int) -> dict[str, Any]:
        local_seed = _stable_score(
            f"{ctx['brand']}|{fam}|{seed_budget}|{scenario_budget_lower}|{scenario_budget_upper}|{target_count}"
        )
        local_rng = random.Random(local_seed)
        local_accepted: list[dict[str, Any]] = []
        local_scaled = np.empty((0, len(bounds)), dtype=float)
        local_exact_keys: set[tuple[float, ...]] = set()
        local_near_count = 0
        local_attempts = 0
        local_notes: list[str] = []
        worker_min_distance = float(min_distance)
        worker_timeout_hit = False
        worker_target_count = max(target_count, int(math.ceil(target_count * 1.15)))

        def local_try_accept_candidate(
            vec: np.ndarray,
            seed_source: str,
            near_opt: bool,
            budget_target: float | None = None,
        ) -> bool:
            nonlocal local_near_count, local_scaled
            sampled_budget_target = (
                float(budget_target)
                if budget_target is not None
                else _sample_budget_target_in_band(
                    lower_budget=scenario_budget_lower,
                    upper_budget=scenario_budget_upper,
                    budget_zone_preference=budget_zone_preference,
                    near_opt=near_opt,
                    rng=local_rng,
                )
            )
            projected = _project_vector_to_budget(vec, sampled_budget_target, bounds, coeffs, baseline_budget)
            if projected is None:
                projected = _project_vector_to_budget_band(
                    vec,
                    scenario_budget_lower,
                    scenario_budget_upper,
                    bounds,
                    coeffs,
                    baseline_budget,
                )
            if projected is None:
                return False
            projected = _quantize_vector_to_market_budget_steps(projected, market_data, regions, limits_map, bounds)
            if projected is None:
                return False
            if not _is_vector_feasible_in_budget_band(
                projected,
                scenario_budget_lower,
                scenario_budget_upper,
                bounds,
                coeffs,
                baseline_budget,
            ):
                return False
            if not _is_reach_share_targets_satisfied(
                projected,
                market_data,
                regions,
                ctx.get("overrides", {}),
                tolerance_pct=REACH_SHARE_TARGET_TOLERANCE_PCT,
            ):
                return False
            key = _vector_key(projected)
            if key in local_exact_keys:
                return False
            scaled = (projected - low) / span
            if local_scaled.shape[0] > 0:
                dists = np.linalg.norm(local_scaled - scaled, axis=1)
                if float(np.min(dists)) < worker_min_distance:
                    return False
            evaluated = _evaluate_solution_vector(
                projected,
                market_data,
                regions,
                limits_map,
                region_prices,
                overrides=ctx.get("overrides", {}),
            )
            local_accepted.append(
                {
                    "scenario_index": 0,
                    "scenario_id": "",
                    "family": fam.capitalize(),
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
                    "_vector_key": key,
                }
            )
            local_scaled = np.vstack((local_scaled, scaled.reshape(1, -1)))
            local_exact_keys.add(key)
            if near_opt:
                local_near_count += 1
            return True

        while len(local_accepted) < worker_target_count and local_near_count < near_target_count and local_attempts < SCENARIO_MAX_ATTEMPTS:
            if timed_out():
                worker_timeout_hit = True
                break
            local_attempts += 1
            candidate = _sample_candidate_vector(seeds[fam], fam, True, bounds, regions, params, local_rng)
            local_try_accept_candidate(candidate, seed_source=f"near_{fam}_seed", near_opt=True)

        while len(local_accepted) < worker_target_count and local_attempts < SCENARIO_MAX_ATTEMPTS:
            if timed_out():
                worker_timeout_hit = True
                break
            local_attempts += 1
            candidate = _sample_candidate_vector(seeds[fam], fam, False, bounds, regions, params, local_rng)
            local_try_accept_candidate(candidate, seed_source=f"{fam}_strategy", near_opt=False)

        if len(local_accepted) < target_count and not worker_timeout_hit:
            original_min_distance = float(worker_min_distance)
            for relaxed_min_distance in (
                max(0.0, original_min_distance * 0.5),
                max(0.0, original_min_distance * 0.25),
                max(0.0, original_min_distance * 0.1),
                0.0,
            ):
                relaxed_min_distance = float(round(relaxed_min_distance, 6))
                if relaxed_min_distance >= worker_min_distance:
                    continue
                worker_min_distance = relaxed_min_distance
                local_notes.append(
                    f"{fam.capitalize()} family relaxed diversity threshold from {original_min_distance:.4f} to {relaxed_min_distance:.4f}."
                )
                local_try_accept_candidate(seeds[fam], seed_source=f"{fam}_seed_relaxed", near_opt=False, budget_target=seed_budget)
                relax_attempts = 0
                relax_max_attempts = max(1200, SCENARIO_MAX_ATTEMPTS // max(3, len(active_families)))
                while len(local_accepted) < worker_target_count and relax_attempts < relax_max_attempts:
                    if timed_out():
                        worker_timeout_hit = True
                        break
                    relax_attempts += 1
                    local_attempts += 1
                    candidate = _sample_candidate_vector(seeds[fam], fam, False, bounds, regions, params, local_rng)
                    local_try_accept_candidate(candidate, seed_source=f"{fam}_relaxed", near_opt=False)
                if worker_timeout_hit or len(local_accepted) >= worker_target_count:
                    break

        return {
            "family": fam,
            "scenarios": local_accepted,
            "near_count": local_near_count,
            "attempts": local_attempts,
            "timeout_hit": worker_timeout_hit,
            "notes": local_notes,
        }

    set_progress(32, f"Generating {len(active_families)} scenario families in parallel...")
    family_batches: list[dict[str, Any]] = []
    max_workers = max(1, min(len(active_families), 6))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(generate_family_batch, fam, family_targets.get(fam, 0), family_near_targets.get(fam, 0)): fam
            for fam in active_families
            if family_targets.get(fam, 0) > 0
        }
        completed_families = 0
        for future in concurrent.futures.as_completed(future_map):
            family_batches.append(future.result())
            completed_families += 1
            set_progress(
                32 + int(min(28, 28 * completed_families / max(1, len(future_map)))),
                f"Generating {len(active_families)} scenario families in parallel...",
            )

    family_batches.sort(key=lambda batch: active_families.index(batch["family"]))
    merged_exact_keys: set[tuple[float, ...]] = set()
    for batch in family_batches:
        near_count += int(batch.get("near_count", 0) or 0)
        attempts += int(batch.get("attempts", 0) or 0)
        timeout_hit = timeout_hit or bool(batch.get("timeout_hit"))
        notes.extend(list(batch.get("notes", []) or []))
        for scenario in batch.get("scenarios", []):
            key = tuple(scenario.get("_vector_key", ()))
            if key in merged_exact_keys:
                continue
            merged_exact_keys.add(key)
            accepted.append(scenario)

    accepted = accepted[:target_total]
    if near_count < target_near:
        notes.append(f"Near-opt scenario target reduced by feasibility/diversity checks: {near_count} accepted out of requested {target_near}.")
    notes.append(f"Parallel family generation used {len(active_families)} Monte Carlo worker(s).")

    if len(accepted) < target_total:
        notes.append(
            f"Returned {len(accepted)} feasible unique scenarios (requested up to {target_total}); feasible space is narrow under current budget + market constraints."
        )
    if len(accepted) <= 1:
        notes.append(
            "AI strategy guidance was applied, but hard feasibility constraints dominate this run. Loosen market bounds or align target budget to feasible range for more options."
        )
    if timeout_hit:
        notes.append(f"Generation stopped at runtime cap ({runtime_limit}s) to keep UI responsive.")

    family_sequence: dict[str, int] = {}
    label_prefix = str(scenario_label_prefix or "").strip()
    for idx, scenario in enumerate(accepted, start=1):
        scenario["scenario_index"] = idx
        family_label = str(scenario.get("family") or "Scenario").strip() or "Scenario"
        family_key = family_label.lower()
        family_sequence[family_key] = family_sequence.get(family_key, 0) + 1
        family_scenario_id = f"{family_label} {family_sequence[family_key]}"
        scenario["scenario_id"] = f"{label_prefix} / {family_scenario_id}" if label_prefix else family_scenario_id
        scenario.pop("_vector_key", None)

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
        "budget_tolerance": _budget_epsilon(scenario_budget_upper),
        "requested_scenario_budget_lower": round(float(requested_band_lower), 4),
        "requested_scenario_budget_upper": round(float(requested_band_upper), 4),
        "effective_scenario_budget_lower": round(float(scenario_budget_lower), 4),
        "effective_scenario_budget_upper": round(float(scenario_budget_upper), 4),
        "budget_band_lower": round(float(scenario_budget_lower), 4),
        "budget_band_upper": round(float(scenario_budget_upper), 4),
        "budget_band_lower_ratio": round(float(SCENARIO_BUDGET_BAND_LOWER_RATIO), 4),
        "budget_zone_preference": budget_zone_preference,
        "runtime_seconds": round(float(time.time() - started_at), 2),
        "runtime_cap_seconds": runtime_limit,
        "selected_brand": ctx["brand"],
        "selected_markets": regions,
        "requested_target_budget": round(requested_target_budget, 4),
        "target_budget": round(target_budget, 4),
        "feasible_budget_min": round(feasible_budget_min, 4),
        "feasible_budget_max": round(feasible_budget_max, 4),
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
        _update_scenario_job(job_id, progress=15, message="Resolving scenario intent...")
        if payload.resolved_intent is not None:
            resolved_intent = ScenarioResolvedIntent.model_validate(payload.resolved_intent).model_dump(mode="json")
            intent_notes = list(resolved_intent.get("explanation_notes", []))
        else:
            intent_resolution = _resolve_scenario_intent_payload(
                ScenarioIntentResolveRequest(
                    selected_brand=payload.selected_brand,
                    selected_markets=payload.selected_markets,
                    budget_increase_type=payload.budget_increase_type,
                    budget_increase_value=payload.budget_increase_value,
                    market_overrides=payload.market_overrides,
                    intent_prompt=payload.intent_prompt,
                ),
                clarification_round=2,
                clarification_answers={},
            )
            resolved_intent = dict(intent_resolution.get("resolved_intent") or {})
            if not resolved_intent:
                raise HTTPException(status_code=400, detail="Scenario intent could not be resolved for generation.")
            intent_notes = list(intent_resolution.get("notes", []))

        _update_scenario_job(job_id, progress=22, message="Building deterministic generation biases...")
        strategy, strategy_notes = _build_generation_strategy_from_resolved_intent(resolved_intent, ctx)
        if payload.strategy_override:
            strategy = _merge_strategy_override(strategy, payload.strategy_override)
            strategy_notes = [*strategy_notes, "Scenario strategy override was applied to bias family exploration toward the approved market plan."]

        def set_progress(progress: int, message: str) -> None:
            _update_scenario_job(job_id, progress=max(0, min(99, int(progress))), message=message)

        scenarios, artifacts = _generate_scenarios_for_context(
            ctx,
            strategy,
            set_progress,
            target_total_requested=payload.target_scenarios,
            max_runtime_seconds=payload.max_runtime_seconds,
            requested_scenario_budget_lower=payload.scenario_budget_lower,
            requested_scenario_budget_upper=payload.scenario_budget_upper,
            scenario_label_prefix=payload.scenario_label_prefix,
        )
        result_payload = {
            "summary": artifacts["summary"],
            "anchors": artifacts["anchors"],
            "resolved_intent": resolved_intent,
            "strategy_used": strategy,
            "generation_notes": [*intent_notes, *strategy_notes, *artifacts["notes"]],
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
    min_budget_utilized_pct: float | None,
    max_budget_utilized_pct: float | None,
    reach_share_market: str | None,
    reach_share_direction: str | None,
    min_reach_share_delta_pp: float | None,
    reach_share_market_2: str | None,
    reach_share_direction_2: str | None,
    min_reach_share_delta_pp_2: float | None,
    target_budget: float | None,
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
    if min_budget_utilized_pct is not None or max_budget_utilized_pct is not None:
        tb = float(_finite(target_budget, 0.0))
        def _util_pct(s: dict[str, Any]) -> float:
            if tb <= 1e-12:
                return 0.0
            return float(s.get("total_new_spend", 0.0)) / tb * 100.0
        if min_budget_utilized_pct is not None:
            items = [s for s in items if _util_pct(s) >= float(min_budget_utilized_pct)]
        if max_budget_utilized_pct is not None:
            items = [s for s in items if _util_pct(s) <= float(max_budget_utilized_pct)]
    def _apply_reach_share_filter(
        source_items: list[dict[str, Any]],
        market: str | None,
        direction_raw: str | None,
        min_delta_raw: float | None,
    ) -> list[dict[str, Any]]:
        if not market:
            return source_items
        market_keys = [
            part.strip().lower()
            for part in str(market).split(",")
            if str(part).strip()
        ]
        if not market_keys:
            return source_items
        direction = str(direction_raw or "").strip().lower()
        min_delta = abs(float(_finite(min_delta_raw, 0.0)))

        def _reach_share_delta_pp(s: dict[str, Any], market_key: str) -> float | None:
            for row in s.get("markets", []) or []:
                if str(row.get("market", "")).strip().lower() != market_key:
                    continue
                old_share = float(_finite(row.get("fy25_reach_share_pct"), np.nan))
                new_share = float(_finite(row.get("new_reach_share_pct"), np.nan))
                if np.isfinite(old_share) and np.isfinite(new_share):
                    return new_share - old_share
                return None
            return None

        def _matches(s: dict[str, Any], market_key: str) -> bool:
            delta = _reach_share_delta_pp(s, market_key)
            if direction in {"higher", "increase", "inc", "up"}:
                return delta is not None and delta >= min_delta
            if direction in {"lower", "decrease", "dec", "down"}:
                return delta is not None and delta <= -min_delta
            return delta is not None and abs(delta) >= min_delta

        return [s for s in source_items if all(_matches(s, market_key) for market_key in market_keys)]

    items = _apply_reach_share_filter(items, reach_share_market, reach_share_direction, min_reach_share_delta_pp)
    items = _apply_reach_share_filter(items, reach_share_market_2, reach_share_direction_2, min_reach_share_delta_pp_2)

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


def service_resolve_scenario_intent(payload: ScenarioIntentResolveRequest) -> dict[str, Any]:
    return _resolve_scenario_intent_payload(payload, clarification_round=0, clarification_answers={})


def service_clarify_scenario_intent(payload: ScenarioIntentClarifyRequest) -> dict[str, Any]:
    return _resolve_scenario_intent_payload(
        ScenarioIntentResolveRequest(
            selected_brand=payload.selected_brand,
            selected_markets=payload.selected_markets,
            budget_increase_type=payload.budget_increase_type,
            budget_increase_value=payload.budget_increase_value,
            market_overrides=payload.market_overrides,
            intent_prompt=payload.intent_prompt,
        ),
        clarification_round=max(1, int(payload.clarification_round)),
        clarification_answers=dict(payload.clarification_answers or {}),
    )


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
    min_budget_utilized_pct: float | None = None,
    max_budget_utilized_pct: float | None = None,
    reach_share_market: str | None = None,
    reach_share_direction: str | None = None,
    min_reach_share_delta_pp: float | None = None,
    reach_share_market_2: str | None = None,
    reach_share_direction_2: str | None = None,
    min_reach_share_delta_pp_2: float | None = None,
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
        min_budget_utilized_pct=min_budget_utilized_pct,
        max_budget_utilized_pct=max_budget_utilized_pct,
        reach_share_market=reach_share_market,
        reach_share_direction=reach_share_direction,
        min_reach_share_delta_pp=min_reach_share_delta_pp,
        reach_share_market_2=reach_share_market_2,
        reach_share_direction_2=reach_share_direction_2,
        min_reach_share_delta_pp_2=min_reach_share_delta_pp_2,
        target_budget=float((result.get("summary") or {}).get("target_budget", 0.0)),
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


def _call_gemini_plain_text(prompt: str, max_tokens: int = 650) -> tuple[str | None, list[str]]:
    notes: list[str] = []
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        notes.append("Gemini API key missing; fallback summary applied.")
        return None, notes
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.9,
            "maxOutputTokens": int(max(256, min(max_tokens, 1200))),
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
            parts = candidates[0].get("content", {}).get("parts", []) if candidates and isinstance(candidates, list) else []
            text = str(parts[0].get("text", "")).strip() if parts and isinstance(parts, list) else ""
            if text:
                return text, notes
            notes.append("Gemini returned empty summary; fallback summary applied.")
            return None, notes
        except urlerror.HTTPError as exc:
            if exc.code == 429 and attempt < retries:
                time.sleep(0.8 * (2 ** attempt))
                continue
            if exc.code == 429:
                notes.append("Gemini rate limit reached (HTTP 429); fallback summary applied.")
            elif exc.code == 404:
                notes.append("Gemini model not found (HTTP 404); fallback summary applied.")
            elif exc.code == 400:
                notes.append("Gemini request invalid (HTTP 400); fallback summary applied.")
            else:
                notes.append(f"Gemini HTTP error ({exc.code}); fallback summary applied.")
            return None, notes
        except Exception:
            if attempt < retries:
                time.sleep(0.8 * (2 ** attempt))
            else:
                notes.append("Gemini request failed; fallback summary applied.")
    return None, notes


def _build_scenario_market_deltas(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    old_total_spend = sum(max(0.0, float(_finite(m.get("old_total_spend", 0.0), 0.0))) for m in markets)
    out: list[dict[str, Any]] = []
    for row in markets:
        market = str(row.get("market", "")).strip()
        if not market:
            continue
        old_sp = max(0.0, float(_finite(row.get("old_total_spend", 0.0), 0.0)))
        new_share = max(0.0, float(_finite(row.get("new_budget_share", 0.0), 0.0))) * 100.0
        old_share = (old_sp / old_total_spend * 100.0) if old_total_spend > 1e-9 else 0.0
        budget_delta = new_share - old_share
        old_tv = float(_finite(row.get("fy25_tv_share", row.get("tv_split", 0.0)), 0.0)) * 100.0
        new_tv = float(_finite(row.get("tv_split", 0.0), 0.0)) * 100.0
        old_dg = float(_finite(row.get("fy25_digital_share", row.get("digital_split", 0.0)), 0.0)) * 100.0
        new_dg = float(_finite(row.get("digital_split", 0.0), 0.0)) * 100.0
        tv_delta = new_tv - old_tv
        dg_delta = new_dg - old_dg
        out.append(
            {
                "market": market,
                "old_budget_share_pct": round(old_share, 2),
                "new_budget_share_pct": round(new_share, 2),
                "budget_share_change_pct": round(budget_delta, 2),
                "old_tv_split_pct": round(old_tv, 2),
                "new_tv_split_pct": round(new_tv, 2),
                "tv_split_change_pct": round(tv_delta, 2),
                "old_digital_split_pct": round(old_dg, 2),
                "new_digital_split_pct": round(new_dg, 2),
                "digital_split_change_pct": round(dg_delta, 2),
            }
        )
    out.sort(key=lambda r: abs(float(r.get("budget_share_change_pct", 0.0))), reverse=True)
    return out


def _fallback_scenario_summary_text(payload: ScenarioSummaryRequest, deltas: list[dict[str, Any]]) -> str:
    inc = [d["market"] for d in deltas if float(d.get("budget_share_change_pct", 0.0)) > 0][:4]
    dec = [d["market"] for d in deltas if float(d.get("budget_share_change_pct", 0.0)) < 0][:4]
    tv_up = [d["market"] for d in deltas if float(d.get("tv_split_change_pct", 0.0)) > 0][:3]
    dg_up = [d["market"] for d in deltas if float(d.get("digital_split_change_pct", 0.0)) > 0][:3]
    util_pct = (payload.total_new_spend / payload.target_budget * 100.0) if payload.target_budget > 1e-9 else 0.0
    return (
        f"Scenario {payload.scenario_id} summary for {payload.selected_brand}: "
        f"Revenue uplift is {payload.revenue_uplift_pct:+.2f}% with budget utilized at {util_pct:.1f}% of target. "
        f"Budget was increased mainly in {', '.join(inc) if inc else 'no major markets'} and reduced in {', '.join(dec) if dec else 'no major markets'}. "
        f"TV mix increased in {', '.join(tv_up) if tv_up else 'limited markets'}, while Digital mix increased in {', '.join(dg_up) if dg_up else 'limited markets'}. "
        "Use this as a scenario-level readout of post-optimization state TV/Digital allocation changes."
    )


def service_scenario_summary(payload: ScenarioSummaryRequest) -> dict[str, Any]:
    markets = payload.markets or []
    if not markets:
        raise HTTPException(status_code=400, detail="Scenario market rows are required for summary generation.")
    deltas = payload.state_change_rows or _build_scenario_market_deltas(markets)
    compact_rows = deltas[:20]
    util_pct = (payload.total_new_spend / payload.target_budget * 100.0) if payload.target_budget > 1e-9 else 0.0
    increases = [r for r in deltas if float(_finite(r.get("budget_share_change_pct", 0.0), 0.0)) > 0]
    decreases = [r for r in deltas if float(_finite(r.get("budget_share_change_pct", 0.0), 0.0)) < 0]
    tv_up = [r for r in deltas if float(_finite(r.get("tv_split_change_pct", 0.0), 0.0)) > 0]
    tv_down = [r for r in deltas if float(_finite(r.get("tv_split_change_pct", 0.0), 0.0)) < 0]
    dg_up = [r for r in deltas if float(_finite(r.get("digital_split_change_pct", 0.0), 0.0)) > 0]
    dg_down = [r for r in deltas if float(_finite(r.get("digital_split_change_pct", 0.0), 0.0)) < 0]
    prompt = (
        "You are a senior MMM strategy analyst. Analyze ONLY post-optimization state-level changes.\n"
        "Write an intelligent business summary in 7-10 crisp lines.\n"
        "Do not use markdown tables. Avoid generic statements. Mention concrete states and directional changes.\n"
        "Output sections in plain text:\n"
        "1) What changed most\n"
        "2) Budget reallocation readout (increase/decrease states)\n"
        "3) Channel mix readout (TV up/down, Digital up/down states)\n"
        "4) Recommended execution focus\n"
        "5) Risk watchouts\n"
        f"Brand: {payload.selected_brand}\n"
        f"Scenario ID: {payload.scenario_id}\n"
        f"Revenue uplift %: {payload.revenue_uplift_pct:.2f}\n"
        f"Budget utilized % of target: {util_pct:.2f}\n"
        f"User focus: {str(payload.user_prompt or '').strip()}\n"
        f"Budget share increased states: {json.dumps([r.get('market') for r in increases[:8]], ensure_ascii=True)}\n"
        f"Budget share decreased states: {json.dumps([r.get('market') for r in decreases[:8]], ensure_ascii=True)}\n"
        f"TV share up states: {json.dumps([r.get('market') for r in tv_up[:8]], ensure_ascii=True)}\n"
        f"TV share down states: {json.dumps([r.get('market') for r in tv_down[:8]], ensure_ascii=True)}\n"
        f"Digital share up states: {json.dumps([r.get('market') for r in dg_up[:8]], ensure_ascii=True)}\n"
        f"Digital share down states: {json.dumps([r.get('market') for r in dg_down[:8]], ensure_ascii=True)}\n"
        f"State change snapshot: {json.dumps(compact_rows, ensure_ascii=True)}\n"
    )
    text, notes = _call_gemini_plain_text(prompt, max_tokens=700)
    provider = "gemini"
    if not text:
        provider = "fallback"
        text = _fallback_scenario_summary_text(payload, deltas)
    return {
        "status": "ok",
        "provider": provider,
        "scenario_id": payload.scenario_id,
        "summary_text": _clip_text(str(text).strip(), 2400),
        "notes": notes,
    }


def service_health() -> dict[str, str]:
    return {"status": "ok"}


def service_auto_config() -> dict:
    out = _build_auto_config()
    # Fire-and-forget warmup so first-run insights become fast without blocking auto-config response.
    trigger_insights_cache_warmup()
    return out


def service_insights_cache_status() -> dict[str, Any]:
    return _insights_warmup_status_snapshot()


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
    cache_key = _insights_payload_cache_key("s_curves_auto", payload)
    cached = _get_cached_insights_response(cache_key)
    if cached is not None:
        return cached
    try:
        result = _build_s_curves(payload)
        _set_cached_insights_response(cache_key, result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"S-curve generation failed: {exc}") from exc


def service_contributions_auto(payload: ContributionAutoRequest) -> dict:
    cache_key = _insights_payload_cache_key("contributions_auto", payload)
    cached = _get_cached_insights_response(cache_key)
    if cached is not None:
        return cached
    try:
        result = _build_contribution_insights(payload)
        _set_cached_insights_response(cache_key, result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Contribution insights failed: {exc}") from exc


def service_yoy_growth_auto(payload: YoyGrowthRequest) -> dict:
    cache_key = _insights_payload_cache_key("yoy_growth_auto", payload)
    cached = _get_cached_insights_response(cache_key)
    if cached is not None:
        return cached
    try:
        result = _build_yoy_growth_insights(payload)
        _set_cached_insights_response(cache_key, result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"YoY growth insights failed: {exc}") from exc


def service_driver_analysis_auto(payload: DriverAnalysisRequest) -> dict:
    cache_key = _insights_payload_cache_key("driver_analysis_auto", payload)
    cached = _get_cached_insights_response(cache_key)
    if cached is not None:
        return cached
    try:
        result = _build_driver_analysis(payload)
        _set_cached_insights_response(cache_key, result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Driver analysis failed: {exc}") from exc


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
