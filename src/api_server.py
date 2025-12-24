from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


# -----------------------------------------------------------------------------
# Paths (repo)
# -----------------------------------------------------------------------------
# Este arquivo está em: repo_root/src/api_server.py
REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "web"

INDEX_HTML = WEB_DIR / "index.html"
APP_JS = WEB_DIR / "app.js"
SW_JS = WEB_DIR / "sw.js"
STYLES_CSS = WEB_DIR / "styles.css"

DATA_DIR = WEB_DIR / "data"
ICONS_DIR = WEB_DIR / "icons"
EXTRA_STATS_JSON = DATA_DIR / "extra-stats.json"


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI(title="SQUARE FOOT", version="1.6")


# -----------------------------------------------------------------------------
# Static mounts
# -----------------------------------------------------------------------------
# /data/extra-stats.json
if DATA_DIR.exists():
    app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")

# /icons/*
if ICONS_DIR.exists():
    app.mount("/icons", StaticFiles(directory=str(ICONS_DIR)), name="icons")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _safe_read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(str(path))
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _extract_competitions(extra_stats: Any) -> List[Dict[str, str]]:
    """
    Tenta ser robusto com o formato do extra-stats.json.
    Retorna lista de {code, name}.
    """
    comps: List[Dict[str, str]] = []

    # Caso A: {"competitions": [...]}
    if isinstance(extra_stats, dict) and isinstance(extra_stats.get("competitions"), list):
        raw_list = extra_stats["competitions"]
        for item in raw_list:
            if isinstance(item, dict):
                code = str(item.get("code") or item.get("id") or item.get("key") or "").strip()
                name = str(item.get("name") or item.get("label") or code).strip()
                if code:
                    comps.append({"code": code, "name": name})

    # Caso B: dict com chaves sendo códigos
    elif isinstance(extra_stats, dict):
        # ex: {"PL": {...}, "SA": {...}}
        for k, v in extra_stats.items():
            if isinstance(k, str) and k.isupper() and len(k) <= 8:
                name = k
                if isinstance(v, dict):
                    name = str(v.get("name") or v.get("label") or k)
                comps.append({"code": k, "name": name})

    # Caso C: lista direto
    elif isinstance(extra_stats, list):
        for item in extra_stats:
            if isinstance(item, dict):
                code = str(item.get("code") or item.get("id") or item.get("key") or "").strip()
                name = str(item.get("name") or item.get("label") or code).strip()
                if code:
                    comps.append({"code": code, "name": name})

    # Remove duplicados e ordena
    seen = set()
    uniq = []
    for c in comps:
        if c["code"] not in seen:
            seen.add(c["code"])
            uniq.append(c)

    uniq.sort(key=lambda x: x["name"].lower())
    return uniq


# -----------------------------------------------------------------------------
# Frontend routes (arquivos)
# -----------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def serve_index():
    if not INDEX_HTML.exists():
        raise HTTPException(status_code=500, detail="index.html not found in /web")
    return FileResponse(INDEX_HTML)


@app.get("/app.js", include_in_schema=False)
def serve_app_js():
    if not APP_JS.exists():
        raise HTTPException(status_code=404, detail="app.js not found")
    return FileResponse(APP_JS, media_type="application/javascript")


@app.get("/sw.js", include_in_schema=False)
def serve_sw_js():
    if not SW_JS.exists():
        raise HTTPException(status_code=404, detail="sw.js not found")
    return FileResponse(SW_JS, media_type="application/javascript")


@app.get("/styles.css", include_in_schema=False)
def serve_styles():
    if not STYLES_CSS.exists():
        # não é obrigatório existir
        raise HTTPException(status_code=404, detail="styles.css not found")
    return FileResponse(STYLES_CSS, media_type="text/css")


# -----------------------------------------------------------------------------
# API routes (o seu app.js chama isso)
# -----------------------------------------------------------------------------
@app.get("/competitions")
def competitions():
    """
    Retorna no formato que o app.js espera:
    { "competitions": [ { "code": "PL", "name": "Premier League" }, ... ] }
    """
    try:
        extra = _safe_read_json(EXTRA_STATS_JSON)
        comps = _extract_competitions(extra)
        return {"competitions": comps}
    except FileNotFoundError:
        # Se o arquivo não existir no deploy, pelo menos não quebra o front com 404.
        return {"competitions": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load competitions: {e}")


@app.get("/predict/{code}")
def predict(
    code: str,
    max_matches: int = Query(15, ge=1, le=200),
    ttl_seconds: int = Query(60, ge=0, le=3600),
    use_cache: bool = Query(True),
):
    """
    IMPORTANTE:
    - Seu front chama /predict/{code}?max_matches=...&ttl_seconds=...&use_cache=...
    - Se você ainda não tem o motor de previsão ligado aqui, este endpoint devolve
      um payload "válido" (sem 404) para o front funcionar.
    - Depois, quando você quiser plugar o modelo real, é aqui que liga.
    """

    # 1) Tenta usar um módulo seu (se existir) sem quebrar deploy
    #    Ajuste o import conforme seu projeto, se você tiver função pronta.
    try:
        # Exemplo: se você tiver algo como src/predict_live.py com função predict_payload(...)
        from . import predict_live  # type: ignore

        if hasattr(predict_live, "predict_payload"):
            payload = predict_live.predict_payload(
                code=code,
                max_matches=max_matches,
                ttl_seconds=ttl_seconds,
                use_cache=use_cache,
            )
            return payload

        # Se tiver função chamada "predict" que já retorna dict
        if hasattr(predict_live, "predict"):
            payload = predict_live.predict(
                code=code,
                max_matches=max_matches,
                ttl_seconds=ttl_seconds,
                use_cache=use_cache,
            )
            return payload

    except Exception:
        # Se falhar import/exec, cai no fallback abaixo (mas não devolve 404)
        pass

    # 2) Fallback (não quebra o site)
    # Monte um payload seguro: o front vai mostrar "0 jogos" mas não vai sumir.
    return {
        "competition": code,
        "from_cache": False,
        "ttl_seconds": ttl_seconds,
        "max_matches": max_matches,
        "matches": [],
        "note": "Predict engine not wired; endpoint is alive to avoid 404.",
    }


# -----------------------------------------------------------------------------
# SPA fallback (se você clicar em /leagues no browser, ele deve abrir o front)
# -----------------------------------------------------------------------------
@app.get("/{path:path}", include_in_schema=False)
def spa_fallback(path: str):
    """
    Qualquer rota desconhecida no backend vira index.html
    (pra não aparecer Not Found ao abrir links diretos).
    """
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)
    raise HTTPException(status_code=404, detail="Not Found")
