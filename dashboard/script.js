// --- Configuration ---
const VIDEO_URL = "/video";
const EVENTS_URL = "/events?limit=20";
const HEALTH_URL = "/health";

const REFRESH_VIDEO_MS = 300;   // ~3 fps refresh
const REFRESH_EVENTS_MS = 1000; // poll events every second
const REFRESH_HEALTH_MS = 3000; // ping backend health

// --- DOM elements ---
const videoImg = document.getElementById("video-feed");
const videoError = document.getElementById("video-error");

const statusBadge = document.getElementById("status-badge");
const fpsLabel = document.getElementById("fps-label");
const detectionsLabel = document.getElementById("detections-label");
const classesLabel = document.getElementById("classes-label");
const eventsBody = document.getElementById("events-body");
const eventsLimitLabel = document.getElementById("events-limit-label");
const clearEventsBtn = document.getElementById("clear-events");

// --- State ---
let lastEvents = [];
let lastFrameTime = null;

// --- Helpers ---
function setStatus(connected) {
  if (!statusBadge) return;
  if (connected) {
    statusBadge.textContent = "● Connected";
    statusBadge.classList.remove("status-badge--disconnected");
    statusBadge.classList.add("status-badge--connected");
  } else {
    statusBadge.textContent = "● Disconnected";
    statusBadge.classList.remove("status-badge--connected");
    statusBadge.classList.add("status-badge--disconnected");
  }
}

function formatTime(ts) {
  // ts: unix timestamp (float or int)
  try {
    const date = new Date(ts * 1000);
    return date.toLocaleTimeString();
  } catch {
    return "--:--:--";
  }
}

function updateFPSFromEvents(events) {
  if (!events || events.length < 2) {
    fpsLabel.textContent = "FPS: --";
    return;
  }
  const first = events[0];
  const last = events[events.length - 1];

  const df = (last.frame ?? 0) - (first.frame ?? 0);
  const dt = (last.timestamp ?? 0) - (first.timestamp ?? 0);

  if (df > 0 && dt > 0) {
    const fps = df / dt;
    fpsLabel.textContent = `FPS: ${fps.toFixed(1)}`;
  } else {
    fpsLabel.textContent = "FPS: --";
  }
}

function updateDetectionSummary(events) {
  if (!events || events.length === 0) {
    detectionsLabel.textContent = "Detections: 0";
    classesLabel.textContent = "Classes: --";
    return;
  }

  let totalDetections = 0;
  const classSet = new Set();

  events.forEach((ev) => {
    const n = ev.num_detections ?? 0;
    totalDetections += n;

    if (Array.isArray(ev.classes)) {
      ev.classes.forEach((c) => classSet.add(c));
    } else if (Array.isArray(ev.detections)) {
      ev.detections.forEach((d) => {
        if (d.class_name) classSet.add(d.class_name);
      });
    }
  });

  detectionsLabel.textContent = `Detections: ${totalDetections}`;
  classesLabel.textContent =
    classSet.size > 0 ? `Classes: ${Array.from(classSet).join(", ")}` : "Classes: --";
}

function renderEventsTable(events) {
  if (!eventsBody) return;
  eventsBody.innerHTML = "";

  if (!events || events.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = "No events yet.";
    cell.className = "events-empty";
    row.appendChild(cell);
    eventsBody.appendChild(row);
    return;
  }

  events.forEach((ev) => {
    const row = document.createElement("tr");

    const timeCell = document.createElement("td");
    timeCell.textContent = formatTime(ev.timestamp ?? 0);

    const frameCell = document.createElement("td");
    frameCell.textContent = ev.frame ?? "--";

    const numCell = document.createElement("td");
    numCell.textContent = ev.num_detections ?? 0;

    const classesCell = document.createElement("td");
    let classesText = "";
    if (Array.isArray(ev.classes)) {
      classesText = ev.classes.join(", ");
    } else if (Array.isArray(ev.detections)) {
      const cls = ev.detections.map((d) => d.class_name || "?");
      classesText = cls.join(", ");
    } else {
      classesText = "--";
    }
    classesCell.textContent = classesText;

    row.appendChild(timeCell);
    row.appendChild(frameCell);
    row.appendChild(numCell);
    row.appendChild(classesCell);

    eventsBody.appendChild(row);
  });
}

// --- Polling functions ---
async function refreshVideo() {
  if (!videoImg) return;

  // Cache-busting query param so browser fetches fresh frame
  const url = `${VIDEO_URL}?cache=${Date.now()}`;
  videoImg.src = url;
}

async function refreshEvents() {
  try {
    const res = await fetch(EVENTS_URL);
    if (!res.ok) throw new Error("Events fetch failed");
    const events = await res.json();
    lastEvents = Array.isArray(events) ? events : [];

    // Update limit label (if backend respects "limit" query)
    const limitMatch = EVENTS_URL.match(/limit=(\d+)/);
    if (limitMatch && eventsLimitLabel) {
      eventsLimitLabel.textContent = limitMatch[1];
    }

    renderEventsTable(lastEvents);
    updateFPSFromEvents(lastEvents);
    updateDetectionSummary(lastEvents);
  } catch (err) {
    console.error("Error fetching events:", err);
  }
}

async function checkHealth() {
  try {
    const res = await fetch(HEALTH_URL);
    if (res.ok) {
      setStatus(true);
    } else {
      setStatus(false);
    }
  } catch (err) {
    console.warn("Health check failed:", err);
    setStatus(false);
  }
}

// Handle video load / error events
if (videoImg) {
  videoImg.addEventListener("load", () => {
    if (videoError) videoError.classList.add("hidden");
  });
  videoImg.addEventListener("error", () => {
    if (videoError) videoError.classList.remove("hidden");
  });
}

// Clear events button
if (clearEventsBtn) {
  clearEventsBtn.addEventListener("click", () => {
    lastEvents = [];
    renderEventsTable(lastEvents);
    updateFPSFromEvents(lastEvents);
    updateDetectionSummary(lastEvents);
  });
}

// Footer year
const yearSpan = document.getElementById("year");
if (yearSpan) {
  yearSpan.textContent = new Date().getFullYear().toString();
}

// --- Kick things off ---
window.addEventListener("DOMContentLoaded", () => {
  setStatus(false);
  refreshVideo();
  refreshEvents();
  checkHealth();

  setInterval(refreshVideo, REFRESH_VIDEO_MS);
  setInterval(refreshEvents, REFRESH_EVENTS_MS);
  setInterval(checkHealth, REFRESH_HEALTH_MS);
});
