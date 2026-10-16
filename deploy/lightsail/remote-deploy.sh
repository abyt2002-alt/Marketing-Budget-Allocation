#!/bin/bash
# Activate one immutable MMM release as the deploy user.
# Persistent environment files and migration backups are linked or left untouched.
set -euo pipefail
umask 027

SHA="${1:?commit sha required}"
TARBALL="${2:?tarball required}"
SUPPORT="${3:?support directory required}"
APP_ROOT=/opt/apps/mmm-app
RELEASE="${APP_ROOT}/releases/${SHA}"
CURRENT="${APP_ROOT}/current"
LOG="${APP_ROOT}/deploy-history.log"
PM2=/usr/local/bin/pm2
export PATH="/usr/local/bin:${PATH}"
export HOME=/home/deploy
export PM2_HOME=/home/deploy/.pm2

APPS=(mmm-backend)
PROTECTED=(
  "${APP_ROOT}/marketing-budget-allocation-backend/.env"
  "${APP_ROOT}/marketing-budget-allocation-frontend/.env"
)
SNAPSHOT=""
ACTIVATED=0
RESULT=FAILURE
PREV=""
DUMP_BACKUP=""

[[ "${SHA}" =~ ^[0-9a-f]{40}$ ]] || { echo "refusing non-sha release name"; exit 1; }
[[ "$(id -un)" == "deploy" ]] || { echo "this script must run as deploy"; exit 1; }
[[ -f "${TARBALL}" && -d "${SUPPORT}" ]] || { echo "missing upload"; exit 1; }

record() {
  printf '%s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${SHA}" "${RESULT}" >> "${LOG}"
  chmod 640 "${LOG}" || true
  echo "DEPLOY_RESULT sha=${SHA} time=$(date -u +%Y-%m-%dT%H:%M:%SZ) result=${RESULT}"
}

cleanup_upload() {
  local dir
  dir="$(dirname "${TARBALL}")"
  case "${dir}" in
    /tmp/lightsail-${SHA}) rm -rf "${dir}" ;;
  esac
}

snapshot_protected() {
  SNAPSHOT="$(mktemp)"
  : > "${SNAPSHOT}"
  local path
  for path in "${PROTECTED[@]}"; do
    [[ -f "${path}" && ! -L "${path}" ]] || { echo "protected file missing: ${path}"; exit 1; }
    sha256sum "${path}" >> "${SNAPSHOT}"
  done
  find /var/backups -maxdepth 1 -type d -name 'migration-*' -printf '%f\n' | sort >> "${SNAPSHOT}"
}

protected_unchanged() {
  local now path
  now="$(mktemp)"
  for path in "${PROTECTED[@]}"; do
    sha256sum "${path}" >> "${now}"
  done
  find /var/backups -maxdepth 1 -type d -name 'migration-*' -printf '%f\n' | sort >> "${now}"
  if ! cmp -s "${SNAPSHOT}" "${now}"; then
    echo "protected data changed during deployment"
    rm -f "${now}"
    return 1
  fi
  rm -f "${now}"
}

on_exit() {
  local status=$?
  set +e
  if [[ "${status}" -ne 0 && "${ACTIVATED}" -eq 1 && -n "${PREV}" ]]; then
    ln -sfn "${PREV}" "${CURRENT}"
    local app
    for app in "${APPS[@]}"; do
      "${PM2}" delete "${app}" || true
    done
    if [[ -n "${DUMP_BACKUP}" && -f "${DUMP_BACKUP}" ]]; then
      cp "${DUMP_BACKUP}" "${PM2_HOME}/dump.pm2"
    fi
    "${PM2}" resurrect || true
    RESULT=ROLLBACK
  elif [[ "${status}" -ne 0 ]]; then
    RESULT=FAILURE
  fi
  record
  cleanup_upload
  if [[ -n "${SNAPSHOT}" ]]; then
    rm -f "${SNAPSHOT}"
  fi
}
trap on_exit EXIT

reject_tarball() {
  if tar -tzf "${TARBALL}" | grep -E '^\.\./|^/|(^|/)\.\.(/|$)|(^|/)\.env($|\.)|(^|/)analysis_state\.db$|(^|/)app_data\.db$|(^|/)demo_data(/|$)'; then
    echo "tarball contains an unsafe or protected path"
    exit 1
  fi
}

