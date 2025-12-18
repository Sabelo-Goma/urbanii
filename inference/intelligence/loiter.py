from __future__ import annotations
from dataclasses import dataclass
import time
import math


@dataclass
class Track:
    x: float
    y: float
    first_seen: float
    last_seen: float
    dwell_seconds: float = 0.0


class LoiterAnalyzer:
    """
    Very light-weight loitering:
    - track persons by nearest-centroid matching
    - if a person stays within a small radius over time -> loitering
    """

    def __init__(
        self,
        loiter_seconds: float = 25.0,
        match_radius_px: float = 60.0,
        max_track_age_seconds: float = 3.0,
    ):
        self.loiter_seconds = loiter_seconds
        self.match_radius_px = match_radius_px
        self.max_track_age_seconds = max_track_age_seconds

        self._tracks: dict[int, Track] = {}
        self._next_id = 1

    @staticmethod
    def _centroid(bbox: list[float]) -> tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return (x1 + x2) / 2.0, (y1 + y2) / 2.0

    @staticmethod
    def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def analyze(self, detections: list[dict], now: float | None = None) -> dict:
        now = now or time.time()

        # keep only "person"
        persons = [
            d for d in detections
            if d.get("class_name") == "person" and d.get("bbox") is not None
        ]

        centroids = [self._centroid(p["bbox"]) for p in persons]

        # age out tracks
        stale_ids = [
            tid for tid, tr in self._tracks.items()
            if (now - tr.last_seen) > self.max_track_age_seconds
        ]
        for tid in stale_ids:
            del self._tracks[tid]

        # greedy nearest matching
        used_tracks: set[int] = set()
        assignments: list[tuple[int, tuple[float, float]]] = []

        for c in centroids:
            best_tid = None
            best_dist = 1e9

            for tid, tr in self._tracks.items():
                if tid in used_tracks:
                    continue
                d = self._dist((tr.x, tr.y), c)
                if d < best_dist:
                    best_dist = d
                    best_tid = tid

            if best_tid is not None and best_dist <= self.match_radius_px:
                used_tracks.add(best_tid)
                assignments.append((best_tid, c))
            else:
                # new track
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = Track(
                    x=c[0], y=c[1],
                    first_seen=now,
                    last_seen=now,
                    dwell_seconds=0.0,
                )
                used_tracks.add(tid)
                assignments.append((tid, c))

        # update tracks + dwell
        for tid, c in assignments:
            tr = self._tracks[tid]
            dt = max(0.0, now - tr.last_seen)

            moved = self._dist((tr.x, tr.y), c)
            if moved <= self.match_radius_px * 0.5:
                tr.dwell_seconds += dt
            else:
                tr.dwell_seconds = max(0.0, tr.dwell_seconds - dt)  # forgiving decay

            tr.x, tr.y = c
            tr.last_seen = now

        # compute loiterers
        loiterers = [
            {"track_id": tid, "dwell_seconds": round(tr.dwell_seconds, 1)}
            for tid, tr in self._tracks.items()
            if tr.dwell_seconds >= self.loiter_seconds
        ]

        return {
            "enabled": True,
            "threshold_seconds": self.loiter_seconds,
            "active_tracks": len(self._tracks),
            "loiterers": loiterers,
            "loiter_count": len(loiterers),
        }
