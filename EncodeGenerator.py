"""Generate local face embeddings from private images in Images/."""

import pickle
from pathlib import Path

import cv2
import face_recognition
import numpy as np

from firebase_config import PROJECT_DIR


IMAGE_DIR = PROJECT_DIR / "Images"
OUTPUT_PATH = PROJECT_DIR / "EncodeFile.p"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


def main():
    if not IMAGE_DIR.is_dir():
        raise FileNotFoundError(
            "Create Images/ and add one face image per person before encoding."
        )

    image_paths = sorted(
        path
        for path in IMAGE_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not image_paths:
        raise ValueError("No supported face images were found in Images/.")

    encodings = []
    student_ids = []
    for image_path in image_paths:
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError("Could not read image: {}".format(image_path.name))

        rgb_image = np.ascontiguousarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        face_encodings = face_recognition.face_encodings(rgb_image)
        if len(face_encodings) != 1:
            raise ValueError(
                "{} must contain exactly one detectable face; found {}.".format(
                    image_path.name, len(face_encodings)
                )
            )

        encodings.append(face_encodings[0])
        student_ids.append(image_path.stem)
        print("Encoded {}".format(image_path.name))

    temporary_path = OUTPUT_PATH.with_suffix(".tmp")
    with temporary_path.open("wb") as output_file:
        pickle.dump([encodings, student_ids], output_file)
    temporary_path.replace(OUTPUT_PATH)
    print("Saved {} local face encodings to {}".format(len(encodings), OUTPUT_PATH))


if __name__ == "__main__":
    main()
