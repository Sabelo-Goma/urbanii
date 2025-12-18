import cv2
import time
import requests
import subprocess
from ultralytics import YOLO
from intelligence.crowd import CrowdAnalyzer
from intelligence.loiter import LoiterAnalyzer
from intelligence.highway import HighwayAnalyzer


# =============================================================================
# CONFIG
# =============================================================================

BACKEND_URL = "http://localhost:8000"

FRAME_ENDPOINT = f"{BACKEND_URL}/frame"
VIDEO_ENDPOINT = f"{BACKEND_URL}/video"
SCENE_ENDPOINT = f"{BACKEND_URL}/scene"   # authoritative for inference

POLL_INTERVAL = 2.0            # seconds
JPEG_QUALITY = 80
MODEL_PATH = "yolov8s.pt"

HLS_MAX_AGE = 25 * 60          # 25 minutes (YouTube safety window)

crowd_analyzer = CrowdAnalyzer()
loiter_analyzer = LoiterAnalyzer(
    loiter_seconds=25.0,        # tweak as needed
    match_radius_px=60.0,
    max_track_age_seconds=3.0
)

highway_analyzer = HighwayAnalyzer()

# -----------------------------------------------------------------------------
# Scene → Source mapping
# -----------------------------------------------------------------------------

SCENE_SOURCES = {
    "shibuya": {
        "type": "youtube",
        "url": "https://www.youtube.com/watch?v=dfVK7ld38Ys"
    },
    "industrial": {
        "type": "file",
        "url": "BigBuckBunny.mp4"
    },
    "highway": {
        "type": "file",
        "url": "assets/highway_demo.mp4"
    }
}

# =============================================================================
# HELPERS
# =============================================================================

def resolve_stream(scene_key: str) -> str | None:
    """
    Resolve a playable stream URL for the given scene.
    YouTube streams are always resolved fresh.
    """
    source = SCENE_SOURCES.get(scene_key)

    if not source:
        print(f"❌ Scene '{scene_key}' not configured")
        return None

    if source["type"] == "youtube":
        try:
            print("🔄 Resolving fresh YouTube HLS URL…")
            cmd = ["yt-dlp", "-f", "95", "-g", source["url"]]
            output = subprocess.check_output(
                cmd,
                stderr=subprocess.DEVNULL,
                timeout=30
            )
            return output.decode().strip()
        except subprocess.TimeoutExpired:
            print(f"⏱️ yt-dlp timed out while resolving stream for {scene_key}")
            return None
        except Exception as e:
            print(f"❌ yt-dlp failed for {scene_key}: {e}")
            return None

    return source["url"]


def get_active_scene() -> str | None:
    """
    Ask backend which scene is active.
    """
    try:
        r = requests.get(SCENE_ENDPOINT, timeout=2)
        return r.json().get("scene")
    except Exception:
        return None


def _centroid(b):
    x1, y1, x2, y2 = b
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def _near_miss(person_dets, car_dets, px_threshold=70.0):
    """
    Lightweight 'unsafe interaction' for Shibuya:
    - If a car centroid is within N pixels of a person centroid -> flag.
    This is NOT a true collision predictor; it’s a demo-safe heuristic.
    """
    alerts = []
    for p in person_dets:
        pc = _centroid(p["bbox"])
        for c in car_dets:
            cc = _centroid(c["bbox"])
            dx = pc[0] - cc[0]
            dy = pc[1] - cc[1]
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < px_threshold:
                alerts.append({
                    "type": "pedestrian_vehicle_conflict",
                    "distance_px": round(dist, 1),
                    "person_conf": round(float(p["confidence"]), 2),
                    "vehicle_conf": round(float(c["confidence"]), 2),
                })
    return alerts


# =============================================================================
# MAIN LOOP
# =============================================================================

