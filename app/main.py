"""JARVIS LAN: role-based family accounts, hosted AI and extensible command centre."""
import hashlib, hmac, importlib.util, io, json, os, secrets, sqlite3, zipfile, time, math
from contextlib import asynccontextmanager
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import Depends, FastAPI, HTTPException, UploadFile, File
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import httpx
from .printers import get_status, start_monitoring

ROOT=Path(__file__).resolve().parent.parent
DATA=Path(os.getenv('JARVIS_DATA',str(ROOT/'data'))); DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'jarvis.db'; SECURITY=HTTPBasic(); PLUGINS=DATA/'plugins'; PLUGINS.mkdir(exist_ok=True)

def conn():
    c=sqlite3.connect(DB,timeout=15); c.row_factory=sqlite3.Row; return c

def hash_password(password, salt=None):
    salt=salt or secrets.token_bytes(16)
    return salt.hex()+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt,310000).hex()

def verify_password(password, encoded):
    try:
        salt, digest=encoded.split(':'); calculated=hash_password(password,bytes.fromhex(salt)).split(':')[1]
        return hmac.compare_digest(calculated,digest)
    except (ValueError,TypeError): return False

def init_db():
    with conn() as db:
        db.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN (\'admin\',\'family\')) )')
        db.execute('CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,title TEXT NOT NULL,done INTEGER NOT NULL DEFAULT 0, user_id INTEGER REFERENCES users(id))')
        db.execute('CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY,content TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, user_id INTEGER REFERENCES users(id))')
        note_cols=[r['name'] for r in db.execute('PRAGMA table_info(notes)')]
        if 'user_id' not in note_cols: db.execute('ALTER TABLE notes ADD COLUMN user_id INTEGER REFERENCES users(id)')
        cols=[r['name'] for r in db.execute('PRAGMA table_info(tasks)')]
        if 'user_id' not in cols: db.execute('ALTER TABLE tasks ADD COLUMN user_id INTEGER REFERENCES users(id)')
        db.execute('CREATE TABLE IF NOT EXISTS ai_model_preferences(user_id INTEGER PRIMARY KEY, provider TEXT NOT NULL, model TEXT NOT NULL)')
        db.execute("CREATE TABLE IF NOT EXISTS user_preferences(user_id INTEGER PRIMARY KEY, timezone TEXT NOT NULL DEFAULT 'browser')")
        count=db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if not count:
            password=os.getenv('JARVIS_PASSWORD','')
            username=os.getenv('JARVIS_USERNAME','admin')
            if len(password)<12 or password=='CHANGE_TO_A_LONG_UNIQUE_PASSWORD':
                raise RuntimeError('Set a unique JARVIS_PASSWORD (12+ characters) in .env before first launch.')
            db.execute('INSERT INTO users(username,password_hash,role) VALUES (?,?,?)',(username,hash_password(password),'admin'))
            uid=db.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone()[0]
            db.execute('UPDATE tasks SET user_id=? WHERE user_id IS NULL',(uid,))

def current_user(credentials:HTTPBasicCredentials=Depends(SECURITY)):
    with conn() as db: user=db.execute('SELECT * FROM users WHERE username=?',(credentials.username,)).fetchone()
    # Hash even when unknown to reduce account enumeration timing signal
    fallback='00'*16+':'+('00'*32)
    if not verify_password(credentials.password,user['password_hash'] if user else fallback):
        raise HTTPException(401,'Invalid username or password',headers={'WWW-Authenticate':'Basic realm="JARVIS"'})
    return {'id':user['id'],'username':user['username'],'role':user['role']}

def admin(user=Depends(current_user)):
    if user['role']!='admin':raise HTTPException(403,'Administrator access required')
    return user

@asynccontextmanager
async def lifespan(app):
    init_db(); start_monitoring(); yield

app=FastAPI(title='JARVIS LAN',version='v1',lifespan=lifespan)
app.mount('/static',StaticFiles(directory=str(ROOT/'static')),name='static')
@app.get('/')
def home(user=Depends(current_user)):
    return FileResponse(ROOT/'static'/'index.html')
@app.get('/api/me')
def me(user=Depends(current_user)):return user

# Each user controls how times appear in their own dashboard. This does not
# change the Ubuntu host's clock, stored timestamps, or other users' settings.
class TimeZoneSelection(BaseModel):
    timezone: str = Field(min_length=1, max_length=100)

def _validated_timezone(value: str) -> str:
    if value == 'browser':
        return value
    # Accept standard IANA zone names. ZoneInfo validates actual membership.
    if not all(c.isascii() and (c.isalnum() or c in '_/+-') for c in value):
        raise HTTPException(400, 'Choose a valid IANA time zone, such as America/Vancouver')
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise HTTPException(400, 'Unknown time zone. Use a name such as America/Vancouver')
    return value

@app.get('/api/preferences/timezone')
def get_user_timezone(user=Depends(current_user)):
    with conn() as db:
        row = db.execute('SELECT timezone FROM user_preferences WHERE user_id=?',(user['id'],)).fetchone()
    return {'timezone': row['timezone'] if row else 'browser'}

