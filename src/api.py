from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

# Onde ficam as previsões já geradas (ex.: data/preds_live/BL1.json)
PREDS_DIR = Path("data/preds_live")

# Se tu também quiser listar modelos treinados (ex.: data/models/premier-league.joblib)
MODELS_DIR = Path("data/models")

# Códigos "curtos" (football-data) que teu front já usa
FD_CODES: List[str] = ["WC", "CL", "BL1", "DED", "BSA", "PD", "FL1", "ELC", "PPL", "EC", "SA", "PL"]

# Cache em memória para evitar ler arquivo toda hora
_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _load_pred_file(code: str) -> Dict[str, Any]:
    """
    Carrega um JSON de previsões de:
      data/preds_live/{CODE}.json
    """
    path = PREDS_DIR / f"{code}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Predictions file not found: {path.as_posix()}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse {path.as_posix()}: {e}")


def _list_model_stems() -> List[str]:
    """
    Retorna stems de modelos em data/models/*.joblib (ex.: premier-league)
    Só para aparecerem no dropdown, se existirem.
    """
    if not MODELS_DIR.exists():
        return []
    return sorted([p.stem for p in MODELS_DIR.glob("*.joblib")])


@router.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "preds_dir_exists": PREDS_DIR.exists(),
        "preds_files": sorted([p.name for p in PREDS_DIR.glob("*.json")]) if PREDS_DIR.exists() else [],
        "models_dir_exists": MODELS_DIR.exists(),
        "models": _list_model_stems(),
    }


@router.get("/competitions")
def competitions() -> Dict[str, Any]:
    """
    O front precisa disso para preencher o dropdown.
    Mantém compatibilidade devolvendo lista de strings.
    """
    comps: List[str] = []
    comps.extend(FD_CODES)

    # Se existirem previsões prontas com nomes diferentes, inclui também:
    if PREDS_DIR.exists():
        extra_from_preds = sorted([p.stem for p in PREDS_DIR.glob("*.json")])
        for c in extra_from_preds:
            if c not in comps:
                comps.append(c)

    # E também modelos (se tu quiser)
    for m in _list_model_stems():
        if m not in comps:
            comps.append(m)

    return {"competitions": comps, "count": len(comps)}


@router.get("/predict")
def predict_query(
    competition: str = Query(..., description="Ex: BL1, PL, premier-league"),
    max_matches: int = Query(15, ge=1, le=200),
    ttl_seconds: int = Query(60, ge=0, le=3600),
    use_cache: bool = Query(True),
) -> Dict[str, Any]:
    """
    Endpoint alternativo caso teu front chame /predict?competition=BL1...
    """
    return _predict_common(competition, max_matches, ttl_seconds, use_cache)


@router.get("/predict/{competition}")
def predict_path(
    competition: str,
    max_matches: int = Query(15, ge=1, le=200),
    ttl_seconds: int = Query(60, ge=0, le=3600),
    use_cache: bool = Query(True),
) -> Dict[str, Any]:
    """
    Endpoint alternativo caso teu front chame /predict/BL1?...
    """
    return _predict_common(competition, max_matches, ttl_seconds, use_cache)


@router.get("/{competition}")
def predict_root_competition(
    competition: str,
    max_matches: int = Query(15, ge=1, le=200),
    ttl_seconds: int = Query(60, ge=0, le=3600),
    use_cache: bool = Query(True),
) -> Dict[str, Any]:
    """
    ESTE é o mais importante para o teu print:
    o front está chamando /BL1?max_matches=...
    então a gente atende aqui.
    """
    return _predict_common(competition, max_matches, ttl_seconds, use_cache)


def _predict_common(competition: str, max_matches: int, ttl_seconds: int, use_cache: bool) -> Dict[str, Any]:
    code = competition.strip()

    now = time.time()
    if use_cache and ttl_seconds > 0:
        hit = _CACHE.get(code)
        if hit:
            ts, payload = hit
            if (now - ts) <= ttl_seconds:
                return _trim_payload(payload, max_matches)

    payload = _load_pred_file(code)
    if ttl_seconds > 0:
        _CACHE[code] = (now, payload)

    return _trim_payload(payload, max_matches)


def _trim_payload(payload: Dict[str, Any], max_matches: int) -> Dict[str, Any]:
    """
    O teu predict_live.py gera payload com 'predictions': [...]
    Aqui a gente corta para o front não receber 500 jogos.
    """
    out = dict(payload)
    preds = out.get("predictions") or []
    if isinstance(preds, list):
        out["predictions"] = preds[:max_matches]
        out["count"] = len(out["predictions"])
    return out