def main():
    print("🚀 Loading YOLO model…")
    model = YOLO(MODEL_PATH)

    active_scene = None
    cap = None

    current_stream_url = None
    stream_resolved_at = 0

    last_scene_poll = 0

    while True:
        now = time.time()

        # ---------------------------------------------------------------------
        # Poll backend for scene changes
        # ---------------------------------------------------------------------
        if now - last_scene_poll > POLL_INTERVAL:
            scene = get_active_scene()
            last_scene_poll = now

            scene_changed = scene and scene != active_scene
            hls_expired = (
                current_stream_url
                and (time.time() - stream_resolved_at > HLS_MAX_AGE)
            )

            if scene_changed or hls_expired:
                if scene_changed:
                    print(f"🔁 Switching scene → {scene}")
                elif hls_expired:
                    print("⏳ HLS URL expired — refreshing")

                if cap:
                    cap.release()
                    cap = None

                stream_url = resolve_stream(scene)
                if not stream_url:
                    print("⚠️ No valid stream URL — retrying")
                    time.sleep(1)
                    continue

                cap = cv2.VideoCapture(stream_url)
                if not cap.isOpened():
                    print("❌ OpenCV failed to open stream")
                    cap.release()
                    cap = None
                    time.sleep(1)
                    continue

                active_scene = scene
                current_stream_url = stream_url
                stream_resolved_at = time.time()

        if cap is None:
            time.sleep(0.2)
            continue

        # ---------------------------------------------------------------------
        # Read frame
        # ---------------------------------------------------------------------
        ret, frame = cap.read()
        if not ret or frame is None:
            print("⚠️ Frame read failed — forcing reconnect")
            cap.release()
            cap = None
            current_stream_url = None
            time.sleep(0.5)
            continue

        # ---------------------------------------------------------------------
        # Inference
        # ---------------------------------------------------------------------
        results = model(frame, conf=0.15, verbose=False)[0]

        detections = []
        class_counts = {}

        for box in results.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(float, box.xyxy[0])

            cls_name = model.names[cls_id]
            class_counts[cls_name] = class_counts.get(cls_name, 0) + 1

            detections.append({
                "class_id": cls_id,
                "class_name": cls_name,
                "confidence": conf,
                "bbox": [x1, y1, x2, y2]
            })

        # ---------------------------------------------------------------------
        # Scene-specific intelligence
        # ---------------------------------------------------------------------
        intelligence = {}

        # === Shibuya: crowd + loitering + lightweight safety ===
        if active_scene == "shibuya":
            _, frame_width = frame.shape[:2]

            crowd_intel = crowd_analyzer.analyze(detections, frame_width)
            loiter_intel = loiter_analyzer.analyze(detections, now=time.time())

            persons = [
                d for d in detections
                if d["class_name"] == "person" and float(d["confidence"]) > 0.15
            ]
            vehicles = [
                d for d in detections
                if d["class_name"] in ("car", "truck", "bus", "motorcycle")
            ]

            conflict_alerts = _near_miss(persons, vehicles, px_threshold=70.0)

            intelligence["crowd"] = crowd_intel
            intelligence["loitering"] = loiter_intel
            intelligence["safety"] = {
                "alerts": conflict_alerts,
                "alert_count": len(conflict_alerts)
            }

        # === Highway: traffic analyzer only ===
        elif active_scene == "highway":
            frame_height = frame.shape[0]
            traffic_intel = highway_analyzer.analyze(detections, frame_height)
            intelligence["traffic"] = traffic_intel

        # === Industrial: placeholder (no extra intelligence yet) ===
        elif active_scene == "industrial":
            # keep empty for now
            pass

        # if nothing was added, keep schema clean
        if not intelligence:
            intelligence = None

        payload = {
            "scene": active_scene,
            "timestamp": time.time(),
            "num_detections": len(detections),
            "classes": class_counts,
            "detections": detections,
            "intelligence": intelligence
        }

        try:
            requests.post(FRAME_ENDPOINT, json=payload, timeout=1)
        except Exception:
            pass

        # ---------------------------------------------------------------------
        # Draw + send frame
        # ---------------------------------------------------------------------
        for d in detections:
            x1, y1, x2, y2 = map(int, d["bbox"])
            label = f"{d['class_name']} {d['confidence']:.2f}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)
            cv2.putText(
                frame,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 200, 0),
                1
            )

        try:
            _, jpeg = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
            )
            requests.post(VIDEO_ENDPOINT, data=jpeg.tobytes(), timeout=1)
        except Exception:
            pass


if __name__ == "__main__":
    main()
