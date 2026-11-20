"""Transport-independent streaming state machine, tested with injected recognizers."""
import json
import time
from .gates import Speakers, pcm_quality, word_confidence

class Stream:
    def __init__(self, recognizer, emit, enroll=True, clock=time.monotonic):
        self.rec, self.emit, self.clock = recognizer, emit, clock
        self.speakers = Speakers()
        self.enrolling = enroll
        self.sequence = 0
        self.playing = False
        self.cooldown = 0
        self.samples = 0
        self.clipped = 0
        self.started = clock()
        self.last_partial = ''

    def reset(self):
        self.rec.Reset()
        self.samples = self.clipped = 0
        self.last_partial = ''
        self.started = self.clock()

    def playback(self, active):
        self.playing = active
        self.cooldown = self.clock()+.6
        self.reset()

    def feed(self, packet):
        if not 6 <= len(packet) <= 6404 or (len(packet)-4) % 2:
            raise ValueError('Invalid PCM frame size')
        seq = int.from_bytes(packet[:4], 'little')
        if seq != self.sequence:
            raise ValueError('Audio sequence gap: reconnect; no automatic retry')
        self.sequence += 1
        raw = packet[4:]
        quality = pcm_quality(raw)
        if self.playing or self.clock() < self.cooldown:
            return {'type': 'listening', 'reason': 'Playback echo guard'}
        count = len(raw)//2
        self.samples += count
        self.clipped += quality['clipped']*count
        if self.samples > 16000*20:
            self.reset()
            return {'type': 'rejected', 'reason': 'Utterance exceeded 20 seconds; repeat one item'}
        if not self.rec.AcceptWaveform(raw):
            result = json.loads(self.rec.PartialResult())
            partial = result.get('partial', '')[:2000]
            if partial != self.last_partial:
                self.last_partial = partial
                return {'type': 'partial', 'text': partial}
            return None
        result = json.loads(self.rec.Result())
        text = result.get('text', '')[:2000]
        clipping = self.clipped/max(self.samples, 1)
        self.samples = self.clipped = 0
        self.last_partial = ''
        if not text:
            return None
        confidence = word_confidence(result)
        if clipping > .02 or confidence is None or confidence < .85:
            return {'type': 'rejected', 'text': text, 'reason': 'Clipping or uncertain transcription; repeat', 'confidence': confidence}
        if self.enrolling:
            try:
                count = self.speakers.enroll(result.get('spk'), result.get('spk_frames', 0))
            except ValueError as exc:
                return {'type': 'rejected', 'reason': str(exc)}
            self.enrolling = count < 3
            return {'type': 'enrollment', 'count': count, 'ready': not self.enrolling}
        speaker = self.speakers.identify(result.get('spk'), result.get('spk_frames', 0))
        if not speaker['accepted']:
            return {'type': 'rejected', 'text': text, 'speaker': speaker, 'reason': 'Different, short or ambiguous voice; nothing accepted'}
        receipt = self.emit(text, confidence, speaker)
        return {'type': 'evidence', 'text': text, 'confidence': confidence, 'speaker': speaker, 'receipt': receipt}
