import cv2
import time


class CameraStream:
    """
    Handles a live RTSP camera stream.
    """

    def __init__(
        self,
        rtsp_url: str,
        reconnect_delay: int = 3,
    ):
        self.rtsp_url = rtsp_url
        self.reconnect_delay = reconnect_delay
        self.capture = None

    def connect(self) -> bool:
        """
        Connect to the RTSP stream.
        """

        self.release()

        print(
            f"Connecting to RTSP stream: {self.rtsp_url}"
        )

        self.capture = cv2.VideoCapture(
            self.rtsp_url
        )

        if not self.capture.isOpened():
            print(
                "Failed to connect to RTSP stream."
            )

            self.release()

            return False

        print(
            "RTSP stream connected successfully."
        )

        return True

    def read(self):
        """
        Read one frame from the stream.

        Returns:
            frame if successful
            None if unsuccessful
        """

        if self.capture is None:
            return None

        success, frame = self.capture.read()

        if not success:
            return None

        return frame

    def release(self):
        """
        Release the video stream.
        """

        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def run(self):
        """
        Continuously read frames.

        This will later become the main
        video-processing loop for YOLO.
        """

        while True:

            # ------------------------------------------------
            # Connect
            # ------------------------------------------------
            if self.capture is None:

                connected = self.connect()

                if not connected:
                    print(
                        f"Retrying in "
                        f"{self.reconnect_delay} seconds..."
                    )

                    time.sleep(
                        self.reconnect_delay
                    )

                    continue

            # ------------------------------------------------
            # Read frame
            # ------------------------------------------------
            frame = self.read()

            if frame is None:

                print(
                    "Frame read failed. "
                    "Reconnecting..."
                )

                self.release()

                time.sleep(
                    self.reconnect_delay
                )

                continue

            # ------------------------------------------------
            # Frame information
            # ------------------------------------------------
            height, width = frame.shape[:2]

            print(
                f"Frame received: "
                f"{width}x{height}"
            )

            # ------------------------------------------------
            # Temporary stop condition
            #
            # Later this section will contain:
            # YOLO detection
            # tracking
            # event generation
            # frame streaming
            # ------------------------------------------------

            break

        self.release()