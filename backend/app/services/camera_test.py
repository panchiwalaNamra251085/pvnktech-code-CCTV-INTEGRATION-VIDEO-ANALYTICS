import cv2


def test_rtsp_connection(
    rtsp_url: str,
    timeout_seconds: int = 10,
) -> dict:
    """
    Test whether an RTSP camera stream can be opened
    and whether a video frame can be received.
    """

    cap = cv2.VideoCapture(rtsp_url)

    if not cap.isOpened():
        cap.release()

        return {
            "connected": False,
            "message": "Unable to connect to RTSP stream.",
        }

    success, frame = cap.read()

    cap.release()

    if not success or frame is None:
        return {
            "connected": False,
            "message": "RTSP stream opened, but no video frame was received.",
        }

    height, width = frame.shape[:2]

    return {
        "connected": True,
        "message": "RTSP stream is connected and video frame received.",
        "width": width,
        "height": height,
    }   