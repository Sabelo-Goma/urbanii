from collections import deque

VEHICLE_CLASSES = {"car", "truck", "bus", "motorbike", "motorcycle"}
MACHINE_CLASSES = {"forklift"}  # optional if  model emits it 

class IndustrialAnalyzer:
    """
    Demo-safe industrial safety layer (no tracking).
    - Worker presence
    - Vehicle/machinery context
    - Simple zone pressure (bottom of frame = operational area)
    - PPE framed as 'verification recommended' in high-risk context
    """
    def __init__(self, history_size=30, op_zone_start=0.60):
        self.worker_hist = deque(maxlen=history_size)
        self.op_zone_start = op_zone_start

    def analyze(self, detections, frame_height):
        persons = [d for d in detections if d.get("class_name") == "person"]
        vehicles = [d for d in detections if d.get("class_name") in VEHICLE_CLASSES]
        machines = [d for d in detections if d.get("class_name") in MACHINE_CLASSES]

        worker_count = len(persons)
        vehicle_count = len(vehicles)
        machine_count = len(machines)

        self.worker_hist.append(worker_count)

        # Worker trend
        trend = "stable"
        if len(self.worker_hist) >= 6:
            recent = sum(list(self.worker_hist)[-3:]) / 3
            earlier = sum(list(self.worker_hist)[-6:-3]) / 3
            if earlier > 0 and recent > earlier * 1.2:
                trend = "increasing"
            elif earlier > 0 and recent < earlier * 0.8:
                trend = "decreasing"

        # "Operational zone": bottom portion of frame
        workers_in_op_zone = 0
        for p in persons:
            x1, y1, x2, y2 = p.get("bbox", [0, 0, 0, 0])
            cy = (y1 + y2) / 2
            if cy > frame_height * self.op_zone_start:
                workers_in_op_zone += 1

        high_risk_context = (vehicle_count + machine_count) > 0
        ppe_verification_required = workers_in_op_zone > 0 and high_risk_context

        risk = "elevated" if ppe_verification_required else "normal"

        alerts = []
        if ppe_verification_required:
            alerts.append({
                "type": "ppe_verification_required",
                "message": "Worker(s) detected in operational area. PPE verification recommended.",
                "workers_in_zone": workers_in_op_zone,
                "vehicles": vehicle_count,
                "machines": machine_count,
            })

        return {
            "worker_count": worker_count,
            "worker_trend": trend,
            "workers_in_op_zone": workers_in_op_zone,
            "vehicle_count": vehicle_count,
            "machine_count": machine_count,
            "ppe_verification_required": ppe_verification_required,
            "risk": risk,
            "alerts": alerts,
            "alert_count": len(alerts),
        }
