from __future__ import annotations

import json
import math
import os
import re
import statistics
import time
from typing import Any, Literal
from urllib import error as urlerror
from urllib import request as urlrequest


from pydantic import BaseModel, Field

from app.services.engine import (
    OptimizeAutoRequest,
    ScenarioResolvedIntent,
    _load_optimization_context,
    _resolve_aggressiveness_level,
    _resolve_objective_preference,
    _resolve_practicality_level,
    _sanitize_strategy_controls,
)

ALLOWED_METRICS: dict[str, dict[str, str]] = {
    "market_share": {"label": "Market Share", "kind": "level"},
    "category_salience": {"label": "Category Salience", "kind": "level"},
    "brand_salience": {"label": "Brand Salience", "kind": "level"},
    "change_in_market_share": {"label": "Change In Market Share", "kind": "trend"},
    "change_in_brand_equity": {"label": "Change In Brand Equity", "kind": "trend"},
    # Derived fields — computed from raw columns at row-sanitization time
    "category_brand_gap": {"label": "Category−Brand Salience Gap", "kind": "level"},
    "brand_category_gap": {"label": "Brand−Category Salience Gap", "kind": "level"},
    "brand_share_ratio": {"label": "Brand/Category Salience Ratio", "kind": "level"},
}

METRIC_ALIASES: dict[str, str] = {
    "market share change": "change_in_market_share",
    "change in market share": "change_in_market_share",
    "losing market share": "change_in_market_share",
    "market share": "market_share",
    "share": "market_share",
    "category size": "category_salience",
    "category demand": "category_salience",
    "category salience": "category_salience",
    "brand presence": "brand_salience",
    "brand salience": "brand_salience",
    "brand equity change": "change_in_brand_equity",
    "change in brand equity": "change_in_brand_equity",
    "brand equity": "change_in_brand_equity",
    # Derived metric aliases
    "category brand gap": "category_brand_gap",
    "category minus brand": "category_brand_gap",
    "salience gap": "category_brand_gap",
    "gap between category and brand": "category_brand_gap",
    "brand category gap": "brand_category_gap",
    "brand minus category": "brand_category_gap",
    "brand salience ratio": "brand_share_ratio",
    "brand to category ratio": "brand_share_ratio",
    "salience ratio": "brand_share_ratio",
}

COMPARISON_WORDS = ("below", "above", "greater than", "less than", "higher than", "lower than")
TREND_DOWN_WORDS = ("reduced", "reduce", "declined", "decline", "decreased", "decrease", "falling", "fallen", "down", "losing")
TREND_UP_WORDS = ("increased", "increase", "growing", "grown", "improving", "improved", "up", "gaining")


class ScenarioIntentDebugRequest(BaseModel):
    selected_brand: str
    selected_markets: list[str] = Field(default_factory=list)
    budget_increase_type: Literal["percentage", "absolute"] = "percentage"
    budget_increase_value: float = 5.0
    market_overrides: dict[str, dict[str, float]] = Field(default_factory=dict)
    intent_prompt: str = ""
    user_feedback: str = ""
    current_interpretation: dict[str, Any] | None = None
    review_mode: Literal["initial", "revise"] = "initial"


class ScenarioIntentApprovalEvaluationRequest(BaseModel):
    selected_brand: str
    selected_markets: list[str] = Field(default_factory=list)
    budget_increase_type: Literal["percentage", "absolute"] = "percentage"
    budget_increase_value: float = 5.0
    market_overrides: dict[str, dict[str, float]] = Field(default_factory=dict)
    intent_prompt: str = ""
    approved_interpretation: dict[str, Any] = Field(default_factory=dict)


class ScenarioIntentHandoffRequest(BaseModel):
    selected_brand: str
    selected_markets: list[str] = Field(default_factory=list)
    budget_increase_type: Literal["percentage", "absolute"] = "percentage"
    budget_increase_value: float = 5.0
    market_overrides: dict[str, dict[str, float]] = Field(default_factory=dict)
    intent_prompt: str = ""
    approved_interpretation: dict[str, Any] = Field(default_factory=dict)
    scenario_range_lower_pct: float = 80.0
    scenario_range_upper_pct: float = 120.0


def _extract_outer_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    stripped = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", stripped, re.IGNORECASE)
    if fence_match:
        stripped = fence_match.group(1).strip()
    candidates = [stripped]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        candidates.append(stripped[start : end + 1])
    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        for index, ch in enumerate(candidate):
            if ch != "{":
                continue
            try:
                parsed, _offset = decoder.raw_decode(candidate[index:])
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue
    return None


