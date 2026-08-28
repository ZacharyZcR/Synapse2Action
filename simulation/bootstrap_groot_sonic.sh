#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
vendor_dir="${root_dir}/simulation/vendor"
lock_file="${root_dir}/simulation/groot_sonic.lock.json"

[[ "$(uname -s)" == "Linux" ]] || {
  echo "GR00T + SONIC deployment requires Linux; current OS: $(uname -s)" >&2
  exit 2
}
command -v git >/dev/null || { echo "missing dependency: git" >&2; exit 2; }
command -v python3 >/dev/null || { echo "missing dependency: python3" >&2; exit 2; }
python3 -c 'import huggingface_hub' 2>/dev/null || {
  echo "missing Python dependency: huggingface_hub" >&2
  echo "install it in the active environment: python3 -m pip install huggingface_hub" >&2
  exit 2
}

mkdir -p "${vendor_dir}"

clone_locked() {
  local key="$1"
  local destination="$2"
  local repository commit
  repository="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]]["repository"])' "${lock_file}" "${key}")"
  commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]]["commit"])' "${lock_file}" "${key}")"
  if [[ ! -d "${destination}/.git" ]]; then
    GIT_LFS_SKIP_SMUDGE=1 git clone --filter=blob:none "${repository}" "${destination}"
  fi
  git -C "${destination}" fetch --depth 1 origin "${commit}"
  git -C "${destination}" checkout --detach "${commit}"
}

clone_locked isaac_groot "${vendor_dir}/Isaac-GR00T"
clone_locked groot_whole_body_control "${vendor_dir}/GR00T-WholeBodyControl"

python3 "${vendor_dir}/GR00T-WholeBodyControl/download_from_hf.py" --sonic-v1-1 --no-planner

python3 - "${lock_file}" "${vendor_dir}/GR00T-WholeBodyControl/gear_sonic_deploy/policy/sonic_v1_1" <<'PY'
import hashlib
import json
import pathlib
import sys

lock = json.loads(pathlib.Path(sys.argv[1]).read_text())
model_dir = pathlib.Path(sys.argv[2])
for name, metadata in lock["sonic_v1_1"]["files"].items():
    path = model_dir / pathlib.Path(name).name
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != metadata["sha256"]:
        raise SystemExit(f"checksum mismatch: {path}")
    print(f"verified {path.name}: {digest}")
PY

echo "GR00T + SONIC sources and deployment weights are ready."
echo "Continue with the upstream Ubuntu/CUDA build before running MuJoCo sim2sim."
