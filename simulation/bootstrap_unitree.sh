#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
vendor_dir="${root_dir}/simulation/vendor"

clone_at() {
  local repository="$1"
  local commit="$2"
  local destination="$3"
  if [[ ! -d "${destination}/.git" ]]; then
    git clone "${repository}" "${destination}"
  fi
  git -C "${destination}" fetch origin "${commit}"
  git -C "${destination}" checkout --detach "${commit}"
}

mkdir -p "${vendor_dir}"
clone_at \
  https://github.com/unitreerobotics/unitree_sdk2_python.git \
  65691c8a8bc53b98d3976dba4dbf9d5d20b2e7f5 \
  "${vendor_dir}/unitree_sdk2_python"
clone_at \
  https://github.com/unitreerobotics/unitree_mujoco.git \
  4134cb5dc7ff1ba7f484deda48b5274b58694519 \
  "${vendor_dir}/unitree_mujoco"
clone_at \
  https://github.com/unitreerobotics/unitree_rl_lab.git \
  4960b84732b0c2ec593dccbfe963fda1bcd7b1e3 \
  "${vendor_dir}/unitree_rl_lab"

python3 -m pip install -e "${vendor_dir}/unitree_sdk2_python"
python3 -m pip install mujoco pygame

echo "Pinned Unitree SDK2 and MuJoCo sources are ready in ${vendor_dir}"
