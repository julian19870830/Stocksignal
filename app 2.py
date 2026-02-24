"""
StockSignal Pro – All-in-One Server
====================================
Eine URL, alles drin:
- Liefert die PWA-App (iPhone installierbar)
- Proxied Twelve Data API (API-Key bleibt sicher auf Server)
- Hintergrund-Scanner mit 8 Indikatoren
- Push-Notifications via ntfy.sh
"""

import os, time, threading, json, math
from datetime import datetime, timezone
from flask import Flask, jsonify, request, render_template_string
import requests as req

app = Flask(__name__)

# ── Konfiguration ──────────────────────────────────────────────────────────────
API_KEY        = os.environ.get("TWELVE_DATA_KEY", "")
NTFY_TOPIC     = os.environ.get("NTFY_TOPIC", "")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "900"))
WATCHLIST      = os.environ.get("WATCHLIST", "AAPL,NVDA,MSFT,TSLA,AMZN,GOOGL,META,SPY").split(",")

# ── State ──────────────────────────────────────────────────────────────────────
signal_history = []
last_action    = {}
scan_count     = 0
start_time     = datetime.now(timezone.utc)

# ══════════════════════════════════════════════════════════════════════════════
# PWA FRONTEND HTML
# ══════════════════════════════════════════════════════════════════════════════
FRONTEND = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="StockSignal">
<meta name="theme-color" content="#04040f">
<title>StockSignal Pro</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=DM+Sans:wght@400;500;600;700;800&display=swap');
:root{
  --bg:#04040f;--s1:#080816;--s2:#0d0d1e;--border:#16162a;
  --text:#eeeeff;--muted:#3a3a6a;--dim:#1a1a30;
  --buy:#00e5a0;--sell:#ff4466;--hold:#ffb800;--blue:#4488ff;--purple:#9966ff;
  --st:env(safe-area-inset-top,44px);--sb:env(safe-area-inset-bottom,20px);
}
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent;}
html,body{height:100%;background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;-webkit-font-smoothing:antialiased;}

/* Grid background */
body::before{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(68,136,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(68,136,255,.025) 1px,transparent 1px);background-size:36px 36px;pointer-events:none;z-index:0;}

#app{position:relative;z-index:1;padding-top:var(--st);padding-bottom:calc(var(--sb) + 68px);}

/* ── Topbar ── */
.topbar{
  display:flex;align-items:center;justify-content:space-between;
  padding:12px 20px 10px;
  position:sticky;top:var(--st);
  background:rgba(4,4,15,.88);
  backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);
  border-bottom:1px solid var(--border);z-index:100;
}
.tb-brand{display:flex;align-items:center;gap:10px;}
.tb-icon{width:32px;height:32px;background:linear-gradient(135deg,var(--buy),var(--blue));border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:.95rem;}
.tb-name{font-size:.95rem;font-weight:800;letter-spacing:-.3px;}
.tb-sub{font-size:.6rem;color:var(--muted);font-family:'JetBrains Mono',monospace;margin-top:1px;}
.tb-right{display:flex;gap:7px;align-items:center;}
.live-pill{display:flex;align-items:center;gap:5px;background:rgba(0,229,160,.08);border:1px solid rgba(0,229,160,.2);border-radius:20px;padding:4px 10px;font-size:.65rem;font-weight:700;color:var(--buy);font-family:'JetBrains Mono',monospace;}
.ldot{width:6px;height:6px;border-radius:50%;background:var(--buy);animation:pulse 2s infinite;}
.icon-btn{width:34px;height:34px;border-radius:9px;background:var(--s1);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;font-size:.95rem;cursor:pointer;}

/* ── Pages ── */
.page{display:none;}
.page.active{display:block;padding-bottom:16px;}

/* ── Price Hero ── */
.price-hero{padding:22px 20px 18px;border-bottom:1px solid var(--border);}
.ph-sym{font-size:.65rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-family:'JetBrains Mono',monospace;margin-bottom:4px;}
.ph-price{font-size:2.8rem;font-weight:800;letter-spacing:-1.5px;font-variant-numeric:tabular-nums;line-height:1;}
.ph-row{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;align-items:center;}
.pill{padding:5px 13px;border-radius:20px;font-size:.78rem;font-weight:700;font-family:'JetBrains Mono',monospace;}
.pill-up{background:rgba(0,229,160,.12);color:var(--buy);border:1px solid rgba(0,229,160,.2);}
.pill-down{background:rgba(255,68,102,.12);color:var(--sell);border:1px solid rgba(255,68,102,.2);}
.pill-buy{background:rgba(0,229,160,.12);color:var(--buy);border:1px solid rgba(0,229,160,.25);letter-spacing:1px;}
.pill-sell{background:rgba(255,68,102,.12);color:var(--sell);border:1px solid rgba(255,68,102,.25);letter-spacing:1px;}
.pill-hold{background:rgba(255,184,0,.1);color:var(--hold);border:1px solid rgba(255,184,0,.2);letter-spacing:1px;}

/* ── Signal Banner ── */
#sig-banner{margin:14px 16px 0;border-radius:16px;padding:14px 16px;display:none;align-items:center;gap:12px;}
#sig-banner.buy{background:rgba(0,229,160,.08);border:1px solid rgba(0,229,160,.25);}
#sig-banner.sell{background:rgba(255,68,102,.08);border:1px solid rgba(255,68,102,.25);}
.sb-icon{font-size:1.8rem;}
.sb-body{flex:1;}
.sb-type{font-size:1rem;font-weight:800;letter-spacing:.5px;}
.sb-reason{font-size:.72rem;color:var(--muted);margin-top:3px;line-height:1.4;}
.btn-rep{background:rgba(255,255,255,.06);border:1px solid var(--border);color:var(--text);padding:8px 12px;border-radius:10px;font-size:.72rem;cursor:pointer;font-weight:600;}

