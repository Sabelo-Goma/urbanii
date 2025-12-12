import subprocess
import time
import cv2
import numpy as np
import requests
from ultralytics import YOLO

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------

# YouTube live URL (Shibuya / Shinjuku / whatever you’re testing)
YOUTUBE_URL = "https://www.youtube.com/watch?v=dfVK7ld38Ys"

# Backend endpoints (FastAPI)
BACKEND_FRAME_URL = "http://localhost:8000/frame"   # POST JSON
BACKEND_JPEG_URL = "http://localhost:8000/video"    # POST raw JPEG bytes

# Frame size to read from FFmpeg (after scaling)
FRAME_WIDTH = 960
FRAME_HEIGHT = 540
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * 3  # 3 channels (BGR)

# YOLO model path
MODEL_PATH = "yolov8n.pt"

# ---------------------------------------------------------------------
# STREAM HELPERS
# ---------------------------------------------------------------------


def open_youtube_stream():
    """
    Start yt-dlp to fetch the live stream and pipe it into ffmpeg,
    which outputs raw BGR frames to stdout.
    If the stream dies, we’ll call this again to restart.
    """
    print("\n[stream] Spawning yt-dlp + ffmpeg pipeline...")

    yt_cmd = [
        "yt-dlp",
        "--no-cache-dir",
        "-f", "95/best[ext=mp4]/best",   # prefer 720p HLS, fall back to best
        "-o", "-",                       # write video data to stdout
        YOUTUBE_URL,
    ]

    ffmpeg_cmd = [
        "ffmpeg",
        "-loglevel", "error",
        "-i", "pipe:0",                  # read from yt-dlp stdout
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-vf", f"scale={FRAME_WIDTH}:{FRAME_HEIGHT}",
        "pipe:1",
    ]

    yt_proc = subprocess.Popen(
        yt_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    ffmpeg_proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=yt_proc.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    # Let ffmpeg own the stdout pipe
    yt_proc.stdout.close()

    return yt_proc, ffmpeg_proc


def frame_generator():
    """
    Generator that yields raw BGR frame bytes.
    If the pipeline stops (EOF / error), it will tear down and restart.
    """
    while True:
        yt_proc, ffmpeg_proc = open_youtube_stream()

        try:
            while True:
                raw = ffmpeg_proc.stdout.read(FRAME_SIZE)
                if not raw:
                    print("[stream] No more data from ffmpeg. Restarting in 2s...")
                    break
                yield raw
        finally:
            try:
                ffmpeg_proc.kill()
            except Exception:
                pass
            try:
                yt_proc.kill()
            except Exception:
                pass

            time.sleep(2)


# ---------------------------------------------------------------------
# DRAWING + BACKEND SYNC
# ---------------------------------------------------------------------


def draw_overlays(frame, detections, fps):
    """
    Draw bounding boxes, labels, FPS, and Urbanii branding on frame (in-place).
    """
    for det in detections:
        x1, y1, x2, y2 = map(int, det["bbox"])
        label = f"{det['class_name']} {det['confidence']:.2f}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            frame,
            label,
            (x1, max(20, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

    cv2.putText(
        frame,
        "URBANII — Live Inference",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
    )

    cv2.putText(
        frame,
        f"FPS: {fps:.2f}",
        (10, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 0),
        2,
    )

    return frame


def safe_post(url, **kwargs):
    """
    Fire-and-forget POST; log errors but don’t crash the loop.
    """
    try:
        requests.post(url, timeout=0.5, **kwargs)
    except Exception as e:
        print(f"[backend] POST to {url} failed: {e}")


# ---------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------


def main():
    print("[init] Loading YOLOv8n model...")
    model = YOLO(MODEL_PATH)

    gen = frame_generator()
    frame_idx = 0
    last_time = time.time()

    print("[run] Starting inference loop...")
    for raw in gen:
        try:
            frame = np.frombuffer(raw, np.uint8).reshape(
                (FRAME_HEIGHT, FRAME_WIDTH, 3)
            )
        except ValueError:
            # Bad frame size – skip and let generator restart if needed
            print("[stream] Bad frame size, skipping...")
            continue

        # YOLO inference
        results = model(frame, verbose=False)

        detections = []
        for r in results:
            for box in r.boxes:
                class_id = int(box.cls[0])
                detections.append(
                    {
                        "class_id": class_id,
                        "class_name": model.names.get(class_id, str(class_id)),
                        "confidence": float(box.conf[0]),
                        "bbox": list(map(float, box.xyxy[0])),
                    }
                )

        # FPS
        now = time.time()
        fps = 1.0 / max(now - last_time, 1e-6)
        last_time = now

        annotated = draw_overlays(frame.copy(), detections, fps)

        # Send JSON event to backend
        safe_post(
            BACKEND_FRAME_URL,
            json={
                "frame": frame_idx,
                "timestamp": now,
                "num_detections": len(detections),
                "detections": detections,
            },
        )

        # Encode JPEG and send to backend
        ok, jpeg = cv2.imencode(".jpg", annotated)
        if ok:
            safe_post(
                BACKEND_JPEG_URL,
                data=jpeg.tobytes(),
                headers={"Content-Type": "image/jpeg"},
            )

        frame_idx += 1


if __name__ == "__main__":
    main()
