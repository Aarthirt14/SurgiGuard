"""Dependency-free speaker and audio quality gates. Scores are not probabilities."""
import math
from array import array
import sys


def unit(vector):
    if not isinstance(vector, list) or not 2 <= len(vector) <= 512:
        raise ValueError('Invalid speaker vector')
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in vector):
        raise ValueError('Non-finite speaker vector')
    norm = math.sqrt(sum(x*x for x in vector))
    if norm < 1e-9:
        raise ValueError('Empty speaker vector')
    return [x / norm for x in vector]


def similarity(a, b):
    if len(a) != len(b):
        return -1
    return sum(x*y for x, y in zip(a, b))


class Speakers:
    """Three explicit enrollment samples, then conservative turn-level labeling.

    Unknown clusters are never promoted to the authenticated speaker. Vectors
    live only in this connection and are never written to the database.
    """
    def __init__(self, threshold=.75, margin=.10):
        self.samples = []
        self.reference = None
        self.others = []
        self.threshold, self.margin = threshold, margin

    def enroll(self, vector, frames):
        if self.reference is not None:
            raise ValueError('Enrollment already complete')
        if type(frames) not in (int, float) or not math.isfinite(frames) or frames < 100:
            raise ValueError('Speak for longer: at least 100 speaker frames required')
        v = unit(vector)
        if any(similarity(sample, v) < self.threshold for sample in self.samples):
            raise ValueError('Enrollment voices differ; reconnect and enroll one speaker')
        self.samples.append(v)
        if len(self.samples) == 3:
            self.reference = unit([sum(s[i] for s in self.samples) for i in range(len(v))])
        return len(self.samples)

    def identify(self, vector, frames):
        if self.reference is None or frames < 100:
            return {'label': 'unknown', 'accepted': False, 'score': None}
        try:
            v = unit(vector)
        except ValueError:
            return {'label': 'unknown', 'accepted': False, 'score': None}
        score = similarity(v, self.reference)
        other_scores = [similarity(v, x) for x in self.others]
        rival = max(other_scores, default=-1)
        if score >= self.threshold and score-rival >= self.margin:
            return {'label': 'enrolled-speaker', 'accepted': True, 'score': round(score, 4)}
        if score >= self.threshold:
            return {'label': 'ambiguous', 'accepted': False, 'score': round(score, 4)}
        if rival >= self.threshold:
            label = 'other-speaker-' + str(other_scores.index(rival)+1)
        elif len(self.others) < 8:
            self.others.append(v)
            label = 'other-speaker-' + str(len(self.others))
        else:
            label = 'unknown'
        return {'label': label, 'accepted': False, 'score': round(score, 4)}


def pcm_quality(raw):
    if not raw or len(raw) % 2:
        raise ValueError('Expected signed 16-bit mono PCM')
    values = array('h'); values.frombytes(raw)
    if sys.byteorder != 'little':
        values.byteswap()
    return {'rms': math.sqrt(sum((x/32768)**2 for x in values)/len(values)),
            'clipped': sum(abs(x) >= 32700 for x in values)/len(values)}


def word_confidence(result):
    words = result.get('result', [])
    scores = [w.get('conf') for w in words]
    if not scores or any(type(x) not in (float, int) or not math.isfinite(x) or not 0 <= x <= 1 for x in scores):
        return None
    return min(scores)  # weakest word, not a misleading average
