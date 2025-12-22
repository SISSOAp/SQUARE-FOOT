from pathlib import Path
import pandas as pd

from src.model import train_team_poisson, save_model

LEAGUES = [
    "bundesliga",
    "premier-league",
    "la-liga",
    "serie-a",
    "ligue-1",
]

IN_DIR = Path("data/processed/leagues")
OUT_DIR = Path("data/models")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    for league in LEAGUES:
        in_path = IN_DIR / f"{league}.csv"
        if not in_path.exists():
            raise FileNotFoundError(f"Não achei: {in_path}")

        df = pd.read_csv(in_path)

        # Treino (mantendo seus defaults; depois a gente ajusta performance/qualidade)
        model = train_team_poisson(df, iters=600, lr=0.03, reg=0.02)

        out_path = OUT_DIR / f"{league}.joblib"
        save_model(model, str(out_path))

        print(f"OK: {league} -> {out_path} | times={len(model.teams)} | linhas={len(df)}")

if __name__ == "__main__":
    main()
