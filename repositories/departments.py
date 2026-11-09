def find(connection, department_id):
    return connection.execute('SELECT * FROM departments WHERE id=%s', (department_id,)).fetchone()


def list_departments(connection, visible, active, after=None, limit=None):
    clauses, params = [], []
    if visible is not None:
        clauses.append('d.id = ANY(%s::uuid[])')
        params.append(list(visible))
    if active is not None:
        clauses.append('d.is_active = %s')
        params.append(active)
    if after is not None:
        clauses.append('d.id > %s')
        params.append(after)
    where = ' AND '.join(clauses) or 'TRUE'
    suffix = ''
    if limit is not None:
        suffix = ' LIMIT %s'
        params.append(limit + 1)
    return connection.execute(f'''
        SELECT d.*,
          (SELECT count(*) FROM user_departments ud JOIN users u ON u.id=ud.user_id
           WHERE ud.department_id=d.id AND u.is_active) AS employee_count,
          (SELECT count(*) FROM departments child WHERE child.parent_department_id=d.id
             AND child.is_active) AS subdepartment_count
        FROM departments d WHERE {where} ORDER BY d.id {suffix}
    ''', params).fetchall()


def members(connection, department_id, admin):
    return connection.execute('''
        SELECT u.id,u.email,u.full_name,u.role,u.is_active,u.profile_img FROM users u
        JOIN user_departments ud ON ud.user_id=u.id
        WHERE ud.department_id=%s AND (%s OR u.is_active) ORDER BY u.full_name,u.id
    ''', (department_id, admin)).fetchall()


def create(connection, data):
    return connection.execute('''
        INSERT INTO departments(name,description,parent_department_id,manager_id)
        VALUES (%s,%s,%s,%s) RETURNING *
    ''', (data['name'], data.get('description'), data.get('parent_department_id'),
          data.get('manager_id'))).fetchone()


def update(connection, department_id, data):
    allowed = {'name', 'description', 'is_active', 'manager_id', 'parent_department_id'}
    values = {key: value for key,value in data.items() if key in allowed}
    if not values:
        return find(connection, department_id)
    assignments = ', '.join(f'{key}=%s' for key in values)
    return connection.execute(f'UPDATE departments SET {assignments} WHERE id=%s RETURNING *',
                              [*values.values(),department_id]).fetchone()


def deactivate_branch(connection, ids):
    connection.execute('UPDATE departments SET is_active=FALSE WHERE id=ANY(%s::uuid[])', (list(ids),))
