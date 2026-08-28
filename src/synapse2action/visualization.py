from __future__ import annotations

import json
from html import escape
from typing import Any


def render_demo_html(report: dict[str, Any]) -> str:
    data = json.dumps(report, ensure_ascii=False).replace("</", "<\\/")
    status = "EXPECTED OUTCOME" if report["passed"] else "UNEXPECTED OUTCOME"
    object_id = escape(report["world_object"]["object_id"])
    object_color = escape(report["visual"]["object_color"])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Synapse2Action · Hardware-free Demo</title>
  <style>
    :root {{ --primary:#1e3a5f; --secondary:#2563eb; --accent:#a16207; --bg:#f8fafc; --ink:#0f172a; --muted:#e9eef5; --line:#cbd5e1; --ok:#166534; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--bg); font:16px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }}
    .skip {{ position:absolute; left:16px; top:-80px; z-index:10; padding:12px 16px; color:#fff; background:var(--primary); border-radius:8px; }}
    .skip:focus {{ top:16px; }}
    main {{ width:min(1120px,calc(100% - 32px)); margin:0 auto; padding:32px 0 48px; }}
    header {{ display:flex; justify-content:space-between; gap:24px; align-items:flex-start; margin-bottom:24px; }}
    h1 {{ margin:0; font-size:clamp(1.75rem,4vw,3rem); letter-spacing:-.04em; }}
    .eyebrow,.mono {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
    .eyebrow {{ color:var(--secondary); font-weight:700; letter-spacing:.12em; text-transform:uppercase; }}
    .status {{ padding:8px 12px; border:1px solid #86efac; border-radius:999px; color:var(--ok); background:#f0fdf4; font-weight:800; }}
    .layout {{ display:grid; grid-template-columns:minmax(0,1.5fr) minmax(280px,.8fr); gap:20px; }}
    .card {{ border:1px solid var(--line); border-radius:16px; background:#fff; box-shadow:0 12px 32px rgba(15,23,42,.07); }}
    .stage {{ padding:20px; }}
    .stage-head,.controls {{ display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }}
    h2 {{ margin:0; font-size:1.05rem; }}
    svg {{ width:100%; height:auto; min-height:380px; margin-top:16px; border-radius:12px; background:#eef4f8; }}
    .controls {{ margin-top:16px; }}
    button {{ min-width:44px; min-height:44px; padding:10px 14px; border:1px solid var(--line); border-radius:10px; color:var(--ink); background:#fff; cursor:pointer; touch-action:manipulation; font-weight:700; transition:background .2s ease,border-color .2s ease,transform .2s ease; }}
    button:hover {{ background:var(--muted); border-color:var(--primary); }}
    button:active {{ transform:translateY(1px); }}
    button:disabled {{ cursor:not-allowed; opacity:.45; }}
    button:focus-visible,input:focus-visible {{ outline:3px solid rgba(37,99,235,.35); outline-offset:2px; }}
    input[type=range] {{ flex:1; min-width:180px; accent-color:var(--secondary); }}
    aside {{ display:grid; gap:20px; align-content:start; }}
    .panel {{ padding:18px; }}
    dl {{ display:grid; grid-template-columns:1fr auto; gap:10px 16px; margin:16px 0 0; }}
    dt {{ color:#475569; }} dd {{ margin:0; font-weight:800; }}
    .pipeline {{ list-style:none; margin:16px 0 0; padding:0; display:grid; gap:8px; }}
    .pipeline li {{ display:flex; align-items:center; gap:10px; padding:9px 10px; border-radius:9px; background:var(--muted); }}
    .pipeline li::before {{ content:""; width:8px; height:8px; border-radius:50%; background:var(--secondary); }}
    .step-label {{ color:#334155; }}
    .legend {{ display:flex; gap:16px; flex-wrap:wrap; margin-top:12px; color:#475569; font-size:.875rem; }}
    .swatch {{ display:inline-block; width:12px; height:12px; margin-right:6px; border-radius:3px; vertical-align:-1px; }}
    #object,#gripper {{ transition:transform .25s ease-out; }}
    @media (max-width:780px) {{ header {{ display:block; }} .status {{ display:inline-block; margin-top:12px; }} .layout {{ grid-template-columns:1fr; }} svg {{ min-height:280px; }} }}
    @media (prefers-reduced-motion:reduce) {{ *,*::before,*::after {{ scroll-behavior:auto!important; transition:none!important; animation:none!important; }} }}
  </style>
</head>
<body>
<a class="skip" href="#main">跳到主要内容</a>
<main id="main">
  <header>
    <div><div class="eyebrow">Hardware-free experiment</div><h1>Synapse2Action / 念动</h1><p>从模拟神经意图到可验证的桌面抓取放置。</p></div>
    <div class="status" aria-label="Demo status">{escape(status)}</div>
  </header>
  <div class="layout">
    <section class="card stage" aria-labelledby="world-title">
      <div class="stage-head"><h2 id="world-title">二维桌面世界</h2><span id="frameText" class="mono" aria-live="polite"></span></div>
      <svg viewBox="0 0 900 520" role="img" aria-labelledby="sceneTitle sceneDesc">
        <title id="sceneTitle">机器人抓取放置逐帧演示</title><desc id="sceneDesc">红色方块从起点被机械夹爪移动到右侧目标区域。</desc>
        <rect x="28" y="28" width="844" height="464" rx="20" fill="#fff" stroke="#cbd5e1" stroke-width="3"/>
        <rect x="650" y="300" width="150" height="120" rx="16" fill="#dbeafe" stroke="#2563eb" stroke-width="4" stroke-dasharray="12 8"/>
        <text x="725" y="448" text-anchor="middle" fill="#1e3a5f" font-weight="700">DROP ZONE</text>
        <g id="object"><rect x="-24" y="-24" width="48" height="48" rx="8" fill="{object_color}"/><text x="0" y="48" text-anchor="middle" fill="#0f172a" font-weight="700">{object_id}</text></g>
        <g id="gripper" fill="none" stroke="#0f172a" stroke-width="8" stroke-linecap="round"><path d="M-18 -22 L-18 12 L-32 28"/><path d="M18 -22 L18 12 L32 28"/><path d="M0 -55 L0 -22"/></g>
      </svg>
      <div class="legend"><span><i class="swatch" style="background:{object_color}"></i>目标物体</span><span><i class="swatch" style="background:#dbeafe;border:1px solid #2563eb"></i>放置区域</span></div>
      <div class="controls">
        <button id="prev" type="button" aria-label="上一帧">← 上一帧</button>
        <button id="play" type="button" aria-label="播放轨迹">播放</button>
        <button id="next" type="button" aria-label="下一帧">下一帧 →</button>
        <input id="timeline" type="range" min="0" value="0" aria-label="轨迹帧">
      </div>
    </section>
    <aside>
      <section class="card panel"><h2>运行结果</h2><dl><dt>预期状态</dt><dd>{escape(report['expected_final_state'])}</dd><dt>最终状态</dt><dd>{escape(report['final_state'])}</dd><dt>规划动作</dt><dd>{report['planned_actions']}</dd><dt>机器人动作</dt><dd>{report['robot_actions']}</dd><dt>轨迹帧</dt><dd>{len(report['tabletop_frames'])}</dd></dl></section>
      <section class="card panel"><h2>完整管线</h2><ol class="pipeline">{''.join(f'<li>{escape(stage)}</li>' for stage in report['pipeline'])}</ol></section>
      <section class="card panel"><h2>当前帧</h2><p id="frameDetail" class="step-label" aria-live="polite"></p></section>
    </aside>
  </div>
</main>
<script type="application/json" id="demoData">{data}</script>
<script>
  const report=JSON.parse(document.getElementById('demoData').textContent), frames=report.tabletop_frames;
  const object=document.getElementById('object'),gripper=document.getElementById('gripper'),timeline=document.getElementById('timeline');
  const frameText=document.getElementById('frameText'),detail=document.getElementById('frameDetail'),play=document.getElementById('play');
  let index=0,timer=null; timeline.max=frames.length-1;
  const map=p=>({{x:70+p.x*800,y:450-p.y*600}});
  const prev=document.getElementById('prev'),next=document.getElementById('next');
  function render(i){{index=Math.max(0,Math.min(frames.length-1,i));const f=frames[index],o=map(f.object_position),g=map(f.gripper);object.setAttribute('transform',`translate(${{o.x}} ${{o.y}})`);gripper.setAttribute('transform',`translate(${{g.x}} ${{g.y-42}})`);timeline.value=index;prev.disabled=index===0;next.disabled=index===frames.length-1;frameText.textContent=`FRAME ${{index+1}} / ${{frames.length}}`;detail.textContent=`${{f.step}} · object (${{f.object_position.x.toFixed(2)}}, ${{f.object_position.y.toFixed(2)}}) · ${{f.object_held?'已抓取':'未抓取'}}`;}}
  function stop(){{if(timer)clearInterval(timer);timer=null;play.textContent='播放';play.setAttribute('aria-label','播放轨迹');}}
  prev.onclick=()=>{{stop();render(index-1)}};next.onclick=()=>{{stop();render(index+1)}};
  timeline.oninput=e=>{{stop();render(Number(e.target.value))}};
  play.onclick=()=>{{if(timer){{stop();return}};if(index===frames.length-1)render(0);play.textContent='暂停';play.setAttribute('aria-label','暂停轨迹');timer=setInterval(()=>{{if(index===frames.length-1){{stop();return}}render(index+1)}},700)}};
  render(0);
</script>
</body>
</html>"""


def render_g1_dashboard_html(dashboard: dict[str, Any]) -> str:
    data = json.dumps(dashboard, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Synapse2Action · Simulation Console</title>
  <style>
    :root {{ color-scheme:dark; --bg:#020617; --surface:#0f172a; --surface-2:#111c30; --line:#334155; --ink:#f8fafc; --muted:#94a3b8; --green:#4ade80; --cyan:#22d3ee; --amber:#fbbf24; --red:#f87171; --blue:#60a5fa; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; min-width:320px; background:radial-gradient(circle at 75% 0,#0c2941 0,transparent 32rem),var(--bg); color:var(--ink); font:16px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }}
    button {{ font:inherit; }}
    .skip {{ position:fixed; top:-80px; left:16px; z-index:20; padding:12px 16px; border-radius:8px; background:var(--green); color:#052e16; font-weight:800; }}
    .skip:focus {{ top:16px; }}
    main {{ width:min(1500px,calc(100% - 32px)); margin:auto; padding:24px 0 48px; }}
    header {{ display:flex; align-items:flex-start; justify-content:space-between; gap:24px; margin-bottom:20px; }}
    .kicker,.mono {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
    .kicker {{ color:var(--cyan); font-size:.75rem; font-weight:700; letter-spacing:.15em; text-transform:uppercase; }}
    h1 {{ margin:4px 0 6px; font-size:clamp(1.8rem,4vw,3.2rem); line-height:1.05; letter-spacing:-.045em; }}
    h2,h3,p {{ margin-top:0; }}
    .subtitle {{ max-width:760px; margin-bottom:0; color:var(--muted); }}
    .badge {{ display:flex; align-items:center; gap:9px; min-height:44px; padding:9px 14px; border:1px solid #166534; border-radius:999px; background:#052e16; color:#bbf7d0; font-weight:800; white-space:nowrap; }}
    .dot {{ width:9px; height:9px; border-radius:50%; background:currentColor; box-shadow:0 0 16px currentColor; }}
    .metrics {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-bottom:12px; }}
    .metric,.card {{ border:1px solid var(--line); border-radius:14px; background:linear-gradient(145deg,rgba(15,23,42,.96),rgba(8,16,31,.96)); box-shadow:0 12px 32px rgba(0,0,0,.18); }}
    .metric {{ padding:14px 16px; }}
    .metric small {{ display:block; color:var(--muted); font-size:.72rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }}
    .metric strong {{ display:block; margin-top:4px; font:700 clamp(1.2rem,3vw,1.8rem)/1.1 ui-monospace,SFMono-Regular,Menlo,monospace; }}
    .ok {{ color:var(--green); }} .warn {{ color:var(--amber); }}
    .grid {{ display:grid; grid-template-columns:minmax(0,1.55fr) minmax(330px,.8fr); gap:12px; }}
    .stack {{ display:grid; gap:12px; align-content:start; }}
    .card {{ padding:16px; overflow:hidden; }}
    .card-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }}
    .card h2 {{ margin:0; font-size:.86rem; letter-spacing:.07em; text-transform:uppercase; }}
    .camera {{ position:relative; aspect-ratio:16/9; overflow:hidden; border:1px solid var(--line); border-radius:10px; background:#050a14; }}
    .camera img {{ display:block; width:100%; height:100%; object-fit:cover; }}
    .camera-label {{ position:absolute; left:12px; bottom:12px; padding:5px 9px; border:1px solid rgba(148,163,184,.45); border-radius:6px; background:rgba(2,6,23,.78); font:700 .75rem ui-monospace,SFMono-Regular,Menlo,monospace; backdrop-filter:blur(8px); }}
    .thumbs {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:8px; margin-top:10px; }}
    .thumb {{ min-height:56px; padding:0; overflow:hidden; border:1px solid var(--line); border-radius:8px; background:var(--surface); color:var(--ink); cursor:pointer; transition:border-color .2s ease,background .2s ease; }}
    .thumb:hover,.thumb[aria-current=true] {{ border-color:var(--cyan); background:#083344; }}
    .thumb:focus-visible,.control:focus-visible {{ outline:3px solid rgba(34,211,238,.45); outline-offset:2px; }}
    .thumb img {{ display:block; width:100%; aspect-ratio:16/7; object-fit:cover; }}
    .thumb span {{ display:block; padding:5px; font:600 .68rem ui-monospace,SFMono-Regular,Menlo,monospace; text-transform:uppercase; }}
    .controls {{ display:flex; gap:8px; margin-top:10px; }}
    .control {{ min-width:44px; min-height:44px; padding:8px 14px; border:1px solid var(--line); border-radius:8px; background:#172033; color:var(--ink); cursor:pointer; font-weight:750; transition:background .2s ease,border-color .2s ease; }}
    .control:hover {{ background:#1e293b; border-color:var(--cyan); }}
    .pipeline {{ display:grid; grid-template-columns:repeat(8,minmax(82px,1fr)); gap:7px; overflow-x:auto; padding:2px 1px 8px; }}
    .pipe-step {{ min-height:70px; padding:9px; border:1px solid var(--line); border-radius:9px; background:#111827; color:var(--muted); cursor:pointer; text-align:left; }}
    .pipe-step b {{ display:block; margin-top:4px; color:var(--ink); font-size:.75rem; }}
    .pipe-step.active {{ border-color:var(--green); background:#052e16; color:#86efac; }}
    .detail {{ min-height:42px; margin:10px 0 0; color:var(--muted); }}
    .bar-row {{ display:grid; grid-template-columns:74px 1fr 62px; gap:10px; align-items:center; margin:10px 0; }}
    .bar-track {{ height:8px; overflow:hidden; border-radius:999px; background:#1e293b; }}
    .bar-fill {{ height:100%; border-radius:inherit; background:linear-gradient(90deg,var(--blue),var(--cyan)); }}
    .bar-row output {{ color:var(--ink); text-align:right; font:600 .75rem ui-monospace,SFMono-Regular,Menlo,monospace; }}
    .latency {{ position:relative; height:16px; margin:18px 0 8px; border-radius:999px; background:#1e293b; }}
    .latency-fill {{ height:100%; border-radius:inherit; background:linear-gradient(90deg,var(--green),var(--amber)); }}
    .latency-mark {{ position:absolute; top:-6px; bottom:-6px; width:2px; background:var(--cyan); }}
    .latency-labels,.facts {{ display:flex; justify-content:space-between; gap:12px; color:var(--muted); font-size:.75rem; }}
    .topology {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }}
    .node {{ position:relative; min-height:76px; padding:10px; border:1px solid var(--line); border-radius:9px; background:#0b1324; }}
    .node:not(:last-child)::after {{ content:""; position:absolute; top:50%; right:-9px; width:9px; border-top:1px solid var(--cyan); }}
    .node b {{ display:block; font-size:.78rem; }} .node small {{ color:var(--muted); }}
    .facts {{ display:grid; grid-template-columns:1fr 1fr; }}
    .fact {{ padding:9px; border-radius:8px; background:#0b1324; }} .fact b {{ display:block; color:var(--ink); font-size:.9rem; }}
    footer {{ margin-top:12px; color:var(--muted); font-size:.75rem; }}
    @media (max-width:1000px) {{ .grid {{ grid-template-columns:1fr; }} .metrics {{ grid-template-columns:1fr 1fr; }} }}
    @media (max-width:600px) {{ main {{ width:min(100% - 20px,1500px); padding-top:14px; }} header {{ display:block; }} .badge {{ width:max-content; margin-top:14px; }} .metrics {{ grid-template-columns:1fr 1fr; }} .thumbs {{ grid-template-columns:repeat(3,1fr); }} .topology {{ grid-template-columns:1fr; }} .node:not(:last-child)::after {{ display:none; }} }}
    @media (prefers-reduced-motion:reduce) {{ *,*::before,*::after {{ scroll-behavior:auto!important; transition:none!important; animation:none!important; }} }}
  </style>
</head>
<body>
<a class="skip" href="#main">跳到主要内容</a>
<main id="main">
  <header><div><div class="kicker">Hardware-free · Evidence Console</div><h1>Synapse2Action 仿真实验台</h1><p class="subtitle">EEG 意图、Harness 状态、SmolVLA 授权窗口、Unitree 行为层与 MuJoCo 物理结果的统一可视化。</p></div><div class="badge"><span class="dot"></span><span id="runStatus">ACCEPTED</span></div></header>
  <section class="metrics" aria-label="关键指标">
    <div class="metric"><small>Harness state</small><strong id="stateMetric" class="ok">COMPLETED</strong></div>
    <div class="metric"><small>VLA max RTT</small><strong id="latencyMetric">—</strong></div>
    <div class="metric"><small>Chunk coverage</small><strong id="coverageMetric">—</strong></div>
    <div class="metric"><small>Stale fallback</small><strong id="staleMetric" class="ok">0</strong></div>
  </section>
  <div class="grid">
    <div class="stack">
      <section class="card" aria-labelledby="cameraTitle"><div class="card-head"><h2 id="cameraTitle">MuJoCo Camera 01</h2><span class="mono" id="frameCounter"></span></div><div class="camera"><img id="mainFrame" alt="MuJoCo G1 仿真关键帧"><span class="camera-label" id="frameStage"></span></div><div class="thumbs" id="thumbnails"></div><div class="controls"><button class="control" id="previous" type="button">上一帧</button><button class="control" id="play" type="button">播放</button><button class="control" id="next" type="button">下一帧</button></div></section>
      <section class="card" aria-labelledby="pipelineTitle"><div class="card-head"><h2 id="pipelineTitle">Harness event trace</h2><span class="mono" id="traceStatus"></span></div><div class="pipeline" id="pipeline"></div><p class="detail" id="traceDetail" aria-live="polite"></p></section>
      <section class="card"><div class="card-head"><h2>Control ownership</h2><span class="mono ok">GENERATIVE OVERLAY = 0</span></div><div class="topology"><div class="node"><b>SmolVLA · 3Hz</b><small>typed-skill authorization</small></div><div class="node"><b>C++ Behavior</b><small>validated manipulation targets</small></div><div class="node"><b>SDK2 + RL</b><small>balance and low-level control</small></div></div></section>
    </div>
    <aside class="stack">
      <section class="card"><div class="card-head"><h2>EEG decoded intents</h2><span class="mono">BrainFlow / LSL</span></div><div id="intentBars"></div></section>
      <section class="card"><div class="card-head"><h2>VLA realtime budget</h2><span class="mono" id="chunkCount"></span></div><div class="latency"><div class="latency-fill" id="latencyFill"></div><div class="latency-mark" id="coverageMark"></div></div><div class="latency-labels"><span>0 ms</span><span id="latencyText"></span><span id="coverageText"></span></div></section>
      <section class="card"><div class="card-head"><h2>Physical outcome</h2><span class="mono ok">INDEPENDENTLY VERIFIED</span></div><div class="facts" id="facts"></div></section>
      <section class="card"><div class="card-head"><h2>Held-out model quality</h2><span class="mono">SEED 0</span></div><div class="facts"><div class="fact"><small>Overall MSE</small><b id="mse"></b></div><div class="fact"><small>Waist / arm MSE</small><b id="armMse"></b></div><div class="fact"><small>Frames</small><b id="evalFrames"></b></div><div class="fact"><small>Finite</small><b id="finite"></b></div></div></section>
    </aside>
  </div>
  <footer>本页面由本地验收报告生成，不访问网络，不代表真实 EEG 或 G1 硬件性能。</footer>
</main>
<script type="application/json" id="dashboardData">{data}</script>
<script>
const d=JSON.parse(document.getElementById('dashboardData').textContent), q=s=>document.querySelector(s);
const runtime=d.acceptance.runtime, sim=d.simulator, frames=d.frames, trace=d.harness.trace;
q('#runStatus').textContent=d.harness.accepted?'ACCEPTED':'REJECTED'; q('#stateMetric').textContent=d.harness.final_state.toUpperCase();
q('#latencyMetric').textContent=(runtime.maximum_round_trip_ms/1000).toFixed(2)+'s'; q('#coverageMetric').textContent=(runtime.minimum_chunk_coverage_ms/1000).toFixed(2)+'s'; q('#staleMetric').textContent=runtime.stale_fallbacks;
q('#chunkCount').textContent=runtime.chunks_received+' CHUNKS'; const scale=Math.max(runtime.maximum_round_trip_ms,runtime.minimum_chunk_coverage_ms)*1.1;
q('#latencyFill').style.width=(runtime.maximum_round_trip_ms/scale*100)+'%'; q('#coverageMark').style.left=(runtime.minimum_chunk_coverage_ms/scale*100)+'%'; q('#latencyText').textContent='RTT '+Math.round(runtime.maximum_round_trip_ms)+' ms'; q('#coverageText').textContent='budget '+Math.round(runtime.minimum_chunk_coverage_ms)+' ms';
const intents=d.eeg.harness_replay.decoded_examples; q('#intentBars').innerHTML=Object.entries(intents).map(([name,x])=>`<div class="bar-row"><span>${{name}}</span><div class="bar-track"><div class="bar-fill" style="width:${{(x.confidence*100).toFixed(1)}}%"></div></div><output>${{(x.confidence*100).toFixed(1)}}%</output></div>`).join('');
const facts=[['standing',sim.fell_at_seconds===null],['grasped',sim.grasped],['lifted',sim.maximum_object_height_m-sim.initial_object_position_xyz_m[2]>=.1],['released',sim.released],['in drop zone',sim.final_object_center_in_drop_zone],['VLA authorized',sim.vla_authorized_frames>0]];
q('#facts').innerHTML=facts.map(([name,ok])=>`<div class="fact"><small>${{name}}</small><b class="${{ok?'ok':'warn'}}">${{ok?'PASS':'FAIL'}}</b></div>`).join('');
q('#mse').textContent=d.training.mse.toFixed(6); q('#armMse').textContent=d.training.arm_waist_mse.toFixed(6); q('#evalFrames').textContent=d.training.frames; q('#finite').textContent=d.training.finite?'PASS':'FAIL';
let frameIndex=0,traceIndex=trace.length-1,timer=null; const stageName=s=>({{ready:'READY',grasp:'GRASP',lift:'LIFT',release:'RELEASE',final:'FINAL'}}[s]||s.toUpperCase());
function renderFrame(i){{frameIndex=Math.max(0,Math.min(frames.length-1,i));const f=frames[frameIndex];q('#mainFrame').src=f.data;q('#mainFrame').alt='MuJoCo G1 '+stageName(f.stage)+' 关键帧';q('#frameStage').textContent=stageName(f.stage);q('#frameCounter').textContent=`${{frameIndex+1}} / ${{frames.length}}`;document.querySelectorAll('.thumb').forEach((x,n)=>x.setAttribute('aria-current',n===frameIndex));}}
q('#thumbnails').innerHTML=frames.map((f,i)=>`<button class="thumb" type="button" data-index="${{i}}"><img src="${{f.data}}" alt=""><span>${{stageName(f.stage)}}</span></button>`).join('');document.querySelectorAll('.thumb').forEach(x=>x.onclick=()=>{{stop();renderFrame(Number(x.dataset.index))}});
function stop(){{if(timer)clearInterval(timer);timer=null;q('#play').textContent='播放';}} q('#previous').onclick=()=>{{stop();renderFrame(frameIndex-1)}};q('#next').onclick=()=>{{stop();renderFrame(frameIndex+1)}};q('#play').onclick=()=>{{if(timer){{stop();return}};if(frameIndex===frames.length-1)renderFrame(0);q('#play').textContent='暂停';timer=setInterval(()=>frameIndex===frames.length-1?stop():renderFrame(frameIndex+1),900)}};
q('#pipeline').innerHTML=trace.map((x,i)=>`<button class="pipe-step" type="button" data-index="${{i}}"><span class="mono">${{String(i+1).padStart(2,'0')}}</span><b>${{x.event}}</b></button>`).join('');
function renderTrace(i){{traceIndex=i;const x=trace[i];document.querySelectorAll('.pipe-step').forEach((n,j)=>n.classList.toggle('active',j<=i));q('#traceStatus').textContent=x.state.toUpperCase();q('#traceDetail').textContent=`${{x.event}} · ${{x.detail||'—'}} · state=${{x.state}}`;}} document.querySelectorAll('.pipe-step').forEach(x=>x.onclick=()=>renderTrace(Number(x.dataset.index)));
renderFrame(0);renderTrace(traceIndex);
</script>
</body></html>"""
