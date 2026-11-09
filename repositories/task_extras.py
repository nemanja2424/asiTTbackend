"""Queries for links and notifications; no physical file operations."""


def attachments(connection, task_id, project_id, after, limit):
    clause = 'AND a.id>%s' if after else ''
    params = [task_id, project_id] + ([after] if after else []) + [limit + 1]
    return connection.execute(f'''SELECT a.id,a.task_id,a.resource_id,a.added_by,a.created_at,
        u.full_name AS added_by_name,f.original_name AS name,f.size_bytes,f.mime_type,f.folder_id
        FROM task_attachments a JOIN resource_files f ON f.id=a.resource_id
        JOIN resource_libraries l ON l.id=f.library_id
        JOIN users u ON u.id=a.added_by
        WHERE a.task_id=%s AND l.project_id=%s AND f.deleted_at IS NULL {clause} ORDER BY a.id LIMIT %s''', params).fetchall()


def attachment(connection, task_id, attachment_id):
    return connection.execute('SELECT * FROM task_attachments WHERE task_id=%s AND id=%s', (task_id, attachment_id)).fetchone()


def resource(connection, project_id, resource_id):
    return connection.execute('''SELECT f.* FROM resource_files f JOIN resource_libraries l ON l.id=f.library_id
        WHERE l.project_id=%s AND f.id=%s AND f.deleted_at IS NULL''', (project_id, resource_id)).fetchone()


def link(connection, task_id, resource_id, actor_id):
    return connection.execute('''INSERT INTO task_attachments(task_id,resource_id,added_by)
        VALUES (%s,%s,%s) RETURNING id''', (task_id, resource_id, actor_id)).fetchone()['id']


def unlink(connection, attachment_id):
    connection.execute('DELETE FROM task_attachments WHERE id=%s', (attachment_id,))


def notify(connection, user_id, task_id, actor_id, kind, title, message, key):
    connection.execute('''INSERT INTO notifications(user_id,task_id,actor_id,type,title,message,dedupe_key)
        SELECT id,%s,%s,%s,%s,%s,%s FROM users WHERE id=%s AND is_active
        ON CONFLICT (user_id,dedupe_key) DO NOTHING''', (task_id, actor_id, kind, title, message, key, user_id))


def due_candidates(connection, visible, actor, zone):
    return connection.execute('''WITH candidates AS (
        SELECT t.id,t.due_date,((t.due_date + 1)::timestamp AT TIME ZONE %s) AS deadline
        FROM tasks t JOIN projects p ON p.id=t.project_id
        WHERE (t.project_id=ANY(%s::uuid[]) OR (%s AND t.assigned_to=%s))
          AND t.due_date IS NOT NULL AND t.due_date <= ((statement_timestamp() AT TIME ZONE %s)::date + 1)
          AND t.status<>'completed' AND p.archived_at IS NULL AND p.status<>'finished'
          AND (t.assigned_to=%s OR t.created_by=%s OR %s='manager')
    ), due AS (
        SELECT c.*, CASE WHEN statement_timestamp()>=c.deadline THEN 'overdue' ELSE 'due_soon' END AS kind
        FROM candidates c WHERE c.deadline <= statement_timestamp()+interval '24 hours'
    ) SELECT d.id,d.due_date,d.kind FROM due d
        WHERE NOT EXISTS (SELECT 1 FROM notifications n WHERE n.user_id=%s
          AND n.dedupe_key='due:'||d.id::text||':'||to_char(d.due_date,'YYYY-MM-DD')||':'||d.kind)''',
        (zone, list(visible), actor['role']=='worker', actor['id'], zone,
         actor['id'], actor['id'], actor['role'], actor['id'])).fetchall()


def notifications(connection, actor, visible, read_filter, after, limit):
    where = ['n.user_id=%s', '(t.project_id=ANY(%s::uuid[]) OR (%s AND t.assigned_to=%s))']
    params = [actor['id'], list(visible), actor['role']=='worker', actor['id']]
    if read_filter is not None:
        where.append('n.is_read=%s'); params.append(read_filter)
    if after:
        where.append('(n.created_at,n.id)<(%s,%s)'); params.extend(after)
    params.append(limit + 1)
    return connection.execute(f'''SELECT n.id,n.task_id,n.actor_id,n.type,n.title,n.message,n.is_read,n.created_at,n.read_at,
        t.title AS task_title FROM notifications n JOIN tasks t ON t.id=n.task_id
        WHERE {' AND '.join(where)} ORDER BY n.created_at DESC,n.id DESC LIMIT %s''', params).fetchall()


def unread_count(connection, actor, visible):
    return connection.execute('''SELECT count(*) AS total FROM notifications n JOIN tasks t ON t.id=n.task_id
        WHERE n.user_id=%s AND NOT n.is_read AND (t.project_id=ANY(%s::uuid[]) OR (%s AND t.assigned_to=%s))''',
        (actor['id'], list(visible), actor['role']=='worker', actor['id'])).fetchone()['total']


def mark_read(connection, actor, visible, notification_id=None):
    where = ['n.user_id=%s', 'NOT n.is_read', '(t.project_id=ANY(%s::uuid[]) OR (%s AND t.assigned_to=%s))']
    params = [actor['id'], list(visible), actor['role']=='worker', actor['id']]
    if notification_id is not None:
        where.append('n.id=%s'); params.append(notification_id)
    return connection.execute(f'''UPDATE notifications n SET is_read=TRUE,read_at=statement_timestamp()
        FROM tasks t WHERE t.id=n.task_id AND {' AND '.join(where)}''', params).rowcount
