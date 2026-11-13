"""Parameterized task queries; permissions are provided by the service."""
from .projects import EFFECTIVE_CTE

FIELDS = '''t.*, p.name AS project_name, p.status AS project_status, p.archived_at AS project_archived_at,
            a.full_name AS assigned_name, c.full_name AS creator_name'''
JOIN = '''FROM tasks t JOIN projects p ON p.id=t.project_id
          JOIN users c ON c.id=t.created_by LEFT JOIN users a ON a.id=t.assigned_to'''


def find(connection, task_id, lock=False):
    lock_clause = ' FOR KEY SHARE OF t' if lock else ''
    return connection.execute(f'SELECT {FIELDS} {JOIN} WHERE t.id=%s{lock_clause}', (task_id,)).fetchone()


def listing(connection, visible, own, filters, after, limit):
    clauses = ['(t.project_id=ANY(%s::uuid[]) OR (%s::uuid IS NOT NULL AND t.assigned_to=%s))']
    params = [list(visible), own, own]
    if after:
        clauses.append('t.id > %s'); params.append(after)
    if 'task_id' in filters:
        clauses.append('t.id=%s'); params.append(filters['task_id'])
    if 'q' in filters:
        clauses.append('position(lower(%s) in lower(t.title)) > 0'); params.append(filters['q'])
    if filters.get('work_loggable'):
        clauses.append("p.status='active' AND p.archived_at IS NULL")
        clauses.append('EXISTS (SELECT 1 FROM effective_participants e WHERE e.project_id=t.project_id AND e.user_id=%s)')
        params.append(filters['work_loggable_actor'])
    for key in ('project_id', 'assigned_to', 'status', 'priority'):
        if key in filters:
            clauses.append(f't.{key}=%s'); params.append(filters[key])
    for key, operator in (('due_from', '>='), ('due_to', '<=')):
        if key in filters:
            clauses.append(f't.due_date {operator} %s'); params.append(filters[key])
    params.append(limit + 1)
    prefix = EFFECTIVE_CTE if filters.get('work_loggable') else ''
    return connection.execute(prefix + f'SELECT {FIELDS} {JOIN} WHERE {" AND ".join(clauses)} ORDER BY t.id LIMIT %s', params).fetchall()


def create(connection, data, actor_id):
    row = connection.execute('''INSERT INTO tasks(project_id,title,description,assigned_to,created_by,status,priority,due_date,completed_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,CASE WHEN %s='completed' THEN statement_timestamp() ELSE NULL END)
        RETURNING id''', (data['project_id'], data['title'], data.get('description'), data.get('assigned_to'), actor_id,
        data.get('status','pending'), data.get('priority','normal'), data.get('due_date'), data.get('status','pending'))).fetchone()
    return find(connection, row['id'])


def update(connection, task_id, data):
    allowed = ('title','description','assigned_to','status','priority','due_date')
    pairs, params = [], []
    for key in allowed:
        if key in data:
            pairs.append(f'{key}=%s'); params.append(data[key])
    if 'status' in data:
        pairs.append("completed_at=CASE WHEN %s='completed' THEN COALESCE(completed_at,statement_timestamp()) ELSE NULL END")
        params.append(data['status'])
    connection.execute(f'UPDATE tasks SET {", ".join(pairs)} WHERE id=%s', [*params, task_id])
    return find(connection, task_id)


def delete(connection, task_id):
    connection.execute('DELETE FROM tasks WHERE id=%s', (task_id,))


def activity(connection, task_id, actor_id, event_type, old=None, new=None, reason=None):
    return connection.execute('''INSERT INTO task_activity(task_id,actor_id,event_type,old_value,new_value,reason)
                          VALUES (%s,%s,%s,%s,%s,%s) RETURNING id''',
        (task_id, actor_id, event_type, None if old is None else str(old), None if new is None else str(new), reason)).fetchone()['id']


def add_comment(connection, task_id, author_id, content):
    row = connection.execute('''INSERT INTO task_comments(task_id,author_id,content)
        VALUES (%s,%s,%s) RETURNING id''', (task_id, author_id, content)).fetchone()
    return connection.execute('''SELECT c.*,u.full_name AS author_name,u.profile_img AS author_profile_img
        FROM task_comments c JOIN users u ON u.id=c.author_id WHERE c.id=%s''', (row['id'],)).fetchone()


def comment_rows(connection, task_id, after, limit):
    clause, params = '', [task_id]
    if after is not None:
        clause = 'AND (c.created_at,c.id)>(%s,%s)'
        params.extend(after)
    params.append(limit + 1)
    return connection.execute(f'''SELECT c.*,u.full_name AS author_name,u.profile_img AS author_profile_img
        FROM task_comments c JOIN users u ON u.id=c.author_id WHERE c.task_id=%s {clause}
        ORDER BY c.created_at,c.id LIMIT %s''', params).fetchall()


def activity_rows(connection, task_id, after, limit):
    clause, params = '', [task_id]
    if after is not None:
        clause = 'AND (a.created_at,a.id)>(%s,%s)'
        params.extend(after)
    params.append(limit + 1)
    return connection.execute(f'''SELECT a.*,u.full_name AS actor_name,
        ou.full_name AS old_assignee_name, nu.full_name AS new_assignee_name
        FROM task_activity a JOIN users u ON u.id=a.actor_id
        LEFT JOIN users ou ON a.event_type='assignee_changed' AND ou.id::text=a.old_value
        LEFT JOIN users nu ON a.event_type='assignee_changed' AND nu.id::text=a.new_value
        WHERE a.task_id=%s {clause} ORDER BY a.created_at,a.id LIMIT %s''', params).fetchall()
