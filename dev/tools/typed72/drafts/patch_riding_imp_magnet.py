"""Riding-imp magnet path (native_battle._install_imp_armor_hooks, native_battle.py:540-640):
  _riding_imp_candidate: nearest live carrier ('巨人' in its kind) whose riding imp's armour state
      matches, by the patch's own target point and square radius;
  pick_bucket: ordinary heads first; else that carrier if its own head is armed;
  gift_bucket: when the head was already armed the new bucket goes to the imp and the head is kept;
      otherwise a new piece (no black identity, no spent trigger);
  pick_metal / absorb_metal: ordinary pieces first; else the imp's headgear if metal after undoing the
      black art alias (BLACK_ARMOR_LOGIC), stripped whole, attracted under its art name.
Edits the service_plants override in place and records the reason in OVERRIDES.json."""
import json
from pathlib import Path
O=Path(__file__).resolve().parent/'_integration_overrides'
h=O/'service_plants.h';c=O/'service_plants.cpp'
raw_h=h.read_bytes();raw_c=c.read_bytes()
CR=chr(13);LF=chr(10)
HNL=CR+LF if (CR+LF).encode() in raw_h else LF
CNL=CR+LF if (CR+LF).encode() in raw_c else LF
H=raw_h.decode('utf8').replace(CR+LF,LF);C=raw_c.decode('utf8').replace(CR+LF,LF)
if 'riding_imp' in C:raise SystemExit('already patched')
def sub(text,a,b,label):
    assert text.count(a)==1,(label,text.count(a),a[:80])
    return text.replace(a,b)
H=sub(H,'struct MagnetTarget {CombatTarget target;Point point;bool handheld=false;};',
      'struct MagnetTarget {CombatTarget target;Point point;bool handheld=false;bool imp=false;};','mt')
H=sub(H,'    std::optional<MagnetTarget> absorb_target(const ZombieRef&,Point,double tiles);\n',
      '    std::optional<MagnetTarget> absorb_target(const ZombieRef&,Point,double tiles);\n'
      '    // _riding_imp_candidate: the imp on a carrier\'s back as a separate recipient.\n'
      '    std::optional<MagnetTarget> riding_imp(Point center,double tiles,bool armed);\n'
      '    bool absorb_imp(const CombatTarget&,Point target,Point center);\n','decl')
C=sub(C,'bool metal(std::string_view name){',
      '// native_expansion.BLACK_ARMOR_LOGIC / carried_imp_armored.\n'
      'std::string armor_logic(const std::string& a){if(a=="黑路障")return "路障";if(a=="黑铁桶")return "铁桶";return a;}\n'
      'bool carried_imp_armored(const CombatZombie& z){return z.poison.imp_armor.present()&&!z.poison.imp_armor.is_null()&&!z.poison.imp_armor.get().empty()&&z.poison.imp_armor_hp.or_missing(0.)>0.;}\n'
      'bool metal(std::string_view name){','helpers')
tail='    }catch(const std::exception&){}return best;\n}\n'
first=C.index(tail,C.index('std::optional<MagnetTarget> ServicePlants::bucket_target'))
C=(C[:first]+'    }catch(const std::exception&){}\n    if(best)return best;\n'
   '    // pick_bucket fallback: the riding imp, only when the carrier\'s own head is armed.\n'
   '    auto sitting=riding_imp(center,tiles,false);if(!sitting||sitting->target.unit->body.armor.empty())return {};\n'
   '    return sitting;\n}\n'+C[first+len(tail):])
second=C.index(tail,C.index('std::optional<MagnetTarget> ServicePlants::absorb_target'))
C=(C[:second]+'    }catch(const std::exception&){}\n    if(best)return best;\n'
   '    // pick_metal fallback: the riding imp\'s metal headgear.\n'
   '    auto sitting=riding_imp(center,tiles,true);if(!sitting||!metal(armor_logic(sitting->target.unit->poison.imp_armor.get())))return {};\n'
   '    return sitting;\n}\n'+C[second+len(tail):])