/* ── Symbol Chips ── */
.sym-scroll{display:flex;gap:8px;padding:16px 16px;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;}
.sym-scroll::-webkit-scrollbar{display:none;}
.chip{background:var(--s1);border:1px solid var(--border);color:var(--muted);padding:7px 16px;border-radius:20px;font-size:.75rem;font-weight:700;white-space:nowrap;cursor:pointer;flex-shrink:0;font-family:'JetBrains Mono',monospace;transition:all .15s;}
.chip.active{background:rgba(68,136,255,.12);border-color:rgba(68,136,255,.35);color:#93c5fd;}

/* ── Error / Loading ── */
#app-err{margin:0 16px 10px;background:rgba(255,68,102,.06);border:1px solid rgba(255,68,102,.2);border-radius:14px;padding:12px 14px;font-size:.82rem;color:#ff9999;display:none;line-height:1.5;}
#loading{padding:50px 20px;text-align:center;color:var(--muted);font-size:.86rem;display:none;font-family:'JetBrains Mono',monospace;}

/* ── Indicators Grid ── */
.sec{font-size:.6rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);padding:14px 20px 8px;font-family:'JetBrains Mono',monospace;display:flex;align-items:center;gap:10px;}
.sec::after{content:'';flex:1;height:1px;background:var(--border);}
.kpi-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 16px;}
.kpi{background:var(--s1);border:1px solid var(--border);border-radius:16px;padding:14px 15px;}
.kl{font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:5px;font-family:'JetBrains Mono',monospace;}
.kv{font-size:1.1rem;font-weight:800;margin-bottom:3px;letter-spacing:-.3px;}
.ks{font-size:.65rem;color:var(--muted);}

