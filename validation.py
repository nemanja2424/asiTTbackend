from datetime import date, datetime
from uuid import UUID

from flask import request

from .errors import APIError


def json_body(allowed, required=()):
    body = request.get_json()
    if not isinstance(body, dict):
        raise APIError('invalid_input', 'A JSON object is required')
    unknown = set(body) - set(allowed)
    missing = set(required) - set(body)
    if unknown or missing:
        raise APIError('invalid_input', 'Unexpected or missing fields', details={
            'unknown': sorted(unknown), 'missing': sorted(missing)})
    return body


def text(value, field, minimum=1, maximum=None, strip=True):
    if not isinstance(value, str):
        raise APIError('invalid_input', f'{field} must be a string')
    result = value.strip() if strip else value
    if len(result) < minimum or (maximum is not None and len(result) > maximum):
        raise APIError('invalid_input', f'{field} has an invalid length')
    return result


def uuid4(value, field='id'):
    try:
        result = UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise APIError('invalid_input', f'{field} must be a UUID v4') from None
    if result.version != 4:
        raise APIError('invalid_input', f'{field} must be a UUID v4')
    return result


def timestamp(value, field):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError()
        return result
    except (ValueError, TypeError, AttributeError):
        raise APIError('invalid_input', f'{field} must be ISO 8601 with a UTC offset') from None


def integer(value, field, minimum=0, maximum=None):
    if isinstance(value, bool) or not isinstance(value, int):
        raise APIError('invalid_input', f'{field} must be an integer')
    if value < minimum or (maximum is not None and value > maximum):
        raise APIError('invalid_input', f'{field} is outside the allowed range')
    return value


def boolean(value, field):
    if type(value) is not bool:
        raise APIError('invalid_input', f'{field} must be a boolean')
    return value


def query_boolean(value, field):
    if value not in ('true', 'false'):
        raise APIError('invalid_input', f'{field} must be true or false')
    return value == 'true'


def uuid_list(value, field):
    if not isinstance(value, list):
        raise APIError('invalid_input', f'{field} must be a list')
    result = [uuid4(item, field) for item in value]
    return list(dict.fromkeys(result))


def iso_date(value, field):
    if not isinstance(value, str) or len(value) != 10:
        raise APIError('invalid_input', f'{field} must be an ISO date (YYYY-MM-DD)')
    try:
        result = date.fromisoformat(value)
        if result.isoformat() != value:
            raise ValueError()
        return result
    except ValueError:
        raise APIError('invalid_input', f'{field} must be an ISO date (YYYY-MM-DD)') from None