@app.put('/api/preferences/timezone')
def set_user_timezone(selection:TimeZoneSelection,user=Depends(current_user)):
    choice = _validated_timezone(selection.timezone)
    with conn() as db:
        db.execute('INSERT INTO user_preferences(user_id,timezone) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET timezone=excluded.timezone',(user['id'],choice))
    return {'ok':True,'timezone':choice}

class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)

@app.post('/api/account/change-password')
def change_password(value: ChangePasswordIn, user=Depends(current_user)):
    """Self-service password change for admins and family accounts."""
    if value.current_password == value.new_password:
        raise HTTPException(400, 'Choose a different new password')
    with conn() as db:
        row = db.execute('SELECT password_hash FROM users WHERE id=?', (user['id'],)).fetchone()
        if not row or not verify_password(value.current_password, row['password_hash']):
            raise HTTPException(400, 'Current password is incorrect')
        db.execute('UPDATE users SET password_hash=? WHERE id=?',
                   (hash_password(value.new_password), user['id']))
    return {'ok': True, 'message': 'Password changed. Sign in again with your new password.'}

# Approved model identifiers are stored in persistent JARVIS data, not in application files.
MODELS_FILE = DATA / 'ai_models.json'
DEFAULT_MODELS = [
    {'provider':'openrouter','model':'openrouter/free','label':'OpenRouter Free Router'},
    {'provider':'nvidia','model':'meta/llama-3.1-8b-instruct','label':'NVIDIA Llama 3.1 8B'}
]
def approved_models():
    if not MODELS_FILE.exists(): return DEFAULT_MODELS
    try:
        items=json.loads(MODELS_FILE.read_text(encoding='utf-8'))
        if not isinstance(items,list): return DEFAULT_MODELS
        return [x for x in items if isinstance(x,dict) and
                x.get('provider') in ('nvidia','openrouter') and
                isinstance(x.get('model'),str) and 0<len(x['model'])<=160 and
                isinstance(x.get('label'),str) and 0<len(x['label'])<=100][:40]
    except (OSError,ValueError,TypeError): return DEFAULT_MODELS

def selected_model(user_id):
    with conn() as db:
        row=db.execute('SELECT provider,model FROM ai_model_preferences WHERE user_id=?',(user_id,)).fetchone()
    candidates=approved_models()
    if row and any(x['provider']==row['provider'] and x['model']==row['model'] for x in candidates):
        return {'provider':row['provider'],'model':row['model']}
    desired={'provider':os.getenv('AI_PROVIDER','openrouter').lower(),
             'model':os.getenv('AI_MODEL','openrouter/free')}
    if any(x['provider']==desired['provider'] and x['model']==desired['model'] for x in candidates):
        return desired
    return {'provider':candidates[0]['provider'],'model':candidates[0]['model']} if candidates else desired

class ModelChoice(BaseModel):
    provider: str = Field(min_length=1,max_length=20)
    model: str = Field(min_length=1,max_length=160)
class ModelCatalogEntry(ModelChoice):
    label: str = Field(min_length=1,max_length=100)

@app.get('/api/models')
def models(user=Depends(current_user)):
    selected=selected_model(user['id'])
    configured={'openrouter':bool(os.getenv('OPENROUTER_API_KEY')),
                'nvidia':bool(os.getenv('NVIDIA_API_KEY'))}
    return {'models':[dict(item,configured=configured.get(item['provider'],False)) for item in approved_models()],
            'selected':selected,'can_manage':user['role']=='admin'}

@app.put('/api/models/selection')
def choose_model(choice:ModelChoice,user=Depends(current_user)):
    if not any(x['provider']==choice.provider and x['model']==choice.model for x in approved_models()):
        raise HTTPException(400,'Model is not in the administrator-approved list')
    with conn() as db:
        db.execute('INSERT INTO ai_model_preferences(user_id,provider,model) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET provider=excluded.provider,model=excluded.model',
                   (user['id'],choice.provider,choice.model))
    return {'ok':True,'selected':choice.model,'provider':choice.provider}

@app.post('/api/models/catalog')
def add_approved_model(entry:ModelCatalogEntry,user=Depends(admin)):
    if entry.provider not in ('openrouter','nvidia'):raise HTTPException(400,'Unsupported provider')
    catalog=approved_models()
    if not any(x['provider']==entry.provider and x['model']==entry.model for x in catalog):
        if len(catalog)>=40:raise HTTPException(400,'Model catalog is full')
        catalog.append(entry.model_dump())
    MODELS_FILE.write_text(json.dumps(catalog,indent=2),encoding='utf-8')
    return {'ok':True}

@app.delete('/api/models/catalog')
def remove_approved_model(choice:ModelChoice,user=Depends(admin)):
    catalog=[x for x in approved_models() if not(x['provider']==choice.provider and x['model']==choice.model)]
    MODELS_FILE.write_text(json.dumps(catalog,indent=2),encoding='utf-8')
    return {'ok':True}

