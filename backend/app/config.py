import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base config. Values come from the environment; see .env.example."""

    # YOLO model
    YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "models/best.pt")
    # "cpu", "0" for the first CUDA device, "mps" on Apple silicon.
    YOLO_DEVICE = os.getenv("YOLO_DEVICE", "cpu")
    # Detections below this are discarded outright.
    YOLO_MIN_CONFIDENCE = float(os.getenv("YOLO_MIN_CONFIDENCE", "0.25"))
    YOLO_IOU = float(os.getenv("YOLO_IOU", "0.45"))
    # Comma-separated class names to keep; empty means keep everything.
    YOLO_CLASSES = [c for c in os.getenv("YOLO_CLASSES", "person").split(",") if c]
    # Analyse every Nth video frame. Higher is faster and coarser.
    VIDEO_FRAME_STRIDE = int(os.getenv("VIDEO_FRAME_STRIDE", "15"))

    # Confidence gate: at or above this, a detection is trusted and gets low
    # review priority. Below it, a human should look.
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.85"))

    # Storage
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data.db")

    # Uploads
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

    # Flask rejects anything larger with a 413 before the body is read.
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "200")) * 1024 * 1024

    ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "webm", "avi", "mkv", "m4v"}
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "heic"}

    # Which origins the frontend dev server runs on
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")


class DevConfig(Config):
    DEBUG = True


class ProdConfig(Config):
    DEBUG = False


CONFIGS = {
    "development": DevConfig,
    "production": ProdConfig,
}


def get_config(name: str | None = None) -> type[Config]:
    name = name or os.getenv("FLASK_ENV", "development")
    return CONFIGS.get(name, DevConfig)
