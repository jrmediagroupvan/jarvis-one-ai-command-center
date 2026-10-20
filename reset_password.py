#!/usr/bin/env python3
"""Offline account recovery. Run on Ubuntu inside the application container.

   docker compose exec -it jarvis python reset_password.py admin

Restrict shell access to trusted server admins. This changes an existing account
without needing the user's old password. It never echoes the new password.
"""
import getpass
import hashlib
import os
from pathlib import Path
import secrets
import sqlite3
import sys


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python reset_password.py USERNAME')
    username = sys.argv[1]
    first = getpass.getpass('New password (at least 12 characters): ')
    if len(first) < 12:
        raise SystemExit('Password must be at least 12 characters')
    if first != getpass.getpass('Confirm new password: '):
        raise SystemExit('Passwords did not match')
    db_path = Path(os.getenv('JARVIS_DATA', str(Path(__file__).resolve().parent / 'data'))) / 'jarvis.db'
    if not db_path.is_file():
        raise SystemExit(f'User database not found: {db_path}')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', first.encode(), salt, 310000)
    with sqlite3.connect(db_path) as db:
        result = db.execute('UPDATE users SET password_hash=? WHERE username=?',
                            (salt.hex() + ':' + digest.hex(), username))
        if result.rowcount != 1:
            raise SystemExit('Account not found; no changes made')
    print(f'Password updated for {username}. Sign in with the new password.')

if __name__ == '__main__':
    main()
