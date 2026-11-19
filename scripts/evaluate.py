"""Deterministic fixture evaluation; not speech/clinical performance measurement."""
import json,sys,time,statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from protocol import ITEMS,assess
rows=[]
for item in ITEMS:
 for kind in ('clean','noise','wrong','conflict','overlap','omission'):
  text='Not confirmed' if kind=='conflict' else item['expected']
  role=('Surgeon' if item['role']=='Nurse' else 'Nurse') if kind=='wrong' else item['role']
  t=time.perf_counter();status,reason=assess(item,text,role,.58 if kind=='noise' else .97,kind);duration=(time.perf_counter()-t)*1000
  rows.append(dict(item=item['id'],scenario=kind,expected='pending' if kind=='clean' else 'flag',actual=status,rule_latency_ms=duration))
report=dict(scope='Deterministic synthetic fixtures only; no real ASR, acoustics, or clinical effectiveness measured',trials=len(rows),state_accuracy=sum(r['actual']==r['expected'] for r in rows)/len(rows),omission_detection_recall=sum(r['actual']=='flag' for r in rows if r['scenario']=='omission')/6,false_prompt_rate=sum(r['actual']=='flag' for r in rows if r['scenario']=='clean')/6,median_rule_latency_ms=statistics.median(r['rule_latency_ms'] for r in rows),trials_detail=rows)
print(json.dumps(report,indent=2))
if report['state_accuracy']!=1: sys.exit(1)
