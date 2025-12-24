# src/api.py
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, HTTPException, Query

from src.live_fetch import fetch_upcoming_matches
from src.model import load_model

router = APIRouter()

MODELS_DIR = Path("data/models")

# Cache simples em memória (por processo)
# key = (code, max_matches) -> (created_ts, ttl, payload)
_CACHE: Dict[Tuple[str, int], Tuple[float, int, Dict[str, Any]]] = {}


def _now_ts() -> float:
    return time.time()


def _model_path(code: str) -> Path:
    return MODELS_DIR / f"{code}.joblib"


def _list_competitions() -> List[str]:
    if not MODELS_DIR.exists():
        return []
    return sorted([p.stem for p in MODELS_DIR.glob("*.joblib")])


def _safe_team_name(obj: Dict[str, Any]) -> str:
    name = (obj or {}).get("name")
    return str(name) if name else ""


@router.get("/health")
def health() -> Dict[str, Any]:
    comps = _list_competitions()
    return {
        "ok": True,
        "models_dir_exists": MODELS_DIR.exists(),
        "competitions_count": len(comps),
        "competitions": comps[:20],
    }


@router.get("/competitions")
def competitions() -> Dict[str, Any]:
    comps = _list_competitions()
    if not comps:
        raise HTTPException(
            status_code=500,
            detail="Nenhum modelo encontrado em data/models/*.joblib (competitions vazia).",
        )
    return {"competitions": comps, "count": len(comps)}


@router.get("/predict/{code}")
def predict(
    code: str,
    max_matches: int = Query(15, ge=1, le=200),
    ttl_seconds: int = Query(60, ge=0, le=3600),
    use_cache: bool = Query(True),
) -> Dict[str, Any]:
    # 1) Cache
    key = (code, max_matches)
    if use_cache and ttl_seconds > 0 and key in _CACHE:
        created_ts, ttl, payload = _CACHE[key]
        age = _now_ts() - created_ts
        if age <= ttl:
            payload = dict(payload)  # cópia
            payload["cache"] = {"hit": True, "age_s": int(age), "ttl_s": ttl}
            return payload

    # 2) Modelo
    mp = _model_path(code)
    if not mp.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Modelo não encontrado: {mp.as_posix()}",
        )
    model = load_model(str(mp))

    # 3) Jogos futuros via live_fetch
    try:
        data = fetch_upcoming_matches(code)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Falha ao buscar jogos: {e}")

    matches: List[Dict[str, Any]] = (data or {}).get("matches", []) or []

    preds: List[Dict[str, Any]] = []
    returned = 0

    for m in matches:
        home = _safe_team_name(m.get("homeTeam", {}))
        away = _safe_team_name(m.get("awayTeam", {}))
        if not home or not away:
            continue

        row: Dict[str, Any] = {
            "match_id": m.get("id"),
            "utcDate": m.get("utcDate"),
            "status": m.get("status"),
            "home": home,
            "away": away,
        }

        try:
            out = model.predict_1x2(home, away, max_goals=10)
            row["expected_goals"] = out.get("expected_goals")
            row["probabilities_1x2"] = out.get("probabilities_1x2")
        except Exception as e:
            # Não quebra a resposta inteira
            row["error"] = str(e)

        preds.append(row)
        returned += 1
        if returned >= max_matches:
            break

    payload: Dict[str, Any] = {
        "competition": code,
        "matches_fetched": len(matches),
        "returned": returned,
        "predictions": preds,
        "cache": {"hit": False, "age_s": 0, "ttl_s": int(ttl_seconds)},
    }

    # 4) Salva no cache
    if use_cache and ttl_seconds > 0:
        _CACHE[key] = (_now_ts(), int(ttl_seconds), payload)

    return payload
