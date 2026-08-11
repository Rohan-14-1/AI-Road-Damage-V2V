/**
 * Shared utilities: device identity, URL builders, V2V panel.
 *
 * BACKEND_URL is defined in config.js (loaded before this file).
 * - Empty string "" = same origin (local dev, backend serves frontend)
 * - "https://your-app.onrender.com" = deployed backend
 */

/* ─── URL Builders ────────────────────────────────────────────── */

function getBackendBase() {
  // BACKEND_URL comes from config.js
  if (typeof BACKEND_URL !== "undefined" && BACKEND_URL) {
    return BACKEND_URL.replace(/\/+$/, ""); // strip trailing slash
  }
  return window.location.origin; // local dev fallback
}

function getDeviceId() {
  const key = "road-ai-device-id";
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = "device-" + Math.random().toString(36).slice(2, 8);
    sessionStorage.setItem(key, id);
  }
  return id;
}

function wsUrl(path) {
  const base = getBackendBase();
  // Convert http(s) to ws(s)
  const wsBase = base.replace(/^http/, "ws");
  return `${wsBase}${path}`;
}

function apiUrl(path) {
  return `${getBackendBase()}${path}`;
}

/* ─── V2V Panel (shared component) ────────────────────────────── */
const MAX_V2V_LOG = 12;

function initV2VPanel(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  container.innerHTML = `
    <div class="v2v-panel">
      <div class="v2v-header">
        <span class="v2v-title">V2V MESH</span>
        <span class="v2v-dot" id="v2v-dot"></span>
        <span class="v2v-status mono" id="v2v-status">LINK DOWN</span>
      </div>
      <div class="v2v-subnote">
        Simulated LoRa-inspired broadcast &middot; swappable for real hardware
      </div>
      <div class="v2v-log" id="v2v-log">
        <div class="v2v-empty" id="v2v-empty">No hazard broadcasts received yet.</div>
      </div>
    </div>
  `;

  const dot = document.getElementById("v2v-dot");
  const statusEl = document.getElementById("v2v-status");
  const logEl = document.getElementById("v2v-log");
  const emptyEl = document.getElementById("v2v-empty");

  const deviceId = getDeviceId();
  const ws = new WebSocket(wsUrl(`/ws/v2v/${deviceId}`));

  ws.onopen = () => {
    dot.classList.add("connected");
    statusEl.textContent = "LINK UP";
  };

  ws.onclose = () => {
    dot.classList.remove("connected");
    statusEl.textContent = "LINK DOWN";
  };

  ws.onerror = () => {
    dot.classList.remove("connected");
    statusEl.textContent = "LINK DOWN";
  };

  ws.onmessage = (msg) => {
    const event = JSON.parse(msg.data);
    emptyEl.classList.add("hidden");

    const sevClass = (event.severity === "high") ? "high"
                   : (event.severity === "medium") ? "medium"
                   : "low";

    const el = document.createElement("div");
    el.className = "v2v-event";
    el.innerHTML = `
      <span class="sev-tag ${sevClass}">${event.severity}</span>
      <span style="font-weight:600">${event.damage_type.replace(/_/g, " ")}</span>
      <span class="v2v-event-meta">
        ${Math.round(event.confidence * 100)}% &middot; ${event.source} &middot; ${event.device_id}
      </span>
    `;

    logEl.insertBefore(el, logEl.firstChild);

    // Cap the log
    while (logEl.children.length > MAX_V2V_LOG + 1) {
      logEl.removeChild(logEl.lastChild);
    }
  };

  return ws;
}
