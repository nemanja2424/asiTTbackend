import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


def load_config():
    load_dotenv(Path(__file__).with_name('.env'), override=False)
    values = {name: os.environ.get(name, '') for name in
              ('DATABASE_URL', 'JWT_SECRET_KEY', 'CURSOR_SECRET_KEY')}
    if any(not value.strip() for value in values.values()):
        raise RuntimeError('DATABASE_URL, JWT_SECRET_KEY and CURSOR_SECRET_KEY are required')
    if any(len(values[name]) < 32 for name in ('JWT_SECRET_KEY', 'CURSOR_SECRET_KEY')):
        raise RuntimeError('Signing secrets must contain at least 32 characters')
    timezone = os.environ.get('APP_TIMEZONE', 'Europe/Belgrade')
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        raise RuntimeError('APP_TIMEZONE is unavailable; install system timezone data') from None
    try:
        slots = int(os.environ.get('RESOURCE_UPLOAD_SLOTS', '2'))
        reserve = int(os.environ.get('RESOURCE_MIN_FREE_BYTES', str(1024 * 1024 * 1024)))
        if not 1 <= slots <= 128 or reserve < 0:
            raise ValueError()
    except ValueError:
        raise RuntimeError('Invalid resource upload limits') from None
    return {**values, 'APP_TIMEZONE': timezone, 'JWT_ACCESS_DAYS': 30,
            'DB_TRANSACTION_ATTEMPTS': 3, 'MAX_CONTENT_LENGTH': 1024 * 1024,
            'RESOURCE_UPLOAD_SLOTS': slots, 'RESOURCE_MIN_FREE_BYTES': reserve}
