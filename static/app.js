const $=id=>document.getElementById(id);
async function api(path,options={}){const res=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});if(!res.ok)throw new Error((await res.text()).slice(0,220));return res.json()}
function el(tag,text,className){const node=document.createElement(tag);node.textContent=text??'';if(className)node.className=className;return node}

// Time zone preferences are account-scoped and stored in JARVIS SQLite.
// 'browser' retains the previous automatic local browser behavior.
let jarvisTimeZone = 'browser';
const jarvisBrowserTimeZone = (() => {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; }
  catch (_error) { return 'UTC'; }
})();
function jarvisTimeOptions(options = {}) {
  return jarvisTimeZone === 'browser' ? options : { ...options, timeZone: jarvisTimeZone };
}
function jarvisTime(date, options) {
  return new Intl.DateTimeFormat(undefined, jarvisTimeOptions(options)).format(date);
}
function jarvisTimezoneDisplay() {
  const zone = jarvisTimeZone === 'browser' ? jarvisBrowserTimeZone : jarvisTimeZone;
  let abbreviation = '';
  try {
    const parts = new Intl.DateTimeFormat('en-CA', {timeZone: zone, timeZoneName: 'short'}).formatToParts(new Date());
    abbreviation = parts.find(p=>p.type==='timeZoneName')?.value || '';
  } catch (_error) { /* Browser timezone may be configured unusually. */ }
  return (jarvisTimeZone === 'browser' ? 'Automatic · ' : '') + zone.replaceAll('_',' ') + (abbreviation ? ' · ' + abbreviation : '');
}
function renderJarvisTimezone() {
  for (const id of ['timezoneCurrent','hud2-timezone-label']) {
    if ($(id)) $(id).textContent = jarvisTimezoneDisplay();
  }
  if ($('systemClock')) $('systemClock').textContent = jarvisTime(new Date(),{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  if (typeof renderNeonClock === 'function') renderNeonClock();
  if (typeof hud2Clock === 'function') hud2Clock();
}
function updateCustomZoneVisibility() {
  const label = $('customTimezoneLabel');
  if (label) label.hidden = $('timezoneSelect').value !== 'custom';
}
async function loadTimezonePreference() {
  try {
    const result = await api('/preferences/timezone');
    jarvisTimeZone = result.timezone || 'browser';
    const select = $('timezoneSelect');
    if (select) {
      if ([...select.options].some(opt => opt.value === jarvisTimeZone)) {
        select.value = jarvisTimeZone;
        $('customTimezone').value = '';
      } else {
        select.value = 'custom';
        $('customTimezone').value = jarvisTimeZone;
      }
      updateCustomZoneVisibility();
    }
    if ($('timezoneStatus')) $('timezoneStatus').textContent = '';
  } catch (error) {
    if ($('timezoneStatus')) $('timezoneStatus').textContent = 'Could not load saved time zone: ' + error.message;
  }
  renderJarvisTimezone();
}
$('timezoneSelect')?.addEventListener('change', updateCustomZoneVisibility);
$('timezoneForm')?.addEventListener('submit', async event => {
  event.preventDefault();
  const select = $('timezoneSelect');
  const timezone = select.value === 'custom' ? $('customTimezone').value.trim() : select.value;
  const status = $('timezoneStatus');
  if (!timezone) { status.textContent='Enter an IANA time zone.'; return; }
  try {
    if (timezone !== 'browser') new Intl.DateTimeFormat('en-US', {timeZone: timezone});
  } catch (_error) { status.textContent='Invalid time zone. Example: America/Vancouver'; return; }
  $('saveTimezoneButton').disabled = true;
  status.textContent = 'Saving…';
  try {
    const result=await api('/preferences/timezone', {method:'PUT',body:JSON.stringify({timezone})});
    jarvisTimeZone = result.timezone;
    status.textContent = 'Saved. All JARVIS clocks now use ' + jarvisTimezoneDisplay() + '.';
    renderJarvisTimezone();
  } catch(error) { status.textContent = 'Could not save time zone: ' + error.message; }
  finally { $('saveTimezoneButton').disabled = false; }
});
loadTimezonePreference();
function show(name){document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('active',p.id===name));document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('active',b.dataset.section===name));if(name==='dashboard')loadDashboard();if(name==='notes')loadNotes();if(name==='tasks')loadTasks();if(name==='printers')loadPrinters();if(name==='browser')refreshBrowserView();if(name==='plugins')loadPlugins();if(name==='accounts')loadAccounts();if(name==='updates')loadUpdates();if(name==='voices')loadVoiceManager();if(name==='chat'||name==='style')loadModelChoices();if(name==='style')loadWeatherSettings()}
document.querySelectorAll('.nav').forEach(b=>b.addEventListener('click',()=>show(b.dataset.section)));
document.querySelectorAll('[data-goto]').forEach(b=>b.addEventListener('click',()=>{show(b.dataset.goto);if(b.dataset.goto==='chat')$('message').focus();if(b.dataset.goto==='notes')$('noteBody').focus();if(b.dataset.goto==='tasks')$('taskTitle').focus()}));
async function loadDashboard(){try{
 const [s,overview]=await Promise.all([api('/status'),api('/overview')]);
 $('model').textContent=s.provider+' · '+s.model;
 if($('heroProviderBadge'))$('heroProviderBadge').textContent=s.provider+' · '+s.model;
 if($('providerEcho'))$('providerEcho').textContent=s.provider;
 $('printerCount').textContent=overview.printers_online+' / '+overview.printers_total;
 if($('printerEcho'))$('printerEcho').textContent=overview.printers_online+'/'+overview.printers_total;
 $('pendingCount').textContent=overview.pending_tasks;
 if($('taskEcho'))$('taskEcho').textContent=String(overview.pending_tasks);
 $('noteCount').textContent=overview.notes;
 if($('noteEcho'))$('noteEcho').textContent=String(overview.notes);
 const recent=$('recentTasks');recent.replaceChildren();
 if(!overview.recent_tasks.length)recent.append(el('p','No tasks yet. Add one to get started.','muted'));
 overview.recent_tasks.forEach(t=>recent.append(el('p',(t.done?'✓ ':'○ ')+t.title,t.done?'muted':'')));
 updateNeonDashboard(s,overview);
 updateHud2Overview(s,overview);
 }catch(e){$('model').textContent='Unable to load';console.warn(e)}}
