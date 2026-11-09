def filtered_query(visible_users, filters, lower, upper, filter_departments):
    """Build one row per visible log; EXISTS filters never multiply totals."""
    clauses, params = [], []
    if visible_users is not None:
        clauses.append('l.user_id=ANY(%s::uuid[])')
        params.append(list(visible_users))
    if lower is not None:
        clauses.append('l.start_time >= %s')
        params.append(lower)
    if upper is not None:
        clauses.append('l.start_time < %s')
        params.append(upper)
    for key in ('project_id', 'user_id'):
        if key in filters:
            clauses.append(f'l.{key}=%s')
            params.append(filters[key])
    for key, column in (('project_status', 'p.status'), ('user_role', 'u.role')):
        if key in filters:
            clauses.append(f'{column}=%s')
            params.append(filters[key])
    if filter_departments is not None:
        clauses.append('EXISTS (SELECT 1 FROM user_departments ud WHERE ud.user_id=l.user_id AND ud.department_id=ANY(%s::uuid[]))')
        params.append(list(filter_departments))
    where = ' AND '.join(clauses) or 'TRUE'
    return f'''
        WITH filtered_logs AS (
            SELECT l.*,p.name AS project_name,u.full_name AS user_name
            FROM logs l JOIN projects p ON p.id=l.project_id JOIN users u ON u.id=l.user_id
            WHERE {where}
        )
    ''', params


def totals(connection, query, params):
    row = connection.execute(query + '''
        SELECT coalesce(sum(spent_time),0) AS spent_time,count(*) AS log_count FROM filtered_logs
    ''',params).fetchone()
    row['spent_time'] = int(row['spent_time'])
    return row


def grouped(connection, query, params, group_by, timezone, output_departments, limit=None, ranked=False):
    params = list(params)
    if group_by in ('day','week','month'):
        key = 'date_trunc(%s, l.start_time AT TIME ZONE %s)::date'
        params.extend([group_by, timezone])
        # Key expression appears only once, in a derived table.
        source = f'(SELECT l.*, {key} AS bucket FROM filtered_logs l) l'
        group_key, label = 'l.bucket', 'l.bucket::text'
    elif group_by == 'project':
        source, group_key, label = 'filtered_logs l', 'l.project_id', 'max(l.project_name)'
    elif group_by == 'user':
        source, group_key, label = 'filtered_logs l', 'l.user_id', 'max(l.user_name)'
    elif group_by == 'department':
        source = 'filtered_logs l LEFT JOIN user_departments ud ON ud.user_id=l.user_id LEFT JOIN departments d ON d.id=ud.department_id'
        group_key, label = 'd.id', "coalesce(max(d.name),'Unassigned')"
    else:
        raise ValueError('Unsupported report grouping')
    condition = ''
    if group_by == 'department' and output_departments is not None:
        condition = 'WHERE d.id=ANY(%s::uuid[])'
        params.append(list(output_departments))
    order = 'spent_time DESC, key NULLS LAST' if ranked else 'key NULLS LAST'
    suffix = ''
    if limit is not None:
        suffix = ' LIMIT %s'
        params.append(limit)
    rows = connection.execute(query + f'''
        SELECT {group_key}::text AS key, {label} AS label,
               coalesce(sum(l.spent_time),0) AS spent_time,count(*) AS log_count
        FROM {source} {condition} GROUP BY {group_key} ORDER BY {order} {suffix}
    ''', params).fetchall()
    for row in rows:
        row['spent_time'] = int(row['spent_time'])
    return rows
