# Gemini Integration Flow (Current Implementation)

This document captures the **exact current Gemini architecture** used in this project, including:
- what data is sent,
- how prompts are built,
- model/runtime configuration,
- retry/fallback behavior,
- and how outputs are converted into UI reports and scenario jobs.

---

## 1) Environment + Runtime Config

Backend file: `marketing-budget-allocation-backend/app/main.py`

- `GEMINI_API_KEY` is read from environment.
- `GEMINI_MODEL` is read from environment.
- Default model (both flows): `gemini-2.5-flash`.

Scenario engine constants:
- Job TTL: `24h` (`SCENARIO_JOB_TTL_SECONDS = 24 * 60 * 60`)
- Max returned scenarios: `1000` (`SCENARIO_TARGET_TOTAL = 1000`)
- Near-opt diversity distance baseline: `0.04`

---

## 2) Frontend -> Backend Calls

Frontend file: `marketing-budget-allocation-frontend/src/App.tsx`

### Trinity report (Insights AI)
`handleGenerateAiInsights()` posts to endpoints in order:
1. `/api/trinity-report`
2. `/api/insights-ai-summary`
3. `/api/insights-ai` (legacy compatibility)

Request payload:
- `selected_brand`
- `selected_markets`
- `budget_increase_type`
- `budget_increase_value`
- `market_overrides`
- `focus_prompt` (JSON string of compact UI context)

`focus_prompt` currently includes:
- selected insights brand/market
- S-curve summary stats (points + edge uplifts)
- top contribution variables
- latest YoY snapshot

### Step 2 scenario generation
- `POST /api/scenarios/jobs`
- `GET /api/scenarios/jobs/{job_id}`
- `GET /api/scenarios/jobs/{job_id}/results`

---

## 3) Trinity Prompt Construction (Gemini Strict JSON Mode)

Backend functions:
- `_build_ai_insights_summary(...)`
- `_build_ai_insights_prompt(...)`
- `_call_gemini_for_insights_text(...)`
- `_parse_ai_insights_response(...)`

### 3.1 Data prepared before prompt
Backend first computes deterministic diagnostics per selected state:
- YoY growth (latest FY vs previous FY)
- headroom %
- TV/Digital utilization %
- TV/Digital position %
- TV/Digital effectiveness %
- TV/Digital zone: `under-utilized | effective | saturated`
- recommendation action (rule-based)

Then it builds a compact payload for Gemini (`DATA: {...}`):
- `brand`, `markets_count`
- `insights_snapshot` (parsed `focus_prompt`)
- cluster names (`growth_leaders`, `stable_core`, `recovery_priority`)
- portfolio stats (avg/median/min/max YoY, avg/median headroom)
- action counts
- top growth states
- top risk states
- top headroom states

### 3.2 Prompt structure (strict JSON schema)
Gemini is instructed to return **JSON only** with keys:
- `headline`
- `portfolio_takeaway`
- `increase_markets` (state/channel/reason/action)
- `decrease_markets` (state/channel/reason/action)
- `channel_notes` (`tv`, `digital`)
- `risks`
- `evidence`

Prompt rules enforce:
- no markdown or prose outside JSON
- state names must come from provided DATA
- increase/decrease lists max 6 items each
- portfolio takeaway should be analytical, not a repetition of lists

---

## 4) Trinity Gemini Request Config

Function: `_call_gemini_for_insights_text(...)`

Request:
- endpoint: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- `generationConfig`:
  - `temperature: 0.2`
  - `topP: 0.9`
  - `maxOutputTokens: 900`

Reliability behavior:
- retries: `2` (total attempts = 3)
- exponential backoff
- honors `Retry-After` header on HTTP 429

Error mapping notes:
- 429 -> `Gemini rate limit reached ... deterministic insights applied.`
- 404 -> `Gemini model not found ... deterministic insights applied.`
- 400 -> `Gemini request invalid ... deterministic insights applied.`
- network/general -> deterministic fallback note

---

## 5) Trinity Parsing + Fallback Logic

