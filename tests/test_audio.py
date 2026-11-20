import json, struct, unittest
from audio.gates import Speakers, pcm_quality, word_confidence
from audio.stream import Stream


def result(vector=None,conf=.98):
    return dict(text='all team members introduced',result=[dict(word='introduced',conf=conf)],spk=vector or [1,0,0],spk_frames=150)

class Recognizer:
    def __init__(self):self.value=result();self.calls=0;self.resets=0
    def Reset(self):self.resets+=1
    def AcceptWaveform(self,raw):self.calls+=1;return True
    def Result(self):return json.dumps(self.value)
    def PartialResult(self):return json.dumps({'partial':'team'})

def packet(n,value=1000):return struct.pack('<I',n)+struct.pack('<1600h',*([value]*1600))

class AudioTests(unittest.TestCase):
    def test_enrollment_unknown_and_short_voice(self):
        s=Speakers()
        with self.assertRaises(ValueError):s.enroll([1,0],10)
        for _ in range(3):s.enroll([1,0],150)
        self.assertTrue(s.identify([1,0],150)['accepted'])
        self.assertFalse(s.identify([1,0],10)['accepted'])
        self.assertEqual(s.identify([0,1],150)['label'],'other-speaker-1')
        self.assertEqual(s.identify([0,1],150)['label'],'other-speaker-1')
        self.assertFalse(s.identify([float('nan'),1],150)['accepted'])
    def test_mixed_enrollment_and_dimension_rejected(self):
        s=Speakers();s.enroll([1,0],150)
        with self.assertRaises(ValueError):s.enroll([0,1],150)
        with self.assertRaises(ValueError):s.enroll([1,0,0],150)
    def test_minimum_word_confidence(self):
        self.assertIsNone(word_confidence({}))
        self.assertIsNone(word_confidence({'result':[{'conf':float('nan')}]}))
        self.assertEqual(word_confidence({'result':[{'conf':.99},{'conf':.4}]}),.4)
        self.assertEqual(pcm_quality(struct.pack('<2h',32767,-32768))['clipped'],1)
    def test_enrollment_never_emits_and_other_voice_abstains(self):
        emitted=[];r=Recognizer();s=Stream(r,lambda *args:emitted.append(args))
        for i in range(3):self.assertEqual(s.feed(packet(i))['type'],'enrollment')
        self.assertEqual(emitted,[])
        self.assertEqual(s.feed(packet(3))['type'],'evidence')
        r.value=result([0,1,0]);self.assertEqual(s.feed(packet(4))['type'],'rejected')
        self.assertEqual(len(emitted),1)
    def test_gap_clipping_and_unknown_confidence(self):
        s=Stream(Recognizer(),lambda *a:None)
        with self.assertRaises(ValueError):s.feed(packet(1))
        self.assertEqual(s.feed(packet(0,32767))['type'],'rejected')
        s.rec.value=result(conf=.4);self.assertEqual(s.feed(packet(1))['type'],'rejected')
    def test_playback_and_cooldown_never_transcribe(self):
        clock=[0];r=Recognizer();s=Stream(r,lambda *a:None,clock=lambda:clock[0])
        s.playback(True);s.feed(packet(0));self.assertEqual(r.calls,0)
        s.playback(False);s.feed(packet(1));self.assertEqual(r.calls,0)
        clock[0]=1;s.feed(packet(2));self.assertEqual(r.calls,1)

if __name__=='__main__':unittest.main()
