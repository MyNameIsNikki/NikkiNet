ADMIN_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NikkiNet</title>
<style>
  :root{
    color-scheme:dark;
    --bg:#05060d;
    --bg2:#090c16;
    --surface:linear-gradient(180deg,rgba(11,15,26,.97),rgba(6,9,17,.97));
    --border:#1d2b45;
    --border2:#2b4468;
    --text:#e8f7ff;
    --muted:#7f9bb8;
    --accent:#00f0ff;
    --accent2:#5ffcff;
    --magenta:#ff2bd6;
    --violet:#8a2be2;
    --yellow:#f7ff3c;
    --ok:#39ff88;
    --err:#ff3860;
    --warn:#ffcc00;
    --radius:2px;
    --shadow:0 0 0 1px rgba(0,240,255,.10),0 18px 50px rgba(0,0,0,.55);
    --grad:linear-gradient(100deg,#00f0ff,#ff2bd6);
    --mono:'Cascadia Code','Consolas','Courier New',monospace;
    --ease:cubic-bezier(.4,0,.2,1);
    --spring:cubic-bezier(.34,1.4,.64,1);
  }
  *{box-sizing:border-box;}
  html{scrollbar-width:thin;scrollbar-color:rgba(0,240,255,.3)transparent;}
  body{margin:0;font-family:'Segoe UI',system-ui,-apple-system,Roboto,sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;overflow-x:hidden;min-height:100vh;}
  body::before{content:'';position:fixed;inset:0;z-index:-2;pointer-events:none;background-image:linear-gradient(rgba(0,240,255,.055) 1px,transparent 1px),linear-gradient(90deg,rgba(0,240,255,.055) 1px,transparent 1px);background-size:48px 48px;mask-image:radial-gradient(circle at 50% 12%,#000 0%,transparent 78%);-webkit-mask-image:radial-gradient(circle at 50% 12%,#000 0%,transparent 78%);}
  body::after{content:'';position:fixed;inset:0;z-index:9999;pointer-events:none;background:repeating-linear-gradient(0deg,rgba(0,0,0,.16) 0 1px,transparent 1px 4px);opacity:.18;}
  ::selection{background:rgba(255,43,214,.45);color:#fff;}
  ::-webkit-scrollbar{width:10px;height:10px;}
  ::-webkit-scrollbar-thumb{background:rgba(0,240,255,.25);border-radius:0;border:2px solid transparent;background-clip:content-box;}
  ::-webkit-scrollbar-thumb:hover{background:rgba(255,43,214,.45);border:2px solid transparent;background-clip:content-box;}
  ::-webkit-scrollbar-track{background:rgba(0,0,0,.25);}
  :focus-visible{outline:2px solid var(--magenta);outline-offset:2px;}
  button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:none;box-shadow:0 0 0 2px var(--magenta),0 0 18px rgba(255,43,214,.35);}

  .bgfx{position:fixed;inset:0;z-index:-1;overflow:hidden;background:radial-gradient(900px 520px at 80% -10%,rgba(255,43,214,.10),transparent 60%),radial-gradient(800px 600px at -10% 110%,rgba(0,240,255,.10),transparent 60%),linear-gradient(180deg,#070a13,#04050b 70%);}
  .orb{position:absolute;border-radius:50%;filter:blur(110px);animation:float 24s ease-in-out infinite;}
  .o1{width:460px;height:460px;background:#00f0ff;top:-160px;left:6%;opacity:.16;animation-duration:24s;}
  .o2{width:390px;height:390px;background:#ff2bd6;bottom:-130px;right:2%;opacity:.14;animation-duration:28s;animation-delay:-9s;}
  .o3{width:280px;height:280px;background:#8a2be2;top:44%;left:58%;opacity:.16;animation-duration:32s;animation-delay:-16s;}
  @keyframes float{0%,100%{transform:translate(0,0)scale(1);}33%{transform:translate(46px,-34px)scale(1.08);}66%{transform:translate(-34px,28px)scale(.94);}}

  header{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:12px 20px;background:rgba(5,6,13,.93);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid rgba(0,240,255,.28);box-shadow:0 1px 0 rgba(255,43,214,.18),0 10px 34px rgba(0,0,0,.5);}
  header::after{content:'';position:absolute;left:0;right:0;bottom:-1px;height:1px;background:linear-gradient(90deg,transparent,var(--accent),var(--magenta),transparent);opacity:.8;}
  .logo{width:44px;height:44px;border-radius:0;background:linear-gradient(135deg,#00f0ff 0%,#8a2be2 52%,#ff2bd6 100%);display:flex;align-items:center;justify-content:center;font-family:var(--mono);font-weight:900;font-size:25px;color:#02040a;box-shadow:0 0 22px rgba(0,240,255,.45),inset 0 0 18px rgba(255,255,255,.35);clip-path:polygon(0 9px,9px 0,100% 0,100% calc(100% - 9px),calc(100% - 9px) 100%,0 100%);flex:0 0 auto;animation:logoFlicker 7s infinite;}
  @keyframes logoFlicker{0%,93%,100%{filter:none;}94%{filter:brightness(1.8) saturate(1.5);}95%{filter:none;}96%{filter:hue-rotate(25deg);}97%{filter:none;}}
  .brand h1{font-family:var(--mono);font-size:18px;margin:0;letter-spacing:2.4px;text-transform:uppercase;color:#fff;text-shadow:0 0 12px rgba(0,240,255,.55),2px 0 0 rgba(255,43,214,.35);}
  .brand .sub{color:var(--magenta);font-family:var(--mono);font-size:9.5px;letter-spacing:2.2px;margin-top:1px;text-transform:uppercase;}
  .tabs{display:flex;gap:4px;background:rgba(0,240,255,.03);padding:3px;border-radius:0;border:1px solid rgba(0,240,255,.18);clip-path:polygon(0 6px,6px 0,100% 0,100% calc(100% - 6px),calc(100% - 6px) 100%,0 100%);overflow-x:auto;max-width:100%;}
  .tab{padding:8px 15px;border-radius:0;cursor:pointer;color:var(--muted);font-family:var(--mono);font-size:11px;font-weight:700;letter-spacing:.9px;text-transform:uppercase;transition:all .2s var(--ease);white-space:nowrap;}
  .tab:hover{color:var(--accent2);background:rgba(0,240,255,.08);}
  .tab.active{color:#fff;background:linear-gradient(100deg,rgba(0,240,255,.18),rgba(255,43,214,.18));box-shadow:inset 0 0 0 1px rgba(0,240,255,.55),0 0 18px rgba(0,240,255,.16);text-shadow:0 0 10px rgba(0,240,255,.55);}
  .hdr-actions{margin-left:auto;display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end;}

  main{padding:22px;max-width:1240px;margin:0 auto;}
  main section{animation:fadeUp .35s var(--ease);}
  .card{position:relative;background:var(--surface);border:1px solid rgba(0,240,255,.20);border-radius:var(--radius);padding:20px 20px 18px;margin-bottom:18px;box-shadow:var(--shadow);animation:fadeUp .5s cubic-bezier(.22,1,.36,1) both;transition:border-color .25s var(--ease),box-shadow .25s var(--ease);clip-path:polygon(0 12px,12px 0,100% 0,100% calc(100% - 12px),calc(100% - 12px) 100%,0 100%);}
  .card::before{content:'';position:absolute;inset:0 0 auto 0;height:1px;background:linear-gradient(90deg,transparent,rgba(0,240,255,.6),rgba(255,43,214,.5),transparent);}
  .card::after{content:'';position:absolute;top:0;right:0;width:56px;height:2px;background:var(--magenta);box-shadow:0 0 12px var(--magenta);}
  .card:hover{border-color:rgba(0,240,255,.42);box-shadow:0 0 0 1px rgba(0,240,255,.12),0 0 32px rgba(0,240,255,.07),0 18px 50px rgba(0,0,0,.55);}
  .card h2{margin:0 0 14px;font-family:var(--mono);font-size:11.5px;font-weight:800;color:var(--accent2);letter-spacing:1.6px;text-transform:uppercase;text-shadow:0 0 10px rgba(0,240,255,.35);}
  .card h2::before{content:'// ';color:var(--magenta);text-shadow:0 0 10px rgba(255,43,214,.5);}
  section .card:nth-child(2){animation-delay:.07s;}
  section .card:nth-child(3){animation-delay:.14s;}
  @keyframes fadeUp{from{opacity:0;transform:translateY(14px);}to{opacity:1;transform:none;}}

  .table-scroll{overflow-x:auto;margin:0 -4px;padding:0 4px;}
  table{width:100%;border-collapse:separate;border-spacing:0;font-size:12.5px;min-width:760px;}
  th,td{padding:9px 8px;border-bottom:1px solid rgba(0,240,255,.09);text-align:left;vertical-align:middle;}
  th{color:var(--accent);font-family:var(--mono);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;border-bottom:1px solid rgba(0,240,255,.32);white-space:nowrap;}
  tbody tr{transition:background .15s var(--ease);}
  tbody tr:hover{background:rgba(0,240,255,.055);}
  tr.active{background:linear-gradient(90deg,rgba(255,43,214,.20),rgba(255,43,214,.02));box-shadow:inset 3px 0 0 var(--magenta);}
  td .tag{font-size:9.5px;}

  button{cursor:pointer;border:1px solid rgba(0,240,255,.35);border-radius:0;padding:8px 13px;font-size:11.5px;font-weight:700;color:var(--accent2);background:rgba(0,240,255,.045);transition:all .18s var(--ease);font-family:var(--mono);letter-spacing:.4px;text-transform:uppercase;clip-path:polygon(0 5px,5px 0,100% 0,100% calc(100% - 5px),calc(100% - 5px) 100%,0 100%);}
  button:hover{background:rgba(0,240,255,.14);border-color:var(--accent);color:#fff;box-shadow:0 0 18px rgba(0,240,255,.22);transform:translateY(-1px);}
  button:active{transform:translateY(0)scale(.97);}
  button.primary{background:linear-gradient(100deg,#00f0ff,#ff2bd6);color:#02040a;border-color:transparent;font-weight:900;box-shadow:0 0 22px rgba(0,240,255,.22);}
  button.primary:hover{box-shadow:0 0 28px rgba(255,43,214,.42);filter:brightness(1.1);color:#02040a;}
  button.primary:disabled{animation:busyPulse 1.1s ease-in-out infinite;cursor:wait;transform:none;}
  button.danger{background:rgba(255,56,96,.07);border-color:rgba(255,56,96,.55);color:#ff8fa5;}
  button.danger:hover{background:rgba(255,56,96,.2);border-color:var(--err);color:#fff;box-shadow:0 0 18px rgba(255,56,96,.3);}
  button.sm{padding:5px 9px;font-size:10px;border-radius:0;}
  button:disabled{opacity:.5;cursor:wait;transform:none;}
  @keyframes busyPulse{0%,100%{filter:brightness(.92);}50%{filter:brightness(1.25);}}

  input,select,textarea{background:rgba(0,240,255,.035);border:1px solid rgba(0,240,255,.22);color:var(--text);border-radius:0;padding:8px 10px;font-size:12.5px;transition:border-color .2s,box-shadow .2s;font-family:var(--mono);}
  input:focus,select:focus,textarea:focus{outline:none;border-color:var(--magenta);box-shadow:0 0 0 1px var(--magenta),0 0 18px rgba(255,43,214,.18);}
  input[type=checkbox],input[type=radio]{accent-color:var(--accent);cursor:pointer;}
  textarea{font-family:var(--mono);}
  select option{background:#0a0e18;color:var(--text);}

  .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;min-width:0;}
  .grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;}
  .grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;}
  .tag{font-size:9.5px;padding:3px 8px;border-radius:0;background:rgba(0,240,255,.04);border:1px solid rgba(0,240,255,.25);color:var(--muted);white-space:nowrap;font-family:var(--mono);letter-spacing:.4px;text-transform:uppercase;}
  .tag.ok{color:var(--ok);border-color:rgba(57,255,136,.45);box-shadow:0 0 10px rgba(57,255,136,.12);}
  .ok{color:var(--ok);} .err{color:var(--err);} .warn{color:var(--warn);}
  .dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:7px;}
  .ok-dot{background:var(--ok);box-shadow:0 0 10px var(--ok);animation:pulse 2s infinite;}
  .err-dot{background:var(--err);box-shadow:0 0 10px var(--err);}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(57,255,136,.55);}70%{box-shadow:0 0 0 7px rgba(57,255,136,0);}100%{box-shadow:0 0 0 0 rgba(57,255,136,0);}}
  .switch{display:flex;align-items:center;gap:10px;font-size:12px;cursor:pointer;user-select:none;font-family:var(--mono);letter-spacing:.3px;}
  .switch input[type=checkbox]{appearance:none;-webkit-appearance:none;width:42px;height:22px;border-radius:0;background:#1a2337;border:1px solid rgba(0,240,255,.45);position:relative;transition:all .2s var(--ease);flex:0 0 auto;cursor:pointer;clip-path:polygon(0 4px,4px 0,100% 0,100% calc(100% - 4px),calc(100% - 4px) 100%,0 100%);}
  .switch input[type=checkbox]::after{content:'';position:absolute;width:14px;height:14px;border-radius:0;background:#6b7fa3;top:3px;left:3px;transition:all .2s var(--ease);}
  .switch input[type=checkbox]:checked{background:rgba(0,240,255,.22);border-color:var(--accent);box-shadow:0 0 14px rgba(0,240,255,.25);}
  .switch input[type=checkbox]:checked::after{left:23px;background:var(--accent);box-shadow:0 0 10px var(--accent);}
  .seg{display:flex;gap:3px;background:rgba(0,240,255,.03);border:1px solid rgba(0,240,255,.2);border-radius:0;padding:3px;flex-wrap:wrap;}
  .seg button{border-radius:0;padding:6px 11px;background:transparent;border-color:transparent;font-size:10.5px;}
  .seg button.on{background:linear-gradient(100deg,rgba(0,240,255,.2),rgba(255,43,214,.18));color:#fff;box-shadow:inset 0 0 0 1px rgba(0,240,255,.5);}
  .muted{color:var(--muted);font-size:11.5px;}

  #qc-grid{display:flex;flex-wrap:wrap;gap:7px;justify-content:center;}
  .qc-hero{text-align:center;padding:4px 0 2px;}
  .qc-shield-line{display:flex;align-items:baseline;justify-content:center;gap:12px;margin-bottom:14px;flex-wrap:wrap;}
  .qc-state{font-family:var(--mono);font-size:15px;font-weight:900;letter-spacing:4px;text-transform:uppercase;transition:color .4s var(--ease);}
  .qc-state.on{color:var(--ok);text-shadow:0 0 12px rgba(57,255,136,.7),0 0 34px rgba(57,255,136,.3);}
  .qc-state.off{color:var(--err);text-shadow:0 0 12px rgba(255,56,96,.45);}
  .qc-timer{font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums;min-width:70px;text-align:left;font-family:var(--mono);}
  .power{width:104px;height:104px;border-radius:50%;padding:0;margin:0 auto 14px;display:flex;align-items:center;justify-content:center;background:radial-gradient(circle at 50% 50%,rgba(0,240,255,.09),transparent 65%),#070b13;border:2px solid rgba(0,240,255,.4);color:var(--accent);transition:all .35s var(--ease);position:relative;box-shadow:0 0 0 6px rgba(0,240,255,.03),inset 0 0 28px rgba(0,240,255,.08);clip-path:none;}
  .power::before{content:'';position:absolute;inset:-10px;border-radius:50%;border:1px dashed rgba(0,240,255,.25);animation:spin 18s linear infinite;pointer-events:none;}
  .power:hover{transform:scale(1.05);color:#fff;border-color:var(--magenta);box-shadow:0 0 30px rgba(255,43,214,.28),inset 0 0 28px rgba(255,43,214,.12);}
  .power:active{transform:scale(.94);}
  .power.on{color:#02040a;border-color:var(--ok);background:radial-gradient(circle at 50% 50%,#39ff88,#00a86b);box-shadow:0 0 28px rgba(57,255,136,.55),0 0 70px rgba(57,255,136,.2),inset 0 0 22px rgba(255,255,255,.35);animation:powerPulse 2.6s var(--ease) infinite;}
  .power.on::before{border-color:rgba(57,255,136,.4);}
  .power.on:hover{filter:brightness(1.08);transform:scale(1.05);}
  .power.on svg{filter:drop-shadow(0 0 6px rgba(255,255,255,.6));}
  .power.busy{border-color:var(--magenta);color:var(--magenta);animation:none;}
  .power.busy svg{animation:spin 1s linear infinite;}
  @keyframes powerPulse{0%{box-shadow:0 0 28px rgba(57,255,136,.55),0 0 0 0 rgba(57,255,136,.5);}70%{box-shadow:0 0 28px rgba(57,255,136,.55),0 0 0 22px rgba(57,255,136,0);}100%{box-shadow:0 0 28px rgba(57,255,136,.55),0 0 0 0 rgba(57,255,136,0);}}
  @keyframes spin{to{transform:rotate(360deg);}}
  .qc-info{margin-bottom:12px;font-size:13px;color:var(--muted);min-height:20px;transition:color .3s;font-family:var(--mono);}
  .qc-info b{color:#fff;}
  .hdr-conn{display:inline-flex;align-items:center;gap:8px;padding:3px 5px 3px 11px;border-radius:0;background:rgba(57,255,136,.07);border:1px solid rgba(57,255,136,.4);font-size:11px;color:var(--ok);white-space:nowrap;font-family:var(--mono);clip-path:polygon(0 4px,4px 0,100% 0,100% calc(100% - 4px),calc(100% - 4px) 100%,0 100%);}
  .hdr-conn button{padding:2px 7px;font-size:10px;border-radius:0;background:rgba(255,56,96,.12);color:#ff8fa5;border:1px solid rgba(255,56,96,.4);}
  .hdr-conn button:hover{background:rgba(255,56,96,.28);color:#fff;}
  .qc-chip{display:flex;align-items:center;gap:7px;padding:7px 11px;border:1px solid rgba(0,240,255,.2);border-radius:0;cursor:pointer;font-size:11.5px;background:rgba(0,240,255,.025);transition:all .18s var(--ease);user-select:none;font-family:var(--mono);clip-path:polygon(0 4px,4px 0,100% 0,100% calc(100% - 4px),calc(100% - 4px) 100%,0 100%);max-width:100%;}
  .qc-chip:hover{transform:translateY(-2px);border-color:var(--accent);background:rgba(0,240,255,.09);box-shadow:0 0 18px rgba(0,240,255,.18);}
  .qc-chip.sel{border-color:transparent;background:linear-gradient(100deg,rgba(0,240,255,.2),rgba(255,43,214,.18));box-shadow:0 0 0 1px var(--accent),0 0 20px rgba(0,240,255,.2);transform:translateY(-1px);}
  .qc-chip:active{transform:scale(.97);}
  .qc-chip .d{color:var(--ok);font-size:10.5px;font-weight:700;white-space:nowrap;}
  .qc-chip .c{color:var(--muted);font-size:9.5px;white-space:nowrap;}
  #qc-status b{color:#fff;}

  #toast{position:fixed;top:16px;right:16px;max-width:calc(100vw - 32px);z-index:99;background:rgba(7,10,18,.96);backdrop-filter:blur(12px);border:1px solid var(--magenta);color:var(--text);padding:12px 16px;border-radius:0;font-size:12px;display:none;white-space:pre-wrap;box-shadow:0 0 24px rgba(255,43,214,.25),0 12px 40px rgba(0,0,0,.6);font-family:var(--mono);clip-path:polygon(0 7px,7px 0,100% 0,100% calc(100% - 7px),calc(100% - 7px) 100%,0 100%);animation:toastIn .35s var(--spring);}
  @keyframes toastIn{from{opacity:0;transform:translateX(36px)scale(.95);}to{opacity:1;transform:none;}}
  .upd-banner{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:14px auto 0;padding:10px 14px;border-radius:0;background:rgba(255,43,214,.07);border:1px solid rgba(255,43,214,.45);font-size:11.5px;max-width:1240px;width:calc(100% - 32px);box-sizing:border-box;position:relative;z-index:5;font-family:var(--mono);clip-path:polygon(0 6px,6px 0,100% 0,100% calc(100% - 6px),calc(100% - 6px) 100%,0 100%);}

  #logs{font-family:var(--mono);font-size:11.5px;max-height:300px;overflow:auto;background:rgba(0,0,0,.35);border:1px solid rgba(0,240,255,.2);border-radius:0;padding:10px;}
  #logs div{padding:2px 0;border-bottom:1px solid rgba(0,240,255,.06);white-space:pre-wrap;}
  #conns td{font-family:var(--mono);font-size:11.5px;}
  .dlong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:240px;font-family:var(--mono);}
  .modalbg{position:fixed;inset:0;background:rgba(3,4,9,.78);backdrop-filter:blur(5px);display:none;align-items:flex-start;justify-content:center;padding:40px 12px;z-index:50;animation:fadeIn .2s var(--ease);}
  .modal{background:linear-gradient(180deg,#0a0f1c,#060911);border:1px solid rgba(255,43,214,.5);border-radius:0;padding:20px;max-width:680px;width:100%;max-height:86vh;overflow:auto;box-shadow:0 0 40px rgba(255,43,214,.16),0 24px 80px rgba(0,0,0,.7);animation:modalIn .3s var(--spring);clip-path:polygon(0 12px,12px 0,100% 0,100% calc(100% - 12px),calc(100% - 12px) 100%,0 100%);}
  @keyframes modalIn{from{opacity:0;transform:translateY(18px)scale(.97);}to{opacity:1;transform:none;}}
  @keyframes fadeIn{from{opacity:0;}to{opacity:1;}}
  .hidden{display:none !important;}
  .span{font-size:11.5px;color:var(--muted);font-family:var(--mono);}

  @media(max-width:1000px){
    .hdr-actions{width:100%;justify-content:flex-start;margin-left:0;}
    .tabs{order:3;width:100%;}
  }
  @media(max-width:760px){
    main{padding:14px;}
    .grid4,.grid3{grid-template-columns:1fr;}
    header{padding:10px 12px;gap:10px;}
    .brand h1{font-size:15px;}
    .card{padding:16px 14px;}
    .qc-chip{font-size:10.5px;padding:6px 9px;}
    .power{width:92px;height:92px;}
  }
  @media(max-width:520px){
    .hdr-actions .tag{display:none;}
    .hdr-actions .tag#app-version{display:inline-block;}
    .qc-state{font-size:12px;letter-spacing:2px;}
    .qc-timer{min-width:0;}
    .modal{padding:14px;}
    .card h2{font-size:10.5px;letter-spacing:1.1px;}
  }
  @media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms !important;transition-duration:.01ms !important;}}
</style>
</head>
<body>
<div class="bgfx"><div class="orb o1"></div><div class="orb o2"></div><div class="orb o3"></div></div>
<header>
  <div class="logo">N</div>
  <div class="brand"><h1>NikkiNet</h1><div class="sub">прокси-менеджер</div></div>
  <div class="tabs">
    <div class="tab active" data-t="servers" onclick="showTab('servers')">Серверы</div>
    <div class="tab" data-t="subs" onclick="showTab('subs')">Подписки</div>
    <div class="tab" data-t="rules" onclick="showTab('rules')">Правила</div>
    <div class="tab" data-t="monitor" onclick="showTab('monitor')">Монитор</div>
  </div>
  <div class="hdr-actions">
    <span class="hdr-conn hidden" id="hdr-conn"><span class="dot ok-dot"></span><span id="hdr-conn-txt"></span><button class="sm" onclick="qcDisconnect()" title="Отключить">✕</button></span>
    <span class="tag" id="pool-status"></span>
    <span class="tag" id="app-version" title="Версия приложения"></span>
    <span class="tag" id="core-status">движок: ...</span>
    <button class="sm" onclick="reloadCore()">Перезапустить</button>
    <button class="sm danger" onclick="appExit()" title="Полностью выключить приложение (прокси и панель)">Выход</button>
  </div>
</header>
<div id="upd-banner" class="upd-banner hidden">
  <div>⬆ Доступно обновление до <b id="upd-ver"></b> <span class="muted" id="upd-cur"></span></div>
  <div style="display:flex;gap:8px">
    <button class="sm" id="upd-apply-btn" onclick="updApply()">Обновить и перезапустить</button>
    <button class="sm" onclick="updDetails()">Подробнее</button>
  </div>
</div>
<main>

  <section id="tab-servers">
    <div class="card" id="qc-card">
      <div class="qc-hero">
        <div class="qc-shield-line">
          <span class="qc-state" id="qc-state">НЕ ЗАЩИЩЕНЫ</span>
          <span class="qc-timer" id="qc-timer"></span>
        </div>
        <button id="power-btn" class="power" onclick="qcToggle()" title="Подключить / отключить">
          <svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true"><path d="M12 3v9" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" fill="none"/><path d="M17.6 6.4a8 8 0 1 1-11.2 0" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" fill="none"/></svg>
        </button>
        <div class="qc-info" id="qc-info">Нажмите кнопку — подключусь к самому быстрому серверу</div>
        <div class="row" style="justify-content:center;margin-bottom:14px">
          <button class="primary" id="qc-btn" onclick="qcConnect()">Подключиться</button>
          <button class="danger" onclick="qcDisconnect()">Отключиться</button>
        </div>
        <div id="qc-grid"></div>
        <div class="muted" style="margin-top:8px">Клик по стране — выбор, «Подключиться» — к её самому быстрому серверу (перед подключением перепроверю). <b>Если уже подключён — клик по другой стране мгновенно переключит.</b> Круглая кнопка: вкл/выкл.</div>
      </div>
    </div>

    <div class="card">
      <h2>Режим и переключатели</h2>
      <div class="row">
        <span class="span">Неопознанный трафик:</span>
        <div class="seg" id="mode-seg">
          <button data-m="proxy" onclick="setMode('proxy')">Прокси</button>
          <button data-m="direct" onclick="setMode('direct')">Напрямую</button>
          <button data-m="block" onclick="setMode('block')">Блок</button>
        </div>
        <span class="span">Выбор сервера:</span>
        <div class="seg" id="sel-seg">
          <button data-s="manual" onclick="setSelMode('manual')">Вручную</button>
          <button data-s="auto" onclick="setSelMode('auto')">Авто</button>
        </div>
        <label class="switch"><input type="checkbox" id="sp-toggle" onchange="setSystemProxy(this.checked)"> Системный прокси</label>
        <label class="switch"><input type="checkbox" id="vpn-toggle" onchange="setVpn(this.checked)"> Полный VPN (TUN)</label>
      </div>
      <div class="muted" id="listener-note" style="margin-top:8px"></div>
    </div>

    <div class="card">
      <h2>Доступ из локальной сети</h2>
      <div class="row">
        <label class="switch"><input type="checkbox" id="lan-toggle" onchange="setLan(this.checked)"> Разрешить другим устройствам</label>
        <span class="tag" id="lan-state">выключен</span>
      </div>
      <div id="lan-box" class="hidden" style="margin-top:12px">
        <div class="row">
          <span class="span">Адрес:</span><b class="ok" id="lan-addr">—</b>
          <span class="span">Логин:</span><input id="lan-user" style="width:130px" autocomplete="off">
          <span class="span">Пароль:</span><input id="lan-pass" type="password" style="width:170px" autocomplete="new-password" spellcheck="false"><button id="lan-pass-eye" onclick="toggleLanPass(this)">Показать</button>
          <button onclick="genLanPass()">Новый пароль</button>
          <button class="primary" onclick="saveLanCreds()">Применить</button>
        </div>
        <div class="muted" style="margin-top:8px">На телефоне или другом ПК в той же Wi-Fi сети укажите этот адрес как HTTP-прокси и введите логин с паролем. Порт открыт только для локальной подсети и только пока режим включён. Интерфейс приложения по-прежнему доступен только с этого компьютера.</div>
      </div>
    </div>

    <div class="card">
      <h2>Автосбор серверов из интернета</h2>
      <div class="row">
        <button class="primary" onclick="startParse('internet')">Собрать из интернета</button>
        <button onclick="startParse('lists')">Собрать из списков</button>
        <label class="switch"><input type="checkbox" id="np-deep" checked> Проверять через sing-box</label>
        <span class="tag" id="np-phase">ожидание</span>
      </div>
      <div class="muted" id="np-status" style="margin-top:8px">Соберёт серверы из GitHub-списков, публичных сайтов и seeds.txt, проверит их и добавит рабочие в NikkiNet. Без галочки проверки остаются только TCP-отклики — они часто не работают как прокси.</div>
      <div id="np-log" class="hidden" style="margin-top:8px;max-height:160px;overflow:auto;font-size:11px;white-space:pre-wrap"></div>
    </div>

    <div class="card">
      <h2 style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">Серверы <span class="muted" id="srv-sort-note" style="font-weight:400">(отсортированы по пингу; &gt;1500мс отбрасываются)</span>
        <select id="country-filter" onchange="this.dataset.v=this.value;renderServers()" style="margin-left:auto;max-width:300px" title="Фильтр по стране"></select>
      </h2>
      <div class="table-scroll"><table>
        <thead><tr><th style="width:26px"></th><th>Имя</th><th>Страна</th><th>Тип</th><th>Адрес</th><th>Задержка</th><th>Источник</th><th></th></tr></thead>
        <tbody id="srv-tbody"></tbody>
      </table></div>
      <div class="row" style="margin-top:12px">
        <textarea id="srv-text" rows="2" style="flex:1;min-width:220px" placeholder="Вставьте ссылки или ip:port, несколько в строку..."></textarea>
        <button class="primary" onclick="addServersText()">Импортировать</button>
      </div>
      <div class="row" style="margin-top:8px">
        <select id="n-type" style="width:120px">
          <option>http</option><option>https</option><option>socks</option>
          <option>vless</option><option>vmess</option><option>trojan</option><option>ss</option><option>hysteria2</option><option>tuic</option>
        </select>
        <input id="n-host" placeholder="host" style="flex:1;min-width:140px">
        <input id="n-port" placeholder="port" type="number" style="width:90px">
        <input id="n-name" placeholder="имя (необ.)" style="width:140px">
        <button onclick="addServerManual()">Добавить вручную</button>
        <button onclick="testAll()">Проверить все</button>
        <button onclick="purgeDead()">Удалить нерабочие</button>
        <button onclick="geoRefresh()">Определить страны</button>
        <button class="primary" onclick="addWarp()">+ Cloudflare WARP</button>
      </div>
    </div>
  </section>

  <section id="tab-subs" class="hidden">
    <div class="card">
      <h2>Подписки</h2>
      <div class="table-scroll"><table>
        <thead><tr><th>Имя</th><th>URL</th><th>Интервал (ч)</th><th>Обновлено</th><th>Серверов</th><th>Авто</th><th></th></tr></thead>
        <tbody id="sub-tbody"></tbody>
      </table></div>
      <div class="row" style="margin-top:12px">
        <input id="su-url" placeholder="https://example.com/sub" style="flex:1;min-width:220px">
        <input id="su-name" placeholder="имя (необ.)" style="width:160px">
        <input id="su-interval" type="number" value="24" style="width:80px" title="интервал обновления, часов">
        <button class="primary" onclick="addSub()">Добавить подписку</button>
      </div>
    </div>
  </section>

  <section id="tab-rules" class="hidden">
    <div class="card">
      <h2>Правила маршрутизации</h2>
      <div class="muted" style="margin-bottom:10px">Встроенные правила (не удаляются): private-сети и localhost → <b>direct</b>. Правила применяются сверху вниз, затем — режим «неопознанного трафика».</div>
      <div class="table-scroll"><table>
        <thead><tr><th>Действие</th><th>Домены (.суффикс)</th><th>Ключевые слова</th><th>IP/CIDR</th><th>PSN</th><th></th></tr></thead>
        <tbody id="rule-tbody"></tbody>
      </table></div>
      <div class="row" style="margin-top:12px">
        <button class="primary" onclick="addRuleRow()">Добавить правило</button>
        <button onclick="saveRules()">Сохранить правила</button>
      </div>
    </div>
  </section>

  <section id="tab-monitor" class="hidden">
    <div class="card">
      <h2>Активные подключения</h2>
      <div class="muted" id="conn-total" style="margin-bottom:8px"></div>
      <div class="table-scroll"><table><thead><tr><th>Целевой адрес</th><th>Возраст (с)</th><th>Протокол</th></tr></thead><tbody id="conn-tbody"></tbody></table></div>
    </div>
    <div class="card">
      <h2>Журнал движка (sing-box)</h2>
      <div id="logs">--</div>
    </div>
  </section>
</main>

<div class="modalbg" id="modal-bg">
  <div class="modal">
    <h2 id="modal-title" style="margin:0 0 12px">Изменить сервер</h2>
    <div class="grid4">
      <input id="e-name" placeholder="Имя">
      <input id="e-host" placeholder="host">
      <input id="e-port" placeholder="port" type="number">
      <select id="e-type">
        <option>http</option><option>https</option><option>socks</option>
        <option>vless</option><option>vmess</option><option>trojan</option><option>ss</option><option>hysteria2</option><option>tuic</option>
      </select>
      <input id="e-user" placeholder="username (http/socks)">
      <input id="e-pass" placeholder="password">
      <input id="e-uuid" placeholder="uuid (vless/vmess)">
      <input id="e-method" placeholder="метод шифрования (ss)">
      <input id="e-flow" placeholder="flow (vless)">
      <select id="e-sec"><option value="">security: none</option><option value="tls">tls</option><option value="reality">reality</option></select>
      <input id="e-sni" placeholder="SNI">
      <input id="e-fp" placeholder="fingerprint (chrome)">
      <input id="e-pbk" placeholder="reality public key">
      <input id="e-sid" placeholder="reality short id">
      <select id="e-transport"><option value="">tcp</option><option value="ws">ws</option><option value="grpc">grpc</option><option value="http">http</option></select>
      <input id="e-path" placeholder="path (ws)">
      <input id="e-hosthdr" placeholder="Host / serverName (ws/grpc)">
    </div>
    <div class="row" style="margin-top:14px;justify-content:flex-end">
      <button onclick="closeModal()">Отмена</button>
      <button class="primary" onclick="saveServerEdit()">Сохранить</button>
    </div>
  </div>
</div>

<script>
let state=null, editId=null;
const COUNTRY_RU={AF:'Афганистан',AL:'Албания',DZ:'Алжир',AD:'Андорра',AO:'Ангола',AR:'Аргентина',AM:'Армения',AU:'Австралия',AT:'Австрия',AZ:'Азербайджан',BS:'Багамы',BH:'Бахрейн',BD:'Бангладеш',BB:'Барбадос',BY:'Беларусь',BE:'Бельгия',BZ:'Белиз',BJ:'Бенин',BO:'Боливия',BA:'Босния и Герцеговина',BW:'Ботсвана',BR:'Бразилия',BN:'Бруней',BG:'Болгария',BF:'Буркина-Фасо',BI:'Бурунди',KH:'Камбоджа',CM:'Камерун',CA:'Канада',CV:'Кабо-Верде',CF:'ЦАР',TD:'Чад',CL:'Чили',CN:'Китай',CO:'Колумбия',CR:'Коста-Рика',CI:'Кот-д’Ивуар',HR:'Хорватия',CU:'Куба',CY:'Кипр',CZ:'Чехия',CD:'ДР Конго',DK:'Дания',DJ:'Джибути',DM:'Доминика',DO:'Доминикана',EC:'Эквадор',EG:'Египет',SV:'Сальвадор',GQ:'Экв. Гвинея',ER:'Эритрея',EE:'Эстония',SZ:'Эсватини',ET:'Эфиопия',FJ:'Фиджи',FI:'Финляндия',FR:'Франция',GA:'Габон',GM:'Гамбия',GE:'Грузия',DE:'Германия',GH:'Гана',GI:'Гибралтар',GR:'Греция',GL:'Гренландия',GT:'Гватемала',GN:'Гвинея',GY:'Гайана',HT:'Гаити',HN:'Гондурас',HK:'Гонконг',HU:'Венгрия',IS:'Исландия',IN:'Индия',ID:'Индонезия',IR:'Иран',IQ:'Ирак',IE:'Ирландия',IL:'Израиль',IT:'Италия',JM:'Ямайка',JP:'Япония',JO:'Иордания',KZ:'Казахстан',KE:'Кения',KI:'Кирибати',KW:'Кувейт',KG:'Киргизия',LA:'Лаос',LV:'Латвия',LB:'Ливан',LS:'Лесото',LR:'Либерия',LY:'Либия',LI:'Лихтенштейн',LT:'Литва',LU:'Люксембург',MO:'Макао',MG:'Мадагаскар',MW:'Малави',MY:'Малайзия',MV:'Мальдивы',ML:'Мали',MT:'Мальта',MH:'Маршалловы О-ва',MR:'Мавритания',MU:'Маврикий',MX:'Мексика',FM:'Микронезия',MD:'Молдова',MC:'Монако',MN:'Монголия',ME:'Черногория',MA:'Марокко',MZ:'Мозамбик',MM:'Мьянма',NA:'Намибия',NR:'Науру',NP:'Непал',NL:'Нидерланды',NZ:'Новая Зеландия',NI:'Никарагуа',NE:'Нигер',NG:'Нигерия',NU:'Ниуэ',KP:'КНДР',MK:'Сев. Македония',NO:'Норвегия',OM:'Оман',PK:'Пакистан',PS:'Палестина',PA:'Панама',PG:'Папуа — Новая Гвинея',PY:'Парагвай',PE:'Перу',PH:'Филиппины',PL:'Польша',PT:'Португалия',QA:'Катар',CG:'Конго',RO:'Румыния',RU:'Россия',RW:'Руанда',KN:'Сент-Китс и Невис',LC:'Сент-Люсия',VC:'Сент-Винсент',WS:'Самоа',SM:'Сан-Марино',ST:'Сан-Томе',SA:'Саудовская Арабия',SN:'Сенегал',RS:'Сербия',SC:'Сейшелы',SL:'Сьерра-Леоне',SG:'Сингапур',SK:'Словакия',SI:'Словения',SB:'Соломоновы О-ва',SO:'Сомали',ZA:'ЮАР',KR:'Южная Корея',SS:'Южный Судан',ES:'Испания',LK:'Шри-Ланка',SD:'Судан',SR:'Суринам',SE:'Швеция',CH:'Швейцария',SY:'Сирия',TW:'Тайвань',TJ:'Таджикистан',TZ:'Танзания',TH:'Таиланд',TL:'Вост. Тимор',TG:'Того',TO:'Тонга',TT:'Тринидад и Тобаго',TN:'Тунис',TR:'Турция',TM:'Туркмения',TV:'Тувалу',UG:'Уганда',UA:'Украина',AE:'ОАЭ',GB:'Великобритания',US:'США',UY:'Уругвай',UZ:'Узбекистан',VU:'Вануату',VA:'Ватикан',VE:'Венесуэла',VN:'Вьетнам',YE:'Йемен',ZM:'Замбия',ZW:'Зимбабве'};
function flagOf(c){return /^[A-Z]{2}$/.test(c)?String.fromCodePoint(...[...c].map(ch=>0x1F1E6+ch.charCodeAt(0)-65)):'🏳';}
function countryName(c){return /^[A-Z]{2}$/.test(c)?(COUNTRY_RU[c]||c):'Неизвестно';}
const toastEl=document.createElement('div');toastEl.id='toast';document.body.appendChild(toastEl);
let toastTimer=null;
function toast(msg){
  toastEl.textContent=String(msg);
  toastEl.style.display='block';
  clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>{toastEl.style.display='none';},7000);
  try{document.documentElement.setAttribute('data-err',String(msg).slice(0,400));}catch(e){}
}
window.onerror=(m,s,l,c)=>{toast('Ошибка JS: '+m+' (строка '+l+')');};
async function api(path,method,body){
  const opt={method:method||'GET'};
  if(body){opt.headers={'Content-Type':'application/json'};opt.body=JSON.stringify(body);}
  const r=await fetch(path,opt);
  let d=null; try{d=await r.json();}catch(e){}
  if(!r.ok)throw new Error((d&&d.error)||('HTTP '+r.status));
  if(d&&d.ok===false&&d.error)throw new Error(d.error);
  return d;
}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function showTab(t){
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x.dataset.t===t));
  document.querySelectorAll('main section').forEach(x=>x.classList.toggle('hidden',x.id!=='tab-'+t));
}

async function refresh(){
  try{
  state=await api('/api/state');
  document.getElementById('core-status').innerHTML=state.core.running
    ?'<span class="dot ok-dot"></span><span class="ok">движок работает</span>'
    :'<span class="dot err-dot"></span><span class="err">'+(state.core.error?('движок: '+esc(state.core.error.slice(0,40))):'движок: не запущен')+'</span>';
  document.getElementById('listener-note').textContent='Локальный прокси: '+((state.lan&&state.lan.enabled)?((state.lan_ip||'?')+':'+(state.lan_port||8889)+', с логином и паролем)'):'127.0.0.1:8888')+' · Интерфейс: '+state.admin+' · Режим неопознанного трафика: '+state.unmatched;
  document.querySelectorAll('#mode-seg button').forEach(b=>b.classList.toggle('on',b.dataset.m===state.unmatched));
  document.querySelectorAll('#sel-seg button').forEach(b=>b.classList.toggle('on',b.dataset.s===state.selection_mode));
  document.getElementById('sp-toggle').checked=!!state.system_proxy;
  document.getElementById('vpn-toggle').checked=!!state.vpn;
  renderLan();
  renderServers(); renderQC(); renderSubs(); renderRules();
  }catch(e){toast('refresh: '+e.message);}
}
function renderServers(){
  const csel=document.getElementById('country-filter');
  const counts={};
  state.servers.forEach(s=>{const c=String(s.country||'').toUpperCase()||'?';counts[c]=(counts[c]||0)+1;});
  const keys=Object.keys(counts).sort((a,b)=>counts[b]-counts[a]||a.localeCompare(b));
  if(csel){
    const cur=csel.dataset.v||'ALL';
    csel.innerHTML=['ALL'].concat(keys).map(c=>{
      const label=c==='ALL'?('Все страны ('+state.servers.length+')'):(flagOf(c)+' '+countryName(c)+' ('+counts[c]+')');
      return `<option value="${c}">${label}</option>`;
    }).join('');
    if(keys.includes(cur)||cur==='ALL'){csel.value=cur;}else{csel.value='ALL';csel.dataset.v='ALL';}
  }
  const flt=csel?csel.value:'ALL';
  const rows0=(flt==='ALL')?state.servers:state.servers.filter(s=>(String(s.country||'').toUpperCase()||'?')===flt);
  const tb=document.getElementById('srv-tbody'); tb.innerHTML='';
  const sorted=[...rows0].sort((a,b)=>{
    const rank=s=>s.latency_ok?0:(s.tested?2:1);
    if(a.latency!=null&&b.latency!=null)return a.latency-b.latency;
    if(a.latency!=null)return -1;
    if(b.latency!=null)return 1;
    if(rank(a)!==rank(b))return rank(a)-rank(b);
    return String(a.name||'').localeCompare(String(b.name||''));
  });
  const frag=document.createDocumentFragment();
  sorted.forEach(s=>{
    const tr=document.createElement('tr');
    if(s.id===state.active_server_id)tr.className='active';
    const lt=s.latency!=null?`<span class="${s.latency_ok?'ok':'err'}">${s.latency} мс</span>`:'<span class="muted">-</span>';
    const c=String(s.country||'').toUpperCase();
    const cc=(c&&/^[A-Z]{2}$/.test(c))?c:'';
    tr.innerHTML=`
      <td><input type="radio" ${s.id===state.active_server_id?'checked':''} onclick="selectServer('${s.id}')"></td>
      <td>${esc(s.name)}</td>
      <td style="white-space:nowrap" title="${cc}">${flagOf(cc)} ${esc(countryName(cc))}</td>
      <td><span class="tag">${s.type}</span></td>
      <td class="dlong" title="${esc(s.host+':'+s.port)}">${esc(s.host)}:${s.port}</td>
      <td>${lt}</td>
      <td class="muted">${esc((s.source||'manual').replace('sub:',''))}</td>
      <td style="white-space:nowrap">
        <button class="sm" onclick="testServer('${s.id}')">Тест</button>
        <button class="sm" onclick="openEdit('${s.id}')">Изменить</button>
        <button class="sm" onclick="toggleServer('${s.id}',${!s.enabled})">${s.enabled?'Откл':'Вкл'}</button>
        <button class="sm danger" onclick="delServer('${s.id}')">Удалить</button>
      </td>`;
    frag.appendChild(tr);
  });
  tb.appendChild(frag);
  const okN=state.servers.filter(x=>x.latency_ok).length;
  document.getElementById('pool-status').textContent='живых: '+okN+'/'+state.servers.length+(flt!=='ALL'?(' · показано: '+rows0.length):'');
  if(!rows0.length)tb.innerHTML='<tr><td colspan="8" class="muted">Нет серверов'+(flt!=='ALL'?' в стране '+flt:'')+'. Импортируйте подписку или добавьте вручную.</td></tr>';
}
function renderSubs(){
  const tb=document.getElementById('sub-tbody'); tb.innerHTML='';
  state.subs.forEach(s=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`
      <td>${esc(s.name||s.id.slice(0,6))}</td>
      <td class="dlong" title="${esc(s.url)}">${esc(s.url)}</td>
      <td><input type="number" style="width:64px" value="${s.interval_h}" onchange="subSet('${s.id}',{interval_h:+this.value})"></td>
      <td class="muted">${esc(s.last_update||'-')}</td>
      <td>${s.last_count??'-'}</td>
      <td><input type="checkbox" ${s.auto?'checked':''} onchange="subSet('${s.id}',{auto:this.checked})"></td>
      <td style="white-space:nowrap">
        <button class="sm" onclick="subUpdate('${s.id}')">Обновить</button>
        <button class="sm danger" onclick="subDelete('${s.id}')">Удалить</button>
      </td>`;
    tb.appendChild(tr);
  });
  if(!state.subs.length)tb.innerHTML='<tr><td colspan="7" class="muted">Подписок нет.</td></tr>';
}
function renderRules(){
  const tb=document.getElementById('rule-tbody'); tb.innerHTML='';
  const srvOpts=state.servers.map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join('');
  state.rules.forEach((r,i)=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`
      <td>
        <select onchange="state.rules[${i}].action=this.value;renderRules()">
          ${['direct','proxy','block','server'].map(a=>`<option value="${a}" ${r.action===a?'selected':''}>${a}</option>`).join('')}
        </select>
        ${r.action==='server'?`<select onchange="state.rules[${i}].server_id=this.value">${srvOpts}</select>`:''}
      </td>
      <td><input value="${esc((r.domain_suffix||[]).join(', '))}" style="width:220px" oninput="state.rules[${i}].domain_suffix=this.value.split(/[,#\\s]+/).filter(Boolean)"></td>
      <td><input value="${esc((r.keyword||[]).join(', '))}" style="width:180px" oninput="state.rules[${i}].keyword=this.value.split(/[,#\\s]+/).filter(Boolean)"></td>
      <td><input value="${esc((r.ip_cidr||[]).join(', '))}" style="width:180px" oninput="state.rules[${i}].ip_cidr=this.value.split(/[,#\\s]+/).filter(Boolean)"></td>
      <td><input type="checkbox" ${r.ip_is_private?'checked':''} onchange="state.rules[${i}].ip_is_private=this.checked"></td>
      <td style="white-space:nowrap"><button class="sm" onclick="moveRule(${i},-1)">↑</button><button class="sm" onclick="moveRule(${i},1)">↓</button><button class="sm danger" onclick="state.rules.splice(${i},1);renderRules()">Удалить</button></td>`;
    tb.appendChild(tr);
  });
}
function moveRule(i,d){const j=i+d;if(j<0||j>=state.rules.length)return;const r=state.rules.splice(i,1)[0];state.rules.splice(j,0,r);renderRules();}
function addRuleRow(){state.rules.push({action:'direct',server_id:null,domain_suffix:[],keyword:[],ip_cidr:[],ip_is_private:false});renderRules();}
async function saveRules(){try{await api('/api/rules/save','POST',{rules:state.rules});refresh();}catch(e){toast(e.message);}}
async function setMode(m){try{await api('/api/mode','POST',{unmatched:m});refresh();}catch(e){toast(e.message);}}
async function setSelMode(m){try{await api('/api/mode','POST',{selection_mode:m});refresh();}catch(e){toast(e.message);}}
async function setSystemProxy(v){try{await api('/api/system-proxy','POST',{enabled:v});refresh();}catch(e){document.getElementById('sp-toggle').checked=!v;toast(e.message);}}
async function setVpn(v){try{const r=await api('/api/vpn','POST',{enabled:v});if(r.relaunching){toast(r.message||'Перезапуск...');return;}refresh();}catch(e){document.getElementById('vpn-toggle').checked=!v;toast(e.message);}}
function renderLan(){
  const l=state.lan||{};
  document.getElementById('lan-toggle').checked=!!l.enabled;
  const tag=document.getElementById('lan-state');
  tag.textContent=l.enabled?'включён':'выключен';
  tag.className='tag'+(l.enabled?' ok':'');
  document.getElementById('lan-box').classList.toggle('hidden',!l.enabled);
  document.getElementById('lan-addr').textContent=l.enabled?((state.lan_ip||'—')+':'+(state.lan_port||8889)):'—';
  const u=document.getElementById('lan-user'),p=document.getElementById('lan-pass');
  if(document.activeElement!==u&&u.value!==(l.username||''))u.value=l.username||'';
  if(document.activeElement!==p&&p.value!==(l.password||''))p.value=l.password||'';
}
function lanForm(){return {username:document.getElementById('lan-user').value.trim(),password:document.getElementById('lan-pass').value};}
async function setLan(v){
  try{
    const r=await api('/api/lan','POST',Object.assign({enabled:v},lanForm()));
    if(r.warning){toast(r.warning);}
    else if(v&&r.lan){toast('Доступ из сети: '+r.address+' · логин '+r.lan.username+' (пароль задан)');}
    refresh();
  }catch(e){document.getElementById('lan-toggle').checked=!v;toast(e.message);}
}
async function saveLanCreds(){
  try{
    const r=await api('/api/lan','POST',Object.assign({enabled:true},lanForm()));
    if(r.warning){toast(r.warning);}else{toast('Сохранено: '+r.address);}
    refresh();
  }catch(e){toast(e.message);}
}
function toggleLanPass(btn){
  const p=document.getElementById('lan-pass');
  const show=p.type==='password';
  p.type=show?'text':'password';
  btn.textContent=show?'Скрыть':'Показать';
}
function genLanPass(){
  const a='abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';let s='';for(let i=0;i<12;i++)s+=a[Math.floor(Math.random()*a.length)];
  document.getElementById('lan-pass').value=s;
}
let npTimer=null;
async function startParse(mode){
  try{
    const deep=document.getElementById('np-deep').checked;
    const r=await api('/api/parse/start','POST',{mode:mode,deep:deep});
    if(!r.ok){toast(r.error||'Не удалось запустить сбор');return;}
    toast(mode==='internet'?'Сбор из интернета запущен':'Сбор из списков запущен');
    npPoll();
  }catch(e){toast(e.message);}
}
async function npPoll(){
  try{
    const s=await api('/api/parse/status');
    const ph=document.getElementById('np-phase');
    ph.textContent=s.phase||(s.running?'работает':'ожидание');
    ph.className='tag'+(s.running?' ok':'');
    document.getElementById('np-status').textContent='Найдено: '+(s.found||0)+' · живы по TCP: '+(s.alive||0)+' · рабочие: '+(s.working||0)+' · добавлено: '+(s.added||0)+(s.message?' · '+s.message:'');
    const log=document.getElementById('np-log');
    const lines=(s.log||[]).slice(-8);
    log.innerHTML=lines.map(esc).join('<br>');
    log.classList.toggle('hidden',lines.length===0);
    clearTimeout(npTimer);
    if(s.running){npTimer=setTimeout(npPoll,2000);}else{refresh();}
  }catch(e){clearTimeout(npTimer);npTimer=setTimeout(npPoll,5000);}
}
npPoll();
async function reloadCore(){try{await api('/api/reload','POST',{});refresh();}catch(e){toast(e.message);}}
async function appExit(){
  if(!confirm('Полностью выключить приложение? Прокси и панель остановятся.'))return;
  try{
    await api('/api/app/exit','POST',{});
    toast('Выключаюсь: движок и прокси останавливаются...');
    document.getElementById('power-btn').classList.remove('on');
    document.getElementById('qc-state').textContent='НЕ ЗАЩИЩЕНЫ';
    document.getElementById('qc-state').className='qc-state off';
    document.getElementById('hdr-conn').classList.add('hidden');
    setTimeout(()=>{window.close();},2500);
  }catch(e){toast(e.message);}
}
async function selectServer(id){try{await api('/api/server/select','POST',{id});refresh();}catch(e){toast(e.message);}}
let qcCountry=null;
function fmtDur(sec){sec=Math.max(0,Math.floor(sec));const h=Math.floor(sec/3600),m=Math.floor(sec%3600/60),ss=sec%60;return h?(h+' ч '+String(m).padStart(2,'0')+' мин'):(m?(m+' мин '+String(ss).padStart(2,'0')+' с'):(ss+' с'));}
function updateTimer(){
  const el=document.getElementById('qc-timer'); if(!el)return;
  if(state&&state.connected_since&&state.system_proxy){
    el.textContent='· '+fmtDur(Date.now()/1000-state.connected_since);
  }else{el.textContent='';}
}
function renderQC(){
  const grid=document.getElementById('qc-grid'); if(!grid)return;
  const m={};
  state.servers.forEach(s=>{
    if(!s.latency_ok||!s.enabled)return;
    const c=String(s.country||'').toUpperCase();
    if(!/^[A-Z]{2}$/.test(c))return;
    if(!m[c])m[c]={best:null,cnt:0};
    m[c].cnt++;
    if(s.latency!=null&&(m[c].best==null||s.latency<m[c].best))m[c].best=s.latency;
  });
  const keys=Object.keys(m).sort((a,b)=>(m[a].best??99999)-(m[b].best??99999));
  if(qcCountry&&!m[qcCountry])qcCountry=null;
  grid.innerHTML=keys.map(c=>`<div class="qc-chip${c===qcCountry?' sel':''}" onclick="qcPick('${c}')"><span>${flagOf(c)}</span><span>${esc(countryName(c))}</span><span class="d">${m[c].best!=null?m[c].best+' мс':'—'}</span><span class="c">×${m[c].cnt}</span></div>`).join('')||'<span class="muted">Нет живых серверов — обновите подписки или нажмите «Проверить все».</span>';
  const act=state.servers.find(s=>s.id===state.active_server_id);
  const connected=!!(state.system_proxy&&act&&act.latency_ok);
  const ac=act?String(act.country||'').toUpperCase():'';
  const stEl=document.getElementById('qc-state');
  stEl.textContent=connected?'ЗАЩИЩЕНЫ':'НЕ ЗАЩИЩЕНЫ';
  stEl.className='qc-state '+(connected?'on':'off');
  const pb=document.getElementById('power-btn');
  pb.className='power'+(connected?' on':'')+(pb.classList.contains('busy')?' busy':'');
  pb.title=connected?'Отключиться':'Подключиться к самому быстрому серверу';
  const info=document.getElementById('qc-info');
  if(connected){
    info.innerHTML=flagOf(ac)+' <b>'+esc(countryName(ac))+'</b> · '+esc(act.name)+' · <span class="ok">'+(act.latency??'?')+' мс</span>';
  }else if(act&&act.latency_ok){
    info.innerHTML='Выбран '+flagOf(ac)+' '+esc(countryName(ac))+' · <span class="warn">системный прокси выключен — нажмите кнопку</span>';
  }else if(act){
    info.innerHTML='<span class="err">активный сервер не отвечает — выберите другой</span>';
  }else{
    info.textContent='Нажмите кнопку — подключусь к самому быстрому серверу';
  }
  const hc=document.getElementById('hdr-conn');
  if(connected){
    hc.classList.remove('hidden');
    document.getElementById('hdr-conn-txt').textContent=flagOf(ac)+' '+countryName(ac)+' · '+(act.latency??'?')+' мс';
  }else{hc.classList.add('hidden');}
  updateTimer();
}
function qcPick(c){
  const was=qcCountry;
  qcCountry=(was===c)?null:c;
  renderQC();
  // уже подключён + выбрана ДРУГАЯ страна → мгновенное переключение
  if(qcCountry&&qcCountry!==was&&state&&state.system_proxy){
    toast('Переключаюсь на '+flagOf(qcCountry)+' '+countryName(qcCountry)+'...');
    qcConnect();
  }
}
async function qcConnect(){
  const country=qcCountry||'AUTO';
  const btn=document.getElementById('qc-btn');
  const pb=document.getElementById('power-btn');
  btn.disabled=true;btn.textContent='Подключаюсь (~5с)...';
  pb.classList.add('busy');
  try{
    const r=await api('/api/connect','POST',{country});
    const s=r.server||{};
    const c=String(s.country||'').toUpperCase()||'';
    toast('Подключено: '+flagOf(c)+' '+(r.auto?('самый быстрый · '+countryName(c)):countryName(c))+' — '+s.name+' ('+s.latency+' мс)'+(r.sysproxy?'':' · системный прокси не включился: '+(r.sysproxy_error||'')));
    refresh();
  }catch(e){toast(e.message);}
  btn.disabled=false;btn.textContent='Подключиться';
  pb.classList.remove('busy');
}
async function qcToggle(){
  if(state&&state.system_proxy)return qcDisconnect();
  return qcConnect();
}
async function qcDisconnect(){try{await api('/api/disconnect','POST',{});toast('Отключено: системный прокси выключен');refresh();}catch(e){toast(e.message);}}
setInterval(updateTimer,1000);
async function toggleServer(id,enabled){try{await api('/api/server/toggle','POST',{id,enabled});refresh();}catch(e){toast(e.message);}}
async function delServer(id){if(!confirm('Удалить сервер?'))return;try{await api('/api/server/delete','POST',{id});refresh();}catch(e){toast(e.message);}}
async function testServer(id){try{await api('/api/server/test','POST',{id});refresh();}catch(e){toast(e.message);}}
async function testAll(){try{const r=await api('/api/server/testall','POST',{});toast('Массовый тест запущен: '+(r.total||'?')+' серверов. Смотрите прогресс в списке.');}catch(e){toast(e.message);}}
async function purgeDead(){try{const r=await api('/api/server/purge','POST',{});toast('Удалено нерабочих: '+(r.removed??0));refresh();}catch(e){toast(e.message);}}
async function geoRefresh(){try{await api('/api/geo/refresh','POST',{});toast('Определяю страны...');}catch(e){toast(e.message);}}
async function addWarp(){try{toast('Регистрирую WARP (может занять ~30с)...');const r=await api('/api/warp/add','POST',{});const res=r.result||{};if(r.error){toast('WARP: '+r.error);}else if(res.ok){toast('WARP работает: '+res.latency_ms+' мс');}else{toast('WARP зарегистрирован, но недоступен: '+(res.error||''));}refresh();}catch(e){toast(e.message);}}
async function addServersText(){
  const text=document.getElementById('srv-text').value.trim();
  if(!text)return;
  try{const r=await api('/api/server/add','POST',{text});document.getElementById('srv-text').value='';toast('Добавлено серверов: '+r.added+(r.errors?(' Ошибки: '+r.errors.join('; ').slice(0,300)):''));refresh();}catch(e){toast(e.message);}
}
async function addServerManual(){
  const body={server:{type:document.getElementById('n-type').value,host:document.getElementById('n-host').value.trim(),port:+document.getElementById('n-port').value,name:document.getElementById('n-name').value.trim()}};
  try{const r=await api('/api/server/add','POST',body);if(!r.added)toast('Не удалось добавить');refresh();}catch(e){toast(e.message);}
}
function openEdit(id){
  editId=id;const s=state.servers.find(x=>x.id===id);if(!s)return;
  const map={name:s.name,host:s.host,port:s.port,type:s.type,user:s.username,pass:s.password,uuid:s.uuid,method:s.method,flow:s.flow,sec:s.security,sni:s.sni,fp:s.fp,pbk:s.pbk,sid:s.sid,transport:s.transport,path:s.path,hosthdr:s.host_header};
  for(const[k,v]of Object.entries(map))document.getElementById('e-'+k).value=v;
  document.getElementById('modal-bg').style.display='flex';
}
function closeModal(){document.getElementById('modal-bg').style.display='none';}
document.getElementById('modal-bg').addEventListener('click',e=>{if(e.target.id==='modal-bg')closeModal();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});
async function saveServerEdit(){
  const body={id:editId,server:{
    name:document.getElementById('e-name').value,host:document.getElementById('e-host').value,port:+document.getElementById('e-port').value,
    type:document.getElementById('e-type').value,username:document.getElementById('e-user').value,password:document.getElementById('e-pass').value,
    uuid:document.getElementById('e-uuid').value,method:document.getElementById('e-method').value,flow:document.getElementById('e-flow').value,
    security:document.getElementById('e-sec').value,sni:document.getElementById('e-sni').value,fp:document.getElementById('e-fp').value,
    pbk:document.getElementById('e-pbk').value,sid:document.getElementById('e-sid').value,transport:document.getElementById('e-transport').value,
    path:document.getElementById('e-path').value,host_header:document.getElementById('e-hosthdr').value}};
  try{await api('/api/server/update','POST',body);closeModal();refresh();}catch(e){toast(e.message);}
}
async function addSub(){
  const url=document.getElementById('su-url').value.trim(),name=document.getElementById('su-name').value.trim(),interval_h=+document.getElementById('su-interval').value||24;
  if(!url)return;
  try{const r=await api('/api/subs/add','POST',{url,name,interval_h});document.getElementById('su-url').value='';document.getElementById('su-name').value='';toast(r.started?'Подписка добавлена. Серверы тестируются (медленные отсеиваются)...':'Подписка добавлена');refresh();}catch(e){toast(e.message);}
}
async function subUpdate(id){try{const r=await api('/api/subs/update','POST',{id});toast(r.started?'Обновляю и тестирую серверы подписки...':'Готово');refresh();}catch(e){toast(e.message);}}
async function subSet(id,fields){try{await api('/api/subs/set','POST',{id,fields});refresh();}catch(e){toast(e.message);}}
async function subDelete(id){if(!confirm('Удалить подписку?'))return;try{await api('/api/subs/delete','POST',{id});refresh();}catch(e){toast(e.message);}}

async function refreshMonitor(){
  try{
    const conns=await api('/api/connect');
    const tb=document.getElementById('conn-tbody'),tl=document.getElementById('conn-total');
    tb.innerHTML=conns.connections.map(c=>`<tr><td class="dlong">${esc(c.target)}</td><td>${c.age}</td><td>${esc(c.type||'')}</td></tr>`).join('')||'<tr><td colspan="3" class="muted">нет активных</td></tr>';
    const fmt=n=>{n=+n||0;if(n<1024)return n+' B';if(n<1048576)return (n/1024).toFixed(1)+' KB';if(n<1073741824)return (n/1048576).toFixed(1)+' MB';return (n/1073741824).toFixed(2)+' GB';};
    let h='Всего подключений за сессию: '+conns.total+' · Скачано: '+fmt(conns.download)+' · Отдано: '+fmt(conns.upload);
    if(conns.group_now)h+=' · Текущий сервер: '+esc(conns.group_now)+' · ВЫбор: '+conns.selection_mode;
    tl.innerHTML=h;
    const l=await api('/api/log');
    const el=document.getElementById('logs');
    el.innerHTML=l.lines.map(x=>`<div>${esc(x)}</div>`).join('')||'<div>--</div>';
    el.scrollTop=el.scrollHeight;
  }catch(e){}
}
let updInfo=null;
async function updLoop(){
  try{
    const r=await api('/api/update/status');
    updInfo=r;
    const vt=document.getElementById('app-version');
    if(vt&&r.current)vt.textContent='v'+r.current;
    const b=document.getElementById('upd-banner');
    if(r.available&&r.latest){
      document.getElementById('upd-ver').textContent='v'+r.latest.version;
      document.getElementById('upd-cur').textContent='(у вас v'+r.current+')';
      b.classList.remove('hidden');
    }else{b.classList.add('hidden');}
  }catch(e){}
}
async function updApply(){
  const btn=document.getElementById('upd-apply-btn');
  btn.disabled=true;btn.textContent='Скачиваю...';
  try{
    const r=await api('/api/update/apply','POST',{});
    toast(r.message||'Обновление скачивается — приложение перезапустится');
    setTimeout(()=>location.reload(),10000);
    setTimeout(()=>location.reload(),25000);
  }catch(e){toast(e.message);btn.disabled=false;btn.textContent='Обновить и перезапустить';}
}
function updDetails(){
  if(!updInfo||!updInfo.latest){toast('Нет данных об обновлении');return;}
  const n=(updInfo.latest.notes||'').trim().replace(/\\r/g,'');
  toast('Версия v'+updInfo.latest.version+' доступна на GitHub.'+(n?('\\n'+n.slice(0,600)):''));
}
updLoop();
setTimeout(()=>{api('/api/update/check','POST',{}).then(()=>updLoop()).catch(()=>{});},1500);
setInterval(updLoop,300000);
setInterval(()=>{if(state)refresh();},3000);
setInterval(()=>{if(state&&!document.getElementById('tab-monitor').classList.contains('hidden'))refreshMonitor();},2500);
refresh().then(()=>refreshMonitor()).catch(toast);
</script>
</body>
</html>
"""