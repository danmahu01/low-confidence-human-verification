from flask import Blueprint, current_app, jsonify

from .. import detection

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    """Sanity check that the app booted and can see the weights."""
    return jsonify(
        status="ok",
        model_path=str(detection.model_path()),
        model_available=detection.model_available(),
        device=current_app.config["YOLO_DEVICE"],
        classes=current_app.config["YOLO_CLASSES"],
        threshold=current_app.config["CONFIDENCE_THRESHOLD"],
    )
