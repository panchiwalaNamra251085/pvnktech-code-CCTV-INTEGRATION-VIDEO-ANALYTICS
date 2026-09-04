from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass

import cv2


ANALYTICS_CLASSES = {
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "bus",
    "truck",
    "traffic light",
    "stop sign",
}


@dataclass
class DetectionSummary:
    label: str
    confidence: float
    box: tuple[int, int, int, int]
    moving: bool


class AnalyticsEngine:
    """Run object detection and motion tracking on a webcam or RTSP source."""

    def __init__(self, model_name: str = "yolo11n.pt") -> None:
        self.model_name = model_name
        self._model = None
        self._model_lock = threading.Lock()

    def _get_model(self):
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    from ultralytics import YOLO

                    self._model = YOLO(self.model_name)
        return self._model

    def analyze_frame(
        self,
        frame,
        previous_centers: dict[str, tuple[float, float]],
        confidence: float = 0.35,
    ) -> tuple[object, list[DetectionSummary]]:
        model = self._get_model()
        result = model.predict(
            source=frame,
            conf=confidence,
            verbose=False,
            classes=self._class_ids(model),
        )[0]

        detections: list[DetectionSummary] = []
        current_centers: dict[str, tuple[float, float]] = {}
        names = result.names

        if result.boxes is not None:
            for index, box in enumerate(result.boxes):
                class_id = int(box.cls[0])
                label = str(names[class_id])
                x1, y1, x2, y2 = (int(value) for value in box.xyxy[0].tolist())
                center = ((x1 + x2) / 2, (y1 + y2) / 2)
                key = f"{label}:{index}"
                previous = previous_centers.get(key)
                moving = previous is not None and self._distance(center, previous) > 12
                current_centers[key] = center
                detections.append(
                    DetectionSummary(
                        label=label,
                        confidence=float(box.conf[0]),
                        box=(x1, y1, x2, y2),
                        moving=moving,
                    )
                )

        previous_centers.clear()
        previous_centers.update(current_centers)
        annotated = self._annotate(frame, detections)
        return annotated, detections

    @staticmethod
    def _class_ids(model) -> list[int]:
        return [index for index, name in model.names.items() if name in ANALYTICS_CLASSES]

    @staticmethod
    def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
        return ((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2) ** 0.5

    @staticmethod
    def _annotate(frame, detections: list[DetectionSummary]):
        for detection in detections:
            x1, y1, x2, y2 = detection.box
            color = (80, 220, 170) if detection.moving else (180, 210, 100)
            label = f"{detection.label} {detection.confidence:.0%}"
            if detection.moving:
                label += " | moving"
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        return frame

    def stream(self, source: str | int, confidence: float = 0.35) -> Iterator[bytes]:
        capture = cv2.VideoCapture(source)
        previous_centers: dict[str, tuple[float, float]] = {}

        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Unable to open video source: {source}")

        try:
            while True:
                success, frame = capture.read()
                if not success:
                    break

                annotated, detections = self.analyze_frame(frame, previous_centers, confidence)
                cv2.putText(
                    annotated,
                    f"Objects: {len(detections)} | Moving: {sum(item.moving for item in detections)}",
                    (16, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (235, 245, 235),
                    2,
                )
                encoded, buffer = cv2.imencode(".jpg", annotated)
                if not encoded:
                    continue

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + buffer.tobytes()
                    + b"\r\n"
                )
                time.sleep(0.01)
        finally:
            capture.release()


analytics_engine = AnalyticsEngine()
