from ..authorization import require_role, transaction_actor
from ..db import run_transaction
from ..errors import APIError
from ..pagination import page_request, page_response
from ..repositories import projects as project_repository, tasks as repository
from ..validation import timestamp, uuid4
from . import notifications, projects


def editable(project):
    if project['archived_at'] is not None or project['status'] == 'finished':
        raise APIError('project_unavailable', 'Tasks cannot be changed in finished or archived projects', 409)


def assignment(connection, project_id, user_id):
    if user_id is not None and (not project_repository.active_entities(connection, 'users', {user_id}) or
            not project_repository.is_effective_participant(connection, project_id, user_id)):
        raise APIError('invalid_assignments', 'Assignee must be an active project participant')


def task_access(connection, actor, task_id, write=False):
    row = repository.find(connection, task_id)
    visible, manageable = projects.permissions(connection, actor)
    if row is None or (row['project_id'] not in visible and not (actor['role']=='worker' and row['assigned_to']==actor['id'])):
        raise APIError('not_found', 'Task not found', 404)
    can_manage = row['project_id'] in manageable and actor['role'] in ('admin', 'manager')
    if write and not can_manage and not (actor['role']=='worker' and row['assigned_to']==actor['id']):
        raise APIError('forbidden', 'You cannot change this task', 403)
    return row, can_manage, row['project_id'] in visible


def payload(row, actor, can_manage, project_visible=True):
    data = dict(row)
    writable = data['project_archived_at'] is None and data['project_status'] != 'finished'
    data['can_manage'] = bool(writable and can_manage)
    data['can_change_status'] = bool(writable and data['status'] != 'completed' and (can_manage or actor['role']=='worker' and data['assigned_to']==actor['id']))
    data['can_reopen'] = bool(writable and can_manage and data['status']=='completed')
    data['can_comment'] = bool(writable and project_visible)
    return data


def listing(filters, args):
    def operation(connection):
        actor = transaction_actor(connection)
        visible, manageable = projects.permissions(connection, actor)
        effective = dict(filters)
        if effective.pop('mine', False):
            if 'assigned_to' in effective and effective['assigned_to'] != actor['id']:
                raise APIError('invalid_input', 'mine conflicts with assigned_to')
            effective['assigned_to'] = actor['id']
        binding = {**effective, 'endpoint':'tasks', 'actor':str(actor['id']), 'role':actor['role']}
        limit, after = page_request(args, binding)
        if after is not None: after = uuid4(after, 'cursor position')
        rows = repository.listing(connection, visible, actor['id'] if actor['role']=='worker' else None, effective, after, limit)
        values = [payload(row, actor, row['project_id'] in manageable and actor['role'] in ('admin','manager'), row['project_id'] in visible) for row in rows]
        return page_response(values, limit, binding, lambda row: str(row['id']))
    return run_transaction(operation)


def detail(task_id):
    def operation(connection):
        actor = transaction_actor(connection)
        row, manage, visible = task_access(connection, actor, task_id)
        return payload(row, actor, manage, visible)
    return run_transaction(operation)


def create(data):
    def operation(connection):
        actor = transaction_actor(connection)
        require_role(actor, 'admin', 'manager')
        project = projects.accessible(connection, actor, data['project_id'], write=True)
        editable(project)
        assignment(connection, data['project_id'], data.get('assigned_to'))
        row = repository.create(connection, data, actor['id'])
        repository.activity(connection, row['id'], actor['id'], 'created')
        if row['assigned_to'] is not None:
            event_id = repository.activity(connection, row['id'], actor['id'], 'assignee_changed', new=row['assigned_to'])
            notifications.event(connection, row, actor, event_id, 'assigned')
        if row['status'] == 'completed':
            repository.activity(connection, row['id'], actor['id'], 'completed', new='completed')
        return payload(row, actor, True)
    return run_transaction(operation)


