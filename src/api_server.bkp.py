import json
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

# Import do teu fetch (já existe no projeto)
from src.live_fetch import fetch_competition_matches


APP_NAME = "SQUARE FOOT"
DEFAULT_LIMIT = 15
DEFAULT_TTL_SECONDS = 60

# Fuso fixo Brasilia (sem depender do Windows)
BR_TZ = timezone(timedelta(hours=-3))

# Nome amigável das competições (sem chamar API -> evita 429)
LEAGUE_LABELS: Dict[str, str] = {
    "PL": "Premier League",
    "BL1": "Bundesliga",
    "PD": "La Liga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
    "DED": "Eredivisie",
    "PPL": "Primeira Liga (Portugal)",
    "ELC": "EFL Championship",
    "CL": "UEFA Champions League",
    "BSA": "Brasileirão Série A",
    "EC": "Euro (Seleções)",
    "WC": "Copa do Mundo",
}

# Mapa PT-BR (para exibir na UI)
STATUS_PT: Dict[str, str] = {
    "SCHEDULED": "Agendado",
    "TIMED": "Agendado (hora definida)",
    "IN_PLAY": "Ao vivo",
    "PAUSED": "Intervalo",
    "FINISHED": "Finalizado",
    "POSTPONED": "Adiado",
    "SUSPENDED": "Suspenso",
    "CANCELED": "Cancelado",
}

# Opções do dropdown (você pediu para remover TIMED do filtro)
STATUS_FILTER_OPTIONS: List[Tuple[str, str]] = [
    ("SCHEDULED", "Agendado"),
    ("IN_PLAY", "Ao vivo"),
    ("PAUSED", "Intervalo"),
    ("FINISHED", "Finalizado"),
]


app = FastAPI(title=APP_NAME, version="1.0")

# Cache em memória: (key -> (ts, payload))
_CACHE: Dict[str, Tuple[float, Any]] = {}


# ----------------------------
# Utilitários
# ----------------------------
def _now() -> float:
    return time.time()


def _cache_get(key: str, ttl: int) -> Optional[Any]:
    item = _CACHE.get(key)
    if not item:
        return None
    ts, payload = item
    if (_now() - ts) <= ttl:
        return payload
    return None


def _cache_set(key: str, payload: Any) -> None:
    _CACHE[key] = (_now(), payload)


def _parse_utc_iso(dt_str: str) -> datetime:
    # dt_str geralmente vem tipo: "2025-12-21T13:30:00Z"
    s = (dt_str or "").strip()
    if not s:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_dt_br(dt_str: str) -> str:
    """
    Corrige o bug de fuso:
    - parseia como UTC
    - converte para America/Sao_Paulo (UTC-3)
    - formata BR
    """
    try:
        utc_dt = _parse_utc_iso(dt_str)
        br_dt = utc_dt.astimezone(BR_TZ)
        return br_dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return dt_str


def league_name(code: str) -> str:
    return LEAGUE_LABELS.get(code, code)


def status_pt(s: str) -> str:
    return STATUS_PT.get(s, s)


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _score_from_match(m: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    """
    Tenta extrair placar (para ao vivo/finalizado).
    Football-data costuma ter m["score"]["fullTime"].
    """
    sc = (m or {}).get("score") or {}
    ft = sc.get("fullTime") or {}
    ht = sc.get("halfTime") or {}

    h = ft.get("home")
    a = ft.get("away")

    # se fullTime estiver vazio em ao vivo, tenta halfTime
    if h is None or a is None:
        h = ht.get("home")
        a = ht.get("away")

    if h is None or a is None:
        return None, None
    return _safe_int(h, 0), _safe_int(a, 0)


def _match_title(m: Dict[str, Any]) -> Tuple[str, str]:
    home = ((m.get("homeTeam") or {}).get("name")) or m.get("home") or "-"
    away = ((m.get("awayTeam") or {}).get("name")) or m.get("away") or "-"
    return home, away


def _sort_matches(raw: List[Dict[str, Any]], status: str) -> List[Dict[str, Any]]:
    def _dt(m: Dict[str, Any]) -> datetime:
        try:
            return _parse_utc_iso(m.get("utcDate") or "")
        except Exception:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)

    # FINISHED: mais recentes primeiro
    if status == "FINISHED":
        return sorted(raw, key=_dt, reverse=True)

    # outros: mais próximos primeiro
    return sorted(raw, key=_dt)


