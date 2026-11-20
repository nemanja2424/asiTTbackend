from flask import Blueprint, current_app, jsonify


blueprint = Blueprint('system', __name__, url_prefix='/api/system')


@blueprint.get('/update')
def update():
    response = jsonify(latest_version=current_app.config['LATEST_DESKTOP_VERSION'],
                       download_url=current_app.config['DESKTOP_UPDATE_URL'],
                       sha256=current_app.config['DESKTOP_UPDATE_SHA256'])
    response.headers['Cache-Control'] = 'no-store'
    return response
