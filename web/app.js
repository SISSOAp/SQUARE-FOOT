const elCode = document.getElementById("code");
const elMaxMatches = document.getElementById("maxMatches");
const elMinHome = document.getElementById("minHome"); // pode estar hidden (ok)
const elTTL = document.getElementById("ttl"); // pode não existir (vamos tratar)

const elBtnLoad = document.getElementById("btnLoad");
const elBtnSave = document.getElementById("btnSave");
const elBtnAuto = document.getElementById("btnAuto");

const elMeta = document.getElementById("meta");
const elErr = document.getElementById("err");
const elRows = document.getElementById("rows");

const elStatus = document.getElementById("t1"); // filtro Status no HTML
const elDetails = document.getElementById("details"); // novo bloco no HTML

let autoOn = false;
let autoTimer = null;

// ---------- EXTRA STATS (football-data.co.uk) ----------
let EXTRA_ROWS = []; // match-level rows
let EXTRA_READY = false;

const COMP_TO_DIV = {
  "Premier League": "E0",
  "Bundesliga": "D1",
  "La Liga": "SP1",
  "Serie A": "I1",
  "Ligue 1": "F1",
  "Eredivisie": "N1",
  "Primeira Liga (Portugal)": "P1",
  "EFL Championship": "E1",
  "Brasileirão Série A": "B1",
  // "UEFA Champions League": "EC", // se um dia você gerar dataset para ela
};

function normalizeStr(x) {
  return (x ?? "").toString().trim();
}

function pct(x) {
  if (x === null || x === undefined) return "-";
  return (x * 100).toFixed(1) + "%";
}

function fmt2(x) {
  if (x === null || x === undefined) return "-";
  return Number(x).toFixed(2);
}

function formatDateBR(utcDate) {
  if (!utcDate) return "-";
  const d = new Date(utcDate);
  return d.toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit"
  });
}

// season "YYYY-YYYY" a partir da data do jogo (heurística padrão Europa)
function seasonFromUtcDate(utcDate) {
  if (!utcDate) return null;
  const d = new Date(utcDate);
  const y = d.getUTCFullYear();
  const m = d.getUTCMonth() + 1; // 1-12
  // temporada europeia geralmente vira em Jul/Ago; vamos usar Julho como corte
  if (m >= 7) return `${y}-${y + 1}`;
  return `${y - 1}-${y}`;
}

function clearTable() {
  elRows.innerHTML = "";
}

function showError(msg) {
  elErr.textContent = msg || "";
}

function showMeta(html) {
  elMeta.innerHTML = html || "";
}

function hideDetails() {
  if (!elDetails) return;
  elDetails.style.display = "none";
  elDetails.innerHTML = "";
}

function showDetails(html) {
  if (!elDetails) return;
  elDetails.style.display = "block";
  elDetails.innerHTML = html || "";
}

async function loadCompetitions() {
  const r = await fetch("/competitions");
  const j = await r.json();
  elCode.innerHTML = "";
  for (const c of j.competitions || []) {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    elCode.appendChild(opt);
  }
}

function getTTL() {
  // se não existir o input ttl, usa 60
  const v = elTTL ? parseInt(elTTL.value || "60", 10) : 60;
  return Number.isFinite(v) ? v : 60;
}

function buildUrl(code, maxMatches, ttl) {
  return `/predict/${encodeURIComponent(code)}?max_matches=${maxMatches}&ttl_seconds=${ttl}&use_cache=true`;
}

async function fetchPredictions() {
  const code = elCode.value;
  const maxMatches = parseInt(elMaxMatches.value || "10", 10);
  const ttl = getTTL();
  const url = buildUrl(code, maxMatches, ttl);
  const r = await fetch(url);
  return await r.json();
}

// ---------- carregar extra-stats.json ----------
async function loadExtraStats() {
  // Não deixa quebrar o app se o JSON ainda não estiver disponível
  try {
    // cache-bust simples para evitar service worker / cache agressivo
    const url = `/data/extra-stats.json?v=${Date.now()}`;
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();

    // aceitamos vários formatos:
    // - array direto
    // - { rows: [...] }
    // - { data: [...] }
    const rows =
      Array.isArray(j) ? j :
      Array.isArray(j.rows) ? j.rows :
      Array.isArray(j.data) ? j.data :
      [];

    EXTRA_ROWS = rows;
    EXTRA_READY = true;
  } catch (e) {
    EXTRA_ROWS = [];
    EXTRA_READY = false;
  }
}

function asNum(x) {
  const n = Number(x);
  return Number.isFinite(n) ? n : null;
}

