from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, List
import math

import numpy as np
import pandas as pd
from joblib import dump, load


# Evita overflow em exp()
CLIP_MIN = -20.0
CLIP_MAX = 20.0


def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 0.0 if k > 0 else 1.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def score_matrix(lam_home: float, lam_away: float, max_goals: int = 10) -> np.ndarray:
    mat = np.zeros((max_goals + 1, max_goals + 1), dtype=float)
    for i in range(max_goals + 1):
        p_i = poisson_pmf(i, lam_home)
        for j in range(max_goals + 1):
            mat[i, j] = p_i * poisson_pmf(j, lam_away)
    s = mat.sum()
    if s > 0:
        mat /= s
    return mat


def probs_1x2_from_matrix(mat: np.ndarray) -> Tuple[float, float, float]:
    home_win = np.tril(mat, k=-1).sum()
    draw = np.trace(mat)
    away_win = np.triu(mat, k=1).sum()
    return float(home_win), float(draw), float(away_win)


@dataclass
class PoissonTeamModel:
    teams: List[str]
    team_index: Dict[str, int]
    attack: np.ndarray
    defense: np.ndarray
    home_adv: float

    def expected_goals(self, home_team: str, away_team: str) -> Tuple[float, float]:
        hi = self.team_index[home_team]
        ai = self.team_index[away_team]

        log_lam_home = float(self.home_adv + self.attack[hi] - self.defense[ai])
        log_lam_away = float(self.attack[ai] - self.defense[hi])

        # Clamp para evitar exp() estourar
        log_lam_home = min(max(log_lam_home, CLIP_MIN), CLIP_MAX)
        log_lam_away = min(max(log_lam_away, CLIP_MIN), CLIP_MAX)

        lam_home = float(max(math.exp(log_lam_home), 0.01))
        lam_away = float(max(math.exp(log_lam_away), 0.01))
        return lam_home, lam_away

    def predict_1x2(self, home_team: str, away_team: str, max_goals: int = 10) -> Dict:
        lam_home, lam_away = self.expected_goals(home_team, away_team)
        mat = score_matrix(lam_home, lam_away, max_goals=max_goals)
        p_home, p_draw, p_away = probs_1x2_from_matrix(mat)

        top_scores = []
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                top_scores.append(((i, j), float(mat[i, j])))
        top_scores.sort(key=lambda x: x[1], reverse=True)
        top_scores = [{"home": s[0][0], "away": s[0][1], "p": s[1]} for s in top_scores[:10]]

        return {
            "home_team": home_team,
            "away_team": away_team,
            "expected_goals": {"home": lam_home, "away": lam_away},
            "probabilities_1x2": {"home_win": p_home, "draw": p_draw, "away_win": p_away},
            "top_scorelines": top_scores,
            "max_goals_truncation": max_goals,
        }


def train_team_poisson(
    df: pd.DataFrame,
    iters: int = 800,
    lr: float = 0.2,
    reg: float = 0.01,
    verbose_every: int = 200,
) -> PoissonTeamModel:
    required = {"home_team", "away_team", "home_goals", "away_goals"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset faltando colunas: {missing}")

    df = df.copy()
    df["home_goals"] = pd.to_numeric(df["home_goals"], errors="coerce")
    df["away_goals"] = pd.to_numeric(df["away_goals"], errors="coerce")
    df = df.dropna(subset=["home_team", "away_team", "home_goals", "away_goals"])

    teams = sorted(set(df["home_team"]).union(set(df["away_team"])))
    team_index = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    home_idx = df["home_team"].map(team_index).to_numpy(dtype=int)
    away_idx = df["away_team"].map(team_index).to_numpy(dtype=int)
    home_goals = df["home_goals"].to_numpy(dtype=float)
    away_goals = df["away_goals"].to_numpy(dtype=float)

    attack = np.zeros(n, dtype=float)
    defense = np.zeros(n, dtype=float)
    home_adv = 0.0

    m = float(len(df))

    for step in range(1, iters + 1):
        log_lam_home = home_adv + attack[home_idx] - defense[away_idx]
        log_lam_away = attack[away_idx] - defense[home_idx]

        log_lam_home = np.clip(log_lam_home, CLIP_MIN, CLIP_MAX)
        log_lam_away = np.clip(log_lam_away, CLIP_MIN, CLIP_MAX)

        lam_home = np.exp(log_lam_home)
        lam_away = np.exp(log_lam_away)

        err_home = lam_home - home_goals
        err_away = lam_away - away_goals

        grad_attack = np.zeros(n, dtype=float)
        grad_defense = np.zeros(n, dtype=float)

        np.add.at(grad_attack, home_idx, err_home)
        np.add.at(grad_attack, away_idx, err_away)

        np.add.at(grad_defense, away_idx, -err_home)
        np.add.at(grad_defense, home_idx, -err_away)

                grad_home_adv = float(err_home.sum())

        # Média por jogo + regularização L2
        grad_attack = grad_attack / m + 2.0 * reg * attack
        grad_defense = grad_defense / m + 2.0 * reg * defense
        grad_home_adv = grad_home_adv / m + 2.0 * reg * home_adv

        # Atualização (gradiente descendente)
        attack -= lr * grad_attack
        defense -= lr * grad_defense
        home_adv -= lr * grad_home_adv

        if verbose_every and (step % verbose_every == 0 or step == 1 or step == iters):
            # NLL (ignorando constantes de fatorial — não muda o treino)
            nll = float((lam_home - home_goals * log_lam_home).sum() + (lam_away - away_goals * log_lam_away).sum())
            nll += float(reg * (np.sum(attack**2) + np.sum(defense**2) + home_adv**2))
            print(f"[{step}/{iters}] nll={nll:.2f} home_adv={home_adv:.3f}")

    return PoissonTeamModel(
        teams=teams,
        team_index=team_index,
        attack=attack,
        defense=defense,
        home_adv=float(home_adv),
    )


def save_model(model: PoissonTeamModel, path: str) -> None:
    dump(model, path)


def load_model(path: str) -> PoissonTeamModel:
    return load(path)

