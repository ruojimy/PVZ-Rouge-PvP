"""Compact paired evaluation and common-window activity screens."""
import bisect,gzip,sys
from overnight_common import *
from tempo_gate import assess
def evaluate(name,ids,model=None,seat=None,corpus=None,full=False,zombie_model=None,stop=DEADLINE):
    corpus=corpus or B/'corpus-plain';out=B/('tmp' if full else 'eval')/name
    assert not out.exists();out.mkdir(parents=True)
    args=[sys.executable,'-X','utf8',H/'eval.py','--bin',BIN/'headless_match.exe','--corpus',corpus,'--out-dir',out,
          '--ids',','.join(ids),'--jobs','4','--limit-seconds','600']
    if model:args+=['--planner','nn']
    args+=['--','--telemetry']
    if not full:args+=['--no-records']
    if model:args+=['--model',model,'--nn-seat',seat]
    if zombie_model:args+=['--zombie-model',zombie_model]
    command('eval-'+name,args,stop=stop)
    s=read(out/'summary.json');assert not s['crashed'] and len(s['matches'])==len(ids)
    assert all(not v['ai_error'] for v in s['matches'].values())
    return out,s
def footer(path):
    # Compact evaluation files contain only a header and a result.
    with path.open('rb') as f:return json.loads(f.read().rstrip(b'\n').rsplit(b'\n',1)[-1])
def measure(events,seat,until):
    plans=[r for r in events if r['kind']=='plan' and r['side']==seat and r['time']<until]
    deploy=[r for r in events if r['kind']=='deploy' and r['side']==seat and r['time']<=until]
    times=sorted(r['time'] for r in deploy);resource=rich=siege=0.
    for i,row in enumerate(plans):
        now=row['time'];end=min(until,plans[i+1]['time'] if i+1<len(plans) else until);dt=end-now
        resource+=row['resource']*dt;siege+=(row['mode']=='siege')*dt
        last=bisect.bisect_right(times,now)-1
        if now-(times[last] if last>=0 else 0)>=30 and row['resource']>=700 and row['hp']>0 and not row['recovering']:rich+=dt
    return dict(deploys=len(deploy),mean_resource=resource/until,rich_idle=rich,siege_fraction=siege/until,
                longest_idle=max(b-a for a,b in zip([0.,*times],[*times,until])))
def subset(s,ids):return dict(s,ids=ids,matches={i:s['matches'][i] for i in ids},crashed=[i for i in s['crashed'] if i in ids])
def screen(reference_path,candidate_path,seat):
    a=read(reference_path/'summary.json');b=read(candidate_path/'summary.json');a=subset(a,b['ids'])
    gate=assess(a,b,seat);activity={};flagged={}
    for uid in b['ids']:
        until=min(a['matches'][uid]['time'],b['matches'][uid]['time'])
        x=measure(footer(reference_path/'matches'/f'{uid}.jsonl')['activity'],seat,until)
        y=measure(footer(candidate_path/'matches'/f'{uid}.jsonl')['activity'],seat,until);flags=[]
        if y['rich_idle']>x['rich_idle']+30:flags.append('added_rich_idle')
        if x['deploys']>=10 and y['deploys']<.75*x['deploys'] and y['mean_resource']>1.5*x['mean_resource']:flags.append('less_deployment_more_resources')
        activity[uid]=dict(reference=x,candidate=y,flags=flags)
        if flags:flagged[uid]=flags
    return dict(outcome=gate,activity=activity,activity_flags=flagged,passed=gate['passed'] and not flagged)
def archive_full(folder,name):
    target=B/'eval'/name;assert not target.exists();(target/'matches').mkdir(parents=True)
    manifest={};summary=read(folder/'summary.json')
    for path in sorted((folder/'matches').glob('*.jsonl')):
        guard();raw_hash=sha(path);archive=B/'archives'/name/(path.name+'.gz');archive.parent.mkdir(parents=True,exist_ok=True)
        with path.open('rb') as source,archive.open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=6,mtime=0) as out:
            shutil.copyfileobj(source,out)
        with gzip.open(archive,'rb') as check:assert hashlib.file_digest(check,'sha256').hexdigest()==raw_hash
        with path.open('rb') as source:head=json.loads(source.readline())
        tail=footer(path);head['records']=False;head['archived_records']=str(archive)
        compact=target/'matches'/path.name
        compact.write_text(json.dumps(head,ensure_ascii=False)+'\n'+json.dumps(tail,ensure_ascii=False)+'\n','utf-8')
        summary['matches'][path.stem]['raw_match_sha256']=raw_hash;summary['matches'][path.stem]['file_sha256']=sha(compact)
        manifest[str(path)]=dict(raw_sha256=raw_hash,archive=str(archive),archive_sha256=sha(archive),bytes=archive.stat().st_size)
        # Persist proof before releasing this run's temporary original.
        write(target/'archives.json',manifest);delete_temporary_file(path)
    write(target/'summary.json',summary);shutil.copy2(folder/'timing.json',target/'timing.json')
    return target
