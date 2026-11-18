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
@media (max-width:600px){
  .top{padding:10px 12px}.brand h1{font-size:12px;letter-spacing:.12em}
  main{padding:12px 10px 30px}
  .kpis{grid-template-columns:1fr 1fr;gap:10px}
  .kpi .v{font-size:21px}
  .tabs{width:100%}.tab{flex:1;padding:8px 4px}
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
      <div class="pb"><dl class="kv" id="wrKv"></dl><table class="tbl" id="wrPh" style="margin-top:12px"></table></div></div>
    <div class="panel"><div class="ph"><b>Netz / Zähler</b><span class="r" id="netzBadge"></span></div>
      <div class="pb"><dl class="kv" id="netzKv"></dl><table class="tbl" id="netzPh" style="margin-top:12px"></table>
      <div class="empty" id="netzNone" style="display:none">Kein Smart Meter erkannt – Netz- und Hausverbrauchswerte stehen nicht zur Verfügung.</div></div></div>
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
        <div class="f"><label>Timeout (s)</label><input type="number" id="c_wr_timeout_s" step="0.5" min="1"></div>
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
  location.hash=b.dataset.v;
});
if(location.hash){const t=document.querySelector('.tab[data-v="'+location.hash.slice(1)+'"]'); if(t) t.click();}

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
  showBanner(wr.verbunden?'':('Wechselrichter: '+(wr.fehler||'nicht verbunden')));
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
  renderAll();
}
function setFlow(id,on,rev){const e=$(id); e.classList.toggle('on',!!on); e.classList.toggle('rev',!!rev);}

// ---------- Werte-Tabelle ----------
const GRP={geraet:'Gerät',pv:'PV',wr:'Wechselrichter',akku:'Akku',netz:'Netz',haus:'Haus'};
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
  web:['port','titel']};
const SEC={wr:'wechselrichter',mq:'mqtt',web:'web'};
let CFG=null;
async function loadCfg(){
  const r=await fetch('api/config',{cache:'no-store'}); const j=await r.json(); CFG=j.config;
  for(const p in FIELDS) for(const k of FIELDS[p]){const el=$('c_'+p+'_'+k), val=CFG[SEC[p]][k];
    if(el.type==='checkbox') el.checked=!!val; else el.value=(k==='passwort')?'':(val??'');}
  $('cfgPath').textContent=j.datei; loadLog();
}
function collect(){
  const out={}; for(const p in FIELDS){out[SEC[p]]={}; for(const k of FIELDS[p]){const el=$('c_'+p+'_'+k);
    out[SEC[p]][k]=el.type==='checkbox'?el.checked:el.type==='number'?(el.value===''?null:Number(el.value)):el.value.trim();}}
  if(!out.mqtt.passwort) delete out.mqtt.passwort; return out;
}
function msg(id,t,cls){const e=$(id); e.textContent=t; e.className='msg '+(cls||'');}
$('btnSave').onclick=async()=>{
  msg('msgSave','speichere …');
  try{const r=await fetch('api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(collect())});
    const j=await r.json(); if(!j.ok){msg('msgSave',j.fehler||'Fehler','err');return;}
    msg('msgSave','Gespeichert.','ok');
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
