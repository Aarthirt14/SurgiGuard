"""Account-based nonclinical research workspace. Standard library only."""
import copy,hashlib,json,re,secrets,time,os
from urllib.parse import urlparse,parse_qs
from server import Store,Handler,Problem,require,stamp,ROOT
from protocol import ITEMS,ROLES

def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def password_hash(password,salt):return hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),240000).hex()
def text(value,name,limit=200):
    require(isinstance(value,str) and 1<=len(value.strip())<=limit,f'{name} is required (maximum {limit} characters)')
    return value.strip()

class SystemStore(Store):
    def __init__(self,path):
        super().__init__(path)
        self.db.executescript('''CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,username TEXT UNIQUE,name TEXT,role TEXT,salt TEXT,password TEXT);
        CREATE TABLE IF NOT EXISTS logins(token TEXT PRIMARY KEY,user_id TEXT,expires REAL);
        CREATE TABLE IF NOT EXISTS protocols(id TEXT PRIMARY KEY,body TEXT);
        CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,body TEXT);
        CREATE TABLE IF NOT EXISTS memberships(session TEXT,user_id TEXT,capability TEXT,PRIMARY KEY(session,user_id));
        CREATE TABLE IF NOT EXISTS studies(session TEXT PRIMARY KEY,body TEXT);
        CREATE TABLE IF NOT EXISTS reviews(session TEXT,user_id TEXT,body TEXT,PRIMARY KEY(session,user_id));
        CREATE TABLE IF NOT EXISTS governance(id INTEGER PRIMARY KEY,body TEXT);''')
        self.db.execute('CREATE TABLE IF NOT EXISTS study_scores(id INTEGER PRIMARY KEY,session TEXT,body TEXT)')
        self.attempts={}
        with self.db:
            if not self.db.execute('SELECT 1 FROM protocols').fetchone():
                p=dict(id='SG-SIM-03',name='Pre-incision Time Out',revision=1,status='draft',created=stamp(),items=copy.deepcopy(ITEMS),note='Simplified teaching fixture. Review required for nonclinical simulation.')
                self.db.execute('INSERT INTO protocols VALUES (?,?)',(p['id'],json.dumps(p)))
            if not self.db.execute('SELECT 1 FROM cases').fetchone():
                for cid,name,scenario in [('SIM-024','Alex Morgan','Baseline team verification'),('SIM-025','Jordan Taylor','Noise and interruption exercise')]:
                    c=dict(id=cid,name=name,procedure='Elective procedure',site='Left',scenario=scenario,notes='Synthetic training case. No medical record or treatment advice.',synthetic=True)
                    self.db.execute('INSERT INTO cases VALUES (?,?)',(cid,json.dumps(c)))
    def public_user(self,row):return dict(id=row[0],username=row[1],name=row[2],role=row[3])
    def users(self):return [self.public_user(r) for r in self.db.execute('SELECT id,username,name,role FROM users ORDER BY name')]
    def govern(self,kind,user,detail):self.db.execute('INSERT INTO governance(body) VALUES (?)',(json.dumps(dict(timestamp=stamp(),type=kind,user=user,detail=detail)),))
    def add_user(self,data):
        username=text(data.get('username'),'Username',50).lower();name=text(data.get('name'),'Name',80);role=data.get('role');pw=data.get('password')
        require(re.fullmatch(r'[a-z0-9_.-]{3,50}',username),'Use 3–50 letters, digits, dots, hyphens or underscores')
        require(role in (*ROLES,'Coordinator'),'Invalid role');require(isinstance(pw,str) and 10<=len(pw)<=200,'Password must contain 10–200 characters')
        require(not self.db.execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone(),'Username already exists',409)
        uid=secrets.token_urlsafe(12);salt=secrets.token_hex(16)
        self.db.execute('INSERT INTO users VALUES (?,?,?,?,?,?)',(uid,username,name,role,salt,password_hash(pw,salt)))
        return dict(id=uid,username=username,name=name,role=role)
    def setup(self,data):
        with self.lock,self.db:
            require(not self.users(),'Workspace already initialized',409)
            key=os.getenv('SURGIGUARD_ACCESS_KEY','');require(not key or secrets.compare_digest(str(data.get('accessKey','')),key),'Invalid setup key',403)
            u=self.add_user(dict(data,role='Coordinator'));self.govern('WORKSPACE_SETUP',u['id'],{})
        return self.login(data,'setup')
    def login(self,data,ip):
        username=str(data.get('username','')).lower();pw=str(data.get('password',''));key=(ip,username)
        with self.lock:
            recent=[t for t in self.attempts.get(key,[]) if t>time.time()-300];self.attempts[key]=recent
            require(len(recent)<10,'Too many attempts; try again in five minutes',429)
            row=self.db.execute('SELECT id,username,name,role,salt,password FROM users WHERE username=?',(username,)).fetchone()
            actual=password_hash(pw,row[4] if row else 'invalid-user-salt')
            if not row or not secrets.compare_digest(actual,row[5]):recent.append(time.time());raise Problem('Incorrect username or password',401)
            self.attempts.pop(key,None);token=secrets.token_urlsafe(32)
            with self.db:
                self.db.execute('INSERT INTO logins VALUES (?,?,?)',(digest(token),row[0],time.time()+28800));self.govern('LOGIN',row[0],{})
        return dict(token=token,user=self.public_user(row))
    def user(self,token):
        with self.lock:row=self.db.execute('SELECT u.id,u.username,u.name,u.role FROM users u JOIN logins l ON u.id=l.user_id WHERE l.token=? AND l.expires>?',(digest(token),time.time())).fetchone()
        require(row is not None,'Please sign in again',401);return self.public_user(row)
    def admin(self,u):require(u['role']=='Coordinator','Coordinator access required',403)
    def access(self,u,sid):
        require(isinstance(sid,str),'Session ID required')
        row=self.db.execute('SELECT capability FROM memberships WHERE session=? AND user_id=?',(sid,u['id'])).fetchone()
        require(row is not None or u['role']=='Coordinator','You are not assigned to this session',403)
        require(self.db.execute('SELECT 1 FROM studies WHERE session=?',(sid,)).fetchone(),'Session not found',404)
        return row[0] if row else None
    def workspace(self,u):
        with self.lock:
            sessions=[]
            for sid,body in self.db.execute('SELECT session,body FROM studies'):
                if u['role']=='Coordinator' or self.db.execute('SELECT 1 FROM memberships WHERE session=? AND user_id=?',(sid,u['id'])).fetchone():
                    s=self.read(sid);sessions.append(dict(json.loads(body),id=sid,closed=s.get('closed',False),running=s['running'],confirmed=sum(x['status']=='confirmed' for x in s['items']),total=len(s['items']),elapsed=s['elapsed'],flags=s['flags'],workload=s['workload']))
            return dict(user=u,users=self.users(),cases=[json.loads(r[0]) for r in self.db.execute('SELECT body FROM cases')],protocols=[json.loads(r[0]) for r in self.db.execute('SELECT body FROM protocols')],sessions=sorted(sessions,key=lambda s:s['created'],reverse=True),governance=[json.loads(r[0]) for r in self.db.execute('SELECT body FROM governance ORDER BY id DESC LIMIT 60')] if u['role']=='Coordinator' else [])
    def session(self,u,sid):
        with self.lock:
            self.access(u,sid);s=self.read(sid);meta=json.loads(self.db.execute('SELECT body FROM studies WHERE session=?',(sid,)).fetchone()[0]);reviews=[dict(json.loads(b),reviewer=uid) for uid,b in self.db.execute('SELECT user_id,body FROM reviews WHERE session=?',(sid,))]
        scores=[json.loads(b) for b, in self.db.execute('SELECT body FROM study_scores WHERE session=? ORDER BY id',(sid,))]
        return dict(state=s,meta=meta,protocol=s['definitions'],reviews=reviews,role=u['role'],scores=scores)
    def create_study(self,u,data):
        self.admin(u)
        with self.lock:
            cid=data.get('case');pid=data.get('protocol');crew=data.get('team',{})
            c=self.db.execute('SELECT body FROM cases WHERE id=?',(cid,)).fetchone();p=self.db.execute('SELECT body FROM protocols WHERE id=?',(pid,)).fetchone();require(c and p,'Choose a case and protocol')
            case=json.loads(c[0]);protocol=json.loads(p[0]);require(protocol['status']=='simulation-approved','Protocol must be approved for simulation first');require(isinstance(crew,dict),'Invalid team')
            title=text(data.get('title'),'Session title',120);members={}
            for role in ROLES:
                row=self.db.execute('SELECT id,username,name,role FROM users WHERE id=?',(crew.get(role),)).fetchone();require(row and row[3]==role,f'Assign a registered {role}');members[role]=self.public_user(row)
            defs=copy.deepcopy(protocol['items'])
            for d in defs:
                d['source']=f'{pid} rev {protocol["revision"]} / {d["id"]}'
                if d['id']=='identity':
                    d['expected']=f'Patient {case["name"]}, {case["procedure"].lower()}, {case["site"].lower()} side confirmed.'
                    d['patterns']=[re.escape(case['name'])+'.*'+re.escape(case['procedure'])+'.*'+re.escape(case['site'])+'.*confirmed']
            result=super().create('Surgeon',data.get('mode','assisted'),defs);sid=result['state']['id']
            meta=dict(title=title,case=case,protocol=dict(id=pid,revision=protocol['revision'],approval=protocol.get('approval')),team=members,created=stamp(),owner=u['id'],mode=data.get('mode','assisted'),trial_group=str(data.get('trial_group',''))[:80])
            with self.db:
                self.db.execute('INSERT INTO studies VALUES (?,?)',(sid,json.dumps(meta)))
                for member in [u,*members.values()]:self.db.execute('INSERT INTO memberships VALUES (?,?,?)',(sid,member['id'],self.token(sid,member['role'])))
                s=json.loads(self.db.execute('SELECT state FROM sessions WHERE id=?',(sid,)).fetchone()[0]);s.update(protocol=f'{pid} rev {protocol["revision"]}',closed=False)
                self.db.execute('UPDATE sessions SET state=? WHERE id=?',(json.dumps(s),sid));self.event(sid,'TEAM_ASSIGNED',None,dict(user=u['id'],team=members))
        return self.session(u,sid)
    def action(self,u,data):
        sid=data.get('session');action=data.get('action');require(action in ('toggle','evidence','interrupt','confirm','correct','override','workload','finish','prompt'),'Unsupported action')
        with self.lock:
            cap=self.access(u,sid);require(cap,'Observer cannot modify this session',403);data=dict(data,_identity=u)
            if action in ('toggle','finish'):self.admin(u)
            if action in ('evidence','interrupt'):
                if data.get('kind') in ('clean','noise','wrong','conflict','overlap','omission'):self.admin(u)
                else:require(u['role'] in ROLES,'An assigned clinician must submit live evidence',403);data['role']=u['role']
            try:self.auth(cap)
            except Problem:
                with self.db:cap=self.token(sid,u['role']);self.db.execute('UPDATE memberships SET capability=? WHERE session=? AND user_id=?',(cap,sid,u['id']))
            super().act(cap,data)
        return self.session(u,sid)
    def mutate(self,u,path,data):
        if path=='/api/study/score':
            from study import validate,metrics
            self.admin(u);sid=data.get('session')
            with self.lock,self.db:
                self.access(u,sid);s=self.read(sid)
                require(not s['running'],'Pause or close the simulation before scoring')
                try:score=validate(data,len(s['items']))
                except ValueError as e:raise Problem(str(e))
                score.update(timestamp=stamp(),reviewer=u['id'],state_version=s['version'],mode=s['mode'],task_seconds=s['elapsed'],workload=s['workload'],metrics=metrics(score['items']),evidence='observer-entered, not independently certified')
                self.db.execute('INSERT INTO study_scores(session,body) VALUES (?,?)',(sid,json.dumps(score)))
                self.event(sid,'STUDY_SCORE',None,score)
            return self.session(u,sid)
        if path=='/api/session/create':return self.create_study(u,data)
        if path=='/api/session/action':return self.action(u,data)
        if path=='/api/review':
            self.admin(u);sid=data.get('session')
            with self.lock,self.db:
                self.access(u,sid);rating=data.get('rating');require(rating in ('pass','needs-review'),'Invalid review outcome');note=text(data.get('note'),'Review note',3000)
                self.db.execute('INSERT OR REPLACE INTO reviews VALUES (?,?,?)',(sid,u['id'],json.dumps(dict(rating=rating,note=note,time=stamp()))));self.event(sid,'RESEARCH_REVIEW',None,dict(user=u['id'],rating=rating,note=note))
            return self.session(u,sid)
        self.admin(u)
        with self.lock,self.db:
            if path=='/api/users':self.govern('USER_CREATED',u['id'],self.add_user(data))
            elif path=='/api/cases':
                cid='SIM-'+secrets.token_hex(3).upper();c=dict(id=cid,name=text(data.get('name'),'Synthetic name',80),procedure=text(data.get('procedure'),'Procedure',120),site=data.get('site'),scenario=text(data.get('scenario'),'Scenario title',100),notes=text(data.get('notes'),'Notes',2000),synthetic=True);require(c['site'] in ('Left','Midline'),'Supported sites: Left or Midline')
                self.db.execute('INSERT INTO cases VALUES (?,?)',(cid,json.dumps(c)));self.govern('CASE_CREATED',u['id'],dict(id=cid))
            elif path=='/api/protocols':
                base=self.db.execute('SELECT body FROM protocols WHERE id=?',(data.get('base'),)).fetchone();require(base,'Base protocol not found');p=json.loads(base[0]);p.update(id='SG-'+secrets.token_hex(4).upper(),name=text(data.get('name'),'Protocol name',120),revision=p['revision']+1,status='draft',note=text(data.get('note'),'Notes',3000),created=stamp());p.pop('approval',None)
                self.db.execute('INSERT INTO protocols VALUES (?,?)',(p['id'],json.dumps(p)));self.govern('PROTOCOL_DRAFT_CREATED',u['id'],dict(id=p['id']))
            elif path=='/api/protocols/approve':
                row=self.db.execute('SELECT body FROM protocols WHERE id=?',(data.get('id'),)).fetchone();require(row,'Protocol not found');p=json.loads(row[0]);require(p['status']=='draft','Only drafts can be approved');require(data.get('attest') is True,'Acknowledge simulation-only approval')
                p.update(status='simulation-approved',approval=dict(by=u['name'],user=u['id'],time=stamp(),note=text(data.get('note'),'Rationale',2000),scope='Nonclinical simulation only'))
                self.db.execute('UPDATE protocols SET body=? WHERE id=?',(json.dumps(p),p['id']));self.govern('SIMULATION_APPROVAL',u['id'],dict(id=p['id'],approval=p['approval']))
            else:raise Problem('Not found',404)
        return self.workspace(u)

