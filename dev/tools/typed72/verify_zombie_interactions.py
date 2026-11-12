"""Bite-context reentrancy and the gravebuster's half-health boundary."""
import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_zombie_motion as motion
shooting=motion.shooting
hero=motion.hero
shared=motion.shared
reference=motion.build_ref
InteractionExtension=motion.MotionExtension

def cases():
    out=[]
    for label,source in motion.cases():
        if label.startswith('hero-and-reciprocal-'):
            c=copy.deepcopy(source)
            # A synchronous installed damage callback reads the same source
            # selection as real explosions and retaliation. Attribute a small
            # hero hit before the ordinary body hit completes.
            c['operations'].insert(-1,dict(op='lifecycle_hook',name='pea_damage',
                body=[dict(op='damage',target='plant',amount=.125)],fail_before=False,fail_after=False))
            out.append(('reciprocal-source-callback-'+label.rsplit('-',1)[-1],c))
        elif label.startswith('plant-bite-'):
            c=copy.deepcopy(source);i=int(label.rsplit('-',1)[-1])
            c['operations'][2]['values'].update(血量=(149.,150.,151.)[i%3],_pvp_max_hp=300.)
            out.append(('half-health-bite-'+str(i),c))
            c=copy.deepcopy(c)
            maximum=(160.,200.,600.)[i%3]
            c['operations'][2]['values'].update(血量=maximum*.5+(-.01,0.,.01)[i//3%3],_pvp_max_hp=maximum,
                                               __pvz_sb_zombie_observed_max_hp=(120.,1000.)[i%2])
            out.append(('independent-public-and-observed-max-hp-'+str(i),c))
    return out

if __name__=='__main__':
    paths=[Path(__file__).resolve(),Path(motion.__file__),Path(motion.phase.__file__),Path(shared.__file__),
           shared.ROOT/'tools/typed72/world_rules_probe.cpp',shared.ROOT/'tools/typed72/zombie_motion_fixture.inc',
           motion.RAW,motion.BITES,motion.BLACK,motion.CACTUS,shared.BATTLE,motion.CONTENT,shared.SEPTEMBER,shared.PLANT_ZOMBIES,
           motion.phase.PERIODIC,motion.phase.EXPANSION]
    sys.exit(shooting.main(paths,reference,cases,InteractionExtension,'typed72-bite-callback-boundaries'))
