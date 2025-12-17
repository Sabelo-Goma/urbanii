const videoFeed = document.getElementById("video-feed");
const videoError = document.getElementById("video-error");

const fpsLabel = document.getElementById("fps-label");
const detectionsLabel = document.getElementById("detections-label");
const classesLabel = document.getElementById("classes-label");

const eventsBody = document.getElementById("events-body");
const resetBtn = document.getElementById("reset-summary");
const sceneSelect = document.getElementById("sceneSelect");
const yearEl = document.getElementById("year");

const statusBadge = document.getElementById("status-badge");


yearEl.textContent = new Date().getFullYear();

let lastFrameTs = 0;

/* ================= STATUS ================= */
function setStatus(connected) {
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

      events.forEach(ev => {
        totalDetections += ev.num_detections || 0;

        (ev.detections || []).forEach(d => {
          classTotals[d.class_name] = (classTotals[d.class_name] || 0) + 1;
        });

        const row = document.createElement("tr");
        row.innerHTML = `
          <td>${new Date(ev.timestamp * 1000).toLocaleTimeString()}</td>
          <td>${ev.frame ?? "-"}</td>
          <td>${ev.num_detections}</td>
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
    });
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
  const res = await fetch("/scenes/switch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scene: sceneSelect.value })
  });

  if (!res.ok) {
    console.error("Scene switch failed");
  }
});

/* ================= RESET ================= */

resetBtn.onclick = () => {
  eventsBody.innerHTML = "";
  detectionsLabel.textContent = "Detections: —";
  classesLabel.textContent = "Classes: —";
};

/* ================= LOOP ================= */

setInterval(refreshVideo, 500);
setInterval(refreshEvents, 1000);
loadScenes();
