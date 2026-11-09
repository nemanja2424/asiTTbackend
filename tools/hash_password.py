from getpass import getpass
from uuid import uuid4

from werkzeug.security import generate_password_hash


def main():
    password = getpass('Lozinka: ')
    confirmation = getpass('Ponovite lozinku: ')
    if password != confirmation:
        raise SystemExit('Lozinke se ne podudaraju.')
    if len(password) < 8:
        raise SystemExit('Lozinka mora imati najmanje 8 karaktera.')

    print(f'UUID: {uuid4()}')
    print(f'Password hash: {generate_password_hash(password, method="scrypt")}')


if __name__ == '__main__':
    main()
