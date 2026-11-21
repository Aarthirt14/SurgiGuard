/* Local continuous PCM transport; transcript/role decisions stay on the server. */
class LocalAudio {
  constructor(onEvent){this.onEvent=onEvent;this.closed=false;this.seq=0;this.playing=false;this.loud=0;}
  async start(token,session,item,duplex=false){
    try{
      this.media=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
      if(this.closed){this.media.getTracks().forEach(t=>t.stop());return;}
      this.media.getTracks().forEach(t=>t.onended=()=>{if(!this.closed){this.onEvent({type:'error',message:'Microphone ended. Reconnect to continue.'});this.stop();}});
      this.ctx=new AudioContext();await this.ctx.audioWorklet.addModule('/pcm-worklet.js');
      if(this.closed){await this.ctx.close();return;}
      const scheme=location.protocol==='https:'?'wss:':'ws:';
      this.ws=new WebSocket(scheme+'//'+location.host+'/api/audio/stream');
      this.ws.onopen=()=>this.ws.send(JSON.stringify({token,session,item,duplex}));
      this.ws.onmessage=async e=>{
        if(this.closed)return;
        const data=JSON.parse(e.data);
        if(data.type==='ready'){
          if(this.closed)return;
          this.source=this.ctx.createMediaStreamSource(this.media);
          this.node=new AudioWorkletNode(this.ctx,'sg-pcm');
          this.node.port.onmessage=e=>this.frame(e.data);
          this.source.connect(this.node);this.node.connect(this.ctx.destination);await this.ctx.resume();
          const settings=this.media.getAudioTracks()[0].getSettings();
          this.onEvent({type:'device',message:'Local PCM · echo cancellation '+(settings.echoCancellation?'enabled':'unavailable')+' · enrollment required'});
        }
        this.onEvent(data);
        if(data.type==='error')this.stop();
      };
      this.ws.onerror=()=>{this.onEvent({type:'error',message:'Audio connection failed. Start audio_server.py or use browser/typed input.'});this.stop();};
      this.ws.onclose=()=>{if(!this.closed){this.onEvent({type:'error',message:'Audio disconnected. Partial speech discarded; reconnect to continue.'});this.stop();}};
    }catch(e){this.stop();throw e;}
  }
  send(data){if(this.ws?.readyState===WebSocket.OPEN)this.ws.send(JSON.stringify(data));}
  playback(active){this.playing=active;this.loud=0;this.send({type:'playback',active});}
  frame({pcm,rms}){
    if(this.closed||this.ws?.readyState!==WebSocket.OPEN)return;
    if(this.ws.bufferedAmount>64000){this.onEvent({type:'error',message:'Audio backpressure. Capture stopped; repeat after reconnecting.'});this.stop();return;}
    if(this.playing){
      this.loud=rms>.045?this.loud+1:0;
      if(this.loud>=3){this.playing=false;window.speechSynthesis?.cancel();this.send({type:'interrupt'});}
    }
    const frame=new Uint8Array(4+pcm.byteLength);new DataView(frame.buffer).setUint32(0,this.seq++,true);frame.set(new Uint8Array(pcm),4);this.ws.send(frame);
  }
  stop(){if(this.closed)return;this.closed=true;this.node?.disconnect();this.source?.disconnect();this.media?.getTracks().forEach(t=>t.stop());this.ctx?.close().catch(()=>{});this.ws?.close();}
}
window.LocalAudio=LocalAudio;
