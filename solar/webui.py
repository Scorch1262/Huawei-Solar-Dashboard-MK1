"""Weboberfläche (eine Seite, eingebettet). Design wie die übrigen Dashboards:
dunkel, Raster-Hintergrund, Amber/Teal-Akzente, Mono-Schrift für Werte."""

PAGE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0b0e11">
<title>__TITLE__</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect x='6' y='6' width='20' height='20' transform='rotate(45 16 16)' fill='none' stroke='%23f5a524' stroke-width='3'/%3E%3Crect x='12' y='12' width='8' height='8' transform='rotate(45 16 16)' fill='%23f5a524'/%3E%3C/svg%3E">
<style>
:root{
  --bg:#0b0e11;--bg2:#11161b;--panel:#151b21;--panel2:#1b232b;--line:#26313b;--line2:#33414d;
  --txt:#d9e1e8;--dim:#8796a3;--mute:#5d6b77;
  --amber:#f5a524;--amber2:#ffc463;--teal:#2dd4bf;--teal2:#5eead4;
  --red:#f26d6d;--green:#4ade80;--blue:#60a5fa;--violet:#a78bfa;
  --mono:ui-monospace,"SF Mono","Cascadia Mono",Consolas,"Roboto Mono",monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--txt);font-family:var(--sans);font-size:14px}
body{background-image:linear-gradient(rgba(45,212,191,.025) 1px,transparent 1px),
  linear-gradient(90deg,rgba(45,212,191,.025) 1px,transparent 1px);background-size:32px 32px;min-height:100vh}
a{color:var(--teal);text-decoration:none}
button,input,select{font:inherit;color:var(--txt)}
.top{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:14px;padding:12px 20px;
  padding-top:max(12px,env(safe-area-inset-top));
  background:rgba(11,14,17,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line);flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:12px;min-width:0}
.logo{width:28px;height:28px;border:1.5px solid var(--amber);display:grid;place-items:center;transform:rotate(45deg);flex:none}
.logo i{width:9px;height:9px;background:var(--amber);display:block}
.brand h1{margin:0;font-size:14px;letter-spacing:.18em;text-transform:uppercase;font-weight:600}
.brand .sub{font-family:var(--mono);font-size:11px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ver{font-family:var(--mono);font-size:10px;color:var(--amber);border:1px solid rgba(245,165,36,.4);padding:2px 6px;letter-spacing:.08em}
.spacer{flex:1}
.chips{display:flex;gap:8px;flex-wrap:wrap}
.chip{display:flex;align-items:center;gap:7px;font-family:var(--mono);font-size:11px;color:var(--dim);
  border:1px solid var(--line);background:var(--bg2);padding:5px 9px;text-transform:uppercase;letter-spacing:.08em}
.dot{width:7px;height:7px;border-radius:50%;background:var(--mute)}
.dot.ok{background:var(--green);box-shadow:0 0 8px rgba(74,222,128,.6)}
.dot.err{background:var(--red);box-shadow:0 0 8px rgba(242,109,109,.6)}
.dot.off{background:var(--mute)}
.tabs{display:flex;gap:2px}
.tab{background:transparent;border:1px solid transparent;border-bottom:2px solid transparent;color:var(--dim);
  padding:7px 12px;cursor:pointer;font-size:12px;letter-spacing:.12em;text-transform:uppercase}
.tab:hover{color:var(--txt)}
.tab.on{color:var(--amber);border-bottom-color:var(--amber)}
main{padding:18px 20px 40px;max-width:1500px;margin:0 auto}
.view{display:none}.view.on{display:block}
.grid{display:grid;gap:14px}
.kpis{grid-template-columns:repeat(auto-fill,minmax(170px,1fr))}
.panel{background:var(--panel);border:1px solid var(--line);position:relative}
.panel::before{content:"";position:absolute;left:-1px;top:-1px;width:10px;height:10px;border-left:2px solid var(--amber);border-top:2px solid var(--amber)}
.ph{display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--line);
  font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--dim)}
.ph b{color:var(--txt);font-weight:600}
.ph .r{margin-left:auto;font-family:var(--mono);letter-spacing:.04em;text-transform:none}
.pb{padding:14px}
.kpi{padding:12px 14px}
.kpi .l{font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--dim);display:flex;align-items:center;gap:7px}
.kpi .l i{width:8px;height:8px;display:inline-block}
.kpi .v{font-family:var(--mono);font-size:26px;margin-top:6px;white-space:nowrap}
.kpi .v small{font-size:13px;color:var(--dim);margin-left:4px}
.kpi .s{font-family:var(--mono);font-size:11px;color:var(--dim);margin-top:4px;min-height:14px}
.main2{grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);margin-top:14px}
.cols3{grid-template-columns:repeat(auto-fit,minmax(300px,1fr));margin-top:14px}
@media (max-width:900px){.main2{grid-template-columns:1fr}}
.flow svg{width:100%;height:auto;display:block;max-height:360px}
.node circle{fill:var(--bg2);stroke:var(--line2);stroke-width:1.5}
.node.act circle{stroke-width:2}
.node text{font-family:var(--mono);fill:var(--txt);text-anchor:middle}
.node .nl{font-size:9px;fill:var(--dim);letter-spacing:.14em}
.node .nv{font-size:13px}
.ln{stroke:var(--line2);stroke-width:2;fill:none}
.fl{stroke-width:2.5;fill:none;stroke-dasharray:5 9;animation:dash 1.1s linear infinite;opacity:0}
.fl.on{opacity:1}.fl.rev{animation-direction:reverse}
@keyframes dash{to{stroke-dashoffset:-28}}
.soc{display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.ring{position:relative;width:150px;height:150px;flex:none}
.ring svg{width:150px;height:150px;transform:rotate(-90deg)}
.ring .c{position:absolute;inset:0;display:grid;place-items:center;text-align:center}
.ring .c b{font-family:var(--mono);font-size:30px;font-weight:500}
.ring .c span{display:block;font-size:10px;color:var(--dim);letter-spacing:.16em;text-transform:uppercase}
.kv{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;font-size:12.5px;align-items:baseline}
.kv dt{color:var(--dim)}
.kv dd{margin:0;font-family:var(--mono);text-align:right;white-space:nowrap}
.tbl{width:100%;border-collapse:collapse;font-size:12.5px}
.tbl th{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--mute);font-weight:500;text-align:right;padding:6px 8px;border-bottom:1px solid var(--line)}
.tbl th:first-child,.tbl td:first-child{text-align:left}
.tbl td{padding:7px 8px;border-bottom:1px solid rgba(38,49,59,.6);font-family:var(--mono);text-align:right;white-space:nowrap}
.tbl td.t{font-family:var(--sans);color:var(--dim);text-align:left}
.bar{height:4px;background:var(--bg2);margin-top:4px;position:relative;overflow:hidden}
.bar i{position:absolute;left:0;top:0;bottom:0;background:var(--amber)}
.badge{font-family:var(--mono);font-size:11px;padding:2px 7px;border:1px solid var(--line2);color:var(--dim)}
.badge.ok{color:var(--green);border-color:rgba(74,222,128,.35)}
.badge.warn{color:var(--amber);border-color:rgba(245,165,36,.4)}
.badge.err{color:var(--red);border-color:rgba(242,109,109,.4)}
.chartwrap{position:relative;height:300px}
canvas{display:block;width:100%;height:100%}
.rng{display:flex;gap:4px;margin-left:auto}
.rng button,.btn{background:var(--bg2);border:1px solid var(--line2);color:var(--dim);padding:5px 10px;cursor:pointer;
  font-family:var(--mono);font-size:11px;letter-spacing:.06em}
.rng button.on{color:var(--amber);border-color:var(--amber)}
.btn:hover,.rng button:hover{color:var(--txt);border-color:var(--dim)}
.btn.pri{color:#111;background:var(--amber);border-color:var(--amber);font-weight:600}
.btn.pri:hover{background:var(--amber2)}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-family:var(--mono);font-size:11px;color:var(--dim);padding:0 14px 10px}
.legend i{display:inline-block;width:12px;height:3px;margin-right:6px;vertical-align:middle}
.tip{position:absolute;pointer-events:none;background:rgba(11,14,17,.95);border:1px solid var(--line2);padding:8px 10px;
  font-family:var(--mono);font-size:11px;display:none;white-space:nowrap;z-index:5}
.form{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px 16px}
.f label{display:block;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);margin-bottom:5px}
.f input[type=text],.f input[type=number],.f input[type=password]{width:100%;background:var(--bg2);border:1px solid var(--line2);
  padding:8px 10px;font-family:var(--mono);font-size:13px;outline:none}
.f input:focus{border-color:var(--teal)}
.f .h{font-size:11px;color:var(--mute);margin-top:4px}
.chk{display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;margin-top:22px}
.chk input{accent-color:var(--amber);width:16px;height:16px}
.acts{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:16px}
.msg{font-family:var(--mono);font-size:12px;color:var(--dim)}
.msg.ok{color:var(--green)}.msg.err{color:var(--red)}
.log{font-family:var(--mono);font-size:11.5px;color:var(--dim);max-height:260px;overflow:auto;white-space:pre-wrap;line-height:1.55}
.search{background:var(--bg2);border:1px solid var(--line2);padding:6px 10px;font-family:var(--mono);font-size:12px;width:220px;outline:none}
.topic{color:var(--teal);font-size:11.5px}
.empty{color:var(--mute);font-family:var(--mono);font-size:12px;padding:6px 0}
.banner{border:1px solid rgba(242,109,109,.4);background:rgba(242,109,109,.07);color:var(--red);padding:10px 14px;
  font-family:var(--mono);font-size:12px;margin-bottom:14px;display:none}
