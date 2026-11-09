def lock_user(connection, user_id, *, shared=False):
    mode = 'SHARE' if shared else 'UPDATE'
    return connection.execute(f'SELECT * FROM users WHERE id=%s FOR {mode}', (user_id,)).fetchone()


def set_path(connection, user_id, path):
    connection.execute('UPDATE users SET profile_img=%s WHERE id=%s', (path, user_id))
