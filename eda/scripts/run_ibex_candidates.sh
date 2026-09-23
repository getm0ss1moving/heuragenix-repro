set -u
BASE=/data/dzy/heura_repr/eda
while [ ! -f "$BASE/runs/ibex_baseline_0001/metrics.json" ]; do sleep 15; done
cd "$BASE"
HEURA_EDA_BASE="$BASE" python3 harness/phase0.py run --run-id ibex_density_040 --design ibex --density 0.40 --threads 16
HEURA_EDA_BASE="$BASE" python3 harness/phase0.py run --run-id ibex_pad_2 --design ibex --pad 2 --threads 16
echo IBEX_CAND_DONE
