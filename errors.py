import psycopg
from flask import jsonify
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    def __init__(self, code, message, status=400, details=None):
        self.code, self.message, self.status, self.details = code, message, status, details
        super().__init__(message)


def register_errors(app):
    @app.errorhandler(APIError)
    def api_error(error):
        body = {'code': error.code, 'message': error.message, 'details': error.details or {}}
        return jsonify(error=body), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        return api_error(APIError('http_error', error.description, error.code))

    @app.errorhandler(psycopg.Error)
    def database_error(error):
        if error.sqlstate in ('40001', '40P01'):
            return api_error(APIError('transaction_conflict', 'Please retry the request', 409))
        if error.sqlstate == '23505':
            return api_error(APIError('already_exists', 'A record already exists', 409))
        if error.sqlstate == '23P01':
            return api_error(APIError('overlapping_interval', 'The work interval overlaps an existing log', 409))
        if error.sqlstate in ('23503', '23514', '23502'):
            return api_error(APIError('integrity_conflict', 'The operation violates a data constraint', 409))
        return api_error(APIError('database_unavailable', 'Database operation failed', 503))

    @app.errorhandler(Exception)
    def unexpected_error(error):
        # Do not log exception text: database diagnostics may contain sensitive data.
        app.logger.error('Unhandled backend error (%s)', type(error).__name__)
        return api_error(APIError('internal_error', 'An internal error occurred', 500))
