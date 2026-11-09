"""Private library metadata and authorization. Filesystem work has no DB retries."""
import mimetypes
import os
from pathlib import Path
import tempfile
from uuid import uuid4

import psycopg
from flask import current_app
from psycopg.rows import dict_row

from ..authorization import transaction_actor
from ..db import run_transaction
from ..errors import APIError
from ..repositories import resources as repo, tasks as task_repo
from ..repositories import scope as scope_repo
from . import departments, projects, scope

ROOT = Path(__file__).resolve().parents[2] / 'data' / 'resources'
MAX_BYTES = 100 * 1024 * 1024


def name(value):
    if not isinstance(value, str):
        raise APIError('invalid_input', 'A name is required')
    value = value.strip()
    if not value or len(value) > 255 or value in ('.', '..') or any(ord(c) < 32 or c in '/\\' for c in value):
        raise APIError('invalid_input', 'Invalid file or folder name')
    return value


def _authorize(connection, kind, owner_id):
    actor = transaction_actor(connection)
    if kind == 'projects':
        projects.accessible(connection, actor, owner_id)
    else:
        departments.accessible(connection, actor, owner_id)
        if actor['role'] == 'manager' and owner_id not in scope.managed_departments(connection, actor):
            raise APIError('not_found', 'Library not found', 404)
        if actor['role'] == 'worker' and owner_id not in scope_repo.memberships(connection, actor['id']):
            raise APIError('not_found', 'Library not found', 404)
    return actor


def _context(connection, kind, owner_id):
    _authorize(connection, kind, owner_id)
    library_id = repo.library(connection, kind, owner_id)
    # In READ COMMITTED uploads/downloads, recheck rights after waiting for the lock.
    actor = _authorize(connection, kind, owner_id)
    folders, files = repo.rows(connection, library_id)
    return actor, library_id, {x['id']: x for x in folders}, {x['id']: x for x in files}


def _run(kind, owner_id, callback):
    return run_transaction(lambda connection: callback(connection, *_context(connection, kind, owner_id)))


def check_access(kind, owner_id):
    _run(kind, owner_id, lambda *_: None)


def accessible_libraries():
    """Return names only, using the same scopes as individual library access."""
    def operation(connection):
        actor = transaction_actor(connection)
        project_ids, _ = projects.permissions(connection, actor)
        project_rows = repo.accessible_projects(connection, project_ids)
        visible = scope.visible_departments(connection, actor)
        if actor['role'] == 'manager':
            visible = scope.managed_departments(connection, actor)
        elif actor['role'] == 'worker':
            visible = scope_repo.memberships(connection, actor['id'])
        department_rows = repo.accessible_departments(connection, visible)
        return {'projects': project_rows, 'departments': department_rows}
    return run_transaction(operation)


def _folder(folders, folder_id, active=True):
    if folder_id is None:
        return None
    row = folders.get(folder_id)
    if row is None or (active and row['deleted_at'] is not None):
        raise APIError('not_found', 'Folder not found', 404)
    return row


def _path(folders, folder_id):
    result, seen = [], set()
    while folder_id is not None:
        if folder_id in seen or folder_id not in folders:
            raise APIError('integrity_conflict', 'Invalid folder hierarchy', 409)
        seen.add(folder_id)
        row = folders[folder_id]
        result.append({'id': row['id'], 'name': row['name']})
        folder_id = row['parent_folder_id']
    return list(reversed(result))


def _item(row, kind, folders):
    folder_id = row['parent_folder_id'] if kind == 'folder' else row['folder_id']
    return {'id':row['id'], 'kind':kind, 'name':row['name'] if kind == 'folder' else row['original_name'],
            'folder_id':folder_id, 'size_bytes':None if kind == 'folder' else row['size_bytes'],
            'mime_type':None if kind == 'folder' else row['mime_type'], 'created_at':row['created_at'],
            'created_by_name':row['created_by_name'], 'deleted_at':row['deleted_at'], 'path':_path(folders, folder_id)}


def _conflict(folders, files, parent, candidate, exclude=None):
    key = candidate.casefold()
    for kind, rows in (('folder', folders.values()), ('file', files.values())):
        for row in rows:
            if row['id'] == exclude or row['deleted_at'] is not None:
                continue
            row_parent = row['parent_folder_id'] if kind == 'folder' else row['folder_id']
            row_name = row['name'] if kind == 'folder' else row['original_name']
            if row_parent == parent and row_name.casefold() == key:
                raise APIError('already_exists', 'A file or folder with that name already exists', 409)


def _descendants(folders, root):
    found = {root}
    while True:
        added = {row['id'] for row in folders.values() if row['parent_folder_id'] in found} - found
        if not added:
            return found
        found.update(added)


