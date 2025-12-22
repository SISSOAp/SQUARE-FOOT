from src.live_fetch import fetch_competition_matches
from src.model import load_model

# mapeia competição -> arquivo do modelo treinado
MODEL_BY_COMP = {
    "CL":  "data/models/CL.joblib",
    "BL1": "data/models/BL1.joblib",
    "DED": "data/models/DED.joblib",
    "BSA": "data/models/BSA.joblib",
    "PD":  "data/models/PD.joblib",
    "FL1": "data/models/FL1.joblib",
    "ELC": "data/models/ELC.joblib",
    "PPL": "data/models/PPL.joblib",
    "EC":  "data/models/EC.joblib",
    "SA":  "data/models/SA.joblib",
    "PL":  "data/models/PL.joblib",
}



def main():
    for code in MODEL_BY_COMP.keys():
        try:
            run_competition(code)
            print()  # linha em branco entre competições
        except Exception as e:
            print(f"[ERRO] {code}: {e}")
            print()

    model_path = MODEL_BY_COMP.get(code)
    if not model_path:
        raise RuntimeError(f"Sem modelo mapeado para {code}. Adicione em MODEL_BY_COMP.")

    model = load_model(model_path)

    data = fetch_competition_matches(code, status="SCHEDULED")
    matches = data.get("matches", [])

    print(f"Competição {code} | próximos jogos: {len(matches)}")
    for m in matches[:10]:
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]

        # se o nome do time não bater 100% com o que o modelo conhece, isso pode dar KeyError
        pred = model.predict_1x2(home, away, max_goals=10)

        p = pred["probabilities_1x2"]
        print(f"{home} vs {away} | H={p['home_win']:.3f} D={p['draw']:.3f} A={p['away_win']:.3f}")

if __name__ == "__main__":
    main()
