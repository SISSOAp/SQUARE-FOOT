from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional, List
import json
import time

from fastapi import APIRouter, HTTPException, Query

from src.model import load_model, PoissonTeamModel

router = APIRouter()

MODELS_DIR = Path("data/models")
FIXTURES_DIR = Path("data/fixtures")  # opcional (se existir, lê jogos daqui)

MODELS: Dict[str, PoissonTeamModel] = {}

# cache simples em memória
_CACHE: Dict[str, Dict[str, Any]] = {}  # key -> {"ts": float, "data": dict}


def _load_all_models() -> Dict[str, PoissonTeamModel]:
    if not MODELS_DIR.exists():
        # não derruba import; derruba quando tentar usar
        return {}

    models: Dict[str, PoissonTeamModel] = {}
    for p in MODELS_DIR.glob("*.joblib"):
        models[p.stem] = load_model(str(p))
    return models


@router.on_event("startup")
def startup_load_models() -> None:
    global MODELS
    MODELS = _load_all_models()


def _get_model_or_404(code: str) -> PoissonTeamModel:
    m = MODELS.get(code)
    if not m:
        raise HTTPException(
            status_code=404,
            detail=f"Competição '{code}' não encontrada. Modelos disponíveis: {sorted(MODELS.keys())}",
        )
    return m


@router.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "models_loaded": sorted(MODELS.keys())}


@router.get("/competitions")
def competitions() -> Dict[str, Any]:
    # o front só precisa de um array em competitions[]
    return {"competitions": sorted(MODELS.keys()), "count": len(MODELS)}


def _read_fixtures(code: str) -> List[Dict[str, Any]]:
    """
    Opções suportadas (se você quiser plugar jogos):
    - data/fixtures/{code}.json   (lista de jogos, ou {matches:[...]}, ou {data:[...]})
    Caso não exista, devolve [] (o app não quebra; só mostra 0 jogos).
    """
    p = FIXTURES_DIR / f"{code}.json"
    if not p.exists():
        return []

    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            if isinstance(raw.get("matches"), list):
                return raw["matches"]
            if isinstance(raw.get("data"), list):
                return raw["data"]
        return []
    except Exception:
        return []


def _normalize_team_name(x: Any) -> str:
    if not x:
        return ""
    # aceita formatos comuns (football-data etc.)
    if isinstance(x, dict):
        return (x.get("name") or x.get("shortName") or x.get("tla") or "").strip()
    return str(x).strip()


@router.get("/predict/{code}")
def predict_competition(
    code: str,
    max_matches: int = Query(10, ge=1, le=100),
    ttl_seconds: int = Query(60, ge=0, le=3600),
    use_cache: bool = Query(True),
) -> Dict[str, Any]:
    """
    Formato de resposta pensado para o seu app.js:
    - competitions vem de /competitions
    - predict/{code} retorna meta + lista predictions
    """

    cache_key = f"{code}:{max_matches}:{ttl_seconds}"
    now = time.time()

    if use_cache and ttl_seconds > 0:
        hit = _CACHE.get(cache_key)
        if hit and (now - hit["ts"] <= ttl_seconds):
            data = hit["data"]
            data["cache"] = "HIT"
            data["ttl_seconds"] = ttl_seconds
            return data

    model = _get_model_or_404(code)

    matches = _read_fixtures(code)
    api_matches = len(matches)

    # limita
    matches = matches[:max_matches]

    predictions: List[Dict[str, Any]] = []
    for m in matches:
        # tenta extrair campos em formatos comuns
        utc_date = m.get("utcDate") or m.get("date") or m.get("kickoff") or None

        home = _normalize_team_name(m.get("homeTeam") or m.get("home") or m.get("HomeTeam"))
        away = _normalize_team_name(m.get("awayTeam") or m.get("away") or m.get("AwayTeam"))

        # se não conseguir nomes, pula
        if not home or not away:
            continue

        # se time não existe no modelo, pula (evita 500)
        if home not in model.team_index or away not in model.team_index:
            continue

        out = model.predict_1x2(home, away, max_goals=10)

        predictions.append(
            {
                "utcDate": utc_date,
                "competitionName": code,
                "home": home,
                "away": away,
                "probabilities_1x2": out.get("probabilities_1x2", {}),
                "expected_goals": out.get("expected_goals", {}),
                "top_scorelines": out.get("top_scorelines", []),
                # mantém o bruto se você quiser debugar:
                "raw": out,
            }
        )

    data = {
        "competition": code,
        "api_matches": api_matches,
        "shown": len(predictions),
        "cache": "MISS",
        "ttl_seconds": ttl_seconds,
        "predictions": predictions,
    }

    if use_cache and ttl_seconds > 0:
        _CACHE[cache_key] = {"ts": now, "data": data}

    return data