def _can_manage(actor, row, kind, folders, files):
    if actor['role'] != 'worker':
        return
    owner = row['created_by'] if kind == 'folder' else row['uploaded_by']
    if owner != actor['id']:
        raise APIError('forbidden', 'You may manage only your own items', 403)
    if kind == 'folder':
        ids = _descendants(folders, row['id'])
        if any(f['created_by'] != actor['id'] for f in folders.values() if f['id'] in ids) or any(
                f['uploaded_by'] != actor['id'] for f in files.values() if f['folder_id'] in ids):
            raise APIError('forbidden', 'Folder contains items belonging to another user', 403)


def listing(kind, owner_id, folder_id, search, trash):
    def operation(connection):
        _authorize(connection, kind, owner_id)
        library_id = repo.library(connection, kind, owner_id)
        folder_rows, file_rows, ancestors = repo.listing_rows(connection, library_id, folder_id, search, trash)
        folders = {x['id']:x for x in ancestors}
        folder = _folder(folders, folder_id) if not trash else None
        result = []
        for item_kind, rows in (('folder', folder_rows), ('file', file_rows)):
            for row in rows:
                deleted = row['deleted_at'] is not None
                item_name = row['name'] if item_kind == 'folder' else row['original_name']
                parent = row['parent_folder_id'] if item_kind == 'folder' else row['folder_id']
                if deleted != trash or (search and search.casefold() not in item_name.casefold()):
                    continue
                if not trash and not search and parent != folder_id:
                    continue
                result.append(_item(row, item_kind, folders))
        result.sort(key=lambda x: (x['kind'] != 'folder', x['name'].casefold(), str(x['id'])))
        current = None if folder is None else {'id':folder['id'],'name':folder['name'],
            'parent_id':folder['parent_folder_id'], 'path':_path(folders, folder['id'])}
        return {'items':result, 'folder':current}
    return run_transaction(operation)


def detail(kind, owner_id, item_id):
    def operation(connection, actor, library_id, folders, files):
        row = files.get(item_id)
        if row is None or row['deleted_at'] is not None:
            raise APIError('not_found', 'File not found', 404)
        return _item(row, 'file', folders)
    return _run(kind, owner_id, operation)


def create_folder(kind, owner_id, parent, value):
    value = name(value)
    def operation(connection, actor, library_id, folders, files):
        _folder(folders, parent)
        _conflict(folders, files, parent, value)
        item_id = repo.create_folder(connection, library_id, parent, value, actor['id'])
        folders, files = repo.rows(connection, library_id)
        return _item(next(x for x in folders if x['id'] == item_id), 'folder', {x['id']:x for x in folders})
    return _run(kind, owner_id, operation)


def update(kind, owner_id, item_kind, item_id, values):
    def operation(connection, actor, library_id, folders, files):
        row = (folders if item_kind == 'folder' else files).get(item_id)
        if row is None or row['deleted_at'] is not None:
            raise APIError('not_found', 'Item not found', 404)
        _can_manage(actor, row, item_kind, folders, files)
        parent_key = 'parent_folder_id' if item_kind == 'folder' else 'folder_id'
        name_key = 'name' if item_kind == 'folder' else 'original_name'
        parent = values.get('parent', row[parent_key])
        new_name = name(values['name']) if 'name' in values else row[name_key]
        _folder(folders, parent)
        if item_kind == 'folder' and parent in _descendants(folders, item_id):
            raise APIError('invalid_input', 'Folder cannot be moved into itself or its descendants')
        _conflict(folders, files, parent, new_name, item_id)
        repo.update(connection, 'resource_folders' if item_kind == 'folder' else 'resource_files', item_id,
                    {parent_key:parent, name_key:new_name})
        row.update({parent_key:parent, name_key:new_name})
        return _item(row, item_kind, folders)
    return _run(kind, owner_id, operation)


def trash(kind, owner_id, item_kind, item_id):
    def operation(connection, actor, library_id, folders, files):
        row = (folders if item_kind == 'folder' else files).get(item_id)
        if row is None or row['deleted_at'] is not None:
            raise APIError('not_found', 'Item not found', 404)
        _can_manage(actor, row, item_kind, folders, files)
        batch = uuid4()
        ids = _descendants(folders, item_id) if item_kind == 'folder' else set()
        connection.execute('UPDATE resource_folders SET deleted_at=statement_timestamp(),trash_batch=%s WHERE id=ANY(%s::uuid[]) AND deleted_at IS NULL', (batch, list(ids)))
        file_ids = [f['id'] for f in files.values() if f['deleted_at'] is None and (f['folder_id'] in ids or (item_kind == 'file' and f['id'] == item_id))]
        connection.execute('UPDATE resource_files SET deleted_at=statement_timestamp(),trash_batch=%s WHERE id=ANY(%s::uuid[])', (batch, file_ids))
        return {'message':'Item moved to trash'}
    return _run(kind, owner_id, operation)