.ctl{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}
.row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 12px;align-items:center;padding:10px 0;border-bottom:1px solid rgba(38,49,59,.6)}
.row:last-child{border-bottom:0}
.row .rl{font-size:12.5px}
.row .rl small{display:block;color:var(--mute);font-family:var(--mono);font-size:11px;margin-top:2px}
.row .rc{display:flex;gap:6px;align-items:center;justify-content:flex-end;flex-wrap:wrap}
.row input[type=number],.row select,.sel{background:var(--bg2);border:1px solid var(--line2);padding:6px 8px;font-family:var(--mono);font-size:12.5px;outline:none;color:var(--txt)}
.row input[type=number]{width:96px}
.row select{max-width:230px}
.cur{font-family:var(--mono);font-size:12px;color:var(--teal);min-width:64px;text-align:right}
.btn.warn{color:var(--red);border-color:rgba(242,109,109,.5)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.note{font-size:11.5px;color:var(--dim);line-height:1.5;margin-top:8px}
.note.w{color:var(--amber)}
.lock{border:1px dashed var(--line2);padding:18px;color:var(--dim);font-size:13px;line-height:1.6}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.6);display:none;place-items:center;z-index:50;padding:16px}
.modal.on{display:grid}
.dlg{background:var(--panel);border:1px solid var(--line2);width:min(440px,100%);position:relative}
.dlg::before{content:"";position:absolute;left:-1px;top:-1px;width:12px;height:12px;border-left:2px solid var(--amber);border-top:2px solid var(--amber)}
.dlg .pb p{margin:0 0 12px;font-size:13.5px;line-height:1.5}
.dlg .what{font-family:var(--mono);font-size:13px;color:var(--amber);border:1px solid var(--line);background:var(--bg2);padding:10px;margin-bottom:12px}
.dlg input{width:100%;background:var(--bg2);border:1px solid var(--line2);padding:8px 10px;font-family:var(--mono);outline:none;color:var(--txt)}
.res{font-family:var(--mono);font-size:11.5px;margin-top:10px;min-height:14px}
.res.ok{color:var(--green)}.res.err{color:var(--red)}
/* Smart-Laden */
.smgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px;margin-top:14px}
.sl{padding:9px 0 11px;border-bottom:1px solid rgba(38,49,59,.6)}
.sl:last-child{border-bottom:0}
.sl .lab{display:flex;justify-content:space-between;align-items:baseline;font-size:12.5px;margin-bottom:8px;gap:10px}
.sl .lab b{font-family:var(--mono);font-weight:500;color:var(--amber);white-space:nowrap}
.sl .lab small{display:block;color:var(--mute);font-size:11px;margin-top:2px}
input[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:22px;background:transparent;margin:0;cursor:pointer}
input[type=range]:focus{outline:none}
input[type=range]::-webkit-slider-runnable-track{height:4px;background:var(--line2)}
input[type=range]::-moz-range-track{height:4px;background:var(--line2)}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:16px;height:16px;margin-top:-6px;background:var(--amber);border:2px solid var(--bg);transform:rotate(45deg);box-shadow:0 0 0 1px var(--amber)}
input[type=range]::-moz-range-thumb{width:14px;height:14px;background:var(--amber);border:2px solid var(--bg);border-radius:0;transform:rotate(45deg)}
input[type=range]:disabled{opacity:.4;cursor:not-allowed}
.dual{position:relative;height:22px}
.dual input{position:absolute;left:0;top:0;pointer-events:none}
.dual input::-webkit-slider-thumb{pointer-events:auto}
.dual input::-moz-range-thumb{pointer-events:auto}
.dual::before{content:"";position:absolute;left:0;right:0;top:9px;height:4px;background:var(--line2)}
.dual input::-webkit-slider-runnable-track{background:transparent}
.dual input::-moz-range-track{background:transparent}
.dual .fill{position:absolute;top:9px;height:4px;background:var(--teal);pointer-events:none}
.seg{display:flex;border:1px solid var(--line2)}
.seg button{flex:1;background:var(--bg2);border:0;color:var(--dim);padding:7px 8px;cursor:pointer;font-family:var(--mono);font-size:11.5px}
.seg button.on{background:rgba(245,165,36,.14);color:var(--amber)}
.sw{display:flex;align-items:center;gap:12px;cursor:pointer;font-size:13.5px;user-select:none}
.sw input{display:none}
.sw i{width:42px;height:22px;background:var(--line2);position:relative;transition:.2s;flex:none}
.sw i::after{content:"";position:absolute;left:3px;top:3px;width:16px;height:16px;background:var(--dim);transition:.2s}
.sw input:checked+i{background:rgba(74,222,128,.25)}
.sw input:checked+i::after{left:23px;background:var(--green)}
.status{font-family:var(--mono);font-size:13px;line-height:1.5}
.geo{display:flex;gap:6px}
.geo input{flex:1;background:var(--bg2);border:1px solid var(--line2);padding:7px 9px;font-family:var(--mono);font-size:12.5px;outline:none;color:var(--txt)}
.geolist{display:flex;flex-direction:column;gap:4px;margin-top:6px}
.geolist button{text-align:left;background:var(--bg2);border:1px solid var(--line);color:var(--txt);padding:6px 9px;cursor:pointer;font-size:12px}
.geolist button:hover{border-color:var(--teal)}
.prev{font-family:var(--mono);font-size:11px;color:var(--amber);border:1px solid rgba(245,165,36,.4);padding:2px 7px;display:none}
.chart2{position:relative;height:230px}
@media (max-width:600px){
  .chart2{height:200px}
  .ctl{grid-template-columns:1fr}
  .row{grid-template-columns:1fr}.row .rc{justify-content:flex-start}
  .top{padding:10px 12px}.brand h1{font-size:12px;letter-spacing:.12em}
  main{padding:12px 10px 30px}
  .kpis{grid-template-columns:1fr 1fr;gap:10px}
  .kpi .v{font-size:21px}
  .tabs{width:100%;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}.tabs::-webkit-scrollbar{display:none}
  .tab{flex:none;padding:8px 10px;white-space:nowrap}
  .chartwrap{height:240px}
  .search{width:100%}
}
</style>
</head>
<body>
<header class="top">
  <div class="brand">
    <div class="logo"><i></i></div>
    <div style="min-width:0">
      <h1 id="title">__TITLE__</h1>
      <div class="sub" id="sub">Huawei SUN2000 · warte auf Daten …</div>
    </div>
    <span class="ver">v__VERSION__</span>
  </div>
  <div class="spacer"></div>
  <div class="chips">
    <div class="chip"><span class="dot" id="dWr"></span>Wechselrichter</div>
    <div class="chip"><span class="dot" id="dMq"></span>MQTT</div>
  </div>
  <nav class="tabs">
    <button class="tab on" data-v="ov">Übersicht</button>
    <button class="tab" data-v="smart">Smart-Laden</button>
    <button class="tab" data-v="ctl">Steuerung</button>
    <button class="tab" data-v="val">Werte</button>
    <button class="tab" data-v="set">Einstellungen</button>
  </nav>
</header>

<main>
<div class="banner" id="banner"></div>

<!-- ================= Übersicht ================= -->
<section class="view on" id="v-ov">
  <div class="grid kpis">
    <div class="panel kpi"><div class="l"><i style="background:var(--amber)"></i>PV-Leistung</div><div class="v" id="kPv">–</div><div class="s" id="kPvS"></div></div>
    <div class="panel kpi"><div class="l"><i style="background:var(--teal)"></i>Hausverbrauch</div><div class="v" id="kHaus">–</div><div class="s" id="kHausS"></div></div>
    <div class="panel kpi"><div class="l"><i style="background:var(--violet)"></i>Akku</div><div class="v" id="kAkku">–</div><div class="s" id="kAkkuS"></div></div>
    <div class="panel kpi"><div class="l"><i style="background:var(--blue)"></i>Netz</div><div class="v" id="kNetz">–</div><div class="s" id="kNetzS"></div></div>
    <div class="panel kpi"><div class="l"><i style="background:var(--green)"></i>Ausgangsleistung</div><div class="v" id="kWr">–</div><div class="s" id="kWrS"></div></div>
    <div class="panel kpi"><div class="l"><i style="background:var(--amber2)"></i>Ertrag heute</div><div class="v" id="kErt">–</div><div class="s" id="kErtS"></div></div>
    <div class="panel kpi" style="cursor:pointer" onclick="document.querySelector('.tab[data-v=smart]').click()"><div class="l"><i style="background:var(--teal2)"></i>Strompreis</div><div class="v" id="kPreis">–</div><div class="s" id="kPreisS"></div></div>
  </div>

  <div class="grid main2">
    <div class="panel flow">
      <div class="ph"><b>Energiefluss</b><span class="r" id="flowTs"></span></div>
      <div class="pb">
        <svg viewBox="0 0 420 310">
          <defs>
            <marker id="m" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="5" markerHeight="5"><circle cx="3" cy="3" r="2" fill="#33414d"/></marker>
          </defs>
          <path class="ln" d="M210 74 V128"/><path class="ln" d="M182 155 H92"/><path class="ln" d="M238 155 H328"/><path class="ln" d="M210 182 V236"/>
          <path id="fPv" class="fl" stroke="#f5a524" d="M210 74 V128"/>
          <path id="fNetz" class="fl" stroke="#60a5fa" d="M92 155 H182"/>
          <path id="fHaus" class="fl" stroke="#2dd4bf" d="M238 155 H328"/>
          <path id="fAkku" class="fl" stroke="#a78bfa" d="M210 182 V236"/>
          <g class="node" id="nPv"><circle cx="210" cy="44" r="30"/><text class="nl" x="210" y="38">PV</text><text class="nv" id="tPv" x="210" y="55">–</text></g>
          <g class="node" id="nNetz"><circle cx="62" cy="155" r="30"/><text class="nl" x="62" y="149">NETZ</text><text class="nv" id="tNetz" x="62" y="166">–</text></g>
          <g class="node" id="nHaus"><circle cx="358" cy="155" r="30"/><text class="nl" x="358" y="149">HAUS</text><text class="nv" id="tHaus" x="358" y="166">–</text></g>
          <g class="node" id="nAkku"><circle cx="210" cy="266" r="30"/><text class="nl" x="210" y="260">AKKU</text><text class="nv" id="tAkku" x="210" y="277">–</text></g>
          <g class="node"><rect x="183" y="128" width="54" height="54" transform="rotate(45 210 155)" fill="#11161b" stroke="#f5a524" stroke-width="1.5"/>
            <text class="nl" x="210" y="152" style="fill:#f5a524">WR</text><text class="nv" id="tWr" x="210" y="167" style="font-size:11px">–</text></g>
          <text id="lNetz" x="137" y="146" font-family="ui-monospace,monospace" font-size="9.5" fill="#8796a3" text-anchor="middle"></text>
          <text id="lAkku" x="222" y="213" font-family="ui-monospace,monospace" font-size="9.5" fill="#8796a3"></text>
        </svg>
      </div>
    </div>
    <div class="panel">
      <div class="ph"><b>Akku</b><span class="r" id="akkuBadge"></span></div>
      <div class="pb">
        <div class="soc">
          <div class="ring">
            <svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="52" fill="none" stroke="#1b232b" stroke-width="10"/>
              <circle id="socArc" cx="60" cy="60" r="52" fill="none" stroke="#a78bfa" stroke-width="10" stroke-dasharray="0 400"/></svg>
            <div class="c"><div><b id="socTxt">–</b><span>Ladezustand</span></div></div>
          </div>
          <dl class="kv" style="flex:1;min-width:200px" id="akkuKv"></dl>
        </div>
        <div class="empty" id="akkuNone" style="display:none">Kein Akku erkannt.</div>
      </div>
    </div>
  </div>

  <div class="panel" style="margin-top:14px">
    <div class="ph"><b>Verlauf</b>
      <div class="rng" id="rng"><button data-h="1">1 h</button><button data-h="6">6 h</button><button data-h="12">12 h</button><button data-h="24" class="on">24 h</button><button data-h="48">48 h</button></div>
    </div>
    <div class="legend">
      <span><i style="background:var(--amber)"></i>PV</span><span><i style="background:var(--teal)"></i>Haus</span>
      <span><i style="background:var(--violet)"></i>Akku (+ laden)</span><span><i style="background:var(--blue)"></i>Netz (+ Einspeisung)</span>
      <span><i style="background:var(--green)"></i>SOC %</span>
    </div>
    <div class="chartwrap" id="cw"><canvas id="chart"></canvas><div class="tip" id="tip"></div></div>
  </div>

  <div class="grid cols3">
    <div class="panel"><div class="ph"><b>PV-Strings</b><span class="r" id="pvSum"></span></div>
      <div class="pb"><table class="tbl" id="pvTbl"></table></div></div>
    <div class="panel"><div class="ph"><b>Wechselrichter</b><span class="r" id="wrBadge"></span></div>
      <div class="pb"><dl class="kv" id="wrKv"></dl><table class="tbl" id="wrPh" style="margin-top:12px"></table>
      <div class="ph" style="padding:12px 0 8px;border:0;margin-top:6px"><b>Verbindung</b></div><dl class="kv" id="conKv"></dl></div></div>
    <div class="panel"><div class="ph"><b>Netz / Zähler</b><span class="r" id="netzBadge"></span></div>
      <div class="pb"><dl class="kv" id="netzKv"></dl><table class="tbl" id="netzPh" style="margin-top:12px"></table>
      <div class="empty" id="netzNone" style="display:none">Kein Smart Meter erkannt – Netz- und Hausverbrauchswerte stehen nicht zur Verfügung.</div></div></div>
  </div>
</section>

