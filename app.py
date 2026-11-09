import sys
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from flask import Flask
from flask.json.provider import DefaultJSONProvider

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import load_config
from backend.errors import register_errors
from backend.routes.auth import blueprint as auth_blueprint
from backend.routes.users import blueprint as users_blueprint
from backend.routes.departments import blueprint as departments_blueprint
from backend.routes.projects import blueprint as projects_blueprint
from backend.routes.logs import blueprint as logs_blueprint
from backend.routes.reports import blueprint as reports_blueprint
from backend.routes.dashboard import blueprint as dashboard_blueprint
from backend.routes.profile_image import blueprint as profile_image_blueprint
from backend.routes.resources import blueprint as resources_blueprint, ResourceRequest
from backend.routes.ai import blueprint as ai_blueprint
from backend.routes.tasks import blueprint as tasks_blueprint
from backend.routes.notifications import blueprint as notifications_blueprint


class APIJSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(value):
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        return DefaultJSONProvider.default(value)


def create_app():
    app = Flask(__name__)
    app.request_class = ResourceRequest
    app.json_provider_class = APIJSONProvider
    app.json = APIJSONProvider(app)
    app.config.update(load_config())
    register_errors(app)
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(users_blueprint)
    app.register_blueprint(departments_blueprint)
    app.register_blueprint(projects_blueprint)
    app.register_blueprint(logs_blueprint)
    app.register_blueprint(reports_blueprint)
    app.register_blueprint(dashboard_blueprint)
    app.register_blueprint(profile_image_blueprint)
    app.register_blueprint(resources_blueprint)
    app.register_blueprint(ai_blueprint)
    app.register_blueprint(tasks_blueprint)
    app.register_blueprint(notifications_blueprint)
    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5000, debug=False)
