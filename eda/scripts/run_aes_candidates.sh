set -u
BASE=/home/shiliangliang/heura_repr_eda/eda
while tmux has-session -t eda_aes 2>/dev/null; do sleep 20; done
cd "$BASE"
python3 harness/phase0.py run --run-id aes_density_040 --design aes --density 0.40 --threads 16
python3 harness/phase0.py run --run-id aes_pad_2 --design aes --pad 2 --threads 16
python3 harness/phase0.py run --run-id aes_grt_200 --design aes --grt-iters 200 --threads 16
python3 harness/phase0.py run --run-id aes_density_040_pad_2 --design aes --density 0.40 --pad 2 --threads 16
echo AES_CANDIDATES_DONE
