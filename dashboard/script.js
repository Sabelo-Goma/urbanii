/* ================= DOM ================= */

const videoFeed = document.getElementById("video-feed");
const videoError = document.getElementById("video-error");

const detectionsLabel = document.getElementById("detections-label");
const classesLabel = document.getElementById("classes-label");

const eventsBody = document.getElementById("events-body");
const resetBtn = document.getElementById("reset-summary");
const sceneSelect = document.getElementById("sceneSelect");
const yearEl = document.getElementById("year");

const statusBadge = document.getElementById("status-badge");

const crowdMeter = document.getElementById("crowd-meter");
const crowdLevelEl = document.getElementById("crowd-level");
const crowdBarFill = document.getElementById("crowd-bar-fill");
const crowdTrendEl = document.getElementById("crowd-trend");

const trafficMeter = document.getElementById("traffic-meter");
const trafficLevelEl = document.getElementById("traffic-level");
const trafficBarFill = document.getElementById("traffic-bar-fill");
const trafficTrendEl = document.getElementById("traffic-trend");

const loiteringAlert = document.getElementById("loitering-alert");
const loiteringDetails = document.getElementById("loitering-details");

const industrialAlert = document.getElementById("industrial-alert");
const industrialDetails = document.getElementById("industrial-details");

yearEl.textContent = new Date().getFullYear();

/* ================= STATUS ================= */

function setStatus(connected) {
  statusBadge.textContent = connected ? "● Connected" : "● Disconnected";
  statusBadge.className =
    "status-badge " +
    (connected ? "status-badge--connected" : "status-badge--disconnected");
}

/* ================= CROWD ================= */

function resetCrowdMeter() {
  crowdLevelEl.textContent = "—";
  crowdLevelEl.className = "crowd-level";
  crowdBarFill.style.width = "0%";
  crowdTrendEl.textContent = "—";
}

function updateCrowdMeter(crowd) {
  if (!crowd) return resetCrowdMeter();

  crowdLevelEl.className = "crowd-level";

  if (crowd.density === "low") {
    crowdLevelEl.textContent = "LOW";
    crowdLevelEl.classList.add("crowd-level--low");
    crowdBarFill.style.width = "33%";
  } else if (crowd.density === "medium") {
    crowdLevelEl.textContent = "MEDIUM";
    crowdLevelEl.classList.add("crowd-level--medium");
    crowdBarFill.style.width = "66%";
  } else if (crowd.density === "high") {
    crowdLevelEl.textContent = "HIGH";
    crowdLevelEl.classList.add("crowd-level--high");
    crowdBarFill.style.width = "100%";
  } else {
    resetCrowdMeter();
  }

  crowdTrendEl.textContent =
    crowd.trend === "increasing" ? "↑ Crowd increasing" :
    crowd.trend === "decreasing" ? "↓ Crowd decreasing" :
    "→ Crowd stable";
}

/* ================= LOITERING ================= */

function showLoiteringAlert(loitering) {
  const count = loitering.subject_count ?? loitering.count ?? 1;
  const duration = loitering.duration_seconds ?? loitering.duration ?? "?";

  loiteringDetails.textContent =
    `${count} subject(s) stationary for ${duration}s`;

  loiteringAlert.classList.remove("intel-alert--hidden");
}

function hideLoiteringAlert() {
  loiteringAlert.classList.add("intel-alert--hidden");
}

/* ================= INDUSTRIAL ================= */

function showIndustrialAlert(industrial) {
  // Expecting something like:
  // industrial = { risk: "normal"|"elevated", ppe_missing_count: n, alerts: [...] }
  const risk = industrial?.risk ?? "unknown";
  const missing = industrial?.ppe_missing_count;

  if (typeof missing === "number") {
    industrialDetails.textContent =
      `Safety risk: ${risk}. PPE missing signals: ${missing}.`;
  } else if (industrial?.message) {
    industrialDetails.textContent = industrial.message;
  } else {
    industrialDetails.textContent =
      `Safety risk: ${risk}. Potential PPE / proximity risk detected.`;
  }

  industrialAlert.classList.remove("intel-alert--hidden");
}

function hideIndustrialAlert() {
  industrialAlert.classList.add("intel-alert--hidden");
}

/* ================= TRAFFIC ================= */

function resetTrafficMeter() {
  trafficLevelEl.textContent = "—";
  trafficLevelEl.className = "traffic-level";
  trafficBarFill.style.width = "0%";
  trafficTrendEl.textContent = "—";
}

function updateTrafficMeter(traffic) {
  if (!traffic) return resetTrafficMeter();

  trafficLevelEl.className = "traffic-level";

  if (traffic.density === "low") {
    trafficLevelEl.textContent = "LOW";
    trafficLevelEl.classList.add("traffic-level--low");
    trafficBarFill.style.width = "33%";
  } else if (traffic.density === "medium") {
    trafficLevelEl.textContent = "MEDIUM";
    trafficLevelEl.classList.add("traffic-level--medium");
    trafficBarFill.style.width = "66%";
  } else if (traffic.density === "high") {
    trafficLevelEl.textContent = "HIGH";
    trafficLevelEl.classList.add("traffic-level--high");
    trafficBarFill.style.width = "100%";
  } else {
    resetTrafficMeter();
  }

  trafficTrendEl.textContent =
    traffic.trend === "increasing" ? "↑ Traffic increasing" :
    traffic.trend === "decreasing" ? "↓ Traffic decreasing" :
    "→ Traffic stable";
}