### 5.1 Parsing
`_parse_ai_insights_response(...)` now prioritizes strict summary JSON parsing.
Legacy heading-based text parsing remains as a backward-compatible fallback.

Mapped internal blocks:
- `executive_summary`
- `portfolio_position`
- `state_clusters`
- `where_to_increase`
- `where_to_protect_reduce`

### 5.2 Structured finalization
`_finalize_ai_structured(...)` fills missing blocks from deterministic analytics.

### 5.3 Executive summary anti-repetition control
If AI executive summary is weak/redundant, backend replaces it with computed diagnostic summary from `_build_exec_summary_insight(...)`:
- growth/decline counts
- YoY dispersion (IQR)
- runway states
- conversion-gap states
- saturation-drag states
- channel tilt/effectiveness

### 5.4 Provider modes returned
Response `summary.provider` can be:
- `gemini` (valid parsed summary JSON/structured response)
- `fallback` (Gemini unavailable/failed)

---

## 6) Trinity API Response Contract (Important Fields)

Returned object includes:
- `selection` (brand, markets, count)
- `summary` (`provider`, cluster counts)
- `computed_executive_summary`
- `channel_diagnostics` (TV/Digital working vs attention states)
- `state_clusters`
- `market_cards` (state-level metrics + zones + action)
- `ai_brief` (final narrative text)
- `ai_structured` (parsed structured form, if available)
- `notes` (Gemini/fallback runtime notes)

---

## 7) Step 2 Intent Translator (Gemini JSON Mode)

Functions:
- `_translate_intent_to_strategy(...)`
- `_call_gemini_for_strategy(...)`

Purpose:
- convert user intent into **strategy controls only**
- never bypass hard optimizer constraints

Prompt expects strict JSON keys only:
- `family_mix_weights` (`volume`, `revenue`, `balanced` in [0,1])
- `pace_preference` (`steady|fast`)
- `coverage_preference` (`few|broad`)
- `diversity_preference` (`low|medium|high`)

Inputs to Gemini:
- raw user `intent_prompt`
- compact `constraints_context`:
  - brand
  - market_count
  - target_budget
  - baseline_budget
  - markets

Request config:
- same model env/default (`gemini-2.5-flash`)
- `temperature: 0.2`
- `responseMimeType: application/json`
- retries + 429/Retry-After behavior

If invalid or failed:
- fallback to deterministic default strategy controls

---

## 8) Scenario Job Lifecycle (Async)

Endpoints:
- `POST /api/scenarios/jobs` -> returns queued job
- `GET /api/scenarios/jobs/{job_id}` -> status/progress
- `GET /api/scenarios/jobs/{job_id}/results` -> paginated results

Statuses:
- `queued`
- `running`
- `completed`
- `failed`
- `expired`

`/results` contract:
- `202` before ready (`ready:false`, `status`, `progress`)
- `200` when completed (anchors + pagination + items)
- structured error payload for failed/expired

---

## 9) Diversity + Ranking Rules in Scenario Engine

Near-opt + broad search are combined with hard constraints.

Key controls:
- max feasible unique scenarios returned: `min(1000, feasible_unique_count)`
- distance rule:
  - normalized L2 distance on decision vectors
  - minimum enforced distance (base 0.04, adjusted by diversity preference)
- balanced anchor score:
  - computed from normalized volume and revenue uplift
- stable tie-break behavior via scenario index/order

---

## 10) What Is Deterministic vs AI

Deterministic (always available):
- optimization constraints and solving
- YoY/headroom/effectiveness computations
- state clustering logic
- fallback narrative/report content
- scenario ranking/pagination/filtering

AI-guided:
- Trinity narrative wording and section phrasing
- strategy translation for scenario sampling controls

AI never directly sets final budget allocations or bypasses hard constraints.

---

## 11) Operational Notes

- If UI shows `Gemini rate limit reached (HTTP 429)...`, pipeline safely falls back to deterministic output.
- If model name is wrong, 404 note appears and deterministic path is used.
- Current design prioritizes uninterrupted UX over hard-failing on LLM errors.
