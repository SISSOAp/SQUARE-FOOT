const elCode = document.getElementById("code");
const elMaxMatches = document.getElementById("maxMatches");
const elMinHome = document.getElementById("minHome");
const elTTL = document.getElementById("ttl");

const elBtnLoad = document.getElementById("btnLoad");
const elBtnSave = document.getElementById("btnSave");
const elBtnAuto = document.getElementById("btnAuto");

const elMeta = document.getElementById("meta");
const elErr = document.getElementById("err");
const elRows = document.getElementById("rows");

let autoOn = false;
let autoTimer = null;

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
  // dd/mm/aaaa hh:mm (no fuso local do navegador)
  return d.toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit"
  });
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

function buildUrl(code, maxMatches, ttl) {
  return `/predict/${encodeURIComponent(code)}?max_matches=${maxMatches}&ttl_seconds=${ttl}&use_cache=true`;
}

async function fetchPredictions() {
  const code = elCode.value;
  const maxMatches = parseInt(elMaxMatches.value || "10", 10);
  const ttl = parseInt(elTTL.value || "60", 10);

  const url = buildUrl(code, maxMatches, ttl);

  const r = await fetch(url);
  return await r.json();
}

function renderTable(j) {
  clearTable();

  if (j.error) {
    showError(JSON.stringify(j, null, 2));
    return;
  }

  const ttl = parseInt(elTTL.value || "60", 10);
  const cache = j.cache?.hit ? `<span class="pill">cache HIT</span>` : `<span class="pill">cache MISS</span>`;
  showMeta(
    `Competição: <b>${j.competition}</b> | jogos na API: <b>${j.matches_fetched}</b> | mostrados: <b>${j.returned}</b> | ${cache} | TTL=${ttl}s`
  );

  const minHomePct = parseFloat(elMinHome.value || "0");
  const preds = j.predictions || [];

  for (const p of preds) {
    const probs = p.probabilities_1x2 || {};
    const xg = p.expected_goals || {};
    const homeWin = probs.home_win ?? null;

    // Filtro: Chance Casa >= X%
    if (homeWin !== null && (homeWin * 100) < minHomePct) continue;

    const scorelines = (p.top_scorelines || [])
      .slice(0, 5)
      .map(s => `${s.home}-${s.away} (${(s.p * 100).toFixed(1)}%)`)
      .join("<br>");

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${formatDateBR(p.utcDate)}</td>
      <td>${(p.home || "-")} vs ${(p.away || "-")}</td>
      <td>${fmt2(xg.home)}</td>
      <td>${fmt2(xg.away)}</td>
      <td>${pct(probs.home_win)}</td>
      <td>${pct(probs.draw)}</td>
      <td>${pct(probs.away_win)}</td>
      <td>${scorelines || "-"}</td>
      <td>${p.status || "-"}</td>
    `;
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
  const ttl = parseInt(elTTL.value || "60", 10);

  // endpoint de salvar
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
elBtnSave.addEventListener("click", saveJson);
elBtnAuto.addEventListener("click", () => setAuto(!autoOn));

(async function init() {
  await loadCompetitions();
  await loadAndRender();
})();