<!-- ================= Smart-Laden ================= -->
<section class="view" id="v-smart">
  <div class="grid kpis">
    <div class="panel kpi"><div class="l"><i style="background:var(--teal2)"></i>Strompreis jetzt</div><div class="v" id="smPreis">–</div><div class="s" id="smPreisS"></div></div>
    <div class="panel kpi"><div class="l"><i style="background:var(--dim)"></i>Preis heute</div><div class="v" id="smTag">–</div><div class="s" id="smTagS"></div></div>
    <div class="panel kpi"><div class="l"><i style="background:var(--amber)"></i>PV-Prognose</div><div class="v" id="smPv">–</div><div class="s" id="smPvS"></div></div>
    <div class="panel kpi"><div class="l"><i style="background:var(--violet)"></i>Geplante Netzladung</div><div class="v" id="smPlan">–</div><div class="s" id="smPlanS"></div></div>
  </div>
  <div class="panel" style="margin-top:14px"><div class="ph"><b>Automatik</b><span class="r"><span class="prev" id="smPrev">Vorschau – noch nicht übernommen</span></span></div>
    <div class="pb" style="display:flex;gap:18px;align-items:center;flex-wrap:wrap">
      <label class="sw"><input type="checkbox" id="sm_aktiv"><i></i>Automatisch aus dem Netz laden</label>
      <label class="sw"><input type="checkbox" id="sm_probebetrieb"><i></i>Probebetrieb (nur rechnen, nichts schreiben)</label>
      <div class="status" id="smStatus" style="flex:1;min-width:220px">–</div>
      <button class="btn pri" id="smSave">Übernehmen</button><button class="btn" id="smReset">Verwerfen</button>
    </div>
    <div class="pb" id="smFault" style="display:none;padding-top:0"><div class="banner" style="display:block;margin:0 0 10px" id="smFaultTxt"></div>
      <button class="btn warn" id="smAck">Störung quittieren</button></div>
    <div class="pb" style="padding-top:0"><details><summary style="cursor:pointer;color:var(--dim);font-size:12px;letter-spacing:.1em;text-transform:uppercase">Sicherheitsprüfungen <span id="smChkSum"></span></summary>
      <div id="smChecks" style="margin-top:10px;font-family:var(--mono);font-size:12px;line-height:1.9"></div>
      <div class="note">Netzladung nur, wenn ALLE Prüfungen bestanden sind. Fällt eine weg, wird sofort gestoppt. Jeder Ladeauftrag läuft höchstens 30 min und endet dann im Wechselrichter von selbst.</div></details></div>
    <div class="pb" style="padding-top:0"><div class="res" id="smMsg" style="margin-top:0"></div><div class="note w" id="smLock" style="display:none;margin-top:0">Die Steuerung ist gesperrt – die Automatik kann erst schreiben, wenn sie unter <a href="#set">Einstellungen → Steuerung</a> freigegeben ist. Der Plan wird trotzdem berechnet.</div></div>
  </div>
  <div class="panel" style="margin-top:14px"><div class="ph"><b>Strompreis &amp; Ladeplan</b><span class="r" id="smSrc"></span></div>
    <div class="legend" style="padding-top:10px"><span><i style="background:var(--teal)"></i>im Preisbereich</span><span><i style="background:var(--violet)"></i>Netzladung geplant</span><span><i style="background:#b3742a"></i>im Bereich, aber PV erwartet</span><span><i style="background:var(--line2)"></i>außerhalb</span></div>
    <div class="chart2" id="cwP"><canvas id="chP"></canvas><div class="tip" id="tipP"></div></div>
    <div class="legend" style="padding-top:12px"><span><i style="background:var(--amber)"></i>PV-Prognose</span><span><i style="background:var(--teal)"></i>Verbrauch (erwartet)</span><span><i style="background:var(--violet)"></i>Netzladung</span><span><i style="background:var(--green)"></i>Akku-SOC mit Plan</span><span><i style="background:rgba(74,222,128,.35)"></i>ohne Netzladung</span></div>
    <div class="chart2" id="cwE"><canvas id="chE"></canvas><div class="tip" id="tipE"></div></div>
  </div>
  <div class="smgrid">
    <div class="panel"><div class="ph"><b>Netzladung</b></div><div class="pb" id="slA"></div></div>
    <div class="panel"><div class="ph"><b>PV-Prognose</b></div><div class="pb">
      <div class="sl"><div class="lab"><span>Quelle<small id="smQuelleInfo"></small></span></div>
        <div class="seg" id="sm_prognose"><button data-v="wetter">Wetterprognose</button><button data-v="statistik">Eigene Statistik</button></div></div>
      <div class="sl"><div class="lab"><span>Standort<small id="smOrt">nicht gesetzt</small></span></div>
        <div class="geo"><input id="smGeoQ" placeholder="Ort oder PLZ"><button class="btn" id="smGeoBtn">Suchen</button></div><div class="geolist" id="smGeoList"></div></div>
      <div id="slB"></div>
      <div class="sl"><label class="chk" style="margin-top:0"><input type="checkbox" id="sm_kalibrierung"> Prognose an die eigene Anlage anpassen<span class="cur" id="smKal" style="margin-left:auto"></span></label></div>
    </div></div>
    <div class="panel"><div class="ph"><b>Preis &amp; Verbrauch</b></div><div class="pb">
      <div class="sl"><div class="lab"><span>Gebotszone</span></div><select class="sel" id="sm_zone" style="width:100%"></select></div>
      <div id="slC"></div>
      <div class="note">Preisgrenzen beziehen sich auf den Endpreis = (Börsenpreis + Aufschlag) × (1 + MwSt). Mit Aufschlag und MwSt 0 gilt der reine Börsenpreis. Quelle: Energy-Charts (Fraunhofer ISE, CC BY 4.0), Ersatz aWATTar · Wetter: Open-Meteo.</div>
    </div></div>
  </div>
</section>

<!-- ================= Steuerung ================= -->
<section class="view" id="v-ctl">
  <div class="lock" id="ctlLock" style="display:none">Die Steuerung ist gesperrt.<br>
    Unter <a href="#set" onclick="document.querySelector('.tab[data-v=set]').click();return false">Einstellungen → Steuerung</a> kann sie freigegeben werden (optional mit PIN).</div>
  <div class="ctl" id="ctlBox">
    <div class="panel"><div class="ph"><b>Akku-Betriebsart</b><span class="r" id="ctModeCur"></span></div><div class="pb">
      <div class="row"><div class="rl">Arbeitsmodus</div>
        <div class="rc"><select id="ctMode"></select><button class="btn" data-act="modus" data-src="ctMode">Übernehmen</button></div></div>
      <div class="row"><div class="rl">PV-Überschuss im Zeitmodus<small>nur bei „Zeitgesteuert (LUNA2000)“</small></div>
        <div class="rc"><span class="cur" id="cur_pv_tou"></span><select id="ctPvTou"><option value="0">einspeisen</option><option value="1">Akku laden</option></select>
        <button class="btn" data-act="pv_tou" data-src="ctPvTou">Übernehmen</button></div></div>
      <div class="note">Zeitfenster für den Zeitmodus werden weiterhin in der FusionSolar-App eingestellt.</div>
      <div class="res" id="res_modus"></div>
    </div></div>

    <div class="panel"><div class="ph"><b>Lade- und Entladegrenzen</b></div><div class="pb">
      <div class="row"><div class="rl">Ladeschluss-SOC<small>90–100 %</small></div>
        <div class="rc"><span class="cur" id="cur_ladeschluss"></span><input type="number" id="in_ladeschluss" min="90" max="100" step="1"><button class="btn" data-act="ladeschluss" data-src="in_ladeschluss">Setzen</button></div></div>
      <div class="row"><div class="rl">Entladeschluss-SOC<small>0–20 %</small></div>
        <div class="rc"><span class="cur" id="cur_entladeschluss"></span><input type="number" id="in_entladeschluss" min="0" max="20" step="1"><button class="btn" data-act="entladeschluss" data-src="in_entladeschluss">Setzen</button></div></div>
      <div class="row"><div class="rl">Max. Ladeleistung<small id="lim_laden">W</small></div>
        <div class="rc"><span class="cur" id="cur_max_laden"></span><input type="number" id="in_max_laden" min="0" step="100"><button class="btn" data-act="max_laden" data-src="in_max_laden">Setzen</button></div></div>
      <div class="row"><div class="rl">Max. Entladeleistung<small id="lim_entladen">W</small></div>
        <div class="rc"><span class="cur" id="cur_max_entladen"></span><input type="number" id="in_max_entladen" min="0" step="100"><button class="btn" data-act="max_entladen" data-src="in_max_entladen">Setzen</button></div></div>
      <div class="res" id="res_grenzen"></div>
    </div></div>

    <div class="panel"><div class="ph"><b>Laden aus dem Netz</b><span class="r" id="ctNetzCur"></span></div><div class="pb">
      <div class="row"><div class="rl">Netzladen<small>Akku darf aus dem Netz laden</small></div>
        <div class="rc"><button class="btn" data-act="netzladen" data-val="1">Einschalten</button><button class="btn" data-act="netzladen" data-val="0">Ausschalten</button></div></div>
      <div class="row"><div class="rl">Netzladen bis SOC<small>20–100 %</small></div>
        <div class="rc"><span class="cur" id="cur_netzladen_soc"></span><input type="number" id="in_netzladen_soc" min="20" max="100" step="1"><button class="btn" data-act="netzladen_soc" data-src="in_netzladen_soc">Setzen</button></div></div>
      <div class="row"><div class="rl">Max. Netzladeleistung<small>W</small></div>
        <div class="rc"><span class="cur" id="cur_netzladen_leistung"></span><input type="number" id="in_netzladen_leistung" min="0" step="100"><button class="btn" data-act="netzladen_leistung" data-src="in_netzladen_leistung">Setzen</button></div></div>
      <div class="res" id="res_netz"></div>
    </div></div>

    <div class="panel"><div class="ph"><b>Zwangsladen / -entladen</b><span class="r" id="ctZwangCur"></span></div><div class="pb">
      <div class="row"><div class="rl">Art</div><div class="rc"><select id="zwArt"><option value="laden">Laden</option><option value="entladen">Entladen</option></select></div></div>
      <div class="row"><div class="rl">Leistung<small>W</small></div><div class="rc"><input type="number" id="zwLeistung" min="100" step="100" value="2500"></div></div>
      <div class="row"><div class="rl">Vorgabe</div><div class="rc"><select id="zwVorgabe"><option value="dauer">Dauer (Minuten)</option><option value="soc">bis Ziel-SOC</option></select>
        <input type="number" id="zwDauer" min="1" max="1440" value="60"><input type="number" id="zwSoc" min="12" max="100" value="80" style="display:none"></div></div>
      <div class="acts" style="margin-top:10px"><button class="btn pri" id="zwStart">Starten</button><button class="btn warn" data-act="zwang_stop">Stoppen</button></div>
      <div class="note">Beim Zwangsladen geht die PV-Leistung in den Akku, Hausverbrauch wird aus dem Netz gedeckt. Läuft nach Ablauf der Dauer bzw. bei Erreichen des Ziel-SOC automatisch aus.</div>
      <div class="res" id="res_zwang"></div>
    </div></div>

    <div class="panel"><div class="ph"><b>Einspeisebegrenzung</b><span class="r" id="ctEinspCur"></span></div><div class="pb">
      <div class="row"><div class="rl">Wirkleistungsregelung</div><div class="rc"><select id="esModus"></select></div></div>
      <div class="row" id="esRowW"><div class="rl">Max. Einspeiseleistung<small>W</small></div><div class="rc"><span class="cur" id="cur_einspeise_w"></span><input type="number" id="esW" min="0" step="100"></div></div>
      <div class="row" id="esRowP"><div class="rl">Max. Einspeiseleistung<small>% der Nennleistung</small></div><div class="rc"><span class="cur" id="cur_einspeise_pct"></span><input type="number" id="esP" min="0" max="100" step="1"></div></div>
      <div class="acts" style="margin-top:10px"><button class="btn" id="esSet">Übernehmen</button></div>
      <div class="note w">Vorgaben des Netzbetreibers (z. B. Einspeisebegrenzung laut Anmeldung) müssen eingehalten werden. Änderungen sind nur möglich, wenn sie unter Einstellungen → Steuerung ausdrücklich erlaubt sind.</div>
      <div class="res" id="res_einsp"></div>
    </div></div>
  </div>
</section>

<!-- ================= Werte ================= -->
<section class="view" id="v-val">
  <div class="panel">
    <div class="ph"><b>Alle Werte &amp; MQTT-Topics</b><span class="r"><input class="search" id="flt" placeholder="Filter …"></span></div>
    <div class="pb" style="overflow-x:auto"><table class="tbl" id="allTbl"></table></div>
  </div>
</section>

