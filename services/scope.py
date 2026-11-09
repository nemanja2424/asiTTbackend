from ..errors import APIError
from ..repositories import scope as repository


def managed_departments(connection, actor):
    return repository.manager_departments(connection, actor['id']) if actor['role'] == 'manager' else set()


def fully_subordinate(connection, actor, target):
    if actor['role'] != 'manager' or target['role'] != 'worker' or actor['id'] == target['id']:
        return False
    memberships = repository.memberships(connection, target['id'])
    return bool(memberships) and memberships <= managed_departments(connection, actor)


def require_user_management(connection, actor, target):
    if actor['role'] != 'admin' and not fully_subordinate(connection, actor, target):
        raise APIError('forbidden', 'User is outside your management scope', 403)


def visible_departments(connection, actor):
    if actor['role'] == 'admin':
        return None
    if actor['role'] == 'manager':
        return managed_departments(connection, actor)
    return repository.memberships(connection, actor['id'])


def readable_user_ids(connection, actor):
    """None means all users. Read scope differs from strict worker management."""
    if actor['role'] == 'admin':
        return None
    if actor['role'] == 'manager':
        return repository.users_in_departments(connection, managed_departments(connection, actor))
    return {actor['id']}
