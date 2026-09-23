set -u
BASE=/data/dzy/heura_repr/eda
cd "$BASE"
HEURA_EDA_BASE="$BASE" python3 harness/phase0.py run --run-id jpeg_layeradj_0001 --design jpeg --layer-adj met1:0.4,met2:0.4,met3:0.3,met4:0.3,met5:0.2 --threads 16
HEURA_EDA_BASE="$BASE" python3 harness/phase0.py run --run-id jpeg_pad_2 --design jpeg --pad 2 --threads 16
echo JPEG_CAND_DONE
