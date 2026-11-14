// White-box acceptance of the generated production composition, including the
// seven omitted arrays, per-tick cleanup and a real poison pulse.
#define TYPED72_NO_MAIN
#include "match_probe.cpp"
#include "sim/typed72_app/cold_file.h"
#include <iostream>
int main(int argc,char** argv){
    try{
        if(argc!=2)throw std::invalid_argument("fixture_retention_test cold.json[.gz]");
        const auto cold=J::parse(pvz::typed72app::read_file_maybe_gz(argv[1]));
        MatchProbe m(1,cold.at("battle").at("width"),cold.at("battle").at("rules").at("melon_splash_damage"));
        m.no_trace=true;m.release_fixtures=true;m.setup(cold,J::object());
        const auto check=[](bool yes,const char* what){if(!yes)throw std::runtime_error(what);};
        std::array<J*,7> logs{&m.aliases64,&m.draws64,&m.events64,&m.spawns64,&m.cost_calls,&m.grenade_events,&m.poison_events};
        for(auto* a:logs)a->push_back("sentinel");
        m.native_tick_done();for(const auto* a:logs)check(a->empty(),"tick failed to release probe evidence");
        m.release_fixtures=false;for(auto* a:logs)a->push_back("retained reference evidence");
        m.native_tick_done();for(const auto* a:logs)check(a->size()==1,"reference retention changed");
        m.release_fixtures=true;m.native_tick_done();
        // Exercise stripped base service functions directly; real overrides have
        // their own business paths and are intentionally never erased.
        m.ContentZombie64Probe::alias_art("a","b");m.ContentZombie64Probe::emit64("e",J::object());
        m.ContentZombie64Probe::draw_zombie({});m.costs["fixture"]=25.;
        check(m.GrenadierProbe::card_cost({},"fixture")==25.,"strip altered a return value");
        m.NativeStatusProbe::poison_damage({},4.,1);
        m.NativeStatusProbe::break_poisoned_barrel({});m.NativeStatusProbe::detach_poisoned_barrel({});
        for(const auto* a:logs)check(a->empty(),"production service retained probe history");
        const auto id=m.cold_admission.spawn("zombie:普通僵尸",Seat::zombie,{1200.,300.},-1.,true);
        check(bool(id),"poison fixture spawn failed");const auto u=m.spawned_zombie(id);
        const double before=u->body.hp;const size_t journal_before=m.log.size();
        m.poison.apply(CombatTarget::zombie(u),2,4.,Seat::plant);
        m.world.tick=250;m.poison.tick({});
        check(u->body.hp==before-8.,"poison damage changed");
        check(m.log.size()>journal_before&&m.log.back().value("event",std::string{})=="poison_damage","poison business journal lost");
        check(m.poison_events.empty(),"real poison retained fixture history");
        m.native_tick_done();
        check(m.deployment.bans==cold.at("battle").value("bans",std::vector<std::string>{}),"cold bans not projected");
        std::cout<<J{{"passed",true},{"arrays_checked",7},{"poison_damage",before-u->body.hp},{"fixture_retention",m.fixture_retention()}}.dump()<<'\n';
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
