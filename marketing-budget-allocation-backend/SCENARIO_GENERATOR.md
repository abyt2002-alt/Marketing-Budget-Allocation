# Scenario Generator

This document explains what the scenario generator does in the backend, what inputs it uses, where AI is involved, how constraints are enforced, and what the API returns.

## What It Is

The scenario generator is an async backend workflow that creates many feasible Step-2 brand-market budget scenarios for a selected brand and market set.

Its job is to:

- start from the current MMM optimization context
- generate multiple candidate TV/Digital allocation plans
- keep only feasible and diverse scenarios
- score and rank the accepted scenarios
- return anchor scenarios such as best volume, best revenue, and best balanced

It is exposed through these APIs:

- `POST /api/scenarios/jobs`
- `GET /api/scenarios/jobs/{job_id}`
- `GET /api/scenarios/jobs/{job_id}/results`
- `POST /api/scenarios/summary`

## High-Level Flow

The scenario flow is:

1. The frontend sends a scenario job request.
2. The backend creates an async job record and starts a worker thread.
3. The worker loads the same optimization context used by Step-2 planning.
4. If the user provided an intent prompt, Gemini translates that prompt into strategy controls.
5. The generator computes deterministic seed solutions.
6. It samples many candidate solutions around those seeds.
7. Every candidate is projected into the allowed budget band and checked against hard constraints.
8. Feasible, unique, sufficiently different candidates are accepted.
9. Accepted scenarios are evaluated for volume uplift, revenue uplift, spend mix, and per-market effects.
10. Scenarios are scored, ranked, and returned through the results endpoint.

## What The Generator Produces

Each scenario is a complete TV/Digital reallocation plan across the selected markets. The response contains:

- scenario ID and index
- scenario family
- seed source
- total volume uplift
- total revenue uplift
- total spend
- weighted TV share
- weighted Digital share
- per-market changes and predicted outcomes

The backend also returns summary metadata:

- scenario count
- near-optimum scenario count
- effective budget band used
- feasible budget range
- runtime
- strategy controls used

It also returns three anchor scenarios:

- `best_volume`
- `best_revenue`
- `best_balanced`

## Main Input Payload

The scenario job request model is:

```json
{
  "selected_brand": "Brand Name",
  "selected_markets": ["State 1", "State 2"],
  "budget_increase_type": "percentage",
  "budget_increase_value": 5.0,
  "market_overrides": {
    "State 1": {
      "tv_min_reach": 10,
      "tv_max_reach": 30,
      "dg_min_reach": 8,
      "dg_max_reach": 25,
      "target_reach_share_pct": 18
    }
  },
  "intent_prompt": "Prioritize revenue upside but keep scenarios broad and practical.",
  "scenario_budget_lower": 1200,
  "scenario_budget_upper": 1500,
  "target_scenarios": 150,
  "max_runtime_seconds": 900
}
```

Meaning of the important fields:

- `selected_brand`: the brand to optimize
- `selected_markets`: markets included in the scenario run
- `budget_increase_type` and `budget_increase_value`: define the target Step-2 budget
- `market_overrides`: optional hard overrides for market limits and reach-share targets
- `intent_prompt`: optional AI guidance for scenario exploration style
- `scenario_budget_lower` and `scenario_budget_upper`: optional explicit budget band for scenario generation
- `target_scenarios`: how many scenarios the user wants
- `max_runtime_seconds`: runtime cap for the generator

## Data Sources

The scenario generator does not invent its own base numbers. It uses the existing MMM backend context, including:

- model data
- market-level spend and reach data
- market bounds and overrides
- region prices from recent history
- elasticity guidance detected from result files

The elasticity guidance is included in the AI constraint context, but hard feasibility still comes from the optimization engine.

## Where AI Is Used

AI is used only in a narrow control role.

If `intent_prompt` is present, Gemini receives:

- the user intent
- brand
- market count
- target budget
- baseline budget
- market list
- requested scenario budget band
- reach-share targets
- elasticity guidance summary

Gemini does not return scenarios. It returns only strategy controls:

- `family_mix_weights`
- `pace_preference`
- `coverage_preference`
- `diversity_preference`
- `budget_zone_preference`

Example strategy JSON:

```json
{
  "family_mix_weights": {
    "volume": 0.4,
    "revenue": 0.4,
    "balanced": 0.2
  },
  "pace_preference": "steady",
  "coverage_preference": "broad",
  "diversity_preference": "medium",
  "budget_zone_preference": "mixed"
}
```

Important limitation:

AI does not choose market-level spend values directly. It only influences how the sampler explores the feasible space.

## What AI Actually Changes

The returned strategy affects sampling behavior:

- which scenario families are sampled more often
- whether exploration is more steady or faster
- whether coverage is narrow or broad
- how much diversity is preferred
- whether the generator samples more from the lower, middle, upper, or mixed part of the budget band

In other words, AI changes exploration bias, not mathematical validity.

## Deterministic Seeds

Before sampling, the backend computes deterministic seed solutions:

- `volume_seed`: optimized for volume
- `revenue_seed`: optimized for revenue
- `balanced_seed`: midpoint blend of the two

These seeds become anchor points for exploration.

## Candidate Generation

The generator creates candidates in two phases:

### 1. Near-optimum phase

The backend samples candidates close to the volume and revenue seeds. This is intended to produce scenarios that stay near strong deterministic solutions.

