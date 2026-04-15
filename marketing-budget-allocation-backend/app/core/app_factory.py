from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(title="Marketing Budget Allocation API", version="0.3.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5190",
            "http://localhost:5190",
        ],
        allow_origin_regex=(
            r"^https?://("
            r"localhost|127\.0\.0\.1|0\.0\.0\.0|"
            r"10\.\d+\.\d+\.\d+|"
            r"192\.168\.\d+\.\d+|"
            r"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+"
            r")(:\d+)?$"
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app
