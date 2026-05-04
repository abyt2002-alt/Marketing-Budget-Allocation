from typing import Any

from fastapi import APIRouter

from app.services.intent_debug import (
    MarketSignalsRequest,
    ScenarioIntentApprovalEvaluationRequest,
    ScenarioIntentDebugRequest,
    ScenarioIntentHandoffRequest,
    service_debug_scenario_intent,
    service_evaluate_approved_scenario_intent,
    service_get_market_signals,
    service_prepare_scenario_handoff,
)

router = APIRouter(tags=["intent-debug"])


@router.post("/api/scenarios/intent/debug")
async def debug_scenario_intent(payload: ScenarioIntentDebugRequest) -> dict[str, Any]:
    return service_debug_scenario_intent(payload)


@router.post("/api/scenarios/intent/evaluate-approved")
async def evaluate_approved_scenario_intent(payload: ScenarioIntentApprovalEvaluationRequest) -> dict[str, Any]:
    return service_evaluate_approved_scenario_intent(payload)


@router.post("/api/scenarios/intent/handoff")
async def prepare_scenario_handoff(payload: ScenarioIntentHandoffRequest) -> dict[str, Any]:
    return service_prepare_scenario_handoff(payload)


@router.post("/api/scenarios/market-signals")
async def get_market_signals(payload: MarketSignalsRequest) -> dict[str, Any]:
    return service_get_market_signals(payload)
