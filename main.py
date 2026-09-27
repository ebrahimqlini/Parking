"""Local Flask interface for the Smart Parking face-recognition module."""

import logging
import os
import pickle
import threading
import time
from pathlib import Path

import cv2
import face_recognition
import numpy as np
from flask import Flask, Response, jsonify, render_template
from firebase_admin import db

from firebase_config import PROJECT_DIR, initialize_firebase


logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

initialize_firebase()

ENCODINGS_PATH = PROJECT_DIR / "EncodeFile.p"
MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.6"))
PROCESS_EVERY_N_FRAMES = max(1, int(os.getenv("FACE_PROCESS_EVERY_N_FRAMES", "5")))
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))


def load_encodings():
    """Load locally generated face encodings, or start without enrolled faces."""
    if not ENCODINGS_PATH.is_file():
        LOGGER.warning(
            "No encoding file found at %s. Run EncodeGenerator.py after adding "
            "private enrollment images to Images/.",
            ENCODINGS_PATH,
        )
        return [], []

    with ENCODINGS_PATH.open("rb") as encoding_file:
        encodings, student_ids = pickle.load(encoding_file)
    if len(encodings) != len(student_ids):
        raise ValueError("EncodeFile.p contains a different number of encodings and IDs.")
    return encodings, student_ids


KNOWN_ENCODINGS, STUDENT_IDS = load_encodings()

_result_lock = threading.Lock()
_student_cache_lock = threading.Lock()
_student_cache = {}
_student_cache_ttl = 60
_latest_result = {
    "status": "starting",
    "name": "Starting camera",
    "email": "",
    "box": None,
}


def update_result(result):
    global _latest_result
    with _result_lock:
        _latest_result = result


def get_student_record(student_id):
    """Read a Firebase record at most once per student per cache interval."""
    now = time.monotonic()
    with _student_cache_lock:
        cached = _student_cache.get(student_id)
        if cached and now - cached[0] < _student_cache_ttl:
            return cached[1]

    record = db.reference("Students/{}".format(student_id)).get()
    with _student_cache_lock:
        _student_cache[student_id] = (now, record)
    return record


class FaceRecognition:
    """Detect a face in a camera frame and resolve it against enrolled IDs."""

    def recognize(self, frame):
        if not KNOWN_ENCODINGS:
            return {
                "status": "not_configured",
                "name": "No enrolled faces",
                "email": "",
                "box": None,
            }

        height, width = frame.shape[:2]
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_frame = np.ascontiguousarray(small_frame[:, :, ::-1])
        face_locations = face_recognition.face_locations(rgb_frame)

        if not face_locations:
            return {
                "status": "no_face",
                "name": "No face detected",
                "email": "",
                "box": None,
            }

        encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        top, right, bottom, left = face_locations[0]
        box = (top * 4, right * 4, bottom * 4, left * 4)
        if not encodings:
            return {
                "status": "unknown",
                "name": "Unknown",
                "email": "Unknown",
                "box": box,
            }

        distances = face_recognition.face_distance(KNOWN_ENCODINGS, encodings[0])
        if len(distances) == 0:
            return {
                "status": "unknown",
                "name": "Unknown",
                "email": "Unknown",
                "box": box,
            }

        match_index = int(np.argmin(distances))
        if distances[match_index] > MATCH_THRESHOLD:
            return {
                "status": "unknown",
                "name": "Unknown",
                "email": "Unknown",
                "box": box,
            }

        student_id = STUDENT_IDS[match_index]
        try:
            student = get_student_record(student_id)
        except Exception:
            LOGGER.exception("Firebase lookup failed for a recognized student ID.")
            return {
                "status": "database_error",
                "name": "Database unavailable",
                "email": "",
                "box": box,
            }

        # A face encoding without a matching Realtime Database record is unknown.
        if not isinstance(student, dict) or not student.get("name"):
            return {
                "status": "unknown",
                "name": "Unknown",
                "email": "Unknown",
                "box": box,
            }

        return {
            "status": "recognized",
            "name": str(student["name"]),
            "email": str(student.get("email") or ""),
            "box": box,
        }


def draw_face_box(frame, result):
    box = result.get("box")
    if not box:
        return frame

    top, right, bottom, left = box
    color = (0, 160, 0) if result.get("status") == "recognized" else (0, 0, 220)
    label = result.get("name", "Unknown")
    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
    cv2.rectangle(frame, (left, bottom - 32), (right, bottom), color, cv2.FILLED)
    cv2.putText(
        frame,
        label,
        (left + 6, bottom - 8),
        cv2.FONT_HERSHEY_DUPLEX,
        0.6,
        (255, 255, 255),
        1,
    )
    return frame


def generate_frames():
    """Stream webcam frames and update recognition at a controlled interval."""
    camera = cv2.VideoCapture(CAMERA_INDEX)
    if not camera.isOpened():
        update_result(
            {
                "status": "camera_unavailable",
                "name": "Camera unavailable",
                "email": "",
                "box": None,
            }
        )
        LOGGER.error("Could not open camera index %s.", CAMERA_INDEX)
        camera.release()
        return

    recognizer = FaceRecognition()
    frame_count = 0
    latest_frame_result = _latest_result
    try:
        while True:
            success, frame = camera.read()
            if not success:
                update_result(
                    {
                        "status": "camera_error",
                        "name": "Camera read failed",
                        "email": "",
                        "box": None,
                    }
                )
                break

            frame_count += 1
            if frame_count % PROCESS_EVERY_N_FRAMES == 0:
                try:
                    latest_frame_result = recognizer.recognize(frame)
                    update_result(latest_frame_result)
                except Exception:
                    LOGGER.exception("Face recognition failed for a camera frame.")
                    latest_frame_result = {
                        "status": "recognition_error",
                        "name": "Recognition error",
                        "email": "",
                        "box": None,
                    }
                    update_result(latest_frame_result)

            frame = draw_face_box(frame, latest_frame_result)
            encoded, buffer = cv2.imencode(".jpg", frame)
            if not encoded:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buffer.tobytes()
                + b"\r\n"
            )
    finally:
        camera.release()
        update_result(
            {
                "status": "stopped",
                "name": "Camera stopped",
                "email": "",
                "box": None,
            }
        )


app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/person_data")
def person_data():
    with _result_lock:
        result = dict(_latest_result)
    result.pop("box", None)
    return jsonify(result)


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
        threaded=True,
        use_reloader=False,
    )
