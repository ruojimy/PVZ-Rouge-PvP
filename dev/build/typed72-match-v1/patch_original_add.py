"""These six patch spawners call __pvz_sb_add_entity_original in the source, bypassing
the content/patch add_entity wrappers. A defaulted add_original_entity keeps every
component probe unchanged while the whole-match composition can bind the raw entry."""
import hashlib,json
from pathlib import Path
root=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
ov=root/'tools/typed72/drafts/_integration_overrides'
src=root/'build/typed72-integrated-v8/source/src/sim/typed'
meta=ov/'OVERRIDES.json';rows=json.loads(meta.read_text(encoding='utf8'))
def base_text(name):
    p=ov/name if (ov/name).exists() else src/name
    return p.read_bytes().decode('utf8'),p
pairs={'zombie_pea':('callbacks_.add_entity(','spawn_zombie_pea'),'squash_effects':('callbacks_.add_entity(','spawn_squash_zombie_entity'),
       'service_plants':('callbacks_.add_entity(','spawn_effect_entity (magnet attract)'),'chili_effects':('services_.add_entity(','spawn_chili_zombie_fire_row'),
       'doom_effects':('services_.add_entity(','spawn_effect_entity (doom)'),'lantern_effects':('services_.add_entity(','spawn_effect_entity (光疗)')}
for stem,(call,where) in pairs.items():
    h,hp=base_text(stem+'.h');nl='\r\n' if '\r\n' in h else '\n'
    import re
    m=re.search(r'virtual void add_entity\(std::string,double(?: facing)?,Motion\)=0;',h);assert m,stem
    h=h[:m.end()]+nl+'    // Source uses __pvz_sb_add_entity_original here; components keep the forwarded default.'+nl+'    virtual void add_original_entity(std::string n,double f,Motion m){add_entity(std::move(n),f,m);}'+h[m.end():]
    c,cp=base_text(stem+'.cpp');assert c.count(call)==1,(stem,c.count(call))
    c=c.replace(call,call.replace('add_entity(','add_original_entity('))
    for name,text,base in ((stem+'.h',h,hp),(stem+'.cpp',c,cp)):
        before=hashlib.sha256(base.read_bytes()).hexdigest()
        (ov/name).write_bytes(text.encode('utf8'))
        rows.setdefault(name,{})
        rows[name].update(base_sha256=rows[name].get('base_sha256',before),base=rows[name].get('base','typed72-content-controller-v8 (via integrated-v8)'))
        rows[name]['reason']=(rows[name].get('reason','')+'; ' if rows[name].get('reason') and 'add_original_entity' not in rows[name].get('reason','') else '')+'add_original_entity: source '+where+' uses __pvz_sb_add_entity_original'
meta.write_text(json.dumps(rows,ensure_ascii=False,indent=1),encoding='utf8')
p=root/'build/typed72-match-v1/match_probe.cpp';t=p.read_text(encoding='utf8')
a='    // Source __pvz_sb_add_entity_wrapper: every native entity birth passes through this.\n'
if 'add_original_entity' not in t:
    assert t.count(a)==1
    t=t.replace(a,'    // __pvz_sb_add_entity_original: the raw native constructor, no content/patch wrappers.\n    void add_original_entity(std::string kind,double f,Motion position)override{ContentPhaseProbe::patched_add_entity(std::move(kind),f,position);}\n    // PvP 哪个植物 replaces the original lookup (native_placement), so clears use the PvP form.\n    void clear_plant(Cell c)override{clear_pvp_plant(battle,c);}\n'+a)
    p.write_text(t,encoding='utf8')
print('ok')
