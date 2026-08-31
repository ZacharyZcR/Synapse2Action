#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
vendor_dir="${root_dir}/simulation/vendor"
lock_file="${root_dir}/simulation/whole_body.lock.json"

[[ "$(uname -s)" == "Linux" ]] || {
  echo "OpenWBT/OpenTrack G1 deployment requires Linux; current OS: $(uname -s)" >&2
  exit 2
}
command -v git >/dev/null || { echo "missing dependency: git" >&2; exit 2; }
command -v python3 >/dev/null || { echo "missing dependency: python3" >&2; exit 2; }

clone_locked() {
  local key="$1"
  local destination="$2"
  local repository commit actual
  repository="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]]["repository"])' "${lock_file}" "${key}")"
  commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]]["commit"])' "${lock_file}" "${key}")"
  if [[ ! -d "${destination}/.git" ]]; then
    GIT_LFS_SKIP_SMUDGE=1 git clone --filter=blob:none "${repository}" "${destination}"
  fi
  git -C "${destination}" fetch --depth 1 origin "${commit}"
  git -C "${destination}" checkout --detach "${commit}"
  actual="$(git -C "${destination}" rev-parse HEAD)"
  [[ "${actual}" == "${commit}" ]] || {
    echo "checkout mismatch for ${key}: expected ${commit}, got ${actual}" >&2
    exit 2
  }
  echo "verified ${key}: ${actual}"
}

mkdir -p "${vendor_dir}"
clone_locked open_wbt "${vendor_dir}/OpenWBT"
clone_locked open_track "${vendor_dir}/OpenTrack"
clone_locked unitree_rl_gym "${vendor_dir}/unitree_rl_gym"
clone_locked unitree_rl_lab "${vendor_dir}/unitree_rl_lab"
clone_locked unitree_mujoco "${vendor_dir}/unitree_mujoco"

echo "Whole-body candidate sources are staged. No dependency, checkpoint, or robot command was installed or executed."
echo "Run check_whole_body_readiness.py before selecting an experiment profile."