function bubble(t,who){const b=el('div',t,'bubble '+(who||''));$('chatHistory').append(b);$('chatHistory').scrollTop=$('chatHistory').scrollHeight;return b}
let chatInFlight=false;
$('chatForm').addEventListener('submit',async e=>{e.preventDefault();const text=$('message').value.trim();if(!text)return;chatInFlight=true;$('message').value='';bubble(text,'user');const reply=bubble('Thinking…');try{const result=await api('/chat',{method:'POST',body:JSON.stringify({message:text})});reply.textContent=result.reply;if(result.browser_action){show('browser')}if($('speakReplies').checked)await speak(reply.textContent)}catch(err){reply.textContent='AI unavailable: '+err.message}finally{chatInFlight=false;if(wakeEnabled)scheduleWake(500)}});
async function loadTasks(){const area=$('taskList');area.replaceChildren();try{for(const t of await api('/tasks')){const row=el('div','','task'+(t.done?' done':''));row.append(el('span',t.title));if(!t.done){const b=el('button','Done');b.onclick=async()=>{await api('/tasks/'+t.id,{method:'PATCH'});loadTasks()};row.append(b)}area.append(row)}}catch(e){area.append(el('p',e.message))}}
$('taskForm').addEventListener('submit',async e=>{e.preventDefault();const title=$('taskTitle').value.trim();if(!title)return;try{await api('/tasks',{method:'POST',body:JSON.stringify({title})});$('taskTitle').value='';loadTasks()}catch(err){alert(err.message)}});
async function loadPrinters(){const area=$('printerList');area.replaceChildren();try{const list=await api('/printers');$('printerSummary').textContent=list.filter(p=>p.online).length+' of '+list.length+' printers online · '+list.filter(p=>String(p.gcode_state||'').toUpperCase()==='RUNNING').length+' printing';if(!list.length)area.append(el('p','No printers configured. Follow README setup.'));for(const p of list){const card=el('article','','printer');card.append(el('span',p.online?'● CONNECTED':'○ OFFLINE'),el('h3',p.name),el('p','State: '+(p.gcode_state??'Unknown')),el('p','Job: '+(p.subtask_name??'—')));const bar=document.createElement('progress');bar.value=Math.min(100,Math.max(0,Number(p.mc_percent)||0));bar.max=100;card.append(bar,el('p',(p.mc_percent??0)+'% · Remaining '+(p.mc_remaining_time??'—')+' min'),el('small','Nozzle: '+(p.nozzle_temper??'—')+' °C · Bed: '+(p.bed_temper??'—')+' °C'));if(p.camera_url){const u=new URL(p.camera_url,location.href);if(['https:','http:'].includes(u.protocol)){const iframe=document.createElement('iframe');iframe.src=u.href;iframe.title=p.name+' camera';iframe.loading='lazy';iframe.referrerPolicy='no-referrer';card.append(iframe)}}else card.append(el('p','Camera: configure a browser-compatible feed URL.','muted'));area.append(card)}}catch(e){area.append(el('p',e.message))}}
$('refreshPrinters').onclick=loadPrinters;setInterval(()=>{if($('printers').classList.contains('active'))loadPrinters()},15000);
async function loadAppearance(){try{const a=await api('/appearance');$('systemName').value=a.title;$('accent').value=a.accent;$('background').value=a.background;applyAppearance(a)}catch(e){console.error(e)}}
function applyAppearance(a){document.documentElement.style.setProperty('--accent',a.accent);document.documentElement.style.setProperty('--bg',a.background);$('brand').textContent=a.title;document.title=a.title+' Command Center';document.querySelectorAll('.theme-preset.active').forEach(b=>b.classList.remove('active'));const brandField=$('systemName');if(brandField&&document.activeElement!==brandField)brandField.value=a.title;const accentField=$('accent');if(accentField&&document.activeElement!==accentField)accentField.value=a.accent;const bgField=$('background');if(bgField&&document.activeElement!==bgField)bgField.value=a.background;}
$('appearanceForm').addEventListener('submit',async e=>{e.preventDefault();try{const a=await api('/appearance',{method:'PUT',body:JSON.stringify({title:$('systemName').value,accent:$('accent').value,background:$('background').value})});applyAppearance(a);alert('Appearance saved.')}catch(err){alert(err.message)}});
function initThemePresets(){document.querySelectorAll('.theme-preset').forEach(btn=>btn.addEventListener('click',()=>{const next={title:btn.dataset.title||$('systemName').value||'JARVIS',accent:btn.dataset.accent||$('accent').value,background:btn.dataset.background||$('background').value};$('systemName').value=next.title;$('accent').value=next.accent;$('background').value=next.background;document.querySelectorAll('.theme-preset').forEach(b=>b.classList.remove('active'));btn.classList.add('active');applyAppearance(next);}));}
function startSystemClock(){const target=$('systemClock');if(!target)return;const render=()=>{const now=new Date();target.textContent=jarvisTime(now, {hour:'2-digit',minute:'2-digit',second:'2-digit'});};render();setInterval(render,1000);}