<!-- ================= Einstellungen ================= -->
<section class="view" id="v-set">
  <div class="grid" style="gap:14px">
    <div class="panel"><div class="ph"><b>Wechselrichter (Modbus TCP)</b></div><div class="pb">
      <div class="form">
        <div class="f"><label>IP-Adresse / Hostname</label><input type="text" id="c_wr_host" placeholder="z. B. 192.168.200.50"><div class="h">SDongle oder Wechselrichter im Heimnetz</div></div>
        <div class="f"><label>Port</label><input type="number" id="c_wr_port"><div class="h">502 (SDongle / WLAN-FE) · 6607 (WR-Hotspot)</div></div>
        <div class="f"><label>Unit-ID</label><input type="number" id="c_wr_unit_id"><div class="h">meist 1 · sonst 0 oder 100</div></div>
        <div class="f"><label>Abfrageintervall (s)</label><input type="number" id="c_wr_intervall_s" step="1" min="2"></div>
        <div class="f"><label>Timeout (s)</label><input type="number" id="c_wr_timeout_s" step="1" min="3"><div class="h">SDongle: 15 s empfohlen</div></div>
        <div class="f"><label>Pause nach Verbinden (s)</label><input type="number" id="c_wr_verbindungs_pause_s" step="0.1" min="0"><div class="h">Huawei braucht ca. 1–2 s</div></div>
      </div>
      <div class="acts"><button class="btn" id="btnTestWr">Verbindung testen</button><span class="msg" id="msgWr"></span></div>
    </div></div>

    <div class="panel"><div class="ph"><b>MQTT</b></div><div class="pb">
      <div class="form">
        <div class="f"><label class="chk"><input type="checkbox" id="c_mq_aktiv"> MQTT aktiv</label></div>
        <div class="f"><label>Broker</label><input type="text" id="c_mq_host" placeholder="z. B. 192.168.200.10"></div>
        <div class="f"><label>Port</label><input type="number" id="c_mq_port"></div>
        <div class="f"><label>Benutzer</label><input type="text" id="c_mq_benutzer" autocomplete="off"></div>
        <div class="f"><label>Passwort</label><input type="password" id="c_mq_passwort" autocomplete="new-password"><div class="h">leer lassen = unverändert</div></div>
        <div class="f"><label>Client-ID</label><input type="text" id="c_mq_client_id"></div>
        <div class="f"><label>Basis-Topic</label><input type="text" id="c_mq_basis_topic"><div class="h">z. B. huawei_solar → huawei_solar/akku/soc_pct</div></div>
        <div class="f"><label>Senden erzwingen nach (s)</label><input type="number" id="c_mq_erzwingen_s" min="0"><div class="h">nur bei „nur Änderungen“</div></div>
        <div class="f"><label class="chk"><input type="checkbox" id="c_mq_retain"> Retain setzen</label></div>
        <div class="f"><label class="chk"><input type="checkbox" id="c_mq_nur_aenderungen"> Nur Änderungen senden</label></div>
        <div class="f"><label class="chk"><input type="checkbox" id="c_mq_json_topic"> Zusätzlich alles als JSON (…/json)</label></div>
      </div>
      <div class="acts"><button class="btn" id="btnTestMq">Broker testen</button><span class="msg" id="msgMq"></span></div>
    </div></div>

    <div class="panel"><div class="ph"><b>Steuerung</b><span class="r" id="stState"></span></div><div class="pb">
      <div class="note" style="margin:0 0 12px">Ab Werk wird nichts in den Wechselrichter geschrieben. Zum Freigeben sind <b>PIN</b> und die <b>Bestätigung der Anlage</b> nötig.
        Geschrieben wird danach nur, wenn genau diese Anlage (Seriennummer, direkt vor jedem Befehl aus dem Gerät gelesen) verbunden ist.</div>
      <dl class="kv" style="margin:0 0 12px;max-width:560px"><dt>Erkannte Anlage</dt><dd id="stDev">–</dd><dt>Bestätigte Anlage</dt><dd id="stConf">keine</dd></dl>
      <div class="form">
        <div class="f"><label class="chk"><input type="checkbox" id="c_st_aktiv"> Steuerung über die Webseite erlauben</label></div>
        <div class="f"><label class="chk"><input type="checkbox" id="c_st_geraet_bestaetigen"> Ich bestätige: die erkannte Anlage ist meine</label></div>
        <div class="f"><label>Neue PIN (mind. 4 Zeichen)</label><input type="password" id="c_st_pin" autocomplete="new-password" maxlength="32"><div class="h" id="pinHint">leer lassen = unverändert</div></div>
        <div class="f"><label>Aktuelle PIN</label><input type="password" id="pinAktuell" autocomplete="off" maxlength="32"><div class="h">nötig zum Freigeben oder Ändern der PIN</div></div>
        <div class="f"><label class="chk"><input type="checkbox" id="c_st_einspeisung_erlaubt"> Einspeisebegrenzung darf geändert werden</label><div class="h">nur mit Wissen über die Vorgaben des Netzbetreibers</div></div>
        <div class="f"><label class="chk"><input type="checkbox" id="c_st_pin_loeschen"> PIN entfernen (sperrt die Steuerung)</label></div>
      </div>
      <div class="note">Sperren geht immer ohne PIN. Jede Änderung wird mit IP-Adresse protokolliert.</div>
    </div></div>

    <div class="panel"><div class="ph"><b>System</b></div><div class="pb">
      <div class="form">
        <div class="f"><label class="chk"><input type="checkbox" id="c_sy_standby_verhindern"> Standby des PCs verhindern (Windows)</label><div class="h">sonst bricht die Abfrage ab, wenn der Rechner schläft</div></div>
      </div>
    </div></div>

    <div class="panel"><div class="ph"><b>Webseite</b></div><div class="pb">
      <div class="form">
        <div class="f"><label>Port</label><input type="number" id="c_web_port"><div class="h">Seite ist im ganzen Netzwerk erreichbar</div></div>
        <div class="f"><label>Titel</label><input type="text" id="c_web_titel"></div>
      </div>
    </div></div>

    <div class="acts" style="margin-top:0"><button class="btn pri" id="btnSave">Speichern</button><span class="msg" id="msgSave"></span></div>

    <div class="panel"><div class="ph"><b>Protokoll</b><span class="r" id="cfgPath"></span></div><div class="pb"><div class="log" id="log"></div></div></div>
  </div>
</section>
</main>

<div class="modal" id="modal"><div class="dlg">
  <div class="ph"><b>Änderung am Wechselrichter</b></div>
  <div class="pb"><p>Folgende Einstellung wird in den Wechselrichter geschrieben:</p>
    <div class="what" id="mWhat"></div>
    <div id="mPinBox" style="display:none;margin-bottom:12px"><label class="f" style="display:block"><span style="display:block;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);margin-bottom:5px">PIN</span><input type="password" id="mPin" autocomplete="off"></label></div>
    <div class="acts" style="margin-top:0"><button class="btn pri" id="mOk">Ausführen</button><button class="btn" id="mNo">Abbrechen</button><span class="msg" id="mMsg"></span></div>
  </div></div></div>

<script>
const $=id=>document.getElementById(id);
const nf=(v,d=0)=>v==null||isNaN(v)?'–':Number(v).toLocaleString('de-DE',{minimumFractionDigits:d,maximumFractionDigits:d});
function pw(w,html=true){ if(w==null) return '–'; const a=Math.abs(w);
  if(a>=1000){const s=nf(w/1000,2);return html?s+'<small>kW</small>':s+' kW'}
  return html?nf(w)+'<small>W</small>':nf(w)+' W'}
function pws(w){ if(w==null) return '–'; return Math.abs(w)>=1000? nf(w/1000,1)+' kW' : nf(w)+' W'}
let META=[], D=null, hours=24, HIST=[];

// ---------- Tabs ----------
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===b));
  document.querySelectorAll('.view').forEach(v=>v.classList.toggle('on',v.id==='v-'+b.dataset.v));
  if(b.dataset.v==='set') loadCfg();
  if(b.dataset.v==='ov') drawChart();
  if(b.dataset.v==='smart') setTimeout(smDraw,30);
  location.hash=b.dataset.v;
});
function fromHash(){const t=document.querySelector('.tab[data-v="'+location.hash.slice(1)+'"]'); if(t&&!t.classList.contains('on')) t.click();}
if(location.hash) fromHash();
window.addEventListener('hashchange',fromHash);

// ---------- Daten ----------
async function poll(){
  try{
    const r=await fetch('api/data',{cache:'no-store'}); D=await r.json(); render();
  }catch(e){ $('dWr').className='dot err'; showBanner('Keine Verbindung zum Dashboard-Programm.'); }
  setTimeout(poll,2000);
}
function showBanner(t){const b=$('banner'); b.textContent=t; b.style.display=t?'block':'none';}

function kv(el,rows){ el.innerHTML=rows.map(([k,v])=>`<dt>${k}</dt><dd>${v}</dd>`).join(''); }
function u(v,unit,d=0){ return v==null?'–':nf(v,d)+(unit?' '+unit:''); }

