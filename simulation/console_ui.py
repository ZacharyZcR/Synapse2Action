from __future__ import annotations


CONSOLE_CSS = r"""
:root{--bg:#071018;--surface:#0d1823;--surface-2:#122231;--surface-3:#172b3d;--line:#294156;--line-strong:#3b5d77;--text:#f3f7fa;--muted:#a9bac7;--primary:#38bdf8;--primary-strong:#0284c7;--success:#5ee6a8;--warning:#f6c453;--danger:#ff7b86;--focus:#fde68a;--radius-sm:8px;--radius-md:12px;--radius-lg:18px;--shadow:0 18px 50px rgba(0,0,0,.24)}
html{background:var(--bg)}body{min-height:100dvh;background:radial-gradient(circle at 82% -10%,rgba(14,165,233,.13),transparent 35%),var(--bg)}main{width:min(1500px,calc(100% - 48px));padding:28px 0 56px}.skip-link{position:fixed;left:16px;top:12px;z-index:1000;transform:translateY(-160%);padding:10px 14px;border-radius:var(--radius-sm);background:var(--text);color:var(--bg);font-weight:800}.skip-link:focus{transform:none}header{align-items:flex-start;padding:0 2px 22px;border-bottom:1px solid var(--line)}header p{max-width:680px;margin:8px 0 0}.live{letter-spacing:.13em}.actions{flex-wrap:wrap;justify-content:flex-end}button,select{border-color:var(--line-strong);touch-action:manipulation}button:active{filter:brightness(.92)}#start{min-width:150px;background:var(--primary);color:#03263a;box-shadow:0 8px 24px rgba(56,189,248,.16)}#language{min-width:52px}.source{margin-top:16px;border:1px solid var(--line);border-left:3px solid var(--primary);border-radius:var(--radius-md);background:linear-gradient(90deg,rgba(56,189,248,.08),transparent 45%),var(--surface);box-shadow:var(--shadow)}.overview{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px}.metric{min-width:0;padding:13px 14px;border:1px solid var(--line);border-radius:var(--radius-md);background:var(--surface)}.metric-label{display:block;margin-bottom:5px;color:var(--muted);font-size:.72rem;font-weight:800;letter-spacing:.09em;text-transform:uppercase}.metric-value{display:block;overflow:hidden;color:var(--text);font:700 .95rem/1.35 ui-monospace,SFMono-Regular,Consolas,monospace;text-overflow:ellipsis;white-space:nowrap}.metric-value[data-tone="success"]{color:var(--success)}.metric-value[data-tone="warning"]{color:var(--warning)}.metric-value[data-tone="danger"]{color:var(--danger)}.progress-shell{grid-column:1/-1;padding:12px 14px;border:1px solid var(--line);border-radius:var(--radius-md);background:var(--surface)}.progress-meta{display:flex;justify-content:space-between;gap:12px;margin-bottom:8px;color:var(--muted);font-size:.78rem}.progress-track{height:6px;overflow:hidden;border-radius:999px;background:#1d3345}.progress-fill{width:0;height:100%;border-radius:inherit;background:linear-gradient(90deg,var(--primary-strong),var(--primary));transition:width .25s ease}.layout{grid-template-columns:minmax(0,1.7fr) minmax(330px,.65fr);gap:12px}.card{border-color:var(--line);border-radius:var(--radius-lg);background:linear-gradient(180deg,rgba(255,255,255,.018),transparent 30%),var(--surface);box-shadow:var(--shadow)}.viewer{border:1px solid var(--line);background:#02070b}.statusline h2,.card>h2{margin:0}.stages{margin-top:12px}.stage{position:relative;grid-template-columns:30px 1fr auto;min-height:58px;padding:10px 10px 10px 12px;border-color:var(--line);background:rgba(255,255,255,.012)}.stage:before{position:absolute;left:-1px;top:10px;bottom:10px;width:3px;border-radius:0 3px 3px 0;background:var(--line);content:""}.stage.running:before{background:var(--primary)}.stage.completed:before{background:var(--success)}.stage.failed:before{background:var(--danger)}.stage small{display:block;overflow-wrap:anywhere}.stage.completed{border-color:rgba(94,230,168,.32)}.stage.failed{border-color:rgba(255,123,134,.5)}.stage.running{border-color:rgba(56,189,248,.55)}.pill{min-width:68px;text-align:center}.stage.completed .pill{color:var(--success)}.stage.failed .pill{color:var(--danger)}pre{min-height:106px;max-height:210px;border:1px solid var(--line)}.result{display:grid;grid-template-columns:auto 1fr;align-items:baseline;gap:10px;padding-top:12px;border-top:1px solid var(--line)}.result p{margin:0}.safety{display:inline-flex;align-items:center;min-height:32px;padding:5px 10px;border:1px solid rgba(246,196,83,.35);border-radius:999px;background:rgba(246,196,83,.07)}
@media(max-width:1024px){main{width:min(100% - 32px,900px)}.overview{grid-template-columns:repeat(2,minmax(0,1fr))}.layout{grid-template-columns:1fr}.layout aside{order:-1}.stages{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:620px){main{width:calc(100% - 24px);padding-top:16px}header{display:block}.actions{display:grid;grid-template-columns:1fr 1fr;margin-top:18px}.actions #start{grid-column:1/-1;grid-row:1}.source{display:grid;gap:10px}.overview{grid-template-columns:1fr 1fr}.metric{padding:11px}.metric-value{font-size:.84rem}.stages{grid-template-columns:1fr}.card{padding:13px}.viewer{aspect-ratio:4/3}.view-tabs{display:grid;grid-template-columns:1fr 1fr}.view-tabs select{grid-column:1/-1}.result{grid-template-columns:1fr}.safety{width:max-content;max-width:100%}}
@media(max-width:390px){.overview{grid-template-columns:1fr}.actions{grid-template-columns:1fr}.actions #start{grid-column:auto}.progress-meta{display:grid;gap:3px}}
@media(prefers-reduced-motion:reduce){.progress-fill{transition:none}}
"""


