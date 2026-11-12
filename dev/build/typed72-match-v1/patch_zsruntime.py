"""Bind zombie_secrets.ZombieSecrets runtime hooks (step, armor_break, unit_gone)
to the typed ZombieSecretRuntime. Sources: native_battle.py:1114 (step after
economy), :304 (二手 installs targets.armor_break), :2172 (on_unit_gone after death)."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,a
    t=t.replace(a,b)
if 'ZombieSecretRuntime' in t:raise SystemExit('already patched')
first_include=t.index('#include')
t=t[:first_include]+'#include "sim/typed/zombie_secret_runtime.h"\n'+t[first_include:]
sub('ColdDeploymentServices,NativeCommandServices {','ColdDeploymentServices,NativeCommandServices,ZombieSecretRuntimeServices {')
sub('    NativeRoomCommands native_commands{','''    ZombieSecretRuntime zruntime{battle,zsecrets,hero_flags,death_state,resources,peas,*this};
    // ZombieSecretRuntimeServices: g["伤害僵尸"] is the content-wrapped ordinary hit.
    void damage_zombie(size_t index,double facing,double amount)override{ordinary_damage(index,facing,amount);}
    std::optional<std::string> spawn_zombie(const std::string& card,Point point,double facing,Seat acting)override{
        const auto saved=deployment.acting_seat;deployment.acting_seat=acting;
        struct Restore{std::optional<Seat>& slot;std::optional<Seat> value;~Restore(){slot=value;}} restore{deployment.acting_seat,saved};
        try{return cold_admission.spawn(card,Seat::zombie,point,facing,true);}catch(const std::invalid_argument&){return {};}  // ValueError: banned form
    }
    void secret_event(const ZombieSecretEvent& e)override{
        J row{{"event",e.name}};
        if(e.name=="heal"){row["target"]=seat_name(*e.side);row["amount"]=e.amount;row["kind"]="zsecret_heal";log_event(row);return;}
        if(e.side)row["side"]=seat_name(*e.side);
        if(e.entity)row["entity"]=*e.entity;
        if(e.card)row["card"]=*e.card;
        if(e.item)row["name"]=*e.item;
        if(e.slot)row["slot"]=*e.slot;
        if(e.wearer)row["wearer"]=*e.wearer;
        if(e.name=="zsecret_heal")row["units"]=e.count;
        if(e.name=="zsecret_pole_smash")row["targets"]=e.count;
        log_event(row);
    }
    void armor_broken(const ZombieRef& unit,ArmorSlot slot,const std::string& kind,double maximum)override{
        ContentPhaseProbe::armor_broken(unit,slot,kind,maximum);zruntime.on_armor_break(unit,slot,kind,maximum);
    }
    NativeRoomCommands native_commands{''')
sub('    void unit_gone(const NativeObject&)override{}','    void unit_gone(const NativeObject& object)override{if(zsecrets.enabled())zruntime.on_unit_gone(object);}')
sub('    void zombie_secrets_step(double)override{}','    void zombie_secrets_step(double dt)override{zruntime.step(dt);}')
sub('        economy_state.subsidy=zsecrets.has("补贴");room.zombie_secrets=zsecrets.enabled();\n','''        economy_state.subsidy=zsecrets.has("补贴");room.zombie_secrets=zsecrets.enabled();
        // ZombieSecrets.__init__ (豌豆 head) and native_battle:304 (二手 watches armour breaks).
        zruntime.present=tick_state.present;zruntime.lock();
        if(zsecrets.has("二手")){chain.damage.watch_armor=true;damage.watch_armor=true;}
''')
p.write_text(t,encoding='utf8')
print('ok')
