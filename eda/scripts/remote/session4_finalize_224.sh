set -uo pipefail
BASE="${HEURA_EDA_BASE:-/data/dzy/heura_repr/eda}"
cd "$BASE" || exit 2
export HEURA_EDA_BASE="$BASE"
export EDA_THREADS=8
LOG=logs/session4_finalize.log
{
  echo "=== retry/compact pass $(date -u +%FT%TZ) ==="
  python3 harness/run_replay_pool.py \
    --plan results/canonical_server/replay_batch_plan_v2.jsonl \
    --out-jsonl results/canonical_server/checkpoint_replay_v2.jsonl \
    --parts-dir results/canonical_server/v2_parts \
    --failures results/canonical_server/replay_batch_v2_failures.tsv \
    --seed-jsonl results/canonical_server/checkpoint_replay_v2_smoke.jsonl \
    --seed-jsonl results/canonical_server/checkpoint_replay_pilot.jsonl \
    --jobs 8 --timeout 7200
  echo "=== validator $(date -u +%FT%TZ) ==="
  python3 harness/validate_replay_v2.py \
    --states results/canonical_server/checkpoint_states_v1.jsonl \
    --plan results/canonical_server/replay_batch_plan_v2.jsonl \
    --replay results/canonical_server/checkpoint_replay_v2.jsonl \
    --failures results/canonical_server/replay_batch_v2_failures.tsv \
    --out-json results/canonical_server/PHASE0_REPLAY_V2_VALIDATION.json
  echo "=== dataset v5 $(date -u +%FT%TZ) ==="
  python3 harness/build_checkpoint_dataset.py \
    --states results/canonical_server/checkpoint_states_v1.jsonl \
    --replay results/canonical_server/checkpoint_replay_v2.jsonl \
    --plan results/canonical_server/replay_batch_plan_v2.jsonl \
    --out-jsonl results/canonical_server/selector_dataset_v5_checkpoint.jsonl \
    --out-sft results/canonical_server/selector_sft_v5_checkpoint.jsonl \
    --out-preferences results/canonical_server/selector_preferences_v5_checkpoint.jsonl \
    --out-summary results/canonical_server/selector_dataset_v5_summary.json \
    --strict
  echo "=== replay summary $(date -u +%FT%TZ) ==="
  python3 harness/summarize_replay_v2.py \
    --replay results/canonical_server/checkpoint_replay_v2.jsonl \
    --plan results/canonical_server/replay_batch_plan_v2.jsonl \
    --out-json results/canonical_server/PHASE0_REPLAY_V2_SUMMARY.json \
    --out-md results/canonical_server/PHASE0_REPLAY_V2_SUMMARY.md
  echo "=== session_status $(date -u +%FT%TZ) ==="
  python3 harness/session_status.py
  echo "FINALIZE_DONE $(date -u +%FT%TZ)"
} 2>&1 | tee "$LOG"
