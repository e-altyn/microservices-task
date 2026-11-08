from hashlib import sha256
from pathlib import Path

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from common.api import make_app
from common.config import load_config

STATIC = Path(__file__).parent / "static"


def create_app(config=None):
    cfg = config or load_config("visualization")
    app = make_app("Visualization")
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/")
    def index():
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        for filename in ("style.css", "app.js"):
            version = sha256((STATIC / filename).read_bytes()).hexdigest()[:12]
            html = html.replace(f'"/static/{filename}"', f'"/static/{filename}?v={version}"')
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
    async def proxy(path: str, request: Request):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > cfg["max_request_bytes"]:
                raise HTTPException(413, "Запрос слишком большой")
        async with httpx.AsyncClient(timeout=cfg["request_timeout"]) as client:
            result = await client.request(request.method, cfg["master_url"] + "/api/" + path,
                                          params=request.query_params, content=bytes(body),
                                          headers={"content-type": request.headers.get("content-type", "application/json")})
        return Response(content=result.content, status_code=result.status_code,
                        media_type=result.headers.get("content-type", "application/json"))

    return app


app = create_app()
