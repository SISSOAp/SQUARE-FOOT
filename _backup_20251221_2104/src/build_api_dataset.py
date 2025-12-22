import os
import pandas as pd

from src.live_fetch import fetch_competition_matches

def build_comp_csv(code: str, out_path: str):
    data = fetch_competition_matches(code)  # sem status => pega histórico disponível
    matches = data.get("matches", [])

    rows = []
    for m in matches:
        # só pega jogos finalizados com placar
        if m.get("status") != "FINISHED":
            continue

        score = m.get("score", {}).get("fullTime", {})
        hg = score.get("home")
        ag = score.get("away")
        if hg is None or ag is None:
            continue

        rows.append({
            "date": (m.get("utcDate") or "")[:10],
            "home_team": m["homeTeam"]["name"],
            "away_team": m["awayTeam"]["name"],
            "home_goals": hg,
            "away_goals": ag,
        })

    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    print(f"OK: {code} -> {out_path} | linhas={len(df)} | times={len(set(df.home_team) | set(df.away_team))}")

if __name__ == "__main__":
    os.makedirs("data/api_processed", exist_ok=True)
    build_comp_csv("BL1", "data/api_processed/BL1.csv")
