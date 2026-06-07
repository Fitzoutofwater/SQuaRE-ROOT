"use strict";

// Vanilla, dependency-free renderer for the Q-Day Leaderboard.
// Reads data.json (produced by scripts/build_leaderboard.py) and renders summary
// tiles, an interactive feasibility-over-time chart, and a sortable ranking table.

const PALETTE = ["#16a34a", "#2563eb", "#db2777", "#9333ea", "#0891b2", "#ca8a04"];
const NUM_KEYS = new Set(["rank", "code_distance_d", "physical_qubits", "wall_clock_days", "feasibility_score"]);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

let STATE = { data: null, colors: {}, visible: new Set() };

// ---- theme: cycles Light -> Dark -> System (System follows the OS live) ----
const THEME_KEY = "qday-theme";
const THEME_MODES = ["light", "dark", "system"];
const THEME_META = {
  light: { icon: "☀︎", label: "Light" },
  dark: { icon: "🌙", label: "Dark" },
  system: { icon: "🖥︎", label: "System" },
};
const prefersDark = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

function readMode() {
  try { const m = localStorage.getItem(THEME_KEY); if (THEME_MODES.includes(m)) return m; } catch (e) { /* ignore */ }
  return "system";
}
function resolveTheme(mode) {
  if (mode === "system") return prefersDark && prefersDark.matches ? "dark" : "light";
  return mode;
}
function applyMode(mode) {
  document.documentElement.setAttribute("data-theme", resolveTheme(mode));
  const btn = document.getElementById("theme-toggle");
  if (btn) {
    btn.textContent = THEME_META[mode].icon;
    const next = THEME_MODES[(THEME_MODES.indexOf(mode) + 1) % THEME_MODES.length];
    btn.title = `Theme: ${THEME_META[mode].label} (click for ${THEME_META[next].label})`;
    btn.setAttribute("aria-label", btn.title);
  }
}
function initTheme() {
  let mode = readMode();
  applyMode(mode);
  const btn = document.getElementById("theme-toggle");
  if (btn) btn.addEventListener("click", () => {
    mode = THEME_MODES[(THEME_MODES.indexOf(mode) + 1) % THEME_MODES.length];
    try { localStorage.setItem(THEME_KEY, mode); } catch (e) { /* ignore */ }
    applyMode(mode);
  });
  if (prefersDark) prefersDark.addEventListener("change", () => { if (mode === "system") applyMode(mode); });
}
initTheme();

// ---- formatting -----------------------------------------------------------
function fmtInt(n) { return n == null ? "—" : Math.round(n).toLocaleString("en-US"); }
function fmtScore(s) { return s == null ? "—" : s.toFixed(1); }
function fmtWall(days) {
  if (days == null) return "—";
  const h = days * 24;
  if (h < 1) return (h * 60).toFixed(1) + " min";
  if (h < 48) return h.toFixed(1) + " h";
  return days.toFixed(2) + " d";
}
function parseDate(iso) { const d = new Date(iso); return isNaN(d) ? null : d; }
function fmtDay(iso) { const d = parseDate(iso); return d ? `${MONTHS[d.getMonth()]} ${d.getDate()}` : iso; }
function fmtDateTime(iso) {
  const d = parseDate(iso);
  if (!d) return iso;
  let h = d.getHours(); const m = String(d.getMinutes()).padStart(2, "0");
  const ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
  return `${MONTHS[d.getMonth()]} ${d.getDate()} at ${String(h).padStart(2, "0")}:${m} ${ap}`;
}
function scoreClass(s) { return s == null ? "muted" : s >= 66 ? "good" : s >= 33 ? "mid" : "low"; }

