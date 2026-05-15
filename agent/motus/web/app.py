"""
MOTUS Web — interactive web interface for MOTUS Agent.

Usage:
    motus-web                     # Start server on http://localhost:8848
    motus-web --port 8848         # Custom port
    motus-web --host 0.0.0.0      # Listen on all interfaces
"""
import sys
import json
import threading
from pathlib import Path
from queue import Queue

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Flask, request, jsonify, Response, send_from_directory, render_template_string
from motus.loop import MOTUSAgent

app = Flask(__name__, static_folder="static", template_folder="templates")

# Active sessions: {session_id: {"agent": MOTUSAgent, "events": Queue, "running": bool}}
_sessions = {}
_lock = threading.Lock()

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MOTUS — The Future of Molecular Science</title>
<style>
:root{--bg:#06060f;--panel:#0b0b1a;--border:#1a1a3a;--cyan:#00d4ff;--gold:#ffb74d;--green:#00e676;--red:#ff5252;--text:#b8c5d6;--dim:#4a5568;--accent-glow:0 0 30px rgba(0,212,255,.15)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter','Segoe UI',system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);height:100dvh;height:100vh;overflow:hidden;display:flex}
@supports not (height:100dvh){body{height:100vh}}
canvas#bg{position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;opacity:.6}

/* Sidebar */
#sidebar{width:280px;min-width:280px;background:var(--panel);border-right:1px solid var(--border);display:flex;flex-direction:column;z-index:1;backdrop-filter:blur(10px)}
.sidebar-header{padding:20px;border-bottom:1px solid var(--border);text-align:center}
.sidebar-header .logo{font-size:2em;font-weight:900;background:linear-gradient(135deg,var(--cyan),#7c4dff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:2px}
.sidebar-header .tagline{font-size:.65em;color:var(--dim);text-transform:uppercase;letter-spacing:3px;margin-top:2px}
.sidebar-status{padding:16px 20px;border-bottom:1px solid var(--border)}
.sidebar-status .status-row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;font-size:.75em}
.sidebar-status .status-dot{width:7px;height:7px;border-radius:50%;display:inline-block;margin-right:6px}
.sidebar-status .dot-online{background:var(--green);box-shadow:0 0 8px var(--green)}
.sidebar-status .dot-idle{background:var(--dim)}
.sidebar-section{padding:16px 20px;border-bottom:1px solid var(--border)}
.sidebar-section .sec-title{font-size:.6em;color:var(--dim);text-transform:uppercase;letter-spacing:2px;margin-bottom:10px}
.tool-list{display:flex;flex-direction:column;gap:6px}
.tool-item{display:flex;align-items:center;gap:8px;font-size:.72em;padding:6px 10px;border-radius:8px;background:rgba(255,255,255,.02);transition:all .2s}
.tool-item .ti-icon{font-size:1em;width:20px;text-align:center}
.tool-item .ti-name{color:#8899aa}
.tool-item.active{background:rgba(0,212,255,.1);border:1px solid rgba(0,212,255,.2)}
.tool-item.active .ti-name{color:var(--cyan)}
#sessionInfo{font-size:.65em;color:var(--dim);padding:16px 20px;margin-top:auto;border-top:1px solid var(--border);font-family:'JetBrains Mono',monospace;word-break:break-all}

/* Main */
#main{flex:1;display:flex;flex-direction:column;z-index:1;min-width:0}
#topbar{padding:12px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;flex-shrink:0}
#topbar .brand{font-weight:700;font-size:.9em;color:var(--cyan)}
#topbar .sep{color:var(--dim);margin:0 4px}
#topbar .subtitle{font-size:.7em;color:var(--dim);letter-spacing:1px}
#topbar .actions{margin-left:auto;display:flex;gap:8px}
#topbar .actions button{background:rgba(255,255,255,.04);border:1px solid var(--border);color:var(--dim);padding:6px 14px;border-radius:8px;cursor:pointer;font-size:.7em;transition:all .2s}
#topbar .actions button:hover{color:#fff;border-color:var(--cyan)}

/* Chat */
#chat{flex:1;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:16px;scroll-behavior:smooth}
#chat::-webkit-scrollbar{width:4px}
#chat::-webkit-scrollbar-track{background:transparent}
#chat::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px}

/* Welcome */
.welcome{text-align:center;padding:60px 20px;animation:fadeUp .6s ease-out}
.welcome h1{font-size:3.2em;font-weight:900;background:linear-gradient(135deg,var(--cyan),#7c4dff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:12px}
.welcome .tag{font-size:1.05em;color:var(--dim);max-width:600px;margin:0 auto 40px;line-height:1.8}
.welcome .tag strong{color:var(--cyan)}
.welcome .cards{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;max-width:900px;margin:0 auto}
.welcome .card{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:18px;width:200px;cursor:pointer;transition:all .3s;text-align:left}
.welcome .card:hover{border-color:var(--cyan);transform:translateY(-3px);box-shadow:var(--accent-glow)}
.welcome .card .c-icon{font-size:1.5em;margin-bottom:8px}
.welcome .card .c-title{font-size:.78em;font-weight:600;color:#8899aa;margin-bottom:4px}
.welcome .card .c-desc{font-size:.65em;color:var(--dim);line-height:1.4}

/* Messages */
.msg{max-width:80%;animation:msgIn .35s ease-out}
.msg.user{align-self:flex-end}
.msg.bot{align-self:flex-start}
.msg .sender{font-size:.62em;margin-bottom:4px;opacity:.6;text-transform:uppercase;letter-spacing:1px}
.msg.user .sender{text-align:right;color:var(--cyan)}
.msg.bot .sender{color:#7c4dff}
.msg .bubble{padding:14px 18px;border-radius:18px;line-height:1.6;font-size:.85em}
.msg.user .bubble{background:linear-gradient(135deg,#1a3366,#1a2255);border-bottom-right-radius:4px;color:#c8ddf8}
.msg.bot .bubble{background:var(--panel);border:1px solid var(--border);border-bottom-left-radius:4px}
.msg.bot .bubble h2{font-size:1.1em;color:var(--cyan);margin:12px 0 6px}
.msg.bot .bubble h3{font-size:.95em;color:#8899cc;margin:10px 0 4px}
.msg.bot .bubble h4{font-size:.85em;color:#667;margin:8px 0 4px}
.msg.bot .bubble p{margin:6px 0}
.msg.bot .bubble ul, .msg.bot .bubble ol{margin:4px 0 4px 20px}
.msg.bot .bubble li{margin:2px 0}
.msg.bot .bubble code{background:rgba(0,0,0,.4);padding:2px 7px;border-radius:4px;font-size:.82em;font-family:'JetBrains Mono',monospace;color:var(--gold)}
.msg.bot .bubble pre{background:rgba(0,0,0,.5);padding:12px 16px;border-radius:10px;overflow-x:auto;font-size:.78em;line-height:1.5;margin:8px 0;border:1px solid var(--border);font-family:'JetBrains Mono',monospace}
.msg.bot .bubble strong{color:#e0e8f0}
.msg.bot .bubble em{color:#aab}

/* Tool event */
.tool-event{align-self:stretch;background:rgba(255,183,77,.04);border:1px solid rgba(255,183,77,.15);border-radius:12px;padding:12px 16px;animation:toolIn .3s ease-out;display:flex;gap:10px;align-items:flex-start}
.tool-event .te-icon{font-size:1.2em;flex-shrink:0;margin-top:2px}
.tool-event .te-body{flex:1;min-width:0}
.tool-event .te-name{font-size:.75em;font-weight:700;color:var(--gold)}
.tool-event .te-args{font-size:.65em;color:var(--dim);margin-left:8px}
.tool-event .te-result{font-size:.7em;color:#687888;margin-top:4px;font-family:'JetBrains Mono',monospace;white-space:pre-wrap;max-height:60px;overflow:hidden;line-height:1.3}

/* Status pulse */
.status-pulse{text-align:center;padding:8px;animation:fadeIn .3s}
.status-pulse .pulse-ring{display:inline-flex;align-items:center;gap:8px;font-size:.7em;color:var(--cyan);opacity:.8}
.status-pulse .pulse-dot{width:8px;height:8px;background:var(--cyan);border-radius:50%;animation:pulse 1.4s infinite}
.status-pulse.error .pulse-dot{background:var(--red)}
.status-pulse.error{color:var(--red)}

@keyframes msgIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
@keyframes toolIn{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:translateX(0)}}
@keyframes fadeUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(0,212,255,.4)}50%{box-shadow:0 0 0 10px rgba(0,212,255,0)}}

/* Input */
#inputBar{padding:16px 24px;border-top:1px solid var(--border);display:flex;gap:10px;flex-shrink:0;background:var(--panel)}
#inputBar input{flex:1;padding:14px 20px;border-radius:28px;border:1px solid var(--border);background:rgba(0,0,0,.4);color:#c8d6e5;font-size:.85em;outline:none;transition:all .3s}
#inputBar input:focus{border-color:var(--cyan);box-shadow:0 0 0 3px rgba(0,212,255,.1)}
#inputBar input::placeholder{color:#3a4060}
#inputBar button{padding:12px 28px;border-radius:28px;border:none;background:linear-gradient(135deg,#1a4477,#1a3366);color:#c8ddf8;cursor:pointer;font-weight:700;font-size:.82em;letter-spacing:.5px;transition:all .3s}
#inputBar button:hover{background:linear-gradient(135deg,#2255aa,#2244aa);box-shadow:0 0 20px rgba(0,100,255,.2)}
#inputBar button:disabled{opacity:.3;cursor:not-allowed}
#inputBar .btn-new{background:transparent;border:1px solid var(--border);padding:12px 16px;font-size:1em}
#inputBar .btn-new:hover{background:rgba(255,255,255,.04)}

/* Toolbar hint */
.input-hint{font-size:.6em;color:var(--dim);text-align:center;padding:4px 0 0;opacity:.5}

/* Hamburger: hidden on desktop, visible on mobile */
.mobile-menu-btn{display:none;background:none;border:1px solid var(--border);color:var(--dim);padding:4px 8px;border-radius:6px;font-size:1.1em;cursor:pointer;flex-shrink:0}
@media(max-width:600px){.mobile-menu-btn{display:block}}

/* ═══════════════════════════════════════════
   RESPONSIVE — Mobile & Tablet
   ═══════════════════════════════════════════ */

/* Tablet: collapse sidebar into top bar */
@media(max-width:900px){
  body{flex-direction:column}
  #sidebar{width:100%;min-width:0;height:auto;flex-direction:row;flex-wrap:wrap;border-right:none;border-bottom:1px solid var(--border);padding:8px 12px;gap:8px;align-items:center}
  .sidebar-header{padding:0;border:none;display:flex;align-items:center;gap:8px}
  .sidebar-header .logo{font-size:1.2em}
  .sidebar-header .tagline{display:none}
  .sidebar-status{display:none}
  .sidebar-section{display:none}
  #sessionInfo{display:none;margin:0;padding:0;border:none;font-size:.55em}
  #main{min-width:0}
  #topbar{padding:8px 12px}
  #topbar .subtitle{display:none}
  #chat{padding:12px}
  .welcome{padding:30px 12px}
  .welcome h1{font-size:2em}
  .welcome .tag{font-size:.82em;max-width:100%}
  .welcome .cards{max-width:100%}
  .welcome .card{width:45%;min-width:140px;padding:12px}
  .msg{max-width:90%}
  #inputBar{padding:10px 12px}
  #inputBar input{padding:10px 14px;font-size:.8em}
  #inputBar button{padding:10px 18px;font-size:.75em}
}

/* Mobile: full responsive redesign */
@media(max-width:600px){
  body{flex-direction:column;font-size:14px}
  #sidebar{flex-shrink:0}
  #main{flex:1;min-height:0}
  canvas#bg{opacity:.3}
  #sidebar{width:100%;min-width:0;height:auto;flex-direction:row;padding:6px 10px;gap:4px;border-right:none;border-bottom:1px solid var(--border);align-items:center;justify-content:space-between}
  .sidebar-header{padding:0;border:none;display:flex;align-items:center;gap:4px;text-align:left}
  .sidebar-header .logo{font-size:1em;letter-spacing:1px}
  .sidebar-header .tagline{display:none}
  .sidebar-status{display:none}
  .sidebar-section{display:none}
  #sessionInfo{display:none}
  #main{min-width:0}
  #sidebar.open-mobile{position:fixed;top:0;left:0;width:260px;height:100%;z-index:100;flex-direction:column;padding:16px;background:var(--panel);border-right:1px solid var(--border);box-shadow:4px 0 30px rgba(0,0,0,.5);overflow-y:auto;align-items:flex-start;justify-content:flex-start}
  #sidebar.open-mobile .sidebar-header{display:block;text-align:center;width:100%;margin-bottom:12px}
  #sidebar.open-mobile .sidebar-header .logo{font-size:1.6em}
  #sidebar.open-mobile .sidebar-status{display:block;width:100%}
  #sidebar.open-mobile .sidebar-section{display:block;width:100%}
  #sidebar.open-mobile #sessionInfo{display:block;width:100%}
  #main{min-width:0}
  #topbar{padding:8px 10px;gap:6px}
  #topbar .brand{font-size:.75em}
  #topbar .sep{display:none}
  #topbar .subtitle{display:none}
  #topbar .actions button{font-size:.6em;padding:4px 8px}
  #chat{padding:10px;gap:10px}
  /* Welcome mobile */
  .welcome{padding:20px 8px}
  .welcome h1{font-size:1.8em}
  .welcome .tag{font-size:.75em;line-height:1.5;margin-bottom:20px;max-width:100%}
  .welcome .cards{gap:8px;max-width:100%}
  .welcome .card{width:100%;padding:14px;border-radius:12px}
  .welcome .card .c-icon{font-size:1.3em}
  .welcome .card .c-title{font-size:.75em}
  .welcome .card .c-desc{font-size:.65em}
  /* Messages mobile */
  .msg{max-width:95%}
  .msg .bubble{padding:10px 14px;font-size:.78em}
  .msg .sender{font-size:.6em}
  .msg.bot .bubble h2{font-size:.95em}
  .msg.bot .bubble h3{font-size:.82em}
  .msg.bot .bubble pre{font-size:.7em;padding:8px 10px}
  /* Tool event mobile */
  .tool-event{padding:8px 12px;gap:6px}
  .tool-event .te-name{font-size:.7em}
  .tool-event .te-result{font-size:.65em;max-height:40px}
  /* Input mobile */
  #inputBar{padding:8px 10px;gap:6px}
  #inputBar .btn-new{padding:10px 12px;font-size:.9em}
  #inputBar input{padding:10px 14px;font-size:.78em;border-radius:22px}
  #inputBar button{padding:10px 16px;font-size:.75em;border-radius:22px}
  .input-hint{display:none}
  /* Status pulse mobile */
  .status-pulse .pulse-ring{font-size:.65em}
}

/* Overlay backdrop */
.mobile-overlay{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.6);z-index:99}
.mobile-overlay.active{display:block}
</style>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
</head>
<body>
<canvas id="bg"></canvas>

<aside id="sidebar">
  <div class="sidebar-header">
    <button class="mobile-menu-btn" onclick="toggleSidebar()">☰</button>
    <div class="logo">MOTUS</div>
    <div class="tagline">AI Molecular Scientist</div>
  </div>
  <div class="sidebar-status">
    <div class="status-row"><span><span class="status-dot dot-online"></span>Engine</span><span style="color:var(--green)">Online</span></div>
    <div class="status-row"><span><span class="status-dot dot-online"></span>GROMACS 2026</span><span style="color:var(--green)">GPU</span></div>
    <div class="status-row"><span><span class="status-dot dot-online"></span>LAMMPS 22Jul2025</span><span style="color:var(--green)">CUDA</span></div>
    <div class="status-row"><span><span class="status-dot dot-idle"></span>DeepSeek</span><span style="color:var(--green)">Connected</span></div>
  </div>
  <div class="sidebar-section">
    <div class="sec-title">Capabilities</div>
    <div class="tool-list">
      <div class="tool-item"><span class="ti-icon">🏗️</span><span class="ti-name">System Builder</span></div>
      <div class="tool-item"><span class="ti-icon">⚡</span><span class="ti-name">MD Engine</span></div>
      <div class="tool-item"><span class="ti-icon">📊</span><span class="ti-name">Analysis Suite</span></div>
      <div class="tool-item"><span class="ti-icon">🎨</span><span class="ti-name">Structure Renderer</span></div>
      <div class="tool-item"><span class="ti-icon">📝</span><span class="ti-name">Paper Generator</span></div>
    </div>
  </div>
  <div class="sidebar-section">
    <div class="sec-title">Active Tools</div>
    <div class="tool-list" id="activeTools">
      <div class="tool-item"><span class="ti-icon">⏳</span><span class="ti-name">Awaiting input...</span></div>
    </div>
  </div>
  <div id="sessionInfo">Session: —</div>
</aside>

<div class="mobile-overlay" id="mobileOverlay" onclick="toggleSidebar()"></div>

<div id="main">
  <div id="topbar">
    <span class="brand">🧬 Research Console</span>
    <span class="sep">›</span>
    <span class="subtitle">AUTONOMOUS MD SCIENTIST</span>
    <div class="actions">
      <button onclick="newSession()">+ New Session</button>
    </div>
  </div>

  <div id="chat">
    <div class="welcome">
      <h1>🧬 MOTUS</h1>
      <div class="tag">
        An <strong>autonomous AI scientist</strong> and <strong>passionate professor</strong>
        specialized in molecular dynamics.<br>
        Research, simulate, analyze, and learn — all through natural conversation.
      </div>
      <div class="cards">
        <div class="card" onclick="quickAsk(this)" data-q="Build a water box with 1000 molecules and run 500ps MD at 300K 1bar">
          <div class="c-icon">💧</div><div class="c-title">Water Simulation</div>
          <div class="c-desc">Build & simulate pure water system with full analysis</div>
        </div>
        <div class="card" onclick="quickAsk(this)" data-q="Study methane hydrate formation: build a system with methane dissolved in water at 260K and 200 bar, run MD, analyze">
          <div class="c-icon">🔥</div><div class="c-title">Methane Hydrate</div>
          <div class="c-desc">Investigate hydrate formation under high pressure</div>
        </div>
        <div class="card" onclick="quickAsk(this)" data-q="Create a solid-liquid interface system and study interfacial properties">
          <div class="c-icon">🧊</div><div class="c-title">Solid-Liquid Interface</div>
          <div class="c-desc">Study wetting, adsorption, and interfacial structure</div>
        </div>
        <div class="card" onclick="quickAsk(this)" data-q="Teach me about hydrogen bonding in water — what it is, why it matters, and run a quick demo to show it">
          <div class="c-icon">🎓</div><div class="c-title">Learn: H-Bonds</div>
          <div class="c-desc">Understand hydrogen bonding with live MD demonstration</div>
        </div>
        <div class="card" onclick="quickAsk(this)" data-q="Explain the NVT and NPT ensembles in MD — what they mean, when to use each, and show me with a simulation">
          <div class="c-icon">📐</div><div class="c-title">Learn: Ensembles</div>
          <div class="c-desc">Master NVT vs NPT with hands-on examples</div>
        </div>
        <div class="card" onclick="quickAsk(this)" data-q="Teach me the fundamentals of molecular dynamics — force fields, integrators, thermostats, and run a simple demo">
          <div class="c-icon">📖</div><div class="c-title">MD Fundamentals</div>
          <div class="c-desc">From Newton's equations to modern MD simulations</div>
        </div>
      </div>
    </div>
  </div>

  <div id="inputBar">
    <button class="btn-new" onclick="newSession()" title="New Session">＋</button>
    <input id="input" placeholder="Ask MOTUS to do molecular dynamics research..." onkeydown="if(event.key==='Enter'&&!event.shiftKey)send()" autofocus>
    <button id="sendBtn" onclick="send()">Send →</button>
  </div>
  <div class="input-hint">Press Enter to send · Shift+Enter for new line</div>
</div>

<script>
let sessionId='';
const EMOJI={build_system:'🏗️',run_md:'⚡',analyze:'📊',read_data:'📖',render_system:'🎨',terminal:'💻',read_file:'📄',write_file:'✏️',search_files:'🔍'};

// Particle background
(function(){
const c=document.getElementById('bg'),ctx=c.getContext('2d');
let w,h,particles=[];
function resize(){w=c.width=window.innerWidth;h=c.height=window.innerHeight}
resize();window.addEventListener('resize',resize);
for(let i=0;i<60;i++)particles.push({x:Math.random()*w,y:Math.random()*h,vx:(Math.random()-.5)*.4,vy:(Math.random()-.5)*.4,r:Math.random()*1.5+.5});
function draw(){
ctx.clearRect(0,0,w,h);
particles.forEach((p,i)=>{
p.x+=p.vx;p.y+=p.vy;
if(p.x<0)p.x=w;if(p.x>w)p.x=0;if(p.y<0)p.y=h;if(p.y>h)p.y=0;
ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);ctx.fillStyle='rgba(0,180,255,'+(.08+p.r*.05)+')';ctx.fill();
for(let j=i+1;j<particles.length;j++){
const q=particles[j],dx=p.x-q.x,dy=p.y-q.y,d=Math.sqrt(dx*dx+dy*dy);
if(d<120){ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.strokeStyle='rgba(0,180,255,'+(.02*(1-d/120))+')';ctx.lineWidth=.5;ctx.stroke()}
}
});
requestAnimationFrame(draw)}
draw();
})();

async function init(){
const r=await fetch('/api/new_session');const d=await r.json();
sessionId=d.session_id;document.getElementById('sessionInfo').textContent='Session: '+sessionId;
}
setTimeout(init,100);

function scrollDown(){const c=document.getElementById('chat');c.scrollTop=c.scrollHeight}
function esc(s){return s?String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'):''}

function mdToHtml(t){
if(!t)return'';
let h=esc(t);
h=h.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
h=h.replace(/\*(.+?)\*/g,'<em>$1</em>');
h=h.replace(/`{3}(\w*)\n?([\s\S]*?)`{3}/g,'<pre><code>$2</code></pre>');
h=h.replace(/`([^`]+)`/g,'<code>$1</code>');
h=h.replace(/^#### (.+)$/gm,'<h4>$1</h4>');
h=h.replace(/^### (.+)$/gm,'<h3>$1</h3>');
h=h.replace(/^## (.+)$/gm,'<h2>$1</h2>');
h=h.replace(/^# (.+)$/gm,'<h2>$1</h2>');
h=h.replace(/^- (.+)$/gm,'<li>$1</li>');
h=h.replace(/\n\n/g,'</p><p>');
h='<p>'+h+'</p>';
h=h.replace(/<p><\/p>/g,'');
h=h.replace(/<p><li>/g,'<ul><li>');
h=h.replace(/<\/li><\/p>/g,'</li></ul>');
return h}

function rmWelcome(){const w=document.querySelector('.welcome');if(w)w.remove()}

function addUserMsg(t){
rmWelcome();
const d=document.createElement('div');d.className='msg user';
d.innerHTML='<div class="sender">You</div><div class="bubble">'+esc(t)+'</div>';
document.getElementById('chat').appendChild(d);scrollDown()}

function addToolMsg(name,args,result,iter){
rmWelcome();
const d=document.createElement('div');d.className='tool-event';
d.innerHTML='<div class="te-icon">'+(EMOJI[name]||'🔧')+'</div>'+
'<div class="te-body"><div class="te-name">'+esc(name)+'<span class="te-args">'+(args||'')+'</span></div>'+
(result?'<div class="te-result">'+esc(result)+'</div>':'')+'</div>';
document.getElementById('chat').appendChild(d);
// Update active tools sidebar
const at=document.getElementById('activeTools');
at.innerHTML='<div class="tool-item active"><span class="ti-icon">'+(EMOJI[name]||'🔧')+'</span><span class="ti-name">'+esc(name)+'</span></div>';
scrollDown()}

function addBotMsg(t){
rmWelcome();
const d=document.createElement('div');d.className='msg bot';
d.innerHTML='<div class="sender">🧬 MOTUS</div><div class="bubble">'+mdToHtml(t)+'</div>';
document.getElementById('chat').appendChild(d);
document.getElementById('activeTools').innerHTML='<div class="tool-item"><span class="ti-icon">✅</span><span class="ti-name">Complete</span></div>';
scrollDown()}

function addPulse(s,err){
const d=document.createElement('div');d.className='status-pulse'+(err?' error':'');
d.innerHTML='<span class="pulse-ring"><span class="pulse-dot"></span>'+esc(s)+'</span>';
d.id='pulse-'+Date.now();document.getElementById('chat').appendChild(d);scrollDown();return d}

async function send(){
const inp=document.getElementById('input'),txt=inp.value.trim();if(!txt)return;
inp.value='';inp.disabled=true;document.getElementById('sendBtn').disabled=true;
addUserMsg(txt);const pulse=addPulse('MOTUS is thinking...');
const es=new EventSource('/api/chat/'+sessionId+'?message='+encodeURIComponent(txt));
es.onmessage=function(e){
pulse.remove();
const d=JSON.parse(e.data);
if(d.type==='tool')addToolMsg(d.tool_name,d.args_preview,d.result_preview,d.iteration);
else if(d.type==='response'){addBotMsg(d.content);es.close()}
else if(d.type==='error'){addPulse(d.content,true);es.close()}
else if(d.type==='done')es.close()
};
es.onerror=function(){pulse.remove();es.close()};
setTimeout(()=>{inp.disabled=false;document.getElementById('sendBtn').disabled=false;inp.focus()},500)}

function quickAsk(el){
document.getElementById('input').value=el.dataset.q;send()}

async function newSession(){
const r=await fetch('/api/new_session');const d=await r.json();
sessionId=d.session_id;document.getElementById('sessionInfo').textContent='Session: '+sessionId;
document.getElementById('chat').innerHTML=`
<div class="welcome">
<h1>🧬 MOTUS</h1>
<div class="tag">An <strong>autonomous AI scientist</strong> and <strong>passionate professor</strong> specialized in molecular dynamics.<br>Research, simulate, analyze, and learn — through natural conversation.</div>
<div class="cards">
<div class="card" onclick="quickAsk(this)" data-q="Build a water box with 1000 molecules and run 500ps MD at 300K 1bar"><div class="c-icon">💧</div><div class="c-title">Water Simulation</div><div class="c-desc">Build & simulate pure water system with full analysis</div></div>
<div class="card" onclick="quickAsk(this)" data-q="Study methane hydrate formation: build a system with methane dissolved in water at 260K and 200 bar, run MD, analyze"><div class="c-icon">🔥</div><div class="c-title">Methane Hydrate</div><div class="c-desc">Investigate hydrate formation under high pressure</div></div>
<div class="card" onclick="quickAsk(this)" data-q="Create a solid-liquid interface system and study interfacial properties"><div class="c-icon">🧊</div><div class="c-title">Solid-Liquid Interface</div><div class="c-desc">Study wetting, adsorption, and interfacial structure</div></div>
<div class="card" onclick="quickAsk(this)" data-q="Teach me about hydrogen bonding in water — what it is, why it matters, and run a quick demo to show it"><div class="c-icon">🎓</div><div class="c-title">Learn: H-Bonds</div><div class="c-desc">Understand hydrogen bonding with live MD demonstration</div></div>
<div class="card" onclick="quickAsk(this)" data-q="Explain the NVT and NPT ensembles in MD — what they mean, when to use each, and show me with a simulation"><div class="c-icon">📐</div><div class="c-title">Learn: Ensembles</div><div class="c-desc">Master NVT vs NPT with hands-on examples</div></div>
<div class="card" onclick="quickAsk(this)" data-q="Teach me the fundamentals of molecular dynamics — force fields, integrators, thermostats, and run a simple demo"><div class="c-icon">📖</div><div class="c-title">MD Fundamentals</div><div class="c-desc">From Newton's equations to modern MD simulations</div></div>
</div></div>`;
document.getElementById('activeTools').innerHTML='<div class="tool-item"><span class="ti-icon">⏳</span><span class="ti-name">Awaiting input...</span></div>'}

document.getElementById('input').addEventListener('keydown',function(e){if(e.key==='Enter'&&e.shiftKey){e.preventDefault();this.value+='\n'}});

function toggleSidebar(){
  const sb = document.getElementById('sidebar');
  const ov = document.getElementById('mobileOverlay');
  sb.classList.toggle('open-mobile');
  ov.classList.toggle('active');
}
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/api/new_session")
def new_session():
    agent = MOTUSAgent()
    with _lock:
        _sessions[agent.memory.session_id] = {"agent": agent, "events": Queue(), "running": False}
    return jsonify({"session_id": agent.memory.session_id})

@app.route("/api/session/<sid>/messages")
def session_messages(sid):
    with _lock:
        sess = _sessions.get(sid)
    if not sess:
        return jsonify([])
    agent = sess["agent"]
    msgs = []
    for m in agent.memory.messages:
        role = m.get("role", "")
        if role == "user":
            msgs.append({"type": "user", "content": m.get("content", "")})
        elif role == "tool":
            msgs.append({
                "type": "tool",
                "tool_name": m.get("name", ""),
                "args_preview": "",
                "result_preview": m.get("content", "")[:200],
            })
        elif role == "assistant":
            content = m.get("content", "")
            if content:
                msgs.append({"type": "motus", "content": content})
    return jsonify(msgs)

@app.route("/api/chat/<sid>")
def chat_stream(sid):
    """SSE endpoint — runs agent in thread, streams events."""
    message = request.args.get("message", "")
    if not message:
        return Response("data: {\"type\":\"error\",\"content\":\"No message\"}\n\n", mimetype="text/event-stream")

    with _lock:
        sess = _sessions.get(sid)
    if not sess:
        return Response("data: {\"type\":\"error\",\"content\":\"Session not found\"}\n\n", mimetype="text/event-stream")

    agent = sess["agent"]

    def generate():
        # Override tool callback to emit SSE events
        events = []

        def tool_cb(iteration, fn_name, args, result):
            evt = json.dumps({
                "type": "tool",
                "iteration": iteration,
                "tool_name": fn_name,
                "args_preview": ", ".join(f"{k}={v}" for k, v in args.items() if k != "job_dir")[:100],
                "result_preview": (result or "")[:200],
            })
            events.append(evt)

        original_cb = agent._tool_callback
        agent._tool_callback = tool_cb

        try:
            response_text = agent.chat(message)
        except Exception as e:
            if events:
                for evt in events:
                    yield f"data: {evt}\n\n"
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            return
        finally:
            agent._tool_callback = original_cb

        # Emit all tool events
        for evt in events:
            yield f"data: {evt}\n\n"

        # Emit final response
        yield f"data: {json.dumps({'type': 'response', 'content': response_text})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return Response(generate(), mimetype="text/event-stream")

def main():
    import argparse
    from motus import __version__
    parser = argparse.ArgumentParser(description="MOTUS Web Server")
    parser.add_argument("--port", type=int, default=8848)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    print(f"🧬 MOTUS Web v{__version__} starting at http://{args.host}:{args.port}")
    print(f"   Open your browser and start researching!")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)

if __name__ == "__main__":
    main()