@app.get('/api/status')
def status(user=Depends(current_user)):
    picked=selected_model(user['id'])
    return {'status':'ready','printers':len(get_status()),**picked}
# Read host-visible procfs counters without extra dependencies. Linux Docker shares
# kernel CPU and /proc/meminfo with the host; /app/data is a host bind mount.
# Values may be unavailable on unusual container configurations.
def _cpu_counter():
    line=Path('/proc/stat').read_text().splitlines()[0].split()
    values=[int(x) for x in line[1:]]
    idle=values[3]+(values[4] if len(values)>4 else 0)
    return sum(values), idle

def _mem_percent():
    values={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, _, value=line.partition(':')
        if key in ('MemTotal','MemAvailable'):
            values[key]=int(value.strip().split()[0])
    total=values.get('MemTotal',0)
    return round(100*(total-values['MemAvailable'])/total,1) if total and 'MemAvailable' in values else None

def _uptime_seconds():
    return int(float(Path('/proc/uptime').read_text().split()[0]))

@app.get('/api/system/telemetry')
def system_telemetry(user=Depends(current_user)):
    from shutil import disk_usage
    result={'source':'linux-host-visible','cpu_percent':None,'memory_percent':None,
            'disk_percent':None,'disk_total_gb':None,'disk_used_gb':None,
            'uptime_seconds':None,'sampled_at':int(time.time())}
    try:
        a=_cpu_counter(); time.sleep(0.15); b=_cpu_counter()
        delta=b[0]-a[0]
        if delta>0:result['cpu_percent']=round(max(0,min(100,100*(1-(b[1]-a[1])/delta))),1)
    except (OSError,ValueError,IndexError,ZeroDivisionError):pass
    try: result['memory_percent']=_mem_percent()
    except (OSError,ValueError,KeyError,ZeroDivisionError):pass
    try:
        total,used,_=disk_usage(DATA)
        result.update(disk_percent=round(used/total*100,1),
                      disk_total_gb=round(total/1073741824,1),disk_used_gb=round(used/1073741824,1))
    except (OSError,ValueError,ZeroDivisionError):pass
    try:result['uptime_seconds']=_uptime_seconds()
    except (OSError,ValueError,IndexError):pass
    return result

# Owner-managed outdoor weather location. Saved in the private data volume;
# optional WEATHER_LAT/LON environment variables remain a legacy fallback.
WEATHER_FILE = DATA / 'weather.json'
_WEATHER_CACHE = {'time': 0, 'value': None, 'coords': None}

class WeatherSettingsIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    label: str = Field(default='', max_length=80)

def _weather_coords():
    if WEATHER_FILE.is_file():
        try:
            data = json.loads(WEATHER_FILE.read_text(encoding='utf-8'))
            lat, lon = float(data['latitude']), float(data['longitude'])
            if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError('Invalid saved coordinates')
            return {'latitude':lat,'longitude':lon,'label':str(data.get('label',''))[:80],'source':'dashboard'}
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            # Do not expose malformed data or guess at another location.
            return None
    raw_lat, raw_lon = os.getenv('WEATHER_LAT','').strip(), os.getenv('WEATHER_LON','').strip()
    if not raw_lat or not raw_lon:
        return None
    try:
        lat,lon=float(raw_lat),float(raw_lon)
        if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):
            return None
        return {'latitude':lat,'longitude':lon,'label':'','source':'environment'}
    except ValueError:
        return None

@app.get('/api/settings/weather')
def weather_settings(user=Depends(admin)):
    settings = _weather_coords()
    return {'configured':bool(settings),**(settings or {}),'requires_restart':False}

@app.put('/api/settings/weather')
def save_weather_settings(value:WeatherSettingsIn,user=Depends(admin)):
    if not (math.isfinite(value.latitude) and math.isfinite(value.longitude)):
        raise HTTPException(400,'Coordinates must be finite numbers')
    label = value.label.strip()
    if any(ord(c)<32 or ord(c)==127 for c in label):
        raise HTTPException(400,'Invalid location label')
    payload={'latitude':value.latitude,'longitude':value.longitude,'label':label}
    # Atomic write into the private data mount, not into public source code.
    temp = WEATHER_FILE.with_name(WEATHER_FILE.name+'.'+secrets.token_hex(8)+'.tmp')
    try:
        with open(temp,'x',encoding='utf-8') as f:
            os.chmod(temp,0o600)
            json.dump(payload,f,ensure_ascii=True)
        temp.replace(WEATHER_FILE)
    finally:
        temp.unlink(missing_ok=True)
    _WEATHER_CACHE.update(time=0,value=None,coords=None)
    return {'ok':True,'configured':True,**payload,'source':'dashboard'}

@app.delete('/api/settings/weather')
def reset_weather_settings(user=Depends(admin)):
    WEATHER_FILE.unlink(missing_ok=True)
    _WEATHER_CACHE.update(time=0,value=None,coords=None)
    return {'ok':True,'configured':bool(_weather_coords()),'source':'environment' if _weather_coords() else 'none'}

