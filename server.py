"""Local nonclinical research server. Python 3.10+, standard library only."""
import argparse, hashlib, json, math, os, secrets, sqlite3, threading, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from protocol import ITEMS, ROLES, VERSION, assess
ROOT = Path(__file__).resolve().parent

def stamp(): return datetime.now(timezone.utc).isoformat()
class Problem(Exception):
    def __init__(self, message, status=400): self.message, self.status = message, status

def require(condition, message, status=400):
    if not condition: raise Problem(message, status)

class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, state TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT NOT NULL, body TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tokens(hash TEXT PRIMARY KEY, session TEXT NOT NULL, role TEXT NOT NULL, expires REAL NOT NULL);''')
        self.lock = threading.RLock()
    def create(self, role, mode, definitions=None):
        definitions = definitions or ITEMS
        require(role in ROLES, 'Invalid role'); require(mode in ('assisted','static'), 'Invalid mode')
        sid = secrets.token_urlsafe(18)
        state = dict(id=sid,version=0,mode=mode,protocol=VERSION,definitions=definitions,running=False,elapsed=0,active_since=None,created=stamp(),items=[dict(status='waiting',evidence=None) for _ in definitions],messages=[],responses=0,flags=0,recoveries=0,workload=None)
        with self.lock, self.db:
            self.db.execute('INSERT INTO sessions VALUES (?,?)', (sid,json.dumps(state)))
            self.event(sid,'SESSION_CREATED',None,dict(mode=mode,role=role))
            token = self.token(sid,role)
        return dict(token=token,state=self.read(sid),role=role,protocol=definitions)
    def token(self,sid,role):
        token=secrets.token_urlsafe(32)
        self.db.execute('INSERT INTO tokens VALUES (?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),sid,role,time.time()+86400))
        return token
    def auth(self,token):
        with self.lock:
            row=self.db.execute('SELECT session,role,expires FROM tokens WHERE hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        require(row and row[2]>time.time(),'Session access expired or missing. Create a new session.',401)
        return row[0],row[1]
    def event(self,sid,kind,index,detail):
        prev=self.db.execute('SELECT hash FROM events WHERE session=? ORDER BY seq DESC LIMIT 1',(sid,)).fetchone()
        previous=prev[0] if prev else '0'*64
        stored=self.db.execute('SELECT state FROM sessions WHERE id=?',(sid,)).fetchone()
        definitions=json.loads(stored[0]).get('definitions',ITEMS) if stored else ITEMS
        body=json.dumps(dict(timestamp=stamp(),type=kind,item=definitions[index]['title'] if index is not None else 'Session',detail=detail),sort_keys=True,separators=(',',':'))
        digest=hashlib.sha256((previous+body).encode()).hexdigest()
        self.db.execute('INSERT INTO events(session,body,previous,hash) VALUES (?,?,?,?)',(sid,body,previous,digest))
    def read(self,sid):
        with self.lock:
            row=self.db.execute('SELECT state FROM sessions WHERE id=?',(sid,)).fetchone()
            require(row is not None,'Unknown session',404)
            s=json.loads(row[0]);s['elapsed']=round(s['elapsed']+(time.time()-s['active_since'] if s['running'] else 0))
            s['log']=[dict(json.loads(b),previous=p,hash=h) for b,p,h in self.db.execute('SELECT body,previous,hash FROM events WHERE session=? ORDER BY seq',(sid,))]
        return s
    def act(self,token,data):
        sid,actor=self.auth(token)
        with self.lock,self.db:
            s=json.loads(self.db.execute('SELECT state FROM sessions WHERE id=?',(sid,)).fetchone()[0])
            require(data.get('version')==s['version'],'Session changed. Refresh and retry the action.',409)
            action=data.get('action'); i=data.get('item'); detail={'actor':actor}
            if data.get('_identity'): detail['account']=data['_identity']
            definitions=s.get('definitions',ITEMS)
            require(not s.get('closed'), 'Session is closed',409)
            if action in ('evidence','confirm','correct','override','interrupt','prompt'):
                require(type(i) is int and 0<=i<len(definitions),'Invalid checklist item')
                require(s['running'],'Start the session first')
                x=s['items'][i];d=definitions[i]
            if action=='toggle':
                if s['running']: s['elapsed']+=time.time()-s['active_since'];s['active_since']=None
                else: s['active_since']=time.time()
                s['running']=not s['running'];detail['running']=s['running']
            elif action=='prompt':
                require(s['mode']=='assisted','Prompts disabled in static comparator')
                require(x['status'] not in ('pending','confirmed'),'Resolve or confirm current evidence first')
                timeout=data.get('timeout',30)
                require(type(timeout) is int and 5<=timeout<=120,'Response timeout must be 5–120 seconds')
                require(actor in ('Coordinator',d['role']),'Only facilitator or designated role may prompt',403)
                from omissions import active_time
                x['response_deadline']=active_time(s,time.time())+timeout
                message=f'{d["role"]}, please verify {d["title"]}.'
                detail.update(timeout=timeout,source=d['source'],prompt=message)
                s['messages'].append(dict(role='SurgiGuard',text=message,time=stamp()))
            elif action=='role':
                role=data.get('role');require(role in ROLES,'Invalid role')
                # Role switching is deliberately exposed in this nonclinical demo, not identity proof.
                new_token=self.token(sid,role);detail['new_role']=role
            elif action in ('evidence','interrupt'):
                require(s['mode']=='assisted','Assistant input is disabled in static mode')
                require(x['status']!='confirmed','Reopen the item before adding evidence')
                text=data.get('text','');role=data.get('role');confidence=data.get('confidence');kind=data.get('kind','typed')
                require(isinstance(text,str) and len(text)<=2000,'Response must be at most 2000 characters')
                require(role in ROLES,'Invalid speaking role')
                require(confidence is None or (type(confidence) in (int,float) and math.isfinite(confidence) and 0<=confidence<=1),'Invalid confidence')
                require(kind in ('typed','speech','clean','noise','wrong','conflict','overlap','omission','interruption'),'Invalid evidence type')
                if action=='interrupt': kind='interruption'
                status,reason=assess(d,text,role,confidence,kind)
                if x.get('kind') in ('overlap','interruption') and status=='pending': s['recoveries']+=1
                x.update(status=status,reason=reason,kind=kind,evidence=dict(text=text,role=role,confidence=confidence,source=kind))
                if status=='pending':x.pop('response_deadline',None)
                s['responses']+=1;s['flags']+=int(status=='flag')
                s['messages'] += [dict(role=role,text=text,confidence=confidence,source=kind,time=stamp()),dict(role='SurgiGuard',text=reason,warning=status=='flag',time=stamp())]
                detail.update(x)
            elif action=='confirm':
                require(actor==d['role'],'Only the designated role can confirm',403)
                require(x['status']!='confirmed','Item already confirmed')
                require(s['mode']=='static' or x['status']=='pending','Evidence is unresolved; cannot confirm',409)
                x.pop('response_deadline',None)
                x.update(status='confirmed',confirmedBy=actor,confirmedAt=stamp());detail['evidence']=x['evidence']
                s['messages'].append(dict(role='SurgiGuard',text=f'{d["title"]} explicitly confirmed by {actor}.',time=stamp()))
            elif action in ('correct','override'):
                require(actor==d['role'],'Only the designated role can correct or override',403)
                reason=data.get('reason','');require(isinstance(reason,str) and 3<=len(reason.strip())<=1000,'A reason of 3–1000 characters is required')
                detail.update(reason=reason,previous=dict(x));x.clear();x.update(status='flag' if action=='override' else 'waiting',evidence=None,reason='Override recorded; unresolved.' if action=='override' else 'Reopened for corrected evidence.')
            elif action=='finish':
                require(all(x['status']=='confirmed' for x in s['items']), 'Confirm all items before closing',409)
                if s['running']: s['elapsed']+=time.time()-s['active_since']
                s.update(running=False,active_since=None,closed=True,closed_at=stamp())
            elif action=='workload':
                rating=data.get('rating');require(type(rating) in (int,float) and math.isfinite(rating) and 0<=rating<=10,'Workload must be 0–10');s['workload']=rating;detail['rating']=rating
            else: raise Problem('Unknown action')
            s['version']+=1
            self.event(sid,action.upper(),i if action in ('evidence','confirm','correct','override','interrupt','prompt') else None,detail)
            self.db.execute('UPDATE sessions SET state=? WHERE id=?',(json.dumps(s),sid))
        result=dict(state=self.read(sid),role=detail.get('new_role',actor))
        if action=='role': result['token']=new_token
        return result

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): pass # Avoid recording transcripts, tokens and paths in access logs.
    def reply(self,status,value,content_type='application/json'):
        body=json.dumps(value).encode() if content_type=='application/json' else value
        self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        try:
            path=urlparse(self.path).path
            if path=='/api/health': return self.reply(200,dict(ok=True,nonclinical=True,protocol=VERSION))
            if path=='/api/session':
                sid,role=self.server.store.auth(self.headers.get('Authorization','').removeprefix('Bearer '))
                return self.reply(200,dict(state=self.server.store.read(sid),role=role,protocol=ITEMS))
            assets={'/':('index.html','text/html; charset=utf-8'),'/style.css':('style.css','text/css'),'/app.js':('app.js','text/javascript')}
            require(path in assets,'Not found',404);name,mime=assets[path]
            self.reply(200,(ROOT/'web'/name).read_bytes(),mime)
        except Problem as e: self.reply(e.status,dict(error=e.message))
    def do_POST(self):
        try:
            origin=self.headers.get('Origin');require(not origin or urlparse(origin).netloc==self.headers.get('Host'),'Cross-origin request rejected',403)
            require(self.headers.get('Content-Type','').startswith('application/json'),'JSON required',415)
            length=int(self.headers.get('Content-Length','0'));require(0<length<=16000,'Invalid request size',413)
            data=json.loads(self.rfile.read(length));require(isinstance(data,dict),'JSON object required')
            if self.path=='/api/sessions':
                key=os.getenv('SURGIGUARD_ACCESS_KEY','')
                require(not key or secrets.compare_digest(str(data.get('accessKey','')),key),'Invalid workspace key',403)
                result=self.server.store.create(data.get('role','Surgeon'),data.get('mode','assisted'))
            elif self.path=='/api/action': result=self.server.store.act(self.headers.get('Authorization','').removeprefix('Bearer '),data)
            else: raise Problem('Not found',404)
            self.reply(200,result)
        except Problem as e: self.reply(e.status,dict(error=e.message))
        except (ValueError,TypeError): self.reply(400,dict(error='Invalid JSON or parameter'))
        except Exception: self.reply(500,dict(error='Internal server error. No action confirmed; refresh session state.'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8000);p.add_argument('--strictPort',action='store_true',help=argparse.SUPPRESS);p.add_argument('--db',default=str(ROOT/'data'/'surgiguard.sqlite3'));args=p.parse_args()
    if args.host not in ('127.0.0.1','localhost','::1') and not os.getenv('SURGIGUARD_ACCESS_KEY'): p.error('Set SURGIGUARD_ACCESS_KEY before binding to a network interface')
    Path(args.db).parent.mkdir(parents=True,exist_ok=True)
    from system import SystemHandler, SystemStore
    server=ThreadingHTTPServer((args.host,args.port),SystemHandler);server.store=SystemStore(args.db)
    from omissions import start_monitor
    monitor,monitor_thread=start_monitor(server.store)
    print(f'SurgiGuard nonclinical simulator: http://{args.host}:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        monitor.set();monitor_thread.join(timeout=2);server.server_close();server.store.db.close()
if __name__=='__main__': main()