function render(){
  const v=D.werte, s=D.geraet, wr=D.wechselrichter, mq=D.mqtt;
  $('dWr').className='dot '+(wr.verbunden?'ok':'err');
  $('dMq').className='dot '+(mq.aktiv?(mq.verbunden?'ok':'err'):'off');
  const nx=wr.naechster_versuch?Math.max(0,Math.round(wr.naechster_versuch-wr.jetzt)):0;
  const stale=wr.verbunden&&wr.letzte_abfrage&&(wr.jetzt-wr.letzte_abfrage>120);
  showBanner(wr.verbunden?(stale?'Wechselrichter antwortet verzögert: '+(wr.fehler||''):''):('Wechselrichter: '+(wr.fehler||'nicht verbunden')+(nx?' – nächster Versuch in '+nx+' s':'')));
  $('sub').textContent=(s.modell||'Huawei SUN2000')+(s.seriennummer?' · SN '+s.seriennummer:'')+(wr.letzte_abfrage?' · '+new Date(wr.letzte_abfrage*1000).toLocaleTimeString('de-DE'):'');
  if(D.titel && $('title').textContent!==D.titel){$('title').textContent=D.titel; document.title=D.titel;}
  const akku=v._akku, zl=v._zaehler;

  // KPIs
  $('kPv').innerHTML=pw(v.pv_leistung);
  $('kPvS').textContent=s.nennleistung&&v.pv_leistung!=null?nf(100*v.pv_leistung/s.nennleistung)+' % der Nennleistung':'';
  $('kHaus').innerHTML=pw(v.haus_verbrauch);
  $('kHausS').textContent=v.autarkie_pct!=null?'Autarkie '+nf(v.autarkie_pct)+' %':(zl?'':'kein Zähler');
  if(akku){ $('kAkku').innerHTML=nf(v.akku_soc,1)+'<small>%</small>';
    const p=v.akku_leistung; $('kAkkuS').textContent=p==null?'':(p>10?'lädt '+pws(p):p<-10?'entlädt '+pws(-p):'Ruhe');
  } else { $('kAkku').innerHTML='–'; $('kAkkuS').textContent='kein Akku'; }
  if(zl){ const g=v.netz_leistung; $('kNetz').innerHTML=pw(Math.abs(g));
    $('kNetzS').textContent=g>10?'Einspeisung':g<-10?'Bezug':'ausgeglichen';
  } else { $('kNetz').innerHTML='–'; $('kNetzS').textContent='kein Zähler'; }
  $('kWr').innerHTML=pw(v.wr_leistung); $('kWrS').textContent=v.wr_status_text||'';
  $('kErt').innerHTML=v.ertrag_heute==null?'–':nf(v.ertrag_heute,2)+'<small>kWh</small>';
  $('kErtS').textContent=v.ertrag_gesamt!=null?'gesamt '+nf(v.ertrag_gesamt,0)+' kWh':'';

  // Energiefluss
  const pv=v.pv_leistung||0, g=zl?v.netz_leistung:null, ap=akku?v.akku_leistung:null, h=v.haus_verbrauch;
  $('tPv').textContent=pws(v.pv_leistung); $('tHaus').textContent=pws(h); $('tWr').textContent=pws(v.wr_leistung);
  $('tNetz').textContent=g==null?'–':pws(Math.abs(g)); $('tAkku').textContent=akku?nf(v.akku_soc)+' %':'–';
  $('lNetz').textContent=g==null?'':(g>10?'Einspeisung':g<-10?'Bezug':'');
  $('lAkku').textContent=ap==null?'':(ap>10?'laden '+pws(ap):ap<-10?'entladen '+pws(-ap):'');
  setFlow('fPv',pv>10,false); setFlow('fHaus',h!=null&&h>10,false);
  setFlow('fNetz',g!=null&&Math.abs(g)>10,g>0); setFlow('fAkku',ap!=null&&Math.abs(ap)>10,ap<0);
  $('flowTs').textContent=wr.dauer_ms?'Abfrage '+wr.dauer_ms+' ms':'';

  // Akku
  $('akkuNone').style.display=akku?'none':'block';
  document.querySelector('.soc').style.display=akku?'flex':'none';
  if(akku){
    const soc=v.akku_soc||0, L=2*Math.PI*52;
    $('socArc').setAttribute('stroke-dasharray',(L*soc/100)+' '+L);
    $('socArc').setAttribute('stroke',soc<15?'#f26d6d':soc<35?'#f5a524':'#a78bfa');
    $('socTxt').textContent=nf(soc,1)+'%';
    const st=v.akku_status; $('akkuBadge').innerHTML=`<span class="badge ${st===2?'ok':st===3?'err':'warn'}">${v.akku_status_text||'–'}</span>`;
    const cap=v.akku_kapazitaet;
    kv($('akkuKv'),[
      ['Leistung',ap==null?'–':(ap>10?'+':'')+pws(ap)],
      ['Kapazität',cap?nf(cap/1000,1)+' kWh':'–'],
      ['Energie gespeichert',cap&&v.akku_soc!=null?nf(cap*v.akku_soc/100000,2)+' kWh':'–'],
      ['Heute geladen',u(v.akku_geladen_heute,'kWh',2)],['Heute entladen',u(v.akku_entladen_heute,'kWh',2)],
      ['Temperatur',u(v.akku_temp,'°C',1)],['Bus',u(v.akku_bus_u,'V',1)+' / '+u(v.akku_bus_i,'A',1)],
      ['Gesamt geladen',u(v.akku_geladen_gesamt,'kWh',0)],['Gesamt entladen',u(v.akku_entladen_gesamt,'kWh',0)]]);
  } else $('akkuBadge').innerHTML='';

  // PV-Strings
  const n=Math.max(1,Math.min(4,s.pv_strings||2)); let rows='<tr><th>String</th><th>Spannung</th><th>Strom</th><th>Leistung</th></tr>';
  let maxP=Math.max(1,...[1,2,3,4].map(i=>v['pv'+i+'_p']||0));
  for(let i=1;i<=n;i++){const p=v['pv'+i+'_p'];
    rows+=`<tr><td class="t">PV${i}<div class="bar"><i style="width:${p?Math.min(100,100*p/maxP):0}%"></i></div></td><td>${u(v['pv'+i+'_u'],'V',1)}</td><td>${u(v['pv'+i+'_i'],'A',2)}</td><td>${pws(p)}</td></tr>`;}
  $('pvTbl').innerHTML=rows; $('pvSum').textContent='Σ '+pws(v.pv_leistung);

  // Wechselrichter
  const wc=v.wr_status; const cls=wc==null?'':(wc>=0x200&&wc<0x300)?'ok':(wc>=0x300&&wc<0x400)?'err':'warn';
  $('wrBadge').innerHTML=v.wr_status_text?`<span class="badge ${cls}">${v.wr_status_text}</span>`:'';
  const alarm=[v.alarm1,v.alarm2,v.alarm3].some(x=>x);
  kv($('wrKv'),[['Wirkleistung',pws(v.wr_leistung)],['Blindleistung',u(v.wr_blind,'var')],['Leistungsfaktor',u(v.wr_pf,'',3)],
    ['Frequenz',u(v.wr_freq,'Hz',2)],['Wirkungsgrad',u(v.wr_eff,'%',2)],['Innentemperatur',u(v.wr_temp,'°C',1)],
    ['Isolationswiderstand',u(v.wr_iso,'MΩ',3)],['Spitze heute',pws(v.spitze_heute)],
    ['Alarme',alarm?`<span class="badge err">${[v.alarm1,v.alarm2,v.alarm3].map(x=>'0x'+(x||0).toString(16).toUpperCase().padStart(4,'0')).join(' ')}</span>`:'<span class="badge ok">keine</span>']]);
  const ago=t=>{ if(!t) return '–'; const s=Math.max(0,Math.round(wr.jetzt-t)); return s<120?s+' s':s<7200?Math.round(s/60)+' min':(s/3600).toLocaleString('de-DE',{maximumFractionDigits:1})+' h'; };
  kv($('conKv'),[['Status',wr.verbunden?'<span class="badge ok">verbunden</span>':`<span class="badge err">getrennt</span>`],
    ['Verbunden seit',wr.verbunden&&wr.verbunden_seit?ago(wr.verbunden_seit):'–'],
    ['Letzte Abfrage',wr.letzte_abfrage?'vor '+ago(wr.letzte_abfrage):'–'],
    ['Abbrüche seit Start',nf(wr.abbrueche)],['Zeitüberschreitungen',nf(wr.zeitueberschreitungen)],
    ['Letzter Abbruch',wr.letzter_abbruch?'vor '+ago(wr.letzter_abbruch):'–'],
    ...(wr.letzte_ursache?[['Ursache','<span style="white-space:normal;color:var(--dim)">'+esc(wr.letzte_ursache)+'</span>']]:[])]);
  $('wrPh').innerHTML='<tr><th>Phase</th><th>Spannung</th><th>Strom</th></tr>'+[1,2,3].map(i=>`<tr><td class="t">L${i}</td><td>${u(v['u_l'+i],'V',1)}</td><td>${u(v['i_l'+i],'A',2)}</td></tr>`).join('');

  // Netz
  $('netzNone').style.display=zl?'none':'block'; $('netzKv').style.display=$('netzPh').style.display=zl?'':'none';
  $('netzBadge').innerHTML=zl?'<span class="badge ok">Zähler OK</span>':'<span class="badge warn">kein Zähler</span>';
  if(zl){
    kv($('netzKv'),[['Netzleistung',(g>0?'+':'')+pws(g)],['Bezug',pws(v.netz_bezug)],['Einspeisung',pws(v.netz_einspeisung)],
      ['Frequenz',u(v.netz_freq,'Hz',2)],['Eingespeist gesamt',u(v.netz_eingespeist,'kWh',1)],['Bezogen gesamt',u(v.netz_bezogen,'kWh',1)],
      ['Eigenverbrauch (aktuell)',u(v.eigenverbrauch_pct,'%',0)]]);
    $('netzPh').innerHTML='<tr><th>Phase</th><th>Spannung</th><th>Strom</th><th>Leistung</th></tr>'+[1,2,3].map(i=>`<tr><td class="t">L${i}</td><td>${u(v['netz_u_l'+i],'V',1)}</td><td>${u(v['netz_i_l'+i],'A',2)}</td><td>${pws(v['netz_p_l'+i])}</td></tr>`).join('');
  }
  renderAll(); renderCtl();
}
function esc(t){return String(t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

// ---------- Steuerung ----------
let ctlInit=false;
function renderCtl(){
  const v=D.werte, sc=D.steuerung;
  $('ctlLock').style.display=sc.sperre?'block':'none';
  if(sc.sperre) $('ctlLock').innerHTML='<b>Steuerung gesperrt:</b> '+esc(sc.sperre)+'<br>Freigabe unter <a href="#set">Einstellungen → Steuerung</a> (PIN und Bestätigung der Anlage).';
  document.querySelectorAll('#ctlBox button,#ctlBox select,#ctlBox input').forEach(e=>e.disabled=!!sc.sperre);
  document.querySelectorAll('#esModus,#esW,#esP,#esSet').forEach(e=>e.disabled=!!sc.sperre||!sc.einspeisung_erlaubt);
  if(!ctlInit && sc.modi){ ctlInit=true;
    $('ctMode').innerHTML=Object.entries(sc.modi).map(([k,t])=>`<option value="${k}">${t}</option>`).join('');
    $('esModus').innerHTML=Object.entries(sc.einspeise_modi).map(([k,t])=>`<option value="${k}">${t}</option>`).join('');
    if(v.st_modus!=null) $('ctMode').value=v.st_modus;
    if(v.st_einspeise_modus!=null) $('esModus').value=v.st_einspeise_modus;
    if(v.st_pv_tou!=null) $('ctPvTou').value=v.st_pv_tou;
    esVis();
  }
  const na='<span style="color:var(--mute)">n. v.</span>';
  $('ctModeCur').innerHTML=v.st_modus_text?`<span class="badge ok">${esc(v.st_modus_text)}</span>`:'';
  const cur=(id,val,unit)=>{const e=$('cur_'+id); if(e) e.innerHTML=val==null?na:nf(val,unit==='%'?0:0)+' '+unit;};
  cur('ladeschluss',v.st_ladeschluss,'%'); cur('entladeschluss',v.st_entladeschluss,'%');
  cur('max_laden',v.st_max_laden,'W'); cur('max_entladen',v.st_max_entladen,'W');
  cur('netzladen_soc',v.st_netzladen_soc,'%'); cur('netzladen_leistung',v.st_netzladen_leistung,'W');
  cur('einspeise_w',v.st_einspeise_w,'W'); cur('einspeise_pct',v.st_einspeise_pct,'%');
  $('cur_pv_tou').innerHTML=v.st_pv_tou==null?na:(v.st_pv_tou?'laden':'einspeisen');
  $('lim_laden').textContent='W · Akku max. '+(v.akku_max_laden?nf(v.akku_max_laden)+' W':'?');
  $('lim_entladen').textContent='W · Akku max. '+(v.akku_max_entladen?nf(v.akku_max_entladen)+' W':'?');
  $('ctNetzCur').innerHTML=v.st_netzladen==null?'':`<span class="badge ${v.st_netzladen?'warn':''}">${v.st_netzladen?'an':'aus'}</span>`;
  const z=v.st_zwang; $('ctZwangCur').innerHTML=z==null?'':`<span class="badge ${z?'warn':''}">${esc(v.st_zwang_text)}</span>`;
  $('ctEinspCur').innerHTML=v.st_einspeise_text?`<span class="badge">${esc(v.st_einspeise_text)}</span>`:'';
}
function esVis(){const m=$('esModus').value; $('esRowW').style.display=m==='6'?'':'none'; $('esRowP').style.display=m==='7'?'':'none';}
$('esModus').onchange=esVis;
$('zwVorgabe').onchange=()=>{const d=$('zwVorgabe').value==='dauer'; $('zwDauer').style.display=d?'':'none'; $('zwSoc').style.display=d?'none':'';};
const RES={modus:'res_modus',pv_tou:'res_modus',ladeschluss:'res_grenzen',entladeschluss:'res_grenzen',max_laden:'res_grenzen',max_entladen:'res_grenzen',
  netzladen:'res_netz',netzladen_soc:'res_netz',netzladen_leistung:'res_netz',zwang_start:'res_zwang',zwang_stop:'res_zwang',einspeisung:'res_einsp'};
const TXT={modus:'Arbeitsmodus',pv_tou:'PV-Überschuss im Zeitmodus',ladeschluss:'Ladeschluss-SOC',entladeschluss:'Entladeschluss-SOC',max_laden:'Max. Ladeleistung',
  max_entladen:'Max. Entladeleistung',netzladen:'Laden aus dem Netz',netzladen_soc:'Netzladen bis SOC',netzladen_leistung:'Max. Netzladeleistung'};
document.querySelectorAll('#ctlBox [data-act]').forEach(b=>b.onclick=()=>{
  const a=b.dataset.act; let w={}, label;
  if(a==='zwang_stop'){ label='Zwangsladen/-entladen beenden'; }
  else if(b.dataset.src){ const el=$(b.dataset.src); if(el.value===''){res(a,'Bitte einen Wert eingeben','err');return;}
    w.wert=Number(el.value); label=TXT[a]+': '+(el.tagName==='SELECT'?el.options[el.selectedIndex].text:el.value+(el.id.includes('laden')&&!el.id.includes('soc')&&!el.id.includes('schluss')?' W':' %')); }
  else { w.wert=b.dataset.val==='1'; label=TXT[a]+': '+(w.wert?'an':'aus'); }
  ask(a,w,label);
});
$('zwStart').onclick=()=>{
  const w={art:$('zwArt').value,leistung:Number($('zwLeistung').value),vorgabe:$('zwVorgabe').value,dauer:Number($('zwDauer').value),ziel_soc:Number($('zwSoc').value)};
  ask('zwang_start',w,'Zwangs'+w.art+' mit '+w.leistung+' W, '+(w.vorgabe==='dauer'?w.dauer+' min':'bis '+w.ziel_soc+' %'));
};
$('esSet').onclick=()=>{
  const m=$('esModus').value, w={modus:Number(m),max_w:Number($('esW').value),max_pct:Number($('esP').value)};
  if(m==='6'&&$('esW').value===''){res('einspeisung','Bitte Leistung eingeben','err');return;}
  if(m==='7'&&$('esP').value===''){res('einspeisung','Bitte Prozentwert eingeben','err');return;}
  ask('einspeisung',w,'Wirkleistungsregelung: '+$('esModus').options[$('esModus').selectedIndex].text+(m==='6'?' '+w.max_w+' W':m==='7'?' '+w.max_pct+' %':''));
};
function res(a,t,c){const e=$(RES[a]); if(e){e.textContent=t; e.className='res '+(c||'');}}
let pending=null;
function ask(a,w,label){ pending={a,w}; $('mWhat').textContent=label; $('mPinBox').style.display=D.steuerung.pin?'block':'none';
  $('mPin').value=''; $('mMsg').textContent=''; $('mMsg').className='msg'; $('mOk').disabled=false; $('modal').classList.add('on'); if(D.steuerung.pin) setTimeout(()=>$('mPin').focus(),50); }
$('mNo').onclick=()=>{$('modal').classList.remove('on'); pending=null;};
$('modal').onclick=e=>{ if(e.target.id==='modal') $('mNo').click(); };
$('mPin').onkeydown=e=>{ if(e.key==='Enter') $('mOk').click(); };
$('mOk').onclick=async()=>{
  if(!pending) return; const {a,w}=pending;
  if(a==='__ack'){ $('mOk').disabled=true;
    const r=await fetch('api/smart/quittieren',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin:$('mPin').value})}); const j=await r.json();
    if(j.pin_falsch){ $('mMsg').textContent='PIN falsch'; $('mMsg').className='msg err'; $('mOk').disabled=false; return; }
    $('modal').classList.remove('on'); pending=null; smLoad(true); return; }
  if(a==='__smart'){ $('mOk').disabled=true; const r=await smSave($('mPin').value);
    if(r==='pin'){ $('mMsg').textContent='PIN falsch'; $('mMsg').className='msg err'; $('mOk').disabled=false; $('mPin').select(); return; }
    $('modal').classList.remove('on'); pending=null; return; } $('mOk').disabled=true; $('mMsg').textContent='schreibe …'; $('mMsg').className='msg';
  try{ const r=await fetch('api/steuern',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({aktion:a,werte:w,pin:$('mPin').value})});
    const j=await r.json();
    if(j.pin_falsch){ $('mMsg').textContent='PIN falsch'; $('mMsg').className='msg err'; $('mOk').disabled=false; $('mPin').select(); return; }
    $('modal').classList.remove('on'); pending=null;
    if(!j.ok){ res(a,'Fehler: '+j.fehler,'err'); return; }
    if(j.abweichung) res(a,'Geschrieben, Gerät meldet: '+j.ergebnis.filter(x=>!x.ok).map(x=>x.bezeichnung+' = '+x.gelesen).join(', '),'err');
    else res(a,'✓ '+j.text,'ok');
  }catch(e){ $('modal').classList.remove('on'); res(a,'Fehler: '+e,'err'); }
};
function setFlow(id,on,rev){const e=$(id); e.classList.toggle('on',!!on); e.classList.toggle('rev',!!rev);}

