"""Compare recorded paired trials. Reports missing annotations as null, never invented."""
import argparse,json

def summary(s):
    scores=s.get('scores',[]);latest=scores[-1] if scores else None
    return dict(mode=s['mode'],confirmed=sum(x['status']=='confirmed' for x in s['items']),
        active_seconds=s['elapsed'],workload_0_to_10=s['workload'],responses=s['responses'],flags=s['flags'],recoveries=s['recoveries'],
        observer_metrics=latest['metrics'] if latest else None,score_state_version=latest['state_version'] if latest else None,
        score_matches_current_state=latest['state_version']==s['version'] if latest else None,
        score_task_seconds=latest['task_seconds'] if latest else None,score_workload=latest['workload'] if latest else None)

def compare(a,b):
    if a['mode']!='assisted' or b['mode']!='static':raise ValueError('Expected assisted export followed by static export')
    if a['protocol']!=b['protocol']:raise ValueError('Protocol versions differ')
    ma,mb=a.get('metadata',{}),b.get('metadata',{})
    if not ma.get('trial_group') or ma.get('trial_group')!=mb.get('trial_group'):raise ValueError('Shared nonempty paired-trial ID required')
    if ma.get('case')!=mb.get('case'):raise ValueError('Case snapshots differ')
    return dict(trial_group=ma['trial_group'],assisted=summary(a),static=summary(b),
        limitation='Descriptive comparison of recorded observations. Observer labels are not externally certified. Control order, participants and timing method; no clinical benefit inferred.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('assisted');p.add_argument('static');args=p.parse_args()
    try:
        with open(args.assisted) as f:a=json.load(f)
        with open(args.static) as f:b=json.load(f)
        print(json.dumps(compare(a,b),indent=2))
    except ValueError as e:p.error(str(e))
