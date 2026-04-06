import logging
from flask import Flask
from config import Config

def create_app():
    app = Flask(__name__)
    app.secret_key = Config.SECRET_KEY
    app.permanent_session_lifetime = Config.PERMANENT_SESSION_LIFETIME

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Initialize database
    from .database import init_db
    init_db()

    # Register blueprints
    from .routes.auth import auth
    from .routes.search import search
    from .routes.admin import admin
    from .routes.api import api

    app.register_blueprint(auth)
    app.register_blueprint(search)
    app.register_blueprint(admin)
    app.register_blueprint(api)

    # Start scheduler
    from .scheduler import start_scheduler
    start_scheduler()

    return app
