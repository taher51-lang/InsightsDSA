#!/usr/bin/env bash
#
# Idempotent InsightsDSA deploy/update via Ansible (site.yml).
# Re-running applies only what changed; modules are designed to converge safely.
#
# Usage:
#   ./update-insights-dsa.sh
#   ./update-insights-dsa.sh --diff
#   ./update-insights-dsa.sh -l controller --tags insightsdsa
#
# Prerequisites: ansible-playbook on PATH; SSH to hosts in ansible/inventory/.
# Optional: ANSIBLE_VAULT_PASSWORD_FILE, ANSIBLE_PRIVATE_KEY_FILE, etc.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANS_DIR="${ROOT}/ansible"
PLAYBOOK="${ANS_DIR}/site.yml"
CFG="${ANS_DIR}/ansible.cfg"
REQ="${ANS_DIR}/requirements.yml"

if [[ ! -f "${PLAYBOOK}" ]]; then
  echo "error: playbook not found: ${PLAYBOOK}" >&2
  exit 1
fi

if [[ ! -f "${CFG}" ]]; then
  echo "error: ansible config not found: ${CFG}" >&2
  exit 1
fi

if ! command -v ansible-playbook >/dev/null 2>&1; then
  echo "error: ansible-playbook not on PATH (install Ansible, e.g. pip install ansible)." >&2
  exit 1
fi

export ANSIBLE_CONFIG="${CFG}"
cd "${ANS_DIR}"

if [[ -f "${REQ}" ]] && command -v ansible-galaxy >/dev/null 2>&1; then
  ansible-galaxy collection install -r "${REQ}"
fi

exec ansible-playbook site.yml "$@"