/* ================= VIDEO ================= */

function refreshVideo() {
  const img = new Image();
  img.onload = () => {
    videoFeed.src = img.src;
    videoError.classList.add("hidden");
    setStatus(true);
  };
  img.onerror = () => {
    videoError.classList.remove("hidden");
    setStatus(false);
  };
  img.src = `/video?cache=${Date.now()}`;
}

/* ================= EVENTS ================= */

function refreshEvents() {
  fetch("/events?limit=20")
    .then(r => r.json())
    .then(events => {
      eventsBody.innerHTML = "";

      let classTotals = {};
      let totalDetections = 0;

      let crowdIntel = null;
      let loiteringIntel = null;
      let trafficIntel = null;
      let industrialIntel = null;

      const scene = sceneSelect.value;

      events.forEach(ev => {
        totalDetections += ev.num_detections || 0;

        (ev.detections || []).forEach(d => {
          classTotals[d.class_name] =
            (classTotals[d.class_name] || 0) + 1;
        });

        if (!crowdIntel && ev.intelligence?.crowd)
          crowdIntel = ev.intelligence.crowd;

        if (!loiteringIntel && ev.intelligence?.loitering?.active)
          loiteringIntel = ev.intelligence.loitering;

        if (!trafficIntel && ev.intelligence?.traffic)
          trafficIntel = ev.intelligence.traffic;

        if (!industrialIntel && ev.intelligence?.industrial)
          industrialIntel = ev.intelligence.industrial;

        const row = document.createElement("tr");
        row.innerHTML = `
          <td>${new Date(ev.timestamp * 1000).toLocaleTimeString()}</td>
          <td>${ev.num_detections ?? 0}</td>
          <td>${Object.keys(classTotals).join(", ")}</td>
        `;
        eventsBody.appendChild(row);
      });

      detectionsLabel.textContent = `Detections: ${totalDetections}`;
      classesLabel.textContent =
        "Classes: " +
        Object.entries(classTotals)
          .map(([k, v]) => `${k}(${v})`)
          .join(" ");

      /* ===== Scene-aware UI ===== */

      // Crowd (Shibuya only)
      if (scene === "shibuya") {
        crowdMeter.classList.remove("hidden");
        updateCrowdMeter(crowdIntel);
        loiteringIntel ? showLoiteringAlert(loiteringIntel) : hideLoiteringAlert();
      } else {
        crowdMeter.classList.add("hidden");
        resetCrowdMeter();
        hideLoiteringAlert();
      }

      // Traffic (Highway only)
      if (scene === "highway") {
        trafficMeter.classList.remove("hidden");
        updateTrafficMeter(trafficIntel);
      } else {
        trafficMeter.classList.add("hidden");
        resetTrafficMeter();
      }

      // Industrial (Industrial only)
      if (scene === "industrial") {
        //hide other scene alerts)
        crowdMeter.classList.add("hidden");
        trafficMeter.classList.add("hidden");
        resetCrowdMeter();
        resetTrafficMeter();
        hideLoiteringAlert();

        //show safety banner if meaningful data//
        const shouldShow =
          industrialIntel &&
          (industrialIntel.risk !== "elevated" ||
           (Array.isArray(industrialIntel.alerts) && industrialIntel.alerts.length > 0) ||
           (typeof industrialIntel.ppe_missing_count === "number" &&
            industrialIntel.ppe_missing_count === "number" && industrialIntel.ppe_missing_count > 0));
        
        shouldShow ? showIndustrialAlert(industrialIntel) : hideIndustrialAlert();
      } else {
        hideIndustrialAlert() ;
      }    
    })
    .catch(err => console.error("Failed to refresh events", err));
}

/* ================= SCENES ================= */

function loadScenes() {
  fetch("/scenes")
    .then(r => r.json())
    .then(data => {
      sceneSelect.innerHTML = "";
      Object.entries(data.scenes).forEach(([key, scene]) => {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = scene.label;
        if (key === data.active) opt.selected = true;
        sceneSelect.appendChild(opt);
      });
    });
}

sceneSelect.addEventListener("change", async () => {
  await fetch("/scenes/switch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scene: sceneSelect.value })
  });

  eventsBody.innerHTML = "";
  resetCrowdMeter();
  resetTrafficMeter();
  hideLoiteringAlert();
  hideIndustrialAlert();
});

/* ================= RESET ================= */

resetBtn.onclick = () => {
  eventsBody.innerHTML = "";
  detectionsLabel.textContent = "Detections: —";
  classesLabel.textContent = "Classes: —";
  resetCrowdMeter();
  resetTrafficMeter();
  hideLoiteringAlert();
  hideIndustrialAlert();
};

/* ================= LOOP ================= */

setInterval(refreshVideo, 500);
setInterval(refreshEvents, 1000);
loadScenes();
