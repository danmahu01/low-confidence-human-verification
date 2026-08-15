from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.datastructures import FileStorage

from .. import confidence, detection, storage, store
from ..errors import ApiError

bp = Blueprint("upload", __name__)

# Accept whichever field name the client used, so an <input name="video">
# and an <input name="image"> both work.
FIELD_NAMES = ("file", "video", "image", "media")


def _incoming_file() -> FileStorage | None:
    for name in FIELD_NAMES:
        file = request.files.get(name)
        if file is not None:
            return file
    return None


@bp.post("/upload")
def upload():
    """Accept one video or image, run YOLO over it, return what was found."""
    file = _incoming_file()
    if file is None:
        raise ApiError(
            "No file uploaded. Send multipart/form-data with one of: "
            f"{', '.join(FIELD_NAMES)}.",
            status=400,
        )

    stored = storage.save(file)
    path = storage.upload_dir() / stored.stored_name

    # Inference runs inline, so a long video holds the request open.
    # Move this to a worker if clips get big.
    detections = detection.detect(path, stored.kind, stored.id)

    # Walk them lowest-confidence first, re-scoring the uncertain ones.
    confidence.apply(detections, stored.id)

    people = [d.to_dict() for d in detections]

    store.save_analysis(stored.to_dict(), people)

    return jsonify(upload=stored.to_dict(), people=people), 201


@bp.get("/upload/<upload_id>/file")
def download(upload_id: str):
    """Serve a stored upload back — used for previews on the results page."""
    # IDs are generated hex; reject anything else before it reaches glob().
    if not upload_id.isalnum():
        raise ApiError("Invalid upload id.", status=400)

    directory = storage.upload_dir()
    matches = list(directory.glob(f"{upload_id}.*"))
    if not matches:
        raise ApiError("Upload not found.", status=404)

    # conditional=True enables range requests, which video players need to seek.
    return send_from_directory(directory, matches[0].name, conditional=True)


@bp.get("/upload/<upload_id>/crops/<filename>")
def crop(upload_id: str, filename: str):
    """Serve one detection thumbnail."""
    if not upload_id.isalnum():
        raise ApiError("Invalid upload id.", status=400)

    # send_from_directory rejects traversal in `filename` itself.
    return send_from_directory(storage.crops_dir(upload_id), filename)


@bp.get("/upload/limits")
def limits():
    """Let the frontend read the accepted types and size cap."""
    return jsonify(
        max_bytes=current_app.config["MAX_CONTENT_LENGTH"],
        video_extensions=sorted(current_app.config["ALLOWED_VIDEO_EXTENSIONS"]),
        image_extensions=sorted(current_app.config["ALLOWED_IMAGE_EXTENSIONS"]),
    )
