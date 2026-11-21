"""Active-time silence deadlines, independent of browser polling."""
import json,time,threading
from server import stamp

def active_time(state,now):
    return state['elapsed']+(max(0,now-state['active_since']) if state['running'] else 0)

def poll(store,now=None):
    now=time.time() if now is None else now
    changed=[]
    with store.lock,store.db:
        for sid,body in list(store.db.execute('SELECT id,state FROM sessions')):
            s=json.loads(body)
            if not s['running'] or s.get('closed') or s['mode']!='assisted':continue
            for index,item in enumerate(s['items']):
                deadline=item.get('response_deadline')
                if deadline is None or active_time(s,now)<deadline:continue
                item.pop('response_deadline',None)
                if item['status'] in ('pending','confirmed'):continue
                reason=f'No acceptable response received. Ask the {s["definitions"][index]["role"]} to repeat.'
                item.update(status='flag',kind='omission',reason=reason)
                s['flags']+=1;s['version']+=1
                s['messages'].append(dict(role='SurgiGuard',text=reason,warning=True,time=stamp()))
                store.event(sid,'OMISSION_DETECTED',index,dict(reason=reason,deadline=deadline,active_time=active_time(s,now),automatic=True))
                changed.append((sid,index))
            if any(x[0]==sid for x in changed):store.db.execute('UPDATE sessions SET state=? WHERE id=?',(json.dumps(s),sid))
    return changed

def start_monitor(store):
    stop=threading.Event()
    def run():
        while not stop.wait(.5):poll(store)
    thread=threading.Thread(target=run,name='omission-monitor',daemon=True);thread.start()
    return stop,thread