// ---------- Smart-Laden ----------
const SL={
  A:[{k:'ziel_soc',t:'Ziel-SOC',h:'bis zu diesem Ladezustand aus dem Netz laden',min:10,max:100,step:1,f:v=>v+' %'},
     {k:'ladeleistung_w',t:'Ladeleistung aus dem Netz',min:300,max:10000,step:100,f:v=>nf(v)+' W'},
     {k:'horizont_h',t:'Vorausschau',h:'so weit plant die Automatik voraus',min:4,max:40,step:1,f:v=>v+' h'}],
  B:[{k:'pv_vertrauen_pct',t:'PV-Prognose berücksichtigen',h:'0 % = ignorieren · 100 % = voll vertrauen',min:0,max:150,step:5,f:v=>v+' %'},
     {k:'kwp',t:'Anlagenleistung',min:0.5,max:30,step:0.1,f:v=>nf(v,1)+' kWp'},
     {k:'neigung',t:'Modulneigung',min:0,max:90,step:1,f:v=>v+'°'},
     {k:'ausrichtung',t:'Ausrichtung',h:'−90 Ost · 0 Süd · 90 West',min:-180,max:180,step:5,f:v=>v+'° '+(Math.abs(v)<=22?'Süd':v<-157||v>157?'Nord':v<-67&&v>-113?'Ost':v>67&&v<113?'West':v<0?'Südost':'Südwest')},
     {k:'wirkungsgrad_pct',t:'Systemwirkungsgrad',h:'Verluste durch Wärme, Wechselrichter, Verschattung',min:30,max:110,step:1,f:v=>v+' %'}],
  C:[{k:'aufschlag_ct',t:'Aufschlag (Netzentgelt, Umlagen …)',min:0,max:40,step:0.5,f:v=>nf(v,1)+' ct/kWh'},
     {k:'mwst_pct',t:'MwSt',min:0,max:25,step:1,f:v=>v+' %'},
     {k:'grundlast_w',t:'Grundlast (solange keine Statistik da ist)',min:0,max:3000,step:50,f:v=>nf(v)+' W'}]
};
let SM=null, SMF=null, smDirty=false, smInit=false, smPlan=null, smTimer=null;
function slHtml(d){return `<div class="sl"><div class="lab"><span>${d.t}${d.h?'<small>'+d.h+'</small>':''}</span><b id="v_${d.k}"></b></div>
  <input type="range" id="sm_${d.k}" min="${d.min}" max="${d.max}" step="${d.step}"></div>`;}
function smBuild(){
  $('slA').innerHTML=`<div class="sl"><div class="lab"><span>Preisbereich für Netzladung<small>laden, wenn der Preis in diesem Bereich liegt</small></span><b id="v_preis"></b></div>
    <div class="dual"><div class="fill" id="pfill"></div><input type="range" id="sm_preis_min_ct" min="-20" max="60" step="0.5"><input type="range" id="sm_preis_max_ct" min="-20" max="60" step="0.5"></div></div>`
    +SL.A.map(slHtml).join('');
  $('slB').innerHTML=SL.B.map(slHtml).join(''); $('slC').innerHTML=SL.C.map(slHtml).join('');
  $('sm_zone').innerHTML=Object.entries(SM.zonen).map(([k,t])=>`<option value="${k}">${t} (${k})</option>`).join('');
  document.querySelectorAll('#v-smart input[type=range]').forEach(el=>el.addEventListener('input',()=>{
    const a=$('sm_preis_min_ct'), b=$('sm_preis_max_ct');
    if(el===a&&+a.value>+b.value) a.value=b.value; if(el===b&&+b.value<+a.value) b.value=a.value;
    SMF[el.id.slice(3)]=+el.value; smLabels(); smChanged(); }));
  $('sm_zone').onchange=()=>{SMF.zone=$('sm_zone').value; smChanged();};
  $('sm_kalibrierung').onchange=()=>{SMF.kalibrierung=$('sm_kalibrierung').checked; smChanged();};
  $('sm_aktiv').onchange=()=>{SMF.aktiv=$('sm_aktiv').checked; smChanged(false);};
  $('sm_probebetrieb').onchange=()=>{SMF.probebetrieb=$('sm_probebetrieb').checked; smChanged(false);};
  document.querySelectorAll('#sm_prognose button').forEach(b=>b.onclick=()=>{SMF.prognose=b.dataset.v; smLabels(); smChanged();});
}
function smFill(){
  const f=SMF; for(const k in f){const el=$('sm_'+k); if(!el) continue; if(el.type==='checkbox') el.checked=!!f[k]; else if(el.tagName!=='DIV') el.value=f[k];}
  smLabels();
}
function smLabels(){
  const f=SMF; for(const d of [...SL.A,...SL.B,...SL.C]) $('v_'+d.k).textContent=d.f(+f[d.k]);
  $('v_preis').textContent=nf(f.preis_min_ct,1)+' … '+nf(f.preis_max_ct,1)+' ct';
  const lo=(f.preis_min_ct+20)/80*100, hi=(f.preis_max_ct+20)/80*100; $('pfill').style.left=lo+'%'; $('pfill').style.width=(hi-lo)+'%';
  document.querySelectorAll('#sm_prognose button').forEach(b=>b.classList.toggle('on',b.dataset.v===f.prognose));
  $('smOrt').textContent=f.ort_name?f.ort_name+' ('+nf(f.lat,3)+', '+nf(f.lon,3)+')':'nicht gesetzt – ohne Standort wird die eigene Statistik verwendet';
}
function smChanged(preview=true){
  smDirty=true; $('smPrev').style.display='inline-block';
  if(!preview) return; clearTimeout(smTimer);
  smTimer=setTimeout(async()=>{ try{const r=await fetch('api/smart/vorschau',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({smart:SMF})});
    const j=await r.json(); if(j.ok){smPlan=j.plan; smDraw(); smKpiPlan();} else $('smMsg').textContent=j.fehler, $('smMsg').className='res err';}catch(e){} },350);
}
async function smLoad(force){
  try{ const r=await fetch('api/smart',{cache:'no-store'}); SM=await r.json(); }catch(e){return;}
  const z=SM.zustand;
  $('kPreis').innerHTML=z.preis_ct==null?'–':nf(z.preis_ct,1)+'<small>ct</small>';
  $('kPreisS').textContent=SM.einstellungen.aktiv?(z.aktiv_laden?'lädt aus dem Netz':'Automatik an'):'Automatik aus';
  if(!$('v-smart').classList.contains('on') && !force) return;
  if(!smInit){ smInit=true; smBuild(); }
  if(!smDirty||force){ SMF=JSON.parse(JSON.stringify(SM.einstellungen)); smFill(); smPlan=z.plan; smDirty=false; $('smPrev').style.display='none'; }
  $('smLock').style.display=(SM.steuerung_aktiv||SM.einstellungen.probebetrieb)?'none':'block';
  $('smStatus').innerHTML=`<span class="badge ${z.stoerung?'err':z.aktiv_laden?'warn':SM.einstellungen.aktiv?'ok':''}" style="white-space:normal">${esc(z.status)}</span>`;
  $('smFault').style.display=z.stoerung?'block':'none'; $('smFaultTxt').textContent='STÖRUNG: '+(z.stoerung||'')+' – die Automatik ist gesperrt, bis die Ursache geklärt und die Störung quittiert ist.';
  const ck=z.pruefungen||[]; const nok=ck.filter(c=>!c.ok).length;
  $('smChkSum').innerHTML=ck.length?(nok?`<span class="badge err">${nok} nicht erfüllt</span>`:'<span class="badge ok">alle erfüllt</span>'):'';
  $('smChecks').innerHTML=ck.map(c=>`<div><span style="color:${c.ok?'var(--green)':'var(--red)'}">${c.ok?'✓':'✗'}</span> ${esc(c.name)}${c.info?' <span style="color:var(--mute)">– '+esc(c.info)+'</span>':''}</div>`).join('');
  $('smPreis').innerHTML=z.preis_ct==null?'–':nf(z.preis_ct,2)+'<small>ct/kWh</small>';
  $('smPreisS').textContent=z.preis_boerse_ct==null?(z.preis_fehler||'kein Preis'):'Börse '+nf(z.preis_boerse_ct,2)+' ct · '+z.preis_quelle;
  $('smTag').innerHTML=z.heute_min_ct==null?'–':nf(z.heute_min_ct,1)+'–'+nf(z.heute_max_ct,1)+'<small>ct</small>';
  $('smTagS').textContent=z.heute_min_ct==null?'':'Ø '+nf(z.heute_mittel_ct,1)+' ct · morgen '+(z.morgen_verfuegbar?'verfügbar':'ab ca. 13 Uhr');
  $('smPv').innerHTML=z.pv_rest_heute_kwh==null?'–':nf(z.pv_rest_heute_kwh,1)+'<small>kWh</small>';
  $('smPvS').textContent=z.pv_rest_heute_kwh==null?(z.pv_fehler||'keine Prognose'):'Rest heute · morgen '+nf(z.pv_morgen_kwh,1)+' kWh';
  $('smKal').textContent=z.kalibrierung?'Faktor '+nf(z.kalibrierung,2):'lernt noch ('+z.kalibrierung_stunden+'/12 h)';
  $('smQuelleInfo').textContent='Statistik: '+z.statistik_tage+' Tag(e) Messwerte';
  $('smSrc').textContent=z.preis_abruf?'Preise '+new Date(z.preis_abruf*1000).toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})+(z.pv_abruf?' · Wetter '+new Date(z.pv_abruf*1000).toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'}):''):'';
  smKpiPlan(); smDraw();
}
function smKpiPlan(){
  const p=smPlan; if(!p){$('smPlan').textContent='–'; $('smPlanS').textContent='Akku nicht verbunden'; return;}
  $('smPlan').innerHTML=nf(p.geplant_kwh,1)+'<small>kWh</small>';
  const nx=p.naechste_ladung?new Date(p.naechste_ladung*1000).toLocaleString('de-DE',{weekday:'short',hour:'2-digit',minute:'2-digit'}):null;
  $('smPlanS').textContent=nx?('ab '+nx+(p.kosten_ct_kwh!=null?' · Ø '+nf(p.kosten_ct_kwh,1)+' ct':'')):(p.pv_gesperrt?p.pv_gesperrt+' günstige ¼ h wegen PV ausgelassen':'keine');
}
document.querySelector('.tab[data-v="smart"]').addEventListener('click',()=>smLoad());
setInterval(()=>smLoad(),10000);
$('smReset').onclick=()=>smLoad(true);
$('smGeoBtn').onclick=async()=>{
  const q=$('smGeoQ').value.trim(); $('smGeoList').innerHTML='<span class="msg">suche …</span>';
  try{const r=await fetch('api/geo?q='+encodeURIComponent(q)); const j=await r.json();
    if(!j.ok){$('smGeoList').innerHTML='<span class="msg err">'+esc(j.fehler)+'</span>';return;}
    if(!j.treffer.length){$('smGeoList').innerHTML='<span class="msg">nichts gefunden</span>';return;}
    $('smGeoList').innerHTML=j.treffer.map((t,i)=>`<button data-i="${i}">${esc(t.beschreibung)}</button>`).join('');
    $('smGeoList').querySelectorAll('button').forEach(b=>b.onclick=()=>{const t=j.treffer[+b.dataset.i];
      SMF.ort_name=t.beschreibung; SMF.lat=t.lat; SMF.lon=t.lon; $('smGeoList').innerHTML=''; smLabels(); smChanged();});
  }catch(e){$('smGeoList').innerHTML='<span class="msg err">'+e+'</span>';}
};
$('smGeoQ').onkeydown=e=>{if(e.key==='Enter') $('smGeoBtn').click();};
$('smAck').onclick=()=>{ pending={a:'__ack'}; $('mWhat').textContent='Störung der Smart-Laden-Automatik quittieren';
  $('mPinBox').style.display=SM.pin?'block':'none'; $('mPin').value=''; $('mMsg').textContent=''; $('mOk').disabled=false; $('modal').classList.add('on'); };
