#!/usr/bin/env python3
"""First-run setup: generate unique administrator credentials without extra packages."""
from pathlib import Path
import secrets
import shutil
import os

ROOT = Path(__file__).resolve().parent
ENV = ROOT / '.env'
EXAMPLE = ROOT / '.env.example'
PRINTERS = ROOT / 'config' / 'printers.json'
PRINTERS_EXAMPLE = ROOT / 'config' / 'printers.example.json'

def main():
    if ENV.exists():
        print('Existing .env found. Admin credentials were NOT changed.')
        print('If already initialized, the admin password is stored as a hash in data/jarvis.db.')
    else:
        password = secrets.token_urlsafe(24)
        lines = EXAMPLE.read_text(encoding='utf-8').splitlines()
        updated = []
        for line in lines:
            if line.startswith('JARVIS_USERNAME='):
                line = 'JARVIS_USERNAME=admin'
            elif line.startswith('JARVIS_PASSWORD='):
                line = 'JARVIS_PASSWORD=' + password
            updated.append(line)
        # Create secret file using restrictive permissions; never check it into git.
        fd = os.open(ENV, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as fp:
            fp.write('\n'.join(updated) + '\n')
        print('\nJARVIS FIRST-RUN ADMIN LOGIN')
        print('Username: admin')
        print('Password: ' + password)
        print('Store this password securely. It will not be printed again by setup.')
    if not PRINTERS.exists():
        shutil.copyfile(PRINTERS_EXAMPLE, PRINTERS)
        print('Created config/printers.json (edit with your printer settings).')
    print('\nNext: edit .env for API keys, then run: docker compose up -d --build')
    print('Open http://YOUR-UBUNTU-SERVER-IP:8765 (use HTTPS for secure login and microphone access).')

if __name__ == '__main__':
    main()
