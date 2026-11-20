/* Microphone-only capture. Never connect synthesized audio to this input. */
class SGPCM extends AudioWorkletProcessor {
  constructor(){super();this.sum=0;this.n=0;this.phase=0;this.out=[];this.energy=0;this.count=0;}
  process(inputs,outputs){
    const input=inputs[0]?.[0];if(!input)return true;
    for(const sample of input){
      this.sum+=sample;this.n++;this.phase+=16000;
      if(this.phase>=sampleRate){
        this.phase-=sampleRate;const x=this.sum/this.n;this.sum=0;this.n=0;
        this.out.push(Math.round(Math.max(-1,Math.min(1,x))*32767));this.energy+=x*x;this.count++;
        if(this.out.length===1600){
          const pcm=new Int16Array(this.out);this.port.postMessage({pcm:pcm.buffer,rms:Math.sqrt(this.energy/this.count)},[pcm.buffer]);
          this.out=[];this.energy=0;this.count=0;
        }
      }
    }
    // AudioWorklet outputs remain zero. Capture stays alive without microphone feedback.
    return true;
  }
}
registerProcessor('sg-pcm',SGPCM);
