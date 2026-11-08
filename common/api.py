import logging
import sqlite3

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)


def make_app(name):
    app = FastAPI(title=name, version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": name}

    @app.exception_handler(httpx.RequestError)
    async def upstream_error(request: Request, exc):
        log.warning("Upstream unavailable: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "Сервис недоступен. Повторите запрос позже."})

    @app.exception_handler(sqlite3.Error)
    async def database_error(request: Request, exc):
        log.exception("Database error")
        return JSONResponse(status_code=503, content={"detail": "Хранилище временно недоступно."})

    return app


def call(base, path, method="GET", timeout=30, **kwargs):
    with httpx.Client(timeout=timeout) as client:
        response = client.request(method, base.rstrip("/") + path, **kwargs)
    if response.is_error:
        try:
            detail = response.json().get("detail", "Ошибка зависимого сервиса")
        except ValueError:
            detail = "Ошибка зависимого сервиса"
        raise HTTPException(response.status_code, detail)
    return response.json()
