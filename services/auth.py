from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import run_transaction
from ..errors import APIError
from ..repositories import auth as repository


TEMPORARY_PREFIX = 'temporary$'


def temporary_hash(password):
    """Used by user creation; never return this hash in API responses."""
    return TEMPORARY_PREFIX + generate_password_hash(password, method='scrypt')


def requires_password_change(user):
    return user['password_hash'].startswith(TEMPORARY_PREFIX)


def password_matches(user, password):
    stored = user['password_hash']
    if requires_password_change(user):
        stored = stored[len(TEMPORARY_PREFIX):]
    try:
        return check_password_hash(stored, password)
    except (ValueError, TypeError):
        return False


def user_payload(connection, user):
    return {'id': str(user['id']), 'email': user['email'], 'full_name': user['full_name'],
            'role': user['role'], 'is_active': user['is_active'], 'profile_img': user['profile_img'],
            'departments': [{'id': str(row['id']), 'name': row['name']}
                            for row in repository.departments(connection, user['id'])]}


def current_user(connection, user_id, restricted=None, lock=False):
    """Call inside EVERY business transaction; do not authorize from token role.

    restricted is the JWT's password-change claim, or None for internal use.
    """
    user = repository.find_by_id(connection, user_id, lock=lock)
    if user is None or not user['is_active']:
        raise APIError('unauthorized', 'Authentication is required', 401)
    if restricted is not None and requires_password_change(user) != restricted:
        raise APIError('login_required', 'Please sign in again', 401)
    return user


def login(email, password):
    def operation(connection):
        user = repository.find_by_email(connection, email)
        if user is None or not user['is_active'] or not password_matches(user, password):
            raise APIError('invalid_credentials', 'Invalid email or password', 401)
        repository.touch_activity(connection, user['id'], force=True)
        restricted = requires_password_change(user)
        now = datetime.now(timezone.utc)
        expires = timedelta(days=current_app.config['JWT_ACCESS_DAYS'])
        token = jwt.encode({'sub': str(user['id']), 'iat': now, 'exp': now + expires,
                            'type': 'access', 'requires_password_change': restricted},
                           current_app.config['JWT_SECRET_KEY'], algorithm='HS256')
        return {'access_token': token, 'token_type': 'Bearer', 'expires_in': int(expires.total_seconds()),
                'requires_password_change': restricted, 'user': user_payload(connection, user)}
    return run_transaction(operation)


def authenticate(user_id, restricted):
    def operation(connection):
        user = current_user(connection, user_id, restricted)
        repository.touch_activity(connection, user_id)
        return user
    return run_transaction(operation)


def me(user_id, restricted):
    def operation(connection):
        user = current_user(connection, user_id, restricted)
        return user_payload(connection, user)
    return run_transaction(operation)


def change_password(user_id, restricted, old_password, new_password):
    def operation(connection):
        user = current_user(connection, user_id, restricted, lock=True)
        if not password_matches(user, old_password):
            raise APIError('invalid_password', 'Old password is incorrect', 400)
        first_change = requires_password_change(user)
        repository.update_password(connection, user_id,
                                   generate_password_hash(new_password, method='scrypt'))
        result = {'message': 'Password changed'}
        if first_change:
            result['requires_login'] = True
        return result
    return run_transaction(operation)
