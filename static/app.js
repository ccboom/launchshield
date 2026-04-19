(function () {
  "use strict";

  const elements = {
    ctaPreset: document.getElementById("cta-preset"),
    customForm: document.getElementById("custom-form"),
    executionPanel: document.getElementById("execution-panel"),
    billingPanel: document.getElementById("billing-panel"),
    findingsPanel: document.getElementById("findings-panel"),
    profitPanel: document.getElementById("profit-panel"),
    runMode: document.getElementById("run-mode"),
    runIdPill: document.getElementById("run-id"),
    progressFill: document.getElementById("progress-fill"),
    progressCount: document.getElementById("progress-count"),
    progressStage: document.getElementById("progress-stage"),
    metricCompleted: document.getElementById("metric-completed"),
    metricConfirmed: document.getElementById("metric-confirmed"),
    metricCritical: document.getElementById("metric-critical"),
    metricHigh: document.getElementById("metric-high"),
    metricMedium: document.getElementById("metric-medium"),
    metricLow: document.getElementById("metric-low"),
    billingFeed: document.getElementById("billing-feed"),
    billingTail: document.getElementById("billing-tail"),
    findingsList: document.getElementById("findings-list"),
    findingsCount: document.getElementById("findings-count"),
    profitToolCost: document.getElementById("profit-tool-cost"),
    profitSettled: document.getElementById("profit-settled"),
    profitGas: document.getElementById("profit-gas"),
    profitConclusion: document.getElementById("profit-conclusion"),
  };

  const state = {
    runId: null,
    eventSource: null,
    planned: 0,
    completed: 0,
    confirmed: 0,
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    invocations: new Map(),
    findings: [],
  };

  function resetState() {
    state.runId = null;
    state.planned = 0;
    state.completed = 0;
    state.confirmed = 0;
    state.critical = 0;
    state.high = 0;
    state.medium = 0;
    state.low = 0;
    state.invocations.clear();
    state.findings = [];
    elements.billingFeed.innerHTML = "";
    elements.findingsList.innerHTML = "";
    elements.progressFill.style.width = "0%";
    elements.progressCount.textContent = "0 / 0";
    elements.progressStage.textContent = "queued";
    elements.metricCompleted.textContent = "0";
    elements.metricConfirmed.textContent = "0";
    elements.metricCritical.textContent = "0";
    elements.metricHigh.textContent = "0";
    elements.metricMedium.textContent = "0";
    elements.metricLow.textContent = "0";
    elements.profitToolCost.textContent = "$0.000";
    elements.profitSettled.textContent = "0.000 USDC";
    elements.profitGas.textContent = "$0.000";
  }

  function showPanels() {
    elements.executionPanel.hidden = false;
    elements.billingPanel.hidden = false;
    elements.findingsPanel.hidden = false;
    elements.profitPanel.hidden = false;
  }

  function updateProgress() {
    elements.progressCount.textContent = `${state.completed} / ${state.planned}`;
    const pct = state.planned > 0 ? Math.min(100, (state.completed / state.planned) * 100) : 0;
    elements.progressFill.style.width = pct.toFixed(1) + "%";
    elements.metricCompleted.textContent = String(state.completed);
    elements.metricConfirmed.textContent = String(state.confirmed);
    elements.metricCritical.textContent = String(state.critical);
    elements.metricHigh.textContent = String(state.high);
    elements.metricMedium.textContent = String(state.medium);
    elements.metricLow.textContent = String(state.low);
  }

  function formatTime(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch (_) {
      return "--:--:--";
    }
  }

  function shortHash(hash) {
    if (!hash) return "—";
    return hash.length > 14 ? hash.slice(0, 8) + "…" + hash.slice(-4) : hash;
  }

  function ensureBillingRow(invocationId) {
    let row = state.invocations.get(invocationId);
    if (row) return row;
    const li = document.createElement("li");
    li.className = "billing-row submitted";
    li.dataset.invocation = invocationId;
    li.innerHTML = `
      <span class="time">--:--:--</span>
      <span class="tool">—</span>
      <span class="target">—</span>
      <span class="amount">—</span>
      <span class="tx">pending</span>
    `;
    elements.billingFeed.prepend(li);
    row = {
      element: li,
      time: li.querySelector(".time"),
      tool: li.querySelector(".tool"),
      target: li.querySelector(".target"),
      amount: li.querySelector(".amount"),
      tx: li.querySelector(".tx"),
    };
    state.invocations.set(invocationId, row);
    return row;
  }

  function renderFinding(finding) {
    state.findings.push(finding);
    const severity = (finding.severity || "low").toLowerCase();
    if (severity === "critical") state.critical += 1;
    else if (severity === "high") state.high += 1;
    else if (severity === "medium") state.medium += 1;
    else state.low += 1;
    updateProgress();

    elements.findingsCount.textContent = String(state.findings.length);
    const list = elements.findingsList;
    if (list.children.length >= 10) {
      list.removeChild(list.lastChild);
    }
    const li = document.createElement("li");
    li.className = `finding-card ${severity}`;
    li.innerHTML = `
      <header>
        <h3></h3>
        <span class="severity"></span>
      </header>
      <p></p>
    `;
    li.querySelector("h3").textContent = finding.title || finding.finding_id;
    li.querySelector(".severity").textContent = `${severity} · ${finding.source || ""}`;
    li.querySelector("p").textContent = finding.summary || "";
    list.prepend(li);
  }

  function applyEvent(event) {
    const { type, payload, emitted_at } = event;
    const time = formatTime(emitted_at);
    switch (type) {
      case "run.started": {
        state.planned = payload.planned_invocations || 0;
        updateProgress();
        elements.progressStage.textContent = "starting";
        break;
      }
      case "stage.started": {
        elements.progressStage.textContent = payload.stage;
        break;
      }
      case "tool.invoked": {
        const row = ensureBillingRow(payload.invocation_id);
        row.time.textContent = time;
        row.tool.textContent = payload.tool_name;
        row.target.textContent = payload.target;
        row.amount.textContent = `${payload.price_usd.toFixed(3)} USD`;
        row.tx.textContent = "invoked";
        break;
      }
      case "payment.submitted": {
        const row = ensureBillingRow(payload.invocation_id);
        row.tx.textContent = "submitted";
        row.element.classList.remove("confirmed", "failed");
        row.element.classList.add("submitted");
        break;
      }
      case "payment.confirmed": {
        state.confirmed += 1;
        updateProgress();
        const row = ensureBillingRow(payload.invocation_id);
        row.element.classList.remove("submitted", "failed");
        row.element.classList.add("confirmed");
        const hashText = shortHash(payload.tx_hash);
        if (payload.explorer_url) {
          row.tx.innerHTML = `<a target="_blank" rel="noreferrer"></a>`;
          const link = row.tx.querySelector("a");
          link.href = payload.explorer_url;
          link.textContent = hashText;
        } else {
          row.tx.textContent = hashText;
        }
        if (payload.amount_usdc) {
          row.amount.textContent = `${payload.amount_usdc.toFixed(3)} USDC`;
        }
        break;
      }
      case "tool.completed": {
        state.completed += 1;
        updateProgress();
        break;
      }
      case "tool.failed": {
        state.completed += 1;
        updateProgress();
        const row = ensureBillingRow(payload.invocation_id);
        row.element.classList.add("failed");
        row.tx.textContent = "failed";
        break;
      }
      case "finding.created": {
        renderFinding(payload);
        break;
      }
      case "stage.completed": {
        if (payload.stage === "summary.profitability") {
          elements.profitToolCost.textContent = `$${(payload.tool_cost_usd || 0).toFixed(3)}`;
          elements.profitSettled.textContent = `${(payload.settled_usdc || 0).toFixed(3)} USDC`;
          elements.profitGas.textContent = `$${(payload.traditional_gas_estimate_usd || 0).toFixed(3)}`;
        }
        break;
      }
      case "run.completed": {
        elements.progressStage.textContent = "completed";
        elements.billingTail.textContent = "complete";
        if (payload.profitability) {
          const p = payload.profitability;
          elements.profitToolCost.textContent = `$${(p.tool_cost_usd || 0).toFixed(3)}`;
          elements.profitSettled.textContent = `${(p.settled_usdc || 0).toFixed(3)} USDC`;
          elements.profitGas.textContent = `$${(p.traditional_gas_estimate_usd || 0).toFixed(3)}`;
          if (p.conclusion_headline) {
            elements.profitConclusion.textContent = p.conclusion_headline;
          }
        }
        closeStream();
        break;
      }
      case "run.failed": {
        elements.progressStage.textContent = "failed";
        elements.billingTail.textContent = "failed";
        closeStream();
        break;
      }
      default:
        break;
    }
  }

  function closeStream() {
    if (state.eventSource) {
      state.eventSource.close();
      state.eventSource = null;
    }
  }

  function attachStream(runId, mode) {
    state.runId = runId;
    elements.runIdPill.textContent = runId;
    elements.runMode.textContent = mode;
    showPanels();

    const types = [
      "run.started",
      "stage.started",
      "tool.invoked",
      "payment.submitted",
      "payment.confirmed",
      "tool.completed",
      "tool.failed",
      "finding.created",
      "stage.completed",
      "run.completed",
      "run.failed",
    ];
    const source = new EventSource(`/api/runs/${runId}/events`);
    state.eventSource = source;
    for (const t of types) {
      source.addEventListener(t, (ev) => {
        try {
          const data = JSON.parse(ev.data);
          applyEvent(data);
        } catch (err) {
          console.error("bad event", err, ev);
        }
      });
    }
    source.onerror = () => {
      elements.billingTail.textContent = "disconnected";
    };
  }

  async function createRun(payload) {
    resetState();
    elements.billingTail.textContent = "live";
    const resp = await fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      alert(`Failed to start run: ${err.detail || resp.statusText}`);
      return;
    }
    const data = await resp.json();
    attachStream(data.run_id, data.mode);
  }

  elements.ctaPreset.addEventListener("click", () => {
    createRun({ mode: "preset-stress" });
  });

  elements.customForm.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const data = new FormData(elements.customForm);
    createRun({
      mode: "custom-standard",
      repo_url: data.get("repo_url"),
      target_url: data.get("target_url"),
    });
  });
})();
