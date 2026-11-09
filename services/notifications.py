"""Per-user notifications, generated in transactions and filtered by current access."""
from flask import current_app

from ..authorization import transaction_actor
from ..db import run_transaction
from ..errors import APIError
from ..pagination import page_request, page_response
from ..repositories import task_extras as repo
from ..validation import timestamp, uuid4
from . import projects

TITLES = {'assigned':('Novi zadatak','Zadatak vam je dodeljen.'),
          'reassigned':('Promenjena dodela','Zadatak je dodeljen drugom korisniku ili je dodela uklonjena.'),
          'comment':('Novi komentar','Dodat je komentar na zadatak.'),
          'reopened':('Vraćeno na doradu','Zadatak je vraćen na doradu.'),
          'due_changed':('Promenjen rok','Promenjen je rok zadatka.'),
          'due_soon':('Rok uskoro ističe','Rok zadatka ističe u naredna 24 sata.'),
          'overdue':('Rok je istekao','Zadatak nije završen pre isteka roka.')}


def event(connection, task, actor, event_id, kind, extra=(), include_assignee=True, include_observers=True):
    recipients = set(extra)
    if include_assignee and task.get('assigned_to'): recipients.add(task['assigned_to'])
    if include_observers:
        if task.get('created_by'): recipients.add(task['created_by'])
        managers = connection.execute("SELECT id,role FROM users WHERE role='manager' AND is_active").fetchall()
        for manager in managers:
            _, manageable = projects.permissions(connection, manager)
            if task['project_id'] in manageable: recipients.add(manager['id'])
    if not include_assignee and task.get('assigned_to'):
        recipients.discard(task['assigned_to'])
    recipients.discard(actor['id'])
    for user_id in recipients:
        title, message = TITLES[kind]
        if kind == 'assigned' and user_id != task.get('assigned_to'):
            title, message = 'Promenjena dodela', 'Zadatak je dodeljen korisniku.'
        repo.notify(connection, user_id, task['id'], actor['id'], kind, title, message, f'event:{event_id}:{kind}')


def generate_due(connection, actor, visible):
    for task in repo.due_candidates(connection, visible, actor, current_app.config['APP_TIMEZONE']):
        kind = task['kind']
        title, message = TITLES[kind]
        key = f"due:{task['id']}:{task['due_date'].isoformat()}:{kind}"
        repo.notify(connection, actor['id'], task['id'], None, kind, title, message, key)


def listing(args, read_filter):
    def operation(connection):
        actor = transaction_actor(connection)
        visible, _ = projects.permissions(connection, actor)
        generate_due(connection, actor, visible)
        binding = {'endpoint':'notifications','actor':str(actor['id']),'role':actor['role'],'is_read':read_filter}
        limit, after = page_request(args, binding)
        if after is not None:
            if not isinstance(after, list) or len(after) != 2: raise APIError('invalid_cursor', 'Invalid cursor')
            after = (timestamp(after[0], 'cursor time'), uuid4(after[1], 'cursor id'))
        rows = repo.notifications(connection, actor, visible, read_filter, after, limit)
        return page_response(rows, limit, binding, lambda row:[row['created_at'].isoformat(),str(row['id'])])
    return run_transaction(operation)


def count():
    def operation(connection):
        actor = transaction_actor(connection)
        visible, _ = projects.permissions(connection, actor)
        generate_due(connection, actor, visible)
        return {'count':repo.unread_count(connection, actor, visible)}
    return run_transaction(operation)


def read(notification_id=None):
    def operation(connection):
        actor = transaction_actor(connection)
        visible, _ = projects.permissions(connection, actor)
        if notification_id is not None:
            available = connection.execute('''SELECT n.id FROM notifications n JOIN tasks t ON t.id=n.task_id
                WHERE n.id=%s AND n.user_id=%s AND (t.project_id=ANY(%s::uuid[]) OR (%s AND t.assigned_to=%s))''',
                (notification_id, actor['id'], list(visible), actor['role']=='worker', actor['id'])).fetchone()
            if not available: raise APIError('not_found', 'Notification not found', 404)
        count = repo.mark_read(connection, actor, visible, notification_id)
        return {'updated':count}
    return run_transaction(operation)


def scheduled_due_check():
    """Operator-scheduled job; each user is re-read in a separate transaction."""
    ids = run_transaction(lambda connection: [row['id'] for row in connection.execute(
        'SELECT id FROM users WHERE is_active ORDER BY id').fetchall()])
    for user_id in ids:
        def operation(connection):
            actor = connection.execute('SELECT id,role,is_active FROM users WHERE id=%s', (user_id,)).fetchone()
            if actor is None or not actor['is_active']:
                return
            visible, _ = projects.permissions(connection, actor)
            generate_due(connection, actor, visible)
        run_transaction(operation)
    return len(ids)
