"""Source correspondence for the installed zombie-pea and PvP launch chains."""
import argparse
import ast
import hashlib
import json
import marshal
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_peas as reference
from verify_stages import sha
ROOT=reference.ROOT

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('verification','negative','out'):ap.add_argument('--'+key,required=True)
    a=ap.parse_args();folder=Path(a.verification).resolve();entries=[];evidence={}
    for name,path in (('regression',folder/'summary.json'),('negative',Path(a.negative).resolve()/'summary.json')):
        report=json.loads(path.read_text(encoding='utf8'));assert report['passed'],name;evidence[name]=dict(path=str(path),sha256=sha(path))
    for path,digest in json.loads((folder/'pinned.json').read_text(encoding='utf8')).items():assert sha(Path(path))==digest,path
    def add(path,names,target,owner=None,method=False):
        tree=ast.parse(path.read_text(encoding='utf8'),str(path));nodes=tree.body
        if owner:
            roots=[n for n in ast.walk(tree) if isinstance(n,ast.ClassDef if method else ast.FunctionDef) and n.name==owner];assert len(roots)==1;nodes=roots[0].body
        for name in names:
            matches=[n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name];assert len(matches)==1,(path,name)
            n=matches[0];entries.append(dict(source=str(path),source_sha256=sha(path),symbol=name,owner=owner,lines=[n.lineno,n.end_lineno],ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest(),typed_target=target))
    names=('spawn_zombie_pea','damage_player_from_zombie_pea','play_zombie_pea_splat','is_zombie_pea','zombie_pea_xy','segment_hits_ellipse','damage_charmed_zombie_from_zombie_pea','zombie_pea_hit_charmed_zombie','zombie_pea_hit','zombie_pea_pvp_active','zombie_pea_fire_mult','zombie_pea_torch_check','zombie_pea_fire_splash','update_one_zombie_pea','update_zombie_peas')
    add(reference.patch.PATCH,[reference.P+n for n in names],'ZombiePeas / typed segment_hits_ellipse')
    add(reference.doom.NATIVE_PATCH,('bind',),'ZombiePeas sourced spawn/hit/update / SourcedContext',owner='bind_targets')
    add(reference.doom.LEGACY,('_target_wrapper','_damage_wrapper'),'ZombiePeas retained I-Zombie views and player guards')
    add(reference.plants.protection.PROTECTION,('_patch_damage_code',),'ZombiePeas::plant_damage / UnitProtection')
    add(reference.hero.ZSECRETS,('_hero_pea','install_late','shotgun_volley','has','_own'),'ZombiePeas hero_pea / spawn / shotgun_volley',owner='ZombieSecrets',method=True)
    add(reference.projectiles.SIMULATION,('wrap_delta',),'typed wrap_delta')
    raw=marshal.loads(reference.hero.RAW.read_bytes());code=next(c for c in raw.co_consts if isinstance(c,types.CodeType) and c.co_name=='表面伤害僵尸')
    entries.append(dict(source=str(reference.hero.RAW),source_sha256=sha(reference.hero.RAW),symbol=code.co_name,first_line=code.co_firstlineno,bytecode_sha256=hashlib.sha256(marshal.dumps(code)).hexdigest(),typed_target='DamagePatch::surface_from / NestedOrdinary installed entry'))
    assert len(entries)==26
    report=dict(schema=1,entries=entries,evidence=evidence,implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},
        semantics=['Segment collision preserves target order, spike consumption and torch pass-through.',
            'Direct and splash damage use current protection and exact inclusive-x/strict-y bounds.',
            'Absent surface callback differs from a throwing callback; the installed nested ordinary entry keeps the protection packet and native numeric index.',
            'Source identity, tracking-key presence, legacy player guards and captured roster views survive callback mutation.',
            'Spawn retains its original birth list; the native and legacy update lists preserve different replacement rules.',
            'Native movement is not applied twice, and native-managed shots bypass the legacy age/bounds expiration.',
            'Latest six-shot fan and 200-tick suppression are outside the sourced spawn wrapper.',
            'Hero targeting uses ring distance and stable ties, current team targets, cached proxies, source/seat tagging and ordered shared events.'],
        full_branch_coverage=False,whole_battle_supported=False,production_entry_switched=False,full_product_acceptance=False,
        pending=['Asset callback is executed with no atlas in these fixtures; cold atlas loading still needs its production implementation and validation.',
            'PvP58 dense-planting shell-first outer hit/plant-point hook and NativeContent damage adapters still require integration.',
            'Plant-zombie shooting and complete bonus scheduling','Authoritative plant/unit/entity/hero loops and complete PvP custom content',
            'AI/network/spectators/replay','Old full suite, whole-battle comparisons, current Android, formal performance and game products'])
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))
if __name__=='__main__':main()
