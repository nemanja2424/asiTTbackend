from ..authorization import require_role, transaction_actor
from ..db import run_transaction
from ..errors import APIError
from ..pagination import page_request, page_response
from ..repositories import auth as auth_repository
from ..repositories import departments as repository
from ..repositories import scope as scope_repository
from ..repositories import users as user_repository
from ..validation import uuid4
from . import scope


def accessible(connection, actor, department_id, write=False):
    department = repository.find(connection, department_id)
    visible = scope.visible_departments(connection, actor)
    if department is None or (visible is not None and department_id not in visible) or (
            actor['role'] != 'admin' and not department['is_active']):
        raise APIError('not_found', 'Department not found', 404)
    if write:
        require_role(actor, 'admin', 'manager')
    return department


def manager_assignment(connection, actor, manager_id):
    if manager_id is None:
        return
    manager = auth_repository.find_by_id(connection, manager_id)
    if manager is None or not manager['is_active']:
        raise APIError('invalid_manager', 'Manager must be an active user')
    if actor['role'] == 'admin':
        if manager['role'] == 'worker':
            user_repository.update(connection, manager_id, {'role': 'manager'})
        elif manager['role'] not in ('admin', 'manager'):
            raise APIError('invalid_manager', 'Assigned user must have admin or manager role')
    else:
        memberships = scope_repository.memberships(connection, manager_id)
        if manager['role'] not in ('admin', 'manager') or not memberships or not memberships <= scope.managed_departments(connection, actor):
            raise APIError('forbidden', 'Assigned manager is outside your scope or requires promotion', 403)


def basic(connection, actor, department, visible):
    result = dict(department)
    manager = auth_repository.find_by_id(connection, department['manager_id']) if department['manager_id'] else None
    result['manager'] = ({'id': manager['id'], 'full_name': manager['full_name'], 'profile_img': manager['profile_img']} if manager and
                         (manager['is_active'] or actor['role'] == 'admin') else None)
    if result['manager'] is None:
        result['manager_id'] = None
    parent_id = department['parent_department_id']
    parent = repository.find(connection, parent_id) if parent_id else None
    if parent and (visible is None or parent_id in visible) and (parent['is_active'] or actor['role']=='admin'):
        result['parent_department'] = {'id': parent['id'], 'name': parent['name']}
    else:
        result['parent_department'] = None
        result['parent_department_id'] = None
    return result


def list_departments(active=True, tree=False, args=None):
    def operation(connection):
        actor = transaction_actor(connection)
        if actor['role'] != 'admin' and active is not True:
            raise APIError('forbidden', 'Inactive departments are visible only to admin', 403)
        visible = scope.visible_departments(connection, actor)
        binding = {'endpoint': 'departments', 'actor': str(actor['id']), 'role': actor['role'],
                   'is_active': active, 'visible': sorted(str(item) for item in visible) if visible is not None else None}
        limit, after = (None, None) if tree else page_request(args or {}, binding)
        if after is not None:
            after = uuid4(after, 'cursor position')
        rows = repository.list_departments(connection, visible, active, after, limit)
        items = [basic(connection, actor, row, visible) for row in rows]
        if tree:
            by_id = {row['id']: {**row, 'children': []} for row in items}
            roots = []
            for row in by_id.values():
                parent = by_id.get(row['parent_department_id'])
                if parent is None:
                    roots.append(row)
                else:
                    parent['children'].append(row)
            items = roots
            return {'items': items}
        return page_response(items, limit, binding, lambda row: str(row['id']))
    return run_transaction(operation)


def detail(department_id):
    def operation(connection):
        actor = transaction_actor(connection)
        department = accessible(connection, actor, department_id)
        result = basic(connection, actor, department, scope.visible_departments(connection, actor))
        result['members'] = repository.members(connection, department_id, actor['role']=='admin')
        return result
    return run_transaction(operation)


def create(data):
    def operation(connection):
        actor = transaction_actor(connection)
        require_role(actor, 'admin', 'manager')
        parent_id = data.get('parent_department_id')
        if actor['role']=='manager':
            if parent_id is None or parent_id not in scope.managed_departments(connection, actor):
                raise APIError('forbidden', 'Managers may create departments only below their scope',403)
        if parent_id is not None and repository.find(connection,parent_id) is None:
            raise APIError('invalid_parent','Parent department does not exist')
        manager_assignment(connection,actor,data.get('manager_id'))
        department = repository.create(connection,data)
        return basic(connection,actor,department,scope.visible_departments(connection,actor))
    return run_transaction(operation)


def update(department_id,data):
    def operation(connection):
        actor=transaction_actor(connection)
        accessible(connection,actor,department_id,write=True)
        if 'parent_department_id' in data:
            require_role(actor,'admin')
            parent_id=data['parent_department_id']
            if parent_id is not None:
                if repository.find(connection,parent_id) is None:
                    raise APIError('invalid_parent','Parent department does not exist')
                if parent_id in scope_repository.descendants(connection,department_id):
                    raise APIError('hierarchy_cycle','Department hierarchy cannot contain a cycle',409)
        if 'manager_id' in data:
            manager_assignment(connection,actor,data['manager_id'])
        if data.get('is_active') is False:
            require_role(actor,'admin')
            repository.deactivate_branch(connection,scope_repository.descendants(connection,department_id))
        department=repository.update(connection,department_id,data)
        return basic(connection,actor,department,scope.visible_departments(connection,actor))
    return run_transaction(operation)
