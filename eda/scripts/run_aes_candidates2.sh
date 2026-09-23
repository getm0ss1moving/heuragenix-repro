set -u
BASE=/home/shiliangliang/heura_repr_eda/eda
cd "$BASE"
python3 harness/phase0.py run --run-id aes_density_040 --design aes --density 0.40 --threads 12
python3 harness/phase0.py run --run-id aes_pad_2 --design aes --pad 2 --threads 12
python3 harness/phase0.py run --run-id aes_grt_200 --design aes --grt-iters 200 --threads 12
python3 harness/phase0.py run --run-id aes_density_040_pad_2 --design aes --density 0.40 --pad 2 --threads 12
echo AES_CANDIDATES_DONE
