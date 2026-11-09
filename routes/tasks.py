from flask import Blueprint, jsonify, request

from ..auth import authenticated
from ..errors import APIError
from ..services import tasks as service, task_attachments
from ..validation import iso_date, json_body, query_boolean, text, uuid4

blueprint = Blueprint('tasks', __name__, url_prefix='/api/tasks')
STATUSES = ('pending','in_progress','blocked','completed')
PRIORITIES = ('low','normal','high','urgent')
FIELDS = {'title','description','assigned_to','status','priority','due_date'}


def validated(data):
    if 'title' in data: data['title'] = text(data['title'], 'title', maximum=255)
    if 'description' in data and data['description'] is not None:
        data['description'] = text(data['description'], 'description', minimum=0, maximum=20000, strip=False)
    if 'assigned_to' in data and data['assigned_to'] is not None: data['assigned_to'] = uuid4(data['assigned_to'], 'assigned_to')
    if 'due_date' in data and data['due_date'] is not None: data['due_date'] = iso_date(data['due_date'], 'due_date')
    for key, values in (('status', STATUSES), ('priority', PRIORITIES)):
        if key in data and data[key] not in values: raise APIError('invalid_input', f'{key} is invalid')
    return data


@blueprint.get('')
@authenticated()
def listing():
    filters = {}
    for key in ('project_id','assigned_to'):
        if key in request.args: filters[key] = uuid4(request.args[key], key)
    for key in ('status','priority'):
        if key in request.args: filters[key] = request.args[key]
    for key in ('due_from','due_to'):
        if key in request.args: filters[key] = iso_date(request.args[key], key)
    if 'mine' in request.args: filters['mine'] = query_boolean(request.args['mine'], 'mine')
    if 'due_from' in filters and 'due_to' in filters and filters['due_from'] > filters['due_to']:
        raise APIError('invalid_input', 'Date filter range is reversed')
    return jsonify(service.listing(validated(filters), request.args))


@blueprint.post('')
@authenticated()
def create():
    data = validated(json_body(FIELDS | {'project_id'}, {'project_id','title'}))
    data['project_id'] = uuid4(data['project_id'], 'project_id')
    return jsonify(service.create(data)), 201


@blueprint.get('/<task_id>')
@authenticated()
def detail(task_id):
    return jsonify(service.detail(uuid4(task_id, 'task_id')))


@blueprint.patch('/<task_id>')
@authenticated()
def update(task_id):
    data = validated(json_body(FIELDS))
    if not data: raise APIError('invalid_input', 'At least one field is required')
    return jsonify(service.update(uuid4(task_id, 'task_id'), data))


@blueprint.delete('/<task_id>')
@authenticated()
def delete(task_id):
    return jsonify(service.delete(uuid4(task_id, 'task_id')))


@blueprint.get('/<task_id>/comments')
@authenticated()
def comments(task_id):
    return jsonify(service.timeline(uuid4(task_id, 'task_id'), request.args, 'comments'))


@blueprint.post('/<task_id>/comments')
@authenticated()
def add_comment(task_id):
    data = json_body({'content'}, {'content'})
    return jsonify(service.add_comment(uuid4(task_id, 'task_id'), text(data['content'], 'content', maximum=4000))), 201


@blueprint.get('/<task_id>/activity')
@authenticated()
def activity(task_id):
    return jsonify(service.timeline(uuid4(task_id, 'task_id'), request.args, 'activity'))


@blueprint.post('/<task_id>/reopen')
@authenticated()
def reopen(task_id):
    data = json_body({'reason'}, {'reason'})
    return jsonify(service.reopen(uuid4(task_id, 'task_id'), text(data['reason'], 'reason', maximum=4000)))


@blueprint.get('/<task_id>/attachments')
@authenticated()
def attachments(task_id):
    return jsonify(task_attachments.listing(uuid4(task_id, 'task_id'), request.args))


@blueprint.post('/<task_id>/attachments')
@authenticated()
def add_attachment(task_id):
    data = json_body({'resource_id'}, {'resource_id'})
    return jsonify(task_attachments.link(uuid4(task_id, 'task_id'), uuid4(data['resource_id'], 'resource_id'))), 201


@blueprint.delete('/<task_id>/attachments/<attachment_id>')
@authenticated()
def remove_attachment(task_id, attachment_id):
    return jsonify(task_attachments.unlink(uuid4(task_id, 'task_id'), uuid4(attachment_id, 'attachment_id')))
