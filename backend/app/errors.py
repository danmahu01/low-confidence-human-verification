from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    """Raise this from a route to return a JSON error with a status code."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        return jsonify(error=exc.message), exc.status

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        return jsonify(error=exc.description), exc.code

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        app.logger.exception("unhandled error")
        if app.config.get("DEBUG"):
            return jsonify(error=str(exc)), 500
        return jsonify(error="internal server error"), 500
