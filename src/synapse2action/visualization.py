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