$('smSave').onclick=()=>{
  if(SMF.aktiv&&!SMF.probebetrieb&&SM.pin){ pending={a:'__smart'}; $('mWhat').textContent='Smart-Laden: '+(SMF.aktiv?'Automatik an':'Automatik aus')+' · '+nf(SMF.preis_min_ct,1)+'…'+nf(SMF.preis_max_ct,1)+' ct · Ziel '+SMF.ziel_soc+' %';
    $('mWhat').textContent='Smart-Laden SCHARF schalten (schreibt in den Wechselrichter) · '+nf(SMF.preis_min_ct,1)+'…'+nf(SMF.preis_max_ct,1)+' ct · Ziel '+SMF.ziel_soc+' %';
    $('mPinBox').style.display='block'; $('mPin').value=''; $('mMsg').textContent=''; $('mOk').disabled=false; $('modal').classList.add('on'); setTimeout(()=>$('mPin').focus(),50); return; }
  smSave('');
};
async function smSave(pin){
  try{const r=await fetch('api/smart',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({smart:SMF,pin})}); const j=await r.json();
    if(j.pin_falsch) return 'pin';
    $('smMsg').textContent=j.ok?'✓ Übernommen':'Fehler: '+j.fehler; $('smMsg').className='res '+(j.ok?'ok':'err');
    if(j.ok){ smDirty=false; setTimeout(()=>smLoad(true),800); }
  }catch(e){ $('smMsg').textContent='Fehler: '+e; $('smMsg').className='res err'; }
  return 'ok';
}
// Diagramme
let smGeo={};
function smAxes(c,W,H,L,R,T,B,steps){
  const n=steps.length, t0=steps[0].t, t1=steps[n-1].t+900, pw_=W-L-R;
  const X=t=>L+(t-t0)/(t1-t0)*pw_;
  c.font='10px ui-monospace,Consolas,monospace'; c.textAlign='center'; c.textBaseline='top'; c.fillStyle='#5d6b77';
  let st=3600; for(const s of [3600,7200,10800,21600]){ if(s/(t1-t0)*pw_>=55){st=s;break;} }
  const tz=new Date().getTimezoneOffset()*60;
  for(let t=Math.ceil((t0-tz)/st)*st+tz;t<=t1;t+=st){const x=X(t); if(x<L+14) continue;
    c.strokeStyle='rgba(38,49,59,.55)'; c.beginPath(); c.moveTo(x+.5,T); c.lineTo(x+.5,H-B); c.stroke();
    const d=new Date(t*1000); c.fillText(d.getHours()===0?d.toLocaleDateString('de-DE',{weekday:'short'}):d.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'}),x,H-B+6);}
  const nx=X(Date.now()/1000); c.strokeStyle='#f5a524'; c.setLineDash([3,3]); c.beginPath(); c.moveTo(nx+.5,T); c.lineTo(nx+.5,H-B); c.stroke(); c.setLineDash([]);
  return X;
}
function canvasCtx(cv){const w=cv.parentElement; const dpr=window.devicePixelRatio||1, W=w.clientWidth, H=w.clientHeight;
  cv.width=W*dpr; cv.height=H*dpr; const c=cv.getContext('2d'); c.setTransform(dpr,0,0,dpr,0,0); c.clearRect(0,0,W,H); return [c,W,H];}
function smDraw(){
  if(!$('v-smart').classList.contains('on')) return;
  const p=smPlan; const [c,W,H]=canvasCtx($('chP')); const [e,W2,H2]=canvasCtx($('chE'));
  if(!p||!p.schritte.length){ for(const [x,w,h] of [[c,W,H],[e,W2,H2]]){x.fillStyle='#5d6b77';x.font='12px ui-monospace,monospace';x.textAlign='center';x.fillText('Kein Plan – Akku/Preise noch nicht verfügbar',w/2,h/2);} return; }
  const S=p.schritte, L=52,R=44,T=10,B=24, ph=H-T-B, f=SMF;
  // Preis
  const pr=S.map(s=>s.preis_ct).filter(v=>v!=null);
  let mn=Math.min(0,f.preis_min_ct>-20?f.preis_min_ct:0,...pr), mx=Math.max(5,f.preis_max_ct,...pr); const stp=niceStep((mx-mn)/4); mn=Math.floor(mn/stp)*stp; mx=Math.ceil(mx/stp)*stp;
  const Y=v=>T+ph-(v-mn)/(mx-mn)*ph;
  c.font='10px ui-monospace,Consolas,monospace'; c.textAlign='right'; c.textBaseline='middle';
  for(let v=mn;v<=mx+1e-9;v+=stp){c.strokeStyle='#26313b'; const y=Math.round(Y(v))+.5; c.beginPath(); c.moveTo(L,y); c.lineTo(W-R,y); c.stroke(); c.fillStyle='#5d6b77'; c.fillText(nf(v,stp<1?1:0)+' ct',L-6,y);}
  const X=smAxes(c,W,H,L,R,T,B,S); const bw=Math.max(1,X(S[0].t+900)-X(S[0].t)-1);
  const ylo=Y(Math.max(mn,f.preis_min_ct)), yhi=Y(Math.min(mx,f.preis_max_ct));
  c.fillStyle='rgba(45,212,191,.06)'; c.fillRect(L,yhi,W-L-R,ylo-yhi);
  c.strokeStyle='rgba(45,212,191,.55)'; c.setLineDash([4,4]); for(const y of [yhi, f.preis_min_ct>mn?ylo:null]) if(y!=null){c.beginPath(); c.moveTo(L,y+.5); c.lineTo(W-R,y+.5); c.stroke();} c.setLineDash([]);
  for(const s of S){ if(s.preis_ct==null) continue; const x=X(s.t), y0=Y(0), y=Y(s.preis_ct);
    c.fillStyle=s.netz_wh>0?'#a78bfa':s.grund==='PV-Überschuss erwartet'?'#b3742a':s.im_bereich?'#2dd4bf':'#33414d';
    c.fillRect(x,Math.min(y,y0),bw,Math.max(1,Math.abs(y0-y))); }
  smGeo.P={X,S,L,R,W}; smGeo.E={X,S,L,R,W:W2};
  // Energie
  const ph2=H2-T-B; let emx=Math.max(1000,...S.map(s=>Math.max(s.pv_w,s.last_w,s.netz_wh*4))); const es=niceStep(emx/4); emx=Math.ceil(emx/es)*es;
  const YE=v=>T+ph2-v/emx*ph2, YS=v=>T+ph2-v/100*ph2;
  e.font='10px ui-monospace,Consolas,monospace'; e.textAlign='right'; e.textBaseline='middle';
  for(let v=0;v<=emx+1e-9;v+=es){e.strokeStyle='#26313b'; const y=Math.round(YE(v))+.5; e.beginPath(); e.moveTo(L,y); e.lineTo(W2-R,y); e.stroke(); e.fillStyle='#5d6b77'; e.fillText(v>=1000?nf(v/1000,1)+' kW':v+' W',L-6,y);}
  e.textAlign='left'; e.fillStyle='#4ade80'; for(const v of [0,50,100]) e.fillText(v+'%',W2-R+6,YS(v));
  const X2=smAxes(e,W2,H2,L,R,T,B,S); const bw2=Math.max(1,X2(S[0].t+900)-X2(S[0].t)-1);
  for(const s of S) if(s.netz_wh>0){ e.fillStyle='rgba(167,139,250,.7)'; const y=YE(s.netz_wh*4); e.fillRect(X2(s.t),y,bw2,YE(0)-y); }
  e.fillStyle='rgba(245,165,36,.16)'; e.beginPath(); e.moveTo(X2(S[0].t),YE(0)); for(const s of S) e.lineTo(X2(s.t+450),YE(s.pv_w)); e.lineTo(X2(S[S.length-1].t+900),YE(0)); e.closePath(); e.fill();
  const ln=(fn,col,yf,dash,w)=>{e.strokeStyle=col; e.lineWidth=w||1.6; e.setLineDash(dash||[]); e.beginPath(); S.forEach((s,i)=>{const x=X2(s.t+450), y=yf(fn(s)); i?e.lineTo(x,y):e.moveTo(x,y);}); e.stroke(); e.setLineDash([]); e.lineWidth=1;};
  ln(s=>s.pv_w,'#f5a524',YE); if(f.pv_vertrauen_pct!=100) ln(s=>s.pv_plan_w,'rgba(245,165,36,.6)',YE,[3,3]);
  ln(s=>s.last_w,'#2dd4bf',YE); ln(s=>s.soc_ohne_pct,'rgba(74,222,128,.35)',YS,[4,4]); ln(s=>s.soc_pct,'#4ade80',YS,null,2);
}
function smTip(cwId,tipId,key){ const cw=$(cwId), tip=$(tipId);
  cw.addEventListener('mousemove',ev=>{const g=smGeo[key]; if(!g) return; const r=cw.getBoundingClientRect(), x=ev.clientX-r.left;
    const s=g.S.find(s=>x>=g.X(s.t)&&x<g.X(s.t+900)); if(!s){tip.style.display='none';return;}
    const tm=new Date(s.t*1000).toLocaleString('de-DE',{weekday:'short',hour:'2-digit',minute:'2-digit'});
    tip.innerHTML=`${tm}<br>Preis ${s.preis_ct==null?'–':nf(s.preis_ct,2)+' ct'}<br><span style="color:#f5a524">PV</span> ${pws(s.pv_w)} · <span style="color:#2dd4bf">Last</span> ${pws(s.last_w)}<br>`+
      `<span style="color:#a78bfa">Netzladung</span> ${s.netz_wh>0?nf(s.netz_wh/1000,2)+' kWh':'–'}<br><span style="color:#4ade80">SOC</span> ${nf(s.soc_pct,0)} %`+(s.grund?'<br><span style="color:#f5a524">'+esc(s.grund)+'</span>':'');
    tip.style.display='block'; tip.style.left=Math.min(x+14,r.width-180)+'px'; tip.style.top='8px';});
  cw.addEventListener('mouseleave',()=>tip.style.display='none'); }
smTip('cwP','tipP','P'); smTip('cwE','tipE','E');
window.addEventListener('resize',smDraw);
smLoad(true);

// ---------- Werte-Tabelle ----------
const GRP={geraet:'Gerät',pv:'PV',wr:'Wechselrichter',akku:'Akku',netz:'Netz',haus:'Haus',steuerung:'Steuerung'};
function renderAll(){
  if(!D||!META.length||!$('v-val').classList.contains('on')) return;
  const f=$('flt').value.toLowerCase(), base=D.basis_topic;
  let h='<tr><th>Gruppe</th><th style="text-align:left">Bezeichnung</th><th>Wert</th><th style="text-align:left">MQTT-Topic</th><th>Register</th></tr>';
  for(const m of META){
    const val=m.group==='geraet'?D.geraet[m.key]:D.werte[m.key];
    const txt=val==null?'–':(typeof val==='number'?nf(val,m.dec)+(m.unit?' '+m.unit:''):val);
    const line=(GRP[m.group]+' '+m.label+' '+m.topic+' '+txt).toLowerCase();
    if(f&&!line.includes(f)) continue;
    h+=`<tr><td class="t">${GRP[m.group]}</td><td class="t" style="color:var(--txt)">${m.label}</td><td>${txt}</td><td style="text-align:left" class="topic">${base}/${m.topic}</td><td>${m.reg??'berechnet'}</td></tr>`;
  }
  $('allTbl').innerHTML=h;
}
$('flt').oninput=renderAll;
document.querySelector('.tab[data-v="val"]').addEventListener('click',renderAll);

// ---------- Verlauf ----------
document.querySelectorAll('#rng button').forEach(b=>b.onclick=()=>{
  hours=+b.dataset.h; document.querySelectorAll('#rng button').forEach(x=>x.classList.toggle('on',x===b)); loadHist();});
async function loadHist(){ try{ const r=await fetch('api/history?h='+hours,{cache:'no-store'}); HIST=(await r.json()).punkte; drawChart(); }catch(e){} }
setInterval(loadHist,60000);
const SER=[{i:1,c:'#f5a524',n:'PV'},{i:2,c:'#2dd4bf',n:'Haus'},{i:3,c:'#a78bfa',n:'Akku'},{i:4,c:'#60a5fa',n:'Netz'}];
let geo=null;
function drawChart(){
  const cv=$('chart'), wrap=$('cw'); if(!wrap.offsetWidth) return;
  const dpr=window.devicePixelRatio||1, W=wrap.clientWidth, H=wrap.clientHeight;
  cv.width=W*dpr; cv.height=H*dpr; const c=cv.getContext('2d'); c.setTransform(dpr,0,0,dpr,0,0); c.clearRect(0,0,W,H);
  const L=52,R=40,T=12,B=26, pw_=W-L-R, ph=H-T-B;
  const now=Date.now()/1000, t0=now-hours*3600;
  let mn=0,mx=100;
  for(const p of HIST) for(const s of SER){const y=p[s.i]; if(y!=null){mn=Math.min(mn,y);mx=Math.max(mx,y);}}
  const step=niceStep((mx-mn)/5); mn=Math.floor(mn/step)*step; mx=Math.ceil(mx/step)*step; if(mx===mn) mx=mn+step;
  const X=t=>L+(t-t0)/(now-t0)*pw_, Y=v=>T+ph-(v-mn)/(mx-mn)*ph, Ys=v=>T+ph-v/100*ph;
  c.font='10px ui-monospace,Consolas,monospace'; c.textBaseline='middle';
  c.strokeStyle='#26313b'; c.fillStyle='#5d6b77'; c.lineWidth=1;
  for(let v=mn; v<=mx+1e-9; v+=step){const y=Math.round(Y(v))+.5; c.beginPath(); c.moveTo(L,y); c.lineTo(L+pw_,y); c.stroke();
    c.textAlign='right'; c.fillText(Math.abs(mx)>=2000||Math.abs(mn)>=2000? (v/1000).toLocaleString('de-DE',{maximumFractionDigits:1})+' kW' : v+' W',L-6,y);}
  if(mn<0){c.strokeStyle='#33414d'; const y=Math.round(Y(0))+.5; c.beginPath(); c.moveTo(L,y); c.lineTo(L+pw_,y); c.stroke();}
  c.textAlign='left'; c.fillStyle='#4ade80'; for(const v of [0,50,100]) c.fillText(v+'%',L+pw_+6,Ys(v));
  c.fillStyle='#5d6b77'; c.textAlign='center'; c.textBaseline='top';
  let tStep=21600; for(const st of [600,900,1800,3600,7200,10800,21600,43200]){ if(st/(now-t0)*pw_>=58){tStep=st;break;} }
  const tz=new Date().getTimezoneOffset()*60;
  for(let t=Math.ceil((t0-tz)/tStep)*tStep+tz; t<=now; t+=tStep){const x=X(t); if(x<L+18) continue;
    c.fillText(new Date(t*1000).toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'}),x,T+ph+7);
    c.strokeStyle='rgba(38,49,59,.5)'; c.beginPath(); c.moveTo(x+.5,T); c.lineTo(x+.5,T+ph); c.stroke();}
  const line=(idx,col,yf,dash)=>{c.strokeStyle=col; c.lineWidth=1.6; c.setLineDash(dash||[]); c.beginPath(); let on=false, lt=0;
    for(const p of HIST){const v=p[idx]; if(v==null||p[0]-lt>180){on=false;} if(v==null){lt=p[0];continue;}
      const x=X(p[0]+30), y=yf(v); if(on) c.lineTo(x,y); else {c.moveTo(x,y); on=true;} lt=p[0];}
    c.stroke(); c.setLineDash([]);};
  // PV als Fläche
  c.fillStyle='rgba(245,165,36,.10)'; c.beginPath(); let st=false;
  for(const p of HIST){ if(p[1]==null) continue; const x=X(p[0]+30); if(!st){c.moveTo(x,Y(0)); st=true;} c.lineTo(x,Y(p[1])); }
  if(st){ const lp=HIST.filter(p=>p[1]!=null).pop(); c.lineTo(X(lp[0]+30),Y(0)); c.closePath(); c.fill(); }
  for(const s of SER) line(s.i,s.c,Y);
  line(5,'#4ade80',Ys,[4,4]);
  if(!HIST.length){c.fillStyle='#5d6b77'; c.textAlign='center'; c.textBaseline='middle'; c.font='12px ui-monospace,monospace'; c.fillText('Noch keine Verlaufsdaten',L+pw_/2,T+ph/2);}
  geo={X,L,pw_,t0,now};
}
function niceStep(r){ if(r<=0) return 100; const e=Math.pow(10,Math.floor(Math.log10(r))); for(const m of [1,2,2.5,5,10]) if(r<=m*e) return m*e; return 10*e; }
$('cw').addEventListener('mousemove',ev=>{
  if(!geo||!HIST.length) return; const rect=$('cw').getBoundingClientRect(), x=ev.clientX-rect.left;
  const t=geo.t0+(x-geo.L)/geo.pw_*(geo.now-geo.t0); let best=null,bd=1e12;
  for(const p of HIST){const d=Math.abs(p[0]+30-t); if(d<bd){bd=d;best=p;}}
  const tip=$('tip'); if(!best||bd>600){tip.style.display='none';return;}
  tip.innerHTML=new Date(best[0]*1000).toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})+'<br>'+
    SER.map(s=>`<span style="color:${s.c}">${s.n}</span> ${pws(best[s.i])}`).join('<br>')+`<br><span style="color:#4ade80">SOC</span> ${best[5]==null?'–':nf(best[5],1)+' %'}`;
  tip.style.display='block'; tip.style.left=Math.min(x+14,rect.width-150)+'px'; tip.style.top='10px';
});
$('cw').addEventListener('mouseleave',()=>$('tip').style.display='none');
window.addEventListener('resize',drawChart);

// ---------- Einstellungen ----------
const FIELDS={wr:['host','port','unit_id','intervall_s','timeout_s','verbindungs_pause_s'],
  mq:['aktiv','host','port','benutzer','passwort','client_id','basis_topic','retain','nur_aenderungen','erzwingen_s','json_topic'],
  web:['port','titel'], st:['aktiv','pin','pin_loeschen','geraet_bestaetigen','einspeisung_erlaubt'], sy:['standby_verhindern']};
const SEC={wr:'wechselrichter',mq:'mqtt',web:'web',st:'steuerung',sy:'system'};
let CFG=null;
async function loadCfg(){
  const r=await fetch('api/config',{cache:'no-store'}); const j=await r.json(); CFG=j.config;
  for(const p in FIELDS) for(const k of FIELDS[p]){const el=$('c_'+p+'_'+k), val=CFG[SEC[p]][k];
    if(el.type==='checkbox') el.checked=!!val; else el.value=(k==='passwort'||k==='pin')?'':(val??'');}
  $('pinHint').textContent=CFG.steuerung.pin_gesetzt?'PIN ist gesetzt · leer lassen = unverändert':'noch keine PIN gesetzt';
  const er=j.erkannt||{};
  $('stDev').innerHTML=er.seriennummer?esc((er.modell||'?')+' · SN '+er.seriennummer)+(er.modell_ok?'':' <span class="badge err">nicht unterstützt</span>'):'nicht verbunden';
  $('stConf').innerHTML=CFG.steuerung.geraet_sn?esc((CFG.steuerung.geraet_modell||'')+' · SN '+CFG.steuerung.geraet_sn)+(er.seriennummer&&er.seriennummer!==CFG.steuerung.geraet_sn?' <span class="badge err">abweichend!</span>':''):'keine';
  $('c_st_geraet_bestaetigen').checked=false;
  $('stState').innerHTML=CFG.steuerung.aktiv?'<span class="badge warn">freigegeben</span>':'<span class="badge ok">gesperrt (nur lesen)</span>';
  $('cfgPath').textContent=j.datei; loadLog();
}
function collect(){
  const out={}; for(const p in FIELDS){out[SEC[p]]={}; for(const k of FIELDS[p]){const el=$('c_'+p+'_'+k);
    out[SEC[p]][k]=el.type==='checkbox'?el.checked:el.type==='number'?(el.value===''?null:Number(el.value)):el.value.trim();}}
  if(!out.mqtt.passwort) delete out.mqtt.passwort;
  if(!out.steuerung.pin) delete out.steuerung.pin;
  out.pin_aktuell=$('pinAktuell')?$('pinAktuell').value:''; return out;
}
function msg(id,t,cls){const e=$(id); e.textContent=t; e.className='msg '+(cls||'');}
$('btnSave').onclick=async()=>{
  msg('msgSave','speichere …');
  try{const r=await fetch('api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(collect())});
    const j=await r.json(); if(!j.ok){msg('msgSave',j.fehler||'Fehler','err');return;}
    msg('msgSave','Gespeichert.','ok'); $('pinAktuell').value='';
    if(j.neuer_port && j.neuer_port!=location.port){ msg('msgSave','Gespeichert – wechsle auf Port '+j.neuer_port+' …','ok');
      setTimeout(()=>{location.href=location.protocol+'//'+location.hostname+':'+j.neuer_port+'/#set';},1500); }
    else loadCfg();
  }catch(e){msg('msgSave','Fehler: '+e,'err');}
};
$('btnTestWr').onclick=async()=>{
  msg('msgWr','teste … (kann je Unit-ID einige Sekunden dauern)');
  const c=collect().wechselrichter;
  try{const r=await fetch('api/test_wr',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(c)}); const j=await r.json();
    if(j.ok){ msg('msgWr',`OK – ${j.modell||'?'} · SN ${j.seriennummer||'?'} · Unit-ID ${j.unit_id}`,'ok');
      if(String(j.unit_id)!==$('c_wr_unit_id').value){$('c_wr_unit_id').value=j.unit_id; msg('msgWr',$('msgWr').textContent+' (Unit-ID übernommen – bitte speichern)','ok');}}
    else msg('msgWr','Fehlgeschlagen: '+j.versuche.map(x=>'ID '+x.unit_id+': '+x.fehler).join(' | '),'err');
  }catch(e){msg('msgWr','Fehler: '+e,'err');}
};
$('btnTestMq').onclick=async()=>{
  msg('msgMq','teste …'); const c=collect().mqtt;
  try{const r=await fetch('api/test_mqtt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(c)}); const j=await r.json();
    msg('msgMq',j.ok?'Verbindung zum Broker OK':'Fehlgeschlagen: '+j.fehler,j.ok?'ok':'err');}catch(e){msg('msgMq','Fehler: '+e,'err');}
};
async function loadLog(){ try{const r=await fetch('api/log',{cache:'no-store'}); const j=await r.json(); const el=$('log');
  el.textContent=j.zeilen.join('\n')||'—'; el.scrollTop=el.scrollHeight;}catch(e){} }
setInterval(()=>{ if($('v-set').classList.contains('on')) loadLog(); },5000);

// ---------- Start ----------
fetch('api/meta').then(r=>r.json()).then(j=>{META=j.werte; renderAll();});
poll(); loadHist();
</script>
</body>
</html>
"""
