from fastapi import APIRouter

from app.services.engine import (
    BrandAllocationRequest,
    ContributionAutoRequest,
    OptimizeAutoRequest,
    SCurveAutoRequest,
    YoyGrowthRequest,
    service_brand_allocation,
    service_constraints_auto,
    service_contributions_auto,
    service_optimize_auto,
    service_s_curves_auto,
    service_yoy_growth_auto,
)

router = APIRouter(tags=["optimization"])


@router.post("/api/optimize-auto")
async def optimize_auto(payload: OptimizeAutoRequest) -> dict:
    return service_optimize_auto(payload)


@router.post("/api/constraints-auto")
async def constraints_auto(payload: OptimizeAutoRequest) -> dict:
    return service_constraints_auto(payload)


@router.post("/api/s-curves-auto")
async def s_curves_auto(payload: SCurveAutoRequest) -> dict:
    return service_s_curves_auto(payload)


@router.post("/api/contributions-auto")
async def contributions_auto(payload: ContributionAutoRequest) -> dict:
    return service_contributions_auto(payload)


@router.post("/api/yoy-growth-auto")
async def yoy_growth_auto(payload: YoyGrowthRequest) -> dict:
    return service_yoy_growth_auto(payload)


@router.post("/api/brand-allocation")
async def brand_allocation(payload: BrandAllocationRequest) -> dict:
    return service_brand_allocation(payload)

