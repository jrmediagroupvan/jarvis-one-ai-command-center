#!/usr/bin/env python3
"""Trusted Ubuntu-side updater. Install once with install_update_service.sh.

The web container has NO host Docker socket and cannot perform privileged operations.
Only a validated, admin-password-approved update request reaches this worker.
Only install ZIP files whose source you trust; they contain executable Python.
"""
import hashlib, json, os, subprocess, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
UPDATES=ROOT/'data'/'updates'
REQ=UPDATES/'update_request.json'
STATUS=UPDATES/'update_status.json'
HEARTBEAT=UPDATES/'worker_heartbeat.json'

def atomic_write(path, content):
    target=path.with_suffix('.tmp')
    target.write_text(json.dumps(content))
    target.replace(path)

def status(state, message, id=None):
    atomic_write(STATUS, {'state':state,'message':message,'id':id,
                          'time':datetime.now(timezone.utc).isoformat()})

def process():
    if not REQ.exists():return
    try:
        request=json.loads(REQ.read_text())
        name=request['id']
        if not (len(name)==24 and name.endswith('.zip') and all(c in '0123456789abcdef' for c in name[:-4])):
            raise ValueError('Invalid update identifier')
        archive=(UPDATES/name).resolve()
        if archive.parent!=UPDATES.resolve() or archive.is_symlink() or not archive.is_file():
            raise ValueError('Update archive missing or unsafe')
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=request['sha256']:
            raise ValueError('ZIP checksum mismatch')
        REQ.unlink()
        status('running','Installing reviewed ZIP and rebuilding JARVIS…',name)
        command=[sys.executable,str(ROOT/'apply_update.py'),'--file',str(archive),'--yes']
        result=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              text=True,timeout=600)
        log=UPDATES/'last_update.log'
        log.write_text(result.stdout[-30000:])
        status('success' if result.returncode==0 else 'failed',
               'Update installed. Reload the dashboard.' if result.returncode==0 else
               'Update failed. See data/updates/last_update.log on Ubuntu.',name)
    except Exception as exc:
        REQ.unlink(missing_ok=True)
        (UPDATES/'last_update.log').write_text(traceback.format_exc())
        status('failed',str(exc)[:300])

def main():
    UPDATES.mkdir(parents=True,exist_ok=True)
    while True:
        atomic_write(HEARTBEAT,{'timestamp':time.time()})
        process()
        time.sleep(3)
if __name__=='__main__':main()