@app.get('/api/environment')
async def environment(user=Depends(current_user)):
    settings = _weather_coords()
    if not settings:
        return {'configured': False, 'available': False}
    lat,lon=settings['latitude'],settings['longitude']
    coords=(lat,lon)
    if (_WEATHER_CACHE['value'] is not None and _WEATHER_CACHE['coords']==coords
            and time.monotonic()-_WEATHER_CACHE['time'] < 900):
        return _WEATHER_CACHE['value']
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get('https://api.open-meteo.com/v1/forecast', params={
                'latitude':lat,'longitude':lon,
                'current':'temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code',
                'daily':'temperature_2m_max,temperature_2m_min,precipitation_probability_max',
                'temperature_unit':'celsius','wind_speed_unit':'kmh','forecast_days':1,'timezone':'auto'
            })
            response.raise_for_status()
        payload = response.json(); current = payload['current']; daily = payload.get('daily',{})
        def first(key):return (daily.get(key) or [None])[0]
        labels={0:'Clear sky',1:'Mainly clear',2:'Partly cloudy',3:'Overcast',
                45:'Fog',48:'Depositing rime fog',51:'Light drizzle',53:'Drizzle',55:'Dense drizzle',
                61:'Light rain',63:'Rain',65:'Heavy rain',71:'Light snow',73:'Snow',75:'Heavy snow',
                80:'Rain showers',81:'Rain showers',82:'Heavy showers',95:'Thunderstorm'}
        value={'configured':True,'available':True,
               'temperature_c':current.get('temperature_2m'),
               'humidity_percent':current.get('relative_humidity_2m'),
               'wind_kmh':current.get('wind_speed_10m'),
               'description':labels.get(current.get('weather_code'),'Current conditions'),
               'high_c':first('temperature_2m_max'),'low_c':first('temperature_2m_min'),
               'rain_chance_percent':first('precipitation_probability_max'),
               'source':'Open-Meteo'}
        _WEATHER_CACHE.update(time=time.monotonic(), value=value, coords=coords)
        return value
    except (httpx.HTTPError, KeyError, ValueError, TypeError, IndexError):
        return {'configured':True,'available':False,'reason':'Weather provider unavailable'}

@app.get('/api/printers')
def printers(user=Depends(current_user)):return get_status()

class ChatIn(BaseModel):message:str=Field(min_length=1,max_length=4000)
@app.post('/api/chat')
async def chat(req:ChatIn,user=Depends(current_user)):
    command=req.message.strip()
    import re
    m=re.fullmatch(r'(?:please\s+)?(?:open|launch|go to|navigate to)\s+(?:google\s+chrome\s+(?:and\s+)?(?:open\s+)?|chrome\s+(?:and\s+)?(?:open\s+)?|the\s+)?(.+?)[.!]?',command,flags=re.I)
    if m:
        website=m.group(1).strip()
        if website:
            result=await browser_command(BrowserCommand(action='open',value=website),user)
            return {'reply':f"Opened {result['title'] or website} in JARVIS Browser. Go to the Browser tab to view and interact with it.",'browser_action':result}
    m=re.fullmatch(r'(?:please\s+)?(?:search (?:google |the web )?for|google)\s+(.+?)[.!]?',command,flags=re.I)
    if m:
        result=await browser_command(BrowserCommand(action='search',value=m.group(1)),user)
        return {'reply':'Opened Google search results in JARVIS Browser. Go to the Browser tab to see them.','browser_action':result}
    picked=selected_model(user['id'])
    provider=picked['provider']
    choices={'openrouter':('https://openrouter.ai/api/v1',os.getenv('OPENROUTER_API_KEY','')),
             'nvidia':('https://integrate.api.nvidia.com/v1',os.getenv('NVIDIA_API_KEY',''))}
    if provider not in choices:raise HTTPException(503,'Unsupported AI provider')
    base,key=choices[provider]
    model=picked['model']
    if not key:raise HTTPException(503,f'{provider} API key is not configured on the server')
    headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'}
    if provider=='openrouter':headers.update({'HTTP-Referer':'http://jarvis.local','X-Title':'JARVIS LAN'})
    try:
        async with httpx.AsyncClient(timeout=70) as client:
            r=await client.post(base+'/chat/completions',headers=headers,json={'model':model,'messages':[{'role':'system','content':'You are JARVIS, a helpful family assistant. Give complete, helpful, thorough responses to questions. Organize complex answers clearly, and do not cut yourself short. Never claim to have executed actions you did not execute. Do not reveal secrets.'},{'role':'user','content':req.message}],'max_tokens':min(4000,max(500,int(os.getenv('AI_MAX_TOKENS','2500'))))})
            r.raise_for_status()
        return {'reply':r.json()['choices'][0]['message']['content']}
    except (httpx.HTTPError,ValueError,KeyError,IndexError) as e:
        raise HTTPException(502,f'AI provider request failed ({type(e).__name__}); check provider, model and account quota') from e


