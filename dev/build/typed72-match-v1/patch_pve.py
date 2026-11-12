"""Bind pve.WaveDirector / coop_cycle.CoopCycle (typed PveDirector) into the match.
Sources: native_battle.py:2229-2233 (_team_init binds the director), :1074-1075 (cycle.step
before the native ticks), :2532-2541 (director.step then cleared() result), :2404-2410
(_ladder_support_request), :372 (spawn_remnant), :2497 (drop_coin), :1881 (_ban_free_spawn)."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,(t.count(a),a)
    t=t.replace(a,b)
if 'PveDirector' in t:raise SystemExit('already patched')
i=t.index('#include');t=t[:i]+'#include "sim/typed/pve_director.h"\n'+t[i:]
sub('NativeCommandServices,ZombieSecretRuntimeServices {','NativeCommandServices,ZombieSecretRuntimeServices,PveDirectorServices {')
sub('    NativeRoomCommands native_commands{','''    PveDirector director{battle,catalog,budget,navigation,published.terrain,*this};
    // PveDirectorServices
    std::optional<std::string> spawn_wave_zombie(const std::string& key,Point point,double facing,int64_t wave)override{
        const auto saved=deployment.scripted_wave;deployment.scripted_wave=wave;++battle.spawn_ban_exempt;
        struct Restore{MatchProbe& m;std::optional<int64_t> wave;~Restore(){m.deployment.scripted_wave=wave;--m.battle.spawn_ban_exempt;}} restore{*this,saved};
        return cold_admission.spawn(key,Seat::zombie,point,facing,false);
    }
    ZombieRef native_zombie(const std::string& id)override{const auto o=battle.native_objects.get(id);if(!o)return {};if(const auto* z=std::get_if<ZombieRef>(&*o))return *z;return {};}
    PlantRef native_plant(const std::string& id)override{const auto o=battle.native_objects.get(id);if(!o)return {};if(const auto* q=std::get_if<PlantRef>(&*o))return *q;return {};}
    void drop_coin(double amount,Point point,const std::string& kind)override{resources.drop_coin(amount,point,kind);}
    // NativeBattle.spawn_remnant(x,y): grave-factory body, 出场=500, card hp, no parent; facing from the absent source is 1.
    ZombieRef spawn_remnant(Point point)override{
        const auto card=placement_view.unit_card(Seat::zombie,"zombie:残骸墓碑（非生产）");
        Motion position{point.x,point.y,0.,0.};const auto native=factory.zombie("普通僵尸",position,1.);if(!native)return {};
        native->native.entry.set(500.);native->body.hp=card.hp.get();native->body.motion.replace({point.x,point.y,0.,0.});native->protection.grave=true;
        cold_registration.register_unit(native,card,Seat::zombie,true,cold_admission.context(),nullptr);return native;
    }
    std::optional<Point> grave_soldier_exit(const std::string& key,const std::string& grave)override{
        const auto* unit=public_sync.find(grave);if(!unit)return {};
        return placement_view.grave_soldier_exit(placement_view.unit_card(Seat::zombie,key),Seat::zombie,*unit,1.);
    }
    void set_daylight(bool night)override{economy_state.night=night;battle.placement.day=night?"黑天":"白天";++published.terrain.revision;}
    void event(PveEvent e)override{
        J row{{"event",e.name}};
        for(auto& [key,value]:e.fields)std::visit([&](const auto& v){row[key]=v;},value);
        log_event(row);
    }
    void request_ladder(const ZombieRef& unit)override{director.request_ladder(unit);}
    NativeRoomCommands native_commands{''')
sub('    void cycle_step()override{unsupported.push_back("director cycle");}','    void cycle_step()override{director.cycle_step();}')
sub('    void director_step()override{unsupported.push_back("director");}','    void director_step()override{director.step();}')
sub('    bool director_cleared()const override{return false;}','    bool director_cleared()const override{return director.cleared();}')
sub('        zruntime.present=tick_state.present;zruntime.lock();\n','''        zruntime.present=tick_state.present;zruntime.lock();
        // NativeBattle._team_init: director.bind ran at construction; its products are cold data.
        if(cold.contains("director")){
            const auto& d=cold.at("director");PveDirectorCold c;
            c.day=d.at("day");c.seed=d.at("seed");c.coop=d.at("coop");c.max_zombies=d.at("max_zombies");
            for(const auto& pt:d.at("points"))c.points.push_back({pt.at(0),pt.at(1)});
            for(const auto& e:d.at("pool"))c.pool.push_back({e.at(0).get<std::string>(),e.at(1).get<int>(),e.at(2).get<double>()});
            for(const auto& w:d.at("plan"))c.plan.push_back({w.at("time"),w.at("budget"),w.at("flag")});
            const auto state=[](const J& j){pvz::PyRandom::State s;const auto& w=j.at("mt");for(int i=0;i<624;++i)s.mt[i]=w.at(i).get<uint32_t>();s.mti=j.at("mti");return s;};
            c.rng=state(d.at("rng"));
            if(d.contains("cycle")){c.cycle=true;c.initial_night=d.at("cycle").at("initial_night");c.cycle_rng=state(d.at("cycle").at("rng"));}
            if(d.at("next_wave").get<int64_t>()!=0)throw std::runtime_error("director exported after its first wave");
            director.bind(c);room.director=true;room.director_cycle=c.cycle;
        }
''')
# Exports: the director's unit marks, beside registration.coop_dormant.
sub('write(j,"_pvp_coop_dormant",r.coop_dormant);','write(j,"_pvp_coop_dormant",r.coop_dormant);write(j,"_pvp_wave_index",u.source.wave_index);write(j,"_pvp_spawn_grave",u.pve.spawn_grave);write(j,"_pvp_coop_night_grave",u.pve.night_grave);write(j,"_pvp_coop_just_slept",u.pve.just_slept);')
sub('        const auto& c=p.content_state;const auto& s=p.content70;const auto& fl=p.flying;\n','        const auto& c=p.content_state;const auto& s=p.content70;const auto& fl=p.flying;\n        write(j,"_pvp_coop_coffee",p.pve.coop_coffee);\n')
p.write_text(t,encoding='utf8');print('ok')
