"""Read-only Bambu MQTT monitor. No printer commands are published."""
import copy
import json
import logging
import os
import ssl
import threading
import time
from pathlib import Path
from paho.mqtt import client as mqtt

log = logging.getLogger(__name__)
_state = {}
_lock = threading.Lock()
_printers = []

def load_printers():
    global _printers
    path = Path(os.getenv('PRINTERS_CONFIG', 'config/printers.json'))
    if not path.exists():
        _printers = []
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    out = []
    for p in data.get('printers', []):
        if not all(p.get(k) for k in ('id', 'host', 'serial', 'access_code_env')):
            continue
        code = os.getenv(p['access_code_env'], '')
        if not code:
            log.warning('No access code env for %s', p['id'])
            continue
        out.append({**p, '_code': code})
    _printers = out
    return out

def normalize_print(payload):
    p = payload.get('print', {})
    if not isinstance(p, dict):
        return {}
    keys = ('gcode_state', 'mc_percent', 'mc_remaining_time', 'nozzle_temper',
            'nozzle_target_temper', 'bed_temper', 'bed_target_temper', 'subtask_name',
            'layer_num', 'total_layer_num', 'wifi_signal')
    return {k: p[k] for k in keys if k in p}

def update_state(printer_id, payload):
    incoming = normalize_print(payload)
    if not incoming:
        return
    with _lock:
        current = _state.setdefault(printer_id, {})
        current.update(incoming)  # MQTT reports can contain partial updates
        current['last_seen'] = time.time()

def get_status():
    now = time.time()
    with _lock:
        states = copy.deepcopy(_state)
    return [dict(id=p['id'], name=p.get('name', p['id']),
                 camera_url=p.get('camera_url', ''),
                 online=now-states.get(p['id'], {}).get('last_seen', 0) < 120,
                 **states.get(p['id'], {})) for p in _printers]

def monitor_one(p):
    delay = 5
    while True:
        try:
            # Bambu printer brokers frequently use self-signed TLS certificates.
            c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            c.username_pw_set('bblp', p['_code'])
            c.tls_set(cert_reqs=ssl.CERT_NONE)
            c.tls_insecure_set(True)  # Only connect to trusted LAN printer IPs
            c.on_connect = lambda client, userdata, flags, reason_code, properties: (
                client.subscribe(f"device/{p['serial']}/report") if reason_code == 0
                else log.warning('MQTT connection rejected for %s: %s', p['id'], reason_code)
            )
            def received(client, userdata, msg):
                try:
                    update_state(p['id'], json.loads(msg.payload))
                except (ValueError, TypeError):
                    log.warning('Invalid MQTT JSON from %s', p['id'])
            c.on_message = received
            c.connect(p['host'], 8883, keepalive=60)
            c.loop_forever(retry_first_connection=True)
        except Exception as exc:
            log.warning('Printer %s disconnected: %s', p['id'], exc)
            time.sleep(delay)
            delay = min(delay * 2, 60)

def start_monitoring():
    for p in load_printers():
        threading.Thread(target=monitor_one, args=(p,), daemon=True,
                         name='printer-' + p['id']).start()
