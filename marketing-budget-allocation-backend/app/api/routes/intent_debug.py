from typing import Any

from fastapi import APIRouter

from app.services.intent_debug import ScenarioIntentDebugRequest, service_debug_scenario_intent

router = APIRouter(tags=["intent-debug"])


@router.post("/api/scenarios/intent/debug")
async def debug_scenario_intent(payload: ScenarioIntentDebugRequest) -> dict[str, Any]:
    return service_debug_scenario_intent(payload)
