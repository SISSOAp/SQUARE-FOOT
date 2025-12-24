from __future__ import annotations

from pathlib import Path
import importlib
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


app = FastAPI(title="SQUARE FOOT", version="1.6")


# ========= Paths =========
BASE_DIR = Path(__file__).resolve().parent          # .../src
ROOT_DIR = BASE_DIR.parent                          # .../
WEB_DIR  = ROOT_DIR / "web"                         # .../web

INDEX_HTML = WEB_DIR / "index.html"
APP_JS     = WEB_DIR / "app.js"
SW_JS      = WEB_DIR / "sw.js"


# ========= API import (robusto) =========
api_router = None
api_app = None
api_import_error: Optional[str] = None

try:
    m = importlib.import_module("src.api")

    # Caso 1: src/api.py define APIRouter chamado router (ou api_router)
    if hasattr(m, "router"):
        api_router = getattr(m, "router")
    elif hasattr(m, "api_router"):
        api_router = getattr(m, "api_router")

    # Caso 2: src/api.py define um FastAPI app chamado app
    elif hasattr(m, "app"):
        api_app = getattr(m, "app")

except Exception as e:
    api_import_error = str(e)


# 1) Conecta a API (antes do fallback do SPA)
if api_router is not None:
    app.include_router(api_router)
elif api_app is not None:
    # “mescla” as rotas do FastAPI do src.api dentro deste app
    app.router.routes.extend(api_app.router.routes)


# 2) Static folders
if (WEB_DIR / "data").exists():
    app.mount("/data", StaticFiles(directory=str(WEB_DIR / "data")), name="data")

if (WEB_DIR / "icons").exists():
    app.mount("/icons", StaticFiles(directory=str(WEB_DIR / "icons")), name="icons")


# 3) Arquivos do front
@app.get("/app.js")
def serve_app_js():
    if not APP_JS.exists():
        raise HTTPException(status_code=404, detail="app.js not found in /web")
    return FileResponse(str(APP_JS), media_type="application/javascript")


@app.get("/sw.js")
def serve_sw_js():
    if not SW_JS.exists():
        raise HTTPException(status_code=404, detail="sw.js not found in /web")
    return FileResponse(str(SW_JS), media_type="application/javascript")


@app.get("/")
def serve_index():
    if not INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="index.html not found in /web")
    return FileResponse(str(INDEX_HTML), media_type="text/html")


# 4) Health (pra diagnosticar sem sofrimento)
@app.get("/health")
def health():
    return JSONResponse({
        "ok": True,
        "api_router_loaded": api_router is not None or api_app is not None,
        "api_import_error": api_import_error,
        "web_dir_exists": WEB_DIR.exists(),
        "data_dir_exists": (WEB_DIR / "data").exists(),
        "icons_dir_exists": (WEB_DIR / "icons").exists(),
        "index_exists": INDEX_HTML.exists(),
        "app_js_exists": APP_JS.exists(),
        "sw_js_exists": SW_JS.exists(),
    })


# 5) Fallback do SPA: só front. NÃO engolir rotas da API.
@app.get("/{path:path}")
def spa_fallback(path: str):
    blocked_prefixes = (
        "competitions",
        "predict",
        "leagues",
        "matches",
        "api",
        "data",
        "icons",
        "app.js",
        "sw.js",
        "health",
    )
    if path.startswith(blocked_prefixes):
        raise HTTPException(status_code=404, detail="Not Found")

    if not INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="index.html not found in /web")
    return FileResponse(str(INDEX_HTML), media_type="text/html")
