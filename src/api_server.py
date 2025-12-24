from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Tentativa de importar o router da API (rotas usadas pelo frontend)
api_router = None
api_import_error: Optional[str] = None
try:
    from src.api import router as api_router  # type: ignore
except Exception as e:
    api_router = None
    api_import_error = f"{type(e).__name__}: {e}"

app = FastAPI(title="SQUARE FOOT", version="1.6")

# Paths
# src/api_server.py -> BASE_DIR = .../src
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
WEB_DIR = ROOT_DIR / "web"

INDEX_HTML = WEB_DIR / "index.html"
APP_JS = WEB_DIR / "app.js"
SW_JS = WEB_DIR / "sw.js"

# 1) Inclui rotas da API (ANTES do fallback)
if api_router is not None:
    app.include_router(api_router)

# 2) Servir pastas estáticas (data/icons)
DATA_DIR = WEB_DIR / "data"
ICONS_DIR = WEB_DIR / "icons"

if DATA_DIR.exists():
    app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")

if ICONS_DIR.exists():
    app.mount("/icons", StaticFiles(directory=str(ICONS_DIR)), name="icons")

# 3) Arquivos específicos do front
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

# Health bem explícito (pra não ficar no escuro)
@app.get("/health")
def health() -> JSONResponse:
    payload: Dict[str, Any] = {
        "ok": True,
        "api_router_loaded": api_router is not None,
        "api_import_error": api_import_error,
        "web_dir": str(WEB_DIR),
        "web_dir_exists": WEB_DIR.exists(),
        "index_exists": INDEX_HTML.exists(),
        "app_js_exists": APP_JS.exists(),
        "sw_js_exists": SW_JS.exists(),
        "data_dir_exists": DATA_DIR.exists(),
        "icons_dir_exists": ICONS_DIR.exists(),
    }
    return JSONResponse(payload)

# 4) Fallback do SPA (NÃO pode engolir a API)
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
