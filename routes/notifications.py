from flask import Blueprint, jsonify, request

from ..auth import authenticated
from ..services import notifications as service
from ..validation import query_boolean, uuid4

blueprint = Blueprint('notifications', __name__, url_prefix='/api/notifications')


@blueprint.get('')
@authenticated()
def listing():
    read = query_boolean(request.args['is_read'], 'is_read') if 'is_read' in request.args else None
    return jsonify(service.listing(request.args, read))


@blueprint.get('/unread-count')
@authenticated()
def count():
    return jsonify(service.count())


@blueprint.patch('/<notification_id>/read')
@authenticated()
def read(notification_id):
    return jsonify(service.read(uuid4(notification_id, 'notification_id')))


@blueprint.post('/read-all')
@authenticated()
def read_all():
    return jsonify(service.read())
