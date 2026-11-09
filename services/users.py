import secrets

from ..authorization import transaction_actor
from ..db import run_transaction
from ..errors import APIError
from ..pagination import page_request, page_response
from ..repositories import users as repository
from ..validation import uuid4
from . import scope
from .auth import temporary_hash, user_payload


def payload(connection, user):
    return {**user_payload(connection, user), 'last_active_at': user['last_active_at']}


def target_user(connection, actor, user_id):
    target = repository.find_by_id(connection, user_id)
    if target is None or (not target['is_active'] and actor['role'] != 'admin'):
        raise APIError('not_found', 'User not found', 404)
    return target


def validate_memberships(connection, actor, ids):
    rows = repository.existing_departments(connection, ids)
    if len(rows) != len(ids):
        raise APIError('invalid_departments', 'One or more departments do not exist')
    if actor['role'] == 'manager' and not set(ids) <= scope.managed_departments(connection, actor):
        raise APIError('forbidden', 'Departments are outside your management scope', 403)


def list_users(filters, args):
    def operation(connection):
        actor = transaction_actor(connection)
        if actor['role'] != 'admin' and filters.get('is_active') is False:
            raise APIError('forbidden', 'Inactive users are visible only to admin', 403)
        binding = {**filters, 'endpoint': 'users', 'actor': str(actor['id']), 'role': actor['role']}
        limit, after = page_request(args, binding)
        if after is not None:
            after = uuid4(after, 'cursor position')
        rows = repository.list_users(connection, filters, after, limit, actor['role'] == 'admin')
        return page_response([payload(connection, row) for row in rows], limit, binding, lambda row: row['id'])
    return run_transaction(operation)


def detail(user_id):
    def operation(connection):
        actor = transaction_actor(connection)
        target = target_user(connection, actor, user_id)
        result = payload(connection, target)
        if actor['role'] == 'admin' or scope.fully_subordinate(connection, actor, target):
            result.update(repository.details(connection, user_id))
        return result
    return run_transaction(operation)


def create(data):
    def operation(connection):
        actor = transaction_actor(connection)
        if actor['role'] not in ('admin', 'manager'):
            raise APIError('forbidden', 'You cannot create users', 403)
        if actor['role'] == 'manager' and data.get('role', 'worker') != 'worker':
            raise APIError('forbidden', 'Only admin assigns privileged roles', 403)
        validate_memberships(connection, actor, data['department_ids'])
        password = secrets.token_urlsafe(6)
        target = repository.create(connection, {**data, 'role': data.get('role', 'worker'),
                                               'password_hash': temporary_hash(password)})
        repository.replace_departments(connection, target['id'], data['department_ids'])
        return {**payload(connection, target), 'temporary_password': password}
    return run_transaction(operation)


def update(user_id, data):
    def operation(connection):
        actor = transaction_actor(connection)
        # Managers may reactivate their inactive subordinate workers.
        target = repository.find_by_id(connection, user_id)
        if target is None:
            raise APIError('not_found', 'User not found', 404)
        if actor['role'] == 'worker':
            if actor['id'] != user_id or set(data) - {'full_name'}:
                raise APIError('forbidden', 'Workers may change only their own full_name', 403)
        else:
            scope.require_user_management(connection, actor, target)
        if 'role' in data and actor['role'] != 'admin':
            raise APIError('forbidden', 'Only admin may change roles', 403)
        if 'department_ids' in data:
            validate_memberships(connection, actor, data['department_ids'])
            repository.replace_departments(connection, user_id, data['department_ids'])
        if 'role' in data and data['role'] not in ('admin', 'manager') and target['role'] in ('admin', 'manager'):
            repository.clear_manager_assignments(connection, user_id)
        if data.get('is_active') is False:
            repository.deactivate(connection, user_id)
        updated = repository.update(connection, user_id, data)
        return payload(connection, updated)
    return run_transaction(operation)