class SystemHandler(Handler):
    def bearer(self):return self.headers.get('Authorization','').removeprefix('Bearer ')
    def do_GET(self):
        try:
            p=urlparse(self.path);path=p.path;store=self.server.store
            if path=='/api/status':return self.reply(200,dict(initialized=bool(store.users()),nonclinical=True,version='0.3.0'))
            if path=='/api/audio/capabilities':return self.reply(200,dict(available=False,engine='browser-fallback'))
            if path=='/api/health':return self.reply(200,dict(ok=True,version='0.3.0',nonclinical=True))
            if path.startswith('/api/'):
                u=store.user(self.bearer())
                if path=='/api/workspace':return self.reply(200,store.workspace(u))
                if path=='/api/session':return self.reply(200,store.session(u,parse_qs(p.query).get('id',[''])[0]))
                raise Problem('Not found',404)
            assets={'/':('index.html','text/html; charset=utf-8'),'/style.css':('style.css','text/css'),'/app.js':('app.js','text/javascript'),'/local-audio.js':('local-audio.js','text/javascript'),'/pcm-worklet.js':('pcm-worklet.js','text/javascript')};require(path in assets,'Not found',404);name,mime=assets[path];self.reply(200,(ROOT/'web'/name).read_bytes(),mime)
        except Problem as e:self.reply(e.status,dict(error=e.message))
        except Exception:self.reply(500,dict(error='Server error; check local server configuration'))
    def do_POST(self):
        try:
            origin=self.headers.get('Origin');require(not origin or urlparse(origin).netloc==self.headers.get('Host'),'Cross-origin request rejected',403);require(self.headers.get('Content-Type','').startswith('application/json'),'JSON required',415)
            length=int(self.headers.get('Content-Length','0'));require(0<length<=16000,'Invalid request size',413);data=json.loads(self.rfile.read(length));require(isinstance(data,dict),'JSON object required');store=self.server.store
            if self.path=='/api/setup':r=store.setup(data)
            elif self.path=='/api/login':r=store.login(data,self.client_address[0])
            else:
                u=store.user(self.bearer())
                if self.path=='/api/logout':
                    with store.lock,store.db:store.db.execute('DELETE FROM logins WHERE token=?',(digest(self.bearer()),))
                    r=dict(ok=True)
                else:r=store.mutate(u,self.path,data)
            self.reply(200,r)
        except Problem as e:self.reply(e.status,dict(error=e.message))
        except (ValueError,TypeError):self.reply(400,dict(error='Invalid JSON or parameters'))
        except Exception:self.reply(500,dict(error='Action could not complete. Refresh before retrying.'))
