"""Compare two exported sessions without inventing ground-truth performance metrics."""
import argparse,json
p=argparse.ArgumentParser();p.add_argument('assisted');p.add_argument('static');args=p.parse_args()
a=json.load(open(args.assisted));b=json.load(open(args.static))
if a['mode']!='assisted' or b['mode']!='static': p.error('Expected assisted export followed by static export')
if a['protocol']!=b['protocol']: p.error('Protocol versions differ')
def summary(s): return dict(mode=s['mode'],confirmed=sum(x['status']=='confirmed' for x in s['items']),active_seconds=s['elapsed'],workload_0_to_10=s['workload'],responses=s['responses'],flags=s['flags'],recoveries=s['recoveries'])
print(json.dumps(dict(assisted=summary(a),static=summary(b),limitation='Descriptive comparison only. Completion accuracy, recall and false prompts require independent ground-truth annotation; task order and participants must be controlled.'),indent=2))
