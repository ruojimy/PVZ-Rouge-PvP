"""chain_members.py: top-level member declarations of every struct in the match chain, base first
(construction order), classified as system (typed type from src/sim/typed) or fixture (J, vectors of
fixture records, counters). Output: chain_members.json + a printed summary."""
import json,re,sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
HERE=Path(__file__).resolve().parent;P=HERE/'probes'
CHAIN=[('hero','Probe'),('targets','TargetProbe'),('plants','PlantProbe'),('doom','DoomProbe'),('chili','ChiliProbe'),('sourced','SourcedProbe'),
       ('death','DeathProbe'),('service','ServiceProbe'),('squash','SquashProbe'),('pea','PeaProbe'),('shooting','ShootingProbe'),
       ('world_rules','WorldRulesProbe'),('resources','ResourcesProbe'),('plant_region','PlantRegionProbe'),('flying_plants','FlyingPlantsProbe'),
       ('grenadiers','GrenadierProbe'),('content_zombies64','ContentZombie64Probe'),('native_tick','NativeTickProbe'),('native_status','NativeStatusProbe'),
       ('content_zombies','ContentZombiesProbe'),('content_controllers','ContentControllersProbe'),('content_phase','ContentPhaseProbe')]
TYPED=set(p.stem for p in (HERE.parents[0]/'typed72-integrated-v19/source/src/sim/typed').glob('*.h'))
def struct_body(text,name):
    m=re.search(r'^struct '+name+r'\b[^{]*\{',text,re.M)
    if not m:return None
    depth=0;start=m.end()-1
    for i in range(start,len(text)):
        if text[i]=='{':depth+=1
        elif text[i]=='}':
            depth-=1
            if depth==0:return text[start+1:i]
def top_level(body):
    out=[];depth=0;cur=''
    for ch in body:
        if ch=='{':
            depth+=1
        if depth==0:cur+=ch
        else:cur+=ch if depth==1 and ch=='{' else ''
        if ch=='}':
            depth-=1
            if depth==0:cur+='}'
        if depth==0 and ch==';':out.append(cur.strip());cur=''
    return out
FIXTURE_TYPES=re.compile(r'^(J|std::vector<J>|std::vector<std::(shared_ptr|optional)|std::vector<std::pair|std::map<|std::unordered_map<|std::set<|uint64_t|int64_t|size_t|bool|double|int|std::string|std::optional<)')
rows=[]
for stem,name in CHAIN:
    text=(P/(stem+'_probe.cpp')).read_text(encoding='utf8',errors='replace')
    body=struct_body(text,name)
    if body is None:rows.append({'layer':stem,'struct':name,'missing':True});continue
    members=[]
    for decl in top_level(body):
        d=' '.join(decl.split())
        if not d or '(' in d.split('{')[0] and '{' not in d.split('(')[0] and not re.match(r'^[\w:<>,\s\*&]+\s+\w+\{',d):continue
        if d.startswith(('using ','struct ','enum ','friend ','public:','private:','explicit ','virtual ','static ','template','//')):continue
        m=re.match(r'^([\w:<>,\s\*&]+?)\s+(\w+)\s*(\{.*\}|=.*)?;?$',d)
        if not m:continue
        typ,var=m.group(1).strip(),m.group(2)
        kind='system' if (typ.split('<')[0].split('::')[-1] and not FIXTURE_TYPES.match(typ)) else 'scalar'
        members.append({'type':typ,'name':var,'kind':kind,'init':(m.group(3) or '')[:160]})
    rows.append({'layer':stem,'struct':name,'members':members})
(HERE/'chain_members.json').write_text(json.dumps(rows,ensure_ascii=False,indent=1),encoding='utf8')
systems=sum(1 for r in rows for m in r.get('members',[]) if m['kind']=='system')
scalars=sum(1 for r in rows for m in r.get('members',[]) if m['kind']=='scalar')
for r in rows:print(r['layer'],'|',' '.join(m['type'].split('<')[0]+':'+m['name'] for m in r.get('members',[]) if m['kind']=='system')[:220])
print('system members',systems,'scalar members',scalars)
