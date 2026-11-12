"""Loopback interoperability against the unchanged Python network transport.

No public endpoint or firewall is touched. Credentials remain in process memory.
"""
import argparse,copy,hashlib,importlib.util,json,os,queue,socket,subprocess,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT.parent/'PVZ-Rouge-v1.4.8/next-pvp71/modkit/pvp/network.py'
IDENTITY={'protocol':1,'build':'typed72-interop','rules_hash':'same','catalog_hash':'same'}
def dumps(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'))
def load_network():
    spec=importlib.util.spec_from_file_location('pvp72_network_reference',str(SOURCE));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class Native:
    def __init__(self,exe,log):
        self.errors=log.open('wb');self.process=subprocess.Popen([str(exe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.errors,encoding='utf8',bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));self.lines=queue.Queue();self.events=[]
        def reader():
            for line in self.process.stdout:self.lines.put(line)
        self.reader=threading.Thread(target=reader,daemon=True);self.reader.start()
    def call(self,op,**kw):
        self.process.stdin.write(dumps(dict(op=op,**kw))+'\n');self.process.stdin.flush();line=self.lines.get(timeout=6);result=json.loads(line)
        if isinstance(result,dict) and 'error' in result:raise AssertionError('native probe rejected operation '+op+': '+result['error'])
        return result
    def poll(self):return self.call('poll')
    def close(self):
        if self.process.poll() is None:
            try:self.call('close');self.process.stdin.close();self.process.wait(timeout=3)
            except Exception:self.process.kill();self.process.wait(timeout=3)
        self.errors.close()

class Events:
    def __init__(self,source):self.source=source;self.buffer=[]
    def wait(self,kind,timeout=4,predicate=lambda e:True):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            self.buffer.extend(self.source.poll())
            for i,e in enumerate(self.buffer):
                if e['type']==kind and predicate(e):return self.buffer.pop(i)
            time.sleep(.015)
        raise AssertionError('event timeout '+kind+'; observed kinds '+str([e['type'] for e in self.buffer]))
    def drain(self):self.buffer.extend(self.source.poll());v=self.buffer;self.buffer=[];return v

RAW_STATE={}
def raw_frame(sock,network,timeout=3):
    sock.settimeout(timeout);decoder,messages=RAW_STATE.setdefault(sock,(network.FrameDecoder(),[]))
    while True:
        while messages:
            message=messages.pop(0)
            if message.get('type')=='ping':sock.sendall(network.encode_frame({'type':'pong'}));continue
            if message.get('type')=='pong':continue
            return message
        raw=sock.recv(65536)
        if not raw:raise AssertionError('socket closed before expected frame')
        messages.extend(decoder.feed(raw))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--exe',required=True,type=Path);parser.add_argument('--out',required=True,type=Path);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    paths=[args.exe.resolve(),Path(__file__).resolve(),SOURCE];paths.extend(p for p in (ROOT/'build/typed72-room-stage/source').rglob('*') if p.is_file());paths.append(ROOT/'build/typed72-room-stage/build-inputs.json');pins={str(p):sha(p) for p in paths};(args.out/'pins.json').write_text(dumps(pins),encoding='utf8')
    network=load_network();results=[]
    def check(label,condition):
        if not condition:raise AssertionError(label)
        results.append(dict(label=label,passed=True))
    native=Native(args.exe.resolve(),args.out/'native.stderr.log');clients=[];raws=[];pyserver=None
    options=dict(identity=IDENTITY,room_code='测试-room',max_peers=8,heartbeat=.2,idle=1.5,handshake=.8,reconnect=3.,connect=1.,retry=.05)
    try:
        # Real old-Python client -> real typed server; altered identity key
        # order is intentionally admitted, matching Python dict equality.
        native.call('init',mode='server',options=options);ne=Events(native);port=ne.wait('listening')['port'];check('native binds loopback ephemeral TCP port',port>0)
        py=network.ClientTransport('127.0.0.1:'+str(port),identity=dict(reversed(list(IDENTITY.items()))),room_code='测试-room',heartbeat_interval=.2,idle_timeout=1.5,reconnect_timeout=3,connect_timeout=1,reconnect_delay=.05);clients.append(py);pe=Events(py)
        pc=pe.wait('connected');nc=ne.wait('connected');peer=nc['peer_id'];check('old Python client and typed server handshake',pc['assigned_peer_id']==peer and nc['require_full_snapshot'])
        message=dict(type='input',seq=41,move=-1,jump=True,text='中文🥔',number=.125)
        check('old client queues gameplay payload',py.send(message));received=ne.wait('message');check('typed server receives exact application payload',received['payload']==message and received['sequence']==1)
        snap=dict(type='room_snapshot',snapshot_stream='first',map_included=True,battle={'tick':4,'x':12.5,'hp':39},map={'tiles':[]})
        check('typed server queues authoritative snapshot',native.call('send',peer=peer,payload=snap));check('old client receives typed snapshot',pe.wait('message')['payload']==snap)
        generation=native.call('generation',peer=peer);check('generation rejects stale enqueue',not native.call('send',peer=peer,payload={'type':'stale'},generation=generation-1))
        # Protocol adversaries use a bounded raw loopback client. Each one
        # receives a real welcome and then exercises native sequence handling.
        def hello(**overrides):
            value=dict(type='hello',protocol=1,identity=IDENTITY,room_code='测试-room',session_id=None,token=None,spectator=False,relay_spectator=False,request_player=False);value.update(overrides);return value
        def raw_client(value):
            s=socket.create_connection(('127.0.0.1',port),timeout=2);raws.append(s);data=network.encode_frame(value)
            for i in range(0,len(data),7):s.sendall(data[i:i+7])
            return s,raw_frame(s,network)
        wrong,reply=raw_client(hello(room_code='wrong'));check('room-code rejection is compatible',reply['type']=='reject' and reply['code']=='room_code_invalid');wrong.close()
        wrong,reply=raw_client(hello(protocol=2));check('protocol rejection is compatible',reply['code']=='protocol_mismatch');wrong.close()
        wrong,reply=raw_client(hello(identity=dict(IDENTITY,build='different')));check('identity mismatch names changed field',reply['code']=='identity_mismatch' and reply['detail']=='incompatible fields: build');wrong.close()
        raw,welcome=raw_client(hello());raw_peer=welcome['peer_id'];ne.wait('connected',predicate=lambda e:e['peer_id']==raw_peer);check('fragmented hello decoded',welcome['receive_sequence']==0)
        frame=network.encode_frame(dict(type='data',seq=1,payload={'type':'once'}));raw.sendall(frame+frame);received=ne.wait('message',predicate=lambda e:e['peer_id']==raw_peer);time.sleep(.05);check('duplicate sequence is discarded',received['payload']=={'type':'once'} and not any(e['type']=='message' and e['peer_id']==raw_peer for e in ne.drain()))
        raw.close();ne.wait('disconnected',predicate=lambda e:e['peer_id']==raw_peer)
        resumed,again=raw_client(hello(session_id=welcome['session_id'],token=welcome['token']));check('session token resumes same seat and sequence',again['peer_id']==raw_peer and again['resumed'] and again['receive_sequence']==1);event=ne.wait('reconnected',predicate=lambda e:e['peer_id']==raw_peer);check('resume requires full authoritative snapshot',event['require_full_snapshot'])
        resumed.sendall(network.encode_frame(dict(type='data',seq=3,payload={'type':'gap'})));event=ne.wait('disconnected',predicate=lambda e:e['peer_id']==raw_peer);check('sequence gap disconnects for resync',event['reason']=='protocol_error' and 'sequence gap' in event['detail']);resumed.close()
        check('old generation cannot write after disconnect',not native.call('send',peer=raw_peer,payload={'type':'stale'},generation=1))
        spectator,sw=raw_client(hello(spectator=True));sp=sw['peer_id'];ne.wait('connected',predicate=lambda e:e['peer_id']==sp);check('spectator admitted separately',sw['spectator'])
        spectator.sendall(network.encode_frame(dict(type='data',seq=1,payload={'type':'input','move':1}))+network.encode_frame(dict(type='data',seq=2,payload={'type':'request_full_snapshot'})))
        event=ne.wait('message',predicate=lambda e:e['peer_id']==sp);check('spectator gameplay is blocked but sequence advances',event['sequence']==2 and event['payload']['type']=='request_full_snapshot')
        check('authorized spectator-to-player role change',native.call('role',peer=sp,spectator=False)=='');reply=raw_frame(spectator,network);check('role change reaches socket',reply['type']=='role_changed' and reply['spectator'] is False)
        spectator.sendall(network.encode_frame(dict(type='data',seq=3,payload={'type':'input','move':-1})));check('promoted spectator can send gameplay',ne.wait('message',predicate=lambda e:e['peer_id']==sp)['sequence']==3)
        check('demotion remains protocol compatible',native.call('role',peer=sp,spectator=True)=='');raw_frame(spectator,network)
        native.call('allow_spectators',value=False);check('disabling spectators disconnects audience',ne.wait('disconnected',predicate=lambda e:e['peer_id']==sp)['reason']=='spectators_disabled');spectator.close()
        check('explicit peer release succeeds',native.call('release',peer=peer));ne.wait('disconnected',predicate=lambda e:e['peer_id']==peer)
        py.close();clients.remove(py)
        metrics=native.call('statistics');check('receive blocks remain bounded',metrics['receive_block_peak']<=65536);check('socket output remains bounded',metrics['socket_output_peak']<=metrics['socket_output_limit_per_connection']);check('command and event byte budgets retained',metrics['command_bytes_peak']<=metrics['command_bytes_limit'] and metrics['event_bytes_peak']<=metrics['event_bytes_limit'])
        native.call('close');ne.wait('closed')
        # Typed client -> unchanged Python server, including real TCP loss
        # followed by the existing session resume handshake.
        pyserver=network.ServerTransport('127.0.0.1',0,identity=IDENTITY,room_code='测试-room',max_peers=4,heartbeat_interval=.2,idle_timeout=1.5,reconnect_timeout=3)
        pse=Events(pyserver);pport=pse.wait('listening')['port'];native.call('init',mode='client',endpoint='127.0.0.1:'+str(pport),options=options);ne=Events(native)
        tc=ne.wait('connected');sc=pse.wait('connected');server_peer=sc['peer_id'];check('typed client and old server handshake',tc['assigned_peer_id']==server_peer)
        check('typed client queues command',native.call('send',payload={'type':'input','seq':9,'move':1}));check('old server receives typed client command',pse.wait('message')['payload']=={'type':'input','seq':9,'move':1})
        check('old server sends snapshot',pyserver.send(server_peer,snap));check('typed client receives old snapshot',ne.wait('message')['payload']==snap)
        oldgen=native.call('generation')
        connection=next(c for c in list(pyserver._connections.values()) if c.peer_id==server_peer);connection.sock.shutdown(socket.SHUT_RDWR)
        ne.wait('disconnected');pse.wait('disconnected');rc=ne.wait('reconnected');rs=pse.wait('reconnected');check('real TCP loss resumes old session',rc['assigned_peer_id']==server_peer and rs['peer_id']==server_peer and rc['require_full_snapshot'])
        check('reconnect changes generation and rejects old queued intent',native.call('generation')>oldgen and not native.call('send',payload={'type':'stale'},generation=oldgen))
        check('resumed client queues current intention',native.call('send',payload={'type':'new_after_resume'}));check('old server receives post-resume sequence',pse.wait('message')['payload']=={'type':'new_after_resume'})
        check('old server can demote typed client',pyserver.set_peer_role(server_peer,True)=='');check('typed client emits role_changed',ne.wait('role_changed')['spectator'] is True)
        native.call('close');ne.wait('closed');pyserver.close();pyserver=None
        # Event-byte overflow is terminal and explicit; no input is silently
        # lost while the transport continues to claim a healthy session.
        small=dict(options,max_frame_bytes=1024);native.call('init',mode='server',options=small);ne=Events(native);port=ne.wait('listening')['port']
        raw,welcome=raw_client(hello());peer=welcome['peer_id'];ne.wait('connected',predicate=lambda e:e['peer_id']==peer)
        payload={'type':'noncoalescable','text':'x'*700};raw.sendall(b''.join(network.encode_frame(dict(type='data',seq=i,payload=payload)) for i in range(1,31)))
        time.sleep(.15);event=ne.wait('error');check('stalled application stops on bounded event overflow',event['code']=='event_queue_full');ne.wait('closed');raw.close()
        metrics=native.call('statistics');check('event overflow retains bounded bytes',metrics['event_bytes_peak']<=metrics['event_bytes_limit'])
        # Endpoint parsing executes in the same compiled native boundary.
        for value,expected in [('127.0.0.1:24561',['127.0.0.1',24561]),('[::1]:24562',['::1',24562]),('::1',['::1',24561]),(' example.test ',['example.test',24561])]:check('endpoint '+value,native.call('endpoint',value=value)==expected)
    except Exception as error:
        results.append(dict(label='unexpected failure',passed=False,error=str(error)))
    finally:
        for client in clients:client.close()
        if pyserver is not None:pyserver.close()
        for raw in raws:
            try:raw.close()
            except OSError:pass
        native.close()
    changed=[str(p) for p in paths if sha(p)!=pins[str(p)]];summary=dict(passed=all(r['passed'] for r in results) and not changed,checks=len(results),results=results,changed_inputs=changed,scope='loopback TCP interoperability only; no public relay, physical device, full multiplayer game or product acceptance')
    (args.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(dumps({k:v for k,v in summary.items() if k!='results'}));return 0 if summary['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