# Browser manager: internal-only Playwright Chromium worker. Authenticated per-user sessions.
class BrowserCommand(BaseModel):
    action:str=Field(pattern=r'^(open|search|click|type|scroll|back|forward|reload|screenshot)$')
    value:str=Field(default='',max_length=2048)
    selector:str=Field(default='',max_length=200)

@app.post('/api/browser/command')
async def browser_command(cmd:BrowserCommand,user=Depends(current_user)):
    async with httpx.AsyncClient(timeout=40) as client:
        try:
            resp=await client.post('http://browser:8780/command',json={**cmd.model_dump(),'user_id':user['id']})
            if resp.status_code>=400:raise HTTPException(resp.status_code,resp.text[:300])
            return resp.json()
        except httpx.RequestError as e:raise HTTPException(503,'Browser worker unavailable. Run docker compose up -d --build.') from e

@app.get('/api/browser/screenshot')
async def browser_screenshot(user=Depends(current_user)):
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp=await client.get(f"http://browser:8780/shot/{user['id']}")
            if resp.status_code>=400:raise HTTPException(resp.status_code,'No page ready yet')
            return Response(resp.content,media_type='image/jpeg',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
        except httpx.RequestError as e:raise HTTPException(503,'Browser worker unavailable') from e

# Authenticated voice transcription proxy. The Whisper worker is internal to Docker,
# and no untrusted browser may choose the destination URL.
@app.post('/api/voice/transcribe')
async def voice_transcribe(file: UploadFile = File(...), user=Depends(current_user)):
    max_bytes = 8 * 1024 * 1024
    if (file.content_type or '').split(';')[0].strip().lower() not in ('audio/webm','audio/ogg','audio/mp4','audio/wav','audio/x-wav','audio/mpeg','application/octet-stream'):
        raise HTTPException(415, 'Unsupported recording format')
    raw = await file.read(max_bytes + 1)
    if not raw or len(raw) > max_bytes:
        raise HTTPException(413, 'Voice recording is empty or exceeds 8 MB')
    service = os.getenv('VOICE_SERVICE_URL', 'http://voice:8091').rstrip('/')
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(125, connect=5)) as client:
            response = await client.post(service+'/transcribe', files={'file': (file.filename or 'voice.webm', raw, file.content_type or 'audio/webm')})
        if response.status_code != 200:
            raise HTTPException(502, 'Voice engine error: '+response.text[:160])
        result = response.json()
        return {'text': str(result.get('text',''))[:4000]}
    except httpx.RequestError as exc:
        raise HTTPException(503, 'Voice service unavailable; check docker compose ps') from exc

# Piper model management: models and configuration files live in persistent data.
import re
from fastapi.responses import Response
VOICE_DIR=DATA/'voices'/'piper'
VOICE_DIR.mkdir(parents=True,exist_ok=True)
VOICE_NAME=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,90}$')

def installed_voices():
    return [{'id':p.stem,'name':p.stem.replace('_',' ').replace('-',' ')} for p in sorted(VOICE_DIR.glob('*.onnx'))
            if p.with_name(p.name+'.json').is_file() and VOICE_NAME.fullmatch(p.stem)]

@app.get('/api/voices')
def voices_list(user=Depends(current_user)):
    return {'voices':installed_voices()}

@app.post('/api/voices/upload')
async def voice_upload(file:UploadFile=File(...),user=Depends(admin)):
    filename=Path(file.filename or '').name
    if filename != (file.filename or '') or not (filename.endswith('.onnx') or filename.endswith('.onnx.json')):
        raise HTTPException(400,'Upload a Piper .onnx model or matching .onnx.json configuration')
    name=filename[:-10] if filename.endswith('.onnx.json') else filename[:-5]
    if not VOICE_NAME.fullmatch(name) or '..' in name:
        raise HTTPException(400,'Invalid voice filename')
    max_size=160*1024*1024 if filename.endswith('.onnx') else 256*1024
    temp=VOICE_DIR/(filename+'.uploading-'+secrets.token_hex(8))
    size=0
    try:
        with temp.open('wb') as dest:
            while True:
                chunk=await file.read(1024*1024)
                if not chunk:break
                size+=len(chunk)
                if size>max_size:raise HTTPException(413,'Voice file too large')
                dest.write(chunk)
        if size<8:raise HTTPException(400,'Voice file is empty or incomplete')
        if filename.endswith('.json'):
            try:
                details=json.loads(temp.read_text(encoding='utf-8'))
                if not isinstance(details,dict) or 'audio' not in details or 'phoneme_id_map' not in details:
                    raise ValueError('Missing Piper voice configuration fields')
            except (ValueError,UnicodeError) as exc:raise HTTPException(400,'Invalid Piper configuration JSON') from exc
        else:
            if temp.open('rb').read(16) == b'':raise HTTPException(400,'Empty model')
        os.replace(temp,VOICE_DIR/filename)
    finally:temp.unlink(missing_ok=True)
    return {'ok':True,'file':filename,'voices':installed_voices()}

