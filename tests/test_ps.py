import json,unittest
from unittest.mock import patch
from server import Store,Problem
from omissions import poll
from study import metrics,validate,FIELDS
from audio.channels import Channels
from audio.stream import Stream
from test_audio import Recognizer,packet

class PSTests(unittest.TestCase):
 def setUp(self):self.store=Store(':memory:')
 def tearDown(self):self.store.db.close()
 def test_automatic_omission_pause_resume_and_no_spam(self):
  r=self.store.create('Nurse','assisted');t=r['token'];sid=r['state']['id']
  def act(a,**kw):return self.store.act(t,dict(action=a,version=self.store.read(sid)['version'],**kw))
  with patch('server.time.time',return_value=100):
   act('toggle');act('prompt',item=0,timeout=5)
  self.assertEqual(poll(self.store,104),[])
  with patch('server.time.time',return_value=104):act('toggle')
  self.assertEqual(poll(self.store,200),[])
  with patch('server.time.time',return_value=200):act('toggle')
  self.assertEqual(poll(self.store,202),[(sid,0)])
  self.assertEqual(poll(self.store,300),[])
  self.assertEqual(self.store.read(sid)['items'][0]['kind'],'omission')
  with self.assertRaises(Problem):act('confirm',item=0)
 def test_static_and_resolved_items_have_no_omission(self):
  for mode in ('static','assisted'):
   r=self.store.create('Nurse',mode);t=r['token'];sid=r['state']['id']
   def act(a,**kw):return self.store.act(t,dict(action=a,version=self.store.read(sid)['version'],**kw))
   act('toggle')
   if mode=='static':
    with self.assertRaises(Problem):act('prompt',item=0)
   else:
    act('prompt',item=0,timeout=5);act('evidence',item=0,text='all team members introduced',role='Nurse',confidence=1,kind='typed')
   self.assertEqual(poll(self.store,10**12),[])
 def test_duplex_transcribes_but_playback_never_accepted(self):
  r=Recognizer();s=Stream(r,lambda *a:self.fail('Echo accepted'),duplex=True)
  s.playback(True);out=s.feed(packet(0));self.assertEqual(r.calls,1);self.assertEqual(out['type'],'rejected');self.assertTrue(out['echo'])
 def test_multichannel_overlap_session_isolation_and_release(self):
  now=[1];m=Channels(clock=lambda:now[0]);a=Stream(Recognizer(),lambda *a:None);b=Stream(Recognizer(),lambda *a:None);c=Stream(Recognizer(),lambda *a:None)
  m.add(('one','a'),a);m.add(('one','b'),b);m.add(('two','c'),c)
  raw=packet(0)[4:]
  for _ in range(2):m.feed(('one','a'),raw)
  for _ in range(2):m.feed(('two','c'),raw)
  self.assertFalse(a.overlap_seen)
  for _ in range(2):m.feed(('one','b'),raw)
  self.assertTrue(a.overlap_seen);self.assertTrue(b.overlap_seen);self.assertFalse(c.overlap_seen)
  self.assertEqual(a.feed(packet(0))['type'],'rejected');m.remove(('one','a'));self.assertNotIn(('one','a'),m.channels)
 def test_metrics_null_denominators_and_validation(self):
  row={k:False for k in FIELDS};row.update(completion_correct=True,latency_ms=100)
  other=dict(row,completion_correct=False,omission_expected=True,omission_detected=True,prompt_required=True,interruption_expected=True,recovered=True,latency_ms=300)
  m=metrics([row,other]);self.assertEqual(m['completion_accuracy'],.5);self.assertEqual(m['omission_recall'],1);self.assertEqual(m['median_latency_ms'],200)
  self.assertIsNone(metrics([row])['omission_recall']);self.assertIsNone(metrics([])['completion_accuracy'])
  with self.assertRaises(ValueError):validate(dict(participant='X',method='independent video labels',items=[dict(row,latency_ms=float('nan'))]),1)
if __name__=='__main__':unittest.main()
