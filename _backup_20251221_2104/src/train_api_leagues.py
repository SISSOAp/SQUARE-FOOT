import os
import pandas as pd

from src.model import train_team_poisson, save_model

CODES = [
    "CL",
    "BL1",
    "DED",
    "BSA",
    "PD",
    "FL1",
    "ELC",
    "PPL",
    "EC",
    "SA",
    "PL",
    # "WC" normalmente não serve (linhas=0), então deixo fora
]

def train(code: str):
    inp = f"data/api_processed/{code}.csv"
    out = f"data/models/{code}.joblib"

    if not os.path.exists(inp):
        print(f"[SKIP] {code}: não existe {inp}")
        return

    df = pd.read_csv(inp)

    # Se vier vazio, pula
    if len(df) == 0:
        print(f"[SKIP] {code}: dataset vazio")
        return

    model = train_team_poisson(df, iters=600, lr=0.05, reg=0.02, verbose_every=200)
    save_model(model, out)
    print(f"OK: {code} -> {out} | times={len(model.teams)} | linhas={len(df)}")

def main():
    os.makedirs("data/models", exist_ok=True)
    for code in CODES:
        train(code)

if __name__ == "__main__":
    main()
