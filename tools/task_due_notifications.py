"""Run manually or from an operator-configured scheduler; no network calls."""
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import create_app
from backend.services.notifications import scheduled_due_check


def main():
    app = create_app()
    with app.app_context():
        try:
            users = scheduled_due_check()
        except Exception:
            print('Provera rokova nije uspela; proverite serversku konfiguraciju i bazu.', file=sys.stderr)
            return 1
    print(f'Provera rokova završena. Obrađeno korisnika: {users}.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
