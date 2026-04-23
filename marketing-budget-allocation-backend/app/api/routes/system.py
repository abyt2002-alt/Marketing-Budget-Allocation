from fastapi import APIRouter

from app.services.engine import service_auto_config, service_health, service_insights_cache_status

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return service_health()


@router.get("/api/auto-config")
async def auto_config() -> dict:
    return service_auto_config()


@router.get("/api/insights-cache-status")
async def insights_cache_status() -> dict:
    return service_insights_cache_status()
