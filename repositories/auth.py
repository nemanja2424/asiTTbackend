def find_by_email(connection, email):
    return connection.execute(
        'SELECT * FROM users WHERE lower(email) = lower(%s)', (email,)).fetchone()


def find_by_id(connection, user_id, lock=False):
    query = 'SELECT * FROM users WHERE id = %s'
    if lock:
        query += ' FOR UPDATE'
    return connection.execute(query, (user_id,)).fetchone()


def departments(connection, user_id):
    return connection.execute('''
        SELECT d.id, d.name FROM departments d
        JOIN user_departments ud ON ud.department_id = d.id
        WHERE ud.user_id = %s ORDER BY d.name, d.id
    ''', (user_id,)).fetchall()


def touch_activity(connection, user_id, force=False):
    connection.execute('''
        UPDATE users SET last_active_at = statement_timestamp()
        WHERE id = %s AND (%s OR last_active_at IS NULL
            OR last_active_at <= statement_timestamp() - interval '5 minutes')
    ''', (user_id, force))


def update_password(connection, user_id, password_hash):
    connection.execute('UPDATE users SET password_hash = %s WHERE id = %s',
                       (password_hash, user_id))
