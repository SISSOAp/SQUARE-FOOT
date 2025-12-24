from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Importa o router do src/api.py (tem que existir "router" lá)
try:
    from src.api import router as api_router  # type: ignore
except Exception as e:
    api_router = None
    _api_import_error = str(e)

app = FastAPI(title="SQUARE FOOT", version="1.6")

# Paths
BASE_DIR = Path(__file__).resolve().parent      # .../src
ROOT_DIR = BASE_DIR.parent                      # .../
WEB_DIR = ROOT_DIR / "web"                      # .../web

INDEX_HTML = WEB_DIR / "index.html"
APP_JS = WEB_DIR / "app.js"
SW_JS = WEB_DIR / "sw.js"

# Debug opcional (para ver no /health se o router importou)
@app.get("/health")
def health():
    return {
        "ok": True,
        "api_router_loaded": api_router is not None,
        "web_dir_exists": WEB_DIR.exists(),
        "data_dir_exists": (WEB_DIR / "data").exists(),
        "icons_dir_exists": (WEB_DIR / "icons").exists(),
        "api_import_error": None if api_router is not None else _api_import_error,
    }

# 1) Rotas da API (primeiro)
if api_router is not None:
    app.include_router(api_router)

# 2) Pastas estáticas
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

# 4) Fallback SPA
@app.get("/{path:path}")
def spa_fallback(path: str):
    blocked_prefixes = (
        "competitions",
        "predict",
        "leagues",
        "matches",
        "card",
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
