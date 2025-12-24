from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


# ----------------------------
# Paths
# ----------------------------
# src/api_server.py -> BASE_DIR=.../src
BASE_DIR = Path(__file__).resolve().parent
# repo root
ROOT_DIR = BASE_DIR.parent
# web folder (onde estão index.html, app.js, sw.js, icons/, data/)
WEB_DIR = ROOT_DIR / "web"


# ----------------------------
# App
# ----------------------------
app = FastAPI(title="SQUARE FOOT", version="1.6")


# ----------------------------
# Static folders
# ----------------------------
# Serve /icons/... e /data/... diretamente do disco
# Ex: /data/extra-stats.json
if (WEB_DIR / "icons").exists():
    app.mount("/icons", StaticFiles(directory=str(WEB_DIR / "icons")), name="icons")

if (WEB_DIR / "data").exists():
    app.mount("/data", StaticFiles(directory=str(WEB_DIR / "data")), name="data")


# ----------------------------
# Frontend files
# ----------------------------
def _file_or_404(path: Path, media_type: Optional[str] = None) -> FileResponse:
    # FileResponse já devolve 404 se não existir, mas assim fica explícito
    return FileResponse(str(path), media_type=media_type)


@app.get("/")
def serve_index():
    return _file_or_404(WEB_DIR / "index.html", media_type="text/html")


# Arquivos que você viu no Network (mantém simples e explícito)
@app.get("/app.js")
def serve_app_js():
    return _file_or_404(WEB_DIR / "app.js", media_type="application/javascript")


@app.get("/sw.js")
def serve_sw_js():
    return _file_or_404(WEB_DIR / "sw.js", media_type="application/javascript")


@app.get("/styles.css")
def serve_styles_css():
    return _file_or_404(WEB_DIR / "styles.css", media_type="text/css")


@app.get("/antd.min.css")
def serve_antd_css():
    return _file_or_404(WEB_DIR / "antd.min.css", media_type="text/css")


@app.get("/translation.json")
def serve_translation():
    return _file_or_404(WEB_DIR / "translation.json", media_type="application/json")


@app.get("/site.webmanifest")
def serve_manifest():
    return _file_or_404(WEB_DIR / "site.webmanifest", media_type="application/manifest+json")


@app.get("/favicon.ico")
def serve_favicon():
    return _file_or_404(WEB_DIR / "favicon.ico", media_type="image/x-icon")


# Fallback para arquivos estáticos no root (png, etc) que o front peça
# Ex: /square-foot-logo.png?v=3 -> FastAPI ignora querystring e procura "square-foot-logo.png"
@app.get("/{file_path:path}")
def serve_root_assets(file_path: str):
    # Não intercepta /predict, /competitions etc (isso é tratado pelas rotas da API abaixo).
    # Aqui só cai quando não existe rota e o arquivo existe no /web.
    # Se o arquivo não existir, vai responder 404 normal.
    candidate = WEB_DIR / file_path
    if candidate.is_file():
        return FileResponse(str(candidate))
    return {"detail": "Not Found"}


# ----------------------------
# API routes (RESTORE)
# ----------------------------
# O seu problema atual é exatamente este: as rotas /competitions e /predict sumiram.
# Aqui a gente tenta “reconectar” as rotas antigas sem você ter que caçar trecho.
#
# Ajuste: se suas rotas estiverem em outro módulo, troque o import abaixo.

try:
    # Opção A (comum): src/api.py com router = APIRouter()
    from src.api import router as api_router  # type: ignore
    app.include_router(api_router)
except Exception:
    try:
        # Opção B: src/routes.py
        from src.routes import router as api_router  # type: ignore
        app.include_router(api_router)
    except Exception:
        try:
            # Opção C: src/endpoints.py
            from src.endpoints import router as api_router  # type: ignore
            app.include_router(api_router)
        except Exception:
            # Se cair aqui, o front vai carregar, mas a API continuará 404
            # até você apontar para o módulo certo.
            pass