// Animate a number from 0 to target (ease-out) for a little life on load.
function countUp(el, target) {
  if (target == null) { el.textContent = "—"; return; }
  const dur = 750, start = performance.now();
  function step(now) {
    const t = Math.min(1, (now - start) / dur);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = (target * eased).toFixed(1);
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// Score delta vs the previous run, as a small ▲/▼ badge.
function deltaBadge(name) {
  const h = (STATE.data.history || {})[name] || [];
  if (h.length < 2) return "";
  const d = (h[h.length - 1].feasibility_score ?? 0) - (h[h.length - 2].feasibility_score ?? 0);
  const cls = d > 0.05 ? "up" : d < -0.05 ? "down" : "flat";
  const arr = cls === "up" ? "▲" : cls === "down" ? "▼" : "→";
  return `<span class="delta ${cls}">${arr} ${d >= 0 ? "+" : ""}${d.toFixed(1)}</span>`;
}

// ---- summary --------------------------------------------------------------
function renderSummary(data) {
  const rows = data.scenarios;
  const runs = Math.max(0, ...Object.values(data.history || {}).map((h) => h.length));
  document.getElementById("subline").textContent =
    `${rows.length} scenarios · ${runs} historical run${runs === 1 ? "" : "s"} · last updated ${fmtDateTime(data.generated_at)}`;

  const top = rows[0];
  countUp(document.getElementById("top-score"), top.feasibility_score);
  document.getElementById("top-name").textContent = top.scenario;
  const hist = (data.history || {})[top.scenario] || [];
  const trendEl = document.getElementById("top-trend");
  if (hist.length >= 2) {
    const d = (hist[hist.length - 1].feasibility_score ?? 0) - (hist[hist.length - 2].feasibility_score ?? 0);
    const cls = d > 0.05 ? "up" : d < -0.05 ? "down" : "flat";
    trendEl.className = "trend " + cls;
    trendEl.textContent = `${cls === "up" ? "↑" : cls === "down" ? "↓" : "→"} ${d >= 0 ? "+" : ""}${d.toFixed(1)}`;
  }

  const modalities = new Set(rows.map((r) => r.modality).filter(Boolean));
  const problems = new Set(rows.map((r) => r.problem).filter(Boolean));
  document.getElementById("count-value").textContent = String(rows.length);
  document.getElementById("count-sub").textContent =
    `${modalities.size} modalit${modalities.size === 1 ? "y" : "ies"} · ${problems.size} target problem${problems.size === 1 ? "" : "s"}`;

  document.getElementById("updated-value").textContent = fmtDateTime(data.generated_at);
  document.getElementById("updated-sub").textContent = "commit " + data.commit;
}

// ---- chart ----------------------------------------------------------------
function renderPills(data) {
  const host = document.getElementById("pills");
  host.innerHTML = data.scenarios
    .map((s) => {
      const c = STATE.colors[s.scenario];
      const on = STATE.visible.has(s.scenario);
      return `<button class="pill-btn" data-name="${s.scenario}" aria-pressed="${on}" style="color:${c}">
        <span class="dot"></span><span style="color:var(--ink)">${s.scenario}</span></button>`;
    })
    .join("");
  host.querySelectorAll(".pill-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const name = btn.dataset.name;
      if (STATE.visible.has(name)) {
        if (STATE.visible.size > 1) STATE.visible.delete(name);
      } else STATE.visible.add(name);
      btn.setAttribute("aria-pressed", STATE.visible.has(name));
      renderPills(data);
      drawChart(true);
    });
  });
}

const M = { l: 44, r: 18, t: 18, b: 30 };

function chartGeom() {
  const host = document.getElementById("chart-host");
  const W = Math.max(320, host.clientWidth);
  const H = 320;
  return { W, H, x0: M.l, x1: W - M.r, y0: H - M.b, y1: M.t };
}

function seriesPoints(name, g) {
  const hist = (STATE.data.history || {})[name] || [];
  const pts = hist.filter((p) => p.feasibility_score != null);
  const n = pts.length;
  return pts.map((p, i) => ({
    x: n <= 1 ? (g.x0 + g.x1) / 2 : g.x0 + (i * (g.x1 - g.x0)) / (n - 1),
    y: g.y0 - (p.feasibility_score / 100) * (g.y0 - g.y1),
    score: p.feasibility_score,
    date: p.date,
  }));
}

