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

from app.services.engine import OptimizeAutoRequest, _load_optimization_context

ALLOWED_METRICS: dict[str, dict[str, str]] = {
    "market_share": {"label": "Market Share", "kind": "level"},
    "category_salience": {"label": "Category Salience", "kind": "level"},
    "brand_salience": {"label": "Brand Salience", "kind": "level"},
    "change_in_market_share": {"label": "Change In Market Share", "kind": "trend"},
    "change_in_brand_equity": {"label": "Change In Brand Equity", "kind": "trend"},
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
    lowered = text.lower()
    for alias, metric_key in sorted(METRIC_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in lowered:
            return metric_key
    return None


def _sanitize_market_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        market = str(row.get("market", "")).strip()
        if not market:
            continue
        out.append(
            {
                "market": market,
                "category_salience": _safe_float(row.get("category_salience")),
                "brand_salience": _safe_float(row.get("brand_salience")),
                "market_share": _safe_float(row.get("market_share")),
                "change_in_market_share": _safe_float(row.get("change_in_market_share")),
                "change_in_brand_equity": _safe_float(row.get("change_in_brand_equity")),
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
    metrics = _infer_metric_mentions(prompt)
    if len(metrics) < 2:
        return []
    operator = "<"
    direction = "below"
    if any(word in prompt_lower for word in ("above", "greater than", "higher than")):
        operator = ">"
        direction = "above"
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
    mentioned = _infer_metric_mentions(source_text or prompt)
    if left_metric not in ALLOWED_METRICS and mentioned:
        left_metric = mentioned[0]
    if right_metric not in ALLOWED_METRICS and len(mentioned) > 1:
        right_metric = mentioned[1]
    if left_metric not in ALLOWED_METRICS or right_metric not in ALLOWED_METRICS:
        return None
    operator = str(item.get("operator") or "<").strip()
    if operator not in {"<", ">"}:
        operator = "<"
    return {
        "left_metric_key": left_metric,
        "left_metric_label": ALLOWED_METRICS[left_metric]["label"],
        "operator": operator,
        "direction": "below" if operator == "<" else "above",
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
        if operator == "<" and left_value < right_value:
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


def _normalize_interpretation(prompt: str, raw_parsed_json: dict[str, Any] | None, rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    parsed = raw_parsed_json if isinstance(raw_parsed_json, dict) else {}
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

    execution_order = _normalize_execution_order(parsed.get("execution_order"), filters, comparisons, rankings, exclusions)
    interpretation = {
        "goal": str(parsed.get("goal") or prompt).strip() or prompt,
        "task_types": task_types,
        "entity": "market",
        "action_direction": action,
        "filters": filters,
        "comparisons": comparisons,
        "rankings": rankings,
        "exclusions": exclusions,
        "execution_order": execution_order,
        "assumptions": parsed.get("assumptions") if isinstance(parsed.get("assumptions"), list) else [],
        "reasoning": str(parsed.get("reasoning") or "").strip(),
    }

    current_scope = list(available_markets)
    for step in execution_order:
        if step == "comparisons":
            for comparison in comparisons:
                matched, note = _match_comparison(rows, current_scope, comparison)
                comparison["matched_markets"] = matched
                current_scope = matched
                notes.append(note)
        elif step == "filters":
            for filt in filters:
                matched, note = _match_filter(rows, current_scope, filt)
                filt["matched_markets"] = matched
                current_scope = matched
                notes.append(note)
        elif step == "rankings":
            for ranking in rankings:
                matched, note = _apply_ranking(rows, current_scope or available_markets, ranking)
                ranking["matched_markets"] = matched
                current_scope = matched
                notes.append(note)
        elif step == "exclusions":
            for exclusion in exclusions:
                current_scope, note = _apply_exclusion(current_scope, exclusion)
                exclusion["matched_markets"] = list(current_scope)
                notes.append(note)

    interpretation["matched_markets"] = list(current_scope)
    return interpretation, notes


def _build_understanding_summary(interpretation: dict[str, Any], matched_markets: list[str]) -> str:
    action = str(interpretation.get("action_direction") or "increase").strip()
    filters = interpretation.get("filters") or []
    comparisons = interpretation.get("comparisons") or []
    rankings = interpretation.get("rankings") or []
    exclusions = interpretation.get("exclusions") or []
    pieces: list[str] = []
    for comparison in comparisons:
        pieces.append(
            f"{comparison['left_metric_label']} is {comparison['direction']} {comparison['right_metric_label']}"
        )
    for filt in filters:
        operator_text = "decreasing" if filt["kind"] == "trend" and filt["operator"] == "<" else "increasing" if filt["kind"] == "trend" else "low" if filt["operator"] == "<=" else "high"
        pieces.append(f"{filt['metric_label']} is {operator_text}")
    for ranking in rankings:
        pieces.append(f"top {ranking['limit']} by {ranking['metric_label']}")
    for exclusion in exclusions:
        pieces.append(f"exclude {exclusion['market']}")
    logic = "; ".join(pieces) if pieces else "no explicit rule captured"
    if matched_markets:
        return f"Understood as: {action} spend with logic [{logic}]. Matched {len(matched_markets)} selected markets."
    return f"Understood as: {action} spend with logic [{logic}]. No selected markets matched."


def _build_review_block(prompt: str, interpretation: dict[str, Any], matched_markets: list[str]) -> dict[str, Any]:
    prompt_lower = prompt.lower()
    review_reason: list[str] = []
    confidence = 0.94
    if any(word in prompt_lower for word in COMPARISON_WORDS) and not interpretation.get("comparisons"):
        confidence -= 0.35
        review_reason.append("Prompt asks for a metric comparison but no comparison rule was captured.")
    if re.search(r"\btop\s+\d+\b", prompt_lower) and not interpretation.get("rankings"):
        confidence -= 0.3
        review_reason.append("Prompt asks for a ranking but no ranking rule was captured.")
    if any(signal in prompt_lower for signal in ("don't include", "dont include", "do not include", "exclude", "without", "remove")) and not interpretation.get("exclusions"):
        confidence -= 0.3
        review_reason.append("Prompt asks to exclude one or more markets but no exclusion rule was captured.")
    if any(word in prompt_lower for word in TREND_DOWN_WORDS) and "market share" in prompt_lower:
        captured = any(f["metric_key"] == "change_in_market_share" and f["operator"] == "<" for f in interpretation.get("filters", []))
        if not captured:
            confidence -= 0.35
            review_reason.append("Prompt implies declining share trend but the interpretation did not land on `change_in_market_share < 0`.")
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
1. market_share
2. category_salience
3. brand_salience
4. change_in_market_share
5. change_in_brand_equity

Interpret the prompt into a multi-step machine plan.

Rules:
- A prompt may contain multiple steps in combination: filters, comparisons, rankings.
- A prompt may also exclude markets explicitly.
- "losing market share" means a filter on `change_in_market_share < 0`.
- "brand salience is below category salience" means a comparison `brand_salience < category_salience`.
- "top 7 markets by category size" means a ranking on `category_salience`.
- "don't include Karnataka" means an exclusion on market `Karnataka`.
- Do not invent a comparison if the prompt is only a filter.
- Do not invent a ranking if the prompt is only a filter or comparison.
- Use `execution_order` to show how code should apply the plan. Typical order is comparisons -> filters -> rankings.
- Typical order with exclusions is comparisons -> filters -> rankings -> exclusions.
- Return strict JSON only.

USER INTENT:
"{prompt}"

SELECTED MARKETS:
{json.dumps(selected_markets, indent=2)}

AVAILABLE MARKET DATA:
{json.dumps(market_rows, indent=2)}
{revision_block}

Return ONLY this JSON shape:
{{
  "goal": "",
  "task_types": ["recommend", "filter"],
  "entity": "market",
  "action_direction": "increase",
  "filters": [
    {{
      "metric_key": "",
      "metric_label": "",
      "kind": "trend",
      "operator": "<",
      "value": 0,
      "source_text": ""
    }}
  ],
  "comparisons": [
    {{
      "left_metric_key": "",
      "left_metric_label": "",
      "operator": "<",
      "right_metric_key": "",
      "right_metric_label": "",
      "source_text": ""
    }}
  ],
  "rankings": [
    {{
      "metric_key": "",
      "metric_label": "",
      "direction": "descending",
      "limit": 0,
      "source_text": ""
    }}
  ],
  "exclusions": [
    {{
      "market": "",
      "source_text": ""
    }}
  ],
  "execution_order": ["comparisons", "filters", "rankings", "exclusions"],
  "assumptions": [],
  "reasoning": ""
}}
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
    body = {"contents": [{"parts": [{"text": ai_prompt}]}], "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1800}}
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
            parsed_obj = _extract_outer_json_object(text)
            if parsed_obj is not None:
                result["parsed_json"] = parsed_obj
            else:
                notes.append("Gemini returned text that could not be parsed as one outer JSON object.")
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
    market_rows = _sanitize_market_rows(raw_rows)
    if not market_rows:
        market_rows = _sanitize_market_rows([{"market": region} for region in ctx.get("regions", []) if str(region).strip()])
        guidance_notes = list(market_guidance.get("notes", []) or [])
        guidance_notes.append("Market intelligence rows were unavailable for Gemini debug; fallback region rows were used.")
        market_guidance["notes"] = guidance_notes

    gemini_result = _call_gemini_intent_debug(
        payload.intent_prompt,
        ctx["regions"],
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
        "selection": {"brand": ctx["brand"], "markets": list(ctx["regions"]), "markets_count": len(ctx["regions"])},
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
