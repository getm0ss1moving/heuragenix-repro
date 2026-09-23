#!/usr/bin/env bash
set -u
cd /data/dzy/heura_repr/eda
export HEURA_EDA_BASE=/data/dzy/heura_repr/eda
export EDA_THREADS=8
run() { echo "=== $(date +%H:%M:%S) $*"; python3 harness/phase0.py run --threads 8 "$@"; echo "RC=$? $*"; }
run --run-id gcd_baseline_pinoffset_0001 --design gcd
run --run-id phase0_sweep_0002_base --design gcd
run --run-id phase0_sweep_0002_density_025 --design gcd --density 0.25
run --run-id phase0_sweep_0002_density_035 --design gcd --density 0.35
run --run-id phase0_sweep_0002_density_040 --design gcd --density 0.40
run --run-id phase0_sweep_0002_pad_2 --design gcd --pad 2
run --run-id phase0_sweep_0002_pad_6 --design gcd --pad 6
run --run-id phase0_sweep_0002_grt_50 --design gcd --grt-iters 50
run --run-id phase0_sweep_0002_grt_200 --design gcd --grt-iters 200
run --run-id aes_baseline_0001 --design aes
run --run-id aes_density_040 --design aes --density 0.40
run --run-id aes_pad_2 --design aes --pad 2
run --run-id aes_grt_200 --design aes --grt-iters 200
run --run-id aes_density_040_pad_2 --design aes --density 0.40 --pad 2
echo ALL_DONE
