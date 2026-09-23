set -euo pipefail
BASE="${HEURA_EDA_BASE:-/data/dzy/heura_repr/eda}"
cd "$BASE/flow"
export LD_LIBRARY_PATH="$BASE/tools/tclreadline/lib"
rm -rf results
mkdir -p results
exec "$BASE/tools/openroad/bin/openroad" -exit -no_init -no_splash gcd_sky130hd.tcl
