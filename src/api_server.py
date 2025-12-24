from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Se sua API real está em src/api.py (muito provável pelo teu print), ela entra aqui:
# Esse router deve expor /competitions e /predict (ou /leagues etc).
try:
    from src.api import router as api_router  # type: ignore
except Exception:
    api_router = None


app = FastAPI(title="SQUARE FOOT", version="1.6")

# Paths
# src/api_server.py -> BASE_DIR = .../src
BASE_DIR = Path(__file__).resolve().parent
# repo root = .../
ROOT_DIR = BASE_DIR.parent
# web folder = .../web
WEB_DIR = ROOT_DIR / "web"

INDEX_HTML = WEB_DIR / "index.html"
APP_JS = WEB_DIR / "app.js"
SW_JS = WEB_DIR / "sw.js"

# 1) Inclui as rotas de API ANTES de qualquer "fallback" do front
if api_router is not None:
    app.include_router(api_router)

# 2) Static folders (para servir /data/extra-stats.json e /icons/*)
if (WEB_DIR / "data").exists():
    app.mount("/data", StaticFiles(directory=str(WEB_DIR / "data")), name="data")

if (WEB_DIR / "icons").exists():
    app.mount("/icons", StaticFiles(directory=str(WEB_DIR / "icons")), name="icons")

# 3) Arquivos específicos do front (para garantir que /app.js e /sw.js sempre existam)
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


# 4) Fallback do SPA: só serve index.html para rotas do FRONT.
# IMPORTANTÍSSIMO: não pode engolir as rotas da API.
@app.get("/{path:path}")
def spa_fallback(path: str):
    # Bloqueia caminhos que NUNCA devem virar index.html
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
    )
    if path.startswith(blocked_prefixes):
        # Se caiu aqui, é porque a rota da API realmente não existe -> 404
        raise HTTPException(status_code=404, detail="Not Found")

    if not INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="index.html not found in /web")
    return FileResponse(str(INDEX_HTML), media_type="text/html")
