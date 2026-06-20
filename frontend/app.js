/* ===================================================================
   Drop-Driver Analysis — dashboard logic
   Talks to the FastAPI backend at the same origin (/api/...).
   =================================================================== */

const API = "/api";
const els = {
  nav: document.getElementById("nav"),
  results: document.getElementById("results"),
  pills: document.getElementById("datasetPills"),
  runAll: document.getElementById("runAll"),
  healthDot: document.getElementById("healthDot"),
  healthText: document.getElementById("healthText"),
};

const FIG_CAPTIONS = {
  pred_vs_actual: "Predicted vs. actual daily return",
  drop_confusion: "Drop vs. no-drop confusion matrix",
  sentiment_confusion: "News-sentiment confusion matrix",
  feature_importance: "Drivers ranked by importance",
  roc: "ROC curves (Random Forest vs. XGBoost)",
  elbow: "Elbow & silhouette for k",
  clusters: "Drop-event clusters (PCA projection)",
};

// ---- small helpers -------------------------------------------------
const fmt = (v) =>
  typeof v === "number" ? (Number.isInteger(v) ? v : v.toFixed(4)) : v;

function el(tag, cls, html) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (html !== undefined) node.innerHTML = html;
  return node;
}

async function getJSON(path) {
  const res = await fetch(`${API}${path}`);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(body.detail || res.statusText);
    err.kind = body.error || `HTTP ${res.status}`;
    throw err;
  }
  return body;
}

// ---- rendering primitives -----------------------------------------
function table(rows) {
  if (!rows || !rows.length) return el("div");
  const cols = Object.keys(rows[0]);
  const wrap = el("div", "table-wrap");
  const t = el("table");
  const thead = el("thead");
  const htr = el("tr");
  cols.forEach((c) => {
    const isNum = typeof rows[0][c] === "number";
    const th = el("th", isNum ? "num" : null, c.replace(/_/g, " "));
    htr.appendChild(th);
  });
  thead.appendChild(htr);
  const tbody = el("tbody");
  rows.forEach((r) => {
    const tr = el("tr");
    cols.forEach((c) => {
      const isNum = typeof r[c] === "number";
      tr.appendChild(el("td", isNum ? "num" : null, String(fmt(r[c]))));
    });
    tbody.appendChild(tr);
  });
  t.appendChild(thead);
  t.appendChild(tbody);
  wrap.appendChild(t);
  return wrap;
}

function rankingTable(ranking) {
  const max = Math.max(...ranking.map((r) => r.importance));
  const wrap = el("div", "table-wrap");
  const t = el("table");
  t.innerHTML = "<thead><tr><th>#</th><th>driver</th><th class='num'>importance</th></tr></thead>";
  const tb = el("tbody");
  ranking.forEach((r, i) => {
    const tr = el("tr");
    tr.appendChild(el("td", null, String(i + 1)));
    tr.appendChild(el("td", null, r.feature.replace(/_/g, " ")));
    const td = el("td", "num bar-cell");
    const bar = el("div", "bar");
    bar.style.width = `${(r.importance / max) * 100}%`;
    const span = el("span", null, r.importance.toFixed(4));
    td.appendChild(bar);
    td.appendChild(span);
    tr.appendChild(td);
    tb.appendChild(tr);
  });
  t.appendChild(tb);
  wrap.appendChild(t);
  return wrap;
}

function figures(figs) {
  const grid = el("div", "figs");
  Object.entries(figs || {}).forEach(([name, b64]) => {
    const fig = el("div", "fig");
    const img = el("img");
    img.src = `data:image/png;base64,${b64}`;
    img.alt = FIG_CAPTIONS[name] || name;
    fig.appendChild(img);
    fig.appendChild(el("div", "cap", FIG_CAPTIONS[name] || name));
    grid.appendChild(fig);
  });
  return grid;
}

function statRow(stats) {
  const row = el("div", "stat-row");
  stats.forEach(([val, lab, accent]) => {
    const s = el("div", `stat${accent ? " accent" : ""}`);
    s.appendChild(el("div", "val", String(val)));
    s.appendChild(el("div", "lab", lab));
    row.appendChild(s);
  });
  return row;
}

