from flask import Blueprint, Response, jsonify, request

from ..auth import authenticated
from ..errors import APIError
from ..services import profile_image as service
from ..validation import uuid4


blueprint = Blueprint('profile_image', __name__, url_prefix='/api')


@blueprint.post('/me/profile-image')
@authenticated()
def upload():
    # Multipart framing is allowed in addition to the 5 MiB image itself.
    request.max_content_length = 5 * 1024 * 1024 + 64 * 1024
    if set(request.files) != {'image'} or len(request.files.getlist('image')) != 1 or request.form:
        raise APIError('invalid_input', 'Exactly one image file is required')
    return jsonify(profile_img=service.upload(request.files['image'].stream))


@blueprint.delete('/me/profile-image')
@authenticated()
def delete():
    service.delete()
    return jsonify(profile_img=None)


@blueprint.get('/users/<user_id>/profile-image')
@authenticated()
def get(user_id):
    data = service.get(uuid4(user_id))
    response = Response(data, mimetype='image/webp')
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response