/* ── Confidence Meter ── */
.conf-card{background:var(--s1);border:1px solid var(--border);border-radius:18px;margin:0 16px;padding:18px;}
.conf-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;}
.conf-title{font-size:.88rem;font-weight:700;}
.conf-score{font-size:1.4rem;font-weight:800;font-family:'JetBrains Mono',monospace;}
.conf-bar-wrap{height:8px;background:var(--dim);border-radius:4px;overflow:hidden;margin-bottom:12px;}
.conf-bar{height:100%;border-radius:4px;transition:width .5s ease;}
.conf-signals{display:flex;flex-direction:column;gap:6px;}
.sig-row{display:flex;align-items:center;gap:8px;font-size:.75rem;}
.sig-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;}
.sig-dot.buy{background:var(--buy);}
.sig-dot.sell{background:var(--sell);}
.sig-txt{color:#94a3b8;}

/* ── Chart ── */
.chart-card{background:var(--s1);border:1px solid var(--border);border-radius:18px;margin:14px 16px 0;overflow:hidden;}
.ctabs{display:flex;border-bottom:1px solid var(--border);}
.ctab{flex:1;padding:12px 4px;background:transparent;border:none;color:var(--muted);font-size:.72rem;cursor:pointer;border-bottom:2px solid transparent;-webkit-appearance:none;font-family:'DM Sans',sans-serif;font-weight:500;transition:all .15s;}
.ctab.active{color:#93c5fd;font-weight:700;border-bottom-color:var(--blue);}
.cbody{padding:14px 10px 10px;display:none;}
.cbody.active{display:block;}
.cwrap{position:relative;height:200px;}
.cleg{display:flex;gap:12px;margin-top:8px;flex-wrap:wrap;padding:0 4px;}
.cleg span{font-size:.63rem;color:var(--muted);font-family:'JetBrains Mono',monospace;}

/* ── Signal History ── */
.sig-list{padding:0 16px;}
.sr{background:var(--s1);border:1px solid var(--border);border-radius:14px;padding:13px 15px;margin-bottom:9px;display:flex;align-items:center;gap:12px;}
.sr.buy{border-left:3px solid var(--buy);}
.sr.sell{border-left:3px solid var(--sell);}
.sr-badge{padding:3px 9px;border-radius:6px;font-size:.68rem;font-weight:700;white-space:nowrap;font-family:'JetBrains Mono',monospace;}
.sr-badge.buy{background:rgba(0,229,160,.12);color:var(--buy);}
.sr-badge.sell{background:rgba(255,68,102,.12);color:var(--sell);}
.sr-sym{font-size:.95rem;font-weight:800;min-width:50px;letter-spacing:-.3px;}
.sr-info{flex:1;}
.sr-price{font-size:.82rem;font-weight:700;font-family:'JetBrains Mono',monospace;}
.sr-sigs{font-size:.67rem;color:var(--muted);margin-top:2px;line-height:1.4;}
.sr-right{text-align:right;}
.sr-score{font-size:.95rem;font-weight:800;font-family:'JetBrains Mono',monospace;}
.sr-time{font-size:.62rem;color:var(--muted);margin-top:2px;font-family:'JetBrains Mono',monospace;}
.empty{padding:50px 20px;text-align:center;color:var(--muted);font-size:.84rem;font-style:italic;}

/* ── Fear & Greed ── */
.fg-card{background:var(--s1);border:1px solid var(--border);border-radius:18px;margin:14px 16px 0;padding:18px;display:flex;align-items:center;gap:20px;}
.fg-right{flex:1;}
.fg-lbl{font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-family:'JetBrains Mono',monospace;margin-bottom:4px;}
.fg-num{font-size:1.6rem;font-weight:800;letter-spacing:-.5px;}
.fg-name{font-size:.8rem;margin-top:3px;font-weight:600;}
.fg-desc{font-size:.72rem;color:var(--muted);margin-top:7px;line-height:1.5;}

/* ── Bottom Nav ── */
.bnav{position:fixed;bottom:0;left:0;right:0;background:rgba(4,4,15,.96);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border-top:1px solid var(--border);display:flex;padding-bottom:var(--sb);z-index:200;}
.nbtn{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;background:none;border:none;cursor:pointer;padding:10px 4px;-webkit-appearance:none;}
.nbtn .ni{font-size:1.3rem;}
.nbtn .nl{font-size:.58rem;color:var(--muted);font-weight:600;font-family:'JetBrains Mono',monospace;letter-spacing:.03em;}
.nbtn.active .nl{color:var(--blue);}

/* ── Toasts ── */
#toasts{position:fixed;top:calc(var(--st)+8px);left:12px;right:12px;z-index:999;display:flex;flex-direction:column;gap:8px;pointer-events:none;}
.toast{padding:14px 16px;border-radius:16px;display:flex;gap:12px;align-items:center;animation:tIn .3s cubic-bezier(.175,.885,.32,1.275);color:white;box-shadow:0 8px 40px rgba(0,0,0,.6);}
.toast.buy{background:linear-gradient(135deg,rgba(0,229,160,.98),rgba(0,180,120,.98));}
.toast.sell{background:linear-gradient(135deg,rgba(255,68,102,.98),rgba(200,40,70,.98));}
.toast-icon{font-size:1.5rem;}
.toast b{font-size:.9rem;display:block;letter-spacing:.3px;}
.toast small{font-size:.73rem;opacity:.88;}

/* ── Disclaimer ── */
.disclaimer{margin:14px 16px 0;background:rgba(255,184,0,.04);border:1px solid rgba(255,184,0,.1);border-radius:14px;padding:12px 14px;font-size:.68rem;color:#78350f;line-height:1.6;}

@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
@keyframes tIn{from{opacity:0;transform:translateY(-14px) scale(.95)}to{opacity:1;transform:translateY(0) scale(1)}}
</style>
</head>
<body>
<div id="app">
  <div id="toasts"></div>

  <!-- Topbar -->
  <div class="topbar">
    <div class="tb-brand">
      <div class="tb-icon">📈</div>
      <div>
        <div class="tb-name">StockSignal Pro</div>
        <div class="tb-sub" id="tb-sub">LIVE · TWELVE DATA</div>
      </div>
    </div>
    <div class="tb-right">
      <div class="live-pill"><div class="ldot"></div>LIVE</div>
      <div class="icon-btn" id="sound-btn" onclick="toggleSound()">🔊</div>
    </div>
  </div>

  <!-- PAGE: Dashboard -->
  <div id="p-dash" class="page active">
    <div class="price-hero">
      <div class="ph-sym" id="ph-sym">AAPL · Apple Inc.</div>
      <div class="ph-price" id="ph-price">–</div>
      <div class="ph-row">
        <span class="pill" id="chg-pill">–</span>
        <span class="pill" id="rec-pill">–</span>
      </div>
    </div>

    <div id="sig-banner">
      <span class="sb-icon" id="sb-icon"></span>
      <div class="sb-body">
        <div class="sb-type" id="sb-type"></div>
        <div class="sb-reason" id="sb-reason"></div>
      </div>
      <button class="btn-rep" onclick="replaySignal()">🔊</button>
    </div>

    <div class="sym-scroll">
      <div class="chip active" onclick="qLoad('AAPL',this)">AAPL</div>
      <div class="chip" onclick="qLoad('NVDA',this)">NVDA</div>
      <div class="chip" onclick="qLoad('MSFT',this)">MSFT</div>
      <div class="chip" onclick="qLoad('TSLA',this)">TSLA</div>
      <div class="chip" onclick="qLoad('AMZN',this)">AMZN</div>
      <div class="chip" onclick="qLoad('GOOGL',this)">GOOGL</div>
      <div class="chip" onclick="qLoad('META',this)">META</div>
      <div class="chip" onclick="qLoad('SPY',this)">SPY</div>
      <div class="chip" onclick="qLoad('QQQ',this)">QQQ</div>
      <div class="chip" onclick="qLoad('NFLX',this)">NFLX</div>
    </div>

    <div id="app-err"></div>
    <div id="loading">⏳ Analysiere...</div>

    <div id="kpi-sec" style="display:none">
      <div class="sec">Indikatoren</div>
      <div class="kpi-grid">
        <div class="kpi"><div class="kl">RSI (14)</div><div class="kv" id="k-rsi">–</div><div class="ks" id="k-rsi-s">–</div></div>
        <div class="kpi"><div class="kl">MACD</div><div class="kv" id="k-macd">–</div><div class="ks" id="k-macd-s">–</div></div>
        <div class="kpi"><div class="kl">SMA 20</div><div class="kv" id="k-s20" style="color:#ffb800">–</div><div class="ks" id="k-s20-s">–</div></div>
        <div class="kpi"><div class="kl">SMA 50</div><div class="kv" id="k-s50" style="color:#9966ff">–</div><div class="ks" id="k-s50-s">–</div></div>
      </div>

      <div class="sec" style="margin-top:14px">Signal-Stärke</div>
      <div class="conf-card">
        <div class="conf-header">
          <div>
            <div class="conf-title" id="conf-title">–</div>
            <div style="font-size:.7rem;color:var(--muted);margin-top:2px" id="conf-sub">–</div>
          </div>
          <div class="conf-score" id="conf-score">–</div>
        </div>
        <div class="conf-bar-wrap"><div class="conf-bar" id="conf-bar" style="width:0%;background:var(--muted)"></div></div>
        <div class="conf-signals" id="conf-signals"></div>
      </div>

      <div class="sec" style="margin-top:14px">Markt-Stimmung</div>
      <div class="fg-card">
        <svg id="gauge-svg" width="110" height="64" viewBox="0 0 110 64"></svg>
        <div class="fg-right">
          <div class="fg-lbl">Fear &amp; Greed Index</div>
          <div class="fg-num" id="fg-num">–</div>
          <div class="fg-name" id="fg-name">–</div>
          <div class="fg-desc" id="fg-desc">–</div>
        </div>
      </div>
    </div>
  </div>

  <!-- PAGE: Charts -->
  <div id="p-charts" class="page">
    <div style="height:14px"></div>
    <div class="chart-card">
      <div class="ctabs">
        <button class="ctab active" onclick="switchChart('price',this)">Kurs</button>
        <button class="ctab" onclick="switchChart('rsi',this)">RSI</button>
        <button class="ctab" onclick="switchChart('macd',this)">MACD</button>
      </div>
      <div class="cbody active" id="cb-price">
        <div class="cwrap"><canvas id="priceChart"></canvas></div>
        <div class="cleg">
          <span style="color:#4488ff">◆ Kurs</span>
          <span style="color:#ffb800">— SMA20</span>
          <span style="color:#9966ff">— SMA50</span>
          <span style="color:#00e5a0">● Kauf</span>
          <span style="color:#ff4466">● Verkauf</span>
        </div>
      </div>
      <div class="cbody" id="cb-rsi"><div class="cwrap"><canvas id="rsiChart"></canvas></div></div>
      <div class="cbody" id="cb-macd"><div class="cwrap"><canvas id="macdChart"></canvas></div></div>
    </div>
    <div class="disclaimer" style="margin-top:14px">⚠️ Echte Börsendaten via Twelve Data. Charts zeigen 60 Handelstage. Keine Finanzberatung.</div>
  </div>

  <!-- PAGE: Signale -->
  <div id="p-signals" class="page">
    <div class="sec" style="padding-top:18px">Server-Signale (automatisch)</div>
    <div class="sig-list" id="sig-list">
      <div class="empty">Lade Server-Signale...</div>
    </div>
    <div class="sec" style="margin-top:8px">Push-Alerts Status</div>
    <div style="padding:0 16px 16px">
      <div style="background:var(--s1);border:1px solid var(--border);border-radius:14px;padding:14px 16px;font-size:.8rem;color:#94a3b8;line-height:1.7">
        🔔 Alerts kommen via <strong style="color:var(--text)">ntfy App</strong> auf dein iPhone<br>
        ⏱ Scan-Intervall: <strong style="color:var(--text)">{{ interval }} Minuten</strong><br>
        🎯 Mindest-Score für Alert: <strong style="color:var(--text)">+3 / -3</strong><br>
        📊 Überwachte Symbole: <strong style="color:var(--text)">{{ watchlist }}</strong>
      </div>
    </div>
  </div>

  <!-- Bottom Nav -->
  <nav class="bnav">
    <button class="nbtn active" onclick="switchPage('dash',this)"><span class="ni">📊</span><span class="nl">DASHBOARD</span></button>
    <button class="nbtn" onclick="switchPage('charts',this)"><span class="ni">📈</span><span class="nl">CHARTS</span></button>
    <button class="nbtn" onclick="switchPage('signals',this)"><span class="ni">🚦</span><span class="nl">SIGNALE</span></button>
  </nav>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
'use strict';
var SYM = 'AAPL';
var soundOn = true;
var lastSig = null;
var CH = {};
var cd = null;
var fg = 32 + Math.floor(Math.random()*38);
var refreshTimer = null;

// ── Audio ─────────────────────────────────────────────────────────────────────
function playTone(type){
  if(!soundOn)return;
  try{
    var ctx=new(window.AudioContext||window.webkitAudioContext)();
    if(ctx.state==='suspended')ctx.resume();
    var freqs=type==='BUY'?[523,659,784,1047]:[784,659,523,392];
    freqs.forEach(function(f,i){
      var o=ctx.createOscillator(),g=ctx.createGain();
      o.connect(g);g.connect(ctx.destination);
      o.type=type==='BUY'?'sine':'triangle';
      o.frequency.value=f;
      var t=ctx.currentTime+i*.17;
      g.gain.setValueAtTime(0,t);
      g.gain.linearRampToValueAtTime(.36,t+.05);
      g.gain.exponentialRampToValueAtTime(.001,t+.32);
      o.start(t);o.stop(t+.35);
    });
  }catch(e){}
}
function toggleSound(){soundOn=!soundOn;document.getElementById('sound-btn').textContent=soundOn?'🔊':'🔇';if(soundOn)playTone('BUY');}
function replaySignal(){if(lastSig)playTone(lastSig.type);}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(type,title,detail){
  var t=document.createElement('div');
  t.className='toast '+(type==='BUY'?'buy':'sell');
  t.innerHTML='<span class="toast-icon">'+(type==='BUY'?'📈':'📉')+'</span><div><b>'+title+'</b><small>'+detail+'</small></div>';
  document.getElementById('toasts').appendChild(t);
  setTimeout(function(){if(t.parentNode)t.parentNode.removeChild(t);},5500);
}

// ── Indicators ────────────────────────────────────────────────────────────────
function sma(c,p){return c.map(function(_,i){if(i<p-1)return null;var s=0;for(var j=i-p+1;j<=i;j++)s+=c[j];return s/p;});}
function ema(arr,p){var k=2/(p+1),o=[];arr.forEach(function(v,i){o.push(i===0?v:v*k+o[i-1]*(1-k));});return o;}
function calcRSI(c,p){p=p||14;return c.map(function(_,i){if(i<p)return null;var g=0,l=0;for(var j=i-p+1;j<=i;j++){var d=c[j]-c[j-1];if(d>0)g+=d;else l-=d;}return 100-100/(1+(l===0?100:g/l));});}
function calcMACD(c){var e12=ema(c,12),e26=ema(c,26),ml=e12.map(function(v,i){return v-e26[i];}),sig=ema(ml,9);return{ml:ml,sig:sig,hist:ml.map(function(v,i){return v-sig[i];});};}
function bollinger(c,p){p=p||20;var s=sma(c,p),u=[],l=[];s.forEach(function(m,i){if(m===null){u.push(null);l.push(null);return;}var w=c.slice(i-p+1,i+1),std=Math.sqrt(w.reduce(function(a,x){return a+(x-m)*(x-m);},0)/p);u.push(m+2*std);l.push(m-2*std);});return{upper:u,lower:l};}

function analyze(closes){
  var n=closes.length-1;
  if(n<55)return null;
  var price=closes[n],prev=closes[n-1];
  var S20=sma(closes,20),S50=sma(closes,50),RSI=calcRSI(closes),mc=calcMACD(closes),bb=bollinger(closes);
  if(!S20[n]||!S50[n]||!RSI[n])return null;
  var rv=RSI[n],hv=mc.hist[n],hv1=mc.hist[n-1]||0;
  var buy=[],sell=[];

  if(rv<30)buy.push('RSI überverkauft ('+rv.toFixed(1)+')');
  else if(rv>70)sell.push('RSI überkauft ('+rv.toFixed(1)+')');

  if(hv>0&&hv1<=0)buy.push('MACD Crossover ↑');
  else if(hv<0&&hv1>=0)sell.push('MACD Crossover ↓');
  else if(hv>0)buy.push('MACD bullisch');
  else sell.push('MACD bearisch');

  if(S20[n-1]&&S50[n-1]){
    if(S20[n-1]<S50[n-1]&&S20[n]>=S50[n])buy.push('Golden Cross ✨');
    else if(S20[n-1]>S50[n-1]&&S20[n]<=S50[n])sell.push('Death Cross ⚠️');
  }
  if(S20[n]>S50[n])buy.push('Aufwärtstrend');else sell.push('Abwärtstrend');
  if(price>S20[n])buy.push('Über SMA20');else sell.push('Unter SMA20');
  if(bb.lower[n]&&price<=bb.lower[n])buy.push('Unteres Bollinger Band');
  else if(bb.upper[n]&&price>=bb.upper[n])sell.push('Oberes Bollinger Band');

  var bs=buy.length,ss=sell.length,net=bs-ss;
  var action,color;
  if(net>=4){action='KAUFEN';color='buy';}
  else if(net>=2){action='EHER KAUFEN';color='buy';}
  else if(net<=-4){action='VERKAUFEN';color='sell';}
  else if(net<=-2){action='EHER VERKAUFEN';color='sell';}
  else{action='HALTEN';color='hold';}
  return{action:action,color:color,buy:buy,sell:sell,net:net,rsi:rv,hist:hv,s20:S20[n],s50:S50[n],price:price,prev:prev,bb:bb,mc:mc,S20:S20,S50:S50,RSI:RSI};
}

// ── API Calls (über eigenen Server – kein CORS, kein Key im Browser) ──────────
async function apiGet(path){
  var r=await fetch(path);
  var j=await r.json();
  if(j.error)throw new Error(j.error);
  return j;
}

async function loadSym(sym){
  sym=sym.toUpperCase().trim();
  SYM=sym;
  document.getElementById('app-err').style.display='none';
  document.getElementById('loading').style.display='block';
  document.getElementById('kpi-sec').style.display='none';
  document.getElementById('sig-banner').style.display='none';
  document.getElementById('ph-price').textContent='–';

  try{
    var data=await apiGet('/api/candles?symbol='+sym);
    var closes=data.closes,dates=data.dates;
    var quote=await apiGet('/api/quote?symbol='+sym);

    var price=quote.price||closes[closes.length-1];
    var prev=quote.prev||closes[closes.length-2];
    var chg=((price-prev)/prev*100);

    cd={sym:sym,closes:closes,dates:dates,price:price,prev:prev,chg:chg};
    var a=analyze(closes);
    cd.analysis=a;

    document.getElementById('ph-sym').textContent=sym+(quote.name?' · '+quote.name:'');
    document.getElementById('ph-price').textContent='$'+price.toFixed(2);
    document.getElementById('tb-sub').textContent=sym+' · '+new Date().toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'});

    var isUp=chg>=0;
    var cp=document.getElementById('chg-pill');
    cp.textContent=(isUp?'▲ +':'▼ ')+Math.abs(chg).toFixed(2)+'%';
    cp.className='pill '+(isUp?'pill-up':'pill-down');

    if(a){
      var rp=document.getElementById('rec-pill');
      rp.textContent=a.action;
      rp.className='pill pill-'+a.color;

      document.getElementById('k-rsi').textContent=a.rsi.toFixed(1);
      document.getElementById('k-rsi').style.color=a.rsi<30?'var(--buy)':a.rsi>70?'var(--sell)':'#94a3b8';
      document.getElementById('k-rsi-s').textContent=a.rsi<30?'Kaufsignal 🟢':a.rsi>70?'Verkaufssignal 🔴':'Neutral';
      document.getElementById('k-macd').textContent=a.hist>0?'Bullisch ↑':'Bearisch ↓';
      document.getElementById('k-macd').style.color=a.hist>0?'var(--buy)':'var(--sell)';
      document.getElementById('k-macd-s').textContent='Hist: '+a.hist.toFixed(3);
      document.getElementById('k-s20').textContent='$'+a.s20.toFixed(2);
      document.getElementById('k-s20-s').textContent=price>a.s20?'Kurs darüber ↑':'Kurs darunter ↓';
      document.getElementById('k-s50').textContent='$'+a.s50.toFixed(2);
      document.getElementById('k-s50-s').textContent=a.S20[closes.length-1]>a.s50?'Golden Cross ✨':'Death Cross ⚠️';

      // Confidence
      var total=a.buy.length+a.sell.length;
      var dominant=a.color==='buy'?a.buy.length:a.sell.length;
      var pct=total>0?Math.round(dominant/total*100):0;
      document.getElementById('conf-title').textContent=a.action;
      document.getElementById('conf-title').style.color=a.color==='buy'?'var(--buy)':a.color==='sell'?'var(--sell)':'var(--hold)';
      document.getElementById('conf-sub').textContent=dominant+' von '+total+' Indikatoren bestätigen';
      document.getElementById('conf-score').textContent=(a.net>0?'+':'')+a.net;
      document.getElementById('conf-score').style.color=a.net>0?'var(--buy)':a.net<0?'var(--sell)':'var(--muted)';
      var bar=document.getElementById('conf-bar');
      bar.style.width=pct+'%';
      bar.style.background=a.color==='buy'?'var(--buy)':a.color==='sell'?'var(--sell)':'var(--muted)';

      var allSigs=a.buy.map(function(s){return{txt:s,type:'buy'};}).concat(a.sell.map(function(s){return{txt:s,type:'sell'};}));
      document.getElementById('conf-signals').innerHTML=allSigs.slice(0,6).map(function(s){
        return '<div class="sig-row"><div class="sig-dot '+s.type+'"></div><span class="sig-txt">'+s.txt+'</span></div>';
      }).join('');

      // Signal banner für starke Signale
      if(Math.abs(a.net)>=4){
        var isBuy=a.color==='buy';
        lastSig={type:isBuy?'BUY':'SELL'};
        var banner=document.getElementById('sig-banner');
        banner.className='sig-banner '+a.color;
        banner.style.display='flex';
        document.getElementById('sb-icon').textContent=isBuy?'🟢':'🔴';
        document.getElementById('sb-type').textContent=a.action;
        document.getElementById('sb-type').style.color=isBuy?'var(--buy)':'var(--sell)';
        var topSigs=(isBuy?a.buy:a.sell).slice(0,2).join(' · ');
        document.getElementById('sb-reason').textContent=topSigs+' · Score: '+(a.net>0?'+':'')+a.net;
        playTone(isBuy?'BUY':'SELL');
        showToast(isBuy?'BUY':'SELL',a.action+': '+sym,topSigs);
      }
    }

    document.getElementById('loading').style.display='none';
    document.getElementById('kpi-sec').style.display='block';
    renderGauge(fg);
    buildCharts(closes,dates,a);
    startRefresh(sym);

  }catch(err){
    document.getElementById('loading').style.display='none';
    document.getElementById('app-err').textContent='⚠️ '+err.message;
    document.getElementById('app-err').style.display='block';
  }
}

// ── Charts ────────────────────────────────────────────────────────────────────
var cBase={
  responsive:true,maintainAspectRatio:false,
  plugins:{legend:{display:false},tooltip:{backgroundColor:'#080816',borderColor:'#16162a',borderWidth:1,titleColor:'#94a3b8',bodyColor:'#eeeeff',titleFont:{size:10},bodyFont:{size:10},cornerRadius:8}},
  scales:{x:{ticks:{color:'#2a2a4a',font:{size:8},maxTicksLimit:7},grid:{color:'#0e0e1e'}},y:{ticks:{color:'#2a2a4a',font:{size:8}},grid:{color:'#0e0e1e'}}}
};
function buildCharts(closes,dates,a){
  var SL=60;
  var cl=closes.slice(-SL),dl=dates.slice(-SL);
  var S20=sma(closes,20).slice(-SL),S50=sma(closes,50).slice(-SL),RSI=calcRSI(closes).slice(-SL);
  var mc=calcMACD(closes),mll=mc.ml.slice(-SL),sigl=mc.sig.slice(-SL),histl=mc.hist.slice(-SL);
  var off=closes.length-SL;
  var sigs=a?findSigPts(closes,off,SL):[];
  var buyPts=cl.map(function(_,i){return sigs.some(function(s){return s.i===off+i&&s.t==='B';})?cl[i]:null;});
  var sellPts=cl.map(function(_,i){return sigs.some(function(s){return s.i===off+i&&s.t==='S';})?cl[i]:null;});

  if(CH.price)CH.price.destroy();
  CH.price=new Chart(document.getElementById('priceChart'),{
    type:'line',data:{labels:dl,datasets:[
      {data:cl,borderColor:'#4488ff',borderWidth:2,fill:true,backgroundColor:'rgba(68,136,255,.04)',pointRadius:0,tension:.3},
      {data:S20,borderColor:'#ffb800',borderWidth:1.5,fill:false,pointRadius:0,borderDash:[5,3],tension:.3},
      {data:S50,borderColor:'#9966ff',borderWidth:1.5,fill:false,pointRadius:0,borderDash:[5,3],tension:.3},
      {data:buyPts,borderColor:'transparent',backgroundColor:'#00e5a0',pointRadius:buyPts.map(function(v){return v?8:0;}),showLine:false},
      {data:sellPts,borderColor:'transparent',backgroundColor:'#ff4466',pointRadius:sellPts.map(function(v){return v?8:0;}),showLine:false},
    ]},
    options:Object.assign({},cBase,{scales:Object.assign({},cBase.scales,{y:Object.assign({},cBase.scales.y,{ticks:Object.assign({},cBase.scales.y.ticks,{callback:function(v){return'$'+v.toFixed(0);}})})})})
  });

  if(CH.rsi)CH.rsi.destroy();
  CH.rsi=new Chart(document.getElementById('rsiChart'),{
    type:'line',data:{labels:dl,datasets:[
      {data:RSI,borderColor:'#ffb800',borderWidth:2,fill:false,pointRadius:0,tension:.3},
      {data:dl.map(function(){return 70;}),borderColor:'rgba(255,68,102,.4)',borderWidth:1,borderDash:[4,2],fill:false,pointRadius:0},
      {data:dl.map(function(){return 30;}),borderColor:'rgba(0,229,160,.4)',borderWidth:1,borderDash:[4,2],fill:false,pointRadius:0},
    ]},
    options:Object.assign({},cBase,{scales:Object.assign({},cBase.scales,{y:Object.assign({},cBase.scales.y,{min:0,max:100})})})
  });

  if(CH.macd)CH.macd.destroy();
  CH.macd=new Chart(document.getElementById('macdChart'),{
    type:'bar',data:{labels:dl,datasets:[
      {data:histl,backgroundColor:histl.map(function(v){return v>=0?'rgba(0,229,160,.7)':'rgba(255,68,102,.7)';}),order:2},
      {data:mll,type:'line',borderColor:'#4488ff',borderWidth:1.5,fill:false,pointRadius:0,tension:.3,order:1},
      {data:sigl,type:'line',borderColor:'#ffb800',borderWidth:1.5,fill:false,pointRadius:0,tension:.3,order:1},
    ]},options:cBase
  });
}

function findSigPts(closes,offset,sl){
  var out=[],S20=sma(closes,20),S50=sma(closes,50),RSI=calcRSI(closes);
  for(var i=offset+1;i<closes.length;i++){
    if(!RSI[i]||!S20[i]||!S50[i])continue;
    if(RSI[i-1]<30&&RSI[i]>=30)out.push({i:i,t:'B'});
    else if(RSI[i-1]>70&&RSI[i]<=70)out.push({i:i,t:'S'});
    if(S20[i-1]<S50[i-1]&&S20[i]>=S50[i])out.push({i:i,t:'B'});
    else if(S20[i-1]>S50[i-1]&&S20[i]<=S50[i])out.push({i:i,t:'S'});
  }
  return out;
}

// ── Gauge ─────────────────────────────────────────────────────────────────────
function renderGauge(val){
  var cs=['#ff4466','#ff8800','#ffb800','#84cc16','#00e5a0'];
  var color=val<25?cs[0]:val<45?cs[1]:val<55?cs[2]:val<75?cs[3]:cs[4];
  var name=val<25?'Extreme Angst':val<45?'Angst':val<55?'Neutral':val<75?'Gier':'Extreme Gier';
  var desc=val<35?'Markt in Panik – historisch gute Einstiegszeitpunkte':val<55?'Anleger vorsichtig':val<75?'Optimismus steigt':'Überhitzter Markt – Vorsicht';
  function toR(d){return d*Math.PI/180;}
  var cx=55,cy=52,r=42,ang=-90+(val/100)*180;
  var paths=cs.map(function(c,i){var sa=-90+i*36,ea=sa+35;return'<path d="M'+cx+' '+cy+'L'+(cx+r*Math.cos(toR(sa)))+' '+(cy+r*Math.sin(toR(sa)))+'A'+r+' '+r+' 0 0 1 '+(cx+r*Math.cos(toR(ea)))+' '+(cy+r*Math.sin(toR(ea)))+'Z" fill="'+c+'" opacity="0.25"/>';}).join('');
  document.getElementById('gauge-svg').innerHTML=paths+'<line x1="'+cx+'" y1="'+cy+'" x2="'+(cx+r*.76*Math.cos(toR(ang)))+'" y2="'+(cy+r*.76*Math.sin(toR(ang)))+'" stroke="'+color+'" stroke-width="2.5" stroke-linecap="round"/><circle cx="'+cx+'" cy="'+cy+'" r="4" fill="'+color+'"/><text x="'+cx+'" y="'+(cy+13)+'" text-anchor="middle" fill="'+color+'" font-size="13" font-weight="700">'+val+'</text>';
  document.getElementById('fg-num').textContent=val;document.getElementById('fg-num').style.color=color;
  document.getElementById('fg-name').textContent=name;document.getElementById('fg-name').style.color=color;
  document.getElementById('fg-desc').textContent=desc;
}

// ── Auto Refresh ──────────────────────────────────────────────────────────────
function startRefresh(sym){
  if(refreshTimer)clearInterval(refreshTimer);
  refreshTimer=setInterval(async function(){
    try{
      var q=await apiGet('/api/quote?symbol='+sym);
      if(!q.price)return;
      document.getElementById('ph-price').textContent='$'+q.price.toFixed(2);
      var chg=((q.price-q.prev)/q.prev*100),isUp=chg>=0;
      var cp=document.getElementById('chg-pill');
      cp.textContent=(isUp?'▲ +':'▼ ')+Math.abs(chg).toFixed(2)+'%';
      cp.className='pill '+(isUp?'pill-up':'pill-down');
      document.getElementById('tb-sub').textContent=sym+' · '+new Date().toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'});
    }catch(e){}
  },30000);
}

// ── Server Signale laden ──────────────────────────────────────────────────────
async function loadServerSignals(){
  try{
    var data=await apiGet('/signals');
    var el=document.getElementById('sig-list');
    if(!data.signals||!data.signals.length){el.innerHTML='<div class="empty">Noch keine Server-Signale.<br>Erste Analyse läuft automatisch...</div>';return;}
    el.innerHTML=data.signals.map(function(s){
      var isBuy='KAUF' in s.action||s.action.includes('KAUF');
      var color=isBuy?'buy':s.action.includes('VERK')?'sell':'hold';
      return'<div class="sr '+color+'"><div class="sr-badge '+color+'">'+s.action+'</div><div class="sr-sym">'+s.symbol+'</div><div class="sr-info"><div class="sr-price">$'+s.price.toFixed(2)+' <span style="color:'+(s.change>=0?'var(--buy)':'var(--sell)')+'font-size:.72rem">'+(s.change>=0?'+':'')+s.change.toFixed(2)+'%</span></div><div class="sr-sigs">'+(s.signals||[]).slice(0,2).join(' · ')+'</div></div><div class="sr-right"><div class="sr-score" style="color:'+(s.score>0?'var(--buy)':s.score<0?'var(--sell)':'var(--muted)')+'">'+(s.score>0?'+':'')+s.score+'</div><div style="font-size:.62rem;color:var(--muted);font-family:\'JetBrains Mono\',monospace;text-align:right">'+s.confidence+'</div><div class="sr-time">'+s.time+'</div></div></div>';
    }).join('');
  }catch(e){}
}

// ── Navigation ────────────────────────────────────────────────────────────────
function switchPage(id,btn){
  document.querySelectorAll('.page').forEach(function(p){p.classList.remove('active');});
  document.querySelectorAll('.nbtn').forEach(function(b){b.classList.remove('active');});
  document.getElementById('p-'+id).classList.add('active');
  btn.classList.add('active');
  if(id==='signals')loadServerSignals();
}
function switchChart(id,btn){
  document.querySelectorAll('.cbody').forEach(function(b){b.classList.remove('active');});
  document.querySelectorAll('.ctab').forEach(function(b){b.classList.remove('active');});
  document.getElementById('cb-'+id).classList.add('active');btn.classList.add('active');
}
function qLoad(sym,el){
  document.querySelectorAll('.chip').forEach(function(c){c.classList.remove('active');});
  el.classList.add('active');
  loadSym(sym);
}

// ── Start ─────────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded',function(){loadSym('AAPL');});
</script>
</body>
</html>"""

# ══════════════════════════════════════════════════════════════════════════════
# INDIKATOREN (Server-seitig)
# ══════════════════════════════════════════════════════════════════════════════
def srv_sma(c, p):
    return [None if i < p-1 else sum(c[i-p+1:i+1])/p for i in range(len(c))]

def srv_ema(c, p):
    k, o = 2/(p+1), []
    for i, v in enumerate(c): o.append(v if i == 0 else v*k + o[-1]*(1-k))
    return o

def srv_rsi(c, p=14):
    out = []
    for i in range(len(c)):
        if i < p: out.append(None); continue
        g = l = 0
        for j in range(i-p+1, i+1):
            d = c[j]-c[j-1]
            if d > 0: g += d
            else: l -= d
        out.append(100 - 100/(1+(100 if l == 0 else g/l)))
    return out

def srv_macd(c):
    e12 = srv_ema(c, 12); e26 = srv_ema(c, 26)
    ml  = [e12[i]-e26[i] for i in range(len(c))]
    sig = srv_ema(ml, 9)
    return ml, sig, [ml[i]-sig[i] for i in range(len(c))]

def srv_bollinger(c, p=20):
    s = srv_sma(c, p); up = []; lo = []
    for i, m in enumerate(s):
        if m is None: up.append(None); lo.append(None); continue
        w = c[i-p+1:i+1]; std = (sum((x-m)**2 for x in w)/p)**.5
        up.append(m+2*std); lo.append(m-2*std)
    return up, lo

def srv_momentum(c, p=10):
    return [None if i < p else (c[i]/c[i-p]-1)*100 for i in range(len(c))]

def full_analysis(symbol, closes, volumes):
    n = len(closes) - 1
    if n < 55: return None
    price = closes[n]; prev = closes[n-1]
    S20 = srv_sma(closes, 20); S50 = srv_sma(closes, 50)
    RSI = srv_rsi(closes)
    _, _, hist = srv_macd(closes)
    bb_up, bb_lo = srv_bollinger(closes)
    mom = srv_momentum(closes)
    rv = RSI[n]; hv = hist[n]; hv1 = hist[n-1] if n > 0 else 0
    if None in (rv, S20[n], S50[n], hv, bb_up[n], bb_lo[n]): return None

    buy = []; sell = []
    if rv < 30: buy.append(f"RSI überverkauft ({rv:.1f})")
    elif rv > 70: sell.append(f"RSI überkauft ({rv:.1f})")
    if hv > 0 and hv1 <= 0: buy.append("MACD Crossover ↑")
    elif hv < 0 and hv1 >= 0: sell.append("MACD Crossover ↓")
    elif hv > 0: buy.append("MACD bullisch")
    else: sell.append("MACD bearisch")
    if S20[n-1] and S50[n-1]:
        if S20[n-1] < S50[n-1] and S20[n] >= S50[n]: buy.append("Golden Cross ✨")
        elif S20[n-1] > S50[n-1] and S20[n] <= S50[n]: sell.append("Death Cross ⚠️")
    if S20[n] > S50[n]: buy.append("Aufwärtstrend")
    else: sell.append("Abwärtstrend")
    if price > S20[n]: buy.append("Über SMA20")
    else: sell.append("Unter SMA20")
    if price <= bb_lo[n]: buy.append("Unteres Bollinger Band")
    elif price >= bb_up[n]: sell.append("Oberes Bollinger Band")
    if mom[n] is not None:
        if mom[n] > 3: buy.append(f"Momentum +{mom[n]:.1f}%")
        elif mom[n] < -3: sell.append(f"Momentum {mom[n]:.1f}%")
    if volumes and len(volumes) >= 20:
        avg_v = sum(volumes[n-19:n]) / 20
        if avg_v > 0 and volumes[n] > avg_v * 1.5:
            if price > prev: buy.append(f"Hohes Volumen ({volumes[n]/avg_v:.1f}x)")
            else: sell.append(f"Hohes Abgabe-Volumen ({volumes[n]/avg_v:.1f}x)")

    net = len(buy) - len(sell)
    if net >= 4: action, conf = "KAUFEN", "STARK"
    elif net >= 2: action, conf = "EHER KAUFEN", "MITTEL"
    elif net <= -4: action, conf = "VERKAUFEN", "STARK"
    elif net <= -2: action, conf = "EHER VERKAUFEN", "MITTEL"
    else: action, conf = "HALTEN", "NEUTRAL"

    return dict(symbol=symbol, price=round(price,2), change=round((price-prev)/prev*100,2),
                rsi=round(rv,1), s20=round(S20[n],2), s50=round(S50[n],2),
                net=net, action=action, confidence=conf,
                buy_signals=buy, sell_signals=sell,
                stop_loss=round(price*(.97 if net>0 else 1.03),2))

# ══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS (Frontend ruft diese auf – kein API-Key im Browser!)
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/candles")
def api_candles():
    sym = request.args.get("symbol", "AAPL").upper()
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={sym}&interval=1day&outputsize=90&apikey={API_KEY}"
        r = req.get(url, timeout=20); d = r.json()
        if d.get("status") == "error": return jsonify({"error": d.get("message","Unbekanntes Symbol")}), 400
        vals = list(reversed(d["values"]))
        return jsonify({
            "closes": [float(v["close"]) for v in vals],
            "dates":  [v["datetime"][:10] for v in vals],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/quote")
def api_quote():
    sym = request.args.get("symbol", "AAPL").upper()
    try:
        url = f"https://api.twelvedata.com/quote?symbol={sym}&apikey={API_KEY}"
        r = req.get(url, timeout=15); d = r.json()
        if "close" not in d: return jsonify({"error": "Symbol nicht gefunden"}), 400
        return jsonify({
            "price": float(d.get("close", 0)),
            "prev":  float(d.get("previous_close", 0)),
            "name":  d.get("name", sym),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/signals")
def api_signals():
    return jsonify({"signals": signal_history[:30], "scan_count": scan_count})

@app.route("/ping")
def ping():
    return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})

# ══════════════════════════════════════════════════════════════════════════════
# PUSH NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════════
def send_push(title, message, priority="high", tags=""):
    if not NTFY_TOPIC:
        print(f"[PUSH] {title}: {message[:80]}")
        return
    try:
        req.post(f"https://ntfy.sh/{NTFY_TOPIC}",
                 data=message.encode("utf-8"),
                 headers={"Title": title, "Priority": priority, "Tags": tags},
                 timeout=10)
        print(f"[📲] {title}")
    except Exception as e:
        print(f"[Push Fehler] {e}")

def notify(result):
    sym = result["symbol"]; action = result["action"]
    if action == "HALTEN": return
    key = f"{sym}_{action}"
    if last_action.get(sym) == key: return
    last_action[sym] = key
    is_buy = "KAUF" in action
    sigs = result["buy_signals"] if is_buy else result["sell_signals"]
    chg = result["change"]
    title = f"{'📈' if is_buy else '📉'} {action}: {sym} [{result['confidence']}]"
    msg   = (f"Kurs: ${result['price']} ({'+'if chg>=0 else ''}{chg:.2f}%)\n"
             f"Signale: {' | '.join(sigs[:3])}\n"
             f"RSI: {result['rsi']} | Score: {result['net']:+d}/8\n"
             f"Stop-Loss: ${result['stop_loss']}")
    prio  = "urgent" if result["confidence"] == "STARK" else "high"
    tags  = "chart_with_upwards_trend,bell" if is_buy else "chart_with_downwards_trend,warning"
    send_push(title, msg, prio, tags)
    signal_history.insert(0, {
        "time": datetime.now(timezone.utc).strftime("%d.%m %H:%M"),
        "symbol": sym, "action": action, "confidence": result["confidence"],
        "price": result["price"], "change": chg, "score": result["net"],
        "signals": sigs[:3],
    })
    if len(signal_history) > 100: signal_history.pop()

# ══════════════════════════════════════════════════════════════════════════════
# SCANNER LOOP
# ══════════════════════════════════════════════════════════════════════════════
def scan_loop():
    global scan_count
    print(f"[START] Scanner: {WATCHLIST} | Intervall: {CHECK_INTERVAL}s")
    time.sleep(8)
    send_push("✅ StockSignal Pro Online",
              f"Überwache: {', '.join(WATCHLIST)}\nIntervall: {CHECK_INTERVAL//60} Min",
              "default", "rocket")
    while True:
        scan_count += 1
        print(f"\n[SCAN #{scan_count}] {datetime.now(timezone.utc).strftime('%H:%M UTC')}")
        for sym in WATCHLIST:
            try:
                url = f"https://api.twelvedata.com/time_series?symbol={sym}&interval=1day&outputsize=90&apikey={API_KEY}"
                d   = req.get(url, timeout=20).json()
                if d.get("status") == "error": continue
                vals    = list(reversed(d["values"]))
                closes  = [float(v["close"]) for v in vals]
                volumes = [float(v.get("volume", 0)) for v in vals]
                result  = full_analysis(sym, closes, volumes)
                if result:
                    print(f"  {sym}: ${result['price']} | Score:{result['net']:+d} | {result['action']}")
                    notify(result)
                time.sleep(2)
            except Exception as e:
                print(f"  [{sym}] Fehler: {e}")
        print(f"[FERTIG] Nächster Scan in {CHECK_INTERVAL//60} Min")
        time.sleep(CHECK_INTERVAL)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN ROUTE – liefert die PWA App
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template_string(
        FRONTEND,
        interval=CHECK_INTERVAL // 60,
        watchlist=", ".join(WATCHLIST)
    )

if __name__ == "__main__":
    threading.Thread(target=scan_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
