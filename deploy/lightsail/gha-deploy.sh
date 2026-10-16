#!/bin/bash
# Upload one packed revision and run the server-side release script.
# Requires GIT_SHA, LIGHTSAIL_HOST, EXPECTED_FINGERPRINT, LIGHTSAIL_SSH_KEY,
# and LIGHTSAIL_HOST_FINGERPRINT. Never prints the private key.
set -euo pipefail
cd "${GITHUB_WORKSPACE:?}"

[[ "${GIT_SHA}" =~ ^[0-9a-f]{40}$ ]] || { echo "git_sha must be a full commit SHA"; exit 1; }
[[ -n "${LIGHTSAIL_SSH_KEY}" ]] || { echo "LIGHTSAIL_SSH_KEY is not set"; exit 1; }
[[ -n "${LIGHTSAIL_HOST_FINGERPRINT}" ]] || { echo "LIGHTSAIL_HOST_FINGERPRINT is not set"; exit 1; }

fingerprint="${LIGHTSAIL_HOST_FINGERPRINT}"
case "${fingerprint}" in
  SHA256:*) ;;
  *) fingerprint="SHA256:${fingerprint}" ;;
esac
[[ "${fingerprint}" == "${EXPECTED_FINGERPRINT}" ]] || { echo "host fingerprint secret does not match the pinned fingerprint"; exit 1; }

install -m 700 -d "${HOME}/.ssh"
printf '%s\n' "${LIGHTSAIL_SSH_KEY}" > "${HOME}/.ssh/lightsail_deploy"
chmod 600 "${HOME}/.ssh/lightsail_deploy"
ssh-keyscan -T 20 -t ed25519 "${LIGHTSAIL_HOST}" | grep -v '^#' > "${HOME}/.ssh/lightsail_known_hosts"
scanned="$(ssh-keygen -lf "${HOME}/.ssh/lightsail_known_hosts" | awk '{print $2}')"
[[ "${scanned}" == "${EXPECTED_FINGERPRINT}" ]] || { echo "scanned host key does not match the pinned fingerprint"; exit 1; }
chmod 644 "${HOME}/.ssh/lightsail_known_hosts"

ssh_opts=(
  -i "${HOME}/.ssh/lightsail_deploy"
  -o IdentitiesOnly=yes
  -o BatchMode=yes
  -o StrictHostKeyChecking=yes
  -o UserKnownHostsFile="${HOME}/.ssh/lightsail_known_hosts"
)
target="deploy@${LIGHTSAIL_HOST}"
remote_dir="/tmp/lightsail-${GIT_SHA}"

tar \
  --exclude=.git \
  --exclude=node_modules \
  --exclude=.venv \
  --exclude=.venvs \
  --exclude=dist \
  --exclude=.env \
  --exclude=.env.production \
  --exclude=.env.local \
  --exclude=.env.development \
  --exclude=app_data.db \
  --exclude=analysis_state.db \
  --exclude=promo_calendar_context_latest.json \
  --exclude=demo_data \
  --exclude='*.pem' \
  --exclude='*.key' \
  --exclude=id_rsa \
  --exclude=id_ed25519 \
  -czf "${RUNNER_TEMP}/release.tgz" \
  -C source .

if tar -tzf "${RUNNER_TEMP}/release.tgz" | grep -E '(^|/)\.env(\.production|\.local|\.development)?$|(^|/)(app_data|analysis_state)\.db$|(^|/)promo_calendar_context_latest\.json$|(^|/)demo_data(/|$)|(^|/)\.git(/|$)|(^|/)id_(rsa|ed25519)$|\.pem$|\.key$'; then
  echo "release archive still contains protected or secret paths"
  exit 1
fi

ssh "${ssh_opts[@]}" "${target}" "mkdir -p '${remote_dir}/support' && chmod 700 '${remote_dir}'"
scp "${ssh_opts[@]}" "${RUNNER_TEMP}/release.tgz" workflow/deploy/lightsail/remote-deploy.sh "${target}:${remote_dir}/"
scp "${ssh_opts[@]}" workflow/deploy/lightsail/constraints-*.txt "${target}:${remote_dir}/support/"
set -o pipefail
ssh "${ssh_opts[@]}" "${target}" "bash '${remote_dir}/remote-deploy.sh' '${GIT_SHA}' '${remote_dir}/release.tgz' '${remote_dir}/support'" | tee "${RUNNER_TEMP}/deploy.log"
grep -E "DEPLOY_RESULT sha=${GIT_SHA} time=[0-9T:.-]+Z result=SUCCESS" "${RUNNER_TEMP}/deploy.log"
{
  echo "### Lightsail deployment"
  echo "- Commit: \`${GIT_SHA}\`"
  echo "- Host: \`${LIGHTSAIL_HOST}\`"
  grep "DEPLOY_RESULT" "${RUNNER_TEMP}/deploy.log"
} >> "${GITHUB_STEP_SUMMARY}"
