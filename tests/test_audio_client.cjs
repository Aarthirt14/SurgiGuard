// Audio processing and transport unit tests, not a hardware/browser test.
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
let Processor;
const context={sampleRate:48000,AudioWorkletProcessor:class {constructor(){this.port={postMessage:m=>frames.push(m)}}},registerProcessor:(name,p)=>Processor=p};
let frames=[];vm.runInNewContext(fs.readFileSync('web/pcm-worklet.js','utf8'),context);
const p=new Processor();
for(let i=0;i<375;i++)p.process([[new Float32Array(128).fill(.2)]],[]);
assert.equal(frames.length,10);assert.equal(frames[0].pcm.byteLength,3200);assert.ok(Math.abs(frames[0].rms-.2)<.001);
let sent=[],events=[],cancelled=0;
const c={window:{speechSynthesis:{cancel:()=>cancelled++}},WebSocket:{OPEN:1},Uint8Array,DataView};
vm.runInNewContext(fs.readFileSync('web/local-audio.js','utf8'),c);
const a=new c.window.LocalAudio(e=>events.push(e));a.ws={readyState:1,bufferedAmount:0,send:m=>sent.push(m),close:()=>{}};
a.frame(frames[0]);assert.equal(new DataView(sent[0].buffer).getUint32(0,true),0);
a.playback(true);for(let i=0;i<3;i++)a.frame({pcm:frames[0].pcm,rms:.1});assert.equal(cancelled,1);
assert.ok(sent.some(m=>typeof m==='string'&&JSON.parse(m).type==='interrupt'));
a.ws.bufferedAmount=100000;a.frame(frames[0]);assert.equal(a.closed,true);assert.equal(events.at(-1).type,'error');
console.log('Audio client: 16 kHz framing, RMS, sequence, barge-in and backpressure passed.');
