from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.routers import admin, auth, health, inventory, master, orders, services


def create_app() -> FastAPI:
    """Фабрика приложения: middleware, статика и подключение роутеров."""
    app = FastAPI(title=settings.app_name, debug=settings.debug, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(services.router, prefix=settings.api_prefix)
    app.include_router(orders.router, prefix=settings.api_prefix)
    app.include_router(master.router, prefix=settings.api_prefix)
    app.include_router(inventory.router, prefix=settings.api_prefix)
    app.include_router(admin.router, prefix=settings.api_prefix)
    app.include_router(auth.router, include_in_schema=False)
    app.include_router(services.router, include_in_schema=False)
    app.include_router(orders.router, include_in_schema=False)
    app.include_router(master.router, include_in_schema=False)
    app.include_router(inventory.router, include_in_schema=False)
    app.include_router(admin.router, include_in_schema=False)

    return app


app = create_app()
