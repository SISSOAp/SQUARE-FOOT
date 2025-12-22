from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DATA_DIR = Path("data")

# Aceita variações comuns de cabeçalho
HOME_TEAM_KEYS = ["home_team", "homeTeam", "HomeTeam", "home", "mandante"]
AWAY_TEAM_KEYS = ["away_team", "awayTeam", "AwayTeam", "away", "visitante"]
HOME_GOALS_KEYS = ["home_goals", "homeGoals", "FTHG", "HG", "home_score", "gols_mandante"]
AWAY_GOALS_KEYS = ["away_goals", "awayGoals", "FTAG", "AG", "away_score", "gols_visitante"]
DATE_KEYS = ["date", "utcDate", "Date", "match_date", "data"]

def _pick_key(headers: List[str], candidates: List[str]) -> Optional[str]:
    s = {h.lower(): h for h in headers}
    for c in candidates:
        if c.lower() in s:
            return s[c.lower()]
    return None

def _to_int(x) -> Optional[int]:
    try:
        if x is None:
            return None
        x = str(x).strip()
        if x == "" or x.lower() == "none" or x.lower() == "nan":
            return None
        return int(float(x))
    except Exception:
        return None

def _parse_date(x: str) -> Optional[datetime]:
    if not x:
        return None
    x = x.strip()
    # tenta ISO
    try:
        if x.endswith("Z"):
            x = x.replace("Z", "+00:00")
        return datetime.fromisoformat(x)
    except Exception:
        pass
    # tenta formatos comuns
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(x, fmt)
        except Exception:
            continue
    return None

def _find_csv_for_league(code: str) -> Optional[Path]:
    code_u = code.upper()
    candidates = [
        DATA_DIR / f"{code_u}.csv",
        DATA_DIR / f"{code_u.lower()}.csv",
        DATA_DIR / f"matches_{code_u}.csv",
        DATA_DIR / f"matches_{code_u.lower()}.csv",
        DATA_DIR / f"{code_u}_matches.csv",
        DATA_DIR / f"{code_u.lower()}_matches.csv",
    ]
    for p in candidates:
        if p.exists():
            return p

    # fallback: acha qualquer csv que contenha o code no nome
    if DATA_DIR.exists():
        for p in DATA_DIR.glob("*.csv"):
            if code_u.lower() in p.name.lower():
                return p
    return None

@dataclass
class TeamAgg:
    games: int = 0
    gf: int = 0
    ga: int = 0
    btts: int = 0
    over15: int = 0
    over25: int = 0

def _rate(n: int, d: int) -> float:
    return (n / d) if d > 0 else 0.0

def get_team_historical_stats(code: str, team: str) -> Dict[str, Dict[str, float]]:
    """
    Retorna estatísticas históricas do time a partir de um CSV local.
    Saída:
      {
        "home": {"games":..., "gf_avg":..., "ga_avg":..., "btts":..., "over15":..., "over25":...},
        "away": {...},
        "overall": {...}
      }
    """
    csv_path = _find_csv_for_league(code)
    if not csv_path:
        return {}

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        k_home = _pick_key(headers, HOME_TEAM_KEYS)
        k_away = _pick_key(headers, AWAY_TEAM_KEYS)
        k_hg = _pick_key(headers, HOME_GOALS_KEYS)
        k_ag = _pick_key(headers, AWAY_GOALS_KEYS)

        if not (k_home and k_away and k_hg and k_ag):
            return {}

        home = TeamAgg()
        away = TeamAgg()

        for row in reader:
            ht = (row.get(k_home) or "").strip()
            at = (row.get(k_away) or "").strip()
            hg = _to_int(row.get(k_hg))
            ag = _to_int(row.get(k_ag))
            if hg is None or ag is None:
                continue

            total = hg + ag
            is_btts = (hg > 0 and ag > 0)
            is_over15 = (total >= 2)
            is_over25 = (total >= 3)

            if ht == team:
                home.games += 1
                home.gf += hg
                home.ga += ag
                home.btts += 1 if is_btts else 0
                home.over15 += 1 if is_over15 else 0
                home.over25 += 1 if is_over25 else 0
            if at == team:
                away.games += 1
                away.gf += ag
                away.ga += hg
                away.btts += 1 if is_btts else 0
                away.over15 += 1 if is_over15 else 0
                away.over25 += 1 if is_over25 else 0

    def pack(a: TeamAgg) -> Dict[str, float]:
        return {
            "games": float(a.games),
            "gf_avg": (a.gf / a.games) if a.games else 0.0,
            "ga_avg": (a.ga / a.games) if a.games else 0.0,
            "btts": _rate(a.btts, a.games),
            "over15": _rate(a.over15, a.games),
            "over25": _rate(a.over25, a.games),
        }

    overall = TeamAgg(
        games=home.games + away.games,
        gf=home.gf + away.gf,
        ga=home.ga + away.ga,
        btts=home.btts + away.btts,
        over15=home.over15 + away.over15,
        over25=home.over25 + away.over25,
    )

    return {"home": pack(home), "away": pack(away), "overall": pack(overall)}
