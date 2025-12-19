# ~/urbanii/inference/intelligence/highway.py
from collections import deque

VEHICLE_CLASSES = {"car", "truck", "bus", "motorbike"}

class HighwayAnalyzer:
    """
    Traffic density + simple safety signals (no tracking).
    Demo-safe: runs on per-frame aggregates.
    """
    def __init__(self, history_size=30):
        self.history = deque(maxlen=history_size)

    def analyze(self, detections, frame_height):
        vehicles = [d for d in detections if d.get("class_name") in VEHICLE_CLASSES]
        persons  = [d for d in detections if d.get("class_name") == "person"]

        vehicle_count = len(vehicles)
        self.history.append(vehicle_count)

        # Density (tune later using real video)
        if vehicle_count < 6:
            density = "low"
        elif vehicle_count < 15:
            density = "medium"
        else:
            density = "high"

        # Trend
        trend = "stable"
        if len(self.history) >= 6:
            history_list = list(self.history)
            recent = sum(history_list[-3:]) / 3
            earlier = sum(history_list[-6:-3]) / 3
            if earlier > 0 and recent > earlier * 1.2:
                trend = "increasing"
            elif earlier > 0 and recent < earlier * 0.8:
                trend = "decreasing"

        # Safety: pedestrian in roadway zone (lower 40% of frame)
        pedestrian_in_roadway = False
        for p in persons:
            x1, y1, x2, y2 = p.get("bbox", [0,0,0,0])
            cy = (y1 + y2) / 2
            if cy > frame_height * 0.60:
                pedestrian_in_roadway = True
                break

        risk = "elevated" if pedestrian_in_roadway and vehicle_count > 0 else "normal"

        return {
            "vehicle_count": vehicle_count,
            "density": density,
            "trend": trend,
            "pedestrian_in_roadway": pedestrian_in_roadway,
            "risk": risk,
        }