async function loadPlugins(){const area=$('pluginsList');area.replaceChildren();try{const p=await api('/plugins');p.plugins.forEach(n=>area.append(el('p','◈ '+n)))}catch(e){area.append(el('p',e.message))}}
// Local microphone recording -> JARVIS -> private Whisper service -> transcript.
// Browser Web Speech recognition is deliberately not used for input.
// Wake-word mode is explicit opt-in: browser microphone permission and a user click are required.
// Server-side Whisper transcribes short recordings; browser speech recognition is not used.
let recorder=null,inputStream=null,chunks=[],voiceTimer=null,recording=false,converting=false;
let wakeEnabled=false,wakeBusy=false,wakeWaiting=false,wakeEpoch=0,wakeTimer=null;
let speechEpoch=0,activeUtterance=null;
const wakePattern=/\b(?:hey[\s,]+)?jarvis\b[\s,!.?:-]*/i;
const voiceStatus=text=>{ $('voiceStatus').textContent=text; if($('hud2-core-voice'))$('hud2-core-voice').textContent=/Listening|Recording/i.test(text)?'LISTENING':/Transcribing|Thinking/i.test(text)?'PROCESSING':'READY'; };
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function cancelSpeech(){speechEpoch++;window.speechSynthesis?.cancel();if(playbackAudio){playbackAudio.pause();playbackAudio.src='';playbackAudio=null}activeUtterance=null}
function segmentSpeech(text){
 const cleaned=String(text||'').replace(/\s+/g,' ').trim();
 const sentences=cleaned.match(/[^.!?]+[.!?]*/g)||[cleaned];
 const pieces=[];let cur='';
 for(const sentence of sentences){
  const part=sentence.trim();if(!part)continue;
  if(cur.length+part.length+1>170 && cur){pieces.push(cur);cur=''}
  if(part.length>170){if(cur){pieces.push(cur);cur=''}for(let i=0;i<part.length;i+=170)pieces.push(part.slice(i,i+170));}
  else cur+=(cur?' ':'')+part;
 }
 if(cur)pieces.push(cur);return pieces;
}
// Formatting is stripped ONLY for synthesized speech; chat display remains unchanged.
function cleanForSpeech(input){
 let s=String(input||'');
 // Code fences contain syntax that is rarely helpful when read aloud.
 s=s.replace(/```[\s\S]*?```/g,' Code example omitted. ');
 s=s.replace(/!\[([^\]]*)\]\([^)]+\)/g,'$1');
 s=s.replace(/\[([^\]]+)\]\([^)]+\)/g,'$1');
 s=s.replace(/<https?:\/\/[^>]+>/g,' link ');
 s=s.replace(/`([^`]+)`/g,'$1');
 s=s.replace(/<\/?(?:strong|em|b|i|p|div|span|h[1-6]|ul|ol|li|blockquote)(?:\s[^>]*)?>/gi,' ');
 // Tables and thematic breaks.
 s=s.replace(/^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/gm,'');
 s=s.replace(/^\s*[-*_]{3,}\s*$/gm,'');
 s=s.replace(/\s*\|\s*/g,', ');
 s=s.replace(/^\s{0,3}#{1,6}\s+/gm,'');
 s=s.replace(/^\s*>\s?/gm,'');
 s=s.replace(/^\s*(?:[-*+]\s+|\d+[.)]\s+)/gm,'');
 s=s.replace(/\*\*([^*]+)\*\*/g,'$1');
 s=s.replace(/__([^_]+)__/g,'$1');
 s=s.replace(/~~([^~]+)~~/g,'$1');
 s=s.replace(/(?<!\w)[*_]([^*_\n]+)[*_](?!\w)/g,'$1');
 // Drop stray decoration, but preserve sentence punctuation and hyphenated words.
 s=s.replace(/[★•◆►]/g,' ');
 s=s.replace(/\*+/g,'');
 s=s.replace(/\r/g,'').replace(/\n\s*\n+/g,'. ').replace(/\n+/g,'. ');
 s=s.replace(/\s+/g,' ').replace(/\.\s*\./g,'.').trim();
 return s;
}

let playbackAudio=null;
async function speak(text){
 cancelSpeech();const epoch=speechEpoch;
 const pieces=segmentSpeech(cleanForSpeech(text)).slice(0,160);
 const selected=$('voiceSelect').value;
 if(selected.startsWith('piper:')){
  for(const piece of pieces){
   if(epoch!==speechEpoch)break;
   try{
    const response=await fetch('/api/voice/speak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({voice:selected.slice(6),text:piece,speed:Number($('speechRate').value||1)})});
    if(!response.ok)throw Error((await response.text()).slice(0,180));
    const url=URL.createObjectURL(await response.blob());
    try{await new Promise(resolve=>{const a=new Audio(url);playbackAudio=a;a.onended=resolve;a.onerror=resolve;a.play().catch(resolve)})}
    finally{URL.revokeObjectURL(url);playbackAudio=null}
   }catch(err){voiceStatus('Voice playback error: '+err.message);break}
  }
 }else if(window.speechSynthesis){
  const voice=window.speechSynthesis.getVoices().find(v=>v.voiceURI===selected);
  for(const piece of pieces){
   if(epoch!==speechEpoch)break;
   await new Promise(resolve=>{
    const u=new SpeechSynthesisUtterance(piece);activeUtterance=u;
    if(voice)u.voice=voice;u.rate=Number($('speechRate')?.value||1);
    u.onend=resolve;u.onerror=resolve;window.speechSynthesis.speak(u);
    setTimeout(resolve,Math.max(12000,piece.length*120));
   });
  }
 }
 if(epoch===speechEpoch){activeUtterance=null;if(wakeEnabled&&!wakeWaiting)scheduleWake(900)}
}
async function listVoices(){
 const select=$('voiceSelect'),chosen=select.value||localStorage.getItem('jarvisVoice')||'';
 select.replaceChildren(new Option('Browser default',''));
 if(window.speechSynthesis)window.speechSynthesis.getVoices().forEach(v=>select.add(new Option('Browser · '+v.name+' ('+v.lang+')',v.voiceURI)));
 try{const models=await api('/voices');models.voices.forEach(v=>select.add(new Option('Piper · '+v.name,'piper:'+v.id)))}catch(e){console.warn('Voice list:',e)}
 if([...select.options].some(o=>o.value===chosen))select.value=chosen;
}
$('voiceSelect').addEventListener('change',()=>localStorage.setItem('jarvisVoice',$('voiceSelect').value));
if(window.speechSynthesis)window.speechSynthesis.onvoiceschanged=listVoices;
listVoices();
async function loadVoiceManager(){
 const area=$('installedVoices');area.replaceChildren();
 try{const data=await api('/voices');if(!data.voices.length)area.append(el('p','No complete Piper voice pairs installed.','muted'));
  for(const voice of data.voices){const line=el('div','','task');line.append(el('span',voice.name));
   const del=el('button','Delete');del.onclick=async()=>{if(!confirm('Delete voice '+voice.id+'?'))return;await api('/voices/'+encodeURIComponent(voice.id),{method:'DELETE'});loadVoiceManager();listVoices()};line.append(del);area.append(line)}
 }catch(e){area.append(el('p',e.message))}
}
$('voiceUploadForm').addEventListener('submit',async e=>{
 e.preventDefault();const file=$('voiceFile').files[0];if(!file)return;
 $('voiceUploadStatus').textContent='Uploading '+file.name+'…';
 const form=new FormData();form.append('file',file);
 try{const r=await fetch('/api/voices/upload',{method:'POST',body:form});const body=await r.json();if(!r.ok)throw Error(body.detail||'Upload failed');
 $('voiceUploadStatus').textContent='Saved '+file.name+'. Upload matching model/config if needed.';loadVoiceManager();listVoices()}
 catch(err){$('voiceUploadStatus').textContent='Upload failed: '+err.message}
});
$('stopSpeech').onclick=()=>{cancelSpeech();if(wakeEnabled)scheduleWake(400)};
function releaseMic(){clearTimeout(voiceTimer);voiceTimer=null;if(inputStream){inputStream.getTracks().forEach(t=>t.stop());inputStream=null}recording=false;$('micButton').textContent='🎙 Start voice command';$('micButton').setAttribute('aria-pressed','false')}
async function transcribeBlob(blob){
 const form=new FormData();const ext=blob.type.includes('mp4')?'mp4':'webm';form.append('file',blob,'voice.'+ext);
 const r=await fetch('/api/voice/transcribe',{method:'POST',body:form});const body=await r.json();if(!r.ok)throw Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));return (body.text||'').trim();
}
async function submitPhrase(phrase){
 $('message').value=phrase;voiceStatus('Heard: '+phrase);
 $('chatForm').requestSubmit();
}
async function sendAudio(blob){converting=true;$('micButton').disabled=true;voiceStatus('Transcribing speech locally…');
 try{const phrase=await transcribeBlob(blob);if(!phrase){voiceStatus('No words detected. Try speaking closer to your microphone.');return}await submitPhrase(phrase)}
 catch(e){voiceStatus('Voice error: '+e.message)}finally{converting=false;$('micButton').disabled=false}}
function capture(duration=6000){
 return new Promise(async(resolve,reject)=>{
  let stream,rec,part=[],timer;
  try{
   stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
   const mime=['audio/webm;codecs=opus','audio/webm','audio/mp4'].find(x=>MediaRecorder.isTypeSupported(x));
   rec=new MediaRecorder(stream,mime?{mimeType:mime}:undefined);
   rec.ondataavailable=e=>{if(e.data.size)part.push(e.data)};
   rec.onerror=()=>{clearTimeout(timer);stream.getTracks().forEach(t=>t.stop());reject(Error('Microphone recorder failed'))};
   rec.onstop=()=>{clearTimeout(timer);stream.getTracks().forEach(t=>t.stop());resolve(new Blob(part,{type:rec.mimeType||mime||'audio/webm'}))};
   rec.start(250);timer=setTimeout(()=>rec.state==='recording'&&rec.stop(),duration);
   wakeCaptureStop=()=>{if(rec.state==='recording')rec.stop()};
  }catch(e){stream?.getTracks().forEach(t=>t.stop());reject(e)}
 });
}
let wakeCaptureStop=null;
function scheduleWake(ms=250){clearTimeout(wakeTimer);if(!wakeEnabled)return;wakeTimer=setTimeout(()=>wakeLoop(wakeEpoch),ms)}
async function wakeLoop(epoch){
 if(!wakeEnabled||epoch!==wakeEpoch||wakeBusy)return;
 if(converting||recording||chatInFlight||(window.speechSynthesis?.speaking||playbackAudio)){scheduleWake(900);return}
 wakeBusy=true;voiceStatus(wakeWaiting?'Listening for your question…':'Listening for “Hey JARVIS”…');
 try{
  const blob=await capture(wakeWaiting?7000:4200);
  if(!wakeEnabled||epoch!==wakeEpoch)return;
  const phrase=await transcribeBlob(blob);
  if(wakeWaiting){
   wakeWaiting=false;
   if(phrase){await submitPhrase(phrase);voiceStatus('Question received: '+phrase)}
   else voiceStatus('No question heard. Say “Hey JARVIS” to try again.');
  }else if(wakePattern.test(phrase)){
   const command=phrase.replace(wakePattern,'').trim().replace(/^[,\s.!?]+/,'');
   if(command){await submitPhrase(command);voiceStatus('Wake phrase detected: '+command)}
   else{
    wakeWaiting=true;
    voiceStatus('Wake word detected. Responding…');
    if($('wakeGreetingPreference').checked)await speak(nextWakeGreeting());
    if(wakeEnabled&&epoch===wakeEpoch)voiceStatus('Listening for your command…');
   }
  }
 }catch(e){voiceStatus('Wake listening error: '+e.message+'. Try manual voice mode.');disableWake();return}
 finally{wakeBusy=false;if(wakeEnabled&&epoch===wakeEpoch&&!wakeWaiting)scheduleWake(500);else if(wakeEnabled&&wakeWaiting)scheduleWake(100)}
}
// A user explicitly enables listening first; preference is stored only for that
// account and browser. Never attempt to acquire microphone permissions silently.
let voicePreferenceKey='';
const wakeGreetings=[
 'How can I help you?',
 'At your service. What can I do for you?',
 'I am listening. What is your command?',
 'Ready when you are. How may I assist?',
 'Hello. What would you like me to do?'
];
let greetingIndex=-1;
function nextWakeGreeting(){
 // Shuffle by avoiding an identical consecutive greeting.
 let next=Math.floor(Math.random()*wakeGreetings.length);
 if(next===greetingIndex)next=(next+1)%wakeGreetings.length;
 greetingIndex=next;return wakeGreetings[next];
}
function persistWakePreferences(){
 if(!voicePreferenceKey)return;
 try {localStorage.setItem(voicePreferenceKey,JSON.stringify({auto:!!$('autoWakePreference').checked,greet:!!$('wakeGreetingPreference').checked}));}
 catch(_e){if($('wakePreferenceStatus'))$('wakePreferenceStatus').textContent='Browser settings could not be saved.';}
}
async function loadWakePreferences(){
 try{
  const identity=await api('/me');
  voicePreferenceKey='jarvis-wake-v193-'+identity.id+'-'+identity.username;
  let saved={};try{saved=JSON.parse(localStorage.getItem(voicePreferenceKey)||'{}')||{}}catch(_e){}
  $('autoWakePreference').checked=saved.auto===true;
  $('wakeGreetingPreference').checked=saved.greet!==false;
  if(saved.auto!==true)return;
  if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){
   voiceStatus('Automatic listening is saved, but microphone access needs HTTPS or localhost on this browser.');return;
  }
  let permission='prompt';
  try{if(navigator.permissions?.query)permission=(await navigator.permissions.query({name:'microphone'})).state;}catch(_e){}
  if(permission==='granted') await startWakeListening(false);
  else voiceStatus('Automatic wake word is saved. Click Enable “Hey JARVIS” to grant microphone permission.');
 }catch(_e){/* No changes when account identity cannot be read. */}
}
function disableWake(){
 wakeEnabled=false;wakeWaiting=false;wakeEpoch++;clearTimeout(wakeTimer);
 wakeCaptureStop?.();wakeCaptureStop=null;
 $('wakeButton').textContent='Enable “Hey JARVIS”';$('wakeButton').setAttribute('aria-pressed','false');
 if($('hud2-core-voice'))$('hud2-core-voice').textContent='READY';
 voiceStatus('Wake-word listening stopped.');
}
async function startWakeListening(requestPermission=true){
 if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){
  voiceStatus('Microphone unavailable. Use HTTPS or localhost, and allow microphone access in your browser.');return false;
 }
 try{
  // Request permission on a user action only, or reuse existing granted permission.
  if(requestPermission){const stream=await navigator.mediaDevices.getUserMedia({audio:true});stream.getTracks().forEach(t=>t.stop());}
  else{const state=await navigator.permissions.query({name:'microphone'});if(state.state!=='granted')return false;}
  wakeEnabled=true;wakeWaiting=false;wakeEpoch++;
  $('wakeButton').textContent='Disable “Hey JARVIS”';$('wakeButton').setAttribute('aria-pressed','true');
  voiceStatus('Listening for “Hey JARVIS”…');scheduleWake(150);return true;
 }catch(e){voiceStatus('Could not start listening: '+e.message);return false;}
}
$('autoWakePreference').addEventListener('change',async()=>{
 const enabled=$('autoWakePreference').checked;persistWakePreferences();
 if(enabled&&!wakeEnabled){
  // This checkbox is a deliberate user activation, permission may be requested.
  const ok=await startWakeListening(true);
  if(!ok){$('wakePreferenceStatus').textContent='Saved. Microphone access is still required to start.';return;}
 }
 if(!enabled&&wakeEnabled)disableWake();
 $('wakePreferenceStatus').textContent=enabled?'Automatic wake listening enabled for this browser.':'Automatic wake listening off.';
});
$('wakeGreetingPreference').addEventListener('change',persistWakePreferences);
$('wakeButton').onclick=async()=>{
 if(wakeEnabled){disableWake();$('autoWakePreference').checked=false;persistWakePreferences();return;}
 const ok=await startWakeListening(true);
 if(ok){$('autoWakePreference').checked=true;persistWakePreferences();}
};
window.addEventListener('pagehide',disableWake);
loadWakePreferences();
async function startRecording(){if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){voiceStatus('Recording unavailable. Allow microphone access in a secure browser context.');return}
 disableWake();
 try{cancelSpeech();inputStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});const supported=['audio/webm;codecs=opus','audio/webm','audio/mp4'].find(t=>MediaRecorder.isTypeSupported(t));recorder=new MediaRecorder(inputStream,supported?{mimeType:supported}:undefined);chunks=[];
 recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};
 recorder.onerror=()=>{voiceStatus('Recording error. Check the microphone and try again.');releaseMic()};
 recorder.onstop=()=>{const blob=new Blob(chunks,{type:recorder.mimeType||'audio/webm'});releaseMic();if(blob.size>0)sendAudio(blob);else voiceStatus('No audio captured. Please try again.')} ;
 recorder.start(250);recording=true;$('micButton').textContent='■ Stop & transcribe';$('micButton').setAttribute('aria-pressed','true');voiceStatus('Recording… click Stop & transcribe when finished (max 60 seconds).');voiceTimer=setTimeout(()=>{if(recording&&recorder?.state==='recording')recorder.stop()},60000);
 }catch(e){releaseMic();voiceStatus('Microphone failed: '+e.message)}
}
$('micButton').onclick=()=>{if(converting)return;if(recording){if(recorder?.state==='recording')recorder.stop();return}startRecording()};
async function initRole(){try{const u=await api('/me');document.querySelectorAll('.admin-only').forEach(n=>n.hidden=u.role!=='admin')}catch(e){console.warn('Login unavailable',e)}}
$('pluginForm').onsubmit=async e=>{e.preventDefault();const file=$('pluginZip').files[0];if(!file)return;if(!confirm('Plugins can execute arbitrary code on your Ubuntu server. Have you reviewed the Python source?'))return;const data=new FormData();data.append('file',file);try{const r=await fetch('/api/plugins/upload',{method:'POST',body:data});const result=await r.json();if(!r.ok)throw Error(JSON.stringify(result));$('pluginStatus').textContent='Uploaded '+result.plugin+'. Restart JARVIS to load it.';loadPlugins()}catch(err){$('pluginStatus').textContent='Upload failed: '+err.message}};
async function loadAccounts(){const area=$('accountsList');area.replaceChildren();try{for(const u of await api('/users')){const row=el('div',u.username+' — '+u.role,'task');const del=el('button','Delete');del.onclick=async()=>{if(!confirm('Delete account '+u.username+' and its tasks?'))return;try{await api('/users/'+u.id,{method:'DELETE'});loadAccounts()}catch(e){alert(e.message)}};row.append(del);area.append(row)}}catch(e){area.append(el('p',e.message))}}
$('accountForm').onsubmit=async e=>{e.preventDefault();try{await api('/users',{method:'POST',body:JSON.stringify({username:$('newUsername').value,password:$('newPassword').value,role:$('newRole').value})});$('newPassword').value='';$('accountStatus').textContent='Account created';loadAccounts()}catch(err){$('accountStatus').textContent=err.message}};
loadDashboard();loadAppearance();initRole();initThemePresets();startSystemClock();initThemePresets();startSystemClock();

// Self-service password change: supported for admins and family members.
$('changePasswordForm').addEventListener('submit', async event => {
 event.preventDefault();
 const current=$('currentPassword').value;
 const next=$('newOwnPassword').value;
 if(next!==$('confirmOwnPassword').value){$('passwordStatus').textContent='New passwords do not match.';return}
 if(next.length<12){$('passwordStatus').textContent='Use at least 12 characters.';return}
 try{
  const result=await api('/account/change-password',{method:'POST',body:JSON.stringify({current_password:current,new_password:next})});
  $('changePasswordForm').reset();$('passwordStatus').textContent=result.message;
 }catch(e){$('passwordStatus').textContent='Password not changed: '+e.message}
});

let pendingUpdateId='';
async function loadUpdates(){
 const area=$('updatesList');area.replaceChildren();
 try{const items=await api('/updates');if(!items.length)area.append(el('p','No uploaded updates'));
 for(const item of items)area.append(el('p',item.id+' · '+Math.round(item.size/1024)+' KB'));
 const state=await api('/updates/status');$('applyStatus').textContent=state.message || state.state;
 }catch(e){area.append(el('p',e.message))}
}
$('updateForm').addEventListener('submit',async e=>{
 e.preventDefault();const file=$('updateZip').files[0];if(!file)return;
 if(!confirm('Only upload trusted ZIP source code. Continue?'))return;
 const form=new FormData();form.append('file',file);$('updateStatus').textContent='Uploading and validating…';
 try{const r=await fetch('/api/updates/upload',{method:'POST',body:form});const value=await r.json();if(!r.ok)throw Error(value.detail||'Upload rejected');
 pendingUpdateId=value.id;$('applyUpdateButton').disabled=false;
 $('updateStatus').textContent='Ready: version '+value.version+' · SHA-256 '+value.sha256+'. Confirm password and click Apply.';
 loadUpdates();
 }catch(err){$('updateStatus').textContent='Upload failed: '+err.message}
});
$('applyUpdateButton').onclick=async()=>{
 if(!pendingUpdateId)return;
 if(!confirm('Install this trusted ZIP and restart JARVIS? The dashboard will be briefly unavailable.'))return;
 const password=$('applyPassword').value;
 if(!password){$('applyStatus').textContent='Enter your administrator password.';return}
 $('applyStatus').textContent='Queueing update…';
 try{await api('/updates/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({update_id:pendingUpdateId,password})});
 $('applyPassword').value='';$('applyUpdateButton').disabled=true;
 $('applyStatus').textContent='Queued. Waiting for Ubuntu update service…';
 watchUpdateStatus();
 }catch(e){$('applyStatus').textContent='Could not apply: '+e.message}
};



let watchingUpdate=false;
async function watchUpdateStatus(){
 if(watchingUpdate)return;
 watchingUpdate=true;
 for(let attempt=0;attempt<120;attempt++){
  await new Promise(resolve=>setTimeout(resolve,3000));
  try{
   const state=await api('/updates/status');
   $('applyStatus').textContent=(state.state||'unknown').toUpperCase()+': '+(state.message||'');
   if(['success','failed'].includes(state.state)){watchingUpdate=false;return}
  }catch(_err){$('applyStatus').textContent='JARVIS is restarting. Waiting for the dashboard…'}
 }
 watchingUpdate=false;
}

// Notes are stored server-side and scoped to the current user.
async function loadNotes(){
 const list=$('noteList');list.replaceChildren();
 try{
  const items=await api('/notes');
  if(!items.length)list.append(el('p','No notes yet. Save your first idea above.','muted'));
  for(const note of items){
   const card=el('article','','note-card');
   card.append(el('small',note.created_at+' UTC','muted'),el('p',note.content));
   const remove=el('button','Delete');remove.type='button';
   remove.onclick=async()=>{if(!confirm('Delete this note?'))return;try{await api('/notes/'+note.id,{method:'DELETE'});await loadNotes();loadDashboard()}catch(err){$('noteStatus').textContent=err.message}};
   card.append(remove);list.append(card);
  }
 }catch(err){list.append(el('p','Could not load notes: '+err.message))}
}
$('noteForm').addEventListener('submit',async event=>{
 event.preventDefault();const content=$('noteBody').value.trim();if(!content)return;
 try{await api('/notes',{method:'POST',body:JSON.stringify({content})});$('noteBody').value='';$('noteStatus').textContent='Note saved';await loadNotes();loadDashboard()}
 catch(err){$('noteStatus').textContent='Could not save: '+err.message}
});


async function loadModelChoices(){
 try{
  const payload=await api('/models'),select=$('chatModelSelect');
  select.replaceChildren();
  for(const item of payload.models){
    const opt=document.createElement('option');
    opt.value=item.provider+'|'+item.model;
    opt.textContent=item.label+' · '+item.provider+(item.configured?'':' (API key missing)');
    opt.disabled=!item.configured;select.append(opt);
  }
  select.value=payload.selected.provider+'|'+payload.selected.model;
  const area=$('modelCatalogList');area.replaceChildren();
  if(payload.can_manage)for(const item of payload.models){
    const row=el('div',item.label+' — '+item.provider+' / '+item.model,'task');
    const remove=el('button','Remove');
    remove.type='button';
    remove.onclick=async()=>{if(!confirm('Remove this approved model?'))return;
      await api('/models/catalog',{method:'DELETE',body:JSON.stringify({provider:item.provider,model:item.model})});await loadModelChoices()};
    row.append(remove);area.append(row);
  }
 }catch(e){$('modelSwitchStatus').textContent='Models unavailable: '+e.message}
}
$('saveModelChoice').onclick=async()=>{
 const [provider,...parts]=$('chatModelSelect').value.split('|');
 try{await api('/models/selection',{method:'PUT',body:JSON.stringify({provider,model:parts.join('|')})});
 $('modelSwitchStatus').textContent='Model selected for your account.';
 await loadDashboard()}catch(e){$('modelSwitchStatus').textContent=e.message}
};
$('approvedModelForm').onsubmit=async e=>{
 e.preventDefault();
 try{await api('/models/catalog',{method:'POST',body:JSON.stringify({
 provider:$('adminModelProvider').value,label:$('adminModelLabel').value.trim(),model:$('adminModelId').value.trim()})});
 $('modelAdminStatus').textContent='Added to approved models.';await loadModelChoices()
 }catch(err){$('modelAdminStatus').textContent=err.message}
};
loadModelChoices();

// v1.7 cyberpunk command dashboard. All values are retrieved from existing APIs.
function updateNeonDashboard(status,overview){
 const put=(id,v)=>{const node=$(id);if(node)node.textContent=String(v??'—')};
 put('neonModel',status.provider+' · '+status.model);put('neonProviderSide',status.provider);
 put('neonPrinterStatus',overview.printers_online+' of '+overview.printers_total+' online');
 put('neonPrintSide',overview.printers_online+'/'+overview.printers_total);
 put('neonPending',overview.pending_tasks);put('neonCompleted',overview.completed_tasks);
 put('neonNotes',overview.notes);put('neonPrinting',overview.printers_printing);
 put('neonVersion',overview.version);
 loadNeonPrinters();
}
async function loadNeonPrinters(){const area=$('neonPrinterList');if(!area)return;
 try{const printers=await api('/printers');area.replaceChildren();
 if(!printers.length){area.append(el('p','No printers configured. Add them to your printer configuration.','muted'));return}
 for(const p of printers.slice(0,4)){
 const row=el('div','','neon-row'),block=el('div');
 block.append(el('strong',p.name||'Printer'),el('small',p.online?(p.gcode_state||'Online'):'Offline'));
 const progress=document.createElement('progress');progress.max=100;progress.value=Math.min(100,Math.max(0,Number(p.mc_percent)||0));
 row.append(block,progress,el('span',p.online?(p.mc_percent??0)+'%':'Offline','neon-state'));area.append(row)
 }
 }catch(err){area.replaceChildren(el('p','Printer status unavailable','muted'))}
}
function renderNeonClock(){const n=new Date();const t=$('neonTime'),c=$('neonClock'),d=$('neonDate');
 if(t)t.textContent=jarvisTime(n,{hour:'2-digit',minute:'2-digit'});
 if(c)c.textContent=jarvisTime(n,{hour:'2-digit',minute:'2-digit',second:'2-digit'});
 if(d)d.textContent=jarvisTime(n,{weekday:'long',month:'short',day:'numeric',year:'numeric'}).toUpperCase();}
renderNeonClock();setInterval(renderNeonClock,1000);
$('quickChatForm')?.addEventListener('submit',e=>{e.preventDefault();const msg=$('quickChatInput').value.trim();if(!msg)return;$('message').value=msg;$('quickChatInput').value='';$('chatForm').requestSubmit()});

// v1.8.0: real Linux telemetry. Chart only draws observed samples, no fake history.
const jarvisTelemetryHistory=[];
function jarvisFmtUptime(sec){if(!Number.isFinite(sec))return '—';const d=Math.floor(sec/86400),h=Math.floor(sec%86400/3600),m=Math.floor(sec%3600/60);return (d?d+'d ':'')+h+'h '+m+'m'}
function jarvisTelemetryLine(values){return values.map((v,i)=>{const x=values.length===1?300:i/(values.length-1)*600;return x.toFixed(1)+','+(230-Math.max(0,Math.min(100,v))*2.3).toFixed(1)}).join(' ')}
async function refreshJarvisTelemetry(){
 if(!$('dashboard')?.classList.contains('active'))return;
 try{
  const data=await api('/system/telemetry');
  const fmt=x=>x===null||x===undefined?'—':Number(x).toFixed(1)+'%';
  const put=(id,value)=>{if($(id))$(id).textContent=value};
  put('neonCpu',fmt(data.cpu_percent));put('neonMemory',fmt(data.memory_percent));
  hud2Telemetry(data);
  put('neonUptime',jarvisFmtUptime(data.uptime_seconds));
  put('neonCpuSide',fmt(data.cpu_percent));put('neonMemSide',fmt(data.memory_percent));
  put('neonDiskSide',fmt(data.disk_percent));
  put('neonDiskDetails',data.disk_used_gb==null?'Linux filesystem':data.disk_used_gb+' / '+data.disk_total_gb+' GB');
  put('cityDiskUsed', data.disk_percent == null ? '—' : fmt(data.disk_percent));
  put('cityDiskTotal', data.disk_used_gb == null ? 'Disk unavailable' : data.disk_used_gb + ' / ' + data.disk_total_gb + ' GB');
  if($('cityDiskMeter')) $('cityDiskMeter').value=Number.isFinite(Number(data.disk_percent))?Math.max(0,Math.min(100,Number(data.disk_percent))):0;
  put('cityDiagSample', data.sampled_at ? 'Sampled '+ jarvisTime(new Date(data.sampled_at*1000),{hour:'2-digit',minute:'2-digit',second:'2-digit'}) : 'Live Linux host metrics');
  put('neonTelemetrySource','Real Linux samples · '+jarvisTelemetryHistory.length+' collected');
  if(data.cpu_percent!=null&&data.memory_percent!=null){
    jarvisTelemetryHistory.push({cpu:Number(data.cpu_percent),memory:Number(data.memory_percent)});
    if(jarvisTelemetryHistory.length>60)jarvisTelemetryHistory.shift();
    const cpu=jarvisTelemetryHistory.map(x=>x.cpu),mem=jarvisTelemetryHistory.map(x=>x.memory);
    if($('neonCpuLine'))$('neonCpuLine').setAttribute('points',jarvisTelemetryLine(cpu));
    if($('neonMemLine'))$('neonMemLine').setAttribute('points',jarvisTelemetryLine(mem));
  }
 }catch(err){console.warn('Telemetry unavailable:',err)}
}
refreshJarvisTelemetry();
setInterval(refreshJarvisTelemetry,10000);

// Browser manager controls. Runs in a separate internal Chromium worker, not desktop Chrome.
async function browserAction(action,value='',selector=''){
 const status=$('browserStatus');if(status)status.textContent='Working: '+action+'…';
 try{const r=await api('/browser/command',{method:'POST',body:JSON.stringify({action,value,selector})});if(status)status.textContent=(r.title||'Page')+' · '+r.url;refreshBrowserView();return r}
 catch(e){if(status)status.textContent='Browser error: '+e.message;return null}
}
async function refreshBrowserView(){const img=$('browserScreenshot');if(!img)return;img.src='/api/browser/screenshot?t='+Date.now()}
$('browserGoForm')?.addEventListener('submit',e=>{e.preventDefault();browserAction('open',$('browserAddress').value)});
$('browserSearchForm')?.addEventListener('submit',e=>{e.preventDefault();browserAction('search',$('browserQuery').value)});
$('browserClickForm')?.addEventListener('submit',e=>{e.preventDefault();browserAction('click',$('browserClickText').value)});
$('browserTypeForm')?.addEventListener('submit',e=>{e.preventDefault();browserAction('type',$('browserTypeText').value)});
document.querySelectorAll('[data-browser]').forEach(b=>b.addEventListener('click',()=>browserAction(b.dataset.browser,b.dataset.value||'')));
$('browserRefresh')?.addEventListener('click',refreshBrowserView);


// v1.9.1 clean cyan HUD: only real data, no simulated readings or camera stills.
function hud2Put(id,value){const node=$(id);if(node)node.textContent=String(value??'—')}
function hud2Clock(){
 const n=new Date();const time=jarvisTime(n,{hour:'2-digit',minute:'2-digit'});
 hud2Put('hud2-clock',time);hud2Put('hud2-foot-clock',time);
 hud2Put('hud2-date',jarvisTime(n,{weekday:'long',month:'long',day:'numeric',year:'numeric'}).toUpperCase());
}
hud2Clock();setInterval(hud2Clock,1000);
function hud2Telemetry(data){
 const fields=[['cpu','cpu_percent'],['memory','memory_percent'],['disk','disk_percent']];
 for(const [display,source] of fields){
  const value=data[source];const valid=value!==null&&value!==undefined&&Number.isFinite(Number(value));
  hud2Put('hud2-'+display,valid?Number(value).toFixed(1)+'%':'—');
  const meter=$('hud2-'+display+'-meter');if(meter)meter.value=valid?Math.min(100,Math.max(0,Number(value))):0;
 }
 hud2Put('hud2-uptime',data.uptime_seconds==null?'—':jarvisFmtUptime(data.uptime_seconds));
 hud2Put('hud2-disk-details',data.disk_total_gb==null?'—':data.disk_used_gb+' / '+data.disk_total_gb+' GB');
}
function updateHud2Overview(status,overview){
 hud2Put('hud2-provider',String(status.provider||'Unknown').toUpperCase());
 hud2Put('hud2-model',String(status.model||'—'));
 hud2Put('hud2-printer-small',overview.printers_online+' / '+overview.printers_total+' ONLINE');
 hud2Put('hud2-pending',overview.pending_tasks);
 hud2Put('hud2-notes',overview.notes);
 hud2Put('hud2-version',overview.version);
 hud2Put('hud2-ai-state',status.status==='ready'?'READY':'CHECKING');
 hud2Put('hud2-top-status','SYSTEM CONNECTED');
 hud2Put('hud2-foot-status','Printers: '+overview.printers_online+'/'+overview.printers_total+' online · Pending tasks: '+overview.pending_tasks);
 const area=$('hud2-activity-list');if(area){area.replaceChildren();
   if(!overview.recent_tasks?.length)area.append(el('div','No recent tasks.','hud2-muted'));
   for(const task of (overview.recent_tasks||[]).slice(0,3)){
    const line=el('div','','hud2-activity-item');line.append(el('span',task.done?'✓':'○'));line.append(el('div',task.title));area.append(line);
   }
 }
 loadHud2Printers();
}
function hud2PrinterTemp(value){return value==null||value===''?'—':Number.isFinite(Number(value))?Number(value).toFixed(0)+'°C':'—'}
function hud2CameraUrl(value){
 try{const url=new URL(value,location.href);return ['http:','https:'].includes(url.protocol)?url.href:null}catch{return null}
}
async function loadHud2Printers(){
 const area=$('hud2-printer-list');if(!area||!$('dashboard')?.classList.contains('active'))return;
 try{
  const printers=await api('/printers');area.replaceChildren();
  hud2Put('hud2-printer-count',printers.length+' TOTAL');
  if(!printers.length){
   const empty=el('div','','hud2-empty');empty.append(el('strong','No printers configured'),el('p','Add your Bambu printers to config/printers.json and set their access codes in .env. The live camera and temperatures will appear here.'));
   const button=el('button','Open printer monitor');button.type='button';button.onclick=()=>show('printers');empty.append(button);area.append(empty);return;
  }
  for(const p of printers.slice(0,4)){
   const card=el('article','','hud2-printer');
   const camera=el('div','','hud2-printer-camera');
   const url=p.camera_url?hud2CameraUrl(p.camera_url):null;
   if(url){
    const iframe=document.createElement('iframe');iframe.src=url;iframe.loading='lazy';iframe.title=(p.name||'Printer')+' configured camera';iframe.referrerPolicy='no-referrer';camera.append(iframe);
   }else{camera.append(el('span','▣','hud2-camera-symbol'),el('small','CAMERA NOT CONFIGURED'))}
   const info=el('div','','hud2-printer-info');
   const headline=el('div','','hud2-printer-name');headline.append(el('strong',p.name||'Unnamed printer'));
   const state=String(p.gcode_state||'').toUpperCase();
   headline.append(el('span',p.online?(state==='RUNNING'?'PRINTING':state||'ONLINE'):'OFFLINE','hud2-printer-badge'+(p.online?' ok':'')));
   info.append(headline);
   info.append(el('div','State: '+(p.online?(p.gcode_state||'Connected'):'Offline'),'hud2-printer-sub'));
   info.append(el('div','Nozzle: '+hud2PrinterTemp(p.nozzle_temper),'hud2-printer-sub'));
   info.append(el('div','Bed: '+hud2PrinterTemp(p.bed_temper),'hud2-printer-sub'));
   if(state==='RUNNING'&&p.mc_percent!=null){
    const progress=document.createElement('progress');progress.max=100;progress.value=Math.min(100,Math.max(0,Number(p.mc_percent)||0));info.append(progress);
    info.append(el('small',p.mc_percent+'% complete'));
   }
   card.append(camera,info);area.append(card);
  }
 }catch(error){area.replaceChildren(el('div','Printer monitor unavailable.','hud2-empty'));console.warn('HUD printer error',error)}
}
// This panel deliberately mirrors AI Chat in-memory; conversations are not stored in the browser.
function hud2ReflectChat(){
 const log=$('chatHistory'),dest=$('hud2-conversation-list');if(!log||!dest)return;
 const nodes=[...log.querySelectorAll('.bubble')].slice(-8);dest.replaceChildren();
 for(const node of nodes){
  const row=el('div','','hud2-convo-row');row.append(el('span',node.classList.contains('user')?'YOU':'JARVIS'));
  row.append(el('p',node.textContent||''));dest.append(row);
 }
 dest.scrollTop=dest.scrollHeight;
 hud2Put('hud2-chat-state',chatInFlight?'Processing request…':'Ready for a command');
}
if($('chatHistory')){
 new MutationObserver(hud2ReflectChat).observe($('chatHistory'),{subtree:true,childList:true,characterData:true});
 hud2ReflectChat();
}
async function loadHud2Weather(){
 if(!$('hud2-weather-unavailable'))return;
 try{
  const r=await api('/environment');
  if(!r.available){$('hud2-weather-live').hidden=true;$('hud2-weather-unavailable').hidden=false;
   hud2Put('hud2-weather-label',r.configured?'UNAVAILABLE':'SETUP REQUIRED');return}
  $('hud2-weather-live').hidden=false;$('hud2-weather-unavailable').hidden=true;
  hud2Put('hud2-weather-label','LIVE OUTDOOR');
  const metric=x=>x==null?'—':Number(x).toFixed(0);
  hud2Put('hud2-temperature',metric(r.temperature_c)+'°C');
  hud2Put('hud2-weather-description',r.description||'Current conditions');
  hud2Put('hud2-humidity',metric(r.humidity_percent)+'%');
  hud2Put('hud2-wind',metric(r.wind_kmh)+' km/h');
  hud2Put('hud2-high-low',metric(r.high_c)+'° / '+metric(r.low_c)+'°C');
  hud2Put('hud2-rain',r.rain_chance_percent==null?'—':metric(r.rain_chance_percent)+'%');
 }catch(err){$('hud2-weather-live').hidden=true;$('hud2-weather-unavailable').hidden=false;hud2Put('hud2-weather-label','UNAVAILABLE')}
}
loadHud2Weather();setInterval(()=>{if($('dashboard')?.classList.contains('active')){loadHud2Weather();loadHud2Printers()}},60000);


// Admin-only persistent weather location. Coordinates are stored in data/weather.json.
async function loadWeatherSettings(){
 if(!$('weatherSettings'))return;
 try{
  const value=await api('/settings/weather');
  $('weatherLatitude').value=value.configured ? String(value.latitude) : '';
  $('weatherLongitude').value=value.configured ? String(value.longitude) : '';
  $('weatherLocationLabel').value=value.label||'';
  $('weatherSourceStatus').textContent=value.configured ?
   (value.source==='dashboard'?'Dashboard configured':'Using environment fallback') : 'Not configured';
 }catch(error){
  $('weatherSourceStatus').textContent='Administrator access required';
  if($('weatherSettingsStatus'))$('weatherSettingsStatus').textContent='Weather settings unavailable: '+error.message;
 }
}
$('weatherSettingsForm')?.addEventListener('submit',async event=>{
 event.preventDefault();
 const rawLat=$('weatherLatitude').value,rawLon=$('weatherLongitude').value;
 const latitude=Number(rawLat),longitude=Number(rawLon),label=$('weatherLocationLabel').value.trim();
 const status=$('weatherSettingsStatus');
 if(!rawLat||!rawLon||!Number.isFinite(latitude)||!Number.isFinite(longitude)||latitude < -90||latitude >90||longitude < -180||longitude >180){status.textContent='Enter valid latitude (-90 to 90) and longitude (-180 to 180).';return;}
 $('weatherSaveButton').disabled=true;status.textContent='Saving outdoor location…';
 try{
  await api('/settings/weather',{method:'PUT',body:JSON.stringify({latitude,longitude,label})});
  status.textContent='Location saved. The dashboard will refresh without restarting JARVIS.';
  await Promise.all([loadWeatherSettings(),loadHud2Weather()]);
 }catch(error){status.textContent='Could not save location: '+error.message;}
 finally{$('weatherSaveButton').disabled=false;}
});
$('weatherDetectButton')?.addEventListener('click',()=>{
 const status=$('weatherSettingsStatus');
 if(!navigator.geolocation){status.textContent='Browser geolocation requires HTTPS or localhost and location permission.';return;}
 status.textContent='Waiting for your browser location permission…';
 navigator.geolocation.getCurrentPosition(position=>{
  $('weatherLatitude').value=String(Number(position.coords.latitude.toFixed(6)));
  $('weatherLongitude').value=String(Number(position.coords.longitude.toFixed(6)));
  status.textContent='Coordinates filled in. Click Save outdoor location to confirm.';
 },error=>{status.textContent='Location unavailable: '+error.message;},{enableHighAccuracy:false,timeout:12000,maximumAge:60000});
});
$('weatherResetButton')?.addEventListener('click',async()=>{
 const status=$('weatherSettingsStatus');
 if(!window.confirm('Remove saved weather location? JARVIS will use any existing .env fallback, or display Weather not configured.'))return;
 try{await api('/settings/weather',{method:'DELETE'});status.textContent='Weather location reset.';await Promise.all([loadWeatherSettings(),loadHud2Weather()]);}
 catch(error){status.textContent='Could not reset location: '+error.message;}
});
