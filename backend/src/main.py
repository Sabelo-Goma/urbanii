from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel
import time
import logging

# -----------------------------------------------------------------------------
# App + logging
# -----------------------------------------------------------------------------

app = FastAPI()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("urbanii-backend")

# -----------------------------------------------------------------------------
# Scene configuration (authoritative list)
# -----------------------------------------------------------------------------

SCENES = {
    "shibuya": {
        "label": "Shibuya Crossing",
        "type": "youtube",
    },
    "industrial": {
        "label": "Industrial Yard",
        "type": "hls",
    },
    "highway": {
        "label": "Highway Traffic",
        "type": "hls",
    },
}

ACTIVE_SCENE = "shibuya"

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------

class SceneSwitchRequest(BaseModel):
    scene: str

# -----------------------------------------------------------------------------
# In-memory state (ephemeral by design)
# -----------------------------------------------------------------------------

last_video_frame: bytes | None = None
events: list[dict] = []

MAX_EVENTS = 500

# -----------------------------------------------------------------------------
# Scene management
# -----------------------------------------------------------------------------

@app.get("/scene")
def get_active_scene():
    """
    Used by inference node to poll current scene.
    """
    return {"scene": ACTIVE_SCENE}


@app.get("/scenes")
def list_scenes():
    """
    Used by dashboard to populate selector.
    """
    return {
        "active": ACTIVE_SCENE,
        "scenes": SCENES,
    }


@app.post("/scenes/switch")
def switch_scene(payload: SceneSwitchRequest):
    """
    Switch active scene.
    Clears events and video frame to prevent cross-scene bleed.
    """
    global ACTIVE_SCENE, last_video_frame

    if payload.scene not in SCENES:
        log.error(f"Scene switch failed — unknown scene: {payload.scene}")
        return JSONResponse(
            status_code=400,
            content={"error": "Unknown scene", "scene": payload.scene},
        )

    if payload.scene == ACTIVE_SCENE:
        return {
            "status": "noop",
            "active_scene": ACTIVE_SCENE,
        }

    ACTIVE_SCENE = payload.scene
    events.clear()
    last_video_frame = None

    log.info(f"🔁 Scene switched → {ACTIVE_SCENE}")

    return {
        "status": "ok",
        "active_scene": ACTIVE_SCENE,
    }

# -----------------------------------------------------------------------------
# Detection metadata (JSON only)
# -----------------------------------------------------------------------------

@app.post("/frame")
async def receive_frame(payload: dict):
    """
    Receives detection metadata from inference node.
    """
    payload["received_at"] = time.time()
    payload["scene"] = ACTIVE_SCENE

    events.append(payload)

    if len(events) > MAX_EVENTS:
        events.pop(0)

    return {"status": "ok"}


@app.get("/events")
def get_events(limit: int = 20):
    """
    Dashboard polling endpoint.
    """
    return JSONResponse(events[-limit:][::-1])

# -----------------------------------------------------------------------------
# Video frame transport (JPEG bytes)
# -----------------------------------------------------------------------------

@app.post("/video")
async def upload_video_frame(request: Request):
    """
    Receives latest annotated JPEG frame from inference.
    """
    global last_video_frame
    last_video_frame = await request.body()
    return {"status": "ok"}


@app.get("/video")
def get_video():
    """
    Dashboard <img src="/video"> endpoint.
    """
    if last_video_frame is None:
        return Response(status_code=204)
    return Response(content=last_video_frame, media_type="image/jpeg")

# -----------------------------------------------------------------------------
# Health / liveness
# -----------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "active_scene": ACTIVE_SCENE,
        "events": len(events),
        "has_video": last_video_frame is not None,
    }

# -----------------------------------------------------------------------------
# Dashboard mount
# -----------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[2]  # ~/urbanii
DASHBOARD_DIR = ROOT_DIR / "dashboard"

if DASHBOARD_DIR.exists():
    log.info(f"📊 Mounting dashboard from {DASHBOARD_DIR}")
    app.mount(
        "/",
        StaticFiles(directory=str(DASHBOARD_DIR), html=True),
        name="dashboard",
    )
else:
    log.warning(f"⚠️ Dashboard directory not found at: {DASHBOARD_DIR}")
