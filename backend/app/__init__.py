from flask import Flask
from flask_cors import CORS

from .config import get_config
from .errors import register_error_handlers
from .routes import register_blueprints


def create_app(config_name: str | None = None) -> Flask:
    """Application factory. Add new blueprints in app/routes/__init__.py."""
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    register_blueprints(app)
    register_error_handlers(app)

    return app
