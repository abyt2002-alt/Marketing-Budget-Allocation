from fastapi import APIRouter

from app.services.engine import service_auto_config, service_health

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return service_health()


@router.get("/api/auto-config")
async def auto_config() -> dict:
    return service_auto_config()