def _preds_path(code: str) -> str:
    return os.path.join("data", "preds_live", f"{code}.json")


def _load_preds_for_comp(code: str) -> Dict[str, Any]:
    """
    Carrega predictions do arquivo JSON gerado pelo predict_live.
    Cacheia por 60s.
    """
    cache_key = f"preds:{code}"
    cached = _cache_get(cache_key, DEFAULT_TTL_SECONDS)
    if cached is not None:
        return cached

    path = _preds_path(code)
    if not os.path.exists(path):
        payload = {"ok": False, "path": path, "matches": []}
        _cache_set(cache_key, payload)
        return payload

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        payload = {"ok": False, "path": path, "matches": []}
        _cache_set(cache_key, payload)
        return payload

    # normaliza: aceitar {"matches":[...]} ou lista direto
    matches = data.get("matches") if isinstance(data, dict) else None
    if matches is None and isinstance(data, list):
        matches = data
    if matches is None:
        matches = []

    payload = {"ok": True, "path": path, "matches": matches, "raw": data}
    _cache_set(cache_key, payload)
    return payload


def _find_pred(preds: Dict[str, Any], match_id: int) -> Optional[Dict[str, Any]]:
    """
    Procura o match_id no JSON com flexibilidade de chaves.
    """
    lst = preds.get("matches") or []
    for p in lst:
        mid = p.get("match_id") or p.get("id") or p.get("matchId")
        if mid is None:
            continue
        try:
            if int(mid) == int(match_id):
                return p
        except Exception:
            pass
    return None


def _poisson_scorelines(lh: float, la: float, max_g: int = 6) -> List[Tuple[str, float]]:
    """
    Fallback simples (se não vier scorelines do JSON).
    Não é o teu modelo, mas evita card “vazio” caso falte.
    """
    import math

    def pmf(lmb: float, k: int) -> float:
        return math.exp(-lmb) * (lmb**k) / math.factorial(k)

    out: List[Tuple[str, float]] = []
    for hg in range(max_g + 1):
        for ag in range(max_g + 1):
            p = pmf(lh, hg) * pmf(la, ag)
            out.append((f"{hg}-{ag}", p))
    out.sort(key=lambda x: x[1], reverse=True)
    return out[:3]


def _team_form_from_finished(team_name: str, finished: List[Dict[str, Any]], n: int = 5) -> Dict[str, Any]:
    """
    Forma e lista dos últimos N jogos do time.
    """
    games: List[Dict[str, Any]] = []
    for m in finished:
        home, away = _match_title(m)
        if home == team_name or away == team_name:
            games.append(m)

    # finished já vem ordenado recente->antigo no nosso cache
    games = games[:n]

    form: List[str] = []
    lines: List[str] = []
    for m in games:
        home, away = _match_title(m)
        h, a = _score_from_match(m)
        if h is None or a is None:
            continue
        if team_name == home:
            if h > a:
                r = "V"
            elif h == a:
                r = "E"
            else:
                r = "D"
            lines.append(f"{home} {h}-{a} {away}")
        else:
            # team é visitante
            if a > h:
                r = "V"
            elif a == h:
                r = "E"
            else:
                r = "D"
            lines.append(f"{home} {h}-{a} {away}")
        form.append(r)

    # streak: conta repetição do primeiro resultado
    streak = "-"
    if form:
        first = form[0]
        count = 1
        for x in form[1:]:
            if x == first:
                count += 1
            else:
                break
        suffix = {"V": "V", "E": "E", "D": "D"}.get(first, "")
        streak = f"{count}{suffix}"

    return {"form": form, "streak": streak, "lines": lines}


