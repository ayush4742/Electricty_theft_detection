from __future__ import annotations

import logging
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model.pkl"
SCALER_PATH = BASE_DIR / "scaler.pkl"
IMPUTER_PATH = BASE_DIR / "imputer.pkl"
DB_PATH = BASE_DIR / "predictions.db"
HOST = "0.0.0.0"
PORT = 5000
DEBUG = True


def configure_logging() -> None:
    """Configure application logging for console output and file storage."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(BASE_DIR / "app.log", encoding="utf-8"),
        ],
    )
