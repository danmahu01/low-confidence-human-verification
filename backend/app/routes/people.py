from flask import Blueprint, jsonify, request

from .. import store
from ..errors import ApiError

bp = Blueprint("people", __name__)


@bp.get("/people")
def people():
    """Detections from the most recent upload, or from ?upload_id=."""
    upload_id = request.args.get("upload_id")

    if upload_id:
        entry = store.get_analysis(upload_id)
        if entry is None:
            raise ApiError("No analysis for that upload id.", status=404)
    else:
        entry = store.latest_analysis()

    if entry is None:
        return jsonify(people=[], upload=None)

    return jsonify(people=entry["people"], upload=entry["upload"])
