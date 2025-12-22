from __future__ import annotations

from pathlib import Path
import pandas as pd


LEAGUES = [
    "bundesliga",
    "premier-league",
    "la-liga",
    "serie-a",
    "ligue-1",
]

# Tentamos suportar variações comuns de nomes de colunas
CANDIDATES = {
    "date": ["date", "Date"],
    "home_team": ["home_team", "HomeTeam", "hometeam", "home"],
    "away_team": ["away_team", "AwayTeam", "awayteam", "away"],
    "home_goals": ["home_goals", "FTHG", "fthg", "home_score", "hg"],
    "away_goals": ["away_goals", "FTAG", "ftag", "away_score", "ag"],
}


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def normalize_one_file(path: Path, league: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    c_date = pick_col(df, CANDIDATES["date"])
    c_home = pick_col(df, CANDIDATES["home_team"])
    c_away = pick_col(df, CANDIDATES["away_team"])
    c_hg = pick_col(df, CANDIDATES["home_goals"])
    c_ag = pick_col(df, CANDIDATES["away_goals"])

    missing = [k for k, v in [("date", c_date), ("home_team", c_home), ("away_team", c_away), ("home_goals", c_hg), ("away_goals", c_ag)] if v is None]
    if missing:
        raise ValueError(f"{path.name}: faltando colunas {missing}. Colunas atuais: {list(df.columns)}")

    out = df[[c_date, c_home, c_away, c_hg, c_ag]].copy()
    out.columns = ["date", "home_team", "away_team", "home_goals", "away_goals"]

    # season vem do nome do arquivo: season-2324.csv -> 2324
    season = path.stem.replace("season-", "")
    out["season"] = season
    out["league"] = league

    # tipos
    out["date"] = pd.to_datetime(out["date"], errors="coerce", dayfirst=True)
    out["home_goals"] = pd.to_numeric(out["home_goals"], errors="coerce")
    out["away_goals"] = pd.to_numeric(out["away_goals"], errors="coerce")

    out = out.dropna(subset=["date", "home_team", "away_team", "home_goals", "away_goals"])
    out["home_goals"] = out["home_goals"].astype(int)
    out["away_goals"] = out["away_goals"].astype(int)

    return out


def build_league(league: str) -> pd.DataFrame:
    folder = Path("data/raw/eu_top5") / league
    files = sorted(folder.glob("season-*.csv"))
    if not files:
        raise FileNotFoundError(f"Nenhum arquivo season-*.csv em {folder}")

    frames = [normalize_one_file(f, league) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values("date").reset_index(drop=True)
    return df


def main():
    out_dir = Path("data/processed/leagues")
    out_dir.mkdir(parents=True, exist_ok=True)

    all_frames = []

    for league in LEAGUES:
        df_l = build_league(league)
        out_path = out_dir / f"{league}.csv"
        df_l.to_csv(out_path, index=False)
        print(f"OK: {out_path} (linhas={len(df_l)})")
        all_frames.append(df_l)

    df_all = pd.concat(all_frames, ignore_index=True).sort_values("date").reset_index(drop=True)
    df_all.to_csv("data/processed/matches_eu_top5.csv", index=False)
    print(f"OK: data/processed/matches_eu_top5.csv (linhas={len(df_all)})")


if __name__ == "__main__":
    main()
