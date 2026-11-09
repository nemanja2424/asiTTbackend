from flask import Blueprint, jsonify, request

from ..auth import authenticated
from ..errors import APIError
from ..services import users as service
from ..validation import boolean, json_body, query_boolean, text, uuid4, uuid_list


blueprint = Blueprint('users', __name__, url_prefix='/api/users')
ROLES = ('admin', 'manager', 'worker')


def validated(body):
    data = dict(body)
    for field in ('email', 'full_name'):
        if field in data:
            data[field] = text(data[field], field)
    if 'email' in data and ('@' not in data['email'] or any(c.isspace() for c in data['email'])):
        raise APIError('invalid_input', 'email is invalid')
    if 'role' in data and data['role'] not in ROLES:
        raise APIError('invalid_input', 'role is invalid')
    if 'is_active' in data:
        data['is_active'] = boolean(data['is_active'], 'is_active')
    if 'department_ids' in data:
        data['department_ids'] = uuid_list(data['department_ids'], 'department_ids')
    return data


@blueprint.get('')
@authenticated()
def list_users():
    filters = {}
    for field in ('search', 'role'):
        if field in request.args:
            filters[field] = text(request.args[field], field)
    if 'role' in filters and filters['role'] not in ROLES:
        raise APIError('invalid_input', 'role is invalid')
    if 'department_id' in request.args:
        filters['department_id'] = uuid4(request.args['department_id'], 'department_id')
    if 'is_active' in request.args:
        filters['is_active'] = query_boolean(request.args['is_active'], 'is_active')
    return jsonify(service.list_users(filters, request.args))


@blueprint.get('/<user_id>')
@authenticated()
def detail(user_id):
    return jsonify(service.detail(uuid4(user_id)))


@blueprint.post('')
@authenticated()
def create():
    data = validated(json_body({'email', 'full_name', 'role', 'department_ids'},
                               {'email', 'full_name', 'department_ids'}))
    if not data['department_ids']:
        raise APIError('invalid_input', 'At least one department is required')
    return jsonify(service.create(data)), 201


@blueprint.patch('/<user_id>')
@authenticated()
def update(user_id):
    data = validated(json_body({'email', 'full_name', 'role', 'department_ids', 'is_active'}))
    if not data:
        raise APIError('invalid_input', 'At least one field is required')
    return jsonify(service.update(uuid4(user_id), data))


@blueprint.patch('/<user_id>/deactivate')
@authenticated()
def deactivate(user_id):
    return jsonify(service.update(uuid4(user_id), {'is_active': False}))


@blueprint.patch('/<user_id>/activate')
@authenticated()
def activate(user_id):
    return jsonify(service.update(uuid4(user_id), {'is_active': True}))


@blueprint.put('/<user_id>/departments')
@authenticated()
def departments(user_id):
    data = validated(json_body({'department_ids'}, {'department_ids'}))
    return jsonify(service.update(uuid4(user_id), data))
