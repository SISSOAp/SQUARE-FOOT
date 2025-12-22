# src/predict_live.py
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.live_fetch import fetch_upcoming_matches
from src.model import load_model


# Use exatamente os códigos que apareceram no seu print do site
CODES = ["WC", "CL", "BL1", "DED", "BSA", "PD", "FL1", "ELC", "PPL", "EC", "SA", "PL"]

MAX_MATCHES_TO_PRINT = 10  # quantos jogos mostrar na tela por competição
MAX_GOALS_TRUNC = 10       # truncagem da matriz Poisson


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_team_name(obj: Dict[str, Any]) -> str:
    # futebol-data.org normalmente vem {"homeTeam":{"name":...}}
    name = (obj or {}).get("name")
    return str(name) if name else "UNKNOWN_TEAM"


def run_competition(code: str) -> Dict[str, Any]:
    # 1) Puxa jogos futuros
    data = fetch_upcoming_matches(code)
    matches: List[Dict[str, Any]] = data.get("matches", []) or []

    print(f"\nCompetição {code} | próximos jogos: {len(matches)}")

    # 2) Carrega modelo
    model_path = f"data/models/{code}.joblib"
    if not os.path.exists(model_path):
        print(f"[SKIP] {code}: modelo não encontrado em {model_path}")
        return {
            "competition": code,
            "generated_at": _now_iso(),
            "model_path": model_path,
            "error": "model_not_found",
            "predictions": [],
        }

    model = load_model(model_path)

    # 3) Predições
    preds: List[Dict[str, Any]] = []
    shown = 0

    for m in matches:
        home = _safe_team_name(m.get("homeTeam", {}))
        away = _safe_team_name(m.get("awayTeam", {}))

        # alguns jogos podem vir sem time (muito raro); se vier, pula
        if home == "UNKNOWN_TEAM" or away == "UNKNOWN_TEAM":
            continue

        try:
            out = model.predict_1x2(home, away, max_goals=MAX_GOALS_TRUNC)
        except KeyError as e:
            # time não existe no modelo (ex.: recém-promovido e sem histórico no dataset)
            preds.append({
                "match_id": m.get("id"),
                "utcDate": m.get("utcDate"),
                "home": home,
                "away": away,
                "error": f"unknown_team: {str(e)}",
            })
            continue

        pred_row = {
            "match_id": m.get("id"),
            "utcDate": m.get("utcDate"),
            "status": m.get("status"),
            "home": home,
            "away": away,
            "expected_goals": out.get("expected_goals"),
            "probabilities_1x2": out.get("probabilities_1x2"),
        }
        preds.append(pred_row)

        # print na tela só para os primeiros N jogos
        if shown < MAX_MATCHES_TO_PRINT:
            p = pred_row["probabilities_1x2"]
            print(f"{home} vs {away} | H={p['home_win']:.3f} D={p['draw']:.3f} A={p['away_win']:.3f}")
            shown += 1

    return {
        "competition": code,
        "generated_at": _now_iso(),
        "model_path": model_path,
        "matches_fetched": len(matches),
        "predictions": preds,
    }


def main() -> None:
    os.makedirs("data/preds_live", exist_ok=True)

    total_ok = 0
    for code in CODES:
        try:
            payload = run_competition(code)
            out_path = f"data/preds_live/{code}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            total_ok += 1
        except Exception as e:
            print(f"[ERRO] {code}: {e}")

    print(f"\nFinalizado. JSON gerados em: data/preds_live/ | competições processadas: {total_ok}/{len(CODES)}")


if __name__ == "__main__":
    main()