def update(task_id, data):
    def operation(connection):
        actor = transaction_actor(connection)
        row, manage, visible = task_access(connection, actor, task_id, write=True)
        editable({'archived_at':row['project_archived_at'], 'status':row['project_status']})
        if not manage and set(data) != {'status'}:
            raise APIError('forbidden', 'Only the assigned worker may change status', 403)
        if row['status'] == 'completed' and 'status' in data and data['status'] != 'completed':
            raise APIError('reopen_required', 'Completed tasks must be returned for rework with a reason', 409)
        if 'assigned_to' in data:
            assignment(connection, row['project_id'], data['assigned_to'])
        updated = repository.update(connection, task_id, data)
        for field, event in (('title','title_changed'), ('description','description_changed'),
                ('assigned_to','assignee_changed'), ('status','status_changed'),
                ('priority','priority_changed'), ('due_date','due_date_changed')):
            if field not in data or row[field] == updated[field]:
                continue
            if field == 'description':
                repository.activity(connection, task_id, actor['id'], event)
            else:
                kind = 'completed' if field == 'status' and updated['status'] == 'completed' else event
                event_id = repository.activity(connection, task_id, actor['id'], kind, row[field], updated[field])
                if field == 'assigned_to':
                    if updated['assigned_to']:
                        notifications.event(connection, updated, actor, event_id, 'assigned')
                    if row['assigned_to']:
                        notifications.event(connection, updated, actor, event_id, 'reassigned', (row['assigned_to'],),
                                            include_assignee=False, include_observers=not bool(updated['assigned_to']))
                elif field == 'due_date':
                    notifications.event(connection, updated, actor, event_id, 'due_changed')
        return payload(updated, actor, manage, visible)
    return run_transaction(operation)


def delete(task_id):
    def operation(connection):
        actor = transaction_actor(connection)
        row, manage, _ = task_access(connection, actor, task_id, write=True)
        if not manage:
            raise APIError('forbidden', 'You cannot delete this task', 403)
        editable({'archived_at':row['project_archived_at'], 'status':row['project_status']})
        repository.delete(connection, task_id)
        return {'message':'Task deleted'}
    return run_transaction(operation)


def reopen(task_id, reason):
    def operation(connection):
        actor = transaction_actor(connection)
        row, manage, _ = task_access(connection, actor, task_id, write=True)
        if not manage:
            raise APIError('forbidden', 'Only a project manager or administrator can reopen a task', 403)
        editable({'archived_at':row['project_archived_at'], 'status':row['project_status']})
        if row['status'] != 'completed':
            raise APIError('invalid_state', 'Only completed tasks can be returned for rework', 409)
        updated = repository.update(connection, task_id, {'status':'in_progress'})
        event_id = repository.activity(connection, task_id, actor['id'], 'reopened', 'completed', 'in_progress', reason)
        notifications.event(connection, updated, actor, event_id, 'reopened')
        return payload(updated, actor, manage)
    return run_transaction(operation)


def add_comment(task_id, content):
    def operation(connection):
        actor = transaction_actor(connection)
        row, _, visible = task_access(connection, actor, task_id)
        if not visible:
            raise APIError('forbidden', 'You cannot comment without project access', 403)
        editable({'archived_at':row['project_archived_at'], 'status':row['project_status']})
        comment = repository.add_comment(connection, task_id, actor['id'], content)
        event_id = repository.activity(connection, task_id, actor['id'], 'comment_added')
        notifications.event(connection, row, actor, event_id, 'comment')
        return comment
    return run_transaction(operation)


def timeline(task_id, args, kind):
    def operation(connection):
        actor = transaction_actor(connection)
        _, _, visible = task_access(connection, actor, task_id)
        if kind == 'comments' and not visible:
            raise APIError('forbidden', 'You cannot view comments without project access', 403)
        binding = {'endpoint': 'task_' + kind, 'task_id':str(task_id), 'actor':str(actor['id']), 'role':actor['role']}
        limit, after = page_request(args, binding)
        if after is not None:
            if not isinstance(after, list) or len(after) != 2:
                raise APIError('invalid_cursor', 'Cursor position is invalid')
            after = (timestamp(after[0], 'cursor time'), uuid4(after[1], 'cursor id'))
        rows = (repository.comment_rows if kind == 'comments' else repository.activity_rows)(connection, task_id, after, limit)
        return page_response(rows, limit, binding, lambda row:[row['created_at'].isoformat(), str(row['id'])])
    return run_transaction(operation)
