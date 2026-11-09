"""Private, versioned image storage; DB and filesystem cannot commit atomically."""
from io import BytesIO
import os
from pathlib import Path
import tempfile
from uuid import UUID, uuid4
import warnings

import psycopg
from flask import current_app, g
from PIL import Image, ImageOps, UnidentifiedImageError
from psycopg.rows import dict_row

from ..authorization import transaction_actor
from ..errors import APIError
from ..repositories import profile_image as repository
from .auth import current_user


ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / 'data' / 'profile_img'
MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 25_000_000


def _path(relative, user_id):
    """Accept only our own canonical, versioned filename for this user."""
    if not isinstance(relative, str):
        return None
    prefix = f'data/profile_img/{user_id}_'
    if not relative.startswith(prefix) or not relative.endswith('.webp'):
        return None
    version = relative[len(prefix):-5]
    try:
        parsed = UUID(version)
    except ValueError:
        return None
    if parsed.version != 4 or str(parsed) != version:
        return None
    return DIRECTORY / f'{user_id}_{version}.webp'


def _encode(stream):
    raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise APIError('invalid_input', 'Image exceeds the 5 MiB limit', 413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw), formats=('JPEG', 'PNG', 'WEBP')) as image:
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
                    raise APIError('invalid_input', 'Image dimensions are too large')
                image.load()
                image = ImageOps.exif_transpose(image)
                image.thumbnail((512, 512), Image.Resampling.LANCZOS)
                image = image.convert('RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB')
                result = BytesIO()
                image.save(result, format='WEBP', quality=85, method=4, exif=b'', icc_profile=b'', xmp=b'')
                return result.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise APIError('invalid_input', 'Image must be a valid JPEG, PNG or WebP') from None


def _remove(relative, user_id):
    path = _path(relative, user_id)
    if path:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # The committed DB reference remains authoritative; leave an orphan for cleanup.
            current_app.logger.warning('Could not remove an obsolete profile image')


def _write(path, data):
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=DIRECTORY, prefix='.upload-', delete=False) as file:
            temporary = Path(file.name)
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _change(data):
    user_id = g.user['id']
    relative = f'data/profile_img/{user_id}_{uuid4()}.webp' if data is not None else None
    new_path = _path(relative, user_id) if relative else None
    committing = False
    old = None
    # READ COMMITTED + row lock serializes writers without retrying filesystem effects.
    try:
        with psycopg.connect(current_app.config['DATABASE_URL'], row_factory=dict_row,
                             connect_timeout=5) as connection:
            actor = transaction_actor(connection)
            locked = repository.lock_user(connection, actor['id'])
            if locked is None or not locked['is_active']:
                raise APIError('unauthorized', 'Authentication is required', 401)
            # Revalidate password-change state after waiting for the row lock.
            current_user(connection, actor['id'], g.auth_claims['requires_password_change'])
            old = locked['profile_img']
            if new_path:
                _write(new_path, data)
            repository.set_path(connection, actor['id'], relative)
            # If commit's outcome is unknown, retain both files instead of risking data loss.
            committing = True
            connection.commit()
    except Exception:
        if not committing and new_path:
            _remove(relative, user_id)
        raise
    _remove(old, user_id)
    return relative


def upload(stream):
    return _change(_encode(stream))


def delete():
    _change(None)


def get(user_id):
    # Hold a shared row lock while reading so replacement cannot remove this version.
    with psycopg.connect(current_app.config['DATABASE_URL'], row_factory=dict_row,
                         connect_timeout=5) as connection:
        actor = transaction_actor(connection)
        target = repository.lock_user(connection, user_id, shared=True)
        if target is None or (not target['is_active'] and actor['role'] != 'admin'):
            raise APIError('not_found', 'User not found', 404)
        path = _path(target['profile_img'], user_id)
        if path is None:
            raise APIError('not_found', 'Profile image not found', 404)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            raise APIError('not_found', 'Profile image not found', 404) from None
