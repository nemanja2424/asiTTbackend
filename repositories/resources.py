def accessible_projects(connection, ids):
    return connection.execute(
        'SELECT id, name FROM projects WHERE id = ANY(%s::uuid[]) ORDER BY name, id',
        (list(ids),)).fetchall()


def accessible_departments(connection, ids):
    if ids is None:
        return connection.execute('SELECT id, name FROM departments ORDER BY name, id').fetchall()
    return connection.execute(
        'SELECT id, name FROM departments WHERE is_active AND id = ANY(%s::uuid[]) ORDER BY name, id',
        (list(ids),)).fetchall()


def library(connection, kind, owner_id):
    column = 'project_id' if kind == 'projects' else 'department_id'
    connection.execute(f'INSERT INTO resource_libraries ({column}) VALUES (%s) ON CONFLICT ({column}) DO NOTHING', (owner_id,))
    return connection.execute(f'SELECT id FROM resource_libraries WHERE {column}=%s FOR UPDATE', (owner_id,)).fetchone()['id']


def rows(connection, library_id):
    folders = connection.execute('''SELECT f.*,u.full_name AS created_by_name FROM resource_folders f
        JOIN users u ON u.id=f.created_by WHERE f.library_id=%s''', (library_id,)).fetchall()
    files = connection.execute('''SELECT f.*,u.full_name AS created_by_name FROM resource_files f
        JOIN users u ON u.id=f.uploaded_by WHERE f.library_id=%s''', (library_id,)).fetchall()
    return folders, files


def listing_rows(connection, library_id, parent_id, search, trash):
    clauses = 'IS NOT NULL' if trash else 'IS NULL'
    predicate = '' if trash or search else ' AND {parent} IS NOT DISTINCT FROM %s'
    folder_args = [library_id]
    file_args = [library_id]
    if not trash and not search:
        folder_args.append(parent_id)
        file_args.append(parent_id)
    if search:
        predicate += ' AND strpos(lower({name}),lower(%s)) > 0'
        folder_args.append(search)
        file_args.append(search)
    folders = connection.execute(f'''SELECT f.*,u.full_name AS created_by_name FROM resource_folders f
        JOIN users u ON u.id=f.created_by WHERE f.library_id=%s AND f.deleted_at {clauses}''' +
        predicate.format(parent='f.parent_folder_id', name='f.name'), folder_args).fetchall()
    files = connection.execute(f'''SELECT f.*,u.full_name AS created_by_name FROM resource_files f
        JOIN users u ON u.id=f.uploaded_by WHERE f.library_id=%s AND f.deleted_at {clauses}''' +
        predicate.format(parent='f.folder_id', name='f.original_name'), file_args).fetchall()
    seeds = {f['id'] for f in folders} | {f['folder_id'] for f in files if f['folder_id'] is not None}
    if parent_id is not None:
        seeds.add(parent_id)
    ancestors = connection.execute('''WITH RECURSIVE path AS (
        SELECT * FROM resource_folders WHERE library_id=%s AND id=ANY(%s::uuid[])
        UNION SELECT f.* FROM resource_folders f JOIN path p ON p.parent_folder_id=f.id
        WHERE f.library_id=%s
    ) SELECT * FROM path''', (library_id, list(seeds), library_id)).fetchall()
    return folders, files, ancestors


def create_folder(connection, library_id, parent, name, actor):
    return connection.execute('''INSERT INTO resource_folders(library_id,parent_folder_id,name,created_by)
        VALUES (%s,%s,%s,%s) RETURNING id''', (library_id,parent,name,actor)).fetchone()['id']


def create_file(connection, library_id, parent, name, key, mime, size, actor):
    return connection.execute('''INSERT INTO resource_files(library_id,folder_id,original_name,storage_key,mime_type,size_bytes,uploaded_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id''', (library_id,parent,name,key,mime,size,actor)).fetchone()['id']


def update(connection, table, item_id, values):
    # All table/column names originate from service constants, never from request text.
    columns = ','.join(f'{key}=%s' for key in values)
    connection.execute(f'UPDATE {table} SET {columns} WHERE id=%s', [*values.values(), item_id])


def delete(connection, table, ids):
    if ids:
        connection.execute(f'DELETE FROM {table} WHERE id=ANY(%s::uuid[])', (ids,))
