"""After metric migration/reruns, rebuild canonical candidate tables, stats, selector and dataset v4."""
import json
import subprocess
import sys
from pathlib import Path

BASE = Path('/data/dzy/heura_repr/eda')
sys.path.insert(0, str(BASE / 'harness'))
import collect_runs  # noqa: E402

cfg = json.loads((BASE / 'config' / 'dataset_runs.json').read_text())
outdir = BASE / 'results' / 'canonical_server'
outdir.mkdir(parents=True, exist_ok=True)

table_paths = []
for design, item in cfg['designs'].items():
    pairs = [('base', item['base'])] + list(item['candidates'].items())
    runs = []
    for variant, rid in pairs:
        rd = BASE / 'runs' / rid
        if not (rd / 'metrics.json').exists():
            print('MISSING_RUN', design, variant, rid)
            continue
        try:
            rec = collect_runs.record_from_run(str(BASE / 'runs'), rid, variant)
        except Exception as exc:
            print('RECORD_FAIL', design, variant, rid, exc)
            continue
        runs.append(rec)
    obj = {'sweep_id': design + '_canonical_server', 'design': design, 'threads': None, 'runs': runs}
    dest = outdir / (design + '_candidates.json')
    dest.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    table_paths.append(str(dest))
    print('WROTE', dest, 'records', len(runs), 'missing', len(pairs) - len(runs))

subprocess.run([sys.executable, str(BASE / 'harness' / 'stats.py'),
                '--sweep', *table_paths,
                '--out-json', str(outdir / 'PHASE0_STATS_4designs_server.json'),
                '--out-md', str(outdir / 'PHASE0_STATS_4designs_server.md')], check=True)
subprocess.run([sys.executable, str(BASE / 'harness' / 'selector_v0.py'), '--no-llm',
                '--sweep', *table_paths,
                '--out-json', str(outdir / 'PHASE0_SELECTOR_4designs_server.json'),
                '--out-md', str(outdir / 'PHASE0_SELECTOR_4designs_server.md')], check=True)
subprocess.run([sys.executable, str(BASE / 'harness' / 'build_selector_dataset.py'),
                '--config', str(BASE / 'config' / 'dataset_runs.json'),
                '--runs-dir', str(BASE / 'runs'),
                '--out-jsonl', str(outdir / 'selector_dataset_v4.jsonl'),
                '--out-sft', str(outdir / 'selector_sft_v4.jsonl'),
                '--out-summary', str(outdir / 'selector_dataset_v4_summary.json'),
                '--out-preferences', str(outdir / 'selector_preferences_v4.jsonl')], check=True)
print('REBUILD_DONE')
