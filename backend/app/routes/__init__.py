from flask import Flask

from .health import bp as health_bp
from .people import bp as people_bp
from .upload import bp as upload_bp

# Add your blueprints here as you build them.
BLUEPRINTS = (health_bp, upload_bp, people_bp)


def register_blueprints(app: Flask) -> None:
    for bp in BLUEPRINTS:
        app.register_blueprint(bp, url_prefix="/api")
