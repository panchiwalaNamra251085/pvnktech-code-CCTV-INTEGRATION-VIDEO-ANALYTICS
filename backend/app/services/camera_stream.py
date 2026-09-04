import cv2
import time
from ultralytics import YOLO


# ============================================================
# CONFIGURATION
# ============================================================

VIDEO_SOURCE = "http://10.83.197.157:8080/video"

MODEL_PATH = "yolo26n.pt"

CONFIDENCE = 0.30

WINDOW_NAME = "CCTV AI - Mobile Camera"


# ============================================================
# CAMERA STREAM
# ============================================================

class CameraStream:

    def __init__(
        self,
        video_source: str,
        reconnect_delay: int = 3,
    ):
        self.video_source = video_source
        self.reconnect_delay = reconnect_delay
        self.capture = None

    def connect(self) -> bool:

        self.release()

        print()
        print("=" * 60)
        print(f"Connecting to camera:")
        print(self.video_source)
        print("=" * 60)

        self.capture = cv2.VideoCapture(
            self.video_source
        )

        if not self.capture.isOpened():

            print("[ERROR] Failed to connect to camera")

            self.release()

            return False

        print("[INFO] Camera connected successfully")

        return True

    def read(self):

        if self.capture is None:
            return None

        success, frame = self.capture.read()

        if not success:
            return None

        return frame

    def release(self):

        if self.capture is not None:

            self.capture.release()

            self.capture = None


# ============================================================
# LOAD YOLO
# ============================================================

print()
print("[INFO] Loading YOLO model...")

model = YOLO(MODEL_PATH)

print("[INFO] YOLO model loaded successfully")


# ============================================================
# CREATE CAMERA
# ============================================================

camera = CameraStream(
    VIDEO_SOURCE
)


# ============================================================
# FPS
# ============================================================

previous_time = time.time()


# ============================================================
# MAIN LOOP
# ============================================================

try:

    while True:

        # ----------------------------------------------------
        # CONNECT CAMERA
        # ----------------------------------------------------

        if camera.capture is None:

            connected = camera.connect()

            if not connected:

                print(
                    f"[INFO] Retrying in "
                    f"{camera.reconnect_delay} seconds..."
                )

                time.sleep(
                    camera.reconnect_delay
                )

                continue


        # ----------------------------------------------------
        # READ FRAME
        # ----------------------------------------------------

        frame = camera.read()

        if frame is None:

            print(
                "[WARNING] Frame read failed"
            )

            print(
                "[INFO] Reconnecting..."
            )

            camera.release()

            time.sleep(
                camera.reconnect_delay
            )

            continue


        # ----------------------------------------------------
        # YOLO DETECTION
        # ----------------------------------------------------

        results = model(
            frame,
            conf=CONFIDENCE,
            verbose=False
        )


        # ----------------------------------------------------
        # DRAW DETECTIONS
        # ----------------------------------------------------

        annotated_frame = results[0].plot()


        # ----------------------------------------------------
        # FPS CALCULATION
        # ----------------------------------------------------

        current_time = time.time()

        fps = 1.0 / max(
            current_time - previous_time,
            0.001
        )

        previous_time = current_time


        # ----------------------------------------------------
        # DISPLAY FPS
        # ----------------------------------------------------

        cv2.putText(
            annotated_frame,
            f"FPS: {fps:.1f}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )


        # ----------------------------------------------------
        # DISPLAY FRAME
        # ----------------------------------------------------

        cv2.imshow(
            WINDOW_NAME,
            annotated_frame
        )


        # ----------------------------------------------------
        # KEYBOARD
        # ----------------------------------------------------

        key = cv2.waitKey(1) & 0xFF


        # ESC = EXIT

        if key == 27:

            print()
            print("[INFO] ESC pressed")
            break


        # Q = EXIT

        if key == ord("q"):

            print()
            print("[INFO] Q pressed")
            break


finally:

    # ========================================================
    # CLEANUP
    # ========================================================

    camera.release()

    cv2.destroyAllWindows()

    print()
    print("[INFO] CCTV AI stopped")