from flask import Blueprint, current_app, jsonify, request

from .. import detection, storage, validation
from ..errors import ApiError

bp = Blueprint("validate", __name__)

IMAGE_FIELDS = ("file", "image")
LABEL_FIELDS = ("labels", "annotations", "ground_truth", "txt")


def _pick(fields):
    for name in fields:
        found = request.files.get(name)
        if found is not None:
            return found
    return None


@bp.post("/validate")
def validate():
    """Score the model against ground-truth labels for one test image."""
    image_file = _pick(IMAGE_FIELDS)
    label_file = _pick(LABEL_FIELDS)

    if image_file is None:
        raise ApiError(
            f"No image uploaded. Use one of: {', '.join(IMAGE_FIELDS)}.", status=400
        )
    if label_file is None:
        raise ApiError(
            "No ground-truth labels uploaded. Use one of: "
            f"{', '.join(LABEL_FIELDS)}.",
            status=400,
        )

    stored = storage.save(image_file)
    if stored.kind != "image":
        raise ApiError(
            "Validation compares a single frame; upload an image, not a video.",
            status=400,
        )

    path = storage.upload_dir() / stored.stored_name

    import cv2

    image = cv2.imread(str(path))
    if image is None:
        raise ApiError("Could not read the uploaded image.", status=400)
    height, width = image.shape[:2]

    model = detection.get_model()
    truths = validation.parse_labels(
        label_file.read().decode("utf-8", errors="replace"),
        image_width=width,
        image_height=height,
        names=model.names,
        keep_class_ids=detection._class_filter(model),
    )

    detections = detection.detect(path, stored.kind, stored.id)

    iou_threshold = float(
        request.form.get("iou_threshold", current_app.config["VALIDATION_IOU"])
    )
    metrics = validation.evaluate(detections, truths, iou_threshold=iou_threshold)

    return jsonify(
        upload=stored.to_dict(),
        metrics=metrics.to_dict(),
        predictions=[d.to_dict() for d in detections],
        ground_truth=[t.to_dict() for t in truths],
    ), 201
