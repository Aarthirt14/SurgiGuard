"""Reproducible TTS/noise fixtures, not human recordings. Requires FFmpeg with libflite."""
import argparse,array,json,math,random,subprocess,sys,tempfile,wave
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from protocol import ITEMS

def write(path,values):
    a=array.array('h',(max(-32768,min(32767,round(x))) for x in values))
    if sys.byteorder!='little':a.byteswap()
    with wave.open(str(path),'wb') as f:f.setparams((1,2,16000,0,'NONE','not compressed'));f.writeframes(a.tobytes())
def read(path):
    with wave.open(str(path),'rb') as f:a=array.array('h',f.readframes(f.getnframes()))
    if sys.byteorder!='little':a.byteswap()
    return list(a)
def synth(text,voice,path):
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp,'input.txt').write_text(text)
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i',f'flite=textfile=input.txt:voice={voice}','-ar','16000','-ac','1','-y',str(path.resolve())],cwd=tmp,check=True)
    data=read(path);write(path,data+[0]*16000);return data

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',default='data/audio-corpus');a=p.parse_args();root=Path(a.output);root.mkdir(parents=True,exist_ok=True)
    enroll=['The team will listen carefully and take turns speaking during this training exercise.',
            'This is a fictional case and every response must be checked by the designated person.',
            'We will pause after each sentence so the computer can process the spoken response.']
    for i,t in enumerate(enroll,1):synth(t,'kal',root/f'enroll-{i}.wav')
    rows=[];rng=random.Random(42)
    for item in ITEMS:
        clean=synth(item['expected'],'kal',root/(item['id']+'-clean.wav'))
        other=synth('Please pause. I have a different response and need the team to listen.','slt',root/'other.wav')
        rms=math.sqrt(sum(x*x for x in clean)/max(len(clean),1))
        for condition,snr in [('clean',None),('noise10',10),('noise0',0),('overlap',None)]:
            name=item['id']+'-'+condition+'.wav'
            if condition.startswith('noise'):
                std=rms/(10**(snr/20));values=[x+rng.gauss(0,std) for x in clean]
            elif condition=='overlap':values=[.6*x+.6*other[i%len(other)] for i,x in enumerate(clean)]
            else:values=clean
            write(root/name,values+[0]*16000)
            rows.append(dict(id=item['id']+'-'+condition,file=name,condition=condition,snr_db=snr,reference=item['expected'].lower().rstrip('.'),expected_speaker=True,overlap=condition=='overlap'))
    text='Not confirmed. There is a discrepancy and the team must repeat the verification.'
    synth(text,'slt',root/'wrong-speaker.wav')
    rows.append(dict(id='wrong-speaker',file='wrong-speaker.wav',condition='different speaker',reference=text.lower().replace('.',''),expected_speaker=False,overlap=False))
    write(root/'silence.wav',[0]*16000*6)
    rows.append(dict(id='silence',file='silence.wav',condition='silence',reference='',expected_speaker=False,overlap=False))
    manifest=dict(synthetic_only=True,provenance='FFmpeg libflite synthetic voices kal/slt; deterministic Gaussian noise seed 42; not humans or OR acoustics',enrollment=[f'enroll-{i}.wav' for i in range(1,4)],trials=rows)
    (root/'study.json').write_text(json.dumps(manifest,indent=2));print(root/'study.json')
if __name__=='__main__':main()
