from collections import deque

class CrowdAnalyzer:
    """
    Computes crowd density & trend for pedestrian-heavy scenes (e.g. Shibuya).
    """

    def __init__(self, history_size=30):
        self.history = deque(maxlen=history_size)

    def analyze(self, detections, frame_width):
        """
        detections: list of YOLO detection dicts
        frame_width: width of the video frame
        """

        persons = [d for d in detections if d["class_name"] == "person"]
        count = len(persons)

        # ----------------------------
        # Zone analysis (simple thirds)
        # ----------------------------
        zones = {"left": 0, "center": 0, "right": 0}

        for p in persons:
            x1, _, x2, _ = p["bbox"]
            cx = (x1 + x2) / 2

            if cx < frame_width * 0.33:
                zones["left"] += 1
            elif cx < frame_width * 0.66:
                zones["center"] += 1
            else:
                zones["right"] += 1

        # ----------------------------
        # Density classification
        # (normalized for wide urban feeds)
        # ----------------------------
        density_score = count / (frame_width / 1000)

        if density_score < 8:
            density = "low"
        elif density_score < 16:
            density = "medium"
        else:
            density = "high"

        # ----------------------------
        # Trend detection (demo-safe)
        # ----------------------------
        trend = "stable"

        # Only track history when there is a meaningful crowd
        if count >= 3:
            self.history.append(count)

            if len(self.history) >= 6:
                avg_recent = sum(list(self.history)[-3:]) / 3
                avg_earlier = sum(list(self.history)[-6:-3]) / 3

                if avg_recent > avg_earlier * 1.2:
                    trend = "increasing"
                elif avg_recent < avg_earlier * 0.8:
                    trend = "decreasing"

        return {
            "count": count,
            "density": density,
            "trend": trend,
            "zones": zones
        }
