from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app

from ..authorization import require_role, transaction_actor
from ..db import run_transaction
from ..errors import APIError
from ..pagination import page_request, page_response
from ..repositories import projects as repository
from ..validation import uuid4
from . import scope
from .auth import user_payload


def permissions(connection, actor):
    return repository.permission_ids(connection, actor, scope.managed_departments(connection, actor))


def accessible(connection, actor, project_id, write=False):
    project = repository.find(connection, project_id)
    visible, manageable = permissions(connection, actor)
    if project is None or project_id not in visible:
        raise APIError('not_found', 'Project not found', 404)
    if write and project_id not in manageable:
        raise APIError('forbidden', 'You cannot manage this project', 403)
    return project


def participant_payload(connection, row):
    result = user_payload(connection, row)
    result['assignment_sources'] = [source for source, present in (
        ('direct', row['assigned_directly']), ('department', row['assigned_by_department'])) if present]
    return result


def details_payload(connection, actor, project):
    result = dict(project)
    project_id = project['id']
    admin = actor['role'] == 'admin'
    result['departments'] = repository.assigned_departments(connection, project_id)
    result['users'] = [user_payload(connection, row) for row in repository.assigned_users(connection, project_id, admin)]
    result['participants'] = [participant_payload(connection, row) for row in repository.participants(connection, project_id, admin)]
    _, manageable = permissions(connection, actor)
    if admin or project_id in manageable:
        result['spent_time'] = repository.total_time(connection, project_id)
    return result


def validate_assignments(connection, actor, kind, ids, old_ids=None):
    submitted = set(ids)
    rows = repository.active_entities(connection, kind, submitted)
    if len(rows) != len(submitted):
        raise APIError('invalid_assignments', 'All assigned entities must exist and be active')
    if actor['role'] == 'admin':
        return
    require_role(actor, 'manager')
    managed = scope.managed_departments(connection, actor)
    if kind == 'departments':
        own = managed
    else:
        # Include old assignments in classification so foreign ones cannot be silently removed.
        all_ids = submitted | (old_ids or set())
        old_rows = repository.active_entities(connection, 'users', all_ids)
        own = {row['id'] for row in old_rows if scope.fully_subordinate(connection, actor, row)}
    foreign_old = (old_ids or set()) - own
    if not foreign_old <= submitted or not (submitted - foreign_old) <= own:
        raise APIError('forbidden', 'Preserve all assignments outside your scope and change only your own', 403)


def today():
    return datetime.now(ZoneInfo(current_app.config['APP_TIMEZONE'])).date()


def validate_dates(start_date, end_date):
    if end_date is not None and end_date < start_date:
        raise APIError('invalid_dates', 'A finished project cannot end before its start_date')


def list_projects(filters, args):
    def operation(connection):
        actor = transaction_actor(connection)
        visible, _ = permissions(connection, actor)
        binding = {**filters, 'endpoint': 'projects', 'actor': str(actor['id']), 'role': actor['role']}
        limit, after = page_request(args, binding)
        if after is not None:
            after = uuid4(after, 'cursor position')
        rows = repository.list_projects(connection, visible, filters, after, limit)
        return page_response(rows, limit, binding, lambda row: str(row['id']))
    return run_transaction(operation)


def detail(project_id):
    def operation(connection):
        actor = transaction_actor(connection)
        return details_payload(connection, actor, accessible(connection, actor, project_id))
    return run_transaction(operation)


def create(data):
    def operation(connection):
        actor = transaction_actor(connection)
        require_role(actor, 'admin', 'manager')
        for kind in ('departments', 'users'):
            validate_assignments(connection, actor, kind, data.get('department_ids' if kind=='departments' else 'user_ids', []))
        values = {**data, 'status': data.get('status', 'pending')}
        values['end_date'] = today() if values['status']=='finished' else None
        validate_dates(values['start_date'], values['end_date'])
        project = repository.create(connection, values)
        repository.replace_assignments(connection, project['id'], 'departments', data.get('department_ids', []))
        repository.replace_assignments(connection, project['id'], 'users', data.get('user_ids', []))
        return details_payload(connection, actor, project)
    return run_transaction(operation)


def update(project_id, data):
    def operation(connection):
        actor = transaction_actor(connection)
        project = accessible(connection, actor, project_id, write=True)
        values = dict(data)
        if 'status' in values:
            values['end_date'] = today() if values['status']=='finished' else None
        validate_dates(values.get('start_date', project['start_date']), values.get('end_date', project['end_date']))
        updated = repository.update(connection, project_id, values)
        return details_payload(connection, actor, updated)
    return run_transaction(operation)


def archive(project_id, archived):
    return update(project_id, {'archived_at': datetime.now(ZoneInfo(current_app.config['APP_TIMEZONE'])) if archived else None})


def replace_assignments(project_id, kind, ids):
    def operation(connection):
        actor = transaction_actor(connection)
        accessible(connection, actor, project_id, write=True)
        old = repository.assignment_ids(connection, project_id, kind)
        validate_assignments(connection, actor, kind, ids, old)
        repository.replace_assignments(connection, project_id, kind, ids)
        return details_payload(connection, actor, repository.find(connection, project_id))
    return run_transaction(operation)


def participants(project_id, args):
    def operation(connection):
        actor = transaction_actor(connection)
        accessible(connection, actor, project_id)
        binding = {'endpoint': 'participants', 'project_id': str(project_id),
                   'actor': str(actor['id']), 'role': actor['role']}
        limit, after = page_request(args, binding)
        if after is not None:
            after = uuid4(after, 'cursor position')
        rows = [participant_payload(connection, row) for row in repository.participants(
            connection, project_id, actor['role']=='admin', after, limit)]
        return page_response(rows, limit, binding, lambda row: row['id'])
    return run_transaction(operation)
