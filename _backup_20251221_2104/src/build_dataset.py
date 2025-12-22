import glob
import os
import pandas as pd

OUT = "data/processed/matches_all.csv"

def normalize_eu_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    col_map = {}
    for c in df.columns:
        c2 = c.strip().lower()
        if c2 in ["date"]:
            col_map[c] = "date"
        elif c2 in ["hometeam", "home_team", "home"]:
            col_map[c] = "home_team"
        elif c2 in ["awayteam", "away_team", "away"]:
            col_map[c] = "away_team"
        elif c2 in ["fthg", "homegoals", "home_goals", "hg"]:
            col_map[c] = "home_goals"
        elif c2 in ["ftag", "awaygoals", "away_goals", "ag"]:
            col_map[c] = "away_goals"

    df = df.rename(columns=col_map)

    needed = ["date", "home_team", "away_team", "home_goals", "away_goals"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Arquivo {path} sem colunas necessárias: {missing}. Colunas disponíveis: {list(df.columns)}")

    out = df[needed].copy()

    out["date"] = pd.to_datetime(out["date"], errors="coerce", dayfirst=True).dt.date.astype(str)
    out["home_goals"] = pd.to_numeric(out["home_goals"], errors="coerce")
    out["away_goals"] = pd.to_numeric(out["away_goals"], errors="coerce")

    out = out.dropna(subset=["date", "home_team", "away_team", "home_goals", "away_goals"])
    out["home_goals"] = out["home_goals"].astype(int)
    out["away_goals"] = out["away_goals"].astype(int)

    return out

def build():
    files = glob.glob("data/raw/eu_top5/**/*.csv", recursive=True)
    if not files:
        files = glob.glob("data/raw/eu_top5/*.csv")

    all_parts = []
    for f in sorted(files):
        try:
            all_parts.append(normalize_eu_csv(f))
        except Exception as e:
            print(f"[SKIP] {f}: {e}")

    if not all_parts:
        raise RuntimeError("Nenhum CSV válido encontrado em data/raw/eu_top5.")

    big = pd.concat(all_parts, ignore_index=True).drop_duplicates()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    big.to_csv(OUT, index=False)
    print(f"OK: {OUT} (linhas={len(big)})")

if __name__ == "__main__":
    build()
