#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
vendor_dir="${root_dir}/simulation/vendor"
lock_file="${root_dir}/simulation/openpi.lock.json"
destination="${vendor_dir}/openpi"

command -v git >/dev/null || { echo "missing dependency: git" >&2; exit 2; }
command -v python3 >/dev/null || { echo "missing dependency: python3" >&2; exit 2; }

repository="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["openpi"]["repository"])' "${lock_file}")"
commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["openpi"]["commit"])' "${lock_file}")"

mkdir -p "${vendor_dir}"
if [[ ! -d "${destination}/.git" ]]; then
  GIT_LFS_SKIP_SMUDGE=1 git clone --filter=blob:none "${repository}" "${destination}"
fi
git -C "${destination}" fetch --depth 1 origin "${commit}"
git -C "${destination}" checkout --detach "${commit}"
git -C "${destination}" submodule update --init --recursive --depth 1

actual="$(git -C "${destination}" rev-parse HEAD)"
[[ "${actual}" == "${commit}" ]] || {
  echo "OpenPI checkout mismatch: expected ${commit}, got ${actual}" >&2
  exit 2
}

echo "OpenPI source is ready at ${destination}"
echo "Pinned commit: ${actual}"
echo "No model checkpoint or Python dependency was installed."
