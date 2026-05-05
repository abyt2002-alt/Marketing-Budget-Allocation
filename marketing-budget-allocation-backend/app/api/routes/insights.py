from fastapi import APIRouter, Query

from app.services.engine import InsightsAIRequest, service_insights_ai_summary, service_investment_framework, InvestmentSummaryRequest, service_investment_summary

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


@router.get("/api/investment-framework")
async def investment_framework(brand: str = Query(..., description="Brand name")) -> dict:
    return service_investment_framework(brand)


@router.post("/api/investment-summary")
async def investment_summary(payload: InvestmentSummaryRequest) -> dict:
    return service_investment_summary(payload)

