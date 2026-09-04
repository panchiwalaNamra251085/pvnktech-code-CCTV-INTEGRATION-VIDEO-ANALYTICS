import cv2

from person_detector import PersonDetector


def main():

    print("🚀 Starting Step 1...")
    print("👤 Person detection + voice")

    detector = PersonDetector()

    # Open default camera
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("❌ Could not open camera")
        return

    print("📹 Camera started")
    print("Press Q to stop")

    while True:

        success, frame = camera.read()

        if not success:
            print("❌ Failed to read camera frame")
            break

        # Run person detection
        frame, person_detected = detector.detect(frame)

        # Voice alert
        if person_detected:
            detector.speak("Person detected")

        # Show camera
        cv2.imshow(
            "CCTV - Step 1 - Person Detection",
            frame
        )

        # Q = quit
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()

    cv2.destroyAllWindows()

    print("🛑 Camera stopped")


if __name__ == "__main__":
    main()