def manager_departments(connection, manager_id):
    rows = connection.execute('''
        WITH RECURSIVE managed AS (
            SELECT id FROM departments WHERE manager_id = %s
            UNION
            SELECT d.id FROM departments d JOIN managed m ON d.parent_department_id = m.id
        ) SELECT id FROM managed
    ''', (manager_id,)).fetchall()
    return {row['id'] for row in rows}


def memberships(connection, user_id):
    return {row['department_id'] for row in connection.execute(
        'SELECT department_id FROM user_departments WHERE user_id = %s', (user_id,)).fetchall()}


def descendants(connection, department_id):
    return {row['id'] for row in connection.execute('''
        WITH RECURSIVE branch AS (
            SELECT id FROM departments WHERE id = %s
            UNION
            SELECT d.id FROM departments d JOIN branch b ON d.parent_department_id = b.id
        ) SELECT id FROM branch
    ''', (department_id,)).fetchall()}


def users_in_departments(connection, department_ids):
    """Read scope includes every role and inactive historical members."""
    return {row['user_id'] for row in connection.execute('''
        SELECT DISTINCT user_id FROM user_departments WHERE department_id=ANY(%s::uuid[])
    ''', (list(department_ids),)).fetchall()}
