import os
import shutil
import tempfile
from pathlib import Path

from flask import Blueprint, Request, current_app, jsonify, request, send_file

from ..auth import authenticated
from ..errors import APIError
from ..services import resources as service
from ..validation import json_body, query_boolean, uuid4


blueprint = Blueprint('resources', __name__, url_prefix='/api')
BASE = '/<any(projects,departments):kind>/<owner_id>/files'


@blueprint.get('/library/accessible')
@authenticated()
def accessible_libraries():
    return jsonify(service.accessible_libraries())


class ResourceRequest(Request):
    def _get_file_stream(self, total_content_length, content_type, filename=None, content_length=None):
        if self.endpoint == 'resources.upload':
            directory = service.ROOT / '.tmp'
            directory.mkdir(parents=True, exist_ok=True)
            return tempfile.TemporaryFile(dir=directory)
        return super()._get_file_stream(total_content_length, content_type, filename, content_length)


def _id(value, field):
    return uuid4(value, field) if value else None


@blueprint.get(BASE)
@authenticated()
def listing(kind, owner_id):
    trash = query_boolean(request.args.get('trash', 'false'), 'trash')
    search = request.args.get('search', '').strip()
    if len(search) > 255:
        raise APIError('invalid_input', 'Search is too long')
    return jsonify(service.listing(kind, uuid4(owner_id), _id(request.args.get('folder_id'), 'folder_id'), search, trash))


@blueprint.post(BASE + '/folders')
@authenticated()
def create_folder(kind, owner_id):
    body = json_body({'name','parent_id'}, {'name'})
    return jsonify(service.create_folder(kind, uuid4(owner_id), _id(body.get('parent_id'), 'parent_id'), body['name'])), 201


@blueprint.patch(BASE + '/folders/<item_id>')
@blueprint.patch(BASE + '/items/<item_id>')
@authenticated()
def update(kind, owner_id, item_id):
    is_folder = '/folders/' in request.path
    parent_key = 'parent_id' if is_folder else 'folder_id'
    body = json_body({'name', parent_key})
    if not body:
        raise APIError('invalid_input', 'At least one field is required')
    values = {**({'name':body['name']} if 'name' in body else {}),
              **({'parent':_id(body[parent_key], parent_key)} if parent_key in body else {})}
    return jsonify(service.update(kind, uuid4(owner_id), 'folder' if is_folder else 'file', uuid4(item_id), values))


@blueprint.delete(BASE + '/folders/<item_id>')
@blueprint.delete(BASE + '/items/<item_id>')
@authenticated()
def trash(kind, owner_id, item_id):
    return jsonify(service.trash(kind, uuid4(owner_id), 'folder' if '/folders/' in request.path else 'file', uuid4(item_id)))


@blueprint.post(BASE + '/folders/<item_id>/restore')
@blueprint.post(BASE + '/items/<item_id>/restore')
@authenticated()
def restore(kind, owner_id, item_id):
    return jsonify(service.restore(kind, uuid4(owner_id), 'folder' if '/folders/' in request.path else 'file', uuid4(item_id)))


@blueprint.delete(BASE + '/folders/<item_id>/permanent')
@blueprint.delete(BASE + '/items/<item_id>/permanent')
@authenticated()
def permanent(kind, owner_id, item_id):
    return jsonify(service.permanent(kind, uuid4(owner_id), 'folder' if '/folders/' in request.path else 'file', uuid4(item_id)))


@blueprint.get(BASE + '/items/<item_id>')
@authenticated()
def detail(kind, owner_id, item_id):
    return jsonify(service.detail(kind, uuid4(owner_id), uuid4(item_id)))


@blueprint.get(BASE + '/items/<item_id>/download')
@authenticated()
def download(kind, owner_id, item_id):
    stream, filename = service.download(kind, uuid4(owner_id), uuid4(item_id))
    try:
        header = stream.read(12)
        stream.seek(0)
        mime = ('image/png' if header.startswith(b'\x89PNG\r\n\x1a\n') else
                'image/jpeg' if header.startswith(b'\xff\xd8\xff') else
                'image/webp' if header.startswith(b'RIFF') and header[8:12] == b'WEBP' else
                'application/octet-stream')
        response = send_file(stream, mimetype=mime, as_attachment=True,
                             download_name=filename, conditional=False, max_age=0)
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.call_on_close(stream.close)
        return response
    except Exception:
        stream.close()
        raise


@blueprint.post(BASE + '/upload')
@authenticated()
def upload(kind, owner_id):
    owner_id = uuid4(owner_id)
    service.check_access(kind, owner_id)
    request.max_content_length = service.MAX_BYTES + 128 * 1024
    request.max_form_memory_size = 512 * 1024
    request.max_form_parts = 2
    # Cross-process slots use exclusive creation on a shared filesystem. A crash
    # leaves a slot for an operator to inspect and remove, never stolen in-flight.
    directory = service.ROOT / '.tmp'
    directory.mkdir(parents=True, exist_ok=True)
    slot = None
    for index in range(current_app.config['RESOURCE_UPLOAD_SLOTS']):
        candidate = directory / f'slot-{index}.lock'
        try:
            descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(descriptor)
            slot = candidate
            break
        except FileExistsError:
            continue
    if slot is None:
        raise APIError('upload_busy', 'Too many uploads', 503)
    try:
        # Reserve for both the multipart spool and the finalized copy per slot.
        required = current_app.config['RESOURCE_MIN_FREE_BYTES'] + 2 * service.MAX_BYTES * current_app.config['RESOURCE_UPLOAD_SLOTS']
        if shutil.disk_usage(directory).free < required:
            raise APIError('storage_full', 'Insufficient upload space', 503)
        if set(request.files) != {'file'} or len(request.files.getlist('file')) != 1 or set(request.form) - {'folder_id'} or len(request.form.getlist('folder_id')) > 1:
            raise APIError('invalid_input', 'Exactly one file is required')
        return jsonify(service.upload(kind, owner_id, _id(request.form.get('folder_id'), 'folder_id'), request.files['file'])), 201
    finally:
        slot.unlink(missing_ok=True)
