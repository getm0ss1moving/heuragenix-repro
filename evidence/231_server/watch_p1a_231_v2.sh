set -u
B=/data/dzy/heura_repr
OUT=$B/results/paper_table4_231
LOG=$OUT/p1a_watch.log
INSTS="kroC100.tsp kroA100.tsp kroB100.tsp bier127.tsp kroA150.tsp tsp225.tsp kroB200.tsp a280.tsp"
MODES="raw vanilla dual"
echo "$(date +%F_%T) P1A_WATCH_V2_START" >> $LOG
while true; do
  done_n=0; total=24; missing=""
  for m in $MODES; do
    for i in $INSTS; do
      f=$OUT/parts/${m}__${i}.json
      if [ -s "$f" ]; then done_n=$((done_n+1)); else missing="$missing $m/$i"; fi
    done
  done
  run=$(pgrep -f 'eval_selector_tsp_par2.py' | wc -l)
  echo "$(date +%F_%T) done=$done_n/$total running_procs=$run missing:[$missing ]" >> $LOG
  if [ "$done_n" -ge "$total" ]; then
    echo "$(date +%F_%T) ALL_PARTS_PRESENT, combining" >> $LOG
    $B/envs/heura/bin/python - <<'PY' >> $LOG 2>&1
import json,glob,os,csv,collections
OUT='/data/dzy/heura_repr/results/paper_table4_231'
rows=[]
for f in sorted(glob.glob(OUT+'/parts/*.json')):
    try:
        d=json.load(open(f))
        if isinstance(d,list): rows.extend(d)
        else: rows.append(d)
    except Exception as e:
        print('ERR',f,e)
json.dump(rows,open(OUT+'/table4_p1a_all.json','w'),indent=2,ensure_ascii=False)
keys=['model','instance','value','gap','rounds','max_rounds','complete','time_limited','elapsed','tts_budget','rollout_stop','fallback_complete']
with open(OUT+'/table4_p1a_summary.csv','w',newline='') as fh:
    w=csv.writer(fh); w.writerow(keys)
    for r in rows: w.writerow([r.get(k) for k in keys])
by=collections.defaultdict(list)
for r in rows:
    if r.get('gap') is not None: by[r['model']].append(r['gap'])
for m,v in sorted(by.items()): print('AVG_GAP',m,round(sum(v)/len(v),4),'n',len(v))
print('WROTE',OUT+'/table4_p1a_all.json','rows',len(rows))
PY
    echo "$(date +%F_%T) P1A_COMBINE_DONE" >> $LOG
    break
  fi
  if [ "$run" -eq 0 ] && [ "$done_n" -lt "$total" ]; then
    echo "$(date +%F_%T) NO_PROCS_AND_INCOMPLETE (some tasks failed; see logs/)" >> $LOG
    break
  fi
  sleep 240
done
