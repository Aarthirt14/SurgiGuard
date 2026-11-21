"""Independently annotated simulation outcomes; no invented clinical evidence."""
import math
FIELDS=('completion_correct','omission_expected','omission_detected','prompt_required','prompt_observed','interruption_expected','recovered')

def validate(data,count):
    if not isinstance(data,dict):raise ValueError('Study score must be an object')
    participant=data.get('participant','')
    if not isinstance(participant,str) or not 1<=len(participant.strip())<=80:raise ValueError('Pseudonymous participant/team code required')
    note=data.get('method','')
    if not isinstance(note,str) or not 10<=len(note.strip())<=2000:raise ValueError('Describe independent labeling and timing method')
    rows=data.get('items')
    if not isinstance(rows,list) or len(rows)!=count:raise ValueError('Score every checklist item')
    cleaned=[]
    for row in rows:
        if not isinstance(row,dict) or any(type(row.get(k)) is not bool for k in FIELDS):raise ValueError('Every outcome needs an explicit yes/no label')
        latency=row.get('latency_ms')
        if latency is not None and (type(latency) not in (int,float) or not math.isfinite(latency) or not 0<=latency<=3600000):raise ValueError('Invalid latency')
        if row['recovered'] and not row['interruption_expected']:raise ValueError('Recovery requires an interruption opportunity')
        if row['omission_detected'] and not row['omission_expected']:raise ValueError('Omission detection requires an omission opportunity')
        cleaned.append({**{k:row[k] for k in FIELDS},'latency_ms':latency})
    return dict(participant=participant.strip(),method=note.strip(),items=cleaned)

def metrics(rows):
    def ratio(num,den):return num/den if den else None
    n=len(rows);omissions=sum(r['omission_expected'] for r in rows)
    negatives=sum(not r['prompt_required'] for r in rows)
    interruptions=sum(r['interruption_expected'] for r in rows)
    times=sorted(r['latency_ms'] for r in rows if r.get('latency_ms') is not None)
    return dict(items=n,completion_accuracy=ratio(sum(r['completion_correct'] for r in rows),n),
        omission_recall=ratio(sum(r['omission_expected'] and r['omission_detected'] for r in rows),omissions),
        omission_opportunities=omissions,false_prompt_rate=ratio(sum(not r['prompt_required'] and r['prompt_observed'] for r in rows),negatives),
        nonprompt_opportunities=negatives,interruption_recovery=ratio(sum(r['interruption_expected'] and r['recovered'] for r in rows),interruptions),
        interruption_opportunities=interruptions,latency_samples=len(times),
        median_latency_ms=((times[(len(times)-1)//2]+times[len(times)//2])/2 if times else None),
        p95_latency_ms=(times[max(0,math.ceil(.95*len(times))-1)] if times else None))
