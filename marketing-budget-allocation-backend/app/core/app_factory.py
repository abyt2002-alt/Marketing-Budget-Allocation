from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.services.engine import trigger_insights_cache_warmup


def create_app() -> FastAPI:
    app = FastAPI(title="Marketing Budget Allocation API", version="0.3.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.on_event("startup")
    def _startup_warm_insights_cache() -> None:
        trigger_insights_cache_warmup()

    return app