replace_with_link() {
  local relative="$1"
  local persistent="$2"
  local dest="${RELEASE}/${relative}"
  [[ -e "${persistent}" && ! -L "${persistent}" ]] || { echo "missing persistent file ${persistent}"; exit 1; }
  if [[ -e "${dest}" || -L "${dest}" ]]; then
    local real
    real="$(readlink -f "${dest}")"
    case "${real}" in
      "${RELEASE}"|"${RELEASE}"/*) rm -f "${dest}" ;;
      *) echo "refusing to remove ${dest}"; exit 1 ;;
    esac
  fi
  mkdir -p "$(dirname "${dest}")"
  ln -s "${persistent}" "${dest}"
  [[ "$(stat -c %i "${dest}")" == "$(stat -c %i "${persistent}")" ]] || { echo "link mismatch ${relative}"; exit 1; }
}

publish_dist() {
  local dist="$1"
  [[ -f "${dist}/index.html" ]] || { echo "missing ${dist}/index.html"; exit 1; }
  find "${dist}" -type d -exec chmod 755 {} +
  find "${dist}" -type f -exec chmod 644 {} +
}

require_loopback() {
  local port="$1"
  ss -ltn | grep -q "127.0.0.1:${port}" || { echo "port ${port} is not listening"; return 1; }
  if ss -ltn | grep -E "0\\.0\\.0\\.0:${port}([^0-9]|$)|\\[::\\]:${port}([^0-9]|$)|\\*:${port}([^0-9]|$)"; then
    echo "port ${port} is exposed beyond loopback"
    return 1
  fi
}

http_ok() {
  local url="$1"
  shift
  local attempt
  for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
    if curl -fsS --max-time 20 -o /dev/null "$@"; then
      return 0
    fi
    sleep 2
  done
  echo "health check failed: ${url}"
  return 1
}

health_checks() {
  require_loopback 8022
  http_ok "backend-health" "http://127.0.0.1:8022/health"
  http_ok "backend-cache" "http://127.0.0.1:8022/api/insights-cache-status"
  http_ok "public-root" --resolve "mmm.quantmatrix.ai:443:3.7.218.242" "https://mmm.quantmatrix.ai/"
  http_ok "public-cache" --resolve "mmm.quantmatrix.ai:443:3.7.218.242" "https://mmm.quantmatrix.ai/api/insights-cache-status"
  http_ok "public-config" --resolve "mmm.quantmatrix.ai:443:3.7.218.242" "https://mmm.quantmatrix.ai/api/auto-config"
  python3 - <<'PY'
import json, os, subprocess, sys
raw = subprocess.check_output(["/usr/local/bin/pm2", "jlist"])
link = "/opt/apps/mmm-app/current/marketing-budget-allocation-backend"
allowed = {link, os.path.realpath(link)}
found = False
for proc in json.loads(raw):
    if proc.get("name") == "mmm-backend":
        found = True
        if proc.get("pm2_env", {}).get("status") != "online":
            sys.exit("mmm-backend is not online")
        if proc.get("pm2_env", {}).get("pm_cwd", "") not in allowed:
            sys.exit("mmm-backend cwd is not the current release")
if not found:
    sys.exit("mmm-backend is missing")
PY
}

snapshot_protected
reject_tarball

if [[ -d "${RELEASE}" && "$(readlink -f "${CURRENT}")" == "${RELEASE}" ]]; then
  echo "release ${SHA} is already active; checking health without changing files"
  health_checks
  protected_unchanged
  RESULT=SUCCESS
  exit 0
fi
if [[ -e "${RELEASE}" ]]; then
  echo "release directory already exists; refusing to overwrite ${RELEASE}"
  exit 1
fi
PREV="$(readlink -f "${CURRENT}")"
[[ -d "${PREV}" ]] || { echo "current release is missing"; exit 1; }

mkdir -p "${RELEASE}/runtime"
tar --no-same-owner --no-same-permissions -xzf "${TARBALL}" -C "${RELEASE}"
replace_with_link "marketing-budget-allocation-backend/.env" "${APP_ROOT}/marketing-budget-allocation-backend/.env"
replace_with_link "marketing-budget-allocation-frontend/.env" "${APP_ROOT}/marketing-budget-allocation-frontend/.env"

python3 -m venv "${RELEASE}/.venvs/backend"
"${RELEASE}/.venvs/backend/bin/pip" install --disable-pip-version-check --no-input -r "${SUPPORT}/constraints-backend.txt"
cat > "${RELEASE}/runtime/backend.py" <<PY
import os
import sys
app_dir = "${APP_ROOT}/current/marketing-budget-allocation-backend"
os.chdir(app_dir)
os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8022"])
PY

npm ci --legacy-peer-deps --prefix "${RELEASE}/marketing-budget-allocation-frontend"
npm run build --prefix "${RELEASE}/marketing-budget-allocation-frontend"
publish_dist "${RELEASE}/marketing-budget-allocation-frontend/dist"
chmod 755 "${RELEASE}" "${RELEASE}/marketing-budget-allocation-frontend"

if [[ -x /usr/bin/sudo ]] && sudo -n /usr/sbin/nginx -t; then
  echo "nginx configuration test passed"
else
  echo "deploy cannot run nginx -t; checking the existing site still targets current"
  grep -q "/opt/apps/mmm-app/current/" /etc/nginx/sites-enabled/mmm
fi

cat > "${RELEASE}/runtime/ecosystem.config.js" <<EOF
module.exports = {
  apps: [
    { name: "mmm-backend", cwd: "${APP_ROOT}/current/marketing-budget-allocation-backend", script: "${RELEASE}/.venvs/backend/bin/python", args: "${RELEASE}/runtime/backend.py", interpreter: "none", exec_mode: "fork", autorestart: true, max_restarts: 3, min_uptime: 5000 }
  ]
};
EOF

DUMP_BACKUP="${PM2_HOME}/dump.pm2.before-${SHA}"
if [[ -f "${PM2_HOME}/dump.pm2" ]]; then
  cp "${PM2_HOME}/dump.pm2" "${DUMP_BACKUP}"
fi
ACTIVATED=1
ln -sfn "${RELEASE}" "${CURRENT}"
"${PM2}" delete mmm-backend || true
"${PM2}" start "${RELEASE}/runtime/ecosystem.config.js"
sleep 5
health_checks
protected_unchanged
"${PM2}" save
RESULT=SUCCESS
ACTIVATED=0
