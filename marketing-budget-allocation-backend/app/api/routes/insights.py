from fastapi import APIRouter

from app.services.engine import InsightsAIRequest, service_insights_ai_summary

router = APIRouter(tags=["insights"])


@router.post("/api/insights-ai-summary")
async def insights_ai_summary(payload: InsightsAIRequest) -> dict:
    return service_insights_ai_summary(payload)


@router.post("/api/insights-ai")
async def insights_ai(payload: InsightsAIRequest) -> dict:
    return service_insights_ai_summary(payload)


@router.post("/api/trinity-report")
async def trinity_report(payload: InsightsAIRequest) -> dict:
    return service_insights_ai_summary(payload)