// ---- section renderer ---------------------------------------------
function renderSection(key, data, index) {
  const card = el("div", "section-card");
  card.appendChild(el("div", "eyebrow", `Member ${index} · ${key}`));
  card.appendChild(el("h2", null, data.title || key));

  (data.warnings || []).forEach((w) =>
    card.appendChild(el("div", "warn-line", `⚠ ${w}`))
  );

  if (data.ranking) card.appendChild(rankingTable(data.ranking));
  if (data.metrics) card.appendChild(table(data.metrics));

  if (data.anomaly_detection) {
    const a = data.anomaly_detection;
    card.appendChild(
      statRow([
        [data.best_k ?? "—", "clusters (k)"],
        [a.anomalies_flagged, "anomalies flagged"],
        [`${Math.round(a.recall_of_drops * 100)}%`, "drops recovered", true],
      ])
    );
  }
  if (data.cluster_profiles) card.appendChild(table(data.cluster_profiles));
  if (data.figures) card.appendChild(figures(data.figures));
  return card;
}

function renderDatasetPills(ds) {
  els.pills.innerHTML = "";
  if (!ds) return;
  const mode = ds.synthetic
    ? `<span class="pill warn"><b>Synthetic</b> · preview only</span>`
    : `<span class="pill live"><b>Live data</b></span>`;
  els.pills.innerHTML =
    mode +
    `<span class="pill"><b>${ds.rows.toLocaleString()}</b> stock-days</span>` +
    `<span class="pill"><b>${ds.drop_events}</b> drops (${(ds.drop_rate * 100).toFixed(1)}%)</span>` +
    `<span class="pill">${ds.date_start} → ${ds.date_end}</span>`;
}

// ---- states --------------------------------------------------------
function showLoading(msg) {
  els.results.innerHTML = "";
  const box = el("div", "loading");
  box.appendChild(el("div", "spinner"));
  box.appendChild(el("div", null, msg));
  els.results.appendChild(box);
}

function showError(err) {
  els.results.innerHTML = "";
  const box = el("div", "error");
  box.appendChild(el("h2", null, err.kind || "Something went wrong"));
  let detail = err.message;
  if (err.kind === "DataSourceError")
    detail += " — the market/macro source is unreachable. Check your connection, or set USE_SYNTHETIC=true to preview offline.";
  box.appendChild(el("p", null, detail));
  els.results.appendChild(box);
}

// ---- actions -------------------------------------------------------
const SECTION_INDEX = {};

function setActive(key) {
  document.querySelectorAll(".nav-item").forEach((n) =>
    n.classList.toggle("active", n.dataset.key === key)
  );
}

async function runSection(key) {
  setActive(key);
  showLoading(`Running ${key}…`);
  try {
    const data = await getJSON(`/analyze/${key}`);
    renderDatasetPills(data.dataset);
    els.results.innerHTML = "";
    els.results.appendChild(renderSection(key, data, SECTION_INDEX[key]));
  } catch (err) {
    showError(err);
  }
}

async function runAll() {
  setActive(null);
  els.runAll.disabled = true;
  showLoading("Running the full pipeline…");
  try {
    const data = await getJSON(`/analyze`);
    renderDatasetPills(data.dataset);
    els.results.innerHTML = "";
    Object.entries(data.sections).forEach(([key, sec]) =>
      els.results.appendChild(renderSection(key, sec, SECTION_INDEX[key]))
    );
  } catch (err) {
    showError(err);
  } finally {
    els.runAll.disabled = false;
  }
}

// ---- bootstrap -----------------------------------------------------
async function init() {
  // health
  try {
    const h = await getJSON("/health");
    els.healthDot.className = "dot ok";
    els.healthText.textContent = h.synthetic ? "backend ok · synthetic" : "backend ok · live";
  } catch {
    els.healthDot.className = "dot down";
    els.healthText.textContent = "backend offline";
  }

  // nav
  try {
    const { sections } = await getJSON("/sections");
    sections.forEach((s, i) => {
      SECTION_INDEX[s.key] = i + 1;
      const btn = el("button", "nav-item");
      btn.dataset.key = s.key;
      btn.innerHTML = `<span class="idx">0${i + 1}</span><span>${s.title.replace(/^Member \d+ -- /, "")}</span>`;
      btn.addEventListener("click", () => runSection(s.key));
      els.nav.appendChild(btn);
    });
  } catch (err) {
    showError(err);
  }

  els.runAll.addEventListener("click", runAll);
}

init();
