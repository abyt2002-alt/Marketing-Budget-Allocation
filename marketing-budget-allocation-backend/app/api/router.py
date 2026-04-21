from fastapi import APIRouter

from app.api.routes.insights import router as insights_router
from app.api.routes.intent_debug import router as intent_debug_router
from app.api.routes.optimization import router as optimization_router
from app.api.routes.scenarios import router as scenarios_router
from app.api.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(optimization_router)
api_router.include_router(insights_router)
api_router.include_router(intent_debug_router)
api_router.include_router(scenarios_router)
