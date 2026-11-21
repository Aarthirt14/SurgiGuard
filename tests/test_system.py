import json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from server import Problem,ThreadingHTTPServer
from system import SystemStore,SystemHandler,digest
from protocol import ROLES

class SystemTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=SystemStore(Path(self.tmp.name)/'db')
  login=self.store.setup(dict(username='coordinator',name='Research Lead',password='test-password-123'));self.admin=self.store.user(login['token']);self.token=login['token'];self.members={}
  for role in ROLES:
   data=dict(username=role.lower(),name='Test '+role,role=role,password='member-password-123');self.store.mutate(self.admin,'/api/users',data);self.members[role]=self.store.user(self.store.login(data,role)['token'])
  self.team={r:u['id'] for r,u in self.members.items()}
 def tearDown(self):self.store.db.close();self.tmp.cleanup()
 def approve(self):self.store.mutate(self.admin,'/api/protocols/approve',dict(id='SG-SIM-03',note='Reviewed synthetic script',attest=True))
 def create(self):return self.store.create_study(self.admin,dict(title='Test simulation',case='SIM-025',protocol='SG-SIM-03',team=self.team,mode='assisted',trial_group='pair-01'))
 def act(self,user,sid,action,**kw):return self.store.action(user,dict(session=sid,action=action,version=self.store.read(sid)['version'],**kw))
 def test_draft_gate_and_case_bound_immutable_snapshot(self):
  with self.assertRaises(Problem):self.create()
  self.approve();r=self.create();self.assertIn('Jordan Taylor',r['protocol'][1]['expected'])
  self.store.mutate(self.admin,'/api/protocols',dict(base='SG-SIM-03',name='Future revision',note='Future study'))
  self.assertEqual(self.store.session(self.admin,r['state']['id'])['protocol'],r['protocol'])
 def test_account_authority_and_session_isolation(self):
  self.approve();sid=self.create()['state']['id'];self.act(self.admin,sid,'toggle')
  with self.assertRaises(Problem):self.act(self.admin,sid,'confirm',item=0)
  with self.assertRaises(Problem):self.act(self.members['Nurse'],sid,'evidence',item=0,kind='clean',text='Team introduced',role='Nurse',confidence=.97)
  with self.assertRaises(Problem):self.act(self.members['Nurse'],sid,'role',role='Surgeon')
  self.act(self.members['Nurse'],sid,'evidence',item=0,kind='typed',text='All team members introduced',role='Surgeon',confidence=1)
  self.assertEqual(self.store.read(sid)['items'][0]['evidence']['role'],'Nurse')
  with self.assertRaises(Problem):self.act(self.members['Surgeon'],sid,'confirm',item=0)
  self.act(self.members['Nurse'],sid,'confirm',item=0)
  self.store.mutate(self.admin,'/api/users',dict(username='outsider',name='Other Nurse',role='Nurse',password='outsider-password'))
  outsider=self.store.user(self.store.login(dict(username='outsider',password='outsider-password'),'other')['token'])
  with self.assertRaises(Problem):self.store.session(outsider,sid)
  self.assertEqual(self.store.workspace(outsider)['sessions'],[])
 def test_complete_multi_account_closure_and_review(self):
  self.approve();r=self.create();sid=r['state']['id'];self.act(self.admin,sid,'toggle')
  with self.assertRaises(Problem):self.act(self.admin,sid,'finish')
  for i,d in enumerate(r['protocol']):
   u=self.members[d['role']];self.act(u,sid,'evidence',item=i,text=d['expected'],confidence=1,kind='typed');self.act(u,sid,'confirm',item=i)
  self.act(self.members['Surgeon'],sid,'workload',rating=3);self.act(self.admin,sid,'finish');s=self.store.read(sid);self.assertTrue(s['closed']);self.assertFalse(s['running'])
  with self.assertRaises(Problem):self.act(self.members['Nurse'],sid,'correct',item=0,reason='Cannot change closed record')
  result=self.store.mutate(self.admin,'/api/review',dict(session=sid,rating='pass',note='All simulated study steps completed'));self.assertEqual(result['reviews'][0]['rating'],'pass')
  self.assertTrue(any(e['type']=='CONFIRM' and e['detail']['account']['id']==self.members['Nurse']['id'] for e in s['log']))
 def test_password_auth_and_coordinator_permissions(self):
  with self.assertRaises(Problem):self.store.setup(dict(username='again',name='Again',password='password-again'))
  with self.assertRaises(Problem):self.store.login(dict(username='coordinator',password='wrong'),'test')
  with self.assertRaises(Problem):self.store.mutate(self.members['Nurse'],'/api/protocols/approve',dict(id='SG-SIM-03',note='Wrong role',attest=True))
  row=self.store.db.execute('SELECT password,salt FROM users WHERE id=?',(self.admin['id'],)).fetchone();self.assertNotEqual(row[0],'test-password-123');self.assertEqual(len(row[1]),32)
  self.store.db.execute('DELETE FROM logins WHERE token=?',(digest(self.token),));self.store.db.commit()
  with self.assertRaises(Problem):self.store.user(self.token)

 def test_study_scores_require_coordinator_and_preserve_versions(self):
  from study import FIELDS
  self.approve();sid=self.create()['state']['id']
  data=dict(session=sid,participant='TEST-ONLY',method='Independent synthetic fixture labels',items=[{**{k:False for k in FIELDS},'latency_ms':None} for _ in range(6)])
  with self.assertRaises(Problem):self.store.mutate(self.members['Nurse'],'/api/study/score',data)
  first=self.store.mutate(self.admin,'/api/study/score',data)
  self.assertEqual(len(first['scores']),1);self.assertIsNone(first['scores'][0]['metrics']['omission_recall'])
  self.act(self.admin,sid,'toggle')
  with self.assertRaises(Problem):self.store.mutate(self.admin,'/api/study/score',data)
  self.act(self.admin,sid,'toggle');second=self.store.mutate(self.admin,'/api/study/score',data)
  self.assertEqual(len(second['scores']),2);self.assertLess(second['scores'][0]['state_version'],second['scores'][1]['state_version'])

class SystemHTTPTests(unittest.TestCase):
 def test_http_roundtrip_and_no_legacy_bypass(self):
  with tempfile.TemporaryDirectory() as tmp:
   server=ThreadingHTTPServer(('127.0.0.1',0),SystemHandler);server.store=SystemStore(Path(tmp)/'db');threading.Thread(target=server.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(server.server_port)
   def call(path,data=None,token=''):
    req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
    return json.load(urllib.request.urlopen(req))
   try:
    self.assertFalse(call('/api/status')['initialized'])
    with self.assertRaises(urllib.error.HTTPError):call('/api/workspace')
    r=call('/api/setup',dict(username='http-coordinator',name='HTTP Test',password='http-password-123'));t=r['token']
    self.assertEqual(call('/api/workspace',token=t)['user']['role'],'Coordinator')
    with self.assertRaises(urllib.error.HTTPError):call('/api/sessions',{},t)
    with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+'/system.py')
    call('/api/logout',{},t)
    with self.assertRaises(urllib.error.HTTPError):call('/api/workspace',token=t)
   finally:server.shutdown();server.server_close();server.store.db.close()
if __name__=='__main__':unittest.main()
