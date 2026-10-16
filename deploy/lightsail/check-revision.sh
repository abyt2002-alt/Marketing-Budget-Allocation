#!/bin/bash
set -euo pipefail
cd "${SOURCE_DIR:?}"
SHA="${GIT_SHA:?}"
[[ "${SHA}" =~ ^[0-9a-f]{40}$ ]] || { echo "git_sha must be a full commit SHA"; exit 1; }
[[ "$(git rev-parse HEAD)" == "${SHA}" ]] || { echo "checkout does not match git_sha"; exit 1; }
PRODUCTION=823b9c454e134c4091610abb523132b275604b85
if [[ "${SHA}" == "${PRODUCTION}" ]]; then
  echo "Marketing Budget Allocation revision matches production branch aws"
  exit 0
fi
if [[ "${APPROVE_BRANCH:-}" == "APPROVE" ]]; then
  echo "Non-production revision ${SHA} was explicitly approved"
  exit 0
fi
echo "Refusing ${SHA}."
echo "Production is branch aws at ${PRODUCTION}."
echo "origin/main is an ancestor of that revision and is 47 commits behind it."
echo "Automatic main deployment stays disabled. Type APPROVE only after that difference is accepted."
exit 1
