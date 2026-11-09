from flask import Blueprint, g, jsonify

from ..auth import authenticated
from ..services import auth as service
from ..validation import json_body, text


blueprint = Blueprint('auth', __name__, url_prefix='/api/auth')


@blueprint.post('/login')
def login():
    body = json_body({'email', 'password'}, {'email', 'password'})
    email = text(body['email'], 'email')
    password = text(body['password'], 'password', strip=False)
    return jsonify(service.login(email, password))


@blueprint.post('/logout')
@authenticated(allow_password_change=True)
def logout():
    # Stateless access-token contract: desktop removes its local token.
    return jsonify(message='Logged out; remove the access token from this client')


@blueprint.get('/me')
@authenticated(allow_password_change=True)
def me():
    return jsonify(service.me(g.user['id'], g.auth_claims['requires_password_change']))


@blueprint.post('/change-password')
@authenticated(allow_password_change=True)
def change_password():
    body = json_body({'old_password', 'new_password'}, {'old_password', 'new_password'})
    old_password = text(body['old_password'], 'old_password', strip=False)
    new_password = text(body['new_password'], 'new_password', minimum=8, strip=False)
    return jsonify(service.change_password(g.user['id'], g.auth_claims['requires_password_change'],
                                           old_password, new_password))
