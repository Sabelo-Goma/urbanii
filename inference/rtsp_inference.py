import cv2
import time
import requests
import subprocess
from ultralytics import YOLO

# =============================================================================
# CONFIG
# =============================================================================

BACKEND_URL = "http://localhost:8000"

FRAME_ENDPOINT = f"{BACKEND_URL}/frame"
VIDEO_ENDPOINT = f"{BACKEND_URL}/video"
SCENES_ENDPOINT = f"{BACKEND_URL}/scenes"

POLL_INTERVAL = 2.0          # seconds
JPEG_QUALITY = 80
MODEL_PATH = "yolov8n.pt"

# Logical scene → source mapping
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
        "url": "BigBuckBunny.mp4"
    }
}

# =============================================================================
# HELPERS
# =============================================================================

def resolve_stream(scene_key: str) -> str | None:
    """
    Resolve a playable stream URL for the active scene.
    Fail loudly if resolution fails.
    """
    source = SCENE_SOURCES.get(scene_key)

    if not source:
        print(f"❌ Scene '{scene_key}' not configured")
        return None

    if source["type"] == "youtube":
        try:
            cmd = ["yt-dlp", "-f", "95", "-g", source["url"]]
            return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        except Exception as e:
            print(f"❌ yt-dlp failed for {scene_key}: {e}")
            return None

    return source["url"]


def get_active_scene() -> str | None:
    """
    Ask backend which scene is active.
    """
    try:
        r = requests.get(SCENES_ENDPOINT, timeout=2)
        return r.json().get("active")
    except Exception:
        return None


# =============================================================================
# MAIN LOOP
# =============================================================================

def main():
    print("Loading YOLO model...")
    model = YOLO(MODEL_PATH)

    active_scene = None
    cap = None
    last_scene_poll = 0

    while True:
        now = time.time()

        # ---------------------------------------------------------------------
        # Poll backend for scene changes
        # ---------------------------------------------------------------------
        if now - last_scene_poll > POLL_INTERVAL:
            scene = get_active_scene()
            last_scene_poll = now

            if scene and scene != active_scene:
                print(f"🔁 Switching scene → {scene}")

                if cap:
                    cap.release()
                    cap = None

                stream_url = resolve_stream(scene)
                if not stream_url:
                    print("❌ No valid stream URL — waiting for operator action")
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

        if cap is None:
            time.sleep(0.2)
            continue

        # ---------------------------------------------------------------------
        # Read frame
        # ---------------------------------------------------------------------
        ret, frame = cap.read()
        if not ret or frame is None:
            print("⚠️ Frame read failed — reconnecting")
            cap.release()
            cap = None
            time.sleep(0.5)
            continue

        # ---------------------------------------------------------------------
        # Inference
        # ---------------------------------------------------------------------
        results = model(frame, verbose=False)[0]

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

        payload = {
            "scene": active_scene,
            "timestamp": time.time(),
            "num_detections": len(detections),
            "classes": class_counts,
            "detections": detections
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
