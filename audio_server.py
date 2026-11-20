"""Local Vosk streaming gateway. Run only with downloaded models; see docs/AUDIO.md."""
import argparse
import asyncio
import json
import os
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
from server import ThreadingHTTPServer, Problem, require, ROOT
from system import SystemHandler, SystemStore
from audio.stream import Stream


def create_app(store, recognizer_factory, backend_url):
    from aiohttp import web, ClientSession, WSMsgType
    app = web.Application(client_max_size=16000)
    client_key = web.AppKey('upstream_client', ClientSession)
    active = set()

    async def audio(request):
        origin = urlparse(request.headers.get('Origin', ''))
        if origin.netloc != request.host or origin.scheme not in ('http', 'https'):
            raise web.HTTPForbidden(text='Same-origin browser required')
        ws = web.WebSocketResponse(max_msg_size=7000, heartbeat=15, receive_timeout=30)
        await ws.prepare(request)
        key = None
        registered = False
        try:
            hello = await asyncio.wait_for(ws.receive_json(), 10)
            token = hello.get('token', '')
            u = store.user(token)
            sid, item = hello.get('session'), hello.get('item')
            require(u['role'] in ('Surgeon','Anaesthetist','Nurse'), 'Use an assigned clinician account', 403)
            current = store.session(u, sid)['state']
            require(type(item) is int and 0 <= item < len(current['items']), 'Select an item')
            require(current['running'] and not current['closed'] and current['mode']=='assisted', 'Start an assisted session')
            require(current['definitions'][item]['role']==u['role'], 'Select an item assigned to your role', 403)
            require(current['items'][item]['status']!='confirmed', 'Reopen confirmed items first')
            key = (sid,u['id'])
            require(key not in active and len(active)<4, 'Audio capacity reached or account already streaming', 409)
            active.add(key)
            registered = True
            version = current['version']
            def emit(text, confidence, speaker):
                nonlocal version
                # Re-authenticate every accepted utterance. Never use client-supplied role or score.
                user = store.user(token)
                with store.lock:
                    result = store.action(user, dict(session=sid, action='evidence', version=version,
                        item=item, text=text, confidence=confidence, kind='speech'))
                    version = result['state']['version']
                    with store.db:
                        store.event(sid, 'LOCAL_AUDIO_EVIDENCE', item,
                            dict(user=user['id'],speaker=speaker,engine='vosk',role_source='authenticated-account',
                                 confirmation='required',confidence_rule='minimum word confidence'))
                return dict(version=version,status=result['state']['items'][item]['status'])
            rec = await asyncio.to_thread(recognizer_factory)
            stream = Stream(rec, emit)
            await ws.send_json(dict(type='ready', enrollment=3, sampleRate=16000,
                message='Read three distinct synthetic sentences, pausing after each. Enrollment never completes an item.'))
            start = time.monotonic(); byte_count = 0; messages = 0
            while not ws.closed:
                msg = await asyncio.wait_for(ws.receive(), max(.01,min(30,1800-(time.monotonic()-start))))
                # Revocation, pause and conflicting edits stop capture before any new inference.
                store.user(token)
                state = store.session(u, sid)['state']
                require(state['running'] and not state['closed'] and state['version']==version,
                        'Session changed or paused. Reconnect to preserve item attribution',409)
                elapsed = time.monotonic()-start
                require(elapsed < 1800, 'Audio session limit reached')
                messages += 1
                require(messages <= 80*(elapsed+2), 'Audio message rate exceeded')
                if msg.type == WSMsgType.BINARY:
                    byte_count += len(msg.data)
                    require(byte_count <= 40000*(elapsed+2), 'Audio upload exceeds real-time rate')
                    result = await asyncio.to_thread(stream.feed, msg.data)
                    if result:
                        if result['type']=='rejected':
                            # New uncertain evidence must invalidate any prior pending candidate.
                            if not stream.enrolling:
                                rejected = store.action(u,dict(session=sid,action='evidence',version=version,
                                    item=item,text=result.get('text','[Unresolved audio]'),confidence=None,kind='speech'))
                                version = rejected['state']['version']
                            with store.lock,store.db:
                                store.event(sid,'AUDIO_ABSTENTION',item,dict(user=u['id'],**result))
                        await ws.send_json(result)
                elif msg.type == WSMsgType.TEXT:
                    command = json.loads(msg.data)
                    if command.get('type')=='playback':
                        require(type(command.get('active')) is bool,'Invalid playback state')
                        stream.playback(command['active'])
                    elif command.get('type')=='interrupt':
                        stream.playback(False)
                        result = store.action(u,dict(session=sid,action='interrupt',version=version,
                            item=item,kind='interruption',text='[Local audio barge-in; repeat after prompt stops]',confidence=None))
                        version=result['state']['version']
                        await ws.send_json(dict(type='interrupted',message='Context retained. Please repeat your complete response.'))
                    else:
                        raise ValueError('Unknown audio command')
                elif msg.type in (WSMsgType.CLOSE,WSMsgType.CLOSED,WSMsgType.ERROR):
                    break
        except (Problem, ValueError, KeyError, TypeError, asyncio.TimeoutError) as exc:
            if not ws.closed:
                await ws.send_json(dict(type='error',message=str(getattr(exc,'message',None) or exc)[:200]))
        except Exception:
            if not ws.closed:
                await ws.send_json(dict(type='error',message='Local audio engine stopped; reconnect or use typed evidence'))
        finally:
            if registered:
                active.discard(key)
            await ws.close()
        return ws

    async def capabilities(request):
        return web.json_response(dict(available=True,engine='vosk-local',speakerEnrollment=True,
            simultaneousSeparation=False,clinicalValidation=False))

    async def proxy(request):
        # Fixed loopback upstream, no arbitrary URL forwarding. Preserve original Origin/Host.
        async with app[client_key].request(request.method,backend_url+request.rel_url.raw_path_qs,
                data=await request.read(),headers={k:v for k,v in request.headers.items()
                    if k.lower() not in ('connection','transfer-encoding','content-length')},allow_redirects=False) as response:
            return web.Response(body=await response.read(),status=response.status,
                headers={k:v for k,v in response.headers.items() if k.lower() not in
                         ('transfer-encoding','connection','content-length','content-encoding')})
    async def lifecycle(app):
        from aiohttp import ClientTimeout
        async with ClientSession(timeout=ClientTimeout(total=30)) as client:
            app[client_key]=client
            yield
    app.cleanup_ctx.append(lifecycle)
    app.router.add_get('/api/audio/capabilities',capabilities)
    app.router.add_get('/api/audio/stream',audio)
    app.router.add_route('*','/{path:.*}',proxy)
    return app


