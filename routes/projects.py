from flask import Blueprint, jsonify, request

from ..auth import authenticated
from ..errors import APIError
from ..services import projects as service
from ..validation import iso_date, json_body, query_boolean, text, uuid4, uuid_list


blueprint = Blueprint('projects', __name__, url_prefix='/api/projects')
STATUSES = ('pending', 'active', 'paused', 'finished')


def validated(body):
    data = dict(body)
    if 'name' in data:
        data['name'] = text(data['name'], 'name')
    if 'description' in data and data['description'] is not None:
        data['description'] = text(data['description'], 'description', minimum=0)
    if 'status' in data and data['status'] not in STATUSES:
        raise APIError('invalid_input', 'status is invalid')
    if 'start_date' in data:
        data['start_date'] = iso_date(data['start_date'], 'start_date')
    for field in ('department_ids', 'user_ids'):
        if field in data:
            data[field] = uuid_list(data[field], field)
    return data


@blueprint.get('')
@authenticated()
def list_projects():
    filters = {}
    for field in ('search', 'status'):
        if field in request.args:
            filters[field] = text(request.args[field], field)
    if 'status' in filters and filters['status'] not in STATUSES:
        raise APIError('invalid_input', 'status is invalid')
    for field in ('start_date_from', 'start_date_to', 'end_date_from', 'end_date_to'):
        if field in request.args:
            filters[field] = iso_date(request.args[field], field)
    for field in ('start_date', 'end_date'):
        if field+'_from' in filters and field+'_to' in filters and filters[field+'_from'] > filters[field+'_to']:
            raise APIError('invalid_input', 'Date filter range is reversed')
    for field in ('department_id', 'user_id'):
        if field in request.args:
            filters[field] = uuid4(request.args[field], field)
    if 'archived' in request.args:
        filters['archived'] = query_boolean(request.args['archived'], 'archived')
    return jsonify(service.list_projects(filters, request.args))


@blueprint.get('/<project_id>')
@authenticated()
def detail(project_id):
    return jsonify(service.detail(uuid4(project_id)))


@blueprint.post('')
@authenticated()
def create():
    data = validated(json_body({'name', 'description', 'start_date', 'status', 'department_ids', 'user_ids'},
                               {'name', 'start_date'}))
    return jsonify(service.create(data)), 201


@blueprint.patch('/<project_id>')
@authenticated()
def update(project_id):
    data = validated(json_body({'name', 'description', 'start_date'}))
    if not data:
        raise APIError('invalid_input', 'At least one field is required')
    return jsonify(service.update(uuid4(project_id), data))


@blueprint.patch('/<project_id>/status')
@authenticated()
def status(project_id):
    return jsonify(service.update(uuid4(project_id), validated(json_body({'status'}, {'status'}))))


@blueprint.patch('/<project_id>/archive')
@authenticated()
def archive(project_id):
    return jsonify(service.archive(uuid4(project_id), True))


@blueprint.patch('/<project_id>/unarchive')
@authenticated()
def unarchive(project_id):
    return jsonify(service.archive(uuid4(project_id), False))


@blueprint.put('/<project_id>/departments')
@authenticated()
def departments(project_id):
    data = validated(json_body({'department_ids'}, {'department_ids'}))
    return jsonify(service.replace_assignments(uuid4(project_id), 'departments', data['department_ids']))


@blueprint.put('/<project_id>/users')
@authenticated()
def users(project_id):
    data = validated(json_body({'user_ids'}, {'user_ids'}))
    return jsonify(service.replace_assignments(uuid4(project_id), 'users', data['user_ids']))


@blueprint.get('/<project_id>/participants')
@authenticated()
def participants(project_id):
    return jsonify(service.participants(uuid4(project_id), request.args))
