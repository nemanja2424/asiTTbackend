"""Load only named, locally configured context files, caching by modification time."""
from functools import lru_cache
from pathlib import Path

from ..errors import APIError

DIRECTORY = Path(__file__).parent / 'context'
NAMES = {'ROUTER_CONTEXT', 'ANALYST_CONTEXT', 'COMPANY_CONTEXT', 'REPORTS_TOOL'}


@lru_cache(maxsize=8)
def _read(path, modified, size):
    return path.read_text(encoding='utf-8')


def load(name):
    if name not in NAMES:
        raise ValueError('Unknown context')
    path = DIRECTORY / (name + '.md')
    try:
        stat = path.stat()
        if stat.st_size > 100_000:
            raise ValueError()
        content = _read(path, stat.st_mtime_ns, stat.st_size)
        if not content.strip():
            raise ValueError()
        return content
    except (OSError, UnicodeError, ValueError):
        raise APIError('ai_configuration', 'AI kontekst nije pravilno konfigurisan.', 503) from None
