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
    .badge.rejected {{ border-color:#991b1b; background:#450a0a; color:#fecaca; }}
    .header-actions {{ display:flex; align-items:center; gap:8px; }}
    .language {{ min-width:44px; min-height:44px; padding:8px 12px; border:1px solid var(--line); border-radius:9px; background:var(--surface); color:var(--ink); cursor:pointer; font-weight:800; }}
    .language:hover {{ border-color:var(--cyan); }}
    .dot {{ width:9px; height:9px; border-radius:50%; background:currentColor; box-shadow:0 0 16px currentColor; }}
    .metrics {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-bottom:12px; }}
    .metric,.card {{ border:1px solid var(--line); border-radius:14px; background:linear-gradient(145deg,rgba(15,23,42,.96),rgba(8,16,31,.96)); box-shadow:0 12px 32px rgba(0,0,0,.18); }}
    .metric {{ padding:14px 16px; }}
    .metric small {{ display:block; color:var(--muted); font-size:.72rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }}
    .metric strong {{ display:block; margin-top:4px; font:700 clamp(1.2rem,3vw,1.8rem)/1.1 ui-monospace,SFMono-Regular,Menlo,monospace; }}
    .overview {{ display:grid; grid-template-columns:minmax(0,1.4fr) minmax(300px,.8fr); gap:12px; margin-bottom:12px; }}
    .verdict {{ padding:22px; border-color:#166534; background:linear-gradient(135deg,#052e16,#0b1324 62%); }}
    .verdict.rejected {{ border-color:#991b1b; background:linear-gradient(135deg,#450a0a,#0b1324 62%); }}
    .verdict h2 {{ margin:4px 0 10px; font-size:clamp(1.35rem,3vw,2.15rem); letter-spacing:-.025em; text-transform:none; }}
    .verdict p {{ max-width:74ch; margin:0; color:#cbd5e1; }}
    .snapshot {{ margin-top:14px!important; color:var(--muted)!important; font-size:.75rem; }}
    .truth {{ display:grid; gap:8px; padding:16px; }} .truth-row {{ display:grid; grid-template-columns:104px 1fr; gap:10px; align-items:start; padding:8px; border-radius:8px; background:#0b1324; font-size:.78rem; }}
    .truth-row b {{ color:var(--muted); }} .limitation {{ border:1px solid #92400e; background:#271706; }}
    .stage-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }}
    .stage-card {{ min-height:196px; padding:14px; border:1px solid var(--line); border-radius:10px; background:#0b1324; }}
    .stage-card header {{ display:flex; align-items:flex-start; justify-content:space-between; gap:8px; margin:0 0 12px; }}
    .stage-card h3 {{ margin:0; font-size:.78rem; line-height:1.3; }}
    .stage-card dl {{ margin:0; }} .stage-card dt {{ margin-top:8px; color:var(--muted); font-size:.65rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }}
    .stage-card dd {{ margin:2px 0 0; overflow-wrap:anywhere; font-size:.72rem; }}
    .stage-card .explain {{ min-height:48px; margin:0 0 10px; color:#cbd5e1; font-size:.82rem; }}
    .stage-card details {{ margin-top:12px; border-top:1px solid var(--line); padding-top:8px; }}
    details summary {{ min-height:44px; display:flex; align-items:center; color:var(--cyan); cursor:pointer; font-weight:700; }}
    .advanced {{ margin-bottom:12px; border:1px solid var(--line); border-radius:12px; background:rgba(15,23,42,.65); }}
    .advanced > summary {{ padding:10px 16px; }} .advanced .metrics {{ padding:0 12px 12px; margin:0; }}
    .provenance {{ padding:3px 6px; border:1px solid var(--line); border-radius:5px; color:var(--muted); font:800 .6rem ui-monospace,SFMono-Regular,Menlo,monospace; white-space:nowrap; }}
    .provenance.live,.provenance.real_sdk,.provenance.measured {{ border-color:#166534; color:var(--green); }} .provenance.mock,.provenance.synthetic,.provenance.scripted {{ border-color:#92400e; color:var(--amber); }}
    .ok {{ color:var(--green); }} .warn {{ color:var(--amber); }}
    .grid {{ display:grid; grid-template-columns:minmax(0,1.55fr) minmax(330px,.8fr); gap:12px; }}
    .stack {{ display:grid; gap:12px; align-content:start; }}
    .card {{ padding:16px; overflow:hidden; }}
    .card-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }}
    .card h2 {{ margin:0; font-size:.86rem; letter-spacing:.07em; text-transform:uppercase; }}
    .camera {{ position:relative; aspect-ratio:16/9; overflow:hidden; border:1px solid var(--line); border-radius:10px; background:#050a14; }}
    .camera img {{ display:block; width:100%; height:100%; object-fit:cover; }}
    .camera-empty {{ position:absolute; inset:0; display:grid; place-items:center; padding:24px; color:var(--muted); text-align:center; }}
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
    @media (max-width:1000px) {{ .grid,.overview {{ grid-template-columns:1fr; }} .metrics {{ grid-template-columns:1fr 1fr; }} .stage-grid {{ grid-template-columns:1fr 1fr; }} }}
    @media (max-width:600px) {{ main {{ width:min(100% - 20px,1500px); padding-top:14px; }} header {{ display:block; }} .header-actions {{ margin-top:14px; }} .metrics,.stage-grid {{ grid-template-columns:1fr; }} .thumbs {{ grid-template-columns:repeat(3,1fr); }} .topology {{ grid-template-columns:1fr; }} .node:not(:last-child)::after {{ display:none; }} .truth-row {{ grid-template-columns:1fr; }} }}
    @media (prefers-reduced-motion:reduce) {{ *,*::before,*::after {{ scroll-behavior:auto!important; transition:none!important; animation:none!important; }} }}
  </style>
</head>
<body>
<a class="skip" href="#main" data-i18n="skip">跳到主要内容</a>
<main id="main">
  <header><div><div class="kicker">Hardware-free · Evidence Console</div><h1 data-i18n="title">Synapse2Action 仿真实验台</h1><p class="subtitle" data-i18n="subtitle">EEG 意图、Harness 状态、SmolVLA 授权窗口、Unitree 行为层与 MuJoCo 物理结果的统一可视化。</p></div><div class="header-actions"><button class="language" id="language" type="button" aria-label="Switch to English">EN</button><div class="badge"><span class="dot"></span><span id="runStatus">ACCEPTED</span></div></div></header>
  <section class="overview" aria-label="运行摘要"><article class="card verdict" id="verdict"><div class="kicker" data-i18n="latestSnapshot">最近一次验收快照</div><h2 id="verdictTitle"></h2><p id="verdictSummary"></p><p class="snapshot mono" id="snapshotTime"></p></article><aside class="card truth"><div class="truth-row"><b data-i18n="realParts">真实运行</b><span data-i18n="realPartsValue">DeepSeek、SmolVLA 推理、SDK2 控制链</span></div><div class="truth-row"><b data-i18n="simParts">仿真替代</b><span data-i18n="simPartsValue">合成 EEG、MuJoCo 中的 G1 与环境</span></div><div class="truth-row"><b data-i18n="fixedParts">确定性部分</b><span data-i18n="fixedPartsValue">C++ 抓放 Behavior 与物理验收</span></div><div class="truth-row limitation"><b data-i18n="limitation">关键限制</b><span data-i18n="limitationValue">SmolVLA 仅以受限残差影响腰部和双臂，低层平衡仍由 RL Controller 负责。</span></div></aside></section>
  <details class="advanced"><summary data-i18n="advancedMetrics">查看专业运行指标</summary><section class="metrics" aria-label="关键指标">
    <div class="metric"><small data-i18n="harnessState">Harness 状态</small><strong id="stateMetric" class="ok">COMPLETED</strong></div>
    <div class="metric"><small data-i18n="maxRtt">VLA 最大 RTT</small><strong id="latencyMetric">—</strong></div>
    <div class="metric"><small data-i18n="coverage">Chunk 覆盖</small><strong id="coverageMetric">—</strong></div>
    <div class="metric"><small data-i18n="stale">过期回退</small><strong id="staleMetric" class="ok">0</strong></div>
  </section></details>
  <section class="card" aria-labelledby="stagesTitle"><div class="card-head"><h2 id="stagesTitle" data-i18n="intelligenceStages">智能链路阶段</h2><span class="mono" data-i18n="evidenceRule">每阶段必须显示来源与证据</span></div><div class="stage-grid" id="intelligenceStages"></div></section>
  <div style="height:12px"></div>
  <div class="grid">
    <div class="stack">
      <section class="card" aria-labelledby="cameraTitle"><div class="card-head"><h2 id="cameraTitle" data-i18n="camera">MuJoCo 相机 01</h2><span class="mono" id="frameCounter"></span></div><div class="camera"><img id="mainFrame" alt="MuJoCo G1 仿真关键帧"><div class="camera-empty" id="frameEmpty" hidden></div><span class="camera-label" id="frameStage"></span></div><div class="thumbs" id="thumbnails"></div><div class="controls"><button class="control" id="previous" type="button" data-i18n="previous">上一帧</button><button class="control" id="play" type="button">播放</button><button class="control" id="next" type="button" data-i18n="next">下一帧</button></div></section>
      <section class="card" aria-labelledby="pipelineTitle"><div class="card-head"><h2 id="pipelineTitle" data-i18n="trace">Harness 事件链</h2><span class="mono" id="traceStatus"></span></div><div class="pipeline" id="pipeline"></div><p class="detail" id="traceDetail" aria-live="polite"></p></section>
      <section class="card"><div class="card-head"><h2 data-i18n="ownership">控制权归属</h2><span class="mono ok" data-i18n="overlay">VLA 残差覆盖已启用</span></div><div class="topology"><div class="node"><b>SmolVLA · 3Hz</b><small data-i18n="authorization">受限腰部/双臂 Action Chunk</small></div><div class="node"><b>C++ Behavior</b><small data-i18n="targets">经过验证的基线目标</small></div><div class="node"><b>SDK2 + RL</b><small data-i18n="lowLevel">平衡与低层控制</small></div></div></section>
    </div>
    <aside class="stack">
      <section class="card"><div class="card-head"><h2 data-i18n="intents">EEG 解码意图</h2><span class="mono">BrainFlow / LSL</span></div><div id="intentBars"></div></section>
      <section class="card"><div class="card-head"><h2 data-i18n="budget">VLA 实时预算</h2><span class="mono" id="chunkCount"></span></div><div class="latency"><div class="latency-fill" id="latencyFill"></div><div class="latency-mark" id="coverageMark"></div></div><div class="latency-labels"><span>0 ms</span><span id="latencyText"></span><span id="coverageText"></span></div></section>
      <section class="card"><div class="card-head"><h2 data-i18n="outcome">物理结果</h2><span class="mono ok" data-i18n="verified">独立验证</span></div><div class="facts" id="facts"></div></section>
      <section class="card"><div class="card-head"><h2 data-i18n="quality">留出集模型质量</h2><span class="mono">SEED 0</span></div><div class="facts"><div class="fact"><small data-i18n="overallMse">整体 MSE</small><b id="mse"></b></div><div class="fact"><small data-i18n="armMse">腰部 / 手臂 MSE</small><b id="armMse"></b></div><div class="fact"><small data-i18n="frames">帧数</small><b id="evalFrames"></b></div><div class="fact"><small data-i18n="finite">有限值</small><b id="finite"></b></div></div></section>
    </aside>
  </div>
  <footer data-i18n="disclaimer">本页面由本地验收报告生成，不访问网络，不代表真实 EEG 或 G1 硬件性能。</footer>
</main>
<script type="application/json" id="dashboardData">{data}</script>
<script>
const d=JSON.parse(document.getElementById('dashboardData').textContent), q=s=>document.querySelector(s);
const copy={{zh:{{skip:'跳到主要内容',title:'Synapse2Action 仿真实验台',subtitle:'先看结论，再沿七个阶段理解机器人为什么成功或失败。',latestSnapshot:'最近一次验收快照',successTitle:'本次仿真运行成功',failedTitle:'本次仿真运行失败',successSummary:'合成 EEG 选择红色方块；真实 DeepSeek 生成抓放计划；计划经过审阅后才消费确认；SmolVLA 输出受限动作残差；SDK2 控制仿真 G1 完成抓取、抬升、释放和放置。',failedSummary:'流程没有完整通过。下方阶段会标出停止位置，展开证据可查看该阶段的输入和输出。',snapshotLabel:'页面生成时间',realParts:'真实运行',realPartsValue:'DeepSeek、SmolVLA 推理、SDK2 控制链',simParts:'仿真替代',simPartsValue:'合成 EEG、MuJoCo 中的 G1 与环境',fixedParts:'确定性部分',fixedPartsValue:'C++ 抓放 Behavior 与物理验收',limitation:'关键限制',limitationValue:'SmolVLA 仅以受限残差影响腰部和双臂，低层平衡仍由 RL Controller 负责。',advancedMetrics:'查看专业运行指标',viewEvidence:'查看输入与输出证据',stageCompleted:'阶段完成',stageFailed:'阶段失败',intentExplain:'从合成 EEG 中解码“选择红色方块”，确认输入会保留到计划审阅完成。',llm_plannerExplain:'真实 DeepSeek 先把选中目标转换成结构化抓放计划。',plan_reviewExplain:'展示已校验的技能、目标和目的地，确认后才允许执行。',vlaExplain:'SmolVLA读取三路相机和关节状态，返回 Action Chunk；当前输出受限腰部和双臂动作残差。',skill_executorExplain:'确定性 C++ Behavior 校验计划，并生成受约束的抓取、搬运和释放目标。',motion_controlExplain:'Unitree RL Controller 保持平衡，SDK2 将低层控制帧送入 MuJoCo。',physical_verificationExplain:'读取机器人与物体状态，独立检查站立、抓取、抬升、释放和落盘。',intelligenceStages:'这次运行经历了什么',evidenceRule:'按实际执行顺序阅读',status:'状态',input:'收到',output:'产出',latency:'耗时',noFrames:'本次运行未产生 MuJoCo 相机帧，请查看失败阶段。',intent:'01 · 目标选择',llm_planner:'02 · LLM 规划',plan_review:'03 · 计划审阅与确认',vla:'04 · VLA 感知与输出',skill_executor:'05 · 技能校验与执行',motion_control:'06 · 运动控制',physical_verification:'07 · 物理验证',harnessState:'Harness 状态',maxRtt:'VLA 最大 RTT',coverage:'Chunk 覆盖',stale:'过期回退',camera:'MuJoCo 相机 01',previous:'上一帧',next:'下一帧',play:'播放',pause:'暂停',trace:'Harness 事件链',ownership:'控制权归属',overlay:'VLA 残差覆盖已启用',authorization:'受限腰部/双臂 Action Chunk',targets:'经过验证的基线目标',lowLevel:'平衡与低层控制',intents:'EEG 解码意图',budget:'VLA 实时预算',outcome:'物理结果',verified:'独立验证',quality:'留出集模型质量',overallMse:'整体 MSE',armMse:'腰部 / 手臂 MSE',frames:'帧数',finite:'有限值',disclaimer:'这是最近一次运行的离线报告快照，不是实时监控，也不代表真实 EEG 或 G1 硬件性能。',chunks:'个 CHUNK',budgetWord:'预算',pass:'通过',fail:'失败',ready:'就绪',grasp:'抓取',lift:'抬升',release:'释放',final:'最终',standing:'保持站立',grasped:'已抓取',lifted:'已抬升',released:'已释放',dropZone:'进入放置区',authorized:'VLA 动作已应用'}},en:{{skip:'Skip to main content',title:'Synapse2Action Simulation Console',subtitle:'Read the verdict first, then follow seven stages to understand why the robot succeeded or failed.',latestSnapshot:'Latest acceptance snapshot',successTitle:'This simulation run succeeded',failedTitle:'This simulation run failed',successSummary:'Synthetic EEG selected the red cube; live DeepSeek produced a pick-and-place plan; confirmation was consumed only after plan review; SmolVLA contributed bounded action residuals; SDK2 controlled the simulated G1 through grasp, lift, release, and placement.',failedSummary:'The pipeline did not complete. The stages below show where it stopped; expand evidence to inspect that stage’s input and output.',snapshotLabel:'Page generated',realParts:'Live components',realPartsValue:'DeepSeek, SmolVLA inference, and SDK2 control path',simParts:'Simulated substitutes',simPartsValue:'Synthetic EEG and the G1/world in MuJoCo',fixedParts:'Deterministic parts',fixedPartsValue:'C++ pick-place behavior and physical acceptance',limitation:'Key limitation',limitationValue:'SmolVLA contributes bounded waist and arm residuals; the RL controller still owns low-level balance.',advancedMetrics:'Show advanced runtime metrics',viewEvidence:'View input and output evidence',stageCompleted:'Stage completed',stageFailed:'Stage failed',intentExplain:'Decode “select red cube” from synthetic EEG and hold confirmation until plan review completes.',llm_plannerExplain:'Live DeepSeek converts the selected target into a structured pick-and-place plan before confirmation.',plan_reviewExplain:'Show the validated skill, target, and destination; execution remains blocked until confirmation.',vlaExplain:'SmolVLA reads three cameras and joint state and returns Action Chunks; these currently contribute bounded waist and arm action residuals.',skill_executorExplain:'Deterministic C++ behavior validates the plan and produces constrained grasp, transport, and release targets.',motion_controlExplain:'The Unitree RL controller maintains balance while SDK2 sends low-level control frames into MuJoCo.',physical_verificationExplain:'Robot and object state independently verify standing, grasp, lift, release, and drop-zone placement.',intelligenceStages:'What happened in this run',evidenceRule:'Read in execution order',status:'Status',input:'Received',output:'Produced',latency:'Latency',noFrames:'This run produced no MuJoCo camera frames. Inspect the failed stage.',intent:'01 · Target selection',llm_planner:'02 · LLM planning',plan_review:'03 · Plan review and confirmation',vla:'04 · VLA perception and output',skill_executor:'05 · Skill validation and execution',motion_control:'06 · Motion control',physical_verification:'07 · Physical verification',harnessState:'Harness state',maxRtt:'VLA max RTT',coverage:'Chunk coverage',stale:'Stale fallback',camera:'MuJoCo Camera 01',previous:'Previous',next:'Next',play:'Play',pause:'Pause',trace:'Harness event trace',ownership:'Control ownership',overlay:'VLA RESIDUAL OVERLAY ENABLED',authorization:'bounded waist/arm Action Chunk',targets:'validated baseline targets',lowLevel:'balance and low-level control',intents:'EEG decoded intents',budget:'VLA realtime budget',outcome:'Physical outcome',verified:'INDEPENDENTLY VERIFIED',quality:'Held-out model quality',overallMse:'Overall MSE',armMse:'Waist / arm MSE',frames:'Frames',finite:'Finite',disclaimer:'This is an offline snapshot of the latest run, not live monitoring or evidence of physical EEG/G1 performance.',chunks:'CHUNKS',budgetWord:'budget',pass:'PASS',fail:'FAIL',ready:'READY',grasp:'GRASP',lift:'LIFT',release:'RELEASE',final:'FINAL',standing:'standing',grasped:'grasped',lifted:'lifted',released:'released',dropZone:'in drop zone',authorized:'VLA action applied'}}}};
const savedLanguage=()=>{{try{{return localStorage.getItem('s2a-language')}}catch{{return null}}}},saveLanguage=value=>{{try{{localStorage.setItem('s2a-language',value)}}catch{{}}}};
let lang=savedLanguage()||((navigator.language||'').toLowerCase().startsWith('zh')?'zh':'en');
const runtime=d.acceptance.runtime, sim=d.simulator, frames=d.frames, trace=d.harness.trace;
q('#runStatus').textContent=d.harness.accepted?'ACCEPTED':'REJECTED';q('#runStatus').closest('.badge').classList.toggle('rejected',!d.harness.accepted); q('#stateMetric').textContent=d.harness.final_state.toUpperCase();
q('#latencyMetric').textContent=(runtime.maximum_round_trip_ms/1000).toFixed(2)+'s'; q('#coverageMetric').textContent=(runtime.minimum_chunk_coverage_ms/1000).toFixed(2)+'s'; q('#staleMetric').textContent=runtime.stale_fallbacks;
const scale=Math.max(runtime.maximum_round_trip_ms,runtime.minimum_chunk_coverage_ms,1)*1.1;
q('#latencyFill').style.width=(runtime.maximum_round_trip_ms/scale*100)+'%'; q('#coverageMark').style.left=(runtime.minimum_chunk_coverage_ms/scale*100)+'%'; q('#latencyText').textContent='RTT '+Math.round(runtime.maximum_round_trip_ms)+' ms'; q('#coverageText').textContent='budget '+Math.round(runtime.minimum_chunk_coverage_ms)+' ms';
const intents=d.eeg.harness_replay.decoded_examples; q('#intentBars').innerHTML=Object.entries(intents).map(([name,x])=>`<div class="bar-row"><span>${{name}}</span><div class="bar-track"><div class="bar-fill" style="width:${{(x.confidence*100).toFixed(1)}}%"></div></div><output>${{(x.confidence*100).toFixed(1)}}%</output></div>`).join('');
q('#mse').textContent=d.training.mse.toFixed(6); q('#armMse').textContent=d.training.arm_waist_mse.toFixed(6); q('#evalFrames').textContent=d.training.frames; q('#finite').textContent=d.training.finite?'PASS':'FAIL';
let frameIndex=0,traceIndex=trace.length-1,timer=null; const stageName=s=>copy[lang][s]||s.toUpperCase();
function renderFrame(i){{if(!frames.length){{q('#mainFrame').removeAttribute('src');q('#mainFrame').hidden=true;q('#frameEmpty').hidden=false;q('#frameEmpty').textContent=copy[lang].noFrames;q('#frameStage').textContent='';q('#frameCounter').textContent='0 / 0';q('#previous').disabled=q('#play').disabled=q('#next').disabled=true;return}}frameIndex=Math.max(0,Math.min(frames.length-1,i));const f=frames[frameIndex];q('#mainFrame').hidden=false;q('#frameEmpty').hidden=true;q('#mainFrame').src=f.data;q('#mainFrame').alt='MuJoCo G1 '+stageName(f.stage)+' 关键帧';q('#frameStage').textContent=stageName(f.stage);q('#frameCounter').textContent=`${{frameIndex+1}} / ${{frames.length}}`;q('#previous').disabled=frameIndex===0;q('#next').disabled=frameIndex===frames.length-1;document.querySelectorAll('.thumb').forEach((x,n)=>x.setAttribute('aria-current',n===frameIndex));}}
q('#thumbnails').innerHTML=frames.map((f,i)=>`<button class="thumb" type="button" data-index="${{i}}"><img src="${{f.data}}" alt=""><span>${{stageName(f.stage)}}</span></button>`).join('');document.querySelectorAll('.thumb').forEach(x=>x.onclick=()=>{{stop();renderFrame(Number(x.dataset.index))}});
function stop(){{if(timer)clearInterval(timer);timer=null;q('#play').textContent=copy[lang].play;}} q('#previous').onclick=()=>{{stop();renderFrame(frameIndex-1)}};q('#next').onclick=()=>{{stop();renderFrame(frameIndex+1)}};q('#play').onclick=()=>{{if(timer){{stop();return}};if(frameIndex===frames.length-1)renderFrame(0);q('#play').textContent=copy[lang].pause;timer=setInterval(()=>frameIndex===frames.length-1?stop():renderFrame(frameIndex+1),900)}};
q('#pipeline').innerHTML=trace.map((x,i)=>`<button class="pipe-step" type="button" data-index="${{i}}"><span class="mono">${{String(i+1).padStart(2,'0')}}</span><b>${{x.event}}</b></button>`).join('');
function renderTrace(i){{traceIndex=i;const x=trace[i];document.querySelectorAll('.pipe-step').forEach((n,j)=>n.classList.toggle('active',j<=i));q('#traceStatus').textContent=x.state.toUpperCase();q('#traceDetail').textContent=`${{x.event}} · ${{x.detail||'—'}} · state=${{x.state}}`;}} document.querySelectorAll('.pipe-step').forEach(x=>x.onclick=()=>renderTrace(Number(x.dataset.index)));
const describe=value=>value===null||value===undefined?'—':typeof value==='string'?value:JSON.stringify(value);
function applyLanguage(){{
  const t=copy[lang]; document.documentElement.lang=lang==='zh'?'zh-CN':'en';
  document.querySelectorAll('[data-i18n]').forEach(x=>x.textContent=t[x.dataset.i18n]);
  q('#language').textContent=lang==='zh'?'EN':'中文'; q('#language').setAttribute('aria-label',lang==='zh'?'Switch to English':'切换到中文');
  q('#verdict').classList.toggle('rejected',!d.harness.accepted); q('#verdictTitle').textContent=d.harness.accepted?t.successTitle:t.failedTitle; q('#verdictSummary').textContent=d.harness.accepted?t.successSummary:t.failedSummary;
  const generated=d.snapshot&&d.snapshot.generated_at; q('#snapshotTime').textContent=t.snapshotLabel+' · '+(generated?new Date(generated).toLocaleString(lang==='zh'?'zh-CN':'en-US'):'—');
  q('#chunkCount').textContent=runtime.chunks_received+' '+t.chunks; q('#coverageText').textContent=t.budgetWord+' '+Math.round(runtime.minimum_chunk_coverage_ms)+' ms'; q('#finite').textContent=d.training.finite?t.pass:t.fail;
  const facts=[[t.standing,sim.fell_at_seconds===null],[t.grasped,sim.grasped],[t.lifted,(sim.maximum_object_height_m||0)-(sim.initial_object_position_xyz_m||[0,0,0])[2]>=.1],[t.released,sim.released],[t.dropZone,sim.final_object_center_in_drop_zone],[t.authorized,sim.vla_authorized_frames>0]];
  q('#facts').innerHTML=facts.map(([name,ok])=>`<div class="fact"><small>${{name}}</small><b class="${{ok?'ok':'warn'}}">${{ok?t.pass:t.fail}}</b></div>`).join('');
  const stages=d.harness.intelligence_stages||[];
  q('#intelligenceStages').innerHTML=stages.length?stages.map(s=>{{const provenance=[s.provider,s.model].filter(Boolean).join(' · ');return `<article class="stage-card"><header><h3>${{t[s.id]||s.id}}</h3><span class="provenance ${{s.mode}}">${{String(s.mode).toUpperCase()}}</span></header><p class="explain">${{t[s.id+'Explain']||''}}</p><strong class="${{s.status==='completed'?'ok':'warn'}}">${{s.status==='completed'?t.stageCompleted:t.stageFailed}}</strong>${{provenance?`<p class="mono">${{provenance}}</p>`:''}}<details><summary>${{t.viewEvidence}}</summary><dl><dt>${{t.input}}</dt><dd>${{describe(s.input)}}</dd><dt>${{t.output}}</dt><dd>${{describe(s.output)}}</dd>${{s.latency_ms===null||s.latency_ms===undefined?'':`<dt>${{t.latency}}</dt><dd>${{s.latency_ms}} ms</dd>`}}</dl></details></article>`}}).join(''):`<p class="warn">${{lang==='zh'?'旧报告未包含阶段证据，请重新运行仿真。':'Legacy report has no stage evidence. Run the simulation again.'}}</p>`;
  q('#thumbnails').innerHTML=frames.map((f,i)=>`<button class="thumb" type="button" data-index="${{i}}"><img src="${{f.data}}" alt=""><span>${{stageName(f.stage)}}</span></button>`).join('');
  document.querySelectorAll('.thumb').forEach(x=>x.onclick=()=>{{stop();renderFrame(Number(x.dataset.index))}}); renderFrame(frameIndex); stop();
}}
q('#language').onclick=()=>{{lang=lang==='zh'?'en':'zh';saveLanguage(lang);applyLanguage();}};applyLanguage();renderTrace(traceIndex);
</script>
</body></html>"""
