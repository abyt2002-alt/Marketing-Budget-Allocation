from typing import Any

from fastapi import APIRouter, Query

from app.services.engine import (
    SCENARIO_PAGE_SIZE_DEFAULT,
    SCENARIO_PAGE_SIZE_MAX,
    ScenarioJobCreateRequest,
    service_create_scenario_job,
    service_get_scenario_job_results,
    service_get_scenario_job_status,
)

router = APIRouter(tags=["scenarios"])


@router.post("/api/scenarios/jobs")
async def create_scenario_job(payload: ScenarioJobCreateRequest) -> dict[str, Any]:
    return service_create_scenario_job(payload)


@router.get("/api/scenarios/jobs/{job_id}")
async def get_scenario_job_status(job_id: str) -> dict[str, Any]:
    return service_get_scenario_job_status(job_id)


@router.get("/api/scenarios/jobs/{job_id}/results")
async def get_scenario_job_results(
    job_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(SCENARIO_PAGE_SIZE_DEFAULT, ge=1, le=SCENARIO_PAGE_SIZE_MAX),
    sort_key: str = Query("balanced_score"),
    sort_dir: str = Query("desc"),
    family: str | None = Query(None),
    min_volume_uplift_pct: float | None = Query(None),
    max_volume_uplift_pct: float | None = Query(None),
    min_revenue_uplift_pct: float | None = Query(None),
    max_revenue_uplift_pct: float | None = Query(None),
) -> Any:
    return service_get_scenario_job_results(
        job_id=job_id,
        page=page,
        page_size=page_size,
        sort_key=sort_key,
        sort_dir=sort_dir,
        family=family,
        min_volume_uplift_pct=min_volume_uplift_pct,
        max_volume_uplift_pct=max_volume_uplift_pct,
        min_revenue_uplift_pct=min_revenue_uplift_pct,
        max_revenue_uplift_pct=max_revenue_uplift_pct,
    )

