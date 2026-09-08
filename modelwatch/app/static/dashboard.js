"use strict";

const PALETTE = [
  "#5b8def", "#d29922", "#3fb950", "#f85149", "#a371f7",
  "#39c5cf", "#db61a2", "#e3b341", "#6cb6ff", "#7ee787",
];

const fmt = (v, d = 3) => (v === null || v === undefined || Number.isNaN(v) ? "—" : Number(v).toFixed(d));
const shortTime = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—");

let driftChart, perfChart, distChart;

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return r.json();
}

// --------------------------------------------------------------- overview + tables
async function loadSummary() {
  const data = await getJSON("/dashboard/api/summary");

  document.getElementById("kpis").innerHTML = `
    <div class="kpi"><span class="v">${data.experiments}</span><span class="k">experiments</span></div>
    <div class="kpi"><span class="v">${data.runs.length}</span><span class="k">runs</span></div>
    <div class="kpi"><span class="v">${data.prediction_count}</span><span class="k">predictions logged</span></div>
    <div class="kpi"><span class="v">${data.retrain_events.filter(e => e.new_run_id).length}</span><span class="k">auto-retrains</span></div>`;

  const rows = data.runs.slice().reverse().map((r) => {
    const m = r.metrics || {};
    return `<tr>
      <td class="num">${r.id}</td>
      <td>${r.model_name ?? "—"}</td>
      <td class="mono">${r.model_type ?? "—"}</td>
      <td><span class="pill ${r.status}">${r.status}</span></td>
      <td class="num">${fmt(m.accuracy)}</td>
      <td class="num">${fmt(m.precision)}</td>
      <td class="num">${fmt(m.recall)}</td>
      <td class="num">${fmt(m.f1)}</td>
      <td class="num">${fmt(m.auc)}</td>
      <td class="num">${fmt(r.train_duration_seconds, 2)}s</td>
      <td class="num">${r.n_training_rows ?? "—"}</td>
      <td class="mono">${shortTime(r.created_at)}</td>
    </tr>`;
  }).join("");

  document.getElementById("runs-table").innerHTML = `
    <table>
      <thead><tr>
        <th class="num">#</th><th>name</th><th>type</th><th>status</th>
        <th class="num">acc</th><th class="num">prec</th><th class="num">rec</th>
        <th class="num">f1</th><th class="num">auc</th><th class="num">train</th>
        <th class="num">rows</th><th>created</th>
      </tr></thead>
      <tbody>${rows || `<tr><td colspan="12" class="empty">no runs yet</td></tr>`}</tbody>
    </table>`;

  const events = data.retrain_events;
  document.getElementById("events").innerHTML = events.length
    ? events.map((e) => `
        <li class="${e.new_run_id ? "retrained" : ""}">
          <div class="when">${shortTime(e.created_at)} &middot; monitored run ${e.run_id} &middot; by ${e.triggered_by}</div>
          <div>${e.reason ?? ""}</div>
          ${e.new_run_id ? `<div class="mono">→ new run ${e.new_run_id}</div>` : ""}
        </li>`).join("")
    : `<li class="muted">No retrain events recorded yet.</li>`;

  return data;
}

// --------------------------------------------------------------- performance chart
async function loadPerformance() {
  const { points } = await getJSON("/dashboard/api/performance");
  const labels = points.map((p) => `run ${p.run_id}`);
  const mk = (key, color) => ({
    label: key, data: points.map((p) => p[key]), borderColor: color,
    backgroundColor: color, tension: 0.25, spanGaps: true, pointRadius: 4,
  });
  const cfg = {
    type: "line",
    data: { labels, datasets: [mk("accuracy", PALETTE[0]), mk("f1", PALETTE[1]), mk("auc", PALETTE[2])] },
    options: baseOpts({ yMin: 0, yMax: 1, yTitle: "score" }),
  };
  if (perfChart) perfChart.destroy();
  perfChart = new Chart(document.getElementById("perfChart"), cfg);
}

