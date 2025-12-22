from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, Query

from src.model import load_model, PoissonTeamModel

MODELS_DIR = Path("data/models")

app = FastAPI(title="Sports Prob Engine", version="1.0")

MODELS: Dict[str, PoissonTeamModel] = {}


def _load_all_models() -> Dict[str, PoissonTeamModel]:
    if not MODELS_DIR.exists():
        raise RuntimeError(f"Pasta não existe: {MODELS_DIR.resolve()}")

    models: Dict[str, PoissonTeamModel] = {}
    for p in MODELS_DIR.glob("*.joblib"):
        key = p.stem  # ex: "bundesliga", "premier-league"
        models[key] = load_model(str(p))
    return models


@app.on_event("startup")
def startup_load_models() -> None:
    global MODELS
    MODELS = _load_all_models()


def get_model_or_404(league: str) -> PoissonTeamModel:
    m = MODELS.get(league)
    if not m:
        raise HTTPException(
            status_code=404,
            detail=f"Liga '{league}' não encontrada. Use /leagues para ver as disponíveis.",
        )
    return m


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "models_loaded": list(MODELS.keys())}


@app.get("/leagues")
def leagues() -> Dict[str, Any]:
    return {"leagues": sorted(MODELS.keys()), "count": len(MODELS)}


@app.get("/teams")
def teams(league: str = Query(..., description="Ex: bundesliga, premier-league")) -> Dict[str, Any]:
    model = get_model_or_404(league)
    return {"league": league, "teams": model.teams, "count": len(model.teams)}


@app.get("/predict")
def predict(
    league: str = Query(..., description="Ex: bundesliga, premier-league"),
    home_team: str = Query(...),
    away_team: str = Query(...),
    max_goals: int = Query(10, ge=5, le=15),
) -> Dict[str, Any]:
    model = get_model_or_404(league)

    # validações simples (erro mais amigável)
    if home_team not in model.team_index:
        raise HTTPException(status_code=400, detail=f"home_team '{home_team}' não existe na liga {league}")
    if away_team not in model.team_index:
        raise HTTPException(status_code=400, detail=f"away_team '{away_team}' não existe na liga {league}")

    out = model.predict_1x2(home_team, away_team, max_goals=max_goals)
    out["league"] = league
    return out
