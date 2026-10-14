from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, auth, complaints, employee, health, media, notifications, users
from app.core.config import get_settings
from app.core.errors import register_error_handlers


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_settings().media_root.mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Panchayat API",
        version="1.0.0",
        description="Civic issue reporting and resolution platform (backend).",
        lifespan=lifespan,
    )
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    register_error_handlers(app)
    app.include_router(health.router)
    for module in (auth, users, complaints, media, notifications, employee, admin):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()