// --------------------------------------------------------------- drift timeline
async function loadDriftTimeline(runId) {
  const data = await getJSON(`/dashboard/api/drift-timeline/${runId}`);
  const checkpoints = data.checkpoints || [];
  const labels = checkpoints.map((_, i) => `check ${i + 1}`);
  document.getElementById("drift-meta").textContent =
    `${checkpoints.length} check(s) · PSI threshold ${data.psi_threshold}`;

  const featureNames = Object.keys(data.features);
  const datasets = featureNames.map((name, i) => ({
    label: name,
    data: (data.features[name].psi || []).map((d) => d.value),
    borderColor: PALETTE[i % PALETTE.length],
    backgroundColor: PALETTE[i % PALETTE.length],
    tension: 0.25, pointRadius: 3, borderWidth: 2,
  }));

  // Threshold line.
  if (labels.length) {
    datasets.push({
      label: `threshold (${data.psi_threshold})`,
      data: labels.map(() => data.psi_threshold),
      borderColor: "#f85149", borderDash: [6, 4], pointRadius: 0, borderWidth: 1.5,
    });
  }

  const cfg = {
    type: "line",
    data: { labels, datasets },
    options: baseOpts({ yTitle: "PSI", yMin: 0 }),
  };
  if (driftChart) driftChart.destroy();
  driftChart = new Chart(document.getElementById("driftChart"), cfg);
}

// --------------------------------------------------------------- feature distribution
async function loadFeatureList(runId) {
  const data = await getJSON(`/dashboard/api/feature-distribution/${runId}`);
  const sel = document.getElementById("feature-select");
  const current = sel.value;
  sel.innerHTML = (data.features || []).map((f) => `<option value="${f}">${f}</option>`).join("");
  if (current && data.features.includes(current)) sel.value = current;
  return data.feature;
}

async function loadDistribution(runId, feature) {
  const q = feature ? `?feature=${encodeURIComponent(feature)}` : "";
  const data = await getJSON(`/dashboard/api/feature-distribution/${runId}${q}`);
  document.getElementById("dist-meta").textContent =
    `baseline n=${data.baseline_n} · current n=${data.current_n}`;

  const cfg = {
    type: "bar",
    data: {
      labels: data.bin_centers,
      datasets: [
        { label: "baseline", data: data.baseline_counts, backgroundColor: "rgba(91,141,239,0.55)" },
        { label: "current", data: data.current_counts, backgroundColor: "rgba(210,153,34,0.6)" },
      ],
    },
    options: baseOpts({ yTitle: "count", xTitle: data.feature, stacked: false }),
  };
  if (distChart) distChart.destroy();
  distChart = new Chart(document.getElementById("distChart"), cfg);
}

// --------------------------------------------------------------- shared chart opts
function baseOpts({ yMin, yMax, yTitle, xTitle, stacked } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: "#99a0b0", boxWidth: 12 } },
      tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${fmt(c.parsed.y, 4)}` } },
    },
    scales: {
      x: {
        stacked: !!stacked,
        title: { display: !!xTitle, text: xTitle, color: "#99a0b0" },
        ticks: { color: "#99a0b0", maxRotation: 0, autoSkip: true },
        grid: { color: "#2a2f3d" },
      },
      y: {
        stacked: !!stacked,
        min: yMin, max: yMax,
        title: { display: !!yTitle, text: yTitle, color: "#99a0b0" },
        ticks: { color: "#99a0b0" },
        grid: { color: "#2a2f3d" },
      },
    },
  };
}

// --------------------------------------------------------------- wire-up
async function refreshRunScoped() {
  const runId = document.getElementById("run-select").value;
  if (!runId) return;
  await loadDriftTimeline(runId);
  const feature = await loadFeatureList(runId);
  await loadDistribution(runId, document.getElementById("feature-select").value || feature);
}

async function init() {
  const summary = await loadSummary();
  await loadPerformance();

  const runSel = document.getElementById("run-select");
  runSel.innerHTML = summary.runs
    .map((r) => `<option value="${r.id}">run ${r.id} (${r.model_type ?? "?"})</option>`)
    .join("");
  if (window.DEFAULT_RUN_ID) runSel.value = window.DEFAULT_RUN_ID;

  runSel.addEventListener("change", refreshRunScoped);
  document.getElementById("feature-select").addEventListener("change", () => {
    loadDistribution(runSel.value, document.getElementById("feature-select").value);
  });

  if (summary.runs.length) await refreshRunScoped();
}

init().catch((err) => {
  console.error(err);
  document.getElementById("kpis").innerHTML = `<span class="pill significant">error: ${err.message}</span>`;
});
