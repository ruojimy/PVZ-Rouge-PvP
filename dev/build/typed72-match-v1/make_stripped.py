"""make_stripped.py <out stage>: copy the match driver and its probe chain into a new stage with every
fixture-recording statement removed from the service paths (record/before/after and push_back onto
recorder logs), fixture containers released every native tick, and the backend reported as
typed72-stripped-composition-e2. The JSON component entry points stay compiled but are not reachable
from match72. Writes strip-manifest.json with per-file removed statements for review."""
import hashlib,json,re,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
OUT=(HERE.parent/sys.argv[1]).resolve()
if OUT.exists():raise SystemExit('stage exists, use a new directory: '+str(OUT))
RECORD_CALLS=('record','before','after')
LOGS=('calls','render_log','dispatch_calls','phase_draws','phase_events','raw_calls','armor_events','flying_draws','flying_events',
      'cart_events','summon_events','wind_callbacks','expansion_events','spawn_events','tick_events','states','held_hits',
      'aliases64','draws64','events64','spawns64','cost_calls','grenade_events','poison_events')
def balanced_end(text,i):
    """index just past the ')' matching the '(' at text[i]."""
    depth=0;quote=None;k=i
    while k<len(text):
        ch=text[k]
        if quote:
            if ch=='\\':k+=2;continue
            if ch==quote:quote=None
        elif ch in '"\'':quote=ch
        elif ch=='(':depth+=1
        elif ch==')':
            depth-=1
            if depth==0:return k+1
        k+=1
    raise ValueError('unbalanced call')
PATTERN=re.compile(r'(?<![\w.:>])(?:(?:'+'|'.join(RECORD_CALLS)+r')|(?:'+'|'.join(LOGS)+r')\.(?:push_back|emplace_back))\s*\(')
def strip(text):
    out=[];removed=[];pos=0
    for m in PATTERN.finditer(text):
        if m.start()<pos:continue
        # Only whole statements: preceded by ';', '{', '}' or a line start, followed by ';'.
        before=text[:m.start()].rstrip(' \t')
        if before and before[-1] not in ';{}\n':continue
        end=balanced_end(text,m.end()-1)
        rest=text[end:].lstrip(' \t')
        if not rest.startswith(';'):continue
        stop=end+(len(text[end:])-len(rest))+1
        out.append(text[pos:m.start()]);removed.append(' '.join(text[m.start():stop].split())[:160]);pos=stop
    out.append(text[pos:]);return ''.join(out),removed
OUT.mkdir(parents=True);(OUT/'probes').mkdir()
manifest={'source_stage':'build/typed72-match-v1','files':{}}
for src in sorted((HERE/'probes').iterdir()):
    if not src.is_file():continue
    text=src.read_text(encoding='utf8');new,removed=strip(text) if src.suffix in ('.cpp','.inc') else (text,[])
    (OUT/'probes'/src.name).write_text(new,encoding='utf8')
    manifest['files']['probes/'+src.name]={'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'removed':removed}
driver=(HERE/'match_probe.cpp').read_text(encoding='utf8')
new,removed=strip(driver)
for a,b in (('const bool release_fixtures=std::getenv("MATCH_RELEASE_FIXTURES")!=nullptr;','const bool release_fixtures=true;  // stripped composition: no fixture retention'),
            ('"typed72-probe-composition-e1"','"typed72-stripped-composition-e2"')):
    assert new.count(a)>=1,a;new=new.replace(a,b)
(OUT/'match_probe.cpp').write_text(new,encoding='utf8')
manifest['files']['match_probe.cpp']={'source_sha256':hashlib.sha256((HERE/'match_probe.cpp').read_bytes()).hexdigest(),'removed':removed}
for name in ('cold72_export.cpp','CMakeLists.txt','build_match.ps1','errs2.py'):shutil.copyfile(HERE/name,OUT/name)
(OUT/'strip-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=1),encoding='utf8')
print('removed',sum(len(v['removed']) for v in manifest['files'].values()),'statements into',OUT)
