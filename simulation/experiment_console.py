from __future__ import annotations

import argparse
import hmac
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
from threading import Lock, Thread
from time import sleep, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


STAGES = (
    ("dataset", "Open EEG dataset"),
    ("intent", "EEG decoding"),
    ("llm_planner", "LLM planning"),
    ("plan_review", "Plan review and confirmation"),
    ("vla", "VLA inference"),
    ("skill_executor", "Skill execution"),
    ("motion_control", "Robot control"),
    ("physical_verification", "Physical verification"),
)


def groot_history(project: Path) -> list[dict[str, object]]:
    benchmark = project / "reports/simulation/groot-benchmark-phase1"
    video_directory = project / "reports/simulation/groot-evidence-video"
    videos = sorted(video_directory.glob("*.mp4"), key=lambda path: path.stat().st_mtime)
    history = []
    used: set[Path] = set()
    for evidence_path in sorted(benchmark.glob("evidence-seed-*.json")):
        payload = json.loads(evidence_path.read_text())
        episode = payload["episodes"][0]
        written = evidence_path.stat().st_mtime
        candidates = [
            path for path in videos
            if path not in used and 0 <= written - path.stat().st_mtime <= 30
        ]
        video = min(candidates, key=lambda path: written - path.stat().st_mtime) if candidates else None
        if video:
            used.add(video)
        history.append(
            {
                "seed": episode["seed"],
                "stable_on_plate": episode["stable_on_plate"],
                "lifted": episode["lifted"],
                "remained_standing": episode["remained_standing"],
                "maximum_lift_m": episode["maximum_lift_m"],
                "video": video.name if video else None,
                "webm": f"seed-{episode['seed']}.webm"
                if (project / "reports/simulation/groot-evidence-video-web" / f"seed-{episode['seed']}.webm").is_file()
                else None,
            }
        )
    return history


def parse_byte_range(requested: str | None, size: int) -> tuple[int, int, bool]:
    if not requested:
        return 0, size - 1, False
    if not requested.startswith("bytes=") or "," in requested:
        raise ValueError("unsupported range")
    first, last = requested[6:].split("-", 1)
    if not first:
        suffix_length = int(last)
        if suffix_length <= 0:
            raise ValueError("invalid suffix range")
        return max(0, size - suffix_length), size - 1, True
    start = int(first)
    end = min(int(last) if last else size - 1, size - 1)
    if start < 0 or start > end or start >= size:
        raise ValueError("invalid range")
    return start, end, True


def console_html() -> str:
    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Synapse2Action 实验控制台</title><style>
