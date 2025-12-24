# src/api.py
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.live_fetch import fetch_upcoming_matches
from src.model import load_model

router = APIRouter()

# Competitions que teu front espera (pelos teus prints anteriores)
CODES: List[str] = ["WC", "CL", "BL1", "DED", "BSA", "PD", "FL1", "ELC", "PPL", "EC", "SA", "PL"]

# Cache simples em memória (opcional, mas ajuda no Render)
_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TS: Dict[str, float] = {}

def _cache_key(code: str, max_matches: int, status: str) -> str:
    return f"{code}|{max_matches}|{status}"

def _get_model_path(code: str) -> str:
    # Mantém o padrão que tu já tá usando
    return f"data/models/{code}.joblib"

def _load_model_or_404(code: str):
    model_path = _get_model_path(code)
    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail=f"Model not found for {code}: {model_path}")
    return load_model(model_path)

@router.get("/competitions")
def competitions() -> Dict[str, Any]:
    return {"competitions": CODES, "count": len(CODES)}

@router.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "competitions": CODES,
        "models_dir": os.path.abspath("data/models"),
        "models_found": [c for c in CODES if os.path.exists(_get_model_path(c))],
    }

@router.get("/predict/{code}")
def predict_code(
    code: str,
    max_matches: int = Query(15, ge=1, le=50),
    ttl_seconds: int = Query(60, ge=0, le=3600),
    use_cache: bool = Query(True),
    status: str = Query("SCHEDULED"),
) -> Dict[str, Any]:
    """
    Endpoint exatamente no formato que o front está chamando:
    /predict/{CODE}?max_matches=15&ttl_seconds=60&use_cache=true

    Retorna JSON com matches e probabilidades.
    """
    code = code.strip()
    if code not in CODES:
        raise HTTPException(status_code=404, detail=f"Unknown competition code: {code}")

    key = _cache_key(code, max_matches, status)
    now = time.time()

    if use_cache and ttl_seconds > 0:
        ts = _CACHE_TS.get(key)
        if ts is not None and (now - ts) < ttl_seconds:
            payload = _CACHE.get(key)
            if payload is not None:
                payload["cache"] = "HIT"
                payload["cache_age_seconds"] = int(now - ts)
                payload["ttl_seconds"] = ttl_seconds
                return payload

    # 1) Busca jogos futuros da API externa
    data = fetch_upcoming_matches(code)
    matches: List[Dict[str, Any]] = (data or {}).get("matches", []) or []

    # Filtro por status, se a tua live_fetch trouxer vários
    if status:
        matches = [m for m in matches if (m.get("status") == status)]

    # Limite
    matches = matches[:max_matches]

    # 2) Carrega o modelo daquela competição
    model = _load_model_or_404(code)

    # 3) Calcula probabilidades por jogo
    out_matches: List[Dict[str, Any]] = []

    for m in matches:
        home_obj = m.get("homeTeam") or {}
        away_obj = m.get("awayTeam") or {}
        home = home_obj.get("name")
        away = away_obj.get("name")

        # se vier incompleto, pula
        if not home or not away:
            continue

        try:
            pred = model.predict_1x2(home, away, max_goals=10)
            expected_goals = pred.get("expected_goals")
            probs = pred.get("probabilities_1x2")
        except Exception as e:
            out_matches.append(
                {
                    "match_id": m.get("id"),
                    "utcDate": m.get("utcDate"),
                    "status": m.get("status"),
                    "home": home,
                    "away": away,
                    "error": str(e),
                }
            )
            continue

        out_matches.append(
            {
                "match_id": m.get("id"),
                "utcDate": m.get("utcDate"),
                "status": m.get("status"),
                "home": home,
                "away": away,
                "expected_goals": expected_goals,
                "probabilities_1x2": probs,
            }
        )

    payload: Dict[str, Any] = {
        "competition": code,
        "matches_fetched": len(matches),
        "count": len(out_matches),
        "matches": out_matches,
        "model_path": _get_model_path(code),
        "cache": "MISS",
        "ttl_seconds": ttl_seconds,
    }

    if use_cache and ttl_seconds > 0:
        _CACHE[key] = payload
        _CACHE_TS[key] = now

    return payload