function avg(nums) {
  const vals = nums.filter(v => v !== null && v !== undefined && Number.isFinite(v));
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

// retorna stats médios do mandante em casa e visitante fora, para a competição+temporada
function computeExtraAverages({ competitionName, utcDate, home, away }) {
  if (!EXTRA_READY) return null;

  const div = COMP_TO_DIV[competitionName];
  if (!div) return null;

  const season = seasonFromUtcDate(utcDate);
  if (!season) return null;

  // Esperado no match-level row:
  // Div, Season, Date, HomeTeam, AwayTeam, HS, AS, HST, AST, HC, AC, HF, AF, HY, AY, HR, AR
  // Mas vamos ser tolerantes com nomes.
  const rows = EXTRA_ROWS.filter(r => {
    const rDiv = normalizeStr(r.Div ?? r.div);
    const rSeason = normalizeStr(r.Season ?? r.season);
    const okDiv = rDiv === div;
    const okSeason = !rSeason ? true : (normalizeStr(rSeason) === season);
    return okDiv && okSeason;
  });

  if (!rows.length) return { div, season, found: 0 };

  const homeRows = rows.filter(r => normalizeStr(r.HomeTeam ?? r.homeTeam ?? r.Home) === home);
  const awayRows = rows.filter(r => normalizeStr(r.AwayTeam ?? r.awayTeam ?? r.Away) === away);

  // mandante jogando EM CASA: usa HS/HST/HC/HF/HY/HR
  const homeHS = avg(homeRows.map(r => asNum(r.HS)));
  const homeHST = avg(homeRows.map(r => asNum(r.HST)));
  const homeHC = avg(homeRows.map(r => asNum(r.HC)));
  const homeHF = avg(homeRows.map(r => asNum(r.HF)));
  const homeHY = avg(homeRows.map(r => asNum(r.HY)));
  const homeHR = avg(homeRows.map(r => asNum(r.HR)));

  // visitante jogando FORA: usa AS/AST/AC/AF/AY/AR
  const awayAS = avg(awayRows.map(r => asNum(r.AS)));
  const awayAST = avg(awayRows.map(r => asNum(r.AST)));
  const awayAC = avg(awayRows.map(r => asNum(r.AC)));
  const awayAF = avg(awayRows.map(r => asNum(r.AF)));
  const awayAY = avg(awayRows.map(r => asNum(r.AY)));
  const awayAR = avg(awayRows.map(r => asNum(r.AR)));

  return {
    div,
    season,
    found: rows.length,
    homeCount: homeRows.length,
    awayCount: awayRows.length,
    home: { HS: homeHS, HST: homeHST, HC: homeHC, HF: homeHF, HY: homeHY, HR: homeHR },
    away: { AS: awayAS, AST: awayAST, AC: awayAC, AF: awayAF, AY: awayAY, AR: awayAR },
  };
}

function fmt1(x) {
  if (x === null || x === undefined) return "-";
  return Number(x).toFixed(1);
}

function renderDetailsCard(p, extra) {
  const probs = p.probabilities_1x2 || {};
  const xg = p.expected_goals || {};

  const scorelines = (p.top_scorelines || [])
    .slice(0, 5)
    .map(s => `${s.home}-${s.away} (${(s.p * 100).toFixed(1)}%)`)
    .join(" • ");

  let extraHtml = `<div class="pill">Stats extras: indisponível</div>`;
  if (extra && extra.found) {
    extraHtml = `
      <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:8px;">
        <div class="pill">Div: <b>${extra.div}</b></div>
        <div class="pill">Temporada: <b>${extra.season}</b></div>
        <div class="pill">Base (liga/temporada): <b>${extra.found}</b> jogos</div>
        <div class="pill">${p.home}: <b>${extra.homeCount}</b> jogos em casa</div>
        <div class="pill">${p.away}: <b>${extra.awayCount}</b> jogos fora</div>
      </div>

      <div style="margin-top:10px;">
        <div style="opacity:.9; margin-bottom:6px;"><b>Médias (mandante em casa)</b></div>
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
          <div class="pill">HS: <b>${fmt1(extra.home.HS)}</b></div>
          <div class="pill">HST: <b>${fmt1(extra.home.HST)}</b></div>
          <div class="pill">HC: <b>${fmt1(extra.home.HC)}</b></div>
          <div class="pill">HF: <b>${fmt1(extra.home.HF)}</b></div>
          <div class="pill">HY: <b>${fmt1(extra.home.HY)}</b></div>
          <div class="pill">HR: <b>${fmt1(extra.home.HR)}</b></div>
        </div>
      </div>

      <div style="margin-top:10px;">
        <div style="opacity:.9; margin-bottom:6px;"><b>Médias (visitante fora)</b></div>
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
          <div class="pill">AS: <b>${fmt1(extra.away.AS)}</b></div>
          <div class="pill">AST: <b>${fmt1(extra.away.AST)}</b></div>
          <div class="pill">AC: <b>${fmt1(extra.away.AC)}</b></div>
          <div class="pill">AF: <b>${fmt1(extra.away.AF)}</b></div>
          <div class="pill">AY: <b>${fmt1(extra.away.AY)}</b></div>
          <div class="pill">AR: <b>${fmt1(extra.away.AR)}</b></div>
        </div>
      </div>
    `;
  } else if (extra && extra.found === 0) {
    extraHtml = `
      <div class="pill">Stats extras: sem dados para ${extra.div} / ${extra.season}</div>
    `;
  } else if (EXTRA_READY) {
    extraHtml = `<div class="pill">Stats extras: sem mapeamento de liga (COMP_TO_DIV)</div>`;
  }

  return `
    <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
      <div>
        <div style="font-size:16px;"><b>${p.home}</b> vs <b>${p.away}</b></div>
        <div style="opacity:.85; margin-top:4px;">${formatDateBR(p.utcDate)} • ${p.status || "-"}</div>
      </div>
      <button id="btnCloseDetails" style="background:#2b3a4a;">Fechar</button>
    </div>

    <div style="margin-top:10px; display:flex; gap:10px; flex-wrap:wrap;">
      <div class="pill">xG Casa: <b>${fmt2(xg.home)}</b></div>
      <div class="pill">xG Fora: <b>${fmt2(xg.away)}</b></div>
      <div class="pill">Casa: <b>${pct(probs.home_win)}</b></div>
      <div class="pill">Empate: <b>${pct(probs.draw)}</b></div>
      <div class="pill">Fora: <b>${pct(probs.away_win)}</b></div>
    </div>

    <div style="margin-top:10px; opacity:.9;">
      <b>Placares prováveis:</b> ${scorelines || "-"}
    </div>

    <div style="margin-top:12px;">
      ${extraHtml}
    </div>
  `;
}

function renderTable(j) {
  clearTable();
  hideDetails();

  if (j.error) {
    showError(JSON.stringify(j, null, 2));
    return;
  }

  const ttl = getTTL();
  const cache = j.cache?.hit ? `<span class="pill">cache HIT</span>` : `<span class="pill">cache MISS</span>`;
  showMeta(
    `Competição: <b>${j.competition}</b> | jogos na API: <b>${j.matches_fetched}</b> | mostrados: <b>${j.returned}</b> | ${cache} | TTL=${ttl}s`
  );

  const minHomePct = elMinHome ? parseFloat(elMinHome.value || "0") : 0;
  const statusFilter = elStatus ? elStatus.value : null;

  const preds = j.predictions || [];

  // badge (se existir)
  const badge = document.getElementById("rowsBadge");
  if (badge) badge.textContent = `${preds.length}`;

  // tabela é só 3 colunas (Data / Jogo / Status)
  for (const p of preds) {
    const probs = p.probabilities_1x2 || {};
    const homeWin = probs.home_win ?? null;

    if (homeWin !== null && (homeWin * 100) < minHomePct) continue;
    if (statusFilter && p.status && p.status !== statusFilter) continue;

    const tr = document.createElement("tr");
    tr.style.cursor = "pointer";
    tr.innerHTML = `
      <td>${formatDateBR(p.utcDate)}</td>
      <td><b>${(p.home || "-")}</b> vs <b>${(p.away || "-")}</b></td>
      <td>${p.status || "-"}</td>
    `;

    tr.addEventListener("click", () => {
      const extra = computeExtraAverages({
        competitionName: j.competition,
        utcDate: p.utcDate,
        home: normalizeStr(p.home),
        away: normalizeStr(p.away),
      });

      showDetails(renderDetailsCard(p, extra));

      // bind do botão fechar
      const btn = document.getElementById("btnCloseDetails");
      if (btn) btn.addEventListener("click", hideDetails);
      // scroll suave até o card
      if (elDetails) elDetails.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    elRows.appendChild(tr);
  }
}

async function loadAndRender() {
  showError("");
  try {
    const j = await fetchPredictions();
    renderTable(j);
  } catch (e) {
    showError("Falha ao chamar a API. A API está rodando?\n\n" + String(e));
  }
}

async function saveJson() {
  showError("");
  const code = elCode.value;
  const maxMatches = parseInt(elMaxMatches.value || "10", 10);
  const ttl = getTTL();

  const url = `/save/${encodeURIComponent(code)}?max_matches=${maxMatches}&ttl_seconds=${ttl}`;

  try {
    const r = await fetch(url, { method: "POST" });
    const j = await r.json();
    if (j.error) {
      showError(JSON.stringify(j, null, 2));
      return;
    }
    showMeta(`Salvo em: <b>${j.path}</b> | Competição: <b>${j.competition}</b> | jogos: <b>${j.saved}</b>`);
  } catch (e) {
    showError("Falha ao salvar JSON.\n\n" + String(e));
  }
}

function setAuto(on) {
  autoOn = on;
  elBtnAuto.textContent = autoOn ? "Auto: ON" : "Auto: OFF";

  if (autoTimer) {
    clearInterval(autoTimer);
    autoTimer = null;
  }

  if (autoOn) {
    autoTimer = setInterval(loadAndRender, 30000);
  }
}

elBtnLoad.addEventListener("click", loadAndRender);
if (elBtnSave) elBtnSave.addEventListener("click", saveJson);
if (elBtnAuto) elBtnAuto.addEventListener("click", () => setAuto(!autoOn));
if (elStatus) elStatus.addEventListener("change", loadAndRender);

(async function init() {
  await loadExtraStats();     // tenta carregar /data/extra-stats.json
  await loadCompetitions();
  await loadAndRender();
})();