@app.delete('/api/voices/{voice_id}')
def voice_delete(voice_id:str,user=Depends(admin)):
    if not VOICE_NAME.fullmatch(voice_id) or '..' in voice_id:raise HTTPException(400,'Invalid voice')
    for ext in ('.onnx','.onnx.json'):
        (VOICE_DIR/(voice_id+ext)).unlink(missing_ok=True)
    return {'ok':True}

class VoiceSpeechIn(BaseModel):
    voice:str=Field(min_length=1,max_length=91)
    text:str=Field(min_length=1,max_length=1200)
    speed:float=Field(default=1,ge=.7,le=1.3)

@app.post('/api/voice/speak')
async def voice_speak(req:VoiceSpeechIn,user=Depends(current_user)):
    if req.voice not in {v['id'] for v in installed_voices()}:raise HTTPException(404,'Voice model is not installed')
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120,connect=5)) as client:
            r=await client.post(os.getenv('VOICE_SERVICE_URL','http://voice:8091').rstrip('/')+'/speak',json=req.model_dump())
        if r.status_code!=200:raise HTTPException(502,'Speech engine error; check voice service logs')
        return Response(r.content,media_type='audio/wav',headers={'Cache-Control':'no-store'})
    except httpx.RequestError as exc:raise HTTPException(503,'Voice service unavailable') from exc

# Every dashboard query is scoped to the authenticated account.
@app.get('/api/overview')
def overview(user=Depends(current_user)):
    with conn() as db:
        pending=db.execute('SELECT count(*) FROM tasks WHERE user_id=? AND done=0',(user['id'],)).fetchone()[0]
        completed=db.execute('SELECT count(*) FROM tasks WHERE user_id=? AND done=1',(user['id'],)).fetchone()[0]
        notes=db.execute('SELECT count(*) FROM notes WHERE user_id=?',(user['id'],)).fetchone()[0]
        recent=[dict(r) for r in db.execute('SELECT title,done FROM tasks WHERE user_id=? ORDER BY id DESC LIMIT 5',(user['id'],))]
    printers=get_status()
    return {'username':user['username'],'pending_tasks':pending,'completed_tasks':completed,
            'notes':notes,'printers_total':len(printers),
            'printers_online':sum(bool(p.get('online')) for p in printers),
            'printers_printing':sum(str(p.get('gcode_state','')).upper()=='RUNNING' for p in printers),
            'recent_tasks':recent,'version':(ROOT/'VERSION').read_text().strip() if (ROOT/'VERSION').exists() else 'unknown'}

class NoteIn(BaseModel):
    content:str=Field(min_length=1,max_length=4000)

@app.get('/api/notes')
def list_notes(user=Depends(current_user)):
    with conn() as db:
        return [dict(r) for r in db.execute('SELECT id,content,created_at FROM notes WHERE user_id=? ORDER BY id DESC LIMIT 100',(user['id'],))]

@app.post('/api/notes')
def add_note(value:NoteIn,user=Depends(current_user)):
    with conn() as db:
        cursor=db.execute('INSERT INTO notes(content,user_id) VALUES (?,?)',(value.content,user['id']))
        return {'id':cursor.lastrowid,'ok':True}

@app.delete('/api/notes/{note_id}')
def delete_note(note_id:int,user=Depends(current_user)):
    with conn() as db:
        result=db.execute('DELETE FROM notes WHERE id=? AND user_id=?',(note_id,user['id']))
        if not result.rowcount:raise HTTPException(404,'Note not found')
    return {'ok':True}

class TaskIn(BaseModel):title:str=Field(min_length=1,max_length=240)
@app.get('/api/tasks')
def tasks(user=Depends(current_user)):
    with conn() as db:return [dict(r) for r in db.execute('SELECT id,title,done FROM tasks WHERE user_id=? ORDER BY done,id DESC',(user['id'],))]
@app.post('/api/tasks')
def add_task(req:TaskIn,user=Depends(current_user)):
    with conn() as db:
        cur=db.execute('INSERT INTO tasks(title,user_id) VALUES (?,?)',(req.title,user['id']))
        return {'id':cur.lastrowid,'title':req.title,'done':0}
@app.patch('/api/tasks/{task_id}')
def finish_task(task_id:int,user=Depends(current_user)):
    with conn() as db:
        cur=db.execute('UPDATE tasks SET done=1 WHERE id=? AND user_id=?',(task_id,user['id']))
        if not cur.rowcount:raise HTTPException(404,'Task not found')
    return {'ok':True}

class Appearance(BaseModel):
    title:str=Field(default='JARVIS',max_length=60)
    accent:str=Field(default='#54def5',pattern=r'^#[a-fA-F0-9]{6}$')
    background:str=Field(default='#081321',pattern=r'^#[a-fA-F0-9]{6}$')
APPEARANCE=DATA/'appearance.json'
@app.get('/api/appearance')
def appearance(user=Depends(current_user)):
    return json.loads(APPEARANCE.read_text()) if APPEARANCE.exists() else Appearance().model_dump()
@app.put('/api/appearance')
def set_appearance(value:Appearance,user=Depends(admin)):
    APPEARANCE.write_text(value.model_dump_json(),encoding='utf-8');return value

