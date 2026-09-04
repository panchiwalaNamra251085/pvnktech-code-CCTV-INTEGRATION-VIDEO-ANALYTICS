import cv2
import pyttsx3
from ultralytics import YOLO


# Existing YOLO model
MODEL_PATH = r"C:\CCTV-AI\yolo26n.pt"


class PersonDetector:

    def __init__(self):
        print("Loading YOLO model...")

        self.model = YOLO(MODEL_PATH)

        print("YOLO model loaded.")

        # Text-to-speech engine
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 150)

    def speak(self, message: str):
        print(f"🔊 {message}")

        self.engine.say(message)
        self.engine.runAndWait()

    def detect(self, frame):
        """
        Detect persons in one camera frame.

        Returns:
            frame
            person_detected
        """

        results = self.model(
            frame,
            verbose=False
        )

        person_detected = False

        for result in results:

            if result.boxes is None:
                continue

            for box in result.boxes:

                class_id = int(box.cls[0])
                confidence = float(box.conf[0])

                class_name = self.model.names[class_id]

                # Step 1: PERSON ONLY
                if (
                    class_name == "person"
                    and confidence >= 0.50
                ):

                    person_detected = True

                    # Bounding box
                    x1, y1, x2, y2 = map(
                        int,
                        box.xyxy[0]
                    )

                    # Draw box
                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 255, 0),
                        2
                    )

                    # Label
                    label = f"Person {confidence:.2f}"

                    cv2.putText(
                        frame,
                        label,
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2
                    )

        return frame, person_detected


def main():

    print("=" * 50)
    print("STEP 1 - PERSON DETECTION")
    print("=" * 50)

    detector = PersonDetector()

    # Open computer camera
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("ERROR: Could not open camera.")
        return

    print("Camera started.")
    print("Press Q to quit.")

    while True:

        success, frame = camera.read()

        if not success:
            print("ERROR: Could not read camera frame.")
            break

        # Run YOLO
        frame, person_detected = detector.detect(frame)

        # Voice
        if person_detected:
            detector.speak("Person detected")

        # Display
        cv2.imshow(
            "CCTV - Person Detection",
            frame
        )

        # Quit
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()

    print("Camera stopped.")


if __name__ == "__main__":
    main()