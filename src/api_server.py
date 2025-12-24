from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/leagues")
def leagues():
    # Ajuste aqui se você já tiver uma função/constante de ligas
    # Por enquanto, mínimo para não quebrar o front:
    return [
        {"code": "PL", "name": "Premier League"},
        {"code": "SA", "name": "Serie A"},
        {"code": "PD", "name": "LaLiga"},
        {"code": "BL1", "name": "Bundesliga"},
        {"code": "FL1", "name": "Ligue 1"},
        {"code": "CL", "name": "Champions League"},
        {"code": "WC", "name": "World Cup"},
    ]

@router.get("/matches")
def matches(code: str, status: str = "SCHEDULED", limit: int = 15):
    # Se você já tinha lógica de matches, você vai recolocar depois.
    # Agora é só para garantir que o endpoint existe e responde JSON.
    return {"code": code, "status": status, "limit": limit, "matches": []}

@router.get("/card")
def card(code: str, match_id: int):
    # Mesmo caso: endpoint mínimo para o front não morrer.
    return {"code": code, "match_id": match_id, "card": None}

@router.get("/competitions")
def competitions():
    # Alguns front-ends chamam /competitions; deixa compatível também.
    return leagues()

@router.get("/predict")
def predict(code: str, match_id: int):
    # Placeholder: devolve 501 pra ficar explícito que ainda não está implementado.
    raise HTTPException(status_code=501, detail="predict not implemented yet")
