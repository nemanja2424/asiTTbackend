from flask import g

from .errors import APIError
from .services.auth import current_user


def transaction_actor(connection):
    """Re-read actor in service transaction so concurrent authorization is checked.

    All service reads/writes use run_transaction (SERIALIZABLE, whole retry).
    g.user is for presentation only; never use its role for business mutations.
    """
    user = current_user(connection, g.user['id'], g.auth_claims['requires_password_change'])
    if g.auth_claims['requires_password_change']:
        raise APIError('password_change_required', 'Change your temporary password first', 403)
    return user


def require_role(actor, *roles):
    if actor['role'] not in roles:
        raise APIError('forbidden', 'You do not have permission for this operation', 403)
