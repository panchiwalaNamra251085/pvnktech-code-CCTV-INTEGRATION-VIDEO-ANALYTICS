from __future__ import annotations

from collections.abc import Iterator
from threading import Lock
from typing import Any

import cv2
from ultralytics import YOLO


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
VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck"}
TRAFFIC_CLASSES = {"traffic light", "stop sign"}

_model: YOLO | None = None
_model_lock = Lock()


def get_model() -> YOLO:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = YOLO("yolo11n.pt")
    return _model


def open_source(source: str | int) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"Unable to open video source: {source}")
    return capture


def analyze_frame(
    frame: Any,
    previous_centers: dict[int, tuple[float, float]] | None = None,
    confidence: float = 0.35,
) -> tuple[dict[str, Any], Any, dict[int, tuple[float, float]]]:
    result = get_model().track(
        frame,
        persist=True,
        classes=None,
        conf=confidence,
        verbose=False,
    )[0]
    annotated_frame = result.plot()
    counts = {"people": 0, "vehicles": 0, "traffic": 0, "total": 0}
    detections: list[dict[str, Any]] = []
    current_centers: dict[int, tuple[float, float]] = {}
    moving_count = 0

    boxes = result.boxes
    if boxes is None:
        return {"counts": counts, "detections": detections, "moving": False, "moving_objects": 0}, annotated_frame, current_centers

    names = result.names
    ids = boxes.id.int().cpu().tolist() if boxes.id is not None else list(range(len(boxes)))
    for index, box in enumerate(boxes):
        class_id = int(box.cls.item())
        label = str(names[class_id])
        if label not in ANALYTICS_CLASSES:
            continue
        coordinates = box.xyxy[0].cpu().tolist()
        x1, y1, x2, y2 = coordinates
        center = ((x1 + x2) / 2, (y1 + y2) / 2)
        track_id = int(ids[index])
        current_centers[track_id] = center
        was_moving = False
        if previous_centers and track_id in previous_centers:
            old_center = previous_centers[track_id]
            was_moving = ((center[0] - old_center[0]) ** 2 + (center[1] - old_center[1]) ** 2) ** 0.5 > 8
        moving_count += int(was_moving)
        counts["total"] += 1
        if label == "person":
            counts["people"] += 1
        elif label in VEHICLE_CLASSES:
            counts["vehicles"] += 1
        elif label in TRAFFIC_CLASSES:
            counts["traffic"] += 1
        detections.append({
            "id": track_id,
            "label": label,
            "confidence": round(float(box.conf.item()), 3),
            "box": [round(value, 1) for value in coordinates],
            "moving": was_moving,
        })

    return {
        "counts": counts,
        "detections": detections,
        "moving": moving_count > 0,
        "moving_objects": moving_count,
    }, annotated_frame, current_centers


def capture_snapshot(source: str | int) -> tuple[dict[str, Any], Any]:
    capture = open_source(source)
    try:
        success, frame = capture.read()
        if not success or frame is None:
            raise RuntimeError("Video source opened, but no frame was received")
        analytics, annotated_frame, _ = analyze_frame(frame)
        analytics["source"] = str(source)
        analytics["frame_width"] = int(frame.shape[1])
        analytics["frame_height"] = int(frame.shape[0])
        return analytics, annotated_frame
    finally:
        capture.release()


def stream_source(source: str | int) -> Iterator[bytes]:
    capture = open_source(source)
    previous_centers: dict[int, tuple[float, float]] = {}
    try:
        while True:
            success, frame = capture.read()
            if not success or frame is None:
                break
            _, annotated_frame, previous_centers = analyze_frame(frame, previous_centers)
            success, encoded = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not success:
                continue
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + encoded.tobytes() + b"\r\n"
    finally:
        capture.release()
