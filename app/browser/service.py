"""Isolated browser worker: internal Docker port only. Not exposed to LAN."""
import asyncio, os, ipaddress, socket
from urllib.parse import urlparse,quote_plus
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright

app=FastAPI()
engine=None
browser=None
contexts={}
locks={}
class Cmd(BaseModel):
    user_id:int=Field(ge=1)
    action:str=Field(pattern=r'^(open|search|click|type|scroll|back|forward|reload|screenshot)$')
    value:str=Field(default='',max_length=2048)
    selector:str=Field(default='',max_length=200)

async def safe_url(url):
    parsed=urlparse(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:raise HTTPException(400,'Only public HTTPS pages allowed')
    host=parsed.hostname
    if host in ('localhost','metadata.google.internal') or host.endswith(('.local','.internal','.localhost')):raise HTTPException(400,'Internal network targets not permitted')
    try:
        addresses=await asyncio.get_event_loop().getaddrinfo(host,443,type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):raise HTTPException(400,'Private or non-public address blocked')
    except socket.gaierror:raise HTTPException(400,'Host cannot be resolved')
    return url

@app.on_event('startup')
async def start():
    global engine,browser
    engine=await async_playwright().start()
    browser=await engine.chromium.launch(headless=True,args=['--no-sandbox'])

@app.on_event('shutdown')
async def stop():
    for ctx in contexts.values():await ctx.close()
    if browser:await browser.close()
    if engine:await engine.stop()

async def page_for(uid):
    if uid not in contexts:
        ctx=await browser.new_context(viewport={'width':1280,'height':800},accept_downloads=False,permissions=[],service_workers='block')
        await ctx.route('**/*',guard_route)
        contexts[uid]=ctx
    ctx=contexts[uid]
    if not ctx.pages: return await ctx.new_page()
    return ctx.pages[0]

async def guard_route(route):
    try:await safe_url(route.request.url)
    except Exception:await route.abort();return
    await route.continue_()

@app.post('/command')
async def command(cmd:Cmd):
    lock=locks.setdefault(cmd.user_id,asyncio.Lock())
    async with lock:
        p=await page_for(cmd.user_id)
        try:
            a,v=cmd.action,cmd.value.strip()
            if a=='open':
                if not v:raise HTTPException(400,'Enter a URL or website name')
                if not v.startswith('https://'):
                    v={'youtube':'https://www.youtube.com','google':'https://www.google.com','chrome':'https://www.google.com','gmail':'https://mail.google.com','wikipedia':'https://www.wikipedia.org'}.get(v.lower(), 'https://'+v)
                await safe_url(v)
                await p.goto(v,wait_until='domcontentloaded',timeout=25000)
            elif a=='search':
                if not v:raise HTTPException(400,'Enter a search')
                await p.goto('https://www.google.com/search?q='+quote_plus(v),wait_until='domcontentloaded',timeout=25000)
            elif a=='click':
                if not v:raise HTTPException(400,'Enter link/button text')
                await p.get_by_text(v,exact=False).first.click(timeout=6000)
            elif a=='type':
                if not v:raise HTTPException(400,'Enter text')
                selector=cmd.selector or 'input:visible'
                await p.locator(selector).first.fill(v,timeout=6000)
            elif a=='scroll':await p.mouse.wheel(0,-550 if v.lower()=='up' else 550)
            elif a=='back':await p.go_back(wait_until='domcontentloaded',timeout=15000)
            elif a=='forward':await p.go_forward(wait_until='domcontentloaded',timeout=15000)
            elif a=='reload':await p.reload(wait_until='domcontentloaded',timeout=15000)
            elif a=='screenshot':pass
            await asyncio.sleep(.4)
            return {'ok':True,'title':await p.title(),'url':p.url}
        except HTTPException:raise
        except Exception as e:raise HTTPException(400,str(e)[:240])

@app.get('/shot/{user_id}')
async def shot(user_id:int):
    if user_id not in contexts:raise HTTPException(404,'Open a site first')
    async with locks.setdefault(user_id,asyncio.Lock()):
        img=await contexts[user_id].pages[0].screenshot(type='jpeg',quality=76,timeout=12000)
    return Response(img,media_type='image/jpeg',headers={'Cache-Control':'no-store'})