### 2. Diverse strategy phase

The backend samples more broadly according to the AI-derived family weights and exploration controls. This phase is intended to produce a wider set of practical alternatives.

If the feasible space is too tight, the backend can relax the diversity threshold and try again.

## Hard Constraints

Every candidate must pass hard checks before being accepted.

The backend enforces:

- variable bounds
- feasible budget band
- market min/max reach constraints
- reach-share target satisfaction when requested
- uniqueness
- diversity threshold versus already accepted scenarios

If a candidate fails these checks, it is discarded.

This is the key design rule:

AI guidance can suggest how to explore, but it cannot override feasibility.

## Budget Band Logic

The generator works inside a budget band.

Inputs involved:

- requested target budget from Step-2
- feasible minimum budget from bounds
- feasible maximum budget from bounds
- optional `scenario_budget_lower`
- optional `scenario_budget_upper`

The backend clamps requested budgets to feasible limits. If the requested target is outside feasible bounds, the backend adjusts it and adds a note to the response.

The final generator uses:

- effective lower budget band
- effective upper budget band
- budget zone preference from strategy controls

## Scenario Acceptance Rules

A candidate is accepted only if:

- it can be projected into the active budget band
- it remains feasible after projection
- it satisfies reach-share targets when those exist
- it is not an exact duplicate
- it is sufficiently different from previously accepted scenarios

Accepted scenarios are then fully evaluated and stored.

## What Gets Evaluated Per Scenario

For each accepted scenario, the backend calculates:

- total spend
- weighted TV share
- weighted Digital share
- total volume uplift absolute and percent
- total revenue uplift absolute and percent
- baseline and new revenue
- per-market new TV and Digital reach
- per-market spend shifts
- per-market reach-share changes
- per-market predicted volume and revenue changes

This makes each scenario fully inspectable at both portfolio and market level.

## Families

The generator uses three families:

- `Volume`
- `Revenue`
- `Balanced`

These represent the exploration emphasis, not a different constraint system.

- volume family favors candidates near volume-oriented solutions
- revenue family favors candidates near revenue-oriented solutions
- balanced family explores blended solutions

## Scoring And Ranking

After scenario generation:

- `balanced_score` is computed by normalizing volume uplift percent and revenue uplift percent, then averaging the two
- volume rank is assigned by sorting scenarios by volume uplift
- revenue rank is assigned by sorting scenarios by revenue uplift

Anchor scenarios are then picked:

- best volume by `volume_uplift_pct`
- best revenue by `revenue_uplift_pct`
- best balanced by `balanced_score`

## Async Job Lifecycle

The job status endpoint returns:

- `queued`
- `running`
- `completed`
- `failed`
- `expired`

Typical flow:

1. `POST /api/scenarios/jobs`
2. poll `GET /api/scenarios/jobs/{job_id}`
3. fetch `GET /api/scenarios/jobs/{job_id}/results`

The results endpoint returns:

- `202` while still running
- `409` if failed
- `410` if expired
- `200` when completed

## Filtering And Pagination

Completed scenario results support:

- pagination
- sorting
- filtering by family
- filtering by volume uplift
- filtering by revenue uplift
- filtering by budget utilized
- filtering by reach-share change for a selected market

Allowed sort keys include:

- `balanced_score`
- `volume_uplift_pct`
- `revenue_uplift_pct`
- `volume_uplift_abs`
- `revenue_uplift_abs`
- `weighted_tv_share`
- `weighted_digital_share`
- `scenario_id`

## Scenario Summary Endpoint

`POST /api/scenarios/summary` is separate from scenario generation.

Its purpose is to summarize one already-generated scenario in business language.

It takes scenario market rows and optional user prompt context, then:

- calls Gemini for a crisp business summary
- falls back to deterministic text if Gemini fails

This endpoint explains a scenario. It does not generate scenarios.

## Failure And Fallback Behavior

If Gemini is unavailable or returns invalid strategy JSON:

- the backend falls back to default strategy controls
- the scenario generator still runs

If feasible space is too narrow:

- fewer scenarios may be returned
- diversity thresholds may be relaxed
- notes will explain why

If runtime cap is hit:

- generation stops early
- accepted scenarios so far are returned
- a note is added

## What The Scenario Generator Is Not

It is not:

- a free-form AI planner that can ignore MMM constraints
- a raw Excel-to-LLM workflow
- a single best-answer optimizer only
- a guarantee that the requested number of scenarios will be feasible

It is:

- a constrained scenario explorer
- seeded by deterministic optimization
- optionally guided by AI sampling strategy
- scored and ranked for business review

## Practical Interpretation

The safest way to think about it is:

The backend first establishes what is mathematically and operationally feasible. Then it uses AI, when available, to decide how to search that feasible space more intelligently. The final scenarios still come from deterministic evaluation and hard constraint enforcement.

## Code References

Primary files:

- `app/api/routes/scenarios.py`
- `app/services/engine.py`

Key areas:

- request model: `ScenarioJobCreateRequest`
- async entrypoint: `service_create_scenario_job`
- worker: `_run_scenario_job`
- AI strategy translation: `_call_gemini_for_strategy`
- generator core: `_generate_scenarios_for_context`
- results paging/filtering: `service_get_scenario_job_results`
- scenario explanation: `service_scenario_summary`