class AccountIn(BaseModel):
    username:str=Field(min_length=3,max_length=40,pattern=r'^[A-Za-z0-9_-]+$')
    password:str=Field(min_length=12,max_length=256)
    role:str=Field(default='family',pattern=r'^(admin|family)$')
@app.get('/api/users')
def users(user=Depends(admin)):
    with conn() as db:return [dict(row) for row in db.execute('SELECT id,username,role FROM users ORDER BY id')]
@app.post('/api/users')
def create_user(value:AccountIn,user=Depends(admin)):
    try:
        with conn() as db:db.execute('INSERT INTO users(username,password_hash,role) VALUES (?,?,?)',(value.username,hash_password(value.password),value.role))
    except sqlite3.IntegrityError:raise HTTPException(409,'Username already exists')
    return {'ok':True}
@app.delete('/api/users/{user_id}')
def delete_user(user_id:int,user=Depends(admin)):
    if user_id==user['id']:raise HTTPException(400,'You cannot delete your own administrator account')
    with conn() as db:
        target=db.execute('SELECT id,role FROM users WHERE id=?',(user_id,)).fetchone()
        if not target:raise HTTPException(404,'User not found')
        if target['role']=='admin' and db.execute("SELECT count(*) FROM users WHERE role='admin'").fetchone()[0]<=1:
            raise HTTPException(400,'Cannot delete last administrator')
        db.execute('DELETE FROM tasks WHERE user_id=?',(user_id,))
        db.execute('DELETE FROM notes WHERE user_id=?',(user_id,))
        db.execute('DELETE FROM users WHERE id=?',(user_id,))
    return {'ok':True}

# ZIP upload is intentionally administrator-only. Uploaded Python code is fully trusted:
# review before enabling; restart is required so it runs during normal startup.
@app.get('/api/plugins')
def plugin_list(user=Depends(current_user)):
    names=sorted(p.stem for p in PLUGINS.glob('*.py') if not p.name.startswith('_'))
    return {'plugins':names,'can_install':user['role']=='admin'}
@app.post('/api/plugins/upload')
async def upload_plugin(file:UploadFile=File(...),user=Depends(admin)):
    if not (file.filename or '').lower().endswith('.zip'):raise HTTPException(400,'Upload a .zip plugin archive')
    content=await file.read(1024*1024+1)
    if len(content)>1024*1024:raise HTTPException(413,'Plugin ZIP exceeds 1 MB')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members=archive.infolist()
            # One top-level plugin .py file; no hidden paths, symlinks, bytecode or extra contents.
            if len(members)!=1:raise HTTPException(400,'ZIP must contain exactly one root-level Python file')
            member=members[0];name=member.filename
            if not name.endswith('.py') or '/' in name or '\\' in name or not name[:-3].isidentifier() or name.startswith('_'):
                raise HTTPException(400,'Invalid plugin filename')
            if (member.external_attr>>16)&0o170000==0o120000:raise HTTPException(400,'Symlinks forbidden')
            if member.file_size>512*1024:raise HTTPException(413,'Plugin file too large')
            target=PLUGINS/name
            if target.exists():raise HTTPException(409,'Plugin exists; delete manually after review before replacing')
            source=archive.read(member)
            compile(source,name,'exec')
            target.write_bytes(source)
            return {'ok':True,'plugin':name,'requires_restart':True,'warning':'Review code before restarting; plugins execute with server privileges.'}
    except (zipfile.BadZipFile,SyntaxError) as e:raise HTTPException(400,'Invalid Python plugin archive') from e

# Administrator-installed plugins are trusted arbitrary Python code. They need app restart.
# Plugins added via ZIP are loaded with imports at startup only, not during upload.
def register_plugins():
    for item in sorted(PLUGINS.glob('*.py')):
        if item.name.startswith('_'):continue
        spec=importlib.util.spec_from_file_location('jarvis_plugin_'+item.stem,item)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        if hasattr(module,'register'):module.register(app)
register_plugins()


# Updates are uploaded to persistent storage, never executed or extracted in the web container.
# A server administrator must review and apply them on the Ubuntu host with ./apply_update.py.
UPDATES=DATA/'updates'; UPDATES.mkdir(exist_ok=True)
UPDATE_ALLOWED={'app/','static/','plugins/','tests/','config/printers.example.json',
    'Dockerfile','docker-compose.yml','requirements.txt','README.md','LICENSE',
    '.env.example','.gitignore','setup.py','setup.sh','reset_password.py',
    'README_ONE_CLICK.md','apply_update.py','update_worker.py','install_update_service.sh','FEATURE_BUILD_PROMPT.md','VERSION'}

