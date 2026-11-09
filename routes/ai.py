from flask import Blueprint, jsonify, request

from ..auth import authenticated
from ..errors import APIError
from ..validation import json_body
from ..ai import context_loader, nvidia_client, service

blueprint = Blueprint('ai', __name__, url_prefix='/api/ai')


@blueprint.get('/status')
@authenticated()
def status():
    try:
        nvidia_client.configuration()
        for name in ('ROUTER_CONTEXT', 'ANALYST_CONTEXT', 'COMPANY_CONTEXT', 'REPORTS_TOOL'):
            context_loader.load(name)
    except APIError:
        return jsonify(configured=False, availability='unknown')
    return jsonify(configured=True, availability='unknown')


@blueprint.post('/plan')
@authenticated()
def plan():
    if request.content_length is None or request.content_length > 150_000:
        raise APIError('invalid_input', 'AI zahtev je prevelik.', 413)
    body = json_body({'message', 'history'}, {'message'})
    return jsonify(service.plan(body['message'], body.get('history', [])))


@blueprint.post('/answer')
@authenticated()
def answer():
    if request.content_length is None or request.content_length > 500_000:
        raise APIError('invalid_input', 'AI zahtev je prevelik.', 413)
    body = json_body({'plan_token', 'message', 'results'}, {'plan_token', 'message', 'results'})
    return jsonify(service.answer(body['plan_token'], body['message'], body['results']))
