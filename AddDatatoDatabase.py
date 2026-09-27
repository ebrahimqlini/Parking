"""Optionally seed Firebase from the private local students.json file."""

import argparse
import json
from pathlib import Path

from firebase_admin import db

from firebase_config import PROJECT_DIR, initialize_firebase


STUDENT_DATA_PATH = PROJECT_DIR / "students.json"


def main():
    parser = argparse.ArgumentParser(
        description="Seed Firebase Students records from private local JSON data."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the records to Firebase (overwrites matching student IDs)",
    )
    args = parser.parse_args()

    if not STUDENT_DATA_PATH.is_file():
        raise FileNotFoundError(
            "{} is missing. Copy students.example.json to students.json and edit "
            "the records locally first.".format(STUDENT_DATA_PATH.name)
        )

    with STUDENT_DATA_PATH.open("r", encoding="utf-8") as student_file:
        students = json.load(student_file)
    if not isinstance(students, dict) or not students:
        raise ValueError("students.json must contain a non-empty ID-to-record object.")

    for student_id, record in students.items():
        if not isinstance(record, dict) or not record.get("name"):
            raise ValueError("Student {} needs a name.".format(student_id))

    print("Prepared {} student record(s): {}".format(len(students), ", ".join(students)))
    if not args.apply:
        print("Preview only. Add --apply to write records to Firebase.")
        return

    confirmation = input(
        "This will overwrite matching IDs under Firebase Students/. Type WRITE to continue: "
    )
    if confirmation != "WRITE":
        print("No records were written.")
        return

    initialize_firebase()
    for student_id, record in students.items():
        db.reference("Students/{}".format(student_id)).set(record)
    print("Wrote {} student record(s).".format(len(students)))


if __name__ == "__main__":
    main()
