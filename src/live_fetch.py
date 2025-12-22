from __future__ import annotations

import os
from typing import Any, Dict, Optional, List

import requests

BASE_URL = os.getenv("FOOTBALL_API_BASE_URL", "https://api.football-data.org/v4")
TOKEN = (
    os.getenv("FOOTBALL_DATA_TOKEN")
    or os.getenv("FOOTBALL_TOKEN")
    or os.getenv("API_TOKEN")
    or os.getenv("TOKEN")
)

DEFAULT_TIMEOUT = 20


def _headers() -> Dict[str, str]:
    if not TOKEN:
        return {}
    return {"X-Auth-Token": TOKEN}


def _rate_limit_debug(resp: requests.Response) -> str:
    avail = resp.headers.get("X-Requests-Available-Minute") or resp.headers.get("X-Requests-Available")
    reset = resp.headers.get("X-RequestCounter-Reset") or resp.headers.get("Retry-After")
    return f"avail={avail}, reset={reset}"


def _get(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not TOKEN:
        raise RuntimeError(
            "Token não encontrado. Defina FOOTBALL_DATA_TOKEN (ou FOOTBALL_TOKEN/API_TOKEN)."
        )

    resp = requests.get(url, headers=_headers(), params=params, timeout=DEFAULT_TIMEOUT)

    if resp.status_code == 429:
        raise RuntimeError(f"429 Rate limit. {_rate_limit_debug(resp)}")
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def fetch_competition_matches(
    code: str,
    statuses: Optional[List[str]] = None,
    limit: int = 15,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Busca partidas por competição.
    Nota: alguns ambientes não respeitam múltiplos status via query.
    Estratégia: se statuses tiver mais de 1, NÃO manda status na query e filtra localmente.
    """
    url = f"{BASE_URL}/competitions/{code}/matches"
    params: Dict[str, Any] = {}

    if date_from:
        params["dateFrom"] = date_from
    if date_to:
        params["dateTo"] = date_to

    # Se só 1 status, manda. Se múltiplos, filtra localmente (mais robusto).
    if statuses and len(statuses) == 1:
        params["status"] = statuses[0]

    data = _get(url, params=params)

    matches = data.get("matches", []) or []
    if statuses:
        status_set = set(statuses)
        matches = [m for m in matches if (m.get("status") in status_set)]
        data["matches"] = matches

    # Ordena por data e corta
    matches.sort(key=lambda m: (m.get("utcDate") or ""))
    if limit and len(matches) > limit:
        data["matches"] = matches[:limit]

    return data


def fetch_competition_standings(code: str) -> Dict[str, Any]:
    url = f"{BASE_URL}/competitions/{code}/standings"
    return _get(url)
