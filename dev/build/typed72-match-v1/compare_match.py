"""Record reference + typed for one scenario and report the first tick difference.

Records compared per native tick: g/avatars/inp/battle/rng. Nothing is exempted
silently: fields the typed exporter does not emit yet show up as `only_in_reference`
and are counted, so a missing field can never read as equality.

    python compare_match.py <scenario-name> <out-dir>
"""
import hashlib,itertools,json,math,os,re,subprocess,sys
from pathlib import Path
ROOT=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
STAGE=Path(__file__).resolve().parent
EXPORT=STAGE/'build/Release/cold72_export.exe';MATCH=STAGE/'build/Release/match72.exe'
RECORD=ROOT/'build/typed72-ref-recorder-v2/build/Release/ref72_record.exe'
PLAYER_FIELDS=('x','y','vx','vy','h','hp','max_hp','resource','cooldowns','cooldown_spans','seq','last_input_tick','marked_until','immune_until','facing','frozen','slowed','buttered','jumps','jump_cap','grounded','poison_level','jump_held','stats')
TOL=1e-9
IGNORE={'三向目标','智能星命中','target_id','__pvz_sb_source_zombie_id'}  # PvP73: V stores id(zombie) there (a memory address)
# Lists of V object identities (id(zombie), patch 植物僵尸头命中表): only the count is portable.
IDENTITY_LISTS={'植物僵尸头命中表'}
def walk(a,b,path,out):
    if isinstance(a,str) and a.startswith('<') and a.endswith('>'):return
    if isinstance(a,bool) or isinstance(b,bool):
        if bool(a)!=bool(b) or not(isinstance(a,(bool,int,float)) and isinstance(b,(bool,int,float))):out.append(('diff',path,a,b))
        return
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        if a==b or (isinstance(a,float) and isinstance(b,float) and math.isnan(a) and math.isnan(b)):return
        if abs(a-b)<=TOL*max(1.,abs(a),abs(b)):return
        out.append(('diff',path,a,b));return
    if isinstance(a,dict) and isinstance(b,dict):
        for k in a:
            if k in IGNORE:continue
            if k not in b:out.append(('only_in_reference',path+'.'+k,a[k],None))
            elif k in IDENTITY_LISTS and isinstance(a[k],list) and isinstance(b[k],list):
                if len(a[k])!=len(b[k]):out.append(('length',path+'.'+k,len(a[k]),len(b[k])))
            else:walk(a[k],b[k],path+'.'+k,out)
        for k in b:
            if k not in a and k not in IGNORE:out.append(('only_in_typed',path+'.'+k,None,b[k]))
        return
    if isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):out.append(('length',path,len(a),len(b)))
        for i,(x,y) in enumerate(zip(a,b)):walk(x,y,path+'/%d'%i,out)
        return
    if a!=b:out.append(('diff',path,a,b))
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()
def main():
    name=sys.argv[1];out=(ROOT/sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tools/scenarios'/('_expanded_'+name+'.json')
    if not source.exists():source=ROOT/'tools/scenarios'/(name+'.json')
    if (STAGE/'scenarios'/(name+'.json')).exists():source=STAGE/'scenarios'/(name+'.json')
    env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PVP_USERDATA=str(out/'userdata'))
    cold=out/'cold.json';ref=out/'reference.jsonl';typed=out/'typed.jsonl';report=out/'typed-report.json'
    atlas=out/'atlas.bin'
    for cmd in ([EXPORT,source,cold,atlas],[RECORD,source,ref]):
        r=subprocess.run([str(c) for c in cmd],cwd=str(ROOT),env=env,capture_output=True)
        if r.returncode:raise SystemExit('%s failed %d %s'%(cmd[0].name,r.returncode,r.stderr[-400:]))
    typed_final=out/'typed.final.json'
    run=subprocess.run([str(MATCH),str(cold),str(atlas),str(source),str(typed),str(report),str(typed_final)],cwd=str(ROOT),capture_output=True,timeout=1800)
    summary=dict(scenario=name,typed_rc=run.returncode,typed_stderr=run.stderr.decode('utf8','replace')[-2500:])
    if report.exists():summary['typed_report']=json.loads(report.read_text(encoding='utf8'))
    # Streamed: a full match trace is around a gigabyte. Missing keys are tracked across
    # the run; real value differences stop at the first tick.
    missing={};first=None;compared=0;ref_lines=typed_lines=0;last={};rng_changes=0;previous_rng=None;events=[]
    with ref.open(encoding='utf8') as left,(typed.open(encoding='utf8') if typed.exists() else open(os.devnull)) as right:
        for i,(lx,ly) in enumerate(itertools.zip_longest(left,right)):
            if lx is not None:ref_lines+=1
            if ly is not None:typed_lines+=1
            if lx is None or ly is None or first is not None:continue
            x=json.loads(lx);y=json.loads(ly);found=[];keys=('t','g','avatars','inp','battle','rng')
            walk({k:x.get(k) for k in keys},{k:y.get(k) for k in keys},'',found)
            walk({s:{f:v.get(f) for f in PLAYER_FIELDS} for s,v in (x.get('players') or {}).items()},y.get('players') or {},'.players',found)
            real=[f for f in found if f[0] in('diff','length')]
            for kind,path,_,_ in found:
                if kind.startswith('only_in'):missing.setdefault(kind+':'+re.sub(r'/[0-9]+','/*',path),i)
            if real:first=dict(line=i,t=x.get('t'),rt=x.get('rt'),differences=[[f[0],f[1],f[2],f[3]] for f in real[:25]],count=len(real),rng_reference=x.get('rng'),rng_typed=y.get('rng'))
            else:compared=i+1
            if x.get('rng')!=previous_rng:rng_changes+=1;previous_rng=x.get('rng')
            last=dict(t=x['t'],rt=x['rt'],plants=len(x['g']['植物']),zombies=len(x['g']['僵尸']),entities=len(x['g']['实体']),hp={k:v.get('玩家血量') for k,v in x['avatars'].items()},result=x['battle'].get('result'))
    summary.update(reference_lines=ref_lines,typed_lines=typed_lines,compared_until_first_difference=compared,first_difference=first,field_gaps=dict(sorted(missing.items())),last_compared_state=last,reference_rng_changes=rng_changes,
        identical=first is None and not missing and ref_lines==typed_lines and run.returncode==0,
        traces=dict(reference_sha256=sha(ref),typed_sha256=sha(typed) if typed.exists() else None))
    # Settlement and the complete ordered event log.
    final={}
    try:
        rf=json.loads((out/'reference.jsonl.final.json').read_text(encoding='utf8'));tf=json.loads(typed_final.read_text(encoding='utf8'))
        final['result_equal']=rf.get('result')==tf.get('result');final['result']=[rf.get('result'),tf.get('result')];final['tick_equal']=rf.get('tick')==tf.get('tick')
        la,lb=rf.get('log') or [],tf.get('log') or [];found=[];walk(la,lb,'.log',found);final['log_lengths']=[len(la),len(lb)];final['log_differences']=[[f[0],f[1],f[2],f[3]] for f in found[:12]];final['log_difference_count']=len(found)
        import collections
        final['event_counts']=[dict(collections.Counter(e['event'] for e in la)),dict(collections.Counter(e['event'] for e in lb))]
        final['log_equal']=not found
    except Exception as error:final['error']=repr(error)
    summary['final']=final;summary['identical']=summary['identical'] and final.get('log_equal') is True and final.get('result_equal') is True
    if summary['identical'] and '--keep' not in sys.argv:ref.unlink();typed.unlink();(out/'atlas.bin').unlink();summary['traces']['discarded_after_identical']=True
    (out/'comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=1),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k!='field_gaps'},ensure_ascii=False)[:3500])
    print('field gaps',len(missing));print('\n'.join(list(missing)[:70]))
if __name__=='__main__':main()
