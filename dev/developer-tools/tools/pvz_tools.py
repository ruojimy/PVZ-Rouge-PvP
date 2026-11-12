"""Portable developer tools. Python 3.10+, standard library only."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import zipfile

BASE = Path(__file__).resolve().parents[1]
VERSION = '1.0.0'

class ToolError(Exception): pass

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def load(path):
    with Path(path).open(encoding='utf-8-sig') as f:
        return json.load(f,parse_constant=lambda v:(_ for _ in ()).throw(ToolError('Non-finite number: '+v)))

def write_new(path, value):
    path=Path(path).resolve()
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    return str(path)

def safe_relative(name):
    p=PurePosixPath(name)
    if not name or '\\' in name or p.is_absolute() or '..' in p.parts or ':' in name:
        raise ToolError('Unsafe manifest/archive path: '+name)
    return p

def audit_folder(target, manifest):
    target=Path(target).resolve();m=load(manifest)
    expected={f['path']:f for f in m['files']}
    if len(expected)!=len(m['files']):raise ToolError('Duplicate manifest paths')
    actual={p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
    # Self-generated manifest/checksums are named explicitly, not a wildcard exclusion.
    exempt=set(m.get('metadata_files',[]))
    for name in exempt:safe_relative(name)
    if actual != set(expected)|exempt:
        raise ToolError('File allowlist mismatch: missing='+repr(sorted(set(expected)-actual))+' extra='+repr(sorted(actual-set(expected)-exempt)))
    for name,f in expected.items():
        safe_relative(name);p=target/name
        if p.is_symlink() or p.resolve().is_relative_to(target) is False:raise ToolError('Escaping path: '+name)
        if p.stat().st_size!=f['bytes'] or digest(p)!=f['sha256']:raise ToolError('Hash mismatch: '+name)
    sums={}
    for line in (target/'SHA256SUMS.txt').read_text('utf8').splitlines():
        sha,name=line.split('  ',1)
        if name in sums:raise ToolError('Duplicate checksum path')
        sums[name]=sha
    if set(sums)!=set(expected)|{'manifest.json'}:raise ToolError('Checksum allowlist mismatch')
    for name,sha in sums.items():
        safe_relative(name)
        if digest(target/name)!=sha:raise ToolError('Checksum mismatch: '+name)
    return {'allowlist_verified':True,'sha256_verified':True,'files':len(expected),'metadata_files':sorted(exempt)}

def axml_identity(data):
    """Read Android binary XML; adapted from the old axml_rename tool's chunk format."""
    def u16(at):return struct.unpack_from('<H',data,at)[0]
    def u32(at):return struct.unpack_from('<I',data,at)[0]
    if len(data)<8 or u16(0)!=3:raise ToolError('Invalid binary AndroidManifest.xml')
    strings=[];identity={};cursor=u16(2)
    while cursor<len(data):
        if cursor+8>len(data):raise ToolError('Truncated AXML chunk')
        kind,header,size=struct.unpack_from('<HHI',data,cursor)
        if size<header or cursor+size>len(data):raise ToolError('Invalid AXML chunk size')
        if kind==1:
            count=u32(cursor+8);flags=u32(cursor+16);start=cursor+u32(cursor+20)
            for n in range(count):
                pos=start+u32(cursor+header+4*n)
                if flags&0x100:
                    def length8(at):
                        x=data[at];return (((x&0x7f)<<8)|data[at+1],at+2) if x&0x80 else (x,at+1)
                    _,pos=length8(pos);length,pos=length8(pos)
                    strings.append(data[pos:pos+length].decode('utf8'))
                else:
                    length=u16(pos);pos+=2
                    if length&0x8000:length=((length&0x7fff)<<16)|u16(pos);pos+=2
                    strings.append(data[pos:pos+2*length].decode('utf-16le'))
        elif kind==0x102:
            name_index=u32(cursor+20)
            if strings[name_index]=='manifest':
                attr_start=u16(cursor+24);attr_size=u16(cursor+26);count=u16(cursor+28)
                for n in range(count):
                    pos=cursor+16+attr_start+n*attr_size
                    key=strings[u32(pos+4)];raw=u32(pos+8);typ=data[pos+15];value=u32(pos+16)
                    if key in ('package','versionName','versionCode'):
                        identity[key]=strings[raw] if raw!=0xffffffff else strings[value] if typ==3 else value
        cursor+=size
    if set(identity)!={'package','versionName','versionCode'}:raise ToolError('Incomplete APK identity')
    return identity