def _safe_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except Exception:
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _resolve_metric_alias(text: str) -> str | None:
    # Normalize underscores so e.g. "category_size" matches alias "category size"
    lowered = text.lower().replace("_", " ")
    for alias, metric_key in sorted(METRIC_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in lowered:
            return metric_key
    return None


def _resolve_metric_alias_nearest(text: str, side: Literal["left", "right"]) -> str | None:
    lowered = text.lower()
    matches: list[tuple[int, int, str]] = []
    for alias, metric_key in METRIC_ALIASES.items():
        for match in re.finditer(re.escape(alias), lowered):
            matches.append((match.start(), match.end(), metric_key))
    if not matches:
        return None
    if side == "left":
        matches.sort(key=lambda item: item[1], reverse=True)
    else:
        matches.sort(key=lambda item: item[0])
    return matches[0][2]


def _sanitize_market_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        market = str(row.get("market", "")).strip()
        if not market:
            continue
        cat = _safe_float(row.get("category_salience"))
        brand = _safe_float(row.get("brand_salience"))
        out.append(
            {
                "market": market,
                "category_salience": cat,
                "brand_salience": brand,
                "market_share": _safe_float(row.get("market_share")),
                "change_in_market_share": _safe_float(row.get("change_in_market_share")),
                "change_in_brand_equity": _safe_float(row.get("change_in_brand_equity")),
                "overall_media_elasticity": _safe_float(row.get("overall_media_elasticity")),
                "tv_reach_elasticity": _safe_float(row.get("tv_reach_elasticity")),
                "digital_reach_elasticity": _safe_float(row.get("digital_reach_elasticity")),
                "avg_cpr": _safe_float(row.get("avg_cpr")),
                "responsiveness_label": str(row.get("responsiveness_label") or "Unknown"),
                "avg_cpr_band": str(row.get("avg_cpr_band") or "unknown"),
                "brand_salience_band": str(row.get("brand_salience_band") or "unknown"),
                # Derived fields computed on the fly
                "category_brand_gap": (cat - brand) if cat is not None and brand is not None else None,
                "brand_category_gap": (brand - cat) if cat is not None and brand is not None else None,
                "brand_share_ratio": (brand / cat) if cat is not None and brand is not None and cat != 0 else None,
            }
        )
    return out


def _build_level_threshold(rows: list[dict[str, Any]], metric_key: str) -> float | None:
    values = [row[metric_key] for row in rows if _safe_float(row.get(metric_key)) is not None]
    if len(values) < 2:
        return None
    return statistics.median(sorted(float(v) for v in values))


def _infer_top_n(prompt: str) -> int | None:
    match = re.search(r"\btop\s+(\d+)\b", prompt.lower())
    return int(match.group(1)) if match else None


def _infer_metric_mentions(prompt: str) -> list[str]:
    lowered = prompt.lower()
    found: list[tuple[int, str]] = []
    for alias, metric_key in sorted(METRIC_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        match = re.search(re.escape(alias), lowered)
        if match:
            found.append((match.start(), metric_key))
    found.sort(key=lambda item: item[0])
    deduped: list[str] = []
    for _index, metric_key in found:
        if metric_key not in deduped:
            deduped.append(metric_key)
    return deduped


def _infer_filters_from_prompt(prompt: str) -> list[dict[str, Any]]:
    prompt_lower = prompt.lower()
    metrics = _infer_metric_mentions(prompt)
    filters: list[dict[str, Any]] = []
    if any(word in prompt_lower for word in TREND_DOWN_WORDS):
        metric = "change_in_market_share" if "market share" in prompt_lower or "share" in prompt_lower else "change_in_brand_equity" if "brand equity" in prompt_lower else None
        if metric:
            filters.append(
                {
                    "metric_key": metric,
                    "metric_label": ALLOWED_METRICS[metric]["label"],
                    "kind": "trend",
                    "operator": "<",
                    "value": 0,
                    "source_text": prompt,
                }
            )
            return filters
    if any(word in prompt_lower for word in TREND_UP_WORDS):
        metric = "change_in_market_share" if "market share" in prompt_lower or "share" in prompt_lower else "change_in_brand_equity" if "brand equity" in prompt_lower else None
        if metric:
            filters.append(
                {
                    "metric_key": metric,
                    "metric_label": ALLOWED_METRICS[metric]["label"],
                    "kind": "trend",
                    "operator": ">",
                    "value": 0,
                    "source_text": prompt,
                }
            )
            return filters
    if not metrics or _infer_top_n(prompt) or any(word in prompt_lower for word in COMPARISON_WORDS):
        return filters
    metric = metrics[0]
    if ALLOWED_METRICS[metric]["kind"] == "level":
        if "low" in prompt_lower or "weak" in prompt_lower or "under" in prompt_lower:
            filters.append(
                {
                    "metric_key": metric,
                    "metric_label": ALLOWED_METRICS[metric]["label"],
                    "kind": "band",
                    "operator": "<=",
                    "value": "median",
                    "source_text": prompt,
                }
            )
        elif "high" in prompt_lower or "strong" in prompt_lower:
            filters.append(
                {
                    "metric_key": metric,
                    "metric_label": ALLOWED_METRICS[metric]["label"],
                    "kind": "band",
                    "operator": ">=",
                    "value": "median",
                    "source_text": prompt,
                }
            )
    return filters


def _infer_comparisons_from_prompt(prompt: str) -> list[dict[str, Any]]:
    prompt_lower = prompt.lower()
    if not any(word in prompt_lower for word in COMPARISON_WORDS):
        return []
    operator = "<"
    direction = "below"
    keyword = next((word for word in ("below", "less than", "lower than", "above", "greater than", "higher than") if word in prompt_lower), "")
    if not keyword:
        return []
    if keyword in {"above", "greater than", "higher than"}:
        operator = ">"
        direction = "above"
    left_text, right_text = prompt_lower.split(keyword, 1)
    left_metric = _resolve_metric_alias_nearest(left_text, "left")
    right_metric = _resolve_metric_alias_nearest(right_text, "right")
    if left_metric not in ALLOWED_METRICS or right_metric not in ALLOWED_METRICS:
        metrics = _infer_metric_mentions(prompt)
        if len(metrics) < 2:
            return []
        left_metric, right_metric = metrics[0], metrics[1]
    return [
        {
            "left_metric_key": left_metric,
            "left_metric_label": ALLOWED_METRICS[left_metric]["label"],
            "operator": operator,
            "direction": direction,
            "right_metric_key": right_metric,
            "right_metric_label": ALLOWED_METRICS[right_metric]["label"],
            "source_text": prompt,
        }
    ]


def _infer_rankings_from_prompt(prompt: str) -> list[dict[str, Any]]:
    top_n = _infer_top_n(prompt)
    metric_key = _resolve_metric_alias(prompt)
    if not top_n or metric_key not in ALLOWED_METRICS:
        return []
    # Don't infer a selection ranking if "top N" is preceded by an exclusion signal
    prompt_lower = prompt.lower()
    exclusion_signals = ("exclude", "don't include", "dont include", "do not include", "remove", "without")
    top_match = re.search(r"\btop\s+\d+\b", prompt_lower)
    if top_match:
        prefix = prompt_lower[: top_match.start()]
        if any(sig in prefix for sig in exclusion_signals):
            return []
    return [
        {
            "metric_key": metric_key,
            "metric_label": ALLOWED_METRICS[metric_key]["label"],
            "direction": "descending",
            "limit": top_n,
            "source_text": prompt,
        }
    ]


def _infer_exclusions_from_prompt(prompt: str, available_markets: list[str]) -> list[dict[str, Any]]:
    prompt_lower = prompt.lower()
    exclusion_signals = ("don't include", "dont include", "do not include", "exclude", "without", "remove")
    if not any(signal in prompt_lower for signal in exclusion_signals):
        return []
    exclusions: list[dict[str, Any]] = []
    for market in available_markets:
        market_lower = market.lower()
        if market_lower in prompt_lower:
            prefix = prompt_lower.split(market_lower, 1)[0]
            if any(signal in prefix for signal in exclusion_signals):
                exclusions.append({"market": market, "source_text": prompt})
    return exclusions


def _infer_exclude_ranking_from_prompt(prompt: str) -> list[dict[str, Any]]:
    prompt_lower = prompt.lower()
    exclusion_signals = ("exclude", "don't include", "dont include", "do not include", "remove", "without")
    if not any(sig in prompt_lower for sig in exclusion_signals):
        return []
    top_n = _infer_top_n(prompt)
    if not top_n:
        return []
    metric_key = _resolve_metric_alias(prompt)
    if metric_key not in ALLOWED_METRICS:
        return []
    return [
        {
            "metric_key": metric_key,
            "metric_label": ALLOWED_METRICS[metric_key]["label"],
            "direction": "descending",
            "limit": top_n,
            "source_text": prompt,
        }
    ]


def _infer_exclude_filter_from_prompt(prompt: str) -> list[dict[str, Any]]:
    prompt_lower = prompt.lower()
    exclusion_signals = ("exclude", "don't include", "dont include", "do not include", "remove", "without")
    if not any(sig in prompt_lower for sig in exclusion_signals):
        return []
    # Detect "market share above/greater than/over X%"
    pct_match = re.search(
        r"market\s*share\s*(?:is\s*)?(?:above|greater\s*than|more\s*than|over|>|>=)\s*(\d+(?:\.\d+)?)\s*%?",
        prompt_lower,
    )
    if pct_match:
        threshold = float(pct_match.group(1))
        return [
            {
                "metric_key": "market_share",
                "metric_label": "Market Share",
                "kind": "threshold",
                "operator": ">",
                "value": threshold,
                "source_text": prompt,
            }
        ]
    return []


def _normalize_filter_item(item: dict[str, Any], prompt: str) -> dict[str, Any] | None:
    metric_key = str(item.get("metric_key", "")).strip()
    if metric_key not in ALLOWED_METRICS:
        metric_key = _resolve_metric_alias(str(item.get("source_text") or prompt)) or metric_key
    if metric_key not in ALLOWED_METRICS:
        return None
    kind = str(item.get("kind") or item.get("interpretation_kind") or "").strip().lower()
    if kind not in {"trend", "band"}:
        kind = "trend" if ALLOWED_METRICS[metric_key]["kind"] == "trend" else "band"
    operator = str(item.get("operator") or "").strip()
    if kind == "trend" and operator not in {"<", ">"}:
        operator = "<" if any(word in str(item.get("source_text") or prompt).lower() for word in TREND_DOWN_WORDS) else ">"
    if kind == "band" and operator not in {"<=", ">="}:
        operator = "<="
    value = item.get("value", 0 if kind == "trend" else "median")
    return {
        "metric_key": metric_key,
        "metric_label": ALLOWED_METRICS[metric_key]["label"],
        "kind": kind,
        "operator": operator,
        "value": value,
        "source_text": item.get("source_text") or prompt,
    }


def _normalize_comparison_item(item: dict[str, Any], prompt: str) -> dict[str, Any] | None:
    has_signal = bool(str(item.get("left_metric_key", "")).strip()) or bool(str(item.get("right_metric_key", "")).strip()) or any(
        token in str(item.get("source_text") or "").lower() for token in COMPARISON_WORDS
    )
    if not has_signal:
        return None
    left_metric = str(item.get("left_metric_key", "")).strip()
    right_metric = str(item.get("right_metric_key", "")).strip()
    source_text = str(item.get("source_text") or prompt)
    inferred_from_text = _infer_comparisons_from_prompt(source_text or prompt)
    if inferred_from_text:
        inferred = inferred_from_text[0]
        left_metric = inferred["left_metric_key"]
        right_metric = inferred["right_metric_key"]
    else:
        mentioned = _infer_metric_mentions(source_text or prompt)
        if left_metric not in ALLOWED_METRICS and mentioned:
            left_metric = mentioned[0]
        if right_metric not in ALLOWED_METRICS and len(mentioned) > 1:
            right_metric = mentioned[1]
    if left_metric not in ALLOWED_METRICS or right_metric not in ALLOWED_METRICS:
        return None
    operator = str(item.get("operator") or "<").strip()
    if operator not in {"<", ">", "<=", ">="}:
        operator = "<"
    direction = "below" if operator in {"<", "<="} else "above"
    return {
        "left_metric_key": left_metric,
        "left_metric_label": ALLOWED_METRICS[left_metric]["label"],
        "operator": operator,
        "direction": direction,
        "right_metric_key": right_metric,
        "right_metric_label": ALLOWED_METRICS[right_metric]["label"],
        "source_text": source_text,
    }


def _normalize_ranking_item(item: dict[str, Any], prompt: str) -> dict[str, Any] | None:
    has_signal = bool(str(item.get("metric_key", "")).strip()) or bool(item.get("limit")) or "top" in str(item.get("source_text") or "").lower()
    if not has_signal:
        return None
    metric_key = str(item.get("metric_key", "")).strip()
    if metric_key not in ALLOWED_METRICS:
        metric_key = _resolve_metric_alias(str(item.get("source_text") or prompt)) or ""
    if metric_key not in ALLOWED_METRICS:
        return None
    limit = int(item.get("limit") or 0) or (_infer_top_n(prompt) or 0)
    if limit <= 0:
        return None
    direction = str(item.get("direction") or "descending").strip().lower()
    if direction not in {"ascending", "descending"}:
        direction = "descending"
    return {
        "metric_key": metric_key,
        "metric_label": ALLOWED_METRICS[metric_key]["label"],
        "direction": direction,
        "limit": limit,
        "source_text": item.get("source_text") or prompt,
    }


def _normalize_exclusion_item(item: dict[str, Any], available_markets: list[str], prompt: str) -> dict[str, Any] | None:
    market = str(item.get("market", "")).strip()
    if not market:
        return None
    for candidate in available_markets:
        if candidate.lower() == market.lower():
            return {"market": candidate, "source_text": item.get("source_text") or prompt}
    return None


def _normalize_step_item(step: dict[str, Any], available_markets: list[str], prompt: str, index: int) -> dict[str, Any] | None:
    step_type = str(step.get("step_type") or step.get("type") or "").strip().lower()
    if step_type not in {"filter", "comparison", "ranking", "exclude_markets", "exclude_filter", "exclude_ranking"}:
        return None
    base = {
        "id": str(step.get("id") or f"step_{index}").strip() or f"step_{index}",
        "step_type": step_type,
        "enabled": bool(step.get("enabled", True)),
        "source_text": step.get("source_text") or prompt,
    }
    if step_type == "filter":
        normalized = _normalize_filter_item(step, prompt)
        return None if normalized is None else {**base, **normalized}
    if step_type == "comparison":
        normalized = _normalize_comparison_item(step, prompt)
        return None if normalized is None else {**base, **normalized}
    if step_type == "ranking":
        normalized = _normalize_ranking_item(step, prompt)
        return None if normalized is None else {**base, **normalized}
    if step_type == "exclude_markets":
        normalized = _normalize_exclusion_item(step, available_markets, prompt)
        return None if normalized is None else {**base, **normalized}
    if step_type == "exclude_filter":
        metric_key = str(step.get("metric_key", "")).strip()
        if metric_key not in ALLOWED_METRICS:
            metric_key = _resolve_metric_alias(metric_key) or _resolve_metric_alias(str(step.get("source_text") or prompt)) or metric_key
        if metric_key not in ALLOWED_METRICS:
            return None
        return {
            **base,
            "metric_key": metric_key,
            "metric_label": ALLOWED_METRICS[metric_key]["label"],
            "kind": str(step.get("kind") or "threshold").strip(),
            "operator": str(step.get("operator") or ">").strip(),
            "value": step.get("value", 0),
        }
    if step_type == "exclude_ranking":
        metric_key = str(step.get("metric_key", "")).strip()
        if metric_key not in ALLOWED_METRICS:
            metric_key = _resolve_metric_alias(metric_key) or _resolve_metric_alias(str(step.get("source_text") or prompt)) or metric_key
        limit = int(step.get("limit") or 0)
        if metric_key not in ALLOWED_METRICS or limit <= 0:
            return None
        return {
            **base,
            "metric_key": metric_key,
            "metric_label": ALLOWED_METRICS[metric_key]["label"],
            "direction": str(step.get("direction") or "descending").strip().lower(),
            "limit": limit,
        }
    return None


def _normalize_execution_order(
    raw: Any,
    filters: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
    exclusions: list[dict[str, Any]],
) -> list[str]:
    valid = {"filters", "comparisons", "rankings", "exclusions"}
    out: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            key = str(item).strip().lower()
            if key in valid and key not in out:
                out.append(key)
    derived = []
    if comparisons:
        derived.append("comparisons")
    if filters:
        derived.append("filters")
    if rankings:
        derived.append("rankings")
    if exclusions:
        derived.append("exclusions")
    for key in derived:
        if key not in out:
            out.append(key)
    return out


def _steps_from_legacy_groups(
    filters: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
    exclusions: list[dict[str, Any]],
    execution_order: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    steps: list[dict[str, Any]] = []
    order: list[str] = []
    group_map = {
        "comparisons": ("comparison", comparisons),
        "filters": ("filter", filters),
        "rankings": ("ranking", rankings),
        "exclusions": ("exclude_markets", exclusions),
    }
    counter = 1
    for group_name in execution_order:
        step_type, items = group_map.get(group_name, ("", []))
        for item in items:
            step_id = f"step_{counter}"
            counter += 1
            steps.append(
                {
                    "id": step_id,
                    "step_type": step_type,
                    "enabled": True,
                    **item,
                }
            )
            order.append(step_id)
    return steps, order


def _execute_plan_steps(rows: list[dict[str, Any]], steps: list[dict[str, Any]], execution_order: list[str]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    notes: list[str] = []
    available_markets = [row["market"] for row in rows]
    current_scope = list(available_markets)
    step_map = {str(step.get("id")): step for step in steps}
    for step_id in execution_order:
        step = step_map.get(step_id)
        if not step or not bool(step.get("enabled", True)):
            continue
        step_type = str(step.get("step_type") or "").strip().lower()
        input_count = len(current_scope)
        if step_type == "comparison":
            matched, note = _match_comparison(rows, current_scope, step)
            step["input_count"] = input_count
            step["matched_markets"] = matched
            current_scope = matched
            notes.append(note)
        elif step_type == "filter":
            matched, note = _match_filter(rows, current_scope, step)
            step["input_count"] = input_count
            step["matched_markets"] = matched
            current_scope = matched
            notes.append(note)
        elif step_type == "ranking":
            matched, note = _apply_ranking(rows, current_scope or available_markets, step)
            step["input_count"] = input_count
            step["matched_markets"] = matched
            current_scope = matched
            notes.append(note)
        elif step_type == "exclude_markets":
            current_scope, note = _apply_exclusion(current_scope, step)
            step["input_count"] = input_count
            step["matched_markets"] = list(current_scope)
            notes.append(note)
        elif step_type == "exclude_filter":
            current_scope, note = _apply_exclude_filter(rows, current_scope, step)
            step["input_count"] = input_count
            step["matched_markets"] = list(current_scope)
            notes.append(note)
        elif step_type == "exclude_ranking":
            current_scope, note = _apply_exclude_ranking(rows, current_scope, step)
            step["input_count"] = input_count
            step["matched_markets"] = list(current_scope)
            notes.append(note)
    return steps, execution_order, current_scope



def _match_filter(rows: list[dict[str, Any]], market_scope: list[str], filt: dict[str, Any]) -> tuple[list[str], str]:
    metric_key = filt["metric_key"]
    scope = [row for row in rows if row["market"] in set(market_scope)]
    matched: list[str] = []
    if filt["kind"] == "trend":
        for row in scope:
            value = _safe_float(row.get(metric_key))
            if value is None:
                continue
            if filt["operator"] == "<" and value < 0:
                matched.append(row["market"])
            elif filt["operator"] == ">" and value > 0:
                matched.append(row["market"])
        return matched, f"Trend rule applied in code: `{metric_key} {filt['operator']} 0`."
    threshold = _build_level_threshold(scope, metric_key)
    if threshold is None:
        return [], f"Not enough numeric data to classify `{metric_key}` as high or low."
    for row in scope:
        value = _safe_float(row.get(metric_key))
        if value is None:
            continue
        if filt["operator"] == "<=" and value <= threshold:
            matched.append(row["market"])
        elif filt["operator"] == ">=" and value >= threshold:
            matched.append(row["market"])
    return matched, f"Band rule applied in code: `{metric_key} {filt['operator']} median`."


def _match_comparison(rows: list[dict[str, Any]], market_scope: list[str], comparison: dict[str, Any]) -> tuple[list[str], str]:
    scope = [row for row in rows if row["market"] in set(market_scope)]
    matched: list[str] = []
    left_key = comparison["left_metric_key"]
    right_key = comparison["right_metric_key"]
    operator = comparison["operator"]
    for row in scope:
        left_value = _safe_float(row.get(left_key))
        right_value = _safe_float(row.get(right_key))
        if left_value is None or right_value is None:
            continue
        if operator == "<=" and left_value <= right_value:
            matched.append(row["market"])
        elif operator == ">=" and left_value >= right_value:
            matched.append(row["market"])
        elif operator == "<" and left_value < right_value:
            matched.append(row["market"])
        elif operator == ">" and left_value > right_value:
            matched.append(row["market"])
    return matched, f"Comparison rule applied in code: `{left_key} {operator} {right_key}`."


def _apply_ranking(rows: list[dict[str, Any]], market_scope: list[str], ranking: dict[str, Any]) -> tuple[list[str], str]:
    scope = [row for row in rows if row["market"] in set(market_scope)]
    metric_key = ranking["metric_key"]
    items = [(row["market"], _safe_float(row.get(metric_key))) for row in scope]
    items = [(market, value) for market, value in items if value is not None]
    if not items:
        return [], f"No numeric values were available for ranking on `{metric_key}`."
    reverse = ranking["direction"] != "ascending"
    ordered = sorted(items, key=lambda item: item[1], reverse=reverse)
    selected = [market for market, _value in ordered[: int(ranking["limit"])]]
    return selected, f"Ranking applied in code: top {ranking['limit']} {'highest' if reverse else 'lowest'} markets by `{metric_key}`."


def _apply_exclusion(market_scope: list[str], exclusion: dict[str, Any]) -> tuple[list[str], str]:
    market = str(exclusion.get("market", "")).strip()
    remaining = [item for item in market_scope if item != market]
    return remaining, f"Exclusion applied in code: removed `{market}`."


def _apply_exclude_filter(rows: list[dict[str, Any]], market_scope: list[str], step: dict[str, Any]) -> tuple[list[str], str]:
    metric_key = step.get("metric_key", "")
    operator = str(step.get("operator") or ">").strip()
    kind = str(step.get("kind") or "threshold").strip()
    raw_value = step.get("value", 0)
    scope_set = set(market_scope)
    to_remove: set[str] = set()
    for row in rows:
        if row["market"] not in scope_set:
            continue
        val = _safe_float(row.get(metric_key))
        if val is None:
            continue
        threshold: float | None = None
        if kind == "threshold":
            threshold = _safe_float(raw_value)
        elif kind == "trend":
            threshold = 0.0
        elif kind == "band":
            threshold = _build_level_threshold([r for r in rows if r["market"] in scope_set], metric_key)
        if threshold is None:
            continue
        if operator in (">", ">=") and val > threshold:
            to_remove.add(row["market"])
        elif operator in ("<", "<=") and val < threshold:
            to_remove.add(row["market"])
    remaining = [m for m in market_scope if m not in to_remove]
    return remaining, f"Exclude-filter applied: removed {len(to_remove)} markets where `{metric_key} {operator} {raw_value}`."


def _apply_exclude_ranking(rows: list[dict[str, Any]], market_scope: list[str], step: dict[str, Any]) -> tuple[list[str], str]:
    metric_key = step.get("metric_key", "")
    limit = int(step.get("limit") or 0)
    direction = str(step.get("direction") or "descending").strip().lower()
    if limit <= 0:
        return market_scope, "Exclude-ranking skipped: no limit specified."
    # Rank across ALL available rows to find globally top-N markets, then remove from scope
    all_items = [(row["market"], _safe_float(row.get(metric_key))) for row in rows]
    all_items = [(m, v) for m, v in all_items if v is not None]
    reverse = direction != "ascending"
    ordered = sorted(all_items, key=lambda item: item[1], reverse=reverse)
    to_remove = {m for m, _v in ordered[:limit]}
    remaining = [m for m in market_scope if m not in to_remove]
    label = "highest" if reverse else "lowest"
    removed = [m for m in market_scope if m in to_remove]
    return remaining, f"Exclude-ranking applied: removed {removed} (top {limit} {label} by `{metric_key}` globally)."


def _market_passes_step_independently(row: dict[str, Any], step: dict[str, Any]) -> bool:
    """Return True if this market independently satisfies an include step (no scope dependency)."""
    step_type = str(step.get("step_type") or "").strip().lower()
    if step_type == "comparison":
        left_val = _safe_float(row.get(step.get("left_metric_key", "")))
        right_val = _safe_float(row.get(step.get("right_metric_key", "")))
        if left_val is None or right_val is None:
            return False
        op = step.get("operator", "<")
        if op == "<=": return left_val <= right_val
        if op == ">=": return left_val >= right_val
        if op == "<":  return left_val < right_val
        if op == ">":  return left_val > right_val
        return False
    if step_type == "filter":
        metric_key = step.get("metric_key", "")
        kind = str(step.get("kind") or "trend")
        op = str(step.get("operator") or "<")
        val = _safe_float(row.get(metric_key))
        if val is None:
            return False
        if kind == "trend":
            return (op == "<" and val < 0) or (op == ">" and val > 0)
        if kind in ("threshold", "band"):
            threshold = _safe_float(step.get("value", 0))
            if threshold is None:
                return False
            if op == "<=": return val <= threshold
            if op == "<":  return val < threshold
            if op == ">=": return val >= threshold
            if op == ">":  return val > threshold
        return False
    return False  # ranking steps require context — excluded from independent scoring


def _compute_excluded_markets(rows: list[dict[str, Any]], steps: list[dict[str, Any]]) -> set[str]:
    """Compute which markets are caught by any exclusion step, evaluated globally."""
    excluded: set[str] = set()
    for step in steps:
        step_type = str(step.get("step_type") or "").strip().lower()
        if step_type == "exclude_markets":
            market = str(step.get("market", "")).strip()
            if market:
                excluded.add(market)
        elif step_type == "exclude_filter":
            metric_key = step.get("metric_key", "")
            op = str(step.get("operator") or ">")
            kind = str(step.get("kind") or "threshold")
            raw_value = step.get("value", 0)
            for row in rows:
                val = _safe_float(row.get(metric_key))
                if val is None:
                    continue
                threshold: float | None = None
                if kind == "threshold":
                    threshold = _safe_float(raw_value)
                elif kind == "trend":
                    threshold = 0.0
                if threshold is None:
                    continue
                if op in (">", ">=") and val > threshold:
                    excluded.add(row["market"])
                elif op in ("<", "<=") and val < threshold:
                    excluded.add(row["market"])
        elif step_type == "exclude_ranking":
            metric_key = step.get("metric_key", "")
            limit = int(step.get("limit") or 0)
            direction = str(step.get("direction") or "descending").strip().lower()
            if limit <= 0:
                continue
            all_items = [(row["market"], _safe_float(row.get(metric_key))) for row in rows]
            all_items = [(m, v) for m, v in all_items if v is not None]
            reverse = direction != "ascending"
            ordered = sorted(all_items, key=lambda item: item[1], reverse=reverse)
            for m, _ in ordered[:limit]:
                excluded.add(m)
    return excluded


# Fixed 5-column budget-change spectrum — always the same labels regardless of action direction.
# High-scoring markets land on the LEFT (Increase) for positive prompts,
# and on the RIGHT (Decrease) for negative prompts.
FIXED_SPECTRUM = ["Increase", "Slight Increase", "Maintain", "Slight Decrease", "Decrease"]
FIXED_TIER_RANGES = ["All criteria", "Near match", "Partial", "Low match", "No match"]

# Negative-direction prompts flip which end of the spectrum gets the high scorers.
_NEGATIVE_DIRECTIONS = {"decrease", "deprioritize", "reduce", "cut"}


def _criteria_to_col(criteria_met: int, criteria_total: int) -> int:
    """
    Map criteria counts to column 0–4 (T1…T5).

    Logic:
      T1 (col 0) — all N criteria met
      T2 (col 1) — all but 1 criterion met  (N-1 / N)
      T3 (col 2) — more than half met but not near-full
      T4 (col 3) — less than half met (but some)
      T5 (col 4) — no criteria met at all

    With 2 criteria this means:
      2/2 → T1, 1/2 → T2, 0/2 → T5   (T3/T4 empty — working as designed)
    With 3 criteria:
      3/3 → T1, 2/3 → T2, 1/3 → T4, 0/3 → T5
    With 5 criteria:
      5/5 → T1, 4/5 → T2, 3/5 → T3, 2/5 → T4, 1/5 → T4, 0/5 → T5
    """
    if criteria_total == 0:
        return 2  # no criteria defined — neutral
    if criteria_met == criteria_total:
        return 0  # T1: all met
    if criteria_met == 0:
        return 4  # T5: none met
    if criteria_met >= criteria_total - 1:
        return 1  # T2: missing at most 1
    fraction = criteria_met / criteria_total
    return 2 if fraction >= 0.5 else 3  # T3 vs T4


def _compute_market_dispositions(
    rows: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    action_direction: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Score every market independently against include criteria on a 0–100% scale
    and assign it to one of 5 equal-weight columns (20% each).
    Returns (dispositions, tier_definitions).
    """
    include_steps = [s for s in steps if str(s.get("step_type")) in ("filter", "comparison")]
    ranking_steps = [s for s in steps if str(s.get("step_type")) == "ranking"]
    excluded_set = _compute_excluded_markets(rows, steps)
    is_negative = action_direction.lower() in _NEGATIVE_DIRECTIONS
    selected_ranked_markets: set[str] = set()
    if not include_steps and ranking_steps:
        for step in reversed(steps):
            if str(step.get("step_type")) != "ranking":
                continue
            matched = step.get("matched_markets")
            if isinstance(matched, list) and matched:
                selected_ranked_markets = {str(m or "").strip() for m in matched if str(m or "").strip()}
                break

    # Tier defs always show the fixed spectrum left→right
    tier_defs: list[dict[str, Any]] = [
        {"col": i, "id": f"t{i + 1}", "range": FIXED_TIER_RANGES[i], "action": FIXED_SPECTRUM[i]}
        for i in range(5)
    ]

    dispositions: list[dict[str, Any]] = []
    for row in rows:
        market = row["market"]
        is_excluded = market in excluded_set

        if selected_ranked_markets:
            criteria_total = 1
            criteria_met = 1 if market in selected_ranked_markets else 0
        elif include_steps:
            criteria_met = sum(1 for s in include_steps if _market_passes_step_independently(row, s))
            criteria_total = len(include_steps)
        else:
            criteria_met = 0
            criteria_total = 0

        score = (criteria_met / criteria_total) if criteria_total > 0 else 0.0

        if is_excluded:
            col = -1
            action = "No Action"
            tier_id = "excluded"
        else:
            raw_col = _criteria_to_col(criteria_met, criteria_total)
            # Negative prompts flip: high scorers land on the Decrease side (right)
            col = (4 - raw_col) if is_negative else raw_col
            action = FIXED_SPECTRUM[col]
            tier_id = f"t{col + 1}"

        dispositions.append({
            "market": market,
            "tier": tier_id,
            "col": col,
            "action": action,
            "score": round(score, 2),
            "score_pct": round(score * 100),
            "criteria_met": criteria_met,
            "criteria_total": criteria_total,
        })

    dispositions.sort(key=lambda x: (x["col"] if x["col"] >= 0 else 99, -x["score"]))
    return dispositions, tier_defs


def _action_to_col(action_direction: str) -> int:
    a = action_direction.strip().lower()
    if a == "increase": return 0
    if a in ("slight_increase", "slight increase"): return 1
    if a in ("maintain", "hold", "protect", "stable"): return 2
    if a in ("slight_decrease", "slight decrease"): return 3
    if a in ("decrease", "reduce", "deprioritize", "cut"): return 4
    return 2


def _normalize_segment(raw_seg: dict[str, Any], available_markets: list[str], prompt: str, seg_idx: int) -> dict[str, Any] | None:
    raw_steps = raw_seg.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        return None
    action = str(raw_seg.get("action_direction") or "increase").strip().lower()
    if action == "focus":
        action = "increase"
    if action not in {"increase", "decrease", "protect", "hold", "rebalance", "deprioritize", "maintain", "slight_increase", "slight_decrease"}:
        action = "increase"
    seg_prompt = str(raw_seg.get("label") or prompt)
    normalized_steps: list[dict[str, Any]] = []
    for idx, entry in enumerate(raw_steps, start=1):
        if not isinstance(entry, dict):
            continue
        item = _normalize_step_item(entry, available_markets, seg_prompt, idx)
        if item is not None:
            item["id"] = f"seg{seg_idx}_step_{idx}"
            normalized_steps.append(item)
    if not normalized_steps:
        return None
    return {
        "id": str(raw_seg.get("id") or f"seg_{seg_idx}"),
        "label": str(raw_seg.get("label") or f"Segment {seg_idx}"),
        "action_direction": action,
        "steps": normalized_steps,
        "execution_order": [s["id"] for s in normalized_steps],
        "matched_markets": [],
    }


def _compute_dispositions_from_segments(
    rows: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    row_map = {str(row.get("market") or "").strip(): row for row in rows if str(row.get("market") or "").strip()}
    candidate_assignments: dict[str, list[dict[str, Any]]] = {}
    for seg_idx, seg in enumerate(segments):
        label = str(seg.get("label") or seg.get("id") or "")
        action_direction = str(seg.get("action_direction") or "increase").strip().lower()
        for market in seg.get("matched_markets", []):
            market_name = str(market or "").strip()
            if not market_name:
                continue
            candidate_assignments.setdefault(market_name, []).append(
                {
                    "market": market_name,
                    "label": label,
                    "action_direction": action_direction,
                    "action_family": _normalize_action_family(action_direction),
                    "segment_index": seg_idx,
                }
            )

    market_assignment: dict[str, tuple[int, str, str]] = {}
    resolved_market_actions: list[dict[str, Any]] = []
    conflict_resolutions: list[dict[str, Any]] = []
    verdict_rank = {"supported": 3, "mixed": 2, "needs_data": 1, "at_risk": 0}

    for market, assignments in candidate_assignments.items():
        if not assignments:
            continue
        families = {str(item.get("action_family") or "maintain") for item in assignments}
        chosen = assignments[0]
        chosen_review: dict[str, Any] | None = None

        if len(families) > 1:
            row = row_map.get(market)
            scored: list[tuple[float, int, int, dict[str, Any], dict[str, Any]]] = []
            candidate_summaries: list[dict[str, Any]] = []
            for item in assignments:
                review = _build_market_review(
                    row,
                    {
                        "market": market,
                        "action_direction": item["action_direction"],
                        "action_family": item["action_family"],
                        "source_label": item["label"],
                    },
                )
                scored.append(
                    (
                        float(review.get("score", 0)),
                        int(verdict_rank.get(str(review.get("verdict") or "mixed"), 0)),
                        -int(item.get("segment_index", 0)),
                        item,
                        review,
                    )
                )
                candidate_summaries.append(
                    {
                        "action_direction": item["action_direction"],
                        "source_label": item["label"],
                        "score": review.get("score", 0),
                        "verdict": review.get("verdict"),
                        "reason": review.get("summary"),
                    }
                )
            scored.sort(key=lambda entry: (entry[0], entry[1], entry[2]), reverse=True)
            _score, _rank, _seg_order, chosen, chosen_review = scored[0]
            conflict_resolutions.append(
                {
                    "market": market,
                    "candidate_actions": candidate_summaries,
                    "chosen_action_direction": chosen["action_direction"],
                    "chosen_source_label": chosen["label"],
                    "reason": str(chosen_review.get("summary") or "Auto-resolved using elasticity, CPR, and salience."),
                }
            )

        col = _action_to_col(str(chosen.get("action_direction") or "increase"))
        market_assignment[market] = (col, FIXED_SPECTRUM[col], str(chosen.get("label") or ""))
        resolved_market_actions.append(
            {
                "market": market,
                "action_direction": chosen["action_direction"],
                "action_family": chosen["action_family"],
                "source_label": chosen["label"],
                "conflict_reason": str(chosen_review.get("summary") if chosen_review else ""),
            }
        )

    exception_markets: set[str] = set()
    for exc in exceptions:
        market = str(exc.get("market") or "").strip()
        exc_col = _action_to_col(str(exc.get("action_direction") or "increase").strip().lower())
        if market:
            market_assignment[market] = (exc_col, FIXED_SPECTRUM[exc_col], "exception")
            exception_markets.add(market)
            replaced = False
            for item in resolved_market_actions:
                if str(item.get("market") or "") == market:
                    item.update(
                        {
                            "action_direction": str(exc.get("action_direction") or "increase").strip().lower(),
                            "action_family": _normalize_action_family(str(exc.get("action_direction") or "increase")),
                            "source_label": str(exc.get("reason") or "explicit exception"),
                            "conflict_reason": "Explicit exception overrides segment conflict resolution.",
                        }
                    )
                    replaced = True
                    break
            if not replaced:
                resolved_market_actions.append(
                    {
                        "market": market,
                        "action_direction": str(exc.get("action_direction") or "increase").strip().lower(),
                        "action_family": _normalize_action_family(str(exc.get("action_direction") or "increase")),
                        "source_label": str(exc.get("reason") or "explicit exception"),
                        "conflict_reason": "Explicit exception selected this action.",
                    }
                )
    tier_defs = [{"col": i, "id": f"t{i + 1}", "range": FIXED_TIER_RANGES[i], "action": FIXED_SPECTRUM[i]} for i in range(5)]
    dispositions: list[dict[str, Any]] = []
    for row in rows:
        market = row["market"]
        if market in market_assignment:
            col, action, seg_label = market_assignment[market]
            dispositions.append({
                "market": market, "tier": f"t{col + 1}", "col": col, "action": action,
                "score": 1.0, "score_pct": 100, "criteria_met": 0, "criteria_total": 0,
                "segment": seg_label, "is_exception": market in exception_markets,
            })
        else:
            dispositions.append({
                "market": market, "tier": "t3", "col": 2, "action": "Maintain",
                "score": 0.0, "score_pct": 0, "criteria_met": 0, "criteria_total": 0,
                "segment": None, "is_exception": False,
            })
    dispositions.sort(key=lambda x: (x["col"], x["market"]))
    return dispositions, tier_defs, conflict_resolutions, resolved_market_actions


def _normalize_multi_segment_plan(
    prompt: str,
    parsed: dict[str, Any],
    rows: list[dict[str, Any]],
    available_markets: list[str],
    notes: list[str],
) -> tuple[dict[str, Any], list[str]]:
    segments: list[dict[str, Any]] = []
    for i, raw_seg in enumerate(parsed.get("segments", []), start=1):
        if not isinstance(raw_seg, dict):
            continue
        normalized = _normalize_segment(raw_seg, available_markets, prompt, i)
        if normalized:
            segments.append(normalized)
    if not segments:
        notes.append("Multi-segment plan had no valid segments; returning empty result.")
        return {
            "goal": str(parsed.get("goal") or prompt).strip() or prompt,
            "task_types": ["recommend", "filter"], "entity": "market",
            "action_direction": "increase", "steps": [], "execution_order": [],
            "assumptions": [], "reasoning": "", "matched_markets": [],
            "market_dispositions": [], "scoring_tiers": [], "conflict_resolutions": [], "resolved_market_actions": [],
        }, notes
    for seg in segments:
        executed, _, matched = _execute_plan_steps(rows, seg["steps"], seg["execution_order"])
        seg["steps"] = executed
        seg["matched_markets"] = list(matched)
    exceptions: list[dict[str, Any]] = []
    for exc in parsed.get("exceptions", []):
        if not isinstance(exc, dict):
            continue
        market = str(exc.get("market") or "").strip()
        match = next((m for m in available_markets if m.lower() == market.lower()), None)
        if match:
            exceptions.append({
                "market": match,
                "action_direction": str(exc.get("action_direction") or "increase").strip().lower(),
                "reason": str(exc.get("reason") or "explicit exception"),
            })
    market_dispositions, scoring_tiers, conflict_resolutions, resolved_market_actions = _compute_dispositions_from_segments(rows, segments, exceptions)
    all_matched = list({m for seg in segments for m in seg.get("matched_markets", [])})
    if conflict_resolutions:
        notes.append(f"{len(conflict_resolutions)} markets matched conflicting segment actions and were auto-resolved.")
    reasoning = str(parsed.get("reasoning") or "").strip()
    if not reasoning:
        seg_summaries = [f"{s.get('label','segment')} ({len(s.get('matched_markets',[]))} markets, {s.get('action_direction','increase')})" for s in segments]
        reasoning = (
            f"This is a multi-condition strategy targeting {len(segments)} distinct market groups: {'; '.join(seg_summaries)}. "
            f"Each group was identified using different performance signals from the data. "
            f"The plan aims to tailor budget actions to the specific needs of each market cluster."
        )
    return {
        "goal": str(parsed.get("goal") or prompt).strip() or prompt,
        "task_types": ["recommend", "filter"],
        "entity": "market",
        "action_direction": "mixed",
        "is_multi_segment": True,
        "segments": segments,
        "exceptions": exceptions,
        "steps": [],
        "execution_order": [],
        "assumptions": parsed.get("assumptions") if isinstance(parsed.get("assumptions"), list) else [],
        "reasoning": reasoning,
        "matched_markets": all_matched,
        "market_dispositions": market_dispositions,
        "scoring_tiers": scoring_tiers,
        "conflict_resolutions": conflict_resolutions,
        "resolved_market_actions": resolved_market_actions,
    }, notes


def _normalize_interpretation(prompt: str, raw_parsed_json: dict[str, Any] | None, rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    parsed = raw_parsed_json if isinstance(raw_parsed_json, dict) else {}
    if parsed.get("is_multi_segment") and isinstance(parsed.get("segments"), list) and parsed["segments"]:
        return _normalize_multi_segment_plan(prompt, parsed, rows, [row["market"] for row in rows], notes)
    action = str(parsed.get("action_direction") or "increase").strip().lower()
    if action == "focus":
        action = "increase"
    if action not in {"increase", "decrease", "protect", "hold", "rebalance", "recover", "deprioritize"}:
        action = "increase"
        notes.append("Action direction defaulted to `increase`.")

    task_types = parsed.get("task_types")
    if not isinstance(task_types, list) or not task_types:
        task_types = ["recommend", "filter"]
        notes.append("Task types defaulted to `recommend` + `filter`.")

    raw_filters = parsed.get("filters")
    if not isinstance(raw_filters, list):
        raw_filters = parsed.get("conditions") if isinstance(parsed.get("conditions"), list) else []
    filters = [item for item in (_normalize_filter_item(entry, prompt) for entry in raw_filters if isinstance(entry, dict)) if item is not None]
    if not filters:
        inferred = _infer_filters_from_prompt(prompt)
        if inferred:
            filters = inferred
            notes.append("Filter rules were inferred from prompt semantics.")

    raw_comparisons = parsed.get("comparisons")
    if not isinstance(raw_comparisons, list):
        raw_comparisons = [parsed.get("comparison")] if isinstance(parsed.get("comparison"), dict) else []
    comparisons = [item for item in (_normalize_comparison_item(entry, prompt) for entry in raw_comparisons if isinstance(entry, dict)) if item is not None]
    if not comparisons:
        inferred = _infer_comparisons_from_prompt(prompt)
        if inferred:
            comparisons = inferred
            notes.append("Comparison rules were inferred from prompt semantics.")

    raw_rankings = parsed.get("rankings")
    if not isinstance(raw_rankings, list):
        raw_rankings = [parsed.get("ranking")] if isinstance(parsed.get("ranking"), dict) else []
    rankings = [item for item in (_normalize_ranking_item(entry, prompt) for entry in raw_rankings if isinstance(entry, dict)) if item is not None]
    if not rankings:
        inferred = _infer_rankings_from_prompt(prompt)
        if inferred:
            rankings = inferred
            notes.append("Ranking rules were inferred from prompt semantics.")

    available_markets = [row["market"] for row in rows]
    raw_exclusions = parsed.get("exclusions")
    if not isinstance(raw_exclusions, list):
        raw_exclusions = []
    exclusions = [
        item
        for item in (_normalize_exclusion_item(entry, available_markets, prompt) for entry in raw_exclusions if isinstance(entry, dict))
        if item is not None
    ]
    if not exclusions:
        inferred = _infer_exclusions_from_prompt(prompt, available_markets)
        if inferred:
            exclusions = inferred
            notes.append("Exclusion rules were inferred from prompt semantics.")

    raw_steps = parsed.get("steps")
    step_plan: list[dict[str, Any]] = []
    execution_order: list[str] = []
    if isinstance(raw_steps, list):
        normalized_steps = [
            item
            for idx, entry in enumerate(raw_steps, start=1)
            for item in [_normalize_step_item(entry, available_markets, prompt, idx)]
            if item is not None
        ]
        if normalized_steps:
            step_plan = normalized_steps
            execution_order = []
            if isinstance(parsed.get("execution_order"), list):
                valid_ids = {str(step.get("id")) for step in step_plan}
                for item in parsed.get("execution_order", []):
                    step_id = str(item).strip()
                    if step_id in valid_ids and step_id not in execution_order:
                        execution_order.append(step_id)
            for step in step_plan:
                step_id = str(step.get("id"))
                if step_id not in execution_order:
                    execution_order.append(step_id)
        else:
            notes.append("Provided `steps` could not be normalized; falling back to inferred grouped plan.")
    if not step_plan:
        # Trinity returned no steps — fully infer from prompt semantics
        legacy_execution_order = _normalize_execution_order(parsed.get("execution_order"), filters, comparisons, rankings, exclusions)
        step_plan, execution_order = _steps_from_legacy_groups(filters, comparisons, rankings, exclusions, legacy_execution_order)
    # When Trinity returned steps, trust them entirely — no supplemental injection.
    # Human review catches any missed rules; adding inferred steps here causes hallucination.

    # If the step plan has no exclude_ranking but the prompt implies one, inject it
    has_exclude_ranking = any(str(s.get("step_type")) == "exclude_ranking" for s in step_plan)
    if not has_exclude_ranking:
        inferred_er = _infer_exclude_ranking_from_prompt(prompt)
        if inferred_er:
            next_idx = len(step_plan) + 1
            for item in inferred_er:
                step_id = f"step_{next_idx}"
                next_idx += 1
                step_plan.append({"id": step_id, "step_type": "exclude_ranking", "enabled": True, **item})
                execution_order.append(step_id)
            notes.append("Exclude-ranking rule inferred from prompt semantics.")

    # If the step plan has no exclude_filter but the prompt implies one, inject it
    has_exclude_filter = any(str(s.get("step_type")) == "exclude_filter" for s in step_plan)
    if not has_exclude_filter:
        inferred_ef = _infer_exclude_filter_from_prompt(prompt)
        if inferred_ef:
            next_idx = len(step_plan) + 1
            for item in inferred_ef:
                step_id = f"step_{next_idx}"
                next_idx += 1
                step_plan.append({"id": step_id, "step_type": "exclude_filter", "enabled": True, **item})
                execution_order.append(step_id)
            notes.append("Exclude-filter rule inferred from prompt semantics.")

    step_plan, execution_order, matched_markets = _execute_plan_steps(rows, step_plan, execution_order)
    market_dispositions, scoring_tiers = _compute_market_dispositions(rows, step_plan, action)
    interpretation = {
        "goal": str(parsed.get("goal") or prompt).strip() or prompt,
        "task_types": task_types,
        "entity": "market",
        "action_direction": action,
        "steps": step_plan,
        "execution_order": execution_order,
        "assumptions": parsed.get("assumptions") if isinstance(parsed.get("assumptions"), list) else [],
        "reasoning": str(parsed.get("reasoning") or "").strip(),
        "matched_markets": list(matched_markets),
        "market_dispositions": market_dispositions,
        "scoring_tiers": scoring_tiers,
    }
    # If Gemini returned empty reasoning, generate it from the structured interpretation
    if not interpretation.get("reasoning"):
        interpretation["reasoning"] = _generate_reasoning_from_interpretation(interpretation, rows)
    return interpretation, notes


def _generate_reasoning_from_interpretation(interp: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    """Build a plain-English explanation from the structured interpretation data."""
    action = str(interp.get("action_direction") or "increase").strip()
    matched = interp.get("matched_markets") or []
    steps = interp.get("steps") or []
    task_types = interp.get("task_types") or []

    # Describe what filters/signals drove market selection
    conditions: list[str] = []
    for step in steps:
        st = step.get("step_type", "")
        label = step.get("metric_label") or step.get("left_metric_label") or ""
        if st == "filter":
            op = step.get("operator", "")
            kind = step.get("kind", "")
            if kind == "trend":
                direction = "declining" if op in ("<", "<=") else "growing"
                conditions.append(f"{direction} {label.lower()}")
            elif st == "comparison":
                right = step.get("right_metric_label", "")
                conditions.append(f"{label.lower()} below {right.lower()}")
            else:
                conditions.append(f"{label.lower()} threshold")
        elif st == "comparison":
            right = step.get("right_metric_label", "")
            conditions.append(f"{label.lower()} below {right.lower()}")
        elif st == "ranking":
            direction = step.get("direction", "descending")
            limit = step.get("limit", "")
            rank_dir = "highest" if direction == "descending" else "lowest"
            conditions.append(f"top {limit} by {label.lower()}" if limit else f"{rank_dir} {label.lower()}")

    strategy = "recommend" if "recommend" in task_types else action
    market_count = len(matched)
    cond_text = " and ".join(conditions) if conditions else "the specified criteria"
    market_text = f"{market_count} market{'s' if market_count != 1 else ''}" if market_count else "the selected markets"

    return (
        f"The strategy identified is to {action} media investment in markets showing {cond_text}. "
        f"{market_text.capitalize()} met these conditions based on the available performance data. "
        f"The goal is to prioritise budget where market signals indicate the greatest need or opportunity for response."
    )


def _build_understanding_summary(interpretation: dict[str, Any], matched_markets: list[str]) -> str:
    if interpretation.get("is_multi_segment"):
        segs = interpretation.get("segments", [])
        parts = [f"{seg['label']} ({seg['action_direction']}, {len(seg.get('matched_markets', []))} markets)" for seg in segs]
        exc_count = len(interpretation.get("exceptions", []))
        conflict_count = len(interpretation.get("conflict_resolutions", []))
        exc_note = f" + {exc_count} exception{'s' if exc_count != 1 else ''}" if exc_count else ""
        conflict_note = f" + {conflict_count} auto-resolved overlap{'s' if conflict_count != 1 else ''}" if conflict_count else ""
        return f"Multi-segment plan: {'; '.join(parts) or 'no segments'}{exc_note}{conflict_note}. {len(matched_markets)} markets matched across all segments."
    action = str(interpretation.get("action_direction") or "increase").strip()
    pieces: list[str] = []
    for step in interpretation.get("steps") or []:
        step_type = str(step.get("step_type") or "").strip().lower()
        if step_type == "comparison":
            pieces.append(f"{step['left_metric_label']} is {step['direction']} {step['right_metric_label']}")
        elif step_type == "filter":
            operator_text = "decreasing" if step["kind"] == "trend" and step["operator"] == "<" else "increasing" if step["kind"] == "trend" else "low" if step["operator"] == "<=" else "high"
            pieces.append(f"{step['metric_label']} is {operator_text}")
        elif step_type == "ranking":
            pieces.append(f"top {step['limit']} by {step['metric_label']}")
        elif step_type == "exclude_markets":
            pieces.append(f"exclude {step['market']}")
    logic = "; ".join(pieces) if pieces else "no explicit rule captured"
    if matched_markets:
        return f"Understood as: {action} spend with logic [{logic}]. Matched {len(matched_markets)} selected markets."
    return f"Understood as: {action} spend with logic [{logic}]. No selected markets matched."


def _build_review_block(prompt: str, interpretation: dict[str, Any], matched_markets: list[str]) -> dict[str, Any]:
    prompt_lower = prompt.lower()
    review_reason: list[str] = []
    confidence = 0.94
    steps = list(interpretation.get("steps") or [])
    if interpretation.get("is_multi_segment"):
        for _seg in interpretation.get("segments", []):
            steps.extend(_seg.get("steps", []))
    comparison_steps = [step for step in steps if str(step.get("step_type")) == "comparison"]
    filter_steps = [step for step in steps if str(step.get("step_type")) == "filter"]
    ranking_steps = [step for step in steps if str(step.get("step_type")) in ("ranking", "exclude_ranking")]
    exclusion_steps = [step for step in steps if str(step.get("step_type")) in ("exclude_markets", "exclude_filter", "exclude_ranking")]
    if any(word in prompt_lower for word in COMPARISON_WORDS) and not comparison_steps:
        confidence -= 0.35
        review_reason.append("Prompt asks for a metric comparison but no comparison rule was captured.")
    if re.search(r"\btop\s+\d+\b", prompt_lower) and not ranking_steps:
        confidence -= 0.3
        review_reason.append("Prompt asks for a ranking but no ranking rule was captured.")
    if any(signal in prompt_lower for signal in ("don't include", "dont include", "do not include", "exclude", "without", "remove")) and not exclusion_steps:
        confidence -= 0.3
        review_reason.append("Prompt asks to exclude one or more markets but no exclusion rule was captured.")
    if any(word in prompt_lower for word in TREND_DOWN_WORDS) and "market share" in prompt_lower and not interpretation.get("is_multi_segment"):
        captured = any(f["metric_key"] == "change_in_market_share" and f["operator"] == "<" for f in filter_steps)
        if not captured:
            confidence -= 0.35
            review_reason.append("Prompt implies declining share trend but the interpretation did not land on `change_in_market_share < 0`.")
    conflict_resolutions = interpretation.get("conflict_resolutions", [])
    if isinstance(conflict_resolutions, list) and conflict_resolutions:
        confidence -= 0.12
        review_reason.append(f"{len(conflict_resolutions)} market(s) matched conflicting segment actions and were auto-resolved.")
    if not matched_markets:
        confidence -= 0.18
        review_reason.append("No selected markets matched the interpreted rule.")
    return {
        "needs_review": confidence < 0.9 or bool(review_reason),
        "confidence": round(max(0.05, min(0.99, confidence)), 2),
        "summary": _build_understanding_summary(interpretation, matched_markets),
        "review_reason": review_reason,
        "options": ["continue", "give_feedback"],
    }


def _normalize_action_family(action: str) -> str:
    lowered = str(action or "").strip().lower()
    if lowered in {"decrease", "deprioritize", "reduce", "slight_decrease", "slight decrease"}:
        return "decrease"
    if lowered in {"increase", "recover", "protect", "slight_increase", "slight increase"}:
        return "increase"
    if lowered in {"hold", "maintain", "rebalance"}:
        return "maintain"
    return "maintain"


def _extract_approved_market_actions(interpretation: dict[str, Any]) -> list[dict[str, Any]]:
    resolved_market_actions = interpretation.get("resolved_market_actions")
    if isinstance(resolved_market_actions, list) and resolved_market_actions:
        return [
            {
                "market": str(item.get("market") or "").strip(),
                "action_direction": str(item.get("action_direction") or "maintain").strip().lower(),
                "action_family": _normalize_action_family(str(item.get("action_direction") or "maintain")),
                "source_label": str(item.get("source_label") or "Resolved action").strip() or "Resolved action",
                "source_type": "resolved",
            }
            for item in resolved_market_actions
            if str(item.get("market") or "").strip()
        ]
    market_actions: dict[str, dict[str, Any]] = {}
    market_order: list[str] = []
    if interpretation.get("is_multi_segment"):
        for seg in interpretation.get("segments", []) or []:
            if not isinstance(seg, dict):
                continue
            action_direction = str(seg.get("action_direction") or "increase").strip().lower()
            source_label = str(seg.get("label") or "Approved segment").strip() or "Approved segment"
            for market in seg.get("matched_markets", []) or []:
                market_name = str(market or "").strip()
                if not market_name:
                    continue
                if market_name not in market_actions:
                    market_order.append(market_name)
                market_actions[market_name] = {
                    "market": market_name,
                    "action_direction": action_direction,
                    "action_family": _normalize_action_family(action_direction),
                    "source_label": source_label,
                    "source_type": "segment",
                }
        for exc in interpretation.get("exceptions", []) or []:
            if not isinstance(exc, dict):
                continue
            market_name = str(exc.get("market") or "").strip()
            if not market_name:
                continue
            action_direction = str(exc.get("action_direction") or "increase").strip().lower()
            if market_name not in market_actions:
                market_order.append(market_name)
            market_actions[market_name] = {
                "market": market_name,
                "action_direction": action_direction,
                "action_family": _normalize_action_family(action_direction),
                "source_label": str(exc.get("reason") or "Approved exception").strip() or "Approved exception",
                "source_type": "exception",
            }
    else:
        action_direction = str(interpretation.get("action_direction") or "increase").strip().lower()
        source_label = str(interpretation.get("goal") or "Approved plan").strip() or "Approved plan"
        col_to_action = {0: "increase", 1: "slight_increase", 2: "maintain", 3: "slight_decrease", 4: "decrease"}
        market_dispositions = interpretation.get("market_dispositions")
        if isinstance(market_dispositions, list) and market_dispositions:
            for disp in market_dispositions:
                if not isinstance(disp, dict):
                    continue
                market_name = str(disp.get("market") or "").strip()
                if not market_name:
                    continue
                try:
                    col = int(disp.get("col", 2))
                except (TypeError, ValueError):
                    col = 2
                if col < 0:
                    continue
                disp_action = col_to_action.get(col, "maintain")
                if market_name not in market_actions:
                    market_order.append(market_name)
                market_actions[market_name] = {
                    "market": market_name,
                    "action_direction": disp_action,
                    "action_family": _normalize_action_family(disp_action),
                    "source_label": source_label,
                    "source_type": "plan",
                }
        else:
            for market in interpretation.get("matched_markets", []) or []:
                market_name = str(market or "").strip()
                if not market_name:
                    continue
                market_order.append(market_name)
                market_actions[market_name] = {
                    "market": market_name,
                    "action_direction": action_direction,
                    "action_family": _normalize_action_family(action_direction),
                    "source_label": source_label,
                    "source_type": "plan",
                }
    return [market_actions[m] for m in market_order if m in market_actions]


def _is_high_responsiveness(row: dict[str, Any]) -> bool:
    label = str(row.get("responsiveness_label") or "").strip().lower()
    return label == "high" or (_safe_float(row.get("overall_media_elasticity")) or 0.0) >= 0.2


def _is_low_responsiveness(row: dict[str, Any]) -> bool:
    label = str(row.get("responsiveness_label") or "").strip().lower()
    return label == "low" or (
        _safe_float(row.get("overall_media_elasticity")) is not None and float(_safe_float(row.get("overall_media_elasticity")) or 0.0) < 0.08
    )


def _build_market_review(row: dict[str, Any] | None, assignment: dict[str, Any]) -> dict[str, Any]:
    market_name = str(assignment.get("market") or "").strip()
    action_direction = str(assignment.get("action_direction") or "maintain").strip().lower()
    action_family = str(assignment.get("action_family") or _normalize_action_family(action_direction))
    source_label = str(assignment.get("source_label") or "Approved plan").strip() or "Approved plan"
    review = {
        "market": market_name,
        "action_direction": action_direction,
        "action_family": action_family,
        "source_label": source_label,
        "verdict": "needs_data",
        "score": 0,
        "overall_media_elasticity": None,
        "responsiveness_label": "Unknown",
        "avg_cpr": None,
        "avg_cpr_band": None,
        "brand_salience": None,
        "brand_salience_band": None,
        "change_in_market_share": None,
        "change_in_brand_equity": None,
        "supporting_points": [],
        "warning_points": [],
        "summary": "Insufficient data to evaluate this approved action.",
    }
    if row is None:
        review["warning_points"] = ["No market intelligence row was available for this market."]
        return review

    responsiveness_label = str(row.get("responsiveness_label") or "Unknown")
    overall_media_elasticity = _safe_float(row.get("overall_media_elasticity"))
    avg_cpr = _safe_float(row.get("avg_cpr"))
    brand_salience = _safe_float(row.get("brand_salience"))
    change_in_market_share = _safe_float(row.get("change_in_market_share"))
    change_in_brand_equity = _safe_float(row.get("change_in_brand_equity"))
    avg_cpr_band = str(row.get("avg_cpr_band") or "unknown")
    brand_salience_band = str(row.get("brand_salience_band") or "unknown")

    review.update(
        {
            "overall_media_elasticity": overall_media_elasticity,
            "responsiveness_label": responsiveness_label,
            "avg_cpr": avg_cpr,
            "avg_cpr_band": avg_cpr_band,
            "brand_salience": brand_salience,
            "brand_salience_band": brand_salience_band,
            "change_in_market_share": change_in_market_share,
            "change_in_brand_equity": change_in_brand_equity,
        }
    )

    score = 0
    supporting_points: list[str] = []
    warning_points: list[str] = []
    high_resp = _is_high_responsiveness(row)
    low_resp = _is_low_responsiveness(row)

    if action_family == "increase":
        if high_resp:
            score += 2
            supporting_points.append("High media elasticity supports increasing spend.")
        elif low_resp:
            score -= 2
            warning_points.append("Low media elasticity weakens the case for increasing spend.")
        if avg_cpr_band == "low_cost":
            score += 1
            supporting_points.append("Lower CPR makes the increase relatively efficient.")
        elif avg_cpr_band == "high_cost":
            score -= 1
            warning_points.append("High CPR makes the increase more expensive.")
        if change_in_market_share is not None and change_in_market_share < 0:
            score += 1
            supporting_points.append("The market is losing share, so support can be justified.")
        if change_in_brand_equity is not None and change_in_brand_equity < 0:
            score += 1
            supporting_points.append("Brand equity is declining, which supports intervention.")
        if brand_salience_band == "high":
            score += 1
            supporting_points.append("High brand salience improves the odds of converting spend.")
        elif brand_salience_band == "low" and low_resp:
            score -= 1
            warning_points.append("Low brand salience plus low elasticity makes payoff uncertain.")
    elif action_family == "decrease":
        if high_resp:
            score -= 2
            warning_points.append("High media elasticity suggests the market is responsive, so reducing spend is risky.")
        elif low_resp:
            score += 2
            supporting_points.append("Low media elasticity supports deprioritizing spend.")
        if avg_cpr_band == "high_cost":
            score += 1
            supporting_points.append("High CPR supports reducing inefficient spend.")
        elif avg_cpr_band == "low_cost":
            score -= 1
            warning_points.append("Low CPR means the market is relatively efficient today.")
        if brand_salience_band == "high":
            score -= 1
            warning_points.append("High brand salience is a reason to be careful with cuts.")
        elif brand_salience_band == "low":
            score += 1
            supporting_points.append("Lower brand salience weakens the case for defending spend.")
        if change_in_market_share is not None and change_in_market_share > 0:
            score -= 1
            warning_points.append("The market is gaining share, so cutting spend may be premature.")
        if change_in_brand_equity is not None and change_in_brand_equity > 0:
            score -= 1
            warning_points.append("Brand equity is improving, so decreasing support may work against momentum.")
    else:
        if high_resp and brand_salience_band == "high":
            supporting_points.append("The market is responsive with solid salience, so maintaining support is defensible.")
            score += 1
        if avg_cpr_band == "high_cost" and low_resp:
            warning_points.append("High CPR and weak responsiveness suggest the market may deserve sharper action than maintain.")
            score -= 1

    if not supporting_points and not warning_points:
        warning_points.append("The data signals are mixed, so this action needs human judgment.")

    if overall_media_elasticity is None and avg_cpr is None:
        warning_points.append("Elasticity and CPR are both missing for this market.")

    if score >= 2:
        verdict = "supported"
    elif score <= -2:
        verdict = "at_risk"
    else:
        verdict = "mixed"

    summary_bits: list[str] = []
    if supporting_points:
        summary_bits.append(f"Support: {supporting_points[0]}")
    if warning_points:
        summary_bits.append(f"Risk: {warning_points[0]}")

    review.update(
        {
            "verdict": verdict,
            "score": score,
            "supporting_points": supporting_points,
            "warning_points": warning_points,
            "summary": " ".join(summary_bits) if summary_bits else review["summary"],
        }
    )
    return review


def _build_deterministic_evaluation(review_rows: list[dict[str, Any]]) -> dict[str, Any]:
    warnings: list[str] = []
    validations: list[str] = []
    supported = [r for r in review_rows if str(r.get("verdict")) == "supported"]
    at_risk = [r for r in review_rows if str(r.get("verdict")) == "at_risk"]
    mixed = [r for r in review_rows if str(r.get("verdict")) == "mixed"]

    for row in at_risk[:4]:
        warnings.append(f"{row['market']}: {row['summary']}")
    for row in supported[:4]:
        validations.append(f"{row['market']}: {row['summary']}")

    if not warnings:
        warnings.append("No major economic contradictions were flagged in the approved plan.")
    if not validations:
        validations.append("The approved plan has mixed evidence and needs closer human review.")

    headline = "Approved plan looks directionally sound."
    if at_risk:
        headline = "Approved plan has economic conflicts worth reviewing."
    elif mixed:
        headline = "Approved plan is directionally reasonable but has mixed economics."

    summary = (
        f"{len(supported)} market action(s) were strongly supported, "
        f"{len(mixed)} looked mixed, and {len(at_risk)} looked risky "
        f"when checked against elasticity, CPR, and salience."
    )

    return {
        "headline": headline,
        "summary": summary,
        "validations": validations,
        "warnings": warnings,
    }


def _build_approval_ai_prompt(
    brand: str,
    prompt: str,
    interpretation: dict[str, Any],
    deterministic_overview: dict[str, Any],
    market_reviews: list[dict[str, Any]],
) -> str:
    compact_rows = [
        {
            "market": row.get("market"),
            "action_direction": row.get("action_direction"),
            "source_label": row.get("source_label"),
            "verdict": row.get("verdict"),
            "overall_media_elasticity": row.get("overall_media_elasticity"),
            "responsiveness_label": row.get("responsiveness_label"),
            "avg_cpr": row.get("avg_cpr"),
            "avg_cpr_band": row.get("avg_cpr_band"),
            "brand_salience": row.get("brand_salience"),
            "brand_salience_band": row.get("brand_salience_band"),
            "change_in_market_share": row.get("change_in_market_share"),
            "change_in_brand_equity": row.get("change_in_brand_equity"),
            "supporting_points": row.get("supporting_points"),
            "warning_points": row.get("warning_points"),
        }
        for row in market_reviews
    ]
    return f"""You are doing second-layer economic QA for an already-approved marketing action plan.

Do NOT reinterpret the prompt. The first-layer targeting has already been approved by the user.
Your task is only to judge whether the approved increase/decrease calls look sensible given CPR, elasticity, and salience.

BRAND:
{brand}

ORIGINAL PROMPT:
"{prompt}"

APPROVED INTERPRETATION:
{json.dumps(interpretation, indent=2)}

DETERMINISTIC OVERVIEW:
{json.dumps(deterministic_overview, indent=2)}

MARKET REVIEW ROWS:
{json.dumps(compact_rows, indent=2)}

Return strict JSON only with this shape:
{{
  "headline": "",
  "summary": "",
  "validations": ["", ""],
  "warnings": ["", ""],
  "market_green_lights": [
    {{"market": "", "reason": ""}}
  ],
  "market_watchouts": [
    {{"market": "", "reason": ""}}
  ]
}}

Rules:
- Base your answer only on the supplied facts.
- Explicitly call out cases where decrease actions hit high-elasticity or high-salience markets.
- Explicitly call out cases where increase actions hit low-elasticity or high-CPR markets.
- Keep the output concise and executive-friendly.
"""


def _call_gemini_approval_evaluation(
    brand: str,
    prompt: str,
    interpretation: dict[str, Any],
    deterministic_overview: dict[str, Any],
    market_reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    notes: list[str] = []
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    ai_prompt = _build_approval_ai_prompt(brand, prompt, interpretation, deterministic_overview, market_reviews)
    result: dict[str, Any] = {
        "provider": "gemini",
        "model": model,
        "headline": "",
        "summary": "",
        "validations": [],
        "warnings": [],
        "market_green_lights": [],
        "market_watchouts": [],
        "raw_text": "",
        "notes": notes,
    }
    if not api_key:
        notes.append("Gemini API key missing; approval evaluation used deterministic review only.")
        return result

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": ai_prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    for attempt in range(2):
        try:
            req = urlrequest.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urlrequest.urlopen(req, timeout=20) as response:
                parsed = json.loads(response.read().decode("utf-8"))
            candidates = parsed.get("candidates", [])
            if not candidates:
                notes.append("Gemini returned empty approval-evaluation response.")
                return result
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts if not p.get("thought", False)).strip()
            result["raw_text"] = text
            parsed_obj = _extract_outer_json_object(text)
            if not parsed_obj:
                notes.append("Gemini approval evaluation could not be parsed as JSON.")
                return result
            result.update(
                {
                    "headline": str(parsed_obj.get("headline") or "").strip(),
                    "summary": str(parsed_obj.get("summary") or "").strip(),
                    "validations": parsed_obj.get("validations") if isinstance(parsed_obj.get("validations"), list) else [],
                    "warnings": parsed_obj.get("warnings") if isinstance(parsed_obj.get("warnings"), list) else [],
                    "market_green_lights": parsed_obj.get("market_green_lights") if isinstance(parsed_obj.get("market_green_lights"), list) else [],
                    "market_watchouts": parsed_obj.get("market_watchouts") if isinstance(parsed_obj.get("market_watchouts"), list) else [],
                }
            )
            return result
        except urlerror.HTTPError as exc:
            if attempt < 1:
                time.sleep(0.5)
                continue
            notes.append(f"Gemini approval evaluation API error ({exc.code}).")
            return result
        except Exception as exc:  # noqa: BLE001
            if attempt < 1:
                time.sleep(0.5)
                continue
            notes.append(f"Gemini approval evaluation failed: {exc}")
            return result
    return result


def _extract_interpretation_metric_keys(interpretation: dict[str, Any]) -> list[str]:
    metric_keys: list[str] = []

    def add_metric(candidate: Any) -> None:
        metric_key = str(candidate or "").strip()
        if metric_key and metric_key not in metric_keys:
            metric_keys.append(metric_key)

    for step in interpretation.get("steps", []) if isinstance(interpretation.get("steps"), list) else []:
        if not isinstance(step, dict):
            continue
        add_metric(step.get("metric_key"))
        add_metric(step.get("left_metric_key"))
        add_metric(step.get("right_metric_key"))
    for segment in interpretation.get("segments", []) if isinstance(interpretation.get("segments"), list) else []:
        if not isinstance(segment, dict):
            continue
        for step in segment.get("steps", []) if isinstance(segment.get("steps"), list) else []:
            if not isinstance(step, dict):
                continue
            add_metric(step.get("metric_key"))
            add_metric(step.get("left_metric_key"))
            add_metric(step.get("right_metric_key"))
    return metric_keys


def _to_scenario_market_action(action_direction: Any) -> str:
    action = str(action_direction or "hold").strip().lower().replace(" ", "_")
    if action in {"increase", "slight_increase", "recover"}:
        return "increase"
    if action in {"decrease", "slight_decrease", "reduce", "deprioritize"}:
        return "decrease"
    if action in {"protect", "hold", "maintain", "rebalance"}:
        return "hold"
    return "hold"


def _dominant_global_action(action_preferences_by_market: dict[str, str]) -> str:
    counts = {"increase": 0, "decrease": 0, "hold": 0}
    for action in action_preferences_by_market.values():
        counts[_to_scenario_market_action(action)] = counts.get(_to_scenario_market_action(action), 0) + 1
    if not action_preferences_by_market:
        return "hold"
    dominant, dominant_count = max(counts.items(), key=lambda item: item[1]) if counts else ("hold", 0)
    if dominant_count <= 0:
        return "hold"
    return dominant if dominant in {"increase", "decrease", "hold"} else "hold"


def _build_resolved_intent_from_approved_plan(
    brand: str,
    prompt: str,
    selected_markets: list[str],
    interpretation: dict[str, Any],
    approved_actions: list[dict[str, Any]],
    market_reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    review_by_market = {
        str(review.get("market") or "").strip(): review
        for review in market_reviews
        if isinstance(review, dict) and str(review.get("market") or "").strip()
    }
    action_preferences_by_market: dict[str, str] = {}
    market_action_explanations: dict[str, str] = {}
    target_markets: list[str] = []
    protected_markets: list[str] = []
    held_markets: list[str] = []
    deprioritized_markets: list[str] = []
    grouped_markets: dict[str, list[str]] = {}

    for item in approved_actions:
        market = str(item.get("market") or "").strip()
        if not market:
            continue
        scenario_action = _to_scenario_market_action(item.get("action_direction"))
        review = review_by_market.get(market, {})
        explanation = str(
            review.get("summary")
            or item.get("conflict_reason")
            or f"Approved Budget Allocation 2.0 action: {scenario_action}."
        ).strip()
        action_preferences_by_market[market] = scenario_action
        market_action_explanations[market] = explanation
        grouped_markets.setdefault(scenario_action, []).append(market)
        if scenario_action == "increase":
            target_markets.append(market)
        elif scenario_action == "decrease":
            deprioritized_markets.append(market)
        else:
            held_markets.append(market)

    prioritization_logic: list[dict[str, Any]] = []
    for action, markets in grouped_markets.items():
        if not markets:
            continue
        prioritization_logic.append(
            {
                "kind": "action_assignment",
                "label": f"Approved plan: {action}",
                "metric_key": "approved_budget_allocation_2",
                "operator": "assign_action",
                "value": action,
                "markets": sorted(markets),
                "rationale": "Derived from the user-approved Budget Allocation 2.0 plan.",
            }
        )

    goal = str(interpretation.get("goal") or prompt or "Generate scenarios aligned to the approved plan.").strip()
    metric_keys = _extract_interpretation_metric_keys(interpretation)
    objective = _resolve_objective_preference(prompt)
    practicality = _resolve_practicality_level(prompt)
    aggressiveness = _resolve_aggressiveness_level(prompt, objective)
    notes = [
        "Approved Budget Allocation 2.0 output was converted into structured scenario-generation guidance.",
        "Market action preferences come from the approved increase/decrease plan, not from a fresh prompt reinterpretation.",
    ]
    conflict_count = len(interpretation.get("conflict_resolutions", [])) if isinstance(interpretation.get("conflict_resolutions"), list) else 0
    if conflict_count > 0:
        notes.append(f"{conflict_count} overlapping market actions were already resolved before scenario handoff.")

    resolved_intent = ScenarioResolvedIntent(
        analysis_plan={
            "task_types": ["scenario_generation", "budget_allocation_2_handoff"],
            "goal": goal,
            "entity": {"grain": "market", "scope": list(selected_markets), "brand": brand},
            "prioritization_logic": prioritization_logic,
            "derived_metrics": metric_keys,
            "grouping": ["action_preferences_by_market"],
            "segmentation": ["action_preferences_by_market"],
            "output": {"output_type": "scenario_generation_bias", "fields": ["market", "action_preference", "bias_weight"]},
            "assumptions": [
                "Approved increase/decrease actions should bias scenario families toward the selected markets.",
                "Monte Carlo exploration should remain diverse while staying close to the approved plan.",
            ],
            "confidence": 0.95,
            "needs_review": False,
            "review_reason": [],
        },
        primary_anchor_metrics=metric_keys[:2],
        secondary_anchor_metrics=metric_keys[2:4],
        interpretation_summary=goal,
        target_markets=sorted(set(target_markets)),
        protected_markets=sorted(set(protected_markets)),
        held_markets=sorted(set(held_markets)),
        deprioritized_markets=sorted(set(deprioritized_markets)),
        action_preferences_by_market=action_preferences_by_market,
        market_action_explanations=market_action_explanations,
        global_action_preference=_dominant_global_action(action_preferences_by_market),
        objective_preference=objective,
        aggressiveness_level=aggressiveness,
        practicality_level=practicality,
        confidence_score=0.95,
        readiness_for_generation=True,
        confirmation_required=False,
        explanation_notes=notes,
    )
    return resolved_intent.model_dump(mode="json")


def _build_deterministic_scenario_handoff_strategy(
    prompt: str,
    approved_actions: list[dict[str, Any]],
    market_reviews: list[dict[str, Any]],
    scenario_range_lower_pct: float,
    scenario_range_upper_pct: float,
) -> dict[str, Any]:
    increase_count = 0
    decrease_count = 0
    supported_count = 0
    risky_count = 0
    for action in approved_actions:
        normalized = _to_scenario_market_action(action.get("action_direction"))
        if normalized == "increase":
            increase_count += 1
        elif normalized == "decrease":
            decrease_count += 1
    for review in market_reviews:
        verdict = str(review.get("verdict") or "")
        if verdict == "supported":
            supported_count += 1
        elif verdict == "at_risk":
            risky_count += 1

    objective = _resolve_objective_preference(prompt)
    if objective == "volume":
        family_mix_weights = {"volume": 0.46, "revenue": 0.18, "balanced": 0.36}
    elif objective == "revenue":
        family_mix_weights = {"volume": 0.18, "revenue": 0.46, "balanced": 0.36}
    elif objective == "efficiency":
        family_mix_weights = {"volume": 0.16, "revenue": 0.34, "balanced": 0.5}
    else:
        family_mix_weights = {"volume": 0.28, "revenue": 0.22, "balanced": 0.5}

    if increase_count > decrease_count and family_mix_weights["volume"] < 0.32:
        family_mix_weights["balanced"] = max(0.34, family_mix_weights["balanced"] - 0.06)
        family_mix_weights["volume"] = round(1.0 - family_mix_weights["balanced"] - family_mix_weights["revenue"], 2)
    if decrease_count >= increase_count and family_mix_weights["balanced"] < 0.45:
        family_mix_weights["balanced"] = 0.45
        family_mix_weights["volume"] = round(1.0 - family_mix_weights["balanced"] - family_mix_weights["revenue"], 2)

    if scenario_range_upper_pct >= 120:
        budget_zone_preference = "high"
    elif scenario_range_upper_pct <= 100:
        budget_zone_preference = "low"
    elif scenario_range_lower_pct >= 90 and scenario_range_upper_pct <= 115:
        budget_zone_preference = "mid"
    else:
        budget_zone_preference = "mixed"

    coverage_preference = "few" if len(approved_actions) <= 6 else "broad"
    diversity_preference = "medium" if risky_count > 0 else "high"
    strategy_override = _sanitize_strategy_controls(
        {
            "family_mix_weights": family_mix_weights,
            "pace_preference": "steady",
            "coverage_preference": coverage_preference,
            "diversity_preference": diversity_preference,
            "budget_zone_preference": budget_zone_preference,
        }
    )
    summary = (
        f"Bias Monte Carlo toward the {len(approved_actions)} approved markets while keeping a {strategy_override['diversity_preference']} "
        f"diversity search around the approved increase/decrease calls."
    )
    notes = [
        "Approved market actions should stay as the center of gravity for scenario sampling.",
        f"{supported_count} market actions were supported in the economic check; {risky_count} need wider exploration around them.",
    ]
    return {
        "provider": "deterministic",
        "model": "rule-based",
        "summary": summary,
        "notes": notes,
        "strategy_override": strategy_override,
    }


def _build_scenario_handoff_ai_prompt(
    brand: str,
    prompt: str,
    budget_context: dict[str, Any],
    resolved_intent: dict[str, Any],
    market_reviews: list[dict[str, Any]],
    deterministic_strategy: dict[str, Any],
) -> str:
    compact_reviews = []
    for review in market_reviews:
        compact_reviews.append(
            {
                "market": review.get("market"),
                "action_direction": review.get("action_direction"),
                "verdict": review.get("verdict"),
                "summary": review.get("summary"),
                "elasticity": review.get("overall_media_elasticity"),
                "cpr_band": review.get("avg_cpr_band"),
                "brand_salience_band": review.get("brand_salience_band"),
            }
        )
    return f"""You are preparing scenario-generation controls for a marketing Monte Carlo engine.

The approved Budget Allocation 2.0 plan is already final. Do NOT reinterpret market actions.
Your task is only to tune scenario-family exploration so it stays closer to the approved increase/decrease markets while remaining diverse.

BRAND:
{brand}

ORIGINAL PROMPT:
"{prompt}"

BUDGET CONTEXT:
{json.dumps(budget_context, indent=2)}

APPROVED RESOLVED INTENT:
{json.dumps(resolved_intent, indent=2)}

MARKET REVIEW SNAPSHOT:
{json.dumps(compact_reviews, indent=2)}

DETERMINISTIC FALLBACK:
{json.dumps(deterministic_strategy, indent=2)}

Return strict JSON only with this shape:
{{
  "summary": "",
  "notes": ["", ""],
  "family_mix_weights": {{"volume": 0.0, "revenue": 0.0, "balanced": 0.0}},
  "pace_preference": "steady",
  "coverage_preference": "few",
  "diversity_preference": "medium",
  "budget_zone_preference": "mid"
}}

Rules:
- Keep more sampling weight near the approved prompt-selected markets.
- Preserve diversity; do not collapse exploration to one family.
- Use only the supplied facts.
- family_mix_weights must sum to 1.
- Allowed values:
  pace_preference = steady|fast
  coverage_preference = few|broad
  diversity_preference = low|medium|high
  budget_zone_preference = low|mid|high|mixed
"""


def _call_gemini_scenario_handoff(
    brand: str,
    prompt: str,
    budget_context: dict[str, Any],
    resolved_intent: dict[str, Any],
    market_reviews: list[dict[str, Any]],
    deterministic_strategy: dict[str, Any],
) -> dict[str, Any]:
    notes: list[str] = []
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    result: dict[str, Any] = {
        "provider": "gemini",
        "model": model,
        "summary": "",
        "notes": notes,
        "strategy_override": deterministic_strategy.get("strategy_override", {}),
        "raw_text": "",
    }
    if not api_key:
        notes.append("Gemini API key missing; deterministic scenario handoff strategy was used.")
        return result

    ai_prompt = _build_scenario_handoff_ai_prompt(
        brand=brand,
        prompt=prompt,
        budget_context=budget_context,
        resolved_intent=resolved_intent,
        market_reviews=market_reviews,
        deterministic_strategy=deterministic_strategy,
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": ai_prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    for attempt in range(2):
        try:
            req = urlrequest.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urlrequest.urlopen(req, timeout=20) as response:
                parsed = json.loads(response.read().decode("utf-8"))
            candidates = parsed.get("candidates", [])
            if not candidates:
                notes.append("Gemini returned empty scenario-handoff guidance.")
                return result
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts if not part.get("thought", False)).strip()
            result["raw_text"] = text
            parsed_obj = _extract_outer_json_object(text)
            if not parsed_obj:
                notes.append("Gemini scenario-handoff guidance could not be parsed as JSON.")
                return result
            strategy_override = _sanitize_strategy_controls(parsed_obj)
            ai_notes = parsed_obj.get("notes") if isinstance(parsed_obj.get("notes"), list) else []
            result.update(
                {
                    "summary": str(parsed_obj.get("summary") or "").strip(),
                    "notes": [str(note).strip() for note in ai_notes if str(note).strip()],
                    "strategy_override": strategy_override,
                }
            )
            return result
        except urlerror.HTTPError as exc:
            if attempt < 1:
                time.sleep(0.5)
                continue
            notes.append(f"Gemini scenario handoff API error ({exc.code}).")
            return result
        except Exception as exc:  # noqa: BLE001
            if attempt < 1:
                time.sleep(0.5)
                continue
            notes.append(f"Gemini scenario handoff failed: {exc}")
            return result
    return result


def _build_ai_prompt(
    prompt: str,
    selected_markets: list[str],
    market_rows: list[dict[str, Any]],
    user_feedback: str,
    current_interpretation: dict[str, Any] | None,
    review_mode: str,
) -> str:
    revision_block = ""
    if review_mode == "revise" and user_feedback.strip():
        revision_block = f"""
CURRENT INTERPRETATION TO REVISE:
{json.dumps(current_interpretation or {}, indent=2)}

USER FEEDBACK:
"{user_feedback.strip()}"
"""

    return f"""You are interpreting a business prompt for a budget allocation assistant.

The assistant supports only these 5 dataset columns:
1. market_share         (level: 0–100 or 0–1 scale)
2. category_salience    (level)
3. brand_salience       (level)
4. change_in_market_share   (trend: negative = losing, positive = gaining)
5. change_in_brand_equity   (trend: negative = declining, positive = improving)

Interpret the user prompt into an ordered multi-step machine plan using ONLY the 6 step types below.

STEP TYPE REFERENCE (use exact field names):

1. filter — keep markets matching a metric threshold
   {{"id":"step_N","step_type":"filter","enabled":true,"metric_key":"change_in_market_share","metric_label":"Change In Market Share","kind":"trend","operator":"<","value":0,"source_text":"..."}}
   - kind: "trend" for change_* columns (operator < or > against 0), "band" for level columns (operator <= or >= against "median")
   - For an explicit numeric threshold use kind:"threshold" with a numeric value, e.g. value:0.5

2. comparison — keep markets where one metric is above/below another metric
   {{"id":"step_N","step_type":"comparison","enabled":true,"left_metric_key":"brand_salience","left_metric_label":"Brand Salience","operator":"<=","right_metric_key":"category_salience","right_metric_label":"Category Salience","source_text":"..."}}
   - operator: use "<" for strictly below, "<=" for "at or below" / "equal or less", ">" for strictly above, ">=" for "at or above"

3. ranking — keep only the top/bottom N markets by a metric (for SELECTION)
   {{"id":"step_N","step_type":"ranking","enabled":true,"metric_key":"category_salience","metric_label":"Category Salience","direction":"descending","limit":5,"source_text":"..."}}

4. exclude_markets — remove a specific named market
   {{"id":"step_N","step_type":"exclude_markets","enabled":true,"market":"MarketName","source_text":"..."}}

5. exclude_filter — REMOVE markets that match a metric threshold (opposite of filter)
   {{"id":"step_N","step_type":"exclude_filter","enabled":true,"metric_key":"market_share","metric_label":"Market Share","kind":"threshold","operator":">","value":0.5,"source_text":"..."}}
   - Use this when the prompt says "exclude markets where [metric] is [above/below] [value]"

6. exclude_ranking — REMOVE the top/bottom N markets by a metric (opposite of ranking)
   {{"id":"step_N","step_type":"exclude_ranking","enabled":true,"metric_key":"category_salience","metric_label":"Category Salience","direction":"descending","limit":3,"source_text":"..."}}
   - Use this when the prompt says "exclude the top N markets by [metric]"

INTERPRETATION RULES:
- "losing market share" → filter: change_in_market_share < 0
- "brand salience is at or below category salience" → comparison: brand_salience <= category_salience (use operator "<=")
- "brand equity is improving" → filter: change_in_brand_equity > 0
- "exclude the top 3 markets by category size" → exclude_ranking: category_salience descending limit 3
- "exclude any market where market share is above 50%" → exclude_filter: market_share > 0.5 (or the actual scale used in the data)
- "don't include Karnataka" → exclude_markets: market = Karnataka
- Do NOT invent steps not implied by the prompt.
- Use `steps[]` as the only source of truth. Execution order: comparisons → filters → exclude_filters → rankings → exclude_rankings → exclude_markets.
- Return strict JSON only. No markdown, no explanation outside the JSON.

USER INTENT:
"{prompt}"

SELECTED MARKETS:
{json.dumps(selected_markets, indent=2)}

AVAILABLE MARKET DATA (use actual values to set realistic thresholds):
{json.dumps(market_rows, indent=2)}
{revision_block}

SINGLE VS MULTI-SEGMENT DECISION:
- Use SINGLE format when the prompt applies ONE consistent set of conditions to markets (pure AND logic throughout — one pipeline).
- Use MULTI-SEGMENT format when the prompt describes TWO OR MORE distinct market groups each defined by their own conditions (e.g. "For markets below 50%... For markets above 50%..." or "top 5 get increased, bottom 10 get decreased"). This applies EVEN when both groups get the same action direction — because each group needs its own independent filter pipeline.
- Named markets stated as explicit exceptions → add to "exceptions" array (multi-segment format only).

SINGLE-SEGMENT format (default — use for most prompts):
{{
  "goal": "one-line restatement of the business objective in your own words — do NOT copy the prompt",
  "task_types": ["recommend", "filter"],
  "entity": "market",
  "action_direction": "increase",
  "steps": [],
  "execution_order": [],
  "assumptions": [],
  "reasoning": ""
}}

MULTI-SEGMENT format (use when the prompt defines two or more distinct market groups, each with their own conditions):
EXAMPLE A — same action, different conditions per group (both segments use action_direction "increase"):
{{
  "is_multi_segment": true,
  "goal": "",
  "segments": [
    {{
      "id": "seg_1",
      "label": "Low Market Share — Increase where brand equity fell",
      "action_direction": "increase",
      "steps": [
        {{"id":"seg_1_step_1","step_type":"filter","enabled":true,"metric_key":"market_share","metric_label":"Market Share","kind":"threshold","operator":"<","value":50,"source_text":"..."}},
        {{"id":"seg_1_step_2","step_type":"filter","enabled":true,"metric_key":"change_in_brand_equity","metric_label":"Change In Brand Equity","kind":"trend","operator":"<","value":0,"source_text":"..."}}
      ]
    }},
    {{
      "id": "seg_2",
      "label": "High Market Share — Increase where market share fell",
      "action_direction": "increase",
      "steps": [
        {{"id":"seg_2_step_1","step_type":"filter","enabled":true,"metric_key":"market_share","metric_label":"Market Share","kind":"threshold","operator":">=","value":50,"source_text":"..."}},
        {{"id":"seg_2_step_2","step_type":"filter","enabled":true,"metric_key":"change_in_market_share","metric_label":"Change In Market Share","kind":"trend","operator":"<","value":0,"source_text":"..."}}
      ]
    }}
  ],
  "exceptions": [
    {{"market": "MarketName", "action_direction": "increase", "reason": "explicit exception"}}
  ],
  "assumptions": [],
  "reasoning": ""
}}

EXAMPLE B — different actions per group (top 5 increase, bottom 10 decrease):
{{
  "is_multi_segment": true,
  "goal": "",
  "segments": [
    {{
      "id": "seg_1",
      "label": "Top 5 by Category Salience — Increase",
      "action_direction": "increase",
      "steps": [
        {{"id":"seg_1_step_1","step_type":"ranking","enabled":true,"metric_key":"category_salience","metric_label":"Category Salience","direction":"descending","limit":5,"source_text":"..."}}
      ]
    }},
    {{
      "id": "seg_2",
      "label": "Bottom 10 by Category Salience — Decrease",
      "action_direction": "decrease",
      "steps": [
        {{"id":"seg_2_step_1","step_type":"ranking","enabled":true,"metric_key":"category_salience","metric_label":"Category Salience","direction":"ascending","limit":10,"source_text":"..."}}
      ]
    }}
  ],
  "exceptions": [],
  "assumptions": [],
  "reasoning": ""
}}

FIELD INSTRUCTIONS:
- "goal": One sentence restating the business objective in your own words. Do NOT copy the user prompt.
- "reasoning": Write 2-3 sentences in plain English explaining: (1) what strategy you identified, (2) which market signals (e.g. declining market share, brand salience below category) drove which markets being selected, and (3) what the recommended budget action aims to achieve. Do NOT repeat the user prompt verbatim. Write as if briefing a marketing manager who has not seen the original prompt.
- "assumptions": List any assumptions you made that were not explicitly stated in the prompt.
- "action_direction": Must be one of: increase, decrease, protect, hold, rebalance.

Return ONLY valid JSON matching one of the two formats above.
"""


def _call_gemini_intent_debug(
    prompt: str,
    selected_markets: list[str],
    market_rows: list[dict[str, Any]],
    user_feedback: str,
    current_interpretation: dict[str, Any] | None,
    review_mode: str,
) -> dict[str, Any]:
    notes: list[str] = []
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    ai_prompt = _build_ai_prompt(prompt, selected_markets, market_rows, user_feedback, current_interpretation, review_mode)
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
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    for attempt in range(2):
        try:
            req = urlrequest.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urlrequest.urlopen(req, timeout=20) as response:
                parsed = json.loads(response.read().decode("utf-8"))
            print("GEMINI_RAW_RESPONSE:", json.dumps(parsed)[:4000], flush=True)
            candidates = parsed.get("candidates", [])
            if not candidates:
                notes.append("Gemini returned empty response.")
                return result
            parts = candidates[0].get("content", {}).get("parts", [])
            print(f"GEMINI_PARTS_COUNT={len(parts)} PART_KEYS={[list(p.keys()) for p in parts]}", flush=True)
            # Skip thought parts (Gemini 2.5 Flash thinking tokens appear as {"thought": true, "text": "..."})
            text = "".join(p.get("text", "") for p in parts if not p.get("thought", False)).strip()
            print("GEMINI_TEXT_FIRST_500:", repr(text[:500]), flush=True)
            result["raw_text"] = text
            parsed_obj = _extract_outer_json_object(text)
            if parsed_obj is not None:
                result["parsed_json"] = parsed_obj
            else:
                notes.append("Gemini returned text that could not be parsed as one outer JSON object.")
            return result
        except urlerror.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            print(f"GEMINI_HTTP_ERROR code={exc.code} body={body_text[:1000]}", flush=True)
            if attempt < 1:
                time.sleep(0.5)
                continue
            notes.append(f"Gemini API error ({exc.code}): {body_text[:300]}")
            return result
        except Exception as exc:  # noqa: BLE001
            print(f"GEMINI_EXCEPTION: {exc}", flush=True)
            if attempt < 1:
                time.sleep(0.5)
                continue
            notes.append(f"Gemini request failed: {exc}")
            return result
    return result


def service_debug_scenario_intent(payload: ScenarioIntentDebugRequest) -> dict[str, Any]:
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
    raw_rows = market_guidance.get("rows", [])
    if not isinstance(raw_rows, list):
        raw_rows = []
    all_rows = _sanitize_market_rows(raw_rows)
    # Pin scope: only operate on markets the user selected, not the full dataset
    selected_set = set(payload.selected_markets) if payload.selected_markets else None
    market_rows = [r for r in all_rows if selected_set is None or r["market"] in selected_set]
    if not market_rows:
        market_rows = _sanitize_market_rows([{"market": region} for region in ctx.get("regions", []) if str(region).strip()])
        guidance_notes = list(market_guidance.get("notes", []) or [])
        guidance_notes.append("Market intelligence rows were unavailable for Gemini debug; fallback region rows were used.")
        market_guidance["notes"] = guidance_notes

    selected_markets = list(payload.selected_markets) if payload.selected_markets else list(ctx.get("regions", []))
    gemini_result = _call_gemini_intent_debug(
        payload.intent_prompt,
        selected_markets,
        market_rows,
        payload.user_feedback,
        payload.current_interpretation,
        payload.review_mode,
    )
    normalized_interpretation, normalization_notes = _normalize_interpretation(payload.intent_prompt, gemini_result.get("parsed_json"), market_rows)
    matched_markets = list(normalized_interpretation.get("matched_markets", []))
    hitl = _build_review_block(payload.intent_prompt, normalized_interpretation, matched_markets)

    return {
        "status": "ok",
        "selection": {
            "brand": ctx["brand"],
            "markets": list(ctx["regions"]),
            "markets_count": len(ctx["regions"]),
            "baseline_budget": round(float(ctx.get("baseline_budget", 0) or 0), 2),
        },
        "market_intelligence_guidance": {
            "source_file": market_guidance.get("source_file"),
            "matched_row_count": int(market_guidance.get("matched_row_count", 0) or 0),
            "notes": market_guidance.get("notes", []),
        },
        **gemini_result,
        "normalized_interpretation": normalized_interpretation,
        "hitl": hitl,
        "notes": list(gemini_result.get("notes", [])) + normalization_notes,
    }


def service_evaluate_approved_scenario_intent(payload: ScenarioIntentApprovalEvaluationRequest) -> dict[str, Any]:
    ctx = _load_optimization_context(
        OptimizeAutoRequest(
            selected_brand=payload.selected_brand,
            selected_markets=payload.selected_markets,
            budget_increase_type=payload.budget_increase_type,
            budget_increase_value=payload.budget_increase_value,
            market_overrides=payload.market_overrides,
        )
    )
    interpretation = dict(payload.approved_interpretation or {})
    approved_actions = _extract_approved_market_actions(interpretation)
    guidance = dict(ctx.get("market_intelligence_guidance", {}) or {})
    raw_rows = guidance.get("rows", [])
    if not isinstance(raw_rows, list):
        raw_rows = []
    row_map = {
        str(row.get("market") or "").strip(): row
        for row in raw_rows
        if isinstance(row, dict) and str(row.get("market") or "").strip()
    }
    market_reviews = [_build_market_review(row_map.get(str(action.get("market") or "").strip()), action) for action in approved_actions]
    deterministic_overview = _build_deterministic_evaluation(market_reviews)
    ai_review = _call_gemini_approval_evaluation(
        brand=str(ctx.get("brand") or payload.selected_brand),
        prompt=payload.intent_prompt,
        interpretation=interpretation,
        deterministic_overview=deterministic_overview,
        market_reviews=market_reviews,
    )
    return {
        "status": "ok",
        "selection": {"brand": ctx["brand"], "markets": list(ctx["regions"]), "markets_count": len(ctx["regions"])},
        "approved_market_count": len(approved_actions),
        "deterministic_overview": deterministic_overview,
        "ai_review": ai_review,
        "market_reviews": market_reviews,
        "notes": list(guidance.get("notes", []) or []) + list(ai_review.get("notes", []) or []),
    }


def service_prepare_scenario_handoff(payload: ScenarioIntentHandoffRequest) -> dict[str, Any]:
    ctx = _load_optimization_context(
        OptimizeAutoRequest(
            selected_brand=payload.selected_brand,
            selected_markets=payload.selected_markets,
            budget_increase_type=payload.budget_increase_type,
            budget_increase_value=payload.budget_increase_value,
            market_overrides=payload.market_overrides,
        )
    )
    interpretation = dict(payload.approved_interpretation or {})
    approved_actions = _extract_approved_market_actions(interpretation)
    guidance = dict(ctx.get("market_intelligence_guidance", {}) or {})
    raw_rows = guidance.get("rows", [])
    if not isinstance(raw_rows, list):
        raw_rows = []
    row_map = {
        str(row.get("market") or "").strip(): row
        for row in raw_rows
        if isinstance(row, dict) and str(row.get("market") or "").strip()
    }
    market_reviews = [_build_market_review(row_map.get(str(action.get("market") or "").strip()), action) for action in approved_actions]
    resolved_intent = _build_resolved_intent_from_approved_plan(
        brand=str(ctx.get("brand") or payload.selected_brand),
        prompt=payload.intent_prompt,
        selected_markets=list(ctx.get("regions", [])),
        interpretation=interpretation,
        approved_actions=approved_actions,
        market_reviews=market_reviews,
    )
    lower_pct = max(0.0, float(_safe_float(payload.scenario_range_lower_pct) or 80.0))
    upper_pct = max(0.0, float(_safe_float(payload.scenario_range_upper_pct) or 120.0))
    if lower_pct > upper_pct:
        lower_pct, upper_pct = upper_pct, lower_pct
    target_budget = float(_safe_float(ctx.get("target_budget")) or 0.0)
    budget_context = {
        "baseline_budget": round(float(_safe_float(ctx.get("baseline_budget")) or 0.0), 4),
        "target_budget": round(target_budget, 4),
        "scenario_range_lower_pct": round(lower_pct, 2),
        "scenario_range_upper_pct": round(upper_pct, 2),
        "scenario_budget_lower": round(target_budget * lower_pct / 100.0, 4),
        "scenario_budget_upper": round(target_budget * upper_pct / 100.0, 4),
        "budget_increase_type": payload.budget_increase_type,
        "budget_increase_value": round(float(_safe_float(payload.budget_increase_value) or 0.0), 4),
    }
    deterministic_strategy = _build_deterministic_scenario_handoff_strategy(
        prompt=payload.intent_prompt,
        approved_actions=approved_actions,
        market_reviews=market_reviews,
        scenario_range_lower_pct=lower_pct,
        scenario_range_upper_pct=upper_pct,
    )
    ai_strategy = _call_gemini_scenario_handoff(
        brand=str(ctx.get("brand") or payload.selected_brand),
        prompt=payload.intent_prompt,
        budget_context=budget_context,
        resolved_intent=resolved_intent,
        market_reviews=market_reviews,
        deterministic_strategy=deterministic_strategy,
    )
    strategy_override = ai_strategy.get("strategy_override") or deterministic_strategy.get("strategy_override") or {}
    strategy_preview = {
        "provider": str(ai_strategy.get("provider") or deterministic_strategy.get("provider") or "deterministic"),
        "model": str(ai_strategy.get("model") or deterministic_strategy.get("model") or "rule-based"),
        "summary": str(ai_strategy.get("summary") or deterministic_strategy.get("summary") or "").strip(),
        "notes": list(ai_strategy.get("notes") or deterministic_strategy.get("notes") or []),
        **_sanitize_strategy_controls(strategy_override),
    }
    return {
        "status": "ok",
        "selection": {"brand": ctx["brand"], "markets": list(ctx["regions"]), "markets_count": len(ctx["regions"])},
        "approved_market_count": len(approved_actions),
        "budget_context": budget_context,
        "resolved_intent": resolved_intent,
        "strategy_preview": strategy_preview,
        "suggested_job_payload": {
            "selected_brand": ctx["brand"],
            "selected_markets": list(ctx["regions"]),
            "budget_increase_type": payload.budget_increase_type,
            "budget_increase_value": payload.budget_increase_value,
            "market_overrides": payload.market_overrides,
            "intent_prompt": payload.intent_prompt,
            "resolved_intent": resolved_intent,
            "strategy_override": strategy_override,
            "scenario_budget_lower": budget_context["scenario_budget_lower"],
            "scenario_budget_upper": budget_context["scenario_budget_upper"],
        },
        "notes": list(guidance.get("notes", []) or []) + list(strategy_preview.get("notes", []) or []),
    }
