import os
import json
import re
from pathlib import Path

import pandas as pd

# Ligas que VOCÊ usa no site (pela tua lista do dropdown)
TARGET_LEAGUES = {
    "E0": "Premier League",
    "D1": "Bundesliga",
    "SP1": "La Liga",
    "I1": "Serie A",
    "F1": "Ligue 1",
    "N1": "Eredivisie",
    "P1": "Primeira Liga (Portugal)",
    "E1": "EFL Championship",
    "B1": "Brasileirão Série A",
    # "EC": "UEFA Champions League",  # opcional (se você quiser manter)
}

# Stats que vamos usar (sem odds/apostas)
NEEDED_COLS = [
    "Div","Date","HomeTeam","AwayTeam",
    "HS","AS","HST","AST","HC","AC","HF","AF","HY","AY","HR","AR"
]

def season_from_filename(name: str) -> str:
    # all-euro-data-2024-2025.xlsx -> 2024-2025
    m = re.search(r"(\d{4}-\d{4})", name)
    return m.group(1) if m else name

def safe_float(x):
    try:
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None

def add_team_match(agg, team, stats_for, stats_against):
    # agg[team] = {"n":0,"shots_for":0,...}
    if team not in agg:
        agg[team] = {"n": 0}
        for k in stats_for.keys():
            agg[team][f"{k}_for"] = 0.0
            agg[team][f"{k}_against"] = 0.0

    agg[team]["n"] += 1
    for k,v in stats_for.items():
        agg[team][f"{k}_for"] += v
        agg[team][f"{k}_against"] += stats_against[k]

def finalize_avgs(agg):
    out = {}
    for team, d in agg.items():
        n = d.get("n", 0)
        if n <= 0:
            continue
        out[team] = {"n": n}
        for key, val in d.items():
            if key == "n":
                continue
            out[team][key] = round(val / n, 2)
    return out

def main():
    root = Path(__file__).resolve().parents[1]
    in_dir = root / "data" / "football-data"
    out_dir = root / "web" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "extra-stats.json"

    if not in_dir.exists():
        raise SystemExit(f"Pasta não encontrada: {in_dir}")

    # Estrutura final
    result = {
        "meta": {
            "source": "football-data.co.uk (all-euro-data XLSX)",
            "seasons_included": [],
            "leagues": TARGET_LEAGUES,
            "notes": "Averages per match by team. 'for' = a favor do time; 'against' = contra."
        },
        "leagues": {}
    }

    files = sorted([p for p in in_dir.glob("*.xlsx")])
    if not files:
        raise SystemExit(f"Nenhum XLSX encontrado em: {in_dir}")

    seasons = []

    # Vamos acumulando por liga
    league_team_agg = {code: {} for code in TARGET_LEAGUES.keys()}

    for fp in files:
        season = season_from_filename(fp.name)
        seasons.append(season)

        for league_code in TARGET_LEAGUES.keys():
            # Algumas planilhas podem não ter a aba (raro), então tratamos
            try:
                df = pd.read_excel(fp, sheet_name=league_code)
            except Exception:
                continue

            # Confere colunas necessárias
            missing = [c for c in NEEDED_COLS if c not in df.columns]
            if missing:
                continue

            # Mantém só o que interessa
            df = df[NEEDED_COLS].copy()

            # Remove linhas sem times ou sem stats
            df = df.dropna(subset=["HomeTeam","AwayTeam","HS","AS","HST","AST","HC","AC","HF","AF","HY","AY","HR","AR"])

            # Para cada jogo, soma stats no mandante e no visitante
            for _, r in df.iterrows():
                home = str(r["HomeTeam"]).strip()
                away = str(r["AwayTeam"]).strip()

                hs = safe_float(r["HS"]);  a_s = safe_float(r["AS"])
                hst = safe_float(r["HST"]); ast = safe_float(r["AST"])
                hc = safe_float(r["HC"]);  ac = safe_float(r["AC"])
                hf = safe_float(r["HF"]);  af = safe_float(r["AF"])
                hy = safe_float(r["HY"]);  ay = safe_float(r["AY"])
                hr = safe_float(r["HR"]);  ar = safe_float(r["AR"])

                vals = [hs,a_s,hst,ast,hc,ac,hf,af,hy,ay,hr,ar]
                if any(v is None for v in vals):
                    continue

                home_for = {"shots": hs, "sot": hst, "corners": hc, "fouls": hf, "yellow": hy, "red": hr}
                home_against = {"shots": a_s, "sot": ast, "corners": ac, "fouls": af, "yellow": ay, "red": ar}

                away_for = {"shots": a_s, "sot": ast, "corners": ac, "fouls": af, "yellow": ay, "red": ar}
                away_against = {"shots": hs, "sot": hst, "corners": hc, "fouls": hf, "yellow": hy, "red": hr}

                add_team_match(league_team_agg[league_code], home, home_for, home_against)
                add_team_match(league_team_agg[league_code], away, away_for, away_against)

    result["meta"]["seasons_included"] = sorted(list(dict.fromkeys(seasons)))

    # Finaliza médias por liga
    for league_code, agg in league_team_agg.items():
        teams_avg = finalize_avgs(agg)

        # Média da liga (média simples das médias dos times, ponderada por n)
        league_sum = {"n": 0, "shots_for": 0, "shots_against": 0, "sot_for": 0, "sot_against": 0,
                      "corners_for": 0, "corners_against": 0, "fouls_for": 0, "fouls_against": 0,
                      "yellow_for": 0, "yellow_against": 0, "red_for": 0, "red_against": 0}

        for _, d in teams_avg.items():
            n = d["n"]
            league_sum["n"] += n
            for k in league_sum.keys():
                if k == "n": 
                    continue
                league_sum[k] += d.get(k, 0) * n

        league_avg = {}
        if league_sum["n"] > 0:
            for k, v in league_sum.items():
                if k == "n":
                    continue
                league_avg[k] = round(v / league_sum["n"], 2)

        result["leagues"][league_code] = {
            "name": TARGET_LEAGUES[league_code],
            "teams": teams_avg,
            "league_avg": league_avg
        }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"OK! Gerado: {out_path}")

if __name__ == "__main__":
    main()
