import cv2
import pyttsx3
from ultralytics import YOLO


# ============================================================
# CONFIGURATION
# ============================================================

# Existing YOLO model
MODEL_PATH = r"C:\CCTV-AI\yolo26n.pt"

# Camera 2 - IP Webcam
CAMERA_2_URL = "http://192.168.1.105:8080/video"

# YOLO confidence
CONFIDENCE_THRESHOLD = 0.50


# ============================================================
# PERSON DETECTOR
# ============================================================

class PersonDetector:

    def __init__(self):

        print("=" * 60)
        print("Loading YOLO model...")
        print("=" * 60)

        # Load existing model
        self.model = YOLO(MODEL_PATH)

        print("YOLO model loaded successfully.")

        # ----------------------------------------------------
        # Text-to-Speech
        # ----------------------------------------------------

        print("Starting text-to-speech engine...")

        self.engine = pyttsx3.init()

        self.engine.setProperty(
            "rate",
            150
        )

        print("Text-to-speech engine ready.")

    # ========================================================
    # SPEAK
    # ========================================================

    def speak(self, message: str):

        print(f"🔊 {message}")

        self.engine.say(message)

        self.engine.runAndWait()

    # ========================================================
    # DETECT
    # ========================================================

    def detect(self, frame):

        """
        Detect persons in one camera frame.

        Returns:
            frame
            person_detected
            person_count
        """

        # Run YOLO
        results = self.model(
            frame,
            verbose=False
        )

        person_detected = False
        person_count = 0

        # ----------------------------------------------------
        # Process YOLO results
        # ----------------------------------------------------

        for result in results:

            if result.boxes is None:
                continue

            for box in result.boxes:

                # Class ID
                class_id = int(
                    box.cls[0]
                )

                # Confidence
                confidence = float(
                    box.conf[0]
                )

                # Class name
                class_name = self.model.names[
                    class_id
                ]

                # ------------------------------------------------
                # PERSON DETECTION
                # ------------------------------------------------

                if (
                    class_name == "person"
                    and confidence >= CONFIDENCE_THRESHOLD
                ):

                    person_detected = True

                    person_count += 1

                    # Bounding box
                    x1, y1, x2, y2 = map(
                        int,
                        box.xyxy[0]
                    )

                    # Draw bounding box
                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 255, 0),
                        2
                    )

                    # Label
                    label = (
                        f"Person "
                        f"{confidence:.2f}"
                    )

                    cv2.putText(
                        frame,
                        label,
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2
                    )

        return (
            frame,
            person_detected,
            person_count
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)
    print("CCTV AI - CAMERA 2")
    print("IP WEBCAM + YOLO PERSON DETECTION")
    print("=" * 60)
    print()

    # --------------------------------------------------------
    # Create detector
    # --------------------------------------------------------

    detector = PersonDetector()

    # --------------------------------------------------------
    # Open Camera 2 IP Webcam
    # --------------------------------------------------------

    print()
    print("Connecting to Camera 2...")
    print(f"URL: {CAMERA_2_URL}")
    print()

    camera = cv2.VideoCapture(
        CAMERA_2_URL
    )

    # --------------------------------------------------------
    # Check connection
    # --------------------------------------------------------

    if not camera.isOpened():

        print("=" * 60)
        print("ERROR: Could not connect to Camera 2.")
        print("=" * 60)

        print()
        print("Check:")
        print("1. IP Webcam server is running.")
        print("2. Phone and PC are on the same Wi-Fi.")
        print("3. IP address is correct.")
        print("4. Port 8080 is correct.")
        print("5. /video URL is correct.")
        print()

        return

    print("=" * 60)
    print("Camera 2 connected successfully!")
    print("=" * 60)
    print()
    print("YOLO person detection started.")
    print("Press Q to quit.")
    print()

    # ========================================================
    # CAMERA LOOP
    # ========================================================

    while True:

        # Read frame
        success, frame = camera.read()

        # ----------------------------------------------------
        # Check frame
        # ----------------------------------------------------

        if not success:

            print(
                "ERROR: Could not read Camera 2 frame."
            )

            break

        # ----------------------------------------------------
        # YOLO detection
        # ----------------------------------------------------

        (
            frame,
            person_detected,
            person_count
        ) = detector.detect(frame)

        # ----------------------------------------------------
        # Display camera information
        # ----------------------------------------------------

        cv2.putText(
            frame,
            "Camera 2 - IP Webcam",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        # ----------------------------------------------------
        # Person count
        # ----------------------------------------------------

        cv2.putText(
            frame,
            f"Persons: {person_count}",
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        # ----------------------------------------------------
        # Voice alert
        # ----------------------------------------------------

        if person_detected:

            detector.speak(
                "Person detected"
            )

        # ----------------------------------------------------
        # Multiple people alert
        # ----------------------------------------------------

        if person_count >= 2:

            detector.speak(
                "Multiple people detected"
            )

        # ----------------------------------------------------
        # Display frame
        # ----------------------------------------------------

        cv2.imshow(
            "CCTV AI - Camera 2",
            frame
        )

        # ----------------------------------------------------
        # Press Q to quit
        # ----------------------------------------------------

        if cv2.waitKey(1) & 0xFF == ord("q"):

            break

    # ========================================================
    # CLEANUP
    # ========================================================

    camera.release()

    cv2.destroyAllWindows()

    print()
    print("=" * 60)
    print("Camera 2 stopped.")
    print("=" * 60)


# ============================================================
# PROGRAM START
# ============================================================

if __name__ == "__main__":

    main()