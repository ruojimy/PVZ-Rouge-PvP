#include "pvp742_guest_memory_fixture.h"
#include "ui/hand/pressure_pacing.h"
using namespace pvz;
using namespace pvz::guest_memory_audit;
namespace {
V value(const J& j){return py::json_loads(V(j.dump()));}
struct RoomFixture {
    BattleHandle h=battle_from_scenario({{"seed",744},{"durable_heroes",true}});
    V app,room,battle;
    pm_room::C_Room* r;
    RoomFixture(){
        V pg=pg::pygame_module(),screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(720)})});
        app=pm_app::new_Application(Args{pg,screen,h.bridge});callm(app,SY("create"),Args{V(true)});
        room=getattr(app,SY("room"));r=as<pm_room::C_Room>(room);r->a_rules=getattr(h.battle,SY("rules"));
        r->a_replay_enabled=V(false);r->a_decks=V::dict();
        for(const auto& item:py::items_vec(getattr(h.battle,SY("players"))))setitem(r->a_decks,item.first,py::list_it(rd(item.second,V("deck"))));
        callm(room,SY("_start_battle"),Args{});battle=r->a_battle;typed72app::start_battle_session(battle);
        r->a_phase=V("battle");r->a_recording=V::none();r->a_loaded=value({{"plant",true},{"zombie",true}});
        r->a__paced_battle=battle;as<pm_adaptive_pacing::C_AdaptivePacing>(r->a_pacing)->frame_gated=true;
    }
    ~RoomFixture(){try{callm(app,SY("close_room"),Args{});callm(h.battle,SY("close"),Args{});}catch(...){} }
};
}
int main(int argc,char**argv){
    if(argc!=2||!std::getenv("PVP_USERDATA"))return 2;
    SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
    J checks=J::array();int failed=0;
    auto test=[&](const char* name,auto fn){J row={{"name",name}};try{row["evidence"]=fn();row["passed"]=true;}catch(const std::exception&e){row["passed"]=false;row["error"]=e.what();++failed;}checks.push_back(row);std::cout<<row.dump()<<std::endl;};
    test("budget_boundary_state_rng_and_repeated_jump_edges",[]{
        auto h=battle_from_scenario({{"seed",744},{"fixture_flat",true},{"durable_heroes",true}});
        V a=typed72app::wrap_battle(h.battle),b=typed72app::wrap_battle(h.battle);
        typed72app::start_battle_session(a);typed72app::start_battle_session(b);
        int seq=0,yields=0;
        for(int count:{7,19,31,13}){
            for(bool jump:{false,true,false,true,false}){
                V input=value({{"type","move"},{"seq",++seq},{"move",seq%3-1},{"jump",jump}});
                for(const V& v:{a,b})require(!callm(v,SY("command_input"),Args{SV("plant"),input}).truthy(),"input rejected");
            }
            callm(a,SY("step"),Args{V(count)});
            const double target=getattr(a,SY("tick")).num();
            while(getattr(b,SY("tick")).num()<target){
                const double before=getattr(b,SY("tick")).num();
                callm(b,SY("step"),Args({V(target-before)},{{SY("budget_seconds"),V(1e-9)}}));
                require(getattr(b,SY("tick")).num()==before+1.,"sub-step yield or missing progress");++yields;
            }
            require(json(callm(a,SY("snapshot"),Args{}))==json(callm(b,SY("snapshot"),Args{})),"snapshot/native frame changed at equal tick");
            require(dump(callm(getattr(getattr(a,SY("engine")),SY("rng")),SY("getstate"),Args{}))==dump(callm(getattr(getattr(b,SY("engine")),SY("rng")),SY("getstate"),Args{})),"RNG changed");
        }
        const J audit=json(callm(b,SY("backend_audit"),Args{}));
        require(audit["dynamic_v_work"]["step"]["boxes"]==0&&audit["dynamic_v_work"]["step"]["calls"]==0,"dynamic V entered typed loop");
        if(std::getenv("PVP744_INPUT_TRACE")&&std::string(std::getenv("PVP744_INPUT_TRACE"))=="1"){
            const auto& trace=audit.at("input_dispatch").at("entries");require(trace.size()==20,"dispatch trace lost an input edge");
            for(const auto& event:trace)require(event["accepted"]==true&&event["adapter_entered_seconds"]<=event["dispatch_started_seconds"]&&event["dispatch_started_seconds"]<=event["dispatch_completed_seconds"],"dispatch stages not ordered");
        }
        callm(a,SY("close"),Args{});callm(b,SY("close"),Args{});
        return J{{"steps",yields},{"input_edges",seq},{"budget_yields",audit["scheduler_budget_yields"]}};
    });
    test("real_room_debt_conservation_and_zero_delta_drain",[]{
        RoomFixture f;const double before=getattr(f.battle,SY("tick")).num(),dt=getattr(f.battle,SY("dt")).num();
        callm(f.room,SY("update"),Args{V(1.7)});
        const double first=getattr(f.battle,SY("tick")).num()-before;
        require(first>=1.&&first<=12.,"invalid first batch");
        require(std::abs(f.r->a_accumulator.num()+first*dt-1.7)<1e-8,"first batch lost/duplicated credit");
        int rounds=0;
        while(f.r->a_accumulator.num()+1e-9>=dt&&rounds++<100)callm(f.room,SY("update"),Args{V(0.)});
        const double steps=getattr(f.battle,SY("tick")).num()-before;
        require(std::abs(steps*dt+f.r->a_accumulator.num()-1.7)<1e-8,"debt conservation failed");
        require(std::abs(f.r->a_accumulator.num())<1e-8,"debt did not drain");
        return J{{"first_steps",first},{"total_steps",steps},{"drain_calls",rounds},{"debt",f.r->a_accumulator.num()}};
    });
    test("local_frame_reuse_detached_public_snapshots_and_invalidation",[]{
        auto h=battle_from_scenario({{"seed",744},{"fixture_flat",true},{"durable_heroes",true}});
        V battle=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(battle);
        callm(battle,SY("step"),Args{V(1)});
        const auto local=[&]{typed72app::LocalPresentationScope lease(battle);return callm(battle,SY("snapshot"),Args{V(false),V(false)});};
        V first=local();const J initial=json(first);
        for(int i=0;i<200;++i){V next=local();require(py_is(rd(next,SV("units")),rd(first,SV("units"))),"same version rebuilt actor rows");}
        V detached=callm(battle,SY("snapshot"),Args{V(false),V(false)});
        V detached_player=rd(rd(detached,SV("players")),SV("plant"));setitem(detached_player,SV("resource"),V(-999.));
        require(json(local())==initial,"public snapshot mutation corrupted private presentation");
        V input=value({{"type","move"},{"seq",1},{"move",1},{"jump",true}});
        require(!callm(battle,SY("command_input"),Args{SV("plant"),input}).truthy(),"same-tick command rejected");
        V changed=local();require(json(changed)!=initial,"same-tick command did not invalidate frame");
        require(json(first)==initial,"held frame mutated after command");
        const J before_tick=json(changed);callm(battle,SY("step"),Args{V(1)});
        require(json(local())!=before_tick&&json(changed)==before_tick,"tick invalidation/held-frame contract failed");
        V avatars=getattr(battle,SY("avatars"));setitem(rd(avatars,SV("plant")),SV("玩家血量"),V(700.));
        require(json(local())["players"]["plant"]["hp"]==700.,"fixture/health change left stale frame");
        const J audit=json(callm(battle,SY("backend_audit"),Args{}));
        require(audit["local_presentation_builds"]==4&&audit["local_presentation_hits"].get<int>()>=201,"unexpected cache versions");
        callm(battle,SY("close"),Args{});
        return J{{"builds",audit["local_presentation_builds"]},{"hits",audit["local_presentation_hits"]},{"held_frames_unchanged",true}};
    });
    test("early_terminal_battle_debits_only_executed_steps",[]{
        RoomFixture f;V avatars=getattr(f.battle,SY("avatars"));setitem(rd(avatars,SV("zombie")),SV("玩家血量"),V(0.));
        const double before=getattr(f.battle,SY("tick")).num(),dt=getattr(f.battle,SY("dt")).num();
        callm(f.room,SY("update"),Args{V(.4)});
        const double completed=getattr(f.battle,SY("tick")).num()-before;
        require(completed==1.&&getattr(f.battle,SY("result")).truthy(),"fixture did not finish in first step");
        require(std::abs(f.r->a_accumulator.num()+completed*dt-.4)<1e-8,"terminal batch over-debited");
        return J{{"completed_steps",completed},{"retained_seconds",f.r->a_accumulator.num()}};
    });
    test("wall_pressure_requires_independent_frames_and_recovers",[]{
        auto app=std::make_shared<pm_app::C_Application>();auto room=std::make_shared<pm_room::C_Room>();
        V av=V::inst(app);app->a_state=V::dict();app->a_mode=SV("local");app->a_room=V::inst(room);
        J units=J::array();for(int i=0;i<100;++i)units.push_back(J::object());
        app->a_view=value({{"phase","battle"},{"battle",{{"time",0.},{"units",units}}}});
        room->a_pacing=pm_adaptive_pacing::new_AdaptivePacing(Args{});
        auto* p=as<pm_adaptive_pacing::C_AdaptivePacing>(room->a_pacing);p->a_ratio=V(3.);
        const bool candidate=std::getenv("PVP744_PACING")&&std::string(std::getenv("PVP744_PACING"))=="1";
        for(int i=0;i<290;++i)pressure741::observe(av,1./60.,.005);
        require(p->a_scale.num()==1.,"opening slowed");
        pressure741::observe(av,.7,.65);require(p->a_scale.num()==1.,"one long frame slowed battle");
        for(int i=0;i<2;++i)pressure741::observe(av,.7,.65);
        if(candidate)require(p->a_scale.num()<1.,"three severe frames failed sustained wall gate");
        for(int i=0;i<30;++i)pressure741::observe(av,.7,.65);
        require(p->a_scale.num()<.5,"sustained pressure not relieved");const double slow=p->a_scale.num();
        app->a_view=value({{"phase","battle"},{"battle",{{"time",1.},{"units",J::array()}}}});p->a_ratio=V(1.);
        for(int i=0;i<900;++i)pressure741::observe(av,1./60.,.005);
        require(p->a_scale.num()==1.,"recovery failed");
        setitem(app->a_view,SV("paused"),V(true));pressure741::observe(av,.5,.05);
        require(p->pressure_bad_frames==0&&p->pressure_seconds==0.,"pause retained pressure gate");
        return J{{"candidate",candidate},{"slow",slow},{"recovered",p->a_scale.num()}};
    });
    std::ofstream(u8p(argv[1]))<<J{{"passed",failed==0},{"checks",checks}}.dump(2);return failed?1:0;
}
