"""Exports for the remaining field gaps (batch r20), in the V record format:
  zombie _pvp_zs_timer      zombie_secrets._fast_shots setdefault({}) + SHOT_TIMERS seen values
  zombie _pvp_zs_first_used ColdZombieSecrets first-soldier mark (registration.first_soldier_used)
  zombie _pvp_poison        {level,until,next,owner,layers:{str(level):{until,next,owner}}}
  entity 植物僵尸头命中表   identity list (V stores id(zombie)); compared by length
  entity 扁                 flattened sprite object, recorded by V as '<instance>'
  plant  _pvp_pea_angle     PeaHybrid head angle"""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,(t.count(a),a)
    t=t.replace(a,b)
if '"_pvp_zs_timer"' in t:raise SystemExit('already patched')
sub('write(j,"_pvp_coop_dormant",r.coop_dormant);','''write(j,"_pvp_coop_dormant",r.coop_dormant);write(j,"_pvp_zs_first_used",r.first_soldier_used);
        if(u.secret.timer_tracked.present()&&!u.secret.timer_tracked.is_null()&&u.secret.timer_tracked.get()){J seen=J::object();
            if(u.secret.timer_shot.present())seen["植物僵尸射cd"]=u.secret.timer_shot.get();if(u.secret.timer_basket.present())seen["篮球cd"]=u.secret.timer_basket.get();j["_pvp_zs_timer"]=seen;}
        if(u.poison.poison.present())j["_pvp_poison"]=poison_v(u.poison.poison);''')
sub('        write(j,"_pvp_coop_coffee",p.pve.coop_coffee);\n','        write(j,"_pvp_coop_coffee",p.pve.coop_coffee);write(j,"_pvp_pea_angle",p.pea_angle);\n')
sub('        write(j,"牛顿",e.gravity);','''        if(e.bonus.head_hits.present())j["植物僵尸头命中表"]=e.bonus.head_hits.is_null()?J(nullptr):J(J::array());
        if(e.bonus.head_hits.present()&&!e.bonus.head_hits.is_null())for(const auto& hit:e.bonus.head_hits.get())j["植物僵尸头命中表"].push_back(hit.value);
        if(e.flat_sprite.present())j["扁"]="<instance>";
        write(j,"牛顿",e.gravity);''')
sub('    static void plant_extra(J& j,const CombatPlant& p){','''    // V records a poison slot as its dict, layers keyed by str(level).
    static J poison_v(const PoisonSlot& slot){
        if(slot.is_null())return nullptr;const auto& s=*slot.get();J out=J::object();
        write(out,"level",s.level);write(out,"until",s.until);write(out,"next",s.next);
        if(s.owner.present())out["owner"]=seat_name(s.owner.get());
        if(s.layers.present()){
            if(s.layers.is_null())out["layers"]=nullptr;
            else{J layers=J::object();for(const auto& [level,layer]:*s.layers.get())layers[std::to_string(int64_t(level))]={{"until",layer->until},{"next",layer->next},{"owner",seat_name(layer->owner)}};out["layers"]=layers;}
        }
        return out;
    }
    static void plant_extra(J& j,const CombatPlant& p){''')
p.write_text(t,encoding='utf8');print('ok')
