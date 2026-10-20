#!/usr/bin/env python3
"""Apply an admin-staged JARVIS update ZIP on the Ubuntu host.
Run from the JARVIS project root. Never execute this in the web container.
"""
import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
ALLOWED=('app/','static/','plugins/','tests/')
FILES={'Dockerfile','docker-compose.yml','requirements.txt','README.md','LICENSE',
       '.env.example','.gitignore','setup.py','setup.sh','reset_password.py',
       'README_ONE_CLICK.md','apply_update.py','update_worker.py','install_update_service.sh','FEATURE_BUILD_PROMPT.md','VERSION','config/printers.example.json'}
PROTECTED={'data','.env','config/printers.json','config/cameras.json'}

def fail(message):raise SystemExit('ERROR: '+message)

def verified_entries(archive):
    members=[m for m in archive.infolist() if not m.is_dir()]
    if not members or len(members)>250:fail('Invalid number of archive members')
    paths=[m.filename for m in members]
    roots={n.split('/')[0] for n in paths if '/' in n}
    prefix=next(iter(roots))+'/' if len(roots)==1 and all('/' in n for n in paths) else ''
    result=[]
    for m in members:
        n=m.filename
        if not n.startswith(prefix):fail('Mixed zip roots')
        n=n[len(prefix):]
        if ('\\' in n or ':' in n or n.startswith('/') or '..' in Path(n).parts or
            not n or m.file_size>2_000_000 or ((m.external_attr>>16)&0o170000)==0o120000):
            fail('Unsafe ZIP member: '+n)
        if not (n in FILES or any(n.startswith(x) for x in ALLOWED)):fail('Unexpected file: '+n)
        if n.startswith('data/') or n in PROTECTED:fail('Private content included: '+n)
        result.append((n,m))
    if len({n for n,_ in result})!=len(result):fail('Duplicate archive entries')
    names={n for n,_ in result}
    if not {'app/main.py','Dockerfile'}<=names:fail('Not a complete JARVIS update')
    if sum(m.file_size for _,m in result)>30_000_000:fail('Update too large')
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file',required=True,help='Staged update path, e.g. data/updates/abc.zip')
    parser.add_argument('--yes',action='store_true',help='Skip interactive confirmation')
    args=parser.parse_args()
    source=Path(args.file).resolve()
    staged_dir=(ROOT/'data'/'updates').resolve()
    if staged_dir not in source.parents or source.suffix!='.zip':fail('Update must be under data/updates/*.zip')
    if not source.is_file() or source.stat().st_size>15_000_000:fail('Missing or too-large staged update')
    if not (ROOT/'docker-compose.yml').exists():fail('Run this inside the JARVIS project folder')
    with zipfile.ZipFile(source) as z:
        entries=verified_entries(z)
        print(f'Validated {len(entries)} project files. Your .env, data/, real printer config, and private settings will be preserved.')
        if not args.yes and input('Type APPLY to back up and install this update: ').strip()!='APPLY':
            print('Cancelled.');return
        backups=ROOT/'data'/'update_backups';backups.mkdir(parents=True,exist_ok=True)
        backup=backups/('backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        backup.mkdir()
        current=[]
        for n,_ in entries:
            dest=ROOT/n
            if dest.is_symlink():fail('Refusing to replace symlink: '+n)
            previous=backup/n
            if dest.exists():
                previous.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(dest,previous)
                current.append(n)
        (backup/'_existing_files.txt').write_text('\n'.join(current))
        print('Backup:',backup)
        written=[]
        try:
            for n,m in entries:
                destination=ROOT/n
                if destination.parent.is_symlink():fail('Unsafe destination parent: '+n)
                destination.parent.mkdir(parents=True,exist_ok=True)
                with z.open(m) as input_file, tempfile.NamedTemporaryFile(dir=destination.parent,delete=False) as temp:
                    shutil.copyfileobj(input_file,temp)
                    temp_path=Path(temp.name)
                temp_path.replace(destination)
                if n.endswith('.sh') or n=='apply_update.py':destination.chmod(0o755)
                written.append(n)
        except Exception:
            for n in written:
                previous=backup/n; target=ROOT/n
                if previous.exists():shutil.copy2(previous,target)
                else:target.unlink(missing_ok=True)
            raise
    print('Source files installed. Building Docker service now…')
    result=subprocess.run(['docker','compose','up','-d','--build'],cwd=ROOT,check=False)
    if result.returncode:
        print('Docker rebuild failed. Your old source files are saved in',backup)
        print('Inspect docker compose logs and roll back from the backup before retrying.')
        sys.exit(result.returncode)
    print('Update complete. Preserved all private settings and accounts. Backup:',backup)

if __name__=='__main__':main()