function drawChart(animate) {
  const g = chartGeom();
  const svg = document.getElementById("chart");
  svg.setAttribute("viewBox", `0 0 ${g.W} ${g.H}`);

  const visibleNames = STATE.data.scenarios.map((sc) => sc.scenario).filter((n) => STATE.visible.has(n));
  let s = "<defs>";
  visibleNames.forEach((name) => {
    const c = STATE.colors[name];
    s += `<linearGradient id="grad-${cssId(name)}" x1="0" y1="0" x2="0" y2="1">` +
      `<stop offset="0%" stop-color="${c}" stop-opacity="0.22"/>` +
      `<stop offset="100%" stop-color="${c}" stop-opacity="0"/></linearGradient>`;
  });
  s += "</defs>";
  // gridlines + y labels
  for (const v of [0, 25, 50, 75, 100]) {
    const y = g.y0 - (v / 100) * (g.y0 - g.y1);
    s += `<line class="grid" x1="${g.x0}" y1="${y}" x2="${g.x1}" y2="${y}" stroke-width="1"/>`;
    s += `<text class="axis" x="${g.x0 - 10}" y="${y + 4}" text-anchor="end" font-size="11">${v}</text>`;
  }

  const visible = visibleNames;
  let xDates = [];
  visible.forEach((name) => {
    const pts = seriesPoints(name, g);
    if (pts.length > xDates.length) xDates = pts.map((p) => p.date);
    const color = STATE.colors[name];
    const line = pts.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
    if (visible.length === 1 && pts.length > 1) {
      const area = `M${pts[0].x.toFixed(1)} ${g.y0} ` +
        pts.map((p) => `L${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ") +
        ` L${pts[pts.length - 1].x.toFixed(1)} ${g.y0} Z`;
      s += `<path d="${area}" fill="url(#grad-${cssId(name)})"/>`;
    }
    s += `<path class="line" d="${line}" fill="none" stroke="${color}" stroke-width="2.25" stroke-linejoin="round" stroke-linecap="round"/>`;
    pts.forEach((p) => { s += `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="2.6" fill="${color}"/>`; });
  });

  // x labels: first + last
  if (xDates.length) {
    s += `<text class="axis" x="${g.x0}" y="${g.y0 + 20}" text-anchor="start" font-size="11">${fmtDay(xDates[0])}</text>`;
    if (xDates.length > 1)
      s += `<text class="axis" x="${g.x1}" y="${g.y0 + 20}" text-anchor="end" font-size="11">${fmtDay(xDates[xDates.length - 1])}</text>`;
  }

  // hover guide placeholder
  s += `<line id="guide" x1="0" y1="${g.y1}" x2="0" y2="${g.y0}" stroke-width="1" stroke-dasharray="3 3" style="display:none"/>`;
  svg.innerHTML = s;

  if (animate) {
    svg.querySelectorAll("path.line").forEach((path) => {
      const len = path.getTotalLength();
      path.style.strokeDasharray = len;
      path.style.strokeDashoffset = len;
      path.getBoundingClientRect(); // force reflow so the transition runs
      path.style.transition = "stroke-dashoffset .8s ease";
      path.style.strokeDashoffset = "0";
    });
  }
  wireHover(g, visible, xDates.length);
}

function cssId(name) { return name.replace(/[^a-zA-Z0-9_-]/g, "_"); }

function wireHover(g, visible, n) {
  const svg = document.getElementById("chart");
  const tip = document.getElementById("tooltip");
  const guide = svg.querySelector("#guide");
  const host = document.getElementById("chart-host");

  function move(ev) {
    if (n < 1) return;
    const rect = svg.getBoundingClientRect();
    const sx = ((ev.clientX - rect.left) / rect.width) * g.W; // viewBox==host width
    const step = n <= 1 ? 0 : (g.x1 - g.x0) / (n - 1);
    let i = step ? Math.round((sx - g.x0) / step) : 0;
    i = Math.max(0, Math.min(n - 1, i));
    const gx = n <= 1 ? (g.x0 + g.x1) / 2 : g.x0 + i * step;
    guide.setAttribute("x1", gx); guide.setAttribute("x2", gx); guide.style.display = "";

    let rows = "", date = "", minY = g.y0;
    visible.forEach((name) => {
      const pts = seriesPoints(name, g);
      const p = pts[Math.min(i, pts.length - 1)];
      if (!p) return;
      date = p.date; minY = Math.min(minY, p.y);
      rows += `<div class="tt-row"><span class="dot" style="background:${STATE.colors[name]}"></span>${name} <b>${p.score.toFixed(1)}</b></div>`;
    });
    tip.innerHTML = `<div class="tt-date">${fmtDateTime(date)}</div>${rows}`;
    tip.hidden = false;
    const px = (gx / g.W) * host.clientWidth;
    const py = (minY / g.H) * host.clientHeight;
    tip.style.left = px + "px";
    tip.style.top = py + "px";
  }
  svg.addEventListener("mousemove", move);
  svg.addEventListener("mouseleave", () => { tip.hidden = true; guide.style.display = "none"; });
}

// ---- table ----------------------------------------------------------------
function rowCell(row, key, rank) {
  switch (key) {
    case "rank": return `<td class="num rank${rank === 1 ? " medal" : ""}">${rank}</td>`;
    case "scenario":
      return `<td><span class="dot-tag" style="background:${STATE.colors[row.scenario]}"></span><strong>${row.scenario}</strong><span class="cfg">${row.config_file}</span></td>`;
    case "modality": return `<td>${row.modality || "—"}</td>`;
    case "problem": return `<td>${row.problem || "—"}</td>`;
    case "code_distance_d": return `<td class="num">${row.code_distance_d ?? "—"}</td>`;
    case "physical_qubits": return `<td class="num">${fmtInt(row.physical_qubits)}</td>`;
    case "wall_clock_days": return `<td class="num">${fmtWall(row.wall_clock_days)}</td>`;
    case "feasibility_score": {
      const cls = scoreClass(row.feasibility_score);
      const w = row.feasibility_score == null ? 0 : row.feasibility_score;
      return `<td class="num"><div class="fcell">
        <div class="ftop"><span class="pill ${cls}">${fmtScore(row.feasibility_score)}</span>${deltaBadge(row.scenario)}</div>
        <div class="fbar"><span class="${cls}" style="width:${w}%"></span></div>
      </div></td>`;
    }
    default: return "<td></td>";
  }
}

const COLS = ["rank", "scenario", "modality", "problem", "code_distance_d", "physical_qubits", "wall_clock_days", "feasibility_score"];

function renderTable(rows) {
  document.querySelector("#board tbody").innerHTML = rows
    .map((row, idx) => `<tr${idx === 0 ? ' class="tr-leader"' : ""}>` + COLS.map((k) => rowCell(row, k, idx + 1)).join("") + "</tr>")
    .join("");
}

function wireSorting(baseRows) {
  const ths = document.querySelectorAll("#board thead th[data-key]");
  ths.forEach((th) => th.addEventListener("click", () => {
    const key = th.dataset.key;
    const dir = th.getAttribute("aria-sort") === "descending" ? "ascending" : "descending";
    ths.forEach((o) => o.removeAttribute("aria-sort"));
    th.setAttribute("aria-sort", dir);
    const mul = dir === "ascending" ? 1 : -1;
    const sorted = key === "rank" ? (dir === "ascending" ? baseRows : [...baseRows].reverse())
      : [...baseRows].sort((a, b) => {
          const av = a[key], bv = b[key];
          if (av == null) return 1; if (bv == null) return -1;
          return (NUM_KEYS.has(key) ? av - bv : String(av).localeCompare(String(bv))) * mul;
        });
    renderTable(sorted);
  }));
}

// ---- boot -----------------------------------------------------------------
async function main() {
  try {
    const res = await fetch("data.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    STATE.data = data;
    data.scenarios.forEach((s, i) => { STATE.colors[s.scenario] = PALETTE[i % PALETTE.length]; });
    STATE.visible = new Set(data.scenarios.map((s) => s.scenario));

    document.getElementById("nav-methodology").href = data.score_formula_doc || "#";
    renderSummary(data);
    renderPills(data);
    drawChart(true);
    renderTable(data.scenarios);
    wireSorting(data.scenarios);
    let t; window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => drawChart(false), 120); });
  } catch (err) {
    document.querySelector("main").innerHTML =
      '<div class="error">Could not load <code>data.json</code>: ' + err.message + "</div>";
  }
}

main();
