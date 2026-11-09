import hashlib
import json

from flask import current_app
from itsdangerous import BadData, URLSafeSerializer

from .errors import APIError


def _signer():
    return URLSafeSerializer(current_app.config['CURSOR_SECRET_KEY'], salt='cursor-v1')


def _scope(filters):
    return hashlib.sha256(json.dumps(filters, sort_keys=True, separators=(',', ':'),
                                     default=str).encode()).hexdigest()


def page_request(args, filters):
    try:
        limit = int(args.get('limit', '50'))
    except (TypeError, ValueError):
        raise APIError('invalid_pagination', 'limit must be an integer') from None
    if not 1 <= limit <= 100:
        raise APIError('invalid_pagination', 'limit must be between 1 and 100')
    cursor = args.get('cursor')
    if not cursor:
        return limit, None
    try:
        payload = _signer().loads(cursor)
        if not isinstance(payload, dict) or payload.get('scope') != _scope(filters):
            raise ValueError()
        return limit, payload['position']
    except (BadData, ValueError, KeyError, TypeError):
        raise APIError('invalid_cursor', 'Cursor is invalid for these filters') from None


def page_response(rows, limit, filters, position):
    """Query limit+1 rows in a stable order with a unique tie-breaker.

    Include endpoint, actor and all effective filters in filters. Position is a
    callback returning the last item's ordered key values as JSON-safe data.
    """
    has_more = len(rows) > limit
    items = rows[:limit]
    cursor = _signer().dumps({'scope': _scope(filters), 'position': position(items[-1])}) if has_more else None
    return {'items': items, 'next_cursor': cursor}
