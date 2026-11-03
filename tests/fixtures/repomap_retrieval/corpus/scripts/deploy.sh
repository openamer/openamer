#!/usr/bin/env bash
# Roll out the fixture service to a named environment.
set -euo pipefail

TARGET="${1:-staging}"
IMAGE="fleet:latest"

function deploy() {
  local target="$1"
  echo "rolling out ${IMAGE} to ${target}"
}

function rollback() {
  echo "reverting ${TARGET}"
}

if [[ "${TARGET}" == "rollback" ]]; then
  rollback
else
  deploy "${TARGET}"
fi
