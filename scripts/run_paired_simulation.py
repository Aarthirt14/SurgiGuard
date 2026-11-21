"""Automated comparator exercise with scripted actors; NOT a participant study."""
import json,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from system import SystemStore
from protocol import ROLES
from omissions import poll
from compare_sessions import compare

def main():
    with tempfile.TemporaryDirectory() as tmp:
        store=SystemStore(Path(tmp)/'db');admin=store.setup(dict(username='facilitator',name='Scripted actor',password='synthetic-test-password'))['user'];team={}
        for role in ROLES:
            with store.db:team[role]=store.add_user(dict(username=role.lower(),name='Scripted '+role,role=role,password='synthetic-role-password'))
        store.mutate(admin,'/api/protocols/approve',dict(id='SG-SIM-03',note='Automated nonclinical test fixture only',attest=True))
        exports={}
        for mode in ('assisted','static'):
            session=store.create_study(admin,dict(title='Scripted '+mode,case='SIM-024',protocol='SG-SIM-03',team={r:u['id'] for r,u in team.items()},mode=mode,trial_group='AUTOMATED-PAIR-01'));sid=session['state']['id'];rows=[]
            def act(u,action,**kw):return store.action(u,dict(session=sid,version=store.read(sid)['version'],action=action,**kw))
            act(admin,'toggle')
            for i,d in enumerate(session['protocol']):
                omitted=i==4;interrupted=i==3
                if mode=='assisted':
                    if omitted:
                        act(admin,'prompt',item=i,timeout=5)
                        # Advance deadline evaluation only, not the task clock. This is a virtual scenario.
                        poll(store,time.time()+6)
                    else:
                        if interrupted:act(admin,'evidence',item=i,kind='overlap',text='[scripted overlap]',confidence=None,role=d['role'])
                        act(team[d['role']],'evidence',item=i,kind='typed',text=d['expected'],confidence=1)
                if not omitted:act(team[d['role']],'confirm',item=i)
                state=store.read(sid);detected=any(e['type']=='OMISSION_DETECTED' and e['item']==d['title'] for e in state['log'])
                rows.append(dict(completion_correct=(state['items'][i]['status']=='confirmed')==(not omitted),omission_expected=omitted,
                    omission_detected=detected,prompt_required=omitted or interrupted,prompt_observed=any(e['item']==d['title'] and (e['type']=='OMISSION_DETECTED' or e['type']=='EVIDENCE' and e['detail'].get('status')=='flag') for e in state['log']),
                    interruption_expected=interrupted,recovered=interrupted and state['items'][i]['status']=='confirmed',latency_ms=None))
            act(admin,'toggle')
            scored=store.mutate(admin,'/api/study/score',dict(session=sid,participant='SCRIPTED-ACTORS-NO-HUMANS',method='Predeclared script: omit sterility, interrupt anaesthesia. Automated replay, no human workload or speech latency measured.',items=rows))
            exports[mode]={**scored['state'],'metadata':scored['meta'],'scores':scored['scores']}
        report=compare(exports['assisted'],exports['static']);report['scope']='Automated state-machine exercise only. Not a controlled human study or evidence of clinical efficacy.'
        report['timing_note']='Active seconds are machine execution time, not participant task time. Omission deadline advanced by test harness.'
        Path('docs/paired-simulation-results.json').write_text(json.dumps(report,indent=2));store.db.close()
        print('docs/paired-simulation-results.json')
if __name__=='__main__':main()