def _build_standings_from_finished(finished: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """
    Monta classificação a partir de jogos finalizados:
    pts, jogos, gf, ga, sg
    """
    table: Dict[str, Dict[str, int]] = {}
    for m in finished:
        home, away = _match_title(m)
        h, a = _score_from_match(m)
        if h is None or a is None:
            continue

        for t in [home, away]:
            if t not in table:
                table[t] = {"pts": 0, "j": 0, "gf": 0, "ga": 0, "sg": 0}

        table[home]["j"] += 1
        table[away]["j"] += 1

        table[home]["gf"] += h
        table[home]["ga"] += a
        table[away]["gf"] += a
        table[away]["ga"] += h

        # pontos
        if h > a:
            table[home]["pts"] += 3
        elif h < a:
            table[away]["pts"] += 3
        else:
            table[home]["pts"] += 1
            table[away]["pts"] += 1

    # sg
    for t, d in table.items():
        d["sg"] = d["gf"] - d["ga"]

    return table


def _rank(table: Dict[str, Dict[str, int]]) -> List[Tuple[str, Dict[str, int]]]:
    return sorted(
        table.items(),
        key=lambda kv: (kv[1]["pts"], kv[1]["sg"], kv[1]["gf"]),
        reverse=True,
    )


def _team_stand_line(team: str, ranked: List[Tuple[str, Dict[str, int]]]) -> str:
    for i, (t, d) in enumerate(ranked, start=1):
        if t == team:
            return f"#{i} • {d['pts']} pts • J:{d['j']} • SG:{d['sg']}"
    return "-"


# ----------------------------
# HTML (site)
# ----------------------------
INDEX_HTML = r"""
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>SQUARE FOOT</title>
  <style>
    :root{
      --bg0:#050912;
      --bg1:#071021;
      --card:#0b1427cc;
      --stroke:#ffffff14;
      --text:#e8eef8;
      --muted:#a9b6cc;
      --accent:#19c37d;
      --accent2:#2aa3ff;
      --warn:#ffcc66;
    }
    html,body{height:100%;}
    body{
      margin:0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Arial, sans-serif;
      color:var(--text);
      background:
        radial-gradient(1200px 600px at 20% 0%, #0b3b2c55 0%, transparent 60%),
        radial-gradient(1200px 600px at 90% 10%, #103a7755 0%, transparent 60%),
        linear-gradient(180deg, var(--bg0) 0%, var(--bg1) 100%);
    }
    .wrap{max-width:1200px;margin:0 auto;padding:32px 18px 60px;}
    header{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:18px;}
    h1{margin:0;font-size:42px;letter-spacing:1px;}
    .sub{margin-top:6px;color:var(--muted)}
    .tz{color:var(--muted);margin-top:10px;text-align:right}
    .panel{
      background:var(--card);
      border:1px solid var(--stroke);
      border-radius:18px;
      padding:16px;
      box-shadow: 0 12px 40px #00000055;
    }
    .filters{
      display:grid;
      grid-template-columns: 1.6fr 1.3fr 1fr auto;
      gap:14px;
      align-items:end;
    }
    label{display:block;font-size:13px;color:var(--muted);margin-bottom:6px;}
    select,input{
      width:100%;
      background:#0a1326;
      color:var(--text);
      border:1px solid var(--stroke);
      border-radius:12px;
      padding:12px 12px;
      font-size:14px;
      outline:none;
    }
    /* deixa o dropdown legível */
    option{background:#0a1326;color:var(--text);}
    .btn{
      background:linear-gradient(180deg, #0f3b2c 0%, #0b2b21 100%);
      border:1px solid #1ccf8580;
      color:#eafff6;
      padding:12px 18px;
      border-radius:14px;
      font-weight:700;
      cursor:pointer;
      height:44px;
    }
    .btn:hover{filter:brightness(1.05);}
    .how{
      margin-top:14px;
      padding:14px 16px;
      border-radius:14px;
      border:1px dashed #19c37d55;
      background:#0b2b2133;
      color:#cfeee0;
    }
    .grid{
      margin-top:18px;
      display:grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap:16px;
      align-items:start;
    }
    .box-title{
      display:flex;align-items:center;justify-content:space-between;
      margin-bottom:10px;
      color:#d9e6ff;
      font-weight:800;
    }
    .pill{
      border:1px solid var(--stroke);
      background:#0a1326;
      color:var(--muted);
      border-radius:999px;
      padding:6px 10px;
      font-size:12px;
    }
    table{
      width:100%;
      border-collapse:separate;
      border-spacing:0;
      overflow:hidden;
      border-radius:14px;
      border:1px solid var(--stroke);
      background:#0a1326aa;
    }
    th,td{
      padding:12px 12px;
      border-bottom:1px solid var(--stroke);
      vertical-align:top;
    }
    th{font-size:13px;color:var(--muted);text-align:left;background:#0a1326;}
    tr:hover td{background:#0f1d38aa;cursor:pointer}
    .status{
      display:inline-block;
      padding:6px 10px;
      border-radius:999px;
      border:1px solid var(--stroke);
      font-size:12px;
      color:#d7e2f6;
      background:#0b1427;
    }
    .card{
      background:#0a1326aa;
      border:1px solid var(--stroke);
      border-radius:18px;
      padding:16px;
    }
    .card h2{margin:0 0 6px 0;}
    .meta{color:var(--muted);margin-bottom:14px;}
    .kpi-grid{
      display:grid;
      grid-template-columns: repeat(3, 1fr);
      gap:10px;
    }
    .kpi{
      background:#0b1427;
      border:1px solid var(--stroke);
      border-radius:14px;
      padding:12px;
      min-height:66px;
    }
    .k{color:var(--muted);font-size:12px;margin-bottom:6px;}
    .v{font-size:20px;font-weight:900;}
    .small{font-size:14px;font-weight:700;line-height:1.25;}
    .warn{
      margin-top:12px;
      padding:12px 14px;
      border-radius:14px;
      border:1px dashed #ffcc6655;
      background:#2b210b33;
      color:#ffe3aa;
    }
    .split{
      margin-top:14px;
      display:grid;
      grid-template-columns: 1fr 1fr;
      gap:14px;
    }
    ul{margin:8px 0 0 18px;color:#d9e6ff;}
    .desc{color:var(--muted);font-size:12px;margin-top:8px;line-height:1.3;}
    .muted{color:var(--muted);}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1>SQUARE FOOT</h1>
        <div class="sub">Probabilidades simples para jogos de futebol — em tempo real</div>
      </div>
      <div class="tz">Fuso: Horário de Brasília (America/Sao_Paulo)</div>
    </header>

    <div class="panel">
      <div class="filters">
        <div>
          <label>Competição</label>
          <select id="league"></select>
        </div>
        <div>
          <label>Status</label>
          <select id="status"></select>
        </div>
        <div>
          <label>Qtd jogos</label>
          <input id="limit" type="number" value="15" min="1" max="50"/>
        </div>
        <button class="btn" id="btnLoad">Carregar</button>
      </div>

      <div class="how">
        <b>Como usar:</b> escolha a competição → clique em <b>Carregar</b> → clique em um jogo para ver o card.
      </div>

      <div class="grid">
        <div class="panel">
          <div class="box-title">
            <div>Jogos</div>
            <div class="pill" id="pillInfo">—</div>
          </div>
          <table>
            <thead>
              <tr>
                <th style="width:160px;">Data (BR)</th>
                <th>Jogo</th>
                <th style="width:180px;">Status</th>
              </tr>
            </thead>
            <tbody id="tbody"></tbody>
          </table>
        </div>

        <div class="panel">
          <div class="box-title">
            <div>Detalhes do jogo</div>
            <div class="pill" id="pillCard">—</div>
          </div>
          <div class="card" id="card">
            <div class="muted">Selecione um jogo para ver os detalhes.</div>
          </div>
        </div>
      </div>
    </div>
  </div>

<script>
  const elLeague = document.getElementById("league");
  const elStatus = document.getElementById("status");
  const elLimit  = document.getElementById("limit");
  const elBtn    = document.getElementById("btnLoad");
  const elBody   = document.getElementById("tbody");
  const elCard   = document.getElementById("card");
  const elPillInfo = document.getElementById("pillInfo");
  const elPillCard = document.getElementById("pillCard");

  let lastMatches = [];

  function pct(x){
    if (x === null || x === undefined) return "-";
    return (100*x).toFixed(1) + "%";
  }

  function num(x, d=2){
    if (x === null || x === undefined) return "-";
    const v = Number(x);
    if (!isFinite(v)) return "-";
    return v.toFixed(d);
  }

  async function loadLeagues(){
    const r = await fetch("/leagues");
    const data = await r.json();
    elLeague.innerHTML = "";
    for(const it of data.leagues){
      const opt = document.createElement("option");
      opt.value = it.code;
      opt.textContent = it.name;
      elLeague.appendChild(opt);
    }

    elStatus.innerHTML = "";
    for(const it of data.status_options){
      const opt = document.createElement("option");
      opt.value = it.code;
      opt.textContent = it.name;
      elStatus.appendChild(opt);
    }
  }

  function renderMatches(list, infoText){
    elBody.innerHTML = "";
    elPillInfo.textContent = infoText || "—";

    for(const m of list){
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${m.dateBR}</td>
        <td><b>${m.home}</b> vs <b>${m.away}</b></td>
        <td><span class="status">${m.status_pt}</span></td>
      `;
      tr.addEventListener("click", () => loadCard(m.code, m.id));
      elBody.appendChild(tr);
    }
  }

  function renderCard(data){
    elPillCard.textContent = data.updated || "—";

    if(!data.ok){
      elCard.innerHTML = `<div class="warn">${data.message || "Sem dados."}</div>`;
      return;
    }

    const p = data.pred || {};
    const sl = (p.scorelines || []).slice(0,3);
    const scoreLines = sl.map(x => `${x.score} (${(100*x.p).toFixed(1)}%)`).join("<br/>") || "-";

    const standings = data.standings || {};
    const stLine = standings.line || "-";

    const fmH = data.form_home || {};
    const fmA = data.form_away || {};

    elCard.innerHTML = `
      <h2>${data.match.home} vs ${data.match.away}</h2>
      <div class="meta">${data.match.dateBR} • ${data.match.status_pt}</div>

      <div class="kpi-grid">
        <div class="kpi"><div class="k">Prob. Mandante</div><div class="v">${pct(p.H)}</div></div>
        <div class="kpi"><div class="k">Prob. Empate</div><div class="v">${pct(p.D)}</div></div>
        <div class="kpi"><div class="k">Prob. Visitante</div><div class="v">${pct(p.A)}</div></div>

        <div class="kpi"><div class="k">Gols esperados (mandante)</div><div class="v">${num(p.lh)}</div></div>
        <div class="kpi"><div class="k">Gols esperados (visitante)</div><div class="v">${num(p.la)}</div></div>
        <div class="kpi"><div class="k">Ambos marcam</div><div class="v">${pct(p.btts)}</div></div>

        <div class="kpi"><div class="k">Over 1.5 gols</div><div class="v">${pct(p.over15)}</div></div>
        <div class="kpi"><div class="k">Over 2.5 gols</div><div class="v">${pct(p.over25)}</div></div>
        <div class="kpi"><div class="k">Placares mais prováveis</div><div class="v small">${scoreLines}</div></div>

        <div class="kpi" style="grid-column: span 3;">
          <div class="k">Classificação na liga</div>
          <div class="v small">${stLine}</div>
        </div>
      </div>

      ${data.message ? `<div class="warn"><b>Sem cálculo para este jogo.</b><br/>Motivo: ${data.message}</div>` : ""}

      <div class="split">
        <div>
          <b>Últimos 5 jogos — Mandante</b>
          <div class="desc">Forma: ${(fmH.form||[]).join("") || "-"} • Sequência: ${fmH.streak || "-"}. Resultados recentes do time (placar final).</div>
          <ul>${(fmH.lines||[]).map(x=>`<li>${x}</li>`).join("") || "<li>-</li>"}</ul>
        </div>
        <div>
          <b>Últimos 5 jogos — Visitante</b>
          <div class="desc">Forma: ${(fmA.form||[]).join("") || "-"} • Sequência: ${fmA.streak || "-"}. Resultados recentes do time (placar final).</div>
          <ul>${(fmA.lines||[]).map(x=>`<li>${x}</li>`).join("") || "<li>-</li>"}</ul>
        </div>
      </div>
    `;
  }

  async function loadMatches(){
    const code = elLeague.value;
    const status = elStatus.value;
    const limit = Number(elLimit.value || 15);

    elPillInfo.textContent = "Carregando…";
    elBody.innerHTML = "";
    elCard.innerHTML = `<div class="muted">Selecione um jogo para ver os detalhes.</div>`;
    elPillCard.textContent = "—";

    const url = `/matches?code=${encodeURIComponent(code)}&status=${encodeURIComponent(status)}&limit=${encodeURIComponent(limit)}`;
    const r = await fetch(url);
    const data = await r.json();

    if(!data.ok){
      renderMatches([], "—");
      elCard.innerHTML = `<div class="warn">${data.message || "Erro ao buscar jogos."}</div>`;
      return;
    }

    lastMatches = data.matches || [];
    renderMatches(lastMatches, `${data.league_name} • mostrando: ${lastMatches.length}`);
    if(lastMatches.length){
      await loadCard(code, lastMatches[0].id);
    }
  }

  async function loadCard(code, matchId){
    elPillCard.textContent = "Carregando…";
    const url = `/card?code=${encodeURIComponent(code)}&match_id=${encodeURIComponent(matchId)}`;
    const r = await fetch(url);
    const data = await r.json();
    renderCard(data);
  }

  elBtn.addEventListener("click", loadMatches);

  loadLeagues().then(loadMatches);
</script>
</body>
</html>
"""


# ----------------------------
# Endpoints
# ----------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(INDEX_HTML)


@app.get("/health")
def health():
    return {"ok": True, "app": APP_NAME}


@app.get("/leagues")
def leagues():
    leagues = [{"code": c, "name": league_name(c)} for c in sorted(LEAGUE_LABELS.keys(), key=lambda x: league_name(x))]
    status_options = [{"code": c, "name": n} for (c, n) in STATUS_FILTER_OPTIONS]
    return {"ok": True, "leagues": leagues, "status_options": status_options}


@app.get("/matches")
def matches(
    code: str = Query(..., description="Ex: PL, BL1, PD..."),
    status: str = Query("SCHEDULED", description="SCHEDULED/IN_PLAY/PAUSED/FINISHED"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=50),
):
    try:
        cache_key = f"matches:{code}:{status}:{limit}"
        cached = _cache_get(cache_key, DEFAULT_TTL_SECONDS)
        if cached is not None:
            return cached

        data = fetch_competition_matches(code, status=status)
        raw = data.get("matches", []) or []
        raw = _sort_matches(raw, status)

        out: List[Dict[str, Any]] = []
        for m in raw[:limit]:
            home, away = _match_title(m)
            mid = m.get("id")
            utcDate = m.get("utcDate") or ""
            st = m.get("status") or status
            out.append(
                {
                    "code": code,
                    "id": mid,
                    "utcDate": utcDate,
                    "dateBR": format_dt_br(utcDate),
                    "home": home,
                    "away": away,
                    "status_raw": st,
                    "status_pt": status_pt(st),
                }
            )

        payload = {
            "ok": True,
            "code": code,
            "league_name": league_name(code),
            "status": status,
            "matches": out,
        }
        _cache_set(cache_key, payload)
        return payload

    except RuntimeError as e:
        # 429 do teu live_fetch vira RuntimeError
        return JSONResponse(status_code=429, content={"ok": False, "message": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "message": f"Erro: {e}"})


@app.get("/card")
def card(
    code: str = Query(...),
    match_id: int = Query(...),
):
    try:
        # pega o match da lista cacheada mais recente (qualquer status)
        # tenta achar em SCHEDULED, IN_PLAY, PAUSED, FINISHED
        def _get_any_matches() -> List[Dict[str, Any]]:
            allm: List[Dict[str, Any]] = []
            for st in ["IN_PLAY", "PAUSED", "SCHEDULED", "FINISHED"]:
                key = f"matches_raw:{code}:{st}"
                cached = _cache_get(key, DEFAULT_TTL_SECONDS)
                if cached is not None:
                    allm.extend(cached)
                    continue
                data = fetch_competition_matches(code, status=st)
                raw = data.get("matches", []) or []
                raw = _sort_matches(raw, st)
                _cache_set(key, raw)
                allm.extend(raw)
            return allm

        all_matches = _get_any_matches()
        match_obj = None
        for m in all_matches:
            if _safe_int(m.get("id"), -1) == int(match_id):
                match_obj = m
                break

        if not match_obj:
            return {"ok": False, "message": "Jogo não encontrado na API."}

        home, away = _match_title(match_obj)
        utcDate = match_obj.get("utcDate") or ""
        st_raw = match_obj.get("status") or "-"
        st_pt = status_pt(st_raw)

        # predictions (do JSON gerado)
        preds = _load_preds_for_comp(code)
        pred_raw = _find_pred(preds, match_id)

        pred = {
            "H": None, "D": None, "A": None,
            "lh": None, "la": None,
            "btts": None, "over15": None, "over25": None,
            "scorelines": [],
        }
        message = None

        if pred_raw:
            # aceita vários nomes de campo
            pred["H"] = pred_raw.get("H") or pred_raw.get("p_home") or pred_raw.get("home")
            pred["D"] = pred_raw.get("D") or pred_raw.get("p_draw") or pred_raw.get("draw")
            pred["A"] = pred_raw.get("A") or pred_raw.get("p_away") or pred_raw.get("away")

            pred["lh"] = pred_raw.get("lh") or pred_raw.get("lambda_home") or pred_raw.get("lambdaH") or pred_raw.get("lambda_home_team")
            pred["la"] = pred_raw.get("la") or pred_raw.get("lambda_away") or pred_raw.get("lambdaA") or pred_raw.get("lambda_away_team")

            pred["btts"] = pred_raw.get("btts") or pred_raw.get("BTTS") or pred_raw.get("both_score")
            pred["over15"] = pred_raw.get("over15") or pred_raw.get("O15") or pred_raw.get("over_15")
            pred["over25"] = pred_raw.get("over25") or pred_raw.get("O25") or pred_raw.get("over_25")

            # scorelines: aceita formatos comuns
            sl = pred_raw.get("scorelines") or pred_raw.get("top_scores") or pred_raw.get("scores") or []
            scorelines = []
            for x in sl:
                if isinstance(x, dict):
                    sc = x.get("score") or x.get("s") or x.get("label")
                    pr = x.get("p") or x.get("prob") or x.get("probability")
                    if sc is not None and pr is not None:
                        scorelines.append({"score": str(sc), "p": float(pr)})
                elif isinstance(x, (list, tuple)) and len(x) >= 2:
                    scorelines.append({"score": str(x[0]), "p": float(x[1])})
            pred["scorelines"] = scorelines[:3]
        else:
            message = "Previsão não encontrada no arquivo preds_live (rode predict_live antes)."

        # fallback scorelines se lambdas existirem mas scorelines vierem vazias
        if (not pred["scorelines"]) and (pred["lh"] is not None) and (pred["la"] is not None):
            try:
                top3 = _poisson_scorelines(float(pred["lh"]), float(pred["la"]))
                pred["scorelines"] = [{"score": s, "p": p} for (s, p) in top3]
            except Exception:
                pass

        # finished cache (para forma e classificação)
        fin_key = f"matches_raw:{code}:FINISHED"
        finished = _cache_get(fin_key, DEFAULT_TTL_SECONDS)
        if finished is None:
            fin_data = fetch_competition_matches(code, status="FINISHED")
            finished = _sort_matches(fin_data.get("matches", []) or [], "FINISHED")
            _cache_set(fin_key, finished)

        fmH = _team_form_from_finished(home, finished, n=5)
        fmA = _team_form_from_finished(away, finished, n=5)

        standings_line = "-"
        try:
            table = _build_standings_from_finished(finished)
            ranked = _rank(table)
            standings_line = f"<b>{home}</b>: {_team_stand_line(home, ranked)}<br/><b>{away}</b>: {_team_stand_line(away, ranked)}"
        except Exception:
            standings_line = "-"

        return {
            "ok": True,
            "updated": "Atualizado",
            "match": {
                "id": match_id,
                "home": home,
                "away": away,
                "utcDate": utcDate,
                "dateBR": format_dt_br(utcDate),
                "status_raw": st_raw,
                "status_pt": st_pt,
            },
            "pred": pred,
            "standings": {"line": standings_line},
            "form_home": fmH,
            "form_away": fmA,
            "message": message,
        }

    except RuntimeError as e:
        return JSONResponse(status_code=429, content={"ok": False, "message": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "message": f"Erro: {e}"})