:root{color-scheme:dark;--bg:#070b12;--card:#111827;--line:#334155;--text:#f1f5f9;--muted:#a8b3c3;--ok:#34d399;--run:#38bdf8;--wait:#94a3b8;--bad:#f87171;--focus:#fbbf24}*{box-sizing:border-box}[hidden]{display:none!important}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 "Segoe UI",system-ui,sans-serif}main{width:min(1480px,calc(100% - 32px));margin:auto;padding:20px 0 48px}header,.actions,.statusline,.view-tabs{display:flex;align-items:center;justify-content:space-between;gap:12px}h1{margin:0;font-size:clamp(1.6rem,3vw,2.5rem);letter-spacing:-.035em}h2{font-size:1rem}p{color:var(--muted)}button,select{min-height:44px;padding:9px 16px;border:1px solid var(--line);border-radius:8px;background:var(--ok);color:#052e16;font:inherit;font-weight:750;cursor:pointer;transition:background-color .18s,border-color .18s,opacity .18s}button:hover{filter:brightness(1.08)}button:focus-visible,select:focus-visible{outline:3px solid var(--focus);outline-offset:2px}#language,.tab,select{background:var(--card);color:var(--text)}.tab[aria-selected="true"]{border-color:var(--run);color:var(--run)}#stop{background:#3f1118;border-color:#991b1b;color:#fecaca}button:disabled{opacity:.42;cursor:not-allowed;filter:none}.layout{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(340px,.75fr);gap:12px;margin-top:12px}.card{border:1px solid var(--line);border-radius:10px;background:var(--card);padding:16px}.viewer{position:relative;aspect-ratio:16/9;background:#030712;border-radius:8px;overflow:hidden}.viewer img,.viewer video{width:100%;height:100%;object-fit:cover}.viewer .empty{position:absolute;inset:0;display:grid;place-items:center;padding:24px;color:var(--muted);text-align:center}.view-tabs{justify-content:flex-start;margin-bottom:10px}.view-tabs select{margin-left:auto;max-width:340px}.evidence-summary{min-height:24px;margin:8px 0 0;font:13px/1.5 ui-monospace,monospace;color:var(--muted)}.live{color:var(--run);font:700 .75rem ui-monospace,monospace}.stages{display:grid;gap:6px}.stage{display:grid;grid-template-columns:28px 1fr auto;gap:10px;align-items:center;padding:9px 10px;border:1px solid var(--line);border-radius:8px}.num{display:grid;place-items:center;width:26px;height:26px;border-radius:6px;background:#1e293b;font:700 .75rem ui-monospace,monospace}.stage b{display:block}.stage small{color:var(--muted)}.pill{padding:3px 7px;border-radius:5px;background:#1e293b;color:var(--wait);font:700 .65rem ui-monospace,monospace}.stage.running{border-color:var(--run)}.stage.running .pill{color:var(--run)}.stage.completed{border-color:#166534}.stage.completed .pill{color:var(--ok)}.stage.failed{border-color:#991b1b}.stage.failed .pill{color:var(--bad)}pre{max-height:180px;overflow:auto;margin:10px 0 0;padding:12px;border-radius:8px;background:#030712;color:#cbd5e1;font:12px/1.5 ui-monospace,monospace;white-space:pre-wrap}.source{display:flex;justify-content:space-between;gap:16px;margin-top:12px;padding:10px 12px;border-left:3px solid var(--run);background:#0b1627;color:#cbd5e1}.safety{color:#fcd34d}.result{margin-top:14px}.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--focus)}@media(max-width:900px){.layout{grid-template-columns:1fr}header{display:block}.actions{margin-top:14px;flex-wrap:wrap}.source{display:block}.view-tabs{flex-wrap:wrap}.view-tabs select{width:100%;max-width:none;margin:0}}@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body><main><header><div><div class="live">LOCAL SIMULATION CONTROL</div><h1 data-i18n="title">Synapse2Action 任务控制台</h1><p data-i18n="subtitle">审阅任务状态、VLA 推理和 MuJoCo 行为证据。</p></div><div class="actions"><button id="language" type="button">EN</button><button id="stop" type="button" disabled data-i18n="stop">停止仿真</button><button id="start" data-i18n="start">授权并运行</button></div></header><div class="source"><span><b data-i18n="source">输入：</b><span id="profileSource">正在检测 Runtime</span><br><small id="readiness"></small></span><strong class="safety" data-i18n="safety">仿真控制，不是真机急停</strong></div><div class="layout"><section class="card"><div class="statusline"><h2 data-i18n="viewer">MuJoCo 机器人环境</h2><span class="live" id="frameStatus">WAITING</span></div><div class="view-tabs" role="tablist"><button class="tab" id="liveTab" type="button" role="tab" aria-selected="true" data-i18n="liveView">实时画面</button><button class="tab" id="replayTab" type="button" role="tab" aria-selected="false" data-i18n="replayView">GR00T 回放</button><select id="runSelect" aria-label="GR00T evidence run" hidden></select></div><div class="viewer"><img id="frame" hidden alt="MuJoCo G1 live simulation"><video id="replay" controls preload="metadata" hidden aria-label="GR00T G1 MuJoCo evidence replay"></video><div class="empty" id="empty" data-i18n="empty">授权运行后显示实时仿真画面</div></div><p class="evidence-summary" id="evidenceSummary" aria-live="polite"></p><div class="result" aria-live="polite"><b id="verdict"></b><p id="summary"></p></div><pre id="log" tabindex="0">Ready.</pre></section><aside class="card"><h2 data-i18n="stages">运行阶段</h2><div class="stages" id="stages"></div></aside></div></main><script>
const copy={zh:{title:'Synapse2Action 任务控制台',subtitle:'审阅任务状态、VLA 推理和 MuJoCo 行为证据。',start:'授权并运行',stop:'停止仿真',source:'输入：',subjects:'受试者 001-004，留出 004',safety:'仿真控制，不是真机急停',confirm:'确认授权这次仿真运行？',viewer:'MuJoCo 机器人环境',liveView:'实时画面',replayView:'GR00T 回放',empty:'授权运行后显示实时仿真画面',stages:'运行阶段',running:'实验运行中',success:'实验成功',partial:'任务完成，严格净空门槛未通过',failed:'实验失败',stopped:'已停止',notReady:'环境未就绪',idle:'尚未运行',waiting:'等待操作员授权。',successSummary:'八个阶段全部通过。',failedSummary:'物理闭环未通过，请查看失败阶段和实时画面。',stoppedSummary:'仿真进程已停止，机器人真机安全状态不由此按钮保证。',labels:{dataset:['开源 EEG 数据','读取 MAMEM 原始记录'],intent:['EEG 目标选择','解码选择意图并暂存确认输入'],llm_planner:['LLM 规划','输出结构化技能'],plan_review:['计划审阅与确认','校验计划后才允许执行'],vla:['视觉动作模型','读取相机与关节状态'],skill_executor:['技能执行器','生成受约束目标'],motion_control:['机器人控制','RL Controller + SDK2 LowCmd'],physical_verification:['物理验证','检查抓取、抬升与落盘']}},en:{title:'Synapse2Action Mission Console',subtitle:'Review task state, VLA inference, and MuJoCo behavior evidence.',start:'Authorize run',stop:'Stop simulation',source:'Input:',subjects:'Subjects 001-004, held-out 004',safety:'Simulation control, not a hardware E-Stop',confirm:'Authorize this simulation run?',viewer:'MuJoCo robot environment',liveView:'Live view',replayView:'GR00T replay',empty:'Authorize a run to view the live simulation',stages:'Run stages',running:'Experiment running',success:'Experiment succeeded',partial:'Task completed; strict clearance gate missed',failed:'Experiment failed',stopped:'Stopped',notReady:'Environment not ready',idle:'Not started',waiting:'Waiting for operator authorization.',successSummary:'All eight stages passed.',failedSummary:'The physical loop failed. Inspect the failed stage and live view.',stoppedSummary:'The simulation process stopped. This control does not guarantee physical robot safety.',labels:{dataset:['Open EEG data','Read raw MAMEM records'],intent:['EEG target selection','Decode selection and hold confirmation input'],llm_planner:['LLM planning','Emit a typed skill'],plan_review:['Plan review and confirmation','Execute only after plan validation'],vla:['Vision-action model','Read cameras and joint state'],skill_executor:['Skill executor','Emit constrained targets'],motion_control:['Robot control','RL Controller + SDK2 LowCmd'],physical_verification:['Physical verification','Check grasp, lift, and placement']}}};let lang=(navigator.language||'').startsWith('zh')?'zh':'en',frameSeen=0,lastState=null,history=[];const token=new URLSearchParams(location.search).get('token')||'',api=path=>path+'?token='+encodeURIComponent(token);
function translate(){const t=copy[lang];document.documentElement.lang=lang==='zh'?'zh-CN':'en';document.querySelectorAll('[data-i18n]').forEach(x=>x.textContent=t[x.dataset.i18n]);document.querySelector('#language').textContent=lang==='zh'?'EN':'中文';if(lastState)render(lastState)}
function render(s){lastState=s;const t=copy[lang],labels=t.labels,sources={"groot-local":'GR00T N1.6 + MockPlanner + scripted intent',"groot-live-planner":'GR00T N1.6 + live LLM Planner + scripted intent',"full-live":'MAMEM SSVEP + live Planner + SmolVLA'};document.querySelector('#start').disabled=s.running||!s.ready;document.querySelector('#stop').disabled=!s.running;document.querySelector('#profileSource').textContent=sources[s.profile]||s.profile;document.querySelector('#readiness').textContent=s.readiness.message;document.querySelector('#readiness').className=s.ready?'ok':'bad';document.querySelector('#stages').innerHTML=s.stages.map((x,i)=>`<div class="stage ${x.status}"><span class="num">${i+1}</span><span><b>${labels[x.id][0]}</b><small>${x.detail||labels[x.id][1]}</small></span><span class="pill">${x.status.toUpperCase()}</span></div>`).join('');document.querySelector('#log').textContent=s.log.join('\\n')||'Ready.';const v=document.querySelector('#verdict'),partial=s.accepted===false&&s.task_completed===true;v.textContent=s.running?t.running:s.stopped?t.stopped:!s.ready?t.notReady:s.accepted===true?t.success:partial?t.partial:s.accepted===false?t.failed:t.idle;v.className=s.accepted===true?'ok':partial?'warn':s.accepted===false||!s.ready?'bad':'';document.querySelector('#summary').textContent=s.stopped?t.stoppedSummary:!s.ready?s.summary:s.accepted===true?t.successSummary:s.accepted===false?(s.summary||t.failedSummary):t.waiting;if(s.frame_version>frameSeen){frameSeen=s.frame_version;const img=document.querySelector('#frame');img.src=api('/api/frame')+'&v='+frameSeen;img.hidden=false;document.querySelector('#empty').hidden=true;document.querySelector('#frameStatus').textContent='LIVE '+frameSeen}}
function showLive(){document.querySelector('#liveTab').setAttribute('aria-selected','true');document.querySelector('#replayTab').setAttribute('aria-selected','false');document.querySelector('#runSelect').hidden=true;document.querySelector('#replay').pause();document.querySelector('#replay').hidden=true;document.querySelector('#frame').hidden=frameSeen===0;document.querySelector('#empty').hidden=frameSeen!==0;document.querySelector('#evidenceSummary').textContent='';document.querySelector('#frameStatus').textContent=frameSeen?'LIVE '+frameSeen:'WAITING'}
function showReplay(){document.querySelector('#liveTab').setAttribute('aria-selected','false');document.querySelector('#replayTab').setAttribute('aria-selected','true');document.querySelector('#runSelect').hidden=false;document.querySelector('#frame').hidden=true;document.querySelector('#empty').hidden=history.length>0;document.querySelector('#frameStatus').textContent='REPLAY';renderReplay()}
function renderReplay(){const select=document.querySelector('#runSelect'),run=history[Number(select.value)||0],video=document.querySelector('#replay');if(!run){video.hidden=true;document.querySelector('#empty').hidden=false;document.querySelector('#empty').textContent=lang==='zh'?'没有可用的 GR00T 证据。':'No GR00T evidence is available.';return}video.src=api('/api/video/'+encodeURIComponent(run.webm||run.video));video.load();video.hidden=false;document.querySelector('#evidenceSummary').textContent=`Seed ${run.seed} | VP9/WebM | lift ${(run.maximum_lift_m*100).toFixed(1)} cm | stable placement ${run.stable_on_plate?'PASS':'FAIL'} | standing ${run.remained_standing?'PASS':'FAIL'}`}
async function loadHistory(){const r=await fetch(api('/api/history'),{cache:'no-store'});if(!r.ok)return;history=await r.json();const select=document.querySelector('#runSelect');select.innerHTML=history.map((run,index)=>`<option value="${index}">Seed ${run.seed} - ${run.stable_on_plate?'stable placement':'failed run'}</option>`).join('');const preferred=history.findIndex(run=>run.lifted&&run.stable_on_plate);select.value=String(preferred>=0?preferred:0)}
async function action(path){const r=await fetch(api(path),{method:'POST'});if(r.ok)poll()}async function poll(){try{const r=await fetch(api('/api/state'),{cache:'no-store'});if(r.ok)render(await r.json())}catch(e){}setTimeout(poll,500)}document.querySelector('#start').onclick=()=>{if(confirm(copy[lang].confirm))action('/api/run')};document.querySelector('#stop').onclick=()=>action('/api/stop');document.querySelector('#language').onclick=()=>{lang=lang==='zh'?'en':'zh';translate()};translate();poll();
document.querySelector('#liveTab').onclick=showLive;document.querySelector('#replayTab').onclick=showReplay;document.querySelector('#runSelect').onchange=renderReplay;loadHistory();
</script></body></html>"""


class ExperimentController:
    def __init__(self, project: Path, planner_base_url: str, planner_model: str, planner_provider: str, profile: str = "full-live", seed: int = 1002) -> None:
        self.project = project
        self.planner_base_url = planner_base_url
        self.planner_model = planner_model
        self.planner_provider = planner_provider
        self.profile = profile
        self.seed = seed
        self.lock = Lock()
        self.process: subprocess.Popen[str] | None = None
        self.stop_requested = False
        self.state = self._initial_state()

    def _initial_state(self) -> dict:
        readiness = self.readiness()
        return {"running": False, "accepted": None, "task_completed": None, "stopped": False, "profile": self.profile, "seed": self.seed, "ready": readiness["ready"], "readiness": readiness, "summary": "等待实验开始。" if readiness["ready"] else readiness["message"], "frame_version": 0, "log": [], "stages": [{"id": key, "name": name, "status": "pending", "detail": ""} for key, name in STAGES]}

    def readiness(self) -> dict[str, object]:
        if self.profile in {"groot-local", "groot-live-planner"}:
            checks = {
                "groot": (self.project / "simulation/vendor/Isaac-GR00T-N1.6/.venv/bin/python").is_file(),
                "wbc": (self.project / "simulation/vendor/GR00T-WholeBodyControl-N1.6/.venv_eval/bin/python").is_file(),
                "checkpoint": (self.project / "simulation/vendor/models/GR00T-N1.6-G1-PnPAppleToPlate-CW").is_dir(),
            }
            if self.profile == "groot-live-planner":
                checks.update(
                    planner_url=bool(self.planner_base_url),
                    planner_model=bool(self.planner_model),
                    planner_key=bool(os.getenv("S2A_PLANNER_API_KEY")),
                )
        else:
            checks = {
                "docker": shutil.which("docker") is not None,
                "planner_url": bool(self.planner_base_url),
                "planner_key": bool(os.getenv("S2A_PLANNER_API_KEY")),
            }
        missing = [name for name, available in checks.items() if not available]
        return {
            "ready": not missing,
            "checks": checks,
            "message": "运行环境未就绪：" + ", ".join(missing) if missing else "运行环境已就绪。",
        }

    def snapshot(self) -> dict:
        with self.lock:
            return json.loads(json.dumps(self.state))

    def update(self, stage: str, status: str, detail: str = "") -> None:
        with self.lock:
            item = next(x for x in self.state["stages"] if x["id"] == stage)
            if item["status"] == status and item["detail"] == detail:
                return
            item.update(status=status, detail=detail)
            prefix = f"[{stage}] "
            self.state["log"] = [line for line in self.state["log"] if not line.startswith(prefix)]
            suffix = f": {detail}" if detail else ""
            self.state["log"].append(f"{prefix}{status}{suffix}")

    def start(self) -> bool:
        with self.lock:
            if self.state["running"] or not self.state["ready"]:
                return False
            self.state = self._initial_state()
            self.state["running"] = True
            self.stop_requested = False
        Thread(target=self._run, daemon=True).start()
        return True

    def stop(self) -> bool:
        with self.lock:
            if not self.state["running"]:
                return False
            self.stop_requested = True
            process = self.process
            self.state.update(running=False, accepted=False, stopped=True, summary="仿真运行已由操作员停止。")
            self.state["log"].append("[operator] simulation stop requested")
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        return True

    def _command(self, command: list[str]) -> subprocess.Popen[str]:
        process = subprocess.Popen(command, cwd=self.project, env={**os.environ, "PYTHONPATH": str(self.project / "src")}, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        with self.lock:
            self.process = process
        return process

    def _run(self) -> None:
        if self.profile in {"groot-local", "groot-live-planner"}:
            self._run_groot_local()
            return
        try:
            if self.stop_requested:
                return
            self.update("dataset", "running", "PhysioNet/WFDB · MAMEM SSVEP")
            if self.stop_requested:
                return
            eeg = self._command([str(self.project / "simulation/run_public_ssvep.sh")])
            output, _ = eeg.communicate()
            if self.stop_requested:
                return
            if eeg.returncode:
                raise RuntimeError(output[-1000:] or "公开 EEG 实验失败")
            eeg_report = json.loads((self.project / "reports/eeg/public-ssvep.json").read_text())
            self.update("dataset", "completed", f"test windows={eeg_report['window_counts']['test']} · held-out={','.join(eeg_report['split']['test_subjects'])}")
            decoded = eeg_report["harness_replay"]["decoded_examples"]
            self.update("intent", "completed", f"select {decoded['select']['confidence']:.1%} · confirmation buffered {decoded['confirm']['confidence']:.1%}")

            for key in ("llm_planner", "vla", "skill_executor", "motion_control"):
                self.update(key, "running" if key == "llm_planner" else "pending")
            progress = self.project / "reports/simulation/experiment-progress.jsonl"
            progress.unlink(missing_ok=True)
            report = self.project / "reports/simulation/harness-public-eeg-live-g1.json"
            frame = self.project / "reports/simulation/g1-smolvla-frames/live.png"
            started = time()
            command = ["python3", "simulation/run_harness_unitree.py", "--task", "pick-place", "--policy", "smolvla", "--task-spec", "experiments/tasks/g1_pick_place.json", "--decoded-intents", "reports/eeg/public-ssvep.json", "--planner", "live", "--planner-provider", self.planner_provider, "--planner-base-url", self.planner_base_url, "--planner-model", self.planner_model, "--planner-output-mode", "prompt-json", "--planner-api-key-env", "S2A_PLANNER_API_KEY", "--progress-output", str(progress), "--output", str(report)]
            process = self._command(command)
            progress_lines = 0
            while process.poll() is None:
                if self.stop_requested:
                    return
                if progress.exists():
                    lines = progress.read_text().splitlines()
                    for line in lines[progress_lines:]:
                        event = json.loads(line)
                        detail = event.get("detail") or ""
                        if event["stage"] == "llm_planner" and isinstance(detail, dict):
                            detail = f"{detail.get('provider')} · {detail.get('model')} · {detail.get('latency_ms', '…')} ms"
                        self.update(event["stage"], event["status"], str(detail))
                    progress_lines = len(lines)
                if frame.exists() and frame.stat().st_mtime >= started:
                    for key in ("vla", "skill_executor", "motion_control"):
                        if next(x for x in self.state["stages"] if x["id"] == key)["status"] == "pending":
                            self.update(key, "running", "MuJoCo closed loop")
                    with self.lock:
                        self.state["frame_version"] = int(frame.stat().st_mtime_ns)
                sleep(0.25)
            output, _ = process.communicate()
            if self.stop_requested:
                return
            payload = json.loads(report.read_text())
            for stage in payload["intelligence_stages"]:
                if stage["id"] in {x[0] for x in STAGES}:
                    self.update(stage["id"], stage["status"], str(stage.get("output") or ""))
            accepted = bool(payload["accepted"] and process.returncode == 0)
            self.update("physical_verification", "completed" if accepted else "failed", payload["trace"][-1]["detail"])
            with self.lock:
                self.state.update(running=False, accepted=accepted, summary="真实全链路通过。" if accepted else "实验失败，请查看首个失败阶段。")
        except Exception as exc:
            with self.lock:
                for stage in self.state["stages"]:
                    if stage["status"] == "running":
                        stage.update(status="failed", detail=str(exc))
                self.state.update(running=False, accepted=False, summary=str(exc))
                self.state["log"].append(f"[error] {type(exc).__name__}: {exc}")
        finally:
            with self.lock:
                self.process = None

    def _run_groot_local(self) -> None:
        try:
            self.update("dataset", "completed", "Local scripted intent profile")
            self.update("intent", "completed", "select apple + confirm")
            live_planner = self.profile == "groot-live-planner"
            planner_detail = (
                f"{self.planner_provider} · {self.planner_model}"
                if live_planner
                else "MockPlanner + typed TaskSpec"
            )
            self.update("llm_planner", "running" if live_planner else "completed", planner_detail)
            self.update("plan_review", "completed", "apple -> plate authorized")
            for key in ("vla", "skill_executor", "motion_control"):
                self.update(key, "running", "GR00T N1.6 + official WBC")
            progress = self.project / "reports/simulation/experiment-progress.jsonl"
            report = self.project / "reports/simulation/harness-console-groot.json"
            progress.unlink(missing_ok=True)
            report.unlink(missing_ok=True)
            command = ["python3", "simulation/run_harness_unitree.py", "--task", "pick-place", "--policy", "groot", "--planner", "live" if live_planner else "mock", "--seed", str(self.seed), "--progress-output", str(progress), "--output", str(report)]
            if live_planner:
                command.extend(["--planner-provider", self.planner_provider, "--planner-base-url", self.planner_base_url, "--planner-model", self.planner_model, "--planner-output-mode", "prompt-json", "--planner-api-key-env", "S2A_PLANNER_API_KEY"])
            process = self._command(command)
            output, _ = process.communicate()
            if self.stop_requested:
                return
            if not report.exists():
                raise RuntimeError(output[-1000:] or "GR00T local run failed")
            payload = json.loads(report.read_text())
            accepted = bool(payload["accepted"])
            stage_results = {stage["id"]: stage["status"] for stage in payload["intelligence_stages"]}
            planner_stage = next(stage for stage in payload["intelligence_stages"] if stage["id"] == "llm_planner")
            self.update("llm_planner", planner_stage["status"], planner_detail)
            for key in ("vla", "skill_executor", "motion_control"):
                self.update(key, stage_results.get(key, "failed"), "GR00T N1.6 + official WBC")
            outcome_path = self.project / "reports/simulation/g1-groot-closed-loop.json"
            outcome = json.loads(outcome_path.read_text()) if outcome_path.exists() else {}
            detail = payload["trace"][-1]["detail"]
            if not accepted and outcome:
                detail = (
                    f"grasp={outcome.get('maximum_consecutive_grasp_steps', 0)} steps · "
                    f"lift={100 * outcome.get('maximum_lift_m', 0):.2f}/10.00 cm · "
                    f"plate={'yes' if outcome.get('stable_on_target') else 'no'}"
                )
            task_completed = bool(
                outcome.get("official_contact_success")
                and outcome.get("grasped")
                and outcome.get("released")
                and outcome.get("stable_on_target")
                and outcome.get("remained_standing")
            )
            self.update("physical_verification", "completed" if accepted else "failed", detail)
            with self.lock:
                summary = (
                    f"GR00T Seed {self.seed} local loop passed."
                    if accepted
                    else f"Physical verification failed: {detail}."
                )
                self.state.update(
                    running=False,
                    accepted=accepted,
                    task_completed=task_completed,
                    summary=summary,
                )
        except Exception as exc:
            with self.lock:
                for stage in self.state["stages"]:
                    if stage["status"] == "running":
                        stage.update(status="failed", detail=str(exc))
                self.state.update(running=False, accepted=False, summary=str(exc))
                self.state["log"].append(f"[error] {type(exc).__name__}: {exc}")
        finally:
            with self.lock:
                self.process = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive Synapse2Action experiment console")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--planner-base-url", default="")
    parser.add_argument("--planner-model", default="/model")
    parser.add_argument("--planner-provider", default="yuesheng-vllm")
    parser.add_argument("--profile", choices=("groot-local", "groot-live-planner", "full-live"), default="groot-local")
    parser.add_argument("--seed", type=int, default=1002)
    parser.add_argument("--access-token", required=True)
    args = parser.parse_args()
    if args.profile in {"groot-live-planner", "full-live"} and not args.planner_base_url:
        parser.error(f"--profile {args.profile} requires --planner-base-url")
    project = Path(__file__).resolve().parents[1]
    controller = ExperimentController(project, args.planner_base_url, args.planner_model, args.planner_provider, args.profile, args.seed)

    class Handler(BaseHTTPRequestHandler):
        def authorized(self) -> bool:
            supplied = dict(item.split("=", 1) for item in urlparse(self.path).query.split("&") if "=" in item).get("token", "")
            return hmac.compare_digest(supplied, args.access_token)
        def send(self, status: int, kind: str, body: bytes) -> None:
            self.send_response(status); self.send_header("Content-Type", kind); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
        def send_video(self, path: Path) -> None:
            size = path.stat().st_size
            requested = self.headers.get("Range")
            try:
                start, end, partial = parse_byte_range(requested, size)
            except (ValueError, TypeError):
                self.send(416, "text/plain", b"invalid range")
                return
            length = end - start + 1
            self.send_response(206 if partial else 200)
            self.send_header("Content-Type", "video/webm" if path.suffix == ".webm" else "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Cache-Control", "private, max-age=3600")
            self.end_headers()
            with path.open("rb") as stream:
                stream.seek(start)
                try:
                    remaining = length
                    while remaining:
                        chunk = stream.read(min(256 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        def do_GET(self) -> None:
            if not self.authorized(): self.send(401, "text/plain", b"unauthorized"); return
            path = urlparse(self.path).path
            if path == "/": self.send(200, "text/html; charset=utf-8", console_html().encode())
            elif path == "/api/state": self.send(200, "application/json", json.dumps(controller.snapshot()).encode())
            elif path == "/api/history": self.send(200, "application/json", json.dumps(groot_history(project)).encode())
            elif path == "/api/frame":
                frame = project / "reports/simulation/g1-smolvla-frames/live.png"
                self.send(200, "image/png", frame.read_bytes()) if frame.exists() else self.send(404, "text/plain", b"no frame")
            elif path.startswith("/api/video/"):
                name = path.removeprefix("/api/video/")
                directory = project / "reports/simulation" / ("groot-evidence-video-web" if name.endswith(".webm") else "groot-evidence-video")
                video = directory / name
                if video.parent == directory and video.suffix in {".mp4", ".webm"} and video.is_file():
                    self.send_video(video)
                else:
                    self.send(404, "text/plain", b"not found")
            else: self.send(404, "text/plain", b"not found")
        def do_POST(self) -> None:
            if not self.authorized(): self.send(401, "application/json", b'{"error":"unauthorized"}'); return
            path = urlparse(self.path).path
            if path == "/api/run": self.send(202 if controller.start() else 409, "application/json", json.dumps({"started": controller.snapshot()["running"]}).encode())
            elif path == "/api/stop": self.send(202 if controller.stop() else 409, "application/json", json.dumps({"stopped": controller.snapshot()["stopped"]}).encode())
            else: self.send(404, "text/plain", b"not found")
        def log_message(self, format: str, *args: object) -> None: pass

    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
