EFFECTIVE_CTE = '''
    WITH RECURSIVE project_department_scope(project_id, department_id) AS (
        SELECT project_id, department_id FROM project_departments
        UNION
        SELECT s.project_id, d.id FROM project_department_scope s
        JOIN departments d ON d.parent_department_id=s.department_id
    ), effective_participants AS (
        SELECT project_id,user_id FROM project_users
        UNION
        SELECT s.project_id,ud.user_id FROM project_department_scope s
        JOIN user_departments ud ON ud.department_id=s.department_id
    )
'''


def permission_ids(connection, actor, managed):
    if actor['role'] == 'admin':
        ids = {row['id'] for row in connection.execute('SELECT id FROM projects').fetchall()}
        return ids, ids
    if actor['role'] == 'manager':
        rows = connection.execute(EFFECTIVE_CTE + '''
            SELECT p.id FROM projects p WHERE
              EXISTS (SELECT 1 FROM project_department_scope s
                      WHERE s.project_id=p.id AND s.department_id=ANY(%s::uuid[]))
              OR EXISTS (
                  SELECT 1 FROM project_users pu JOIN users u ON u.id=pu.user_id
                  WHERE pu.project_id=p.id AND u.role='worker'
                    AND EXISTS (SELECT 1 FROM user_departments ud WHERE ud.user_id=u.id)
                    AND NOT EXISTS (SELECT 1 FROM user_departments ud WHERE ud.user_id=u.id
                                    AND NOT (ud.department_id=ANY(%s::uuid[])))
              )
        ''', (list(managed), list(managed))).fetchall()
        ids = {row['id'] for row in rows}
        return ids, ids
    rows = connection.execute(EFFECTIVE_CTE + '''
        SELECT project_id AS id FROM effective_participants WHERE user_id=%s
    ''', (actor['id'],)).fetchall()
    return {row['id'] for row in rows}, set()


def find(connection, project_id):
    return connection.execute('SELECT * FROM projects WHERE id=%s', (project_id,)).fetchone()


def list_projects(connection, visible, filters, after, limit):
    clauses, params = ['p.id=ANY(%s::uuid[])'], [list(visible)]
    if after is not None:
        clauses.append('p.id > %s')
        params.append(after)
    if 'status' in filters:
        clauses.append('p.status=%s')
        params.append(filters['status'])
    if 'search' in filters:
        clauses.append('strpos(lower(p.name),lower(%s)) > 0')
        params.append(filters['search'])
    if 'archived' in filters:
        clauses.append('p.archived_at IS NOT NULL' if filters['archived'] else 'p.archived_at IS NULL')
    for field in ('start_date', 'end_date'):
        for suffix, comparator in (('_from', '>='), ('_to', '<=')):
            if field + suffix in filters:
                clauses.append(f'p.{field} {comparator} %s')
                params.append(filters[field + suffix])
    if 'department_id' in filters:
        clauses.append('EXISTS (SELECT 1 FROM project_department_scope s WHERE s.project_id=p.id AND s.department_id=%s)')
        params.append(filters['department_id'])
    if 'user_id' in filters:
        clauses.append('EXISTS (SELECT 1 FROM effective_participants e WHERE e.project_id=p.id AND e.user_id=%s)')
        params.append(filters['user_id'])
    params.append(limit + 1)
    return connection.execute(EFFECTIVE_CTE + f'''
        SELECT p.* FROM projects p WHERE {' AND '.join(clauses)} ORDER BY p.id LIMIT %s
    ''', params).fetchall()


def create(connection, data):
    return connection.execute('''
        INSERT INTO projects(name,description,status,start_date,end_date)
        VALUES (%s,%s,%s,%s,%s) RETURNING *
    ''', (data['name'], data.get('description'), data['status'], data['start_date'], data.get('end_date'))).fetchone()


def update(connection, project_id, data):
    allowed = {'name', 'description', 'status', 'start_date', 'end_date', 'archived_at'}
    values = {key: value for key, value in data.items() if key in allowed}
    assignments = ', '.join(f'{key}=%s' for key in values)
    return connection.execute(f'UPDATE projects SET {assignments} WHERE id=%s RETURNING *',
                              [*values.values(), project_id]).fetchone()


def assignment_ids(connection, project_id, kind):
    table, column = ('project_departments', 'department_id') if kind == 'departments' else ('project_users', 'user_id')
    return {row[column] for row in connection.execute(
        f'SELECT {column} FROM {table} WHERE project_id=%s', (project_id,)).fetchall()}


def replace_assignments(connection, project_id, kind, ids):
    table, column = ('project_departments', 'department_id') if kind == 'departments' else ('project_users', 'user_id')
    connection.execute(f'DELETE FROM {table} WHERE project_id=%s', (project_id,))
    for entity_id in ids:
        connection.execute(f'INSERT INTO {table}(project_id,{column}) VALUES (%s,%s)', (project_id, entity_id))


def assigned_departments(connection, project_id):
    return connection.execute('''
        SELECT d.id,d.name,d.is_active FROM departments d JOIN project_departments pd ON pd.department_id=d.id
        WHERE pd.project_id=%s ORDER BY d.id
    ''', (project_id,)).fetchall()


def assigned_users(connection, project_id, admin):
    return connection.execute('''
        SELECT u.* FROM users u JOIN project_users pu ON pu.user_id=u.id
        WHERE pu.project_id=%s AND (%s OR u.is_active) ORDER BY u.id
    ''', (project_id, admin)).fetchall()


def participants(connection, project_id, admin, after=None, limit=None):
    params = [project_id, project_id, project_id, admin]
    condition = ''
    if after is not None:
        condition = ' AND u.id > %s'
        params.append(after)
    suffix = ''
    if limit is not None:
        suffix = ' LIMIT %s'
        params.append(limit + 1)
    return connection.execute(EFFECTIVE_CTE + f'''
        SELECT u.*,
          EXISTS (SELECT 1 FROM project_users pu WHERE pu.user_id=u.id AND pu.project_id=%s) AS assigned_directly,
          EXISTS (SELECT 1 FROM project_department_scope s JOIN user_departments ud ON ud.department_id=s.department_id
                  WHERE s.project_id=%s AND ud.user_id=u.id) AS assigned_by_department
        FROM users u JOIN effective_participants e ON e.user_id=u.id
        WHERE e.project_id=%s AND (%s OR u.is_active) {condition} ORDER BY u.id {suffix}
    ''', params).fetchall()


def total_time(connection, project_id):
    return int(connection.execute('SELECT coalesce(sum(spent_time),0) AS total FROM logs WHERE project_id=%s',
                                  (project_id,)).fetchone()['total'])


def active_entities(connection, kind, ids):
    table = 'departments' if kind == 'departments' else 'users'
    return connection.execute(f'SELECT * FROM {table} WHERE id=ANY(%s::uuid[]) AND is_active', (list(ids),)).fetchall()


def is_effective_participant(connection, project_id, user_id):
    return connection.execute(EFFECTIVE_CTE + '''
        SELECT 1 FROM effective_participants WHERE project_id=%s AND user_id=%s
    ''', (project_id, user_id)).fetchone() is not None
