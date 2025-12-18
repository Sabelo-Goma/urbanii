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

const loiteringAlert = document.getElementById("loitering-alert");
const loiteringDetails = document.getElementById("loitering-details");

yearEl.textContent = new Date().getFullYear();

let activeScene = null;

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
  loiteringDetails.textContent =
    `${loitering.subject_count ?? 1} subject(s) stationary for ${loitering.duration_seconds ?? "?"}s`;
  loiteringAlert.classList.remove("intel-alert--hidden");
}

function hideLoiteringAlert() {
  loiteringAlert.classList.add("intel-alert--hidden");
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

      events.forEach(ev => {
        totalDetections += ev.num_detections || 0;

        (ev.detections || []).forEach(d => {
          classTotals[d.class_name] =
            (classTotals[d.class_name] || 0) + 1;
        });

        if (!crowdIntel && ev.intelligence?.crowd) {
          crowdIntel = ev.intelligence.crowd;
        }

        if (!loiteringIntel && ev.intelligence?.loitering?.active) {
          loiteringIntel = ev.intelligence.loitering;
        }

        const row = document.createElement("tr");
        row.innerHTML = `
          <td>${new Date(ev.timestamp * 1000).toLocaleTimeString()}</td>
          <td>${ev.frame ?? "-"}</td>
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

      // Scene-aware intelligence
      if (activeScene === "shibuya") {
        crowdMeter.style.opacity = "1";
        updateCrowdMeter(crowdIntel);
        loiteringIntel ? showLoiteringAlert(loiteringIntel) : hideLoiteringAlert();
      } else {
        crowdMeter.style.opacity = "0.35";
        resetCrowdMeter();
        hideLoiteringAlert();
      }
    });
}

/* ================= SCENES ================= */
function loadScenes() {
  fetch("/scenes")
    .then(r => r.json())
    .then(data => {
      activeScene = data.active;
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

  activeScene = sceneSelect.value;
  eventsBody.innerHTML = "";
  resetCrowdMeter();
  hideLoiteringAlert();
});

/* ================= RESET ================= */
resetBtn.onclick = () => {
  eventsBody.innerHTML = "";
  detectionsLabel.textContent = "Detections: —";
  classesLabel.textContent = "Classes: —";
  resetCrowdMeter();
  hideLoiteringAlert();
};

/* ================= LOOP ================= */
setInterval(refreshVideo, 500);
setInterval(refreshEvents, 1000);
loadScenes();
