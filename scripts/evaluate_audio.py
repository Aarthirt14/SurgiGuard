"""Replay labeled, consented synthetic WAV recordings against actual local models.

Usage: python scripts/evaluate_audio.py study.json --model models/... --speaker-model models/...
No audio or embeddings are included in the output. Ground truth never drives inference.
"""
import argparse,json,sys,time,wave
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audio.gates import Speakers,word_confidence,pcm_quality


def edits(reference,hypothesis):
    a=reference.lower().split();b=hypothesis.lower().split();prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        row=[i]
        for j,y in enumerate(b,1):row.append(min(row[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
        prev=row
    return prev[-1],len(a)


def recognize(path,factory):
    rec=factory();parts=[];samples=0;clipped=0;start=time.perf_counter()
    with wave.open(str(path),'rb') as f:
        if (f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getcomptype())!=(1,2,16000,'NONE'):
            raise ValueError('Recordings must be mono PCM16 WAV at 16000 Hz')
        if f.getnframes()>16000*60:raise ValueError('Each evaluation recording must be <=60 seconds')
        while raw:=f.readframes(1600):
            n=len(raw)//2;samples+=n;clipped+=pcm_quality(raw)['clipped']*n
            if rec.AcceptWaveform(raw):parts.append(json.loads(rec.Result()))
        parts.append(json.loads(rec.FinalResult()))
    return [p for p in parts if p.get('text')],clipped/max(samples,1),time.perf_counter()-start,samples/16000


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest');p.add_argument('--model',required=True);p.add_argument('--speaker-model',required=True);p.add_argument('--output',default='audio-report.json');args=p.parse_args()
    from vosk import Model,SpkModel,KaldiRecognizer
    model,spk=Model(args.model),SpkModel(args.speaker_model)
    def factory():
        r=KaldiRecognizer(model,16000);r.SetWords(True);r.SetSpkModel(spk);return r
    manifest=Path(args.manifest);data=json.loads(manifest.read_text());speakers=Speakers()
    if data.get('synthetic_only') is not True:raise ValueError('Only consented recordings of synthetic scenarios are supported')
    if len(data['enrollment'])!=3:raise ValueError('Provide exactly three enrollment recordings')
    enrollment=[]
    for name in data['enrollment']:
        results,clip,_,_=recognize(manifest.parent/name,factory)
        try:
            if len(results)!=1 or clip>.02 or (word_confidence(results[0]) or 0)<.85:
                raise ValueError('One clear, confidently transcribed utterance required')
            speakers.enroll(results[0].get('spk'),results[0].get('spk_frames',0))
            enrollment.append(dict(file=name,accepted=True))
        except ValueError as e:enrollment.append(dict(file=name,accepted=False,reason=str(e)))
    enrolled=speakers.reference is not None
    rows=[];errors=words=0
    for case in data['trials']:
        if type(case.get('expected_speaker')) is not bool or type(case.get('overlap')) is not bool:raise ValueError('Independent speaker and overlap labels required')
        results,clip,processing,duration=recognize(manifest.parent/case['file'],factory)
        transcript=' '.join(r['text'] for r in results);err,n=edits(case['reference'],transcript);errors+=err;words+=n
        matches=[speakers.identify(r.get('spk'),r.get('spk_frames',0)) for r in results]
        # Same acoustic gates as live ingestion; no use of expected_speaker or overlap labels.
        accepted=bool(results) and clip<=.02 and all(m['accepted'] and (word_confidence(r) or 0)>=.85 for r,m in zip(results,matches))
        rows.append(dict(id=case['id'],condition=case['condition'],expected_speaker=case['expected_speaker'],overlap=case['overlap'],
            accepted=accepted,word_errors=err,reference_words=n,processing_seconds=processing,audio_seconds=duration,
            real_time_factor=processing/duration if duration else None,speaker_labels=[m['label'] for m in matches]))
    non_target=[r for r in rows if not r['expected_speaker'] or r['overlap']]
    target=[r for r in rows if r['expected_speaker'] and not r['overlap']]
    report=dict(nonclinical=True,engine='vosk',clinical_validation=False,
        note='Offline processing timing is not live response latency. Acceptance is an audio gate, never checklist completion.',
        word_error_rate=errors/words if words else None,trials=len(rows),enrollment=enrollment,speaker_metrics_valid=enrolled,corpus_provenance=data.get('provenance','user-supplied recordings'),
        false_accept_rate=sum(r['accepted'] for r in non_target)/len(non_target) if non_target and enrolled else None,
        target_accept_rate=sum(r['accepted'] for r in target)/len(target) if target and enrolled else None,results=rows)
    Path(args.output).write_text(json.dumps(report,indent=2));print(args.output)
if __name__=='__main__':main()
