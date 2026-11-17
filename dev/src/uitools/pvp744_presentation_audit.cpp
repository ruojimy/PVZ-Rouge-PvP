#include "pvp742_guest_memory_fixture.h"
#include "ui/gen/pm_presentation.h"
using namespace pvz;
using namespace pvz::guest_memory_audit;
namespace {
V value(const J& j){return py::json_loads(V(j.dump()));}
J frame(double time,double x=0.){
    return {{"phase","battle"},{"match_id","match-a"},{"match_number",1},{"mode","local"},
        {"terrain_hash","map"},{"pacing",{{"slow",true}}},{"map",{{"width",960},{"tile_size",48}}},
        {"battle",{{"time",time},{"terrain_revision",0},
            {"players",{{"plant",{{"x",x},{"y",0},{"hp",100},{"resource",50},{"teleport_ready_at",0}}}}},
            {"units",J::array({{{"id","u"},{"x",x},{"y",0},{"hp",100}}})},
            {"native_frame",{{"positions",{{"u",{x,0}},{"hero:plant",{x,0}}}}}}}}};
}
struct Fixture {
    std::shared_ptr<double> now=std::make_shared<double>(10.);
    V presentation,current;
    Fixture(){auto clock=now;presentation=pm_presentation::new_GuestPresentation(Args{V::func([clock](const Args&){return V(*clock);})});accept(frame(0.));*now=10.02;accept(frame(1./30.,10.));*now=10.03;}
    void accept(J next){current=value(next);callm(presentation,SY("accept"),Args{current});}
    J sample(){return json(callm(presentation,SY("sample"),Args{current}));}
    double x(){return sample()["battle"]["players"]["plant"]["x"].get<double>();}
    void expect_x(double expected){require(std::abs(x()-expected)<1e-7,"unexpected displayed position");}
};
}
int main(int argc,char** argv){
    if(argc!=2||!std::getenv("PVP_USERDATA"))return 2;
    SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
    J checks=J::array();int failed=0;
    auto test=[&](const char* name,auto fn){J row={{"name",name}};try{fn();row["passed"]=true;}catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();++failed;}checks.push_back(row);std::cout<<row.dump()<<std::endl;};
    test("duplicates_preserve_origin_until_completion",[]{Fixture f;f.expect_x(3.);const J original=json(f.current);for(double t:{10.03,10.04,10.05}){*f.now=t;f.accept(frame(1./30.,10.));f.expect_x((t-10.02)*300.);}*f.now=10.06;f.expect_x(10.);require(json(f.current)==original,"sample mutated authoritative frame");});
    test("same_tick_health_resources_ack_and_animation_are_live",[]{Fixture f;auto next=frame(1./30.,10.);next["battle"]["players"]["plant"].update({{"hp",70},{"resource",22},{"seq",8}});next["battle"]["units"][0]["hp"]=60;next["battle"]["native_frame"]["animation"]=4;next["notice"]="new";f.accept(next);f.expect_x(3.);const auto shown=f.sample();require(shown["battle"]["players"]["plant"]["hp"]==70&&shown["battle"]["players"]["plant"]["resource"]==22&&shown["battle"]["players"]["plant"]["seq"]==8&&shown["battle"]["units"][0]["hp"]==60&&shown["battle"]["native_frame"]["animation"]==4&&shown["notice"]=="new","duplicate lost current state");});
    test("new_pose_continues_from_displayed_position",[]{Fixture f;*f.now=10.035;f.expect_x(4.5);f.accept(frame(2./30.,20.));f.expect_x(4.5);*f.now=10.045;f.expect_x(4.5+(20.-4.5)*.3);});
    test("same_tick_coordinate_change_snaps",[]{Fixture f;f.accept(frame(1./30.,11.));f.expect_x(11.);});
    test("teleport_token_change_snaps_hero",[]{Fixture f;auto next=frame(1./30.,10.);next["battle"]["players"]["plant"]["teleport_ready_at"]=5;f.accept(next);f.expect_x(10.);});
    test("death_and_revive_snap",[]{Fixture f;auto dead=frame(1./30.,10.);dead["battle"]["players"]["plant"]["hp"]=0;f.accept(dead);f.expect_x(10.);f.accept(frame(2./30.,20.));f.expect_x(20.);});
    test("pause_disconnect_audit_and_result_reset",[]{for(const std::string field:{"paused","disconnected","audit_error","phase"}){Fixture f;auto next=frame(1./30.,10.);if(field=="phase")next[field]="result";else next[field]=true;f.accept(next);f.expect_x(10.);f.accept(frame(2./30.,20.));f.expect_x(20.);}});
    test("epoch_map_seat_changes_reset",[]{for(const std::string field:{"match_id","match_number","loading_id","mode","terrain_hash","terrain_revision","local_seat"}){Fixture f;auto next=frame(2./30.,20.);if(field=="terrain_revision"||field=="local_seat")next["battle"][field]="changed";else next[field]="changed";f.accept(next);f.expect_x(20.);}});
    test("large_gap_and_reverse_time_snap",[]{Fixture f;*f.now=11.;f.accept(frame(2./30.,20.));f.expect_x(20.);f.accept(frame(0.,0.));f.expect_x(0.);});
    test("ring_seam_uses_short_path",[]{Fixture f;callm(f.presentation,SY("clear"),Args{});*f.now=20.;f.accept(frame(0.,958.));*f.now=20.02;f.accept(frame(1./30.,2.));*f.now=20.02+1./60.;const double x=f.x();require(std::min(std::abs(x),std::abs(x-960.))<1e-7,"seam took the long path");});
    test("guest_normal_latency_duplicate_and_teleport",[]{Fixture f;callm(f.presentation,SY("clear"),Args{});auto a=frame(0.,0.);a["mode"]="guest";a["pacing"]["slow"]=false;*f.now=30.;f.accept(a);a["battle"]=frame(1./30.,10.)["battle"];*f.now=30.02;f.accept(a);*f.now=30.03;f.accept(a);f.expect_x(3.);a["battle"]=frame(2./30.,300.)["battle"];f.accept(a);f.expect_x(300.);});
    std::ofstream(u8p(argv[1]))<<J{{"passed",failed==0},{"checks",checks}}.dump(2);return failed?1:0;
}