OVERVIEW_HTML = r"""
<section class="overview" aria-label="Runtime overview">
  <div class="metric"><span class="metric-label">Runtime</span><span class="metric-value" id="runtimeMetric">Checking</span></div>
  <div class="metric"><span class="metric-label">Policy gate</span><span class="metric-value" id="policyMetric">Candidate</span></div>
  <div class="metric"><span class="metric-label">Pipeline</span><span class="metric-value" id="stageMetric">0 / 8</span></div>
  <div class="metric"><span class="metric-label">Verdict</span><span class="metric-value" id="verdictMetric">Idle</span></div>
  <div class="progress-shell">
    <div class="progress-meta"><span>Execution progress</span><span id="progressLabel">Waiting for authorization</span></div>
    <div class="progress-track" role="progressbar" aria-label="Execution progress" aria-valuemin="0" aria-valuemax="8" aria-valuenow="0"><div class="progress-fill" id="pipelineProgress"></div></div>
  </div>
</section>
"""


CONSOLE_JS = r"""
const enhanceRender=render;
render=function(s){
  enhanceRender(s);
  const completed=s.stages.filter(x=>x.status==='completed').length;
  const failed=s.stages.some(x=>x.status==='failed');
  const running=s.stages.some(x=>x.status==='running');
  const progress=document.querySelector('.progress-track');
  document.querySelector('#runtimeMetric').textContent=s.ready?(s.running?'ONLINE · RUNNING':'ONLINE · READY'):'NOT READY';
  document.querySelector('#runtimeMetric').dataset.tone=s.ready?'success':'danger';
  document.querySelector('#policyMetric').textContent=s.profile==='full-live'?'SMOLVLA · CANDIDATE':'GR00T · CANDIDATE';
  document.querySelector('#policyMetric').dataset.tone='warning';
  document.querySelector('#stageMetric').textContent=`${completed} / ${s.stages.length}`;
  const verdict=s.running?'RUNNING':s.accepted===true?'ACCEPTED':s.accepted===false?'REJECTED':'IDLE';
  document.querySelector('#verdictMetric').textContent=verdict;
  document.querySelector('#verdictMetric').dataset.tone=s.accepted===true?'success':s.accepted===false?'danger':running?'warning':'';
  document.querySelector('#pipelineProgress').style.width=`${100*completed/s.stages.length}%`;
  progress.setAttribute('aria-valuemax',String(s.stages.length));
  progress.setAttribute('aria-valuenow',String(completed));
  document.querySelector('#progressLabel').textContent=failed?'A stage requires attention':running?`Stage ${completed+1} in progress`:s.accepted===true?'All stages accepted':'Waiting for authorization';
  document.querySelector('#start').setAttribute('aria-busy',String(s.running));
};
document.querySelector('#start').onclick=()=>{
  const profile=lastState?.profile==='full-live'?'SmolVLA':'GR00T';
  const warning=lang==='zh'
    ? `授权本次仿真运行？\n\n${profile} 当前是 Candidate，并未通过生产准入。`
    : `Authorize this simulation run?\n\n${profile} is a Candidate and is not production-admitted.`;
  if(confirm(warning))action('/api/run');
};
"""


def enhance_console_html(html: str) -> str:
    """Apply the operations-console visual system without external assets."""

    html = html.replace("</style>", CONSOLE_CSS + "</style>", 1)
    html = html.replace(
        "<body><main>",
        '<body><a class="skip-link" href="#main-content">Skip to console</a><main id="main-content">',
        1,
    )
    html = html.replace('<div class="layout">', OVERVIEW_HTML + '<div class="layout">', 1)
    html = html.replace(
        '<div class="result" aria-live="polite">',
        '<div class="result" role="status" aria-live="polite">',
        1,
    )
    html = html.replace("</script></body>", CONSOLE_JS + "</script></body>", 1)
    return html
