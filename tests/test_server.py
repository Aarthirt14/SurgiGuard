import hashlib,json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from server import Store,Problem,Handler,ThreadingHTTPServer
from protocol import ITEMS,assess

class WorkflowTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'test.sqlite3';self.store=Store(self.path)
  r=self.store.create('Nurse','assisted');self.token=r['token'];self.sid=r['state']['id']
 def tearDown(self): self.store.db.close();self.tmp.cleanup()
 def action(self,action,**kw): return self.store.act(self.token,dict(action=action,version=self.store.read(self.sid)['version'],**kw))
 def start(self): self.action('toggle')
 def evidence(self,i=0,**kw):
  args=dict(item=i,text=ITEMS[i]['expected'],role=ITEMS[i]['role'],confidence=.97,kind='clean');args.update(kw);return self.action('evidence',**args)
 def test_all_items_reject_uncertainty_wrong_role_negation_and_overlap(self):
  self.start()
  for i,d in enumerate(ITEMS):
   for override in [dict(confidence=None),dict(confidence=.58),dict(role='Surgeon' if d['role']=='Nurse' else 'Nurse'),dict(text='Not '+d['expected']),dict(kind='overlap'),dict(kind='omission'),dict(text='unrelated')]:
    with self.subTest(item=i,override=override):
     self.evidence(i,**override);self.assertEqual(self.store.read(self.sid)['items'][i]['status'],'flag')
     with self.assertRaises(Problem): self.action('confirm',item=i)
 def test_confirmation_requires_server_role_and_evidence(self):
  self.start()
  with self.assertRaises(Problem): self.action('confirm',item=0)
  self.evidence();self.assertEqual(self.store.read(self.sid)['items'][0]['status'],'pending')
  r=self.action('role',role='Surgeon');self.token=r['token']
  with self.assertRaises(Problem): self.action('confirm',item=0)
  self.token=self.action('role',role='Nurse')['token'];self.action('confirm',item=0)
  self.assertEqual(self.store.read(self.sid)['items'][0]['status'],'confirmed')
 def test_recovery_correction_and_override_preserve_history(self):
  self.start();self.evidence(kind='overlap');self.evidence();self.assertEqual(self.store.read(self.sid)['recoveries'],1)
  self.action('confirm',item=0)
  with self.assertRaises(Problem): self.evidence()
  with self.assertRaises(Problem): self.action('correct',item=0,reason='')
  self.action('correct',item=0,reason='Recheck the team');self.evidence();self.action('override',item=0,reason='Supervisor review requested')
  s=self.store.read(self.sid);self.assertEqual(s['items'][0]['status'],'flag');self.assertTrue(any(e['type']=='CONFIRM' for e in s['log']))
 def test_restart_persistence_and_hash_chain(self):
  self.start();self.evidence();self.action('confirm',item=0);self.store.db.close();self.store=Store(self.path)
  self.assertEqual(self.store.auth(self.token)[0],self.sid);s=self.store.read(self.sid);self.assertEqual(s['items'][0]['status'],'confirmed')
  previous='0'*64
  for event in s['log']:
   body={k:v for k,v in event.items() if k not in ('previous','hash')};self.assertEqual(event['previous'],previous)
   digest=hashlib.sha256((previous+json.dumps(body,sort_keys=True,separators=(',',':'))).encode()).hexdigest();self.assertEqual(digest,event['hash']);previous=digest
 def test_optimistic_concurrency_and_invalid_input(self):
  self.start();v=self.store.read(self.sid)['version'];self.evidence()
  with self.assertRaises(Problem): self.store.act(self.token,dict(action='confirm',item=0,version=v))
  for conf in (-1,2,float('nan'),'0.9'):
   with self.assertRaises(Problem): self.evidence(confidence=conf)
  with self.assertRaises(Problem): self.store.act('bad-token',dict(action='toggle',version=0))
 def test_pause_static_mode_and_all_six_confirmations(self):
  with self.assertRaises(Problem): self.evidence()
  self.start()
  for i,d in enumerate(ITEMS):
   self.token=self.action('role',role=d['role'])['token'];self.evidence(i);self.action('confirm',item=i)
  self.assertEqual(sum(x['status']=='confirmed' for x in self.store.read(self.sid)['items']),6)
  r=self.store.create('Nurse','static');self.token=r['token'];self.sid=r['state']['id'];self.start()
  with self.assertRaises(Problem): self.evidence()
  self.action('confirm',item=0);self.assertEqual(self.store.read(self.sid)['items'][0]['status'],'confirmed')

class HTTPTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.store=Store(Path(self.tmp.name)/'db');self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.url='http://127.0.0.1:'+str(self.server.server_port)
 def tearDown(self): self.server.shutdown();self.server.server_close();self.server.store.db.close();self.tmp.cleanup()
 def request(self,path,data=None,token='',origin=None):
  headers={'Content-Type':'application/json','Authorization':'Bearer '+token}
  if origin: headers['Origin']=origin
  req=urllib.request.Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
  return urllib.request.urlopen(req)
 def test_http_auth_origin_assets_and_roundtrip(self):
  self.assertEqual(self.request('/').status,200)
  with self.assertRaises(urllib.error.HTTPError): self.request('/api/session')
  with self.assertRaises(urllib.error.HTTPError): self.request('/api/sessions',{},origin='http://evil.test')
  with self.assertRaises(urllib.error.HTTPError): self.request('/../server.py')
  r=json.load(self.request('/api/sessions',{'role':'Nurse','mode':'assisted'}));token=r['token']
  r=json.load(self.request('/api/action',{'action':'toggle','version':0},token));self.assertTrue(r['state']['running'])
  saved=json.load(self.request('/api/session',token=token));self.assertEqual(saved['state']['version'],1)

if __name__=='__main__': unittest.main()
