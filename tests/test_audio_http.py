"""Actual WebSocket transport, fake acoustic model; no speech accuracy claim."""
import asyncio,json,tempfile,unittest
from pathlib import Path
try:
 from aiohttp.test_utils import TestServer,TestClient
 from audio_server import create_app
 HAS_AIOHTTP=True
except ImportError: HAS_AIOHTTP=False
from system import SystemStore
from protocol import ROLES
from test_audio import Recognizer,packet

@unittest.skipUnless(HAS_AIOHTTP,'Install requirements-audio.txt for WebSocket integration tests')
class AudioHTTPTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=SystemStore(Path(self.tmp.name)/'db')
  self.admin=self.store.setup(dict(username='admin',name='Admin',password='admin-test-password'))
  self.user=self.admin['user'];self.members={}
  for role in ROLES:
   data=dict(username=role.lower(),name=role,role=role,password='member-test-password')
   self.store.mutate(self.user,'/api/users',data);self.members[role]=self.store.login(data,role)
  self.store.mutate(self.user,'/api/protocols/approve',dict(id='SG-SIM-03',note='Synthetic test',attest=True))
  self.session=self.store.create_study(self.user,dict(title='Audio test',case='SIM-024',protocol='SG-SIM-03',mode='assisted',team={r:m['user']['id'] for r,m in self.members.items()}))['state']['id']
  self.store.action(self.user,dict(session=self.session,action='toggle',version=0))
  self.recognizers=[]
  def factory():
   rec=Recognizer();self.recognizers.append(rec);return rec
  self.client=TestClient(TestServer(create_app(self.store,factory,'http://127.0.0.1:1')));await self.client.start_server()
  self.origin=str(self.client.make_url('/')).rstrip('/')
 async def asyncTearDown(self):
  await self.client.close();self.store.db.close();self.tmp.cleanup()
 async def connect(self,token=None):
  ws=await self.client.ws_connect('/api/audio/stream',headers={'Origin':self.origin})
  await ws.send_json(dict(token=token or self.members['Nurse']['token'],session=self.session,item=0))
  return ws,await ws.receive_json()
 async def test_real_transport_enrollment_and_explicit_confirmation(self):
  ws,hello=await self.connect();self.assertEqual(hello['type'],'ready')
  for i in range(3):
   await ws.send_bytes(packet(i));self.assertEqual((await ws.receive_json())['type'],'enrollment')
  self.assertEqual(self.store.read(self.session)['items'][0]['status'],'waiting')
  await ws.send_bytes(packet(3));out=await ws.receive_json();self.assertEqual(out['type'],'evidence')
  self.assertEqual(self.store.read(self.session)['items'][0]['status'],'pending')
  self.assertTrue(any(e['type']=='LOCAL_AUDIO_EVIDENCE' for e in self.store.read(self.session)['log']))
  self.recognizers[0].value['spk']=[0,1,0]
  await ws.send_bytes(packet(4));self.assertEqual((await ws.receive_json())['type'],'rejected')
  self.assertEqual(self.store.read(self.session)['items'][0]['status'],'flag')
  await ws.close()
 async def test_role_revocation_and_duplicate_connection(self):
  ws,event=await self.connect(self.admin['token']);self.assertEqual(event['type'],'error');await ws.close()
  first,event=await self.connect();self.assertEqual(event['type'],'ready')
  second,event=await self.connect();self.assertEqual(event['type'],'error');await second.close()
  third,event=await self.connect();self.assertEqual(event['type'],'error');await third.close()
  with self.store.db:self.store.db.execute('DELETE FROM logins')
  await first.send_bytes(packet(0));self.assertEqual((await first.receive_json())['type'],'error');await first.close()
 async def test_other_item_changes_do_not_disconnect_channel(self):
  ws,event=await self.connect();self.assertEqual(event['type'],'ready')
  self.store.action(self.user,dict(session=self.session,action='evidence',version=self.store.read(self.session)['version'],item=1,kind='clean',role='Surgeon',text='Patient Alex Morgan elective procedure left confirmed',confidence=.97))
  await ws.send_bytes(packet(0));self.assertEqual((await ws.receive_json())['type'],'enrollment');await ws.close()
 async def test_external_state_change_aborts_and_origin_rejected(self):
  ws,event=await self.connect()
  self.store.action(self.user,dict(session=self.session,action='toggle',version=self.store.read(self.session)['version']))
  await ws.send_bytes(packet(0));self.assertEqual((await ws.receive_json())['type'],'error');await ws.close()
  response=await self.client.get('/api/audio/stream',headers={'Origin':'https://wrong.example'})
  self.assertEqual(response.status,403)