def update_file_list(raw:bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos=[i for i in archive.infolist() if not i.is_dir()]
            if not infos or len(infos)>250: raise ValueError('Archive must contain 1–250 files')
            names=[i.filename for i in infos]
            # Accept a repo ZIP containing exactly one top-level directory.
            segments={n.split('/')[0] for n in names if '/' in n}
            prefix=next(iter(segments))+'/' if len(segments)==1 and all('/' in n for n in names) else ''
            stripped=[]
            for info in infos:
                name=info.filename
                if not name.startswith(prefix):raise ValueError('Mixed root folders are not supported')
                name=name[len(prefix):]
                bits=Path(name).parts
                if (not name or name.startswith('/') or '\\' in name or '..' in bits or
                    ':' in name or len(name)>240 or info.file_size>2_000_000):
                    raise ValueError('Unsafe or oversized ZIP entry')
                if ((info.external_attr>>16)&0o170000)==0o120000:
                    raise ValueError('Symlink in ZIP is not allowed')
                if name.startswith(('data/','config/printers.json')) or name in ('.env','config/cameras.json'):
                    raise ValueError('Private files must not be included in updates: '+name)
                if not any(name==allowed or (allowed.endswith('/') and name.startswith(allowed)) for allowed in UPDATE_ALLOWED):
                    raise ValueError('Unexpected project file: '+name)
                stripped.append(name)
            if len(stripped)!=len(set(stripped)):raise ValueError('Duplicate files')
            if 'app/main.py' not in stripped or 'Dockerfile' not in stripped:
                raise ValueError('Upload a complete JARVIS project ZIP containing app/main.py and Dockerfile')
            if sum(i.file_size for i in infos)>30_000_000:raise ValueError('Uncompressed files exceed 30 MB')
            version='unspecified'
            if 'VERSION' in stripped:
                idx=stripped.index('VERSION')
                version=archive.read(infos[idx]).decode('utf-8','replace')[:50].strip()
            return {'version':version,'files':stripped,'size':len(raw)}
    except zipfile.BadZipFile as exc:
        raise ValueError('Invalid ZIP file') from exc

@app.get('/api/updates')
def updates(user=Depends(admin)):
    return [{'id':q.name,'size':q.stat().st_size} for q in sorted(UPDATES.glob('*.zip'),reverse=True)]

@app.post('/api/updates/upload')
async def upload_update(file:UploadFile=File(...),user=Depends(admin)):
    if not (file.filename or '').lower().endswith('.zip'):
        raise HTTPException(400,'Please select a JARVIS .zip update')
    raw=await file.read(15_000_001)
    if len(raw)>15_000_000:raise HTTPException(413,'Update ZIP exceeds 15 MB')
    try:info=update_file_list(raw)
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    digest=hashlib.sha256(raw).hexdigest()
    filename=digest[:20]+'.zip'
    destination=UPDATES/filename
    destination.write_bytes(raw)
    return {'ok':True,'id':filename,'sha256':digest,**info,
            'next_step':'On the Ubuntu host run: python3 apply_update.py --file data/updates/'+filename}


class ApplyUpdateRequest(BaseModel):
    update_id: str = Field(pattern=r'^[0-9a-f]{20}\.zip$')
    password: str = Field(min_length=1, max_length=256)

@app.post('/api/updates/apply')
def apply_uploaded_update(request: ApplyUpdateRequest, user=Depends(admin)):
    """Queue only; separate trusted host service installs after validating ZIP again."""
    with conn() as db:
        row=db.execute('SELECT password_hash FROM users WHERE id=?',(user['id'],)).fetchone()
    if not row or not verify_password(request.password,row['password_hash']):
        raise HTTPException(403,'Confirm your current administrator password')
    heartbeat=UPDATES/'worker_heartbeat.json'
    import time
    try:
        hb=json.loads(heartbeat.read_text())
        if time.time()-float(hb.get('timestamp',0))>30:
            raise ValueError('stale')
    except (OSError, ValueError, TypeError):
        raise HTTPException(503,'Ubuntu updater worker is offline. Run ./install_update_service.sh once on the Ubuntu host.')
    archive=UPDATES/request.update_id
    if not archive.is_file():raise HTTPException(404,'ZIP not found')
    import time
    try:update_file_list(archive.read_bytes())
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    state_file=UPDATES/'update_status.json'
    if state_file.exists():
        try:
            state=json.loads(state_file.read_text())
            if state.get('state') in ('queued','running'):
                raise HTTPException(409,'An update is already queued or running')
        except json.JSONDecodeError:pass
    # The host worker watches the persistent volume. No Docker socket is mounted into JARVIS.
    if (UPDATES/'update_request.json').exists():
        raise HTTPException(409,'An update request is already pending')
    payload={'id':request.update_id,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
             'requested_by':user['username'],'requested_at':int(time.time())}
    temp=UPDATES/'update_request.tmp'
    temp.write_text(json.dumps(payload))
    temp.replace(UPDATES/'update_request.json')
    state_file.write_text(json.dumps({'state':'queued','id':request.update_id,'message':'Awaiting Ubuntu update service'}))
    return {'ok':True,'message':'Update queued. The Ubuntu update service will apply it shortly.'}

@app.get('/api/updates/status')
def update_status(user=Depends(admin)):
    f=UPDATES/'update_status.json'
    if not f.exists():return {'state':'idle','message':'No update requested'}
    try:return json.loads(f.read_text())
    except (ValueError,OSError):return {'state':'unknown','message':'Unable to read update status'}
