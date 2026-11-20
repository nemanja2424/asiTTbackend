import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.parse import urlsplit

from dotenv import load_dotenv


def load_config():
    load_dotenv(Path(__file__).with_name('.env'), override=False)
    desktop_version = os.environ.get('LATEST_DESKTOP_VERSION', '1.3.0')
    if (not re.fullmatch(r'(?:0|[1-9][0-9]{0,4})(?:\.(?:0|[1-9][0-9]{0,4})){2}', desktop_version)
            or max(map(int, desktop_version.split('.'))) > 65535):
        raise RuntimeError('LATEST_DESKTOP_VERSION must have the format MAJOR.MINOR.PATCH (0..65535 per component)')
    download_url = os.environ.get('DESKTOP_UPDATE_URL', '')
    update_sha256 = os.environ.get('DESKTOP_UPDATE_SHA256', '')
    if bool(download_url) != bool(update_sha256):
        raise RuntimeError('DESKTOP_UPDATE_URL and DESKTOP_UPDATE_SHA256 must be configured together')
    if download_url:
        try:
            parsed = urlsplit(download_url)
            if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
                    or parsed.password is not None or parsed.fragment or parsed.port == 0
                    or not re.fullmatch(r'[0-9a-fA-F]{64}', update_sha256)):
                raise ValueError()
        except ValueError:
            raise RuntimeError('Invalid desktop update URL or SHA-256') from None
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
    return {**values, 'LATEST_DESKTOP_VERSION': desktop_version,
            'DESKTOP_UPDATE_URL': download_url or None, 'DESKTOP_UPDATE_SHA256': update_sha256.lower() or None,
            'APP_TIMEZONE': timezone, 'JWT_ACCESS_DAYS': 30,
            'DB_TRANSACTION_ATTEMPTS': 3, 'MAX_CONTENT_LENGTH': 1024 * 1024,
            'RESOURCE_UPLOAD_SLOTS': slots, 'RESOURCE_MIN_FREE_BYTES': reserve}