def elf_info(data):
    if data[:4]!=b'\x7fELF' or data[4:6]!=b'\x02\x01':raise ToolError('Expected ELF64 little endian')
    machine=struct.unpack_from('<H',data,18)[0]
    phoff=struct.unpack_from('<Q',data,32)[0];phsize,phnum=struct.unpack_from('<HH',data,54)
    aligns=[]
    for n in range(phnum):
        pos=phoff+n*phsize
        if pos+56>len(data):raise ToolError('Truncated ELF program table')
        if struct.unpack_from('<I',data,pos)[0]==1:aligns.append(struct.unpack_from('<Q',data,pos+48)[0])
    if not aligns:raise ToolError('No ELF LOAD segments')
    return {'machine':machine,'load_alignments':aligns,'all_16k_aligned':all(n>=16384 for n in aligns)}

def apk_inspect(apk):
    apk=Path(apk).resolve()
    with zipfile.ZipFile(apk) as z:
        if z.testzip() is not None:raise ToolError('APK CRC failure')
        names=z.namelist()
        if len(names)!=len(set(names)):raise ToolError('Duplicate APK paths')
        for n in names:safe_relative(n.rstrip('/'))
        ident=axml_identity(z.read('AndroidManifest.xml'))
        build=json.loads(z.read('assets/extract/data/__init__.json'))
        native={n:elf_info(z.read(n)) for n in names if n.startswith('lib/') and n.endswith('.so')}
        if not any(n.endswith('/libmain.so') for n in native):raise ToolError('Missing native libmain.so')
        return {'file':str(apk),'sha256':digest(apk),'zip_crc_verified':True,'identity':ident,'runtime_data':build,
                'native_libraries':native,'all_16k_aligned':all(i['all_16k_aligned'] for i in native.values()),
                'signature_verified':False,'device_tested':False}