C=sub(C,'bool ServicePlants::gift(const CombatTarget& t,Point center) {',
      'std::optional<MagnetTarget> ServicePlants::riding_imp(Point center,double tiles,bool armed){\n'
      '    std::optional<MagnetTarget> best;double distance=0.;const auto targets=*world_.targets;\n'
      '    for(const auto& t:targets)try{\n'
      '        if(t.is_hero()||t.unit->body.kind.find("巨人")==std::string::npos||!live(t)||carried_imp_armored(*t.unit)!=armed)continue;\n'
      '        const auto point=aim_.zombie_point(t);if(!in_range(center,point,tiles))continue;\n'
      '        const double dx=point.x-center.x,dy=point.y-center.y,d=dx*dx+dy*dy;if(!best||d<distance){best=MagnetTarget{t,point,false,true};distance=d;}\n'
      '    }catch(const std::exception&){}\n    return best;\n}\n'
      'bool ServicePlants::absorb_imp(const CombatTarget& t,Point target,Point center){\n'
      '    auto& z=*t.unit;if(!carried_imp_armored(z))return false;const std::string item=z.poison.imp_armor.get();if(!metal(armor_logic(item)))return false;\n'
      '    // strip_carried_imp_armor: nothing broke, so nothing blasts; the carried secondhand mark goes too.\n'
      '    z.poison.imp_armor.set(std::string{});z.poison.imp_armor_hp.set(0.);\n'
      '    if(z.registration.secondhand.present()&&!z.registration.secondhand.is_null())z.registration.secondhand.get().carried_imp.erase();\n'
      '    body(t).hurt=1.;attract(item,target,center);world_.runtime.sound("磁力",{center.x,center.y,0.,0.});return true;\n}\n'
      'bool ServicePlants::gift(const CombatTarget& t,Point center) {','fns')
old=('        // native_battle._install_imp_armor_hooks gift_bucket: a replacement ordinary bucket is a new\n'
     '        // piece, so it carries no black-armour identity and no spent armour trigger.\n'
     '        t.unit->expansion.black_armor.set_null();t.unit->poison.armor_triggered.erase();}')
C=sub(C,old,('        // gift_bucket: an already armed head means this gift was for the riding imp.\n'
             '        if(!before_armor.empty()&&before_hp>0.){t.unit->poison.imp_armor.set(b.armor);t.unit->poison.imp_armor_hp.set(b.armor_hp);b.armor=before_armor;b.armor_hp=before_hp;}\n'
             '        // Otherwise a replacement ordinary bucket is a new piece: no black identity, no spent trigger.\n'
             '        else{t.unit->expansion.black_armor.set_null();t.unit->poison.armor_triggered.erase();}}'),'gift')
C=sub(C,'    auto& b=body(t);if(!t.is_hero()){b.armor="铁桶";',
      '    auto& b=body(t);const std::string before_armor=t.is_hero()?std::string{}:b.armor;const double before_hp=t.is_hero()?0.:b.armor_hp;\n'
      '    if(!t.is_hero()){b.armor="铁桶";','before')
C=sub(C,'        if(auto t=absorb_target(u,center,9.)){fired=absorb(t->target,t->point,center,t->handheld);if(fired)++magnet_absorbs;}',
      '        if(auto t=absorb_target(u,center,9.)){fired=t->imp?absorb_imp(t->target,t->point,center):absorb(t->target,t->point,center,t->handheld);if(fired)++magnet_absorbs;}','dispatch')
h.write_bytes(H.replace(LF,HNL).encode('utf8'));c.write_bytes(C.replace(LF,CNL).encode('utf8'))
m=O/'OVERRIDES.json';rows=json.loads(m.read_text(encoding='utf8'))
for n in ('service_plants.h','service_plants.cpp'):
    rows.setdefault(n,{});rows[n]['reason']=rows[n].get('reason','')+'; riding-imp magnet recipient (_riding_imp_candidate, pick_bucket/gift_bucket, pick_metal/absorb_metal; native_battle.py:540-640)'
m.write_text(json.dumps(rows,ensure_ascii=False,indent=1),encoding='utf8');print('ok')
