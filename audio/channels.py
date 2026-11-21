"""Overlap monitoring across separate authenticated microphones, not source separation."""
import time
from .gates import pcm_quality

class Channels:
    def __init__(self,clock=time.monotonic):self.clock=clock;self.channels={}
    def add(self,key,stream):self.channels[key]=dict(stream=stream,until=0,noise=.004,frames=0)
    def remove(self,key):self.channels.pop(key,None)
    def feed(self,key,raw):
        entry=self.channels[key];q=pcm_quality(raw);now=self.clock()
        # Estimate quiet-room floor on low-energy frames only; energy is not a neural VAD.
        if q['rms']<entry['noise']*2:entry['noise']=.98*entry['noise']+.02*q['rms']
        speech=q['rms']>max(.015,entry['noise']*3) and q['clipped']<.02
        entry['frames']=entry['frames']+1 if speech else 0
        if entry['frames']>=2:entry['until']=now+.25
        live=[v for k,v in self.channels.items() if k[0]==key[0] and v['until']>now]
        if len(live)>1:
            for v in live:v['stream'].overlap_seen=True
        return dict(active=speech,overlap=len(live)>1,noise_floor=entry['noise'])
