"""Minimal HTTPS Chat Completions client; never logs prompts or credentials."""
import json
import os
import re
import socket
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from flask import current_app

from ..errors import APIError


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def configuration():
    key = os.environ.get('NVIDIA_API_KEY', '').strip()
    url = os.environ.get('NVIDIA_BASE_URL', 'https://integrate.api.nvidia.com/v1').rstrip('/')
    parsed = urlsplit(url)
    try:
        timeout = float(os.environ.get('NVIDIA_AI_TIMEOUT_SECONDS', '60'))
        if not 1 <= timeout <= 180 or parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError()
    except ValueError:
        raise APIError('ai_configuration', 'AI servis nije pravilno konfigurisan.', 503) from None
    if not key:
        raise APIError('ai_configuration', 'AI servis nije konfigurisan.', 503)
    return key, url, timeout


def _log_failure(kind, model, status, started):
    # No exception text, headers, URL, response body, prompts, or credentials.
    safe_model = model if isinstance(model, str) and re.fullmatch(r'[a-zA-Z0-9._/-]{1,120}', model) else 'invalid_model'
    current_app.logger.warning('pulse_ai_error kind=%s model=%s upstream_status=%s duration_ms=%d',
                               kind, safe_model, status if status is not None else 'none',
                               round((monotonic() - started) * 1000))


def complete(model, system, payload, *, diagnostics=None, allow_json_fence=False):
    started = monotonic()
    status = None
    try:
        key, base, timeout = configuration()
    except APIError:
        _log_failure('configuration', model, status, started)
        raise
    body = json.dumps({'model': model, 'messages': [{'role': 'system', 'content': system},
        {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
        'temperature': 0.1, 'max_tokens': 4096, 'stream': False,
        'chat_template_kwargs': {'enable_thinking': False}}, ensure_ascii=False).encode('utf-8')
    request = Request(base + '/chat/completions', data=body,
                      headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}, method='POST')
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            status = response.status
            raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            _log_failure('upstream_body_too_large', model, status, started)
            raise APIError('ai_invalid_response', 'AI servis je vratio neispravan odgovor.', 502)
    except HTTPError as error:
        _log_failure('upstream_http', model, error.code, started)
        if error.code == 429:
            raise APIError('ai_rate_limit', 'AI servis je trenutno preopterećen. Pokušajte kasnije.', 503) from None
        raise APIError('ai_provider', 'AI servis nije dostupan ili nije ispravno podešen.', 503) from None
    except (URLError, TimeoutError, OSError) as error:
        reason = error.reason if isinstance(error, URLError) else error
        kind = 'upstream_timeout' if isinstance(reason, (TimeoutError, socket.timeout)) else 'upstream_network'
        _log_failure(kind, model, status, started)
        raise APIError('ai_provider', 'AI servis nije dostupan ili je zahtev istekao.', 503) from None
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        _log_failure('upstream_json_parse', model, status, started)
        raise APIError('ai_invalid_response', 'AI servis je vratio neispravan odgovor.', 502) from None
    try:
        choice = data['choices'][0]
        content = choice['message']['content']
    except (KeyError, IndexError, TypeError):
        _log_failure('upstream_envelope', model, status, started)
        raise APIError('ai_invalid_response', 'AI servis je vratio neispravan odgovor.', 502) from None
    if allow_json_fence and choice.get('finish_reason') == 'length':
        _log_failure('model_output_truncated', model, status, started)
        raise APIError('ai_invalid_response', 'AI servis je vratio neispravan odgovor.', 502)
    try:
        if not isinstance(content, str) or not content.strip() or len(content) > 100_000:
            _log_failure('model_content_empty_or_invalid', model, status, started)
            raise APIError('ai_invalid_response', 'AI servis je vratio neispravan odgovor.', 502)
        # A single fenced JSON object is common model formatting, not additional content.
        # Never use reasoning_content as a fallback or record it in logs.
        candidate = content.strip()
        if allow_json_fence:
            fenced = re.fullmatch(r'```(?:json)?[ \t]*\r?\n(.*?)\r?\n```', candidate, re.DOTALL | re.IGNORECASE)
            if fenced:
                candidate = fenced.group(1)
        result = json.loads(candidate)
        if not isinstance(result, dict):
            _log_failure('model_json_not_object', model, status, started)
            raise APIError('ai_invalid_response', 'AI servis je vratio neispravan odgovor.', 502)
    except (ValueError, TypeError):
        _log_failure('model_json_parse', model, status, started)
        raise APIError('ai_invalid_response', 'AI servis je vratio neispravan odgovor.', 502) from None
    if diagnostics is not None:
        diagnostics.update(upstream_status=status, started=started)
    return result
