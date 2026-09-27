"""Shared Firebase initialization for the local face-recognition tools."""

import os
from pathlib import Path

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials


PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")


def initialize_firebase():
    """Initialize Firebase from local environment settings and credentials."""
    if firebase_admin._apps:
        return firebase_admin.get_app()

    credentials_path = Path(
        os.getenv("FIREBASE_CREDENTIALS", "serviceAccountKey.json")
    )
    if not credentials_path.is_absolute():
        credentials_path = PROJECT_DIR / credentials_path
    if not credentials_path.is_file():
        raise FileNotFoundError(
            "Firebase service-account JSON was not found. Set FIREBASE_CREDENTIALS "
            "in .env or place serviceAccountKey.json in the project folder."
        )

    database_url = os.getenv("FIREBASE_DATABASE_URL")
    if not database_url:
        raise ValueError("FIREBASE_DATABASE_URL is missing from .env.")

    options = {"databaseURL": database_url}
    storage_bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
    if storage_bucket:
        options["storageBucket"] = storage_bucket

    return firebase_admin.initialize_app(
        credentials.Certificate(str(credentials_path)), options
    )
