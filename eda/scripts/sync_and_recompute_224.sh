#!/usr/bin/env bash
# Sync audited harness to 224, recompute canonical metrics, cleanup, pull back.
# Credentials are NOT stored. If SSHPASS is exported and sshpass exists, it uses sshpass -e;
# otherwise ssh/rsync will prompt for password.
# Optional env: HEURA_EDA_HOST, HEURA_EDA_PORT, HEURA_EDA_USER, HEURA_EDA_REMOTE_BASE, PULL_BACK=0, SKIP_RECOMPUTE=1
set -euo pipefail

HOST="${HEURA_EDA_HOST:-202.121.181.105}"
PORT="${HEURA_EDA_PORT:-224}"
USER_NAME="${HEURA_EDA_USER:-shiliangliang}"
REMOTE_BASE="${HEURA_EDA_REMOTE_BASE:-/data/dzy/heura_repr/eda}"
LOCAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -z "${SSHPASS:-}" ] && [ -n "${HEURA_SSH_PASSWORD:-}" ]; then
  SSHPASS="$HEURA_SSH_PASSWORD"
  export SSHPASS
fi

SSH_BASE=(ssh -p "$PORT" -o StrictHostKeyChecking=accept-new)
RSYNC_RSH="ssh -p $PORT -o StrictHostKeyChecking=accept-new"
if command -v sshpass >/dev/null 2>&1 && [ -n "${SSHPASS:-}" ]; then
  SSH_BASE=(sshpass -e ssh -p "$PORT" -o StrictHostKeyChecking=accept-new)
  RSYNC_RSH="sshpass -e ssh -p $PORT -o StrictHostKeyChecking=accept-new"
fi

echo "LOCAL_ROOT=$LOCAL_ROOT"
echo "REMOTE=$USER_NAME@$HOST:$PORT:$REMOTE_BASE"
cd "$LOCAL_ROOT"
rsync -avR --exclude="__pycache__/" --exclude="*.pyc" -e "$RSYNC_RSH" \
  harness/ docs/ scripts/ config/ HANDOFF.md README.md \
  results/PHASE0_REPORT_0006_WNS_FIX.md \
  results/PHASE0_REPORT_0007_METRIC_AUDIT_v1.md \
  results/PHASE0_REPORT_0008_SERVER_RECOMPUTE.md \
  results/canonical_server/ \
  "$USER_NAME@$HOST:$REMOTE_BASE/"

if [ "${SKIP_RECOMPUTE:-0}" = "1" ]; then
  echo "SKIP_RECOMPUTE=1: sync only, no recompute"
else
"${SSH_BASE[@]}" "$USER_NAME@$HOST" "set -euo pipefail; cd '$REMOTE_BASE'; export HEURA_EDA_BASE='$REMOTE_BASE'; \
  python3 harness/smoke_test.py && \
  python3 harness/migrate_legacy_metrics.py --runs-dir runs --in-place && \
  python3 harness/recompute_metrics.py --runs-dir runs --in-place --lef flow/sky130hd/sky130_fd_sc_hd_merged.lef && \
  python3 harness/cleanup_legacy.py --apply && \
  python3 scripts/rebuild_canonical_224.py && \
  echo REMOTE_RECOMPUTE_OK"
fi

if [ "${PULL_BACK:-1}" = "1" ]; then
  echo "Pulling recomputed results back to local mirror..."
  rsync -av -e "$RSYNC_RSH" --exclude="legacy_wrong_metrics/" \
    "$USER_NAME@$HOST:$REMOTE_BASE/results/" "$LOCAL_ROOT/results/"
  rsync -av -e "$RSYNC_RSH" --include="*/" --include="metrics.json" --include="state_card.json" \
    --include="verify.json" --include="meta.json" --include="flow.log" --exclude="*" \
    "$USER_NAME@$HOST:$REMOTE_BASE/runs/" "$LOCAL_ROOT/runs/"
fi

echo "SYNC_AND_RECOMPUTE_DONE"
