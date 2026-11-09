from .projects import EFFECTIVE_CTE


def active_user_count(connection,visible_users):
    condition,params = '',[]
    if visible_users is not None:
        condition = 'AND id=ANY(%s::uuid[])'
        params.append(list(visible_users))
    return connection.execute(f'SELECT count(*) AS count FROM users WHERE is_active {condition}',params).fetchone()['count']


def active_project_count(connection):
    return connection.execute("SELECT count(*) AS count FROM projects WHERE status='active' AND archived_at IS NULL").fetchone()['count']


def active_projects(connection,actor,visible_projects=None):
    clauses,params = ["p.status='active'",'p.archived_at IS NULL'],[]
    if actor['role']=='worker':
        clauses.append('EXISTS (SELECT 1 FROM effective_participants ep WHERE ep.project_id=p.id AND ep.user_id=%s)')
        params.append(actor['id'])
    elif visible_projects is not None:
        clauses.append('p.id=ANY(%s::uuid[])')
        params.append(list(visible_projects))
    return connection.execute(EFFECTIVE_CTE + f'''
        SELECT p.id,p.name,p.description,p.status,p.start_date,p.end_date,p.archived_at
        FROM projects p WHERE {' AND '.join(clauses)} ORDER BY p.name,p.id
    ''',params).fetchall()


def recent_logs(connection,user_id):
    return connection.execute('''
        SELECT * FROM logs WHERE user_id=%s ORDER BY start_time DESC,id DESC LIMIT 5
    ''',(user_id,)).fetchall()
