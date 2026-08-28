from __future__ import annotations

import argparse
import hmac
import json
import os
from pathlib import Path
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


def console_html() -> str:
    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Synapse2Action 实验控制台</title><style>
:root{color-scheme:dark;--bg:#020617;--card:#0f172a;--line:#334155;--text:#f8fafc;--muted:#94a3b8;--ok:#4ade80;--run:#22d3ee;--wait:#64748b;--bad:#f87171}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}main{width:min(1400px,calc(100% - 28px));margin:auto;padding:24px 0 48px}header,.actions,.statusline{display:flex;align-items:center;justify-content:space-between;gap:16px}h1{margin:0;font-size:clamp(1.8rem,4vw,3rem);letter-spacing:-.04em}p{color:var(--muted)}button{min-height:48px;padding:10px 20px;border:1px solid var(--line);border-radius:9px;background:var(--ok);color:#052e16;font-weight:800;cursor:pointer}#language{background:var(--card);color:var(--text)}button:disabled{opacity:.45;cursor:not-allowed}.layout{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(350px,.8fr);gap:14px;margin-top:18px}.card{border:1px solid var(--line);border-radius:14px;background:var(--card);padding:16px}.viewer{position:relative;aspect-ratio:16/9;background:#050a14;border-radius:10px;overflow:hidden}.viewer img{width:100%;height:100%;object-fit:cover}.viewer .empty{position:absolute;inset:0;display:grid;place-items:center;color:var(--muted)}.live{color:var(--run);font:700 .75rem ui-monospace,monospace}.stages{display:grid;gap:8px}.stage{display:grid;grid-template-columns:32px 1fr auto;gap:10px;align-items:center;padding:11px;border:1px solid var(--line);border-radius:9px}.num{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#1e293b;font:700 .75rem ui-monospace,monospace}.stage b{display:block}.stage small{color:var(--muted)}.pill{padding:3px 7px;border-radius:5px;background:#1e293b;color:var(--wait);font:700 .65rem ui-monospace,monospace}.stage.running{border-color:var(--run)}.stage.running .pill{color:var(--run)}.stage.completed{border-color:#166534}.stage.completed .pill{color:var(--ok)}.stage.failed{border-color:#991b1b}.stage.failed .pill{color:var(--bad)}pre{max-height:180px;overflow:auto;margin:10px 0 0;padding:12px;border-radius:8px;background:#050a14;color:#cbd5e1;font:12px/1.5 ui-monospace,monospace;white-space:pre-wrap}.source{margin-top:12px;padding:10px;border-left:3px solid var(--run);background:#071525;color:#cbd5e1}.result{margin-top:14px}.ok{color:var(--ok)}.bad{color:var(--bad)}@media(max-width:900px){.layout{grid-template-columns:1fr}header{display:block}.actions{margin-top:14px}}@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body><main><header><div><div class="live">INTERACTIVE · LOCAL EXPERIMENT</div><h1 data-i18n="title">Synapse2Action 实验控制台</h1><p data-i18n="subtitle">从开源 EEG 数据开始，实时运行 DeepSeek、SmolVLA、SDK2 与 MuJoCo。</p></div><div class="actions"><button id="language" type="button">EN</button><button id="start" data-i18n="start">开始真实实验</button></div></header><div class="source"><b data-i18n="source">数据源：</b>MAMEM SSVEP Database（PhysioNet/WFDB） · <span data-i18n="subjects">受试者 001–004 · 留出受试者 004</span></div><div class="layout"><section class="card"><div class="statusline"><h2 data-i18n="viewer">MuJoCo 实时环境</h2><span class="live" id="frameStatus">WAITING</span></div><div class="viewer"><img id="frame" hidden alt="MuJoCo G1 live simulation"><div class="empty" id="empty" data-i18n="empty">点击“开始真实实验”后显示运行画面</div></div><div class="result"><b id="verdict"></b><p id="summary"></p></div><pre id="log">Ready.</pre></section><aside class="card"><h2 data-i18n="stages">运行阶段</h2><div class="stages" id="stages"></div></aside></div></main><script>
const copy={zh:{title:'Synapse2Action 实验控制台',subtitle:'从开源 EEG 数据开始，实时运行 DeepSeek、SmolVLA、SDK2 与 MuJoCo。',start:'开始真实实验',source:'数据源：',subjects:'受试者 001–004 · 留出受试者 004',viewer:'MuJoCo 实时环境',empty:'点击“开始真实实验”后显示运行画面',stages:'运行阶段',running:'实验运行中',success:'实验成功',failed:'实验失败',idle:'尚未运行',waiting:'等待实验开始。',successSummary:'八个阶段全部通过。',failedSummary:'物理闭环未通过，请查看失败阶段和实时画面。',labels:{dataset:['开源 EEG 数据','读取 MAMEM 原始记录'],intent:['EEG 目标选择','解码选择意图并暂存确认输入'],llm_planner:['真实 LLM 规划','DeepSeek 输出结构化技能'],plan_review:['计划审阅与确认','展示已校验计划后再确认执行'],vla:['视觉动作模型','SmolVLA 读取相机与关节状态'],skill_executor:['技能执行器','C++ Behavior 生成受约束目标'],motion_control:['机器人控制','RL Controller + SDK2 LowCmd'],physical_verification:['物理验证','MuJoCo 检查抓取、抬升与落盘']}},en:{title:'Synapse2Action Experiment Console',subtitle:'Start with open EEG data, then run DeepSeek, SmolVLA, SDK2, and MuJoCo live.',start:'Start real experiment',source:'Data source:',subjects:'Subjects 001–004 · held-out subject 004',viewer:'Live MuJoCo environment',empty:'Start the real experiment to see the running environment',stages:'Run stages',running:'Experiment running',success:'Experiment succeeded',failed:'Experiment failed',idle:'Not started',waiting:'Waiting to start.',successSummary:'All eight stages passed.',failedSummary:'The physical loop failed. Inspect the failed stage and live view.',labels:{dataset:['Open EEG data','Read raw MAMEM records'],intent:['EEG target selection','Decode selection and hold confirmation input'],llm_planner:['Live LLM planning','DeepSeek emits a typed skill'],plan_review:['Plan review and confirmation','Confirm only after reviewing the validated plan'],vla:['Vision-action model','SmolVLA reads cameras and joint state'],skill_executor:['Skill executor','C++ Behavior emits constrained targets'],motion_control:['Robot control','RL Controller + SDK2 LowCmd'],physical_verification:['Physical verification','MuJoCo checks grasp, lift, and placement']}}};let lang=(navigator.language||'').startsWith('zh')?'zh':'en',frameSeen=0,lastState=null;const token=new URLSearchParams(location.search).get('token')||'',api=path=>path+'?token='+encodeURIComponent(token);
function translate(){const t=copy[lang];document.documentElement.lang=lang==='zh'?'zh-CN':'en';document.querySelectorAll('[data-i18n]').forEach(x=>x.textContent=t[x.dataset.i18n]);document.querySelector('#language').textContent=lang==='zh'?'EN':'中文';if(lastState)render(lastState)}
function render(s){lastState=s;const t=copy[lang],labels=t.labels;document.querySelector('#start').disabled=s.running;document.querySelector('#stages').innerHTML=s.stages.map((x,i)=>`<div class="stage ${x.status}"><span class="num">${i+1}</span><span><b>${labels[x.id][0]}</b><small>${x.detail||labels[x.id][1]}</small></span><span class="pill">${x.status.toUpperCase()}</span></div>`).join('');document.querySelector('#log').textContent=s.log.join('\\n')||'Ready.';const v=document.querySelector('#verdict');v.textContent=s.running?t.running:s.accepted===true?t.success:s.accepted===false?t.failed:t.idle;v.className=s.accepted===true?'ok':s.accepted===false?'bad':'';document.querySelector('#summary').textContent=s.accepted===true?t.successSummary:s.accepted===false?t.failedSummary:t.waiting;if(s.frame_version>frameSeen){frameSeen=s.frame_version;const img=document.querySelector('#frame');img.src=api('/api/frame')+'&v='+frameSeen;img.hidden=false;document.querySelector('#empty').hidden=true;document.querySelector('#frameStatus').textContent='LIVE · '+frameSeen}}
async function poll(){try{const r=await fetch(api('/api/state'),{cache:'no-store'});if(r.ok)render(await r.json())}catch(e){}setTimeout(poll,500)}document.querySelector('#start').onclick=async()=>{await fetch(api('/api/run'),{method:'POST'});poll()};document.querySelector('#language').onclick=()=>{lang=lang==='zh'?'en':'zh';translate()};translate();poll();
</script></body></html>"""


class ExperimentController:
    def __init__(self, project: Path, planner_base_url: str, planner_model: str, planner_provider: str) -> None:
        self.project = project
        self.planner_base_url = planner_base_url
        self.planner_model = planner_model
        self.planner_provider = planner_provider
        self.lock = Lock()
        self.state = self._initial_state()

    def _initial_state(self) -> dict:
        return {"running": False, "accepted": None, "summary": "等待实验开始。", "frame_version": 0, "log": [], "stages": [{"id": key, "name": name, "status": "pending", "detail": ""} for key, name in STAGES]}

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
            if self.state["running"]:
                return False
            self.state = self._initial_state()
            self.state["running"] = True
        Thread(target=self._run, daemon=True).start()
        return True

    def _command(self, command: list[str]) -> subprocess.Popen[str]:
        return subprocess.Popen(command, cwd=self.project, env={**os.environ, "PYTHONPATH": str(self.project / "src")}, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def _run(self) -> None:
        try:
            self.update("dataset", "running", "PhysioNet/WFDB · MAMEM SSVEP")
            eeg = self._command([str(self.project / "simulation/run_public_ssvep.sh")])
            output, _ = eeg.communicate()
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
                self.state.update(running=False, accepted=False, summary=str(exc))
                self.state["log"].append(f"[error] {type(exc).__name__}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive Synapse2Action experiment console")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--planner-base-url", required=True)
    parser.add_argument("--planner-model", default="/model")
    parser.add_argument("--planner-provider", default="yuesheng-vllm")
    parser.add_argument("--access-token", required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    controller = ExperimentController(project, args.planner_base_url, args.planner_model, args.planner_provider)

    class Handler(BaseHTTPRequestHandler):
        def authorized(self) -> bool:
            supplied = dict(item.split("=", 1) for item in urlparse(self.path).query.split("&") if "=" in item).get("token", "")
            return hmac.compare_digest(supplied, args.access_token)
        def send(self, status: int, kind: str, body: bytes) -> None:
            self.send_response(status); self.send_header("Content-Type", kind); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
        def do_GET(self) -> None:
            if not self.authorized(): self.send(401, "text/plain", b"unauthorized"); return
            path = urlparse(self.path).path
            if path == "/": self.send(200, "text/html; charset=utf-8", console_html().encode())
            elif path == "/api/state": self.send(200, "application/json", json.dumps(controller.snapshot()).encode())
            elif path == "/api/frame":
                frame = project / "reports/simulation/g1-smolvla-frames/live.png"
                self.send(200, "image/png", frame.read_bytes()) if frame.exists() else self.send(404, "text/plain", b"no frame")
            else: self.send(404, "text/plain", b"not found")
        def do_POST(self) -> None:
            if not self.authorized(): self.send(401, "application/json", b'{"error":"unauthorized"}'); return
            if urlparse(self.path).path == "/api/run": self.send(202 if controller.start() else 409, "application/json", json.dumps({"started": controller.state["running"]}).encode())
            else: self.send(404, "text/plain", b"not found")
        def log_message(self, format: str, *args: object) -> None: pass

    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