def main():
    from aiohttp import web
    from vosk import Model, SpkModel, KaldiRecognizer
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True);p.add_argument('--speaker-model',required=True)
    p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',default=8000,type=int)
    p.add_argument('--db',default=str(ROOT/'data/surgiguard.sqlite3'))
    args=p.parse_args()
    if args.host not in ('localhost','127.0.0.1','::1') and not os.getenv('SURGIGUARD_ACCESS_KEY'):
        p.error('Set SURGIGUARD_ACCESS_KEY before network binding')
    for path in (args.model,args.speaker_model):
        if not Path(path).is_dir():p.error('Model directory not found: '+path)
    model, speaker=Model(args.model),SpkModel(args.speaker_model)
    def factory():
        rec=KaldiRecognizer(model,16000);rec.SetWords(True);rec.SetSpkModel(speaker)
        return rec
    Path(args.db).parent.mkdir(parents=True,exist_ok=True)
    store=SystemStore(args.db)
    backend=ThreadingHTTPServer(('127.0.0.1',0),SystemHandler);backend.store=store
    threading.Thread(target=backend.serve_forever,daemon=True).start()
    try:
        web.run_app(create_app(store,factory,'http://127.0.0.1:'+str(backend.server_port)),
                    host=args.host,port=args.port,access_log=None)
    finally:
        backend.shutdown();backend.server_close();store.db.close()
if __name__=='__main__':main()