class Session:
    def __init__(self,args):
        self.args=args
        self.work=Path(args.work).resolve();self.work.mkdir(parents=True,exist_ok=True)
        self.run=Path(tempfile.mkdtemp(prefix=args.command+'-',dir=self.work))
        self.reads=set();self.processes=[]
        self.trace={'python':sys.executable,'python_version':sys.version.split()[0],'tool_root':str(BASE),
                    'working_directory':str(Path.cwd()),'run_directory':str(self.run),'tool_version':VERSION}
        # Standard Python audit events record actual file opens and child launches.
        def audit(event,values):
            if event=='open' and values and isinstance(values[0],(str,bytes)):
                try:self.reads.add(str(Path(os.fsdecode(values[0])).resolve()))
                except (ValueError,OSError):pass
        sys.addaudithook(audit)

    def game(self,api=False):
        if not self.args.game:raise ToolError('--game must explicitly name the unpacked target game directory')
        folder=Path(self.args.game).resolve()
        exe=folder/'PvZPvPNative.exe'
        if not exe.is_file() or not (folder/'extract/data/__init__.json').is_file():raise ToolError('Not an unpacked native release directory')
        version=load(folder/'extract/data/__init__.json')['BUILD']
        compatible=load(BASE/'compatibility.json')['game_builds']
        if version not in compatible:raise ToolError('UNSUPPORTED_GAME_BUILD: '+str(version))
        if api and b'native-devtools.1' not in exe.read_bytes():
            raise ToolError('MISSING_NATIVE_API: requires the separate native-devtools.1 candidate; stock PvP72 r1 has no developer API')
        self.trace['game_directory']=str(folder);self.trace['game_exe_sha256']=digest(exe)
        self.trace['native_asset_roots']=[str(folder/p) for p in ('extract/data','extract/assets','fonts','extract')]
        return exe

    def process(self,argv,timeout=None,env=None):
        index=len(self.processes);start=time.monotonic()
        environ=os.environ.copy();environ.update({'PVP_USERDATA':str(self.run/'userdata'),'SDL_AUDIODRIVER':'dummy','PYTHONDONTWRITEBYTECODE':'1'})
        if env:environ.update(env)
        try:
            r=subprocess.run([str(a) for a in argv],cwd=self.run,env=environ,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                             timeout=timeout or self.args.timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except subprocess.TimeoutExpired as e:
            (self.run/f'process-{index}.log').write_bytes(e.stdout or b'')
            raise ToolError('Process timed out') from e
        (self.run/f'process-{index}.log').write_bytes(r.stdout)
        self.processes.append({'argv':[str(a) for a in argv],'cwd':str(self.run),'exit_code':r.returncode,
                               'seconds':time.monotonic()-start,'log':str(self.run/f'process-{index}.log')})
        return r

    def native(self,operation,arguments=None,expected=None):
        exe=self.game(api=True)
        directory=Path(tempfile.mkdtemp(prefix=operation+'-',dir=self.run))
        request={'protocol':1,'operation':operation,'arguments':arguments or {}}
        if expected is not None:request['expected']=expected
        req=write_new(directory/'request.json',request);response=directory/'response.json'
        p=self.process([exe,'--developer-tools',req,response])
        if not response.is_file():raise ToolError(f'Native API produced no response (exit {p.returncode})')
        result=load(response)
        if p.returncode or not result.get('ok'):
            raise ToolError(json.dumps(result.get('error',{'exit_code':p.returncode}),ensure_ascii=False))
        if result.get('protocol')!=1:raise ToolError('Response protocol mismatch')
        return result

    def capabilities(self):return self.native('capabilities')

    def finish(self,result,ok=True):
        trace=self.trace|{'actual_python_file_opens':sorted(self.reads),'subprocesses':self.processes}
        write_new(self.run/'paths.json',trace)
        value={'ok':ok,'command':self.args.command,'result':result,'evidence_directory':str(self.run)}
        write_new(self.run/'summary.json',value)
        print(json.dumps(value,ensure_ascii=False,allow_nan=False))
        return 0 if ok else 2

def relay_health(port):
    with socket.create_connection(('127.0.0.1',port),timeout=1) as s:
        data=b'{"relay_protocol":1,"action":"health"}';s.sendall(struct.pack('!I',len(data))+data)
        def read(n):
            result=b''
            while len(result)<n:
                chunk=s.recv(n-len(result))
                if not chunk:raise ToolError('Relay closed unexpectedly')
                result+=chunk
            return result
        size=struct.unpack('!I',read(4))[0]
        if not 0<size<=2048:raise ToolError('Relay health response size invalid')
        return json.loads(read(size))

def relay_test(s):
    identity=s.capabilities()['identity']
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
    config=write_new(s.run/'relay-config.json',{'host':'127.0.0.1','port':port})
    argv=[sys.executable,'-I','-X','utf8',str(BASE/'tools/relay/relay_server.py'),'--config',config]
    with (s.run/'relay.log').open('wb') as log:
        proc=subprocess.Popen(argv,cwd=s.run,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            start=time.monotonic();health=None
            while time.monotonic()-start<10:
                if proc.poll() is not None:raise ToolError('Relay exited before listening')
                try:health=relay_health(port);break
                except (OSError,ToolError):time.sleep(.1)
            if health is None:raise ToolError('Relay failed to start')
            result=s.native('relay-probe',{'port':port},identity)['result']
            with socket.create_connection(('127.0.0.1',port),timeout=2) as conn:
                data=b'{"relay_protocol":999,"action":"health"}';conn.sendall(struct.pack('!I',len(data))+data)
                def read_rejection(n):
                    data=b''
                    while len(data)<n:
                        chunk=conn.recv(n-len(data))
                        if not chunk:raise ToolError('Missing relay rejection response')
                        data+=chunk
                    return data
                size=struct.unpack('!I',read_rejection(4))[0]
                if not 0<size<=2048:raise ToolError('Invalid relay rejection frame')
                rejection=json.loads(read_rejection(size))
                if rejection.get('status')!='error' or rejection.get('code')!='relay_protocol_mismatch':
                    raise ToolError('Invalid relay protocol was not explicitly rejected')
            result.update({'health':health,'invalid_protocol_rejected':True,'service_source_sha256':digest(BASE/'tools/relay/relay_server.py')})
            return result
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
            s.processes.append({'argv':argv,'cwd':str(s.run),'exit_code':proc.returncode,'log':str(s.run/'relay.log'),'stopped':True})

def dispatch(s,a):
    if a.command=='list':
        rows=load(BASE/'migration-matrix.json')
        return {'tool_version':VERSION,'skills':[{'name':r['name'],'status':r['status'],'end_to_end':r['end_to_end']} for r in rows]}
    if a.command=='audit':return audit_folder(a.target,a.manifest)
    if a.command=='apk-inspect':
        result=apk_inspect(a.apk)
        if a.game:
            game=s.game()
            expected=load(game.parent/'extract/data/__init__.json')['BUILD']
            if result['runtime_data']['BUILD']!=expected:raise ToolError('APK_GAME_VERSION_MISMATCH')
            result['pc_build_matches']=True
        return result
    if a.command=='capabilities':return s.capabilities()
    if a.command=='export':
        cap=s.capabilities();data=s.native('export',{'night':a.night,'secrets':a.secret},expected=cap['identity'])
        output=write_new(a.output or s.run/'runtime-export.json',data)
        return {'file':output,'cards':len(data['result']['cards']),'identity':data['identity']}
    if a.command=='map-new':
        cap=s.capabilities();r=s.native('map-new',{'base_map':a.base_map,'name':a.name,'seed':a.seed,'blank':a.blank},cap['identity'])
        return {'file':write_new(a.output,r['result']['document']),'identity':r['identity']}
    if a.command in ('map-check','map-import'):
        cap=s.capabilities();arguments={'file':str(Path(a.file).resolve())}
        if a.command=='map-import':arguments['store']=str(Path(a.store).resolve())
        return s.native(a.command,arguments,cap['identity'])['result']
    if a.command=='replay-demo':
        cap=s.capabilities();output=str(Path(a.output).resolve())
        record=s.native('replay-demo',{'file':output,'ticks':a.ticks},cap['identity'])
        verified=s.native('replay-check',{'file':output},cap['identity'])
        return {'recording':record['result'],'playback':verified['result'],'file':output}
    if a.command=='replay-check':
        cap=s.capabilities();return s.native('replay-check',{'file':str(Path(a.file).resolve())},cap['identity'])['result']
    if a.command=='relay-test':return relay_test(s)
    if a.command=='smoke':
        exe=s.game();report=s.run/'smoke.json';proc=s.process([exe,'--smoke-report',report])
        if proc.returncode or not report.is_file():raise ToolError('Native smoke failed; see process log')
        r=load(report);v=r.get('smoke',{})
        if not(r.get('passed') and v.get('native_checks_passed') and v.get('native_tick')==1250 and v.get('rematched')):
            raise ToolError('Smoke acceptance fields failed')
        return {'report':str(report),'passed':True,'native_tick':v['native_tick'],'rematched':True,'native_checks_passed':True}
    if a.command=='diagnostic':
        if not(1<=a.units<=300 and math.isfinite(a.seconds) and 1<=a.seconds<=600 and math.isfinite(a.warmup) and 0<=a.warmup<=60):
            raise ToolError('DIAGNOSTIC_BOUNDS: units 1..300, seconds 1..600, warmup 0..60; finite numbers required')
        exe=s.game();folder=exe.parent/'reports';before=set(folder.glob('PVP72-*.json'))
        config=write_new(s.run/'diagnostic-config.json',{'scenario':a.scene,'units':a.units,'seconds':a.seconds,'warmup_seconds':a.warmup})
        proc=s.process([exe,'--diagnostic',config],env={'PVZ72_RENDER_STATS':'1'})
        new=set(folder.glob('PVP72-*.json'))-before
        if proc.returncode or len(new)!=1:raise ToolError('Diagnostic failed or ambiguous new reports; see process log')
        report=new.pop();r=load(report)
        if not r.get('completed') or not r.get('native72'):raise ToolError('Incomplete native diagnostic')
        target=s.run/'diagnostic.json';shutil.copy2(report,target)
        return {'report':str(target),'game_report':str(report),'completed':True,'native72':r['native72']}
    raise ToolError('Unknown command')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game',help='Explicit unpacked game directory; no automatic workspace lookup')
    p.add_argument('--work',default=str(Path.cwd()/'developer-tools-output'))
    p.add_argument('--timeout',type=float,default=240)
    sub=p.add_subparsers(dest='command',required=True)
    for name in ['list','capabilities','relay-test','smoke']:sub.add_parser(name)
    q=sub.add_parser('export');q.add_argument('--output');q.add_argument('--night',action='store_true');q.add_argument('--secret',action='append',default=[])
    q=sub.add_parser('map-new');q.add_argument('--output',required=True);q.add_argument('--name',default='开发测试地图');q.add_argument('--base-map',default='家院');q.add_argument('--seed',type=int,default=1);q.add_argument('--blank',action='store_true')
    for name in ['map-check','map-import']:
        q=sub.add_parser(name);q.add_argument('file')
        if name=='map-import':q.add_argument('--store',required=True)
    q=sub.add_parser('replay-demo');q.add_argument('--output',required=True);q.add_argument('--ticks',type=int,default=30)
    q=sub.add_parser('replay-check');q.add_argument('file')
    q=sub.add_parser('diagnostic');q.add_argument('--scene',choices=['ordinary','mixed','barrage'],default='ordinary');q.add_argument('--units',type=int,default=20);q.add_argument('--seconds',type=float,default=5);q.add_argument('--warmup',type=float,default=1)
    q=sub.add_parser('audit');q.add_argument('--target',required=True);q.add_argument('--manifest',required=True)
    q=sub.add_parser('apk-inspect');q.add_argument('apk')
    a=p.parse_args();s=Session(a)
    try:
        if not math.isfinite(a.timeout) or not 0<a.timeout<=600:raise ToolError('Timeout must be finite and within 0..600 seconds')
        return s.finish(dispatch(s,a))
    except (ToolError,OSError,ValueError,KeyError,TypeError,struct.error,zipfile.BadZipFile) as e:
        return s.finish({'error':str(e)},ok=False)

if __name__=='__main__':raise SystemExit(main())
