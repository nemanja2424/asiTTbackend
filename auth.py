from functools import wraps

import jwt
from flask import current_app, g, request

from .errors import APIError
from .services import auth as service
from .validation import uuid4


def authenticated(allow_password_change=False):
    def decorator(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            authorization = request.headers.get('Authorization', '').split()
            if len(authorization) != 2 or authorization[0].lower() != 'bearer':
                raise APIError('unauthorized', 'A Bearer access token is required', 401)
            try:
                claims = jwt.decode(authorization[1], current_app.config['JWT_SECRET_KEY'],
                                    algorithms=['HS256'], options={
                                        'require': ['sub', 'iat', 'exp', 'type', 'requires_password_change']})
                if claims['type'] != 'access' or type(claims['requires_password_change']) is not bool:
                    raise ValueError()
                user_id = uuid4(claims['sub'], 'token subject')
            except (jwt.InvalidTokenError, ValueError, APIError, TypeError):
                raise APIError('unauthorized', 'Access token is invalid or expired', 401) from None
            g.auth_claims = claims
            g.user = service.authenticate(user_id, claims['requires_password_change'])
            if claims['requires_password_change'] and not allow_password_change:
                raise APIError('password_change_required', 'Change your temporary password first', 403)
            return function(*args, **kwargs)
        return wrapped
    return decorator