def restore(kind, owner_id, item_kind, item_id):
    def operation(connection, actor, library_id, folders, files):
        row = (folders if item_kind == 'folder' else files).get(item_id)
        if row is None or row['deleted_at'] is None:
            raise APIError('not_found', 'Deleted item not found', 404)
        _can_manage(actor, row, item_kind, folders, files)
        parent = row['parent_folder_id'] if item_kind == 'folder' else row['folder_id']
        if parent is not None and (parent not in folders or folders[parent]['deleted_at'] is not None):
            raise APIError('integrity_conflict', 'Restore the parent folder first', 409)
        batch = row['trash_batch']
        ids = _descendants(folders, item_id) if item_kind == 'folder' else set()
        folder_rows = [f for f in folders.values() if f['id'] in ids and f['trash_batch'] == batch]
        file_rows = [f for f in files.values() if f['trash_batch'] == batch and (f['folder_id'] in ids or f['id'] == item_id)]
        for f in folder_rows:
            _conflict(folders, files, f['parent_folder_id'], f['name'], f['id'])
        for f in file_rows:
            _conflict(folders, files, f['folder_id'], f['original_name'], f['id'])
        for table, entries in (('resource_folders', folder_rows), ('resource_files', file_rows)):
            connection.execute(f'UPDATE {table} SET deleted_at=NULL,trash_batch=NULL WHERE id=ANY(%s::uuid[])', ([x['id'] for x in entries],))
        return {'message':'Item restored'}
    return _run(kind, owner_id, operation)


def _disk_path(kind, owner_id, key):
    # Inputs are DB UUIDs or validated route UUIDs; never client filenames.
    return ROOT / kind / str(owner_id) / str(key)


def permanent(kind, owner_id, item_kind, item_id):
    def operation(connection, actor, library_id, folders, files):
        if actor['role'] != 'admin':
            raise APIError('forbidden', 'Only admin may permanently delete items', 403)
        row = (folders if item_kind == 'folder' else files).get(item_id)
        if row is None or row['deleted_at'] is None:
            raise APIError('not_found', 'Deleted item not found', 404)
        ids = _descendants(folders, item_id) if item_kind == 'folder' else set()
        entries = [f for f in files.values() if f['folder_id'] in ids or (item_kind == 'file' and f['id'] == item_id)]
        file_ids = [f['id'] for f in entries]
        if file_ids:
            links = connection.execute('''SELECT a.task_id,f.original_name FROM task_attachments a
                JOIN resource_files f ON f.id=a.resource_id WHERE f.id=ANY(%s::uuid[])''', (file_ids,)).fetchall()
            for link in links:
                task_repo.activity(connection, link['task_id'], actor['id'], 'attachment_removed', old=link['original_name'])
        repo.delete(connection, 'resource_files', [f['id'] for f in entries])
        # Children must be removed before parents due to the restrictive FK.
        for folder_id in sorted(ids, key=lambda x: len(_path(folders, x)), reverse=True):
            repo.delete(connection, 'resource_folders', [folder_id])
        return [f['storage_key'] for f in entries]
    keys = _run(kind, owner_id, operation)
    for key in keys:
        try:
            _disk_path(kind, owner_id, key).unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning('Could not remove an obsolete library file')
    return {'message':'Item permanently deleted'}


def upload(kind, owner_id, parent, file):
    filename = name(file.filename)
    mime = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    key = uuid4()
    destination = _disk_path(kind, owner_id, key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    committed_or_uncertain = False
    created = False
    try:
        size = 0
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.upload-', delete=False) as target:
            temp = Path(target.name)
            while True:
                chunk = file.stream.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    raise APIError('invalid_input', 'File exceeds 100 MiB', 413)
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        with psycopg.connect(current_app.config['DATABASE_URL'], row_factory=dict_row, connect_timeout=5) as connection:
            actor, library_id, folders, files = _context(connection, kind, owner_id)
            _folder(folders, parent)
            _conflict(folders, files, parent, filename)
            # UUID destination is created exclusively; no existing file is overwritten.
            os.link(temp, destination)
            created = True
            temp.unlink()
            temp = None
            item_id = repo.create_file(connection, library_id, parent, filename, key, mime, size, actor['id'])
            folders_list, files_list = repo.rows(connection, library_id)
            result = _item(next(f for f in files_list if f['id'] == item_id), 'file', {f['id']:f for f in folders_list})
            committed_or_uncertain = True
            connection.commit()
        return result
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
        if created and not committed_or_uncertain:
            destination.unlink(missing_ok=True)


def download(kind, owner_id, item_id):
    # Open while holding library lock; the file object is streamed after DB commit.
    stream = None
    try:
        with psycopg.connect(current_app.config['DATABASE_URL'], row_factory=dict_row, connect_timeout=5) as connection:
            actor, library_id, folders, files = _context(connection, kind, owner_id)
            row = files.get(item_id)
            if row is None or row['deleted_at'] is not None:
                raise APIError('not_found', 'File not found', 404)
            try:
                stream = _disk_path(kind, owner_id, row['storage_key']).open('rb')
            except FileNotFoundError:
                raise APIError('not_found', 'File not found', 404) from None
        return stream, row['original_name']
    except Exception:
        if stream:
            stream.close()
        raise
