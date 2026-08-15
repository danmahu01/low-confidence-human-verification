"""Saving uploaded media to disk.

Files are stored under UPLOAD_DIR with a generated name, so a hostile
filename can never escape the directory or overwrite an existing upload.
The original name is returned for display only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, asdict
from pathlib import Path

from flask import current_app
from werkzeug.datastructures import FileStorage

from .errors import ApiError


@dataclass
class StoredUpload:
    id: str
    filename: str
    stored_name: str
    kind: str  # "video" | "image"
    content_type: str | None
    size_bytes: int

    def to_dict(self) -> dict:
        return asdict(self)


def upload_dir() -> Path:
    """Resolve UPLOAD_DIR against the app root and create it on first use."""
    path = Path(current_app.config["UPLOAD_DIR"])
    if not path.is_absolute():
        path = Path(current_app.root_path).parent / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def extension_of(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def classify(filename: str) -> str:
    """Return "video" or "image", or raise if the extension isn't allowed."""
    ext = extension_of(filename)
    if ext in current_app.config["ALLOWED_VIDEO_EXTENSIONS"]:
        return "video"
    if ext in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        return "image"

    allowed = sorted(
        current_app.config["ALLOWED_VIDEO_EXTENSIONS"]
        | current_app.config["ALLOWED_IMAGE_EXTENSIONS"]
    )
    raise ApiError(
        f"Unsupported file type {'.' + ext if ext else '(none)'}. "
        f"Allowed: {', '.join(allowed)}",
        status=415,
    )


def save(file: FileStorage) -> StoredUpload:
    """Stream a FileStorage to disk and return its metadata."""
    if not file.filename:
        raise ApiError("No filename on the uploaded file.", status=400)

    kind = classify(file.filename)
    upload_id = uuid.uuid4().hex
    stored_name = f"{upload_id}.{extension_of(file.filename)}"
    destination = upload_dir() / stored_name

    # Werkzeug streams in chunks, so a large video never lands in memory.
    file.save(destination)

    size = destination.stat().st_size
    if size == 0:
        destination.unlink(missing_ok=True)
        raise ApiError("Uploaded file is empty.", status=400)

    return StoredUpload(
        id=upload_id,
        filename=file.filename,
        stored_name=stored_name,
        kind=kind,
        content_type=file.mimetype,
        size_bytes=size,
    )
