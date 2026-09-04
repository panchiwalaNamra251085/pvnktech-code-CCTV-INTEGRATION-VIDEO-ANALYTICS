from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.services.video_analytics import capture_snapshot, stream_source


router = APIRouter(
    prefix="/analytics",
    tags=["Video Analytics"],
)


def parse_source(source: str) -> str | int:
    return int(source) if source.isdigit() else source


@router.get("/snapshot")
def analytics_snapshot(
    source: str = Query("0", description="Webcam index or RTSP/HTTP video URL"),
):
    """Analyze one frame and return people, vehicles, traffic, and movement data."""
    try:
        analytics, _ = capture_snapshot(parse_source(source))
        return analytics
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/stream")
def analytics_stream(
    source: str = Query("0", description="Webcam index or RTSP/HTTP video URL"),
):
    """Return an MJPEG stream with YOLO boxes drawn on detected objects."""
    try:
        frames = stream_source(parse_source(source))
        first_frame = next(frames)
    except (RuntimeError, StopIteration) as error:
        raise HTTPException(status_code=503, detail=str(error) or "No video frame available") from error

    def frames_with_first() :
        yield first_frame
        yield from frames

    return StreamingResponse(
        frames_with_first(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
