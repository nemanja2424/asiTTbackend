from .auth import find_by_id


def existing_departments(connection, ids):
    return connection.execute('SELECT id FROM departments WHERE id = ANY(%s::uuid[])', (ids,)).fetchall()


def list_users(connection, filters, after, limit, admin):
    clauses, params = [], []
    if not admin:
        clauses.append('u.is_active = TRUE')
    if filters.get('search'):
        clauses.append('(strpos(lower(u.full_name), lower(%s)) > 0 OR strpos(lower(u.email), lower(%s)) > 0)')
        params.extend([filters['search'], filters['search']])
    for key in ('role', 'is_active'):
        if key in filters:
            clauses.append(f'u.{key} = %s')
            params.append(filters[key])
    if filters.get('department_id'):
        clauses.append('EXISTS (SELECT 1 FROM user_departments ud WHERE ud.user_id=u.id AND ud.department_id=%s)')
        params.append(filters['department_id'])
    if after:
        clauses.append('u.id > %s')
        params.append(after)
    params.append(limit + 1)
    where = ' AND '.join(clauses) or 'TRUE'
    return connection.execute(f'SELECT u.* FROM users u WHERE {where} ORDER BY u.id LIMIT %s', params).fetchall()


def create(connection, data):
    return connection.execute('''
        INSERT INTO users(email, password_hash, full_name, role)
        VALUES (%s, %s, %s, %s) RETURNING *
    ''', (data['email'], data['password_hash'], data['full_name'], data['role'])).fetchone()


def update(connection, user_id, data):
    allowed = {'email', 'full_name', 'role', 'is_active'}
    values = {key: value for key, value in data.items() if key in allowed}
    if not values:
        return find_by_id(connection, user_id)
    assignments = ', '.join(f'{key} = %s' for key in values)
    return connection.execute(f'UPDATE users SET {assignments} WHERE id = %s RETURNING *',
                              [*values.values(), user_id]).fetchone()


def replace_departments(connection, user_id, department_ids):
    connection.execute('DELETE FROM user_departments WHERE user_id = %s', (user_id,))
    for department_id in department_ids:
        connection.execute('INSERT INTO user_departments(user_id, department_id) VALUES (%s,%s)',
                           (user_id, department_id))


def clear_manager_assignments(connection, user_id):
    connection.execute('UPDATE departments SET manager_id = NULL WHERE manager_id = %s', (user_id,))


def deactivate(connection, user_id):
    clear_manager_assignments(connection, user_id)
    connection.execute('DELETE FROM project_users WHERE user_id = %s', (user_id,))


def details(connection, user_id):
    projects = connection.execute('''
        WITH RECURSIVE memberships AS (
            SELECT department_id AS id FROM user_departments WHERE user_id = %s
            UNION
            SELECT d.parent_department_id FROM departments d JOIN memberships m ON d.id=m.id
            WHERE d.parent_department_id IS NOT NULL
        ) SELECT p.id,p.name,p.status,p.start_date,p.end_date,p.archived_at FROM projects p
        WHERE EXISTS (SELECT 1 FROM project_users pu WHERE pu.project_id=p.id AND pu.user_id=%s)
        OR EXISTS (SELECT 1 FROM project_departments pd JOIN memberships m ON m.id=pd.department_id
                   WHERE pd.project_id=p.id) ORDER BY p.id
    ''', (user_id, user_id)).fetchall()
    stats = connection.execute('''
        SELECT count(*) AS log_count, coalesce(sum(spent_time),0) AS spent_time
        FROM logs WHERE user_id = %s
    ''', (user_id,)).fetchone()
    stats['spent_time'] = int(stats['spent_time'])
    stats['by_project'] = connection.execute('''
        SELECT p.id AS project_id, p.name AS project_name,
               coalesce(sum(l.spent_time),0) AS spent_time, count(*) AS log_count
        FROM logs l JOIN projects p ON p.id=l.project_id
        WHERE l.user_id=%s GROUP BY p.id,p.name ORDER BY p.id
    ''', (user_id,)).fetchall()
    for row in stats['by_project']:
        row['spent_time'] = int(row['spent_time'])
    return {'projects': projects, 'time_statistics': stats}
