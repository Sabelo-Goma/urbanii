from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import time

app = FastAPI()

# -------------------------------------------------------------------
# In-memory storage
# -------------------------------------------------------------------

last_video_frame: bytes | None = None
events: list[dict] = []

MAX_EVENTS = 1000


# -------------------------------------------------------------------
# RECEIVE DETECTION METADATA
# -------------------------------------------------------------------

@app.post("/frame")
async def receive_frame(payload: dict):
    """
    Receives JSON metadata from inference loop:
    {
      frame: int,
      timestamp: float,
      num_detections: int,
      detections: [...]
    }
    """
    payload["received_at"] = time.time()

    events.append(payload)
    if len(events) > MAX_EVENTS:
        events.pop(0)

    return {"status": "ok"}


# -------------------------------------------------------------------
# RETURN LAST N EVENTS
# -------------------------------------------------------------------

@app.get("/events")
async def get_events(limit: int = 20):
    return JSONResponse(events[-limit:][::-1])


# -------------------------------------------------------------------
# RECEIVE RAW JPEG FRAME
# -------------------------------------------------------------------

@app.post("/video")
async def upload_video_frame(request: Request):
    """
    Receives JPEG bytes from inference script.
    """
    global last_video_frame
    last_video_frame = await request.body()
    return {"status": "ok"}


# -------------------------------------------------------------------
# SERVE LAST FRAME FOR DASHBOARD <img src="/video">
# -------------------------------------------------------------------

@app.get("/video")
async def get_video():
    if last_video_frame is None:
        return Response(status_code=204)
    return Response(content=last_video_frame, media_type="image/jpeg")


# -------------------------------------------------------------------
# HEALTH CHECK
# -------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# -------------------------------------------------------------------
# STATIC DASHBOARD MOUNT
# -------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[2]   # ~/urbanii
DASHBOARD_DIR = ROOT_DIR / "dashboard"

if DASHBOARD_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(DASHBOARD_DIR), html=True),
        name="dashboard",
    )
else:
    print(f"⚠️ Dashboard directory not found at: {DASHBOARD_DIR}")
