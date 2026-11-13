def create(connection, user_id, data):
    return connection.execute('''
        INSERT INTO logs(user_id,project_id,task_id,start_time,end_time,spent_time,note)
        VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *
    ''', (user_id,data['project_id'],data.get('task_id'),data['start_time'],data['end_time'],data['spent_time'],data.get('note'))).fetchone()


def find(connection, log_id, visible_users):
    clauses, params = ['id=%s'], [log_id]
    if visible_users is not None:
        clauses.append('user_id=ANY(%s::uuid[])')
        params.append(list(visible_users))
    return connection.execute(f"SELECT * FROM logs WHERE {' AND '.join(clauses)}",params).fetchone()


def list_logs(connection, visible_users, filters, lower, upper, after, limit):
    clauses, params = [], []
    if visible_users is not None:
        clauses.append('l.user_id=ANY(%s::uuid[])')
        params.append(list(visible_users))
    for field in ('user_id','project_id'):
        if field in filters:
            clauses.append(f'l.{field}=%s')
            params.append(filters[field])
    if 'department_id' in filters:
        clauses.append('EXISTS (SELECT 1 FROM user_departments ud WHERE ud.user_id=l.user_id AND ud.department_id=%s)')
        params.append(filters['department_id'])
    for key, comparator in (('min_spent_time','>='),('max_spent_time','<=')):
        if key in filters:
            clauses.append(f'l.spent_time {comparator} %s')
            params.append(filters[key])
    if lower is not None:
        clauses.append('l.start_time >= %s')
        params.append(lower)
    if upper is not None:
        clauses.append('l.start_time < %s')
        params.append(upper)
    if after is not None:
        clauses.append('l.id > %s')
        params.append(after)
    where = ' AND '.join(clauses) or 'TRUE'
    params.append(limit+1)
    return connection.execute(f'SELECT l.* FROM logs l WHERE {where} ORDER BY l.id LIMIT %s',params).fetchall()


def delete(connection,log_id):
    connection.execute('DELETE FROM logs WHERE id=%s',(log_id,))
