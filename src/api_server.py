# src/api_server.py
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api import router as api_router  # <-- agora funciona (api.py virou router puro)

app = FastAPI(title="SQUARE FOOT", version="1.6")

BASE_DIR = Path(__file__).resolve().parent       # .../src
ROOT_DIR = BASE_DIR.parent                       # repo root
WEB_DIR = ROOT_DIR / "web"

INDEX_HTML = WEB_DIR / "index.html"
APP_JS = WEB_DIR / "app.js"
SW_JS = WEB_DIR / "sw.js"

# 1) API routes
app.include_router(api_router)

# 2) Static folders
if (WEB_DIR / "data").exists():
    app.mount("/data", StaticFiles(directory=str(WEB_DIR / "data")), name="data")

if (WEB_DIR / "icons").exists():
    app.mount("/icons", StaticFiles(directory=str(WEB_DIR / "icons")), name="icons")

def _no_cache_headers() -> dict:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    }

@app.get("/app.js")
def serve_app_js():
    if not APP_JS.exists():
        raise HTTPException(status_code=404, detail="app.js not found in /web")
    return FileResponse(str(APP_JS), media_type="application/javascript", headers=_no_cache_headers())

@app.get("/sw.js")
def serve_sw_js():
    if not SW_JS.exists():
        raise HTTPException(status_code=404, detail="sw.js not found in /web")
    return FileResponse(str(SW_JS), media_type="application/javascript", headers=_no_cache_headers())

@app.get("/")
def serve_index():
    if not INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="index.html not found in /web")
    return FileResponse(str(INDEX_HTML), media_type="text/html", headers=_no_cache_headers())

# 4) SPA fallback (não engole API nem static)
@app.get("/{path:path}")
def spa_fallback(path: str):
    blocked_prefixes = (
        "competitions",
        "predict",
        "health",
        "data",
        "icons",
        "app.js",
        "sw.js",
    )
    if path.startswith(blocked_prefixes):
        raise HTTPException(status_code=404, detail="Not Found")

    if not INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="index.html not found in /web")
    return FileResponse(str(INDEX_HTML), media_type="text/html", headers=_no_cache_headers())
