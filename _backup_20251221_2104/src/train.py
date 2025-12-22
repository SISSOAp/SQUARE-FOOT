import pandas as pd
from src.model import train_team_poisson, save_model

INPUT_CSV = "data/processed/matches_all.csv"

OUTPUT_MODEL = "data/model.joblib"

def main():
    df = pd.read_csv(INPUT_CSV)
    model = train_team_poisson(df, iters=600, lr=0.03, reg=0.02)
    save_model(model, OUTPUT_MODEL)
    print(f"Modelo salvo em: {OUTPUT_MODEL}")
    print(f"Times conhecidos: {len(model.teams)}")

if __name__ == "__main__":
    main()
