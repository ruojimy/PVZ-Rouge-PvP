// Production crowd movement reproduction. This reports real sampled positions;
// it does not add a unit collision model or assume every layout must be climbable.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/trace.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "sim/pvp/gen/pm_team_maps.h"
#include "ui/gen/pm_room.h"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iostream>
#include <set>
using namespace pvz;using J=nlohmann::json;
namespace {
void need(bool ok,const std::string& text){if(!ok)throw std::runtime_error(text);}
// The actual Room path already owns a started typed battle. Forward its real
// acceptance API instead of re-exporting that live wrapper as a cold battle.
struct AuditBattle {
 std::unique_ptr<typed72app::Session> typed;V wrapped;
 ~AuditBattle(){if(wrapped.has())try{callm(wrapped,SY("close"),Args{});}catch(...){}}
 static V v(const J& j){return py::json_loads(V(j.dump()));}
 static J j(const V& value){return J::parse(dump(value));}
 void fixture_set_avatar(const std::string& side,const J& fields){if(typed)typed->fixture_set_avatar(side,fields);else callm(wrapped,SY("fixture_set_avatar"),Args{V(side),v(fields)});}
 void fixture_ditu(int64_t row,int64_t col,const J& fields){if(typed){typed->fixture_ditu(row,col,fields);return;}V cell=rd(rd(rd(getattr(wrapped,SY("g")),SV("ditu")),V(row)),V(col));for(const auto& [key,value]:fields.items())setitem(cell,V(key),v(value));callm(wrapped,SY("_sync_terrain"),Args{});}
 J snapshot(bool frame){if(typed)return typed->snapshot(frame);return j(callm(wrapped,SY("snapshot"),Args{}));}
 std::string command(const std::string& side,const J& input){return typed?typed->command(side,input):py_str(callm(wrapped,SY("command_input"),Args{V(side),v(input)}));}
 std::optional<std::string> spawn(const std::string& card,const std::string& side,double x,double y,double facing,bool temporary){if(typed)return typed->spawn(card,side,x,y,facing,temporary);const V out=callm(wrapped,SY("spawn"),Args{V(card),V(side),V(x),V(y),V(facing),V(temporary)});return out.is_none()?std::nullopt:std::optional(py_str(py::m_get(out,SV("id"))));}
 void fixture_place_zombie(const std::string& id,double x,double y,double facing){if(typed)need(typed->fixture_place_zombie(id,x,y,facing),"fixture place failed");else need(callm(wrapped,SY("fixture_place_zombie"),Args{V(id),V::list({V(x),V(y)}),V(facing)}).truthy(),"actual fixture place failed");}
 void native_set(bool avatar,const std::string& id,const J& fields){if(typed){typed->native_set(avatar,id,fields);return;}V record=rd(getattr(wrapped,Sym(avatar?"avatars":"_native_objects")),V(id));for(const auto& [key,value]:fields.items())setitem(record,V(key),v(value));}
 void step(){if(typed)typed->step();else callm(wrapped,SY("step"),Args{});}
 J native_view(){if(typed)return typed->native_view();return {{"g",j(getattr(wrapped,SY("g")))},{"avatars",j(getattr(wrapped,SY("avatars")))}};}
 typed72app::SessionClock clock(){if(typed)return typed->clock();return {int64_t(getattr(wrapped,SY("tick")).num()),int64_t(getattr(getattr(wrapped,SY("engine")),SY("native_tick")).num()),int64_t(getattr(wrapped,SY("terrain_revision")).num()),getattr(wrapped,SY("time")).num(),getattr(wrapped,SY("deathmatch")).truthy()};}
 J rng_state(){if(typed)return typed->rng_state();const V state=callm(getattr(getattr(wrapped,SY("engine")),SY("rng")),SY("getstate"),Args{}),words=state.idx(1);J mt=J::array();for(int i=0;i<624;++i)mt.push_back(words.idx(i).num());return {{"mt",mt},{"mti",words.idx(624).num()}};}
 bool finished(){return typed?typed->finished():getattr(wrapped,SY("result")).truthy();}
 J performance_counters(){return typed?typed->performance_counters():j(callm(wrapped,SY("backend_audit"),Args{}))["performance"];}
};
J run(const J& config){
 const auto map=config.value("map",std::string("oasis")),mode=config.value("mode",std::string("coop")),layout=config.value("layout",std::string("same"));
 const int count=config.value("count",40),ticks=config.value("ticks",1400),stride=config.value("sample_stride",20),seed=config.value("seed",742);
 need(count>=0&&count<=1000&&ticks>0&&stride>0,"invalid audit limits");
 need(count>0||config.value("track_all_mobiles",false),"zero manual actors requires natural mobile tracking");
 J scenario={{"seed",seed},{"mode",mode},{"durable_heroes",true},{"rules",{{"pve_max_zombies",config.value("population_rule",40)}}}};
 if(config.value("passive_heroes",false))scenario["decks"]={{"plant",{"plant:坚果"}},{"zombie",{"zombie:脑光墓碑","zombie:普通僵尸"}}};
 if(map=="oasis")scenario["team_map"]="ea66000000000000000000000000000a";else if(map=="flat_wall")scenario["fixture_flat"]=true;else throw std::invalid_argument("unknown map");
 auto h=battle_from_scenario(scenario);
 struct Close {BattleHandle& h;~Close(){try{callm(h.battle,SY("close"),Args{});}catch(...){}}} close{h};
 V room;J room_entry;
 auto cold=typed72app::export_cold(h.battle,seed);
 if(config.contains("room_day")){
  need(mode=="coop"&&map=="oasis","actual Room director fixture requires cooperative Oasis map");
  const auto value=[](const J& j){return py::json_loads(V(j.dump()));};
  room=pm_room::new_Room(Args{h.bridge,getattr(h.battle,SY("rules"))});auto* r=as<pm_room::C_Room>(room);
  r->a_mode=SV("coop");r->a_phase=SV("config");r->a_seed=V(seed);r->a_replay_enabled=V(false);
  r->a_members=value({{"host","plant"},{"guest","plant2"}});r->a_connected=value({{"host",true},{"guest",true}});
  need(py_str(callm(room,SY("set_pve"),Args({V(config["room_day"].get<int>()),value({"plant:向日葵"})},{{SY("seed"),V(seed)},{SY("max_zombies"),V(40)}}))).empty(),"actual Room.set_pve rejected");
  const auto limit=config.value("population_rule",40);
  need(py_str(callm(room,SY("command"),Args{SV("host"),value({{"type","pve_population"},{"max_zombies",limit},{"revision",r->a_revision.num()}})})).empty(),"actual population command rejected");
  r->a_map=pm_team_maps::f_bundled_snapshot(Args{V("ea66000000000000000000000000000a")});
  callm(room,SY("_start_pve"),Args{});
  room_entry={{"entry","Room.set_pve -> Room.command(pve_population) -> Room._start_pve"},{"day",config["room_day"]},{"requested_limit",limit},
   {"rule",rd(getattr(r->a_battle,SY("rules")),SV("pve_max_zombies")).num()},{"director_limit",getattr(getattr(r->a_battle,SY("director")),SY("max_zombies")).num()}};
  room_entry["scope"]="The actual already-typed Room battle is advanced through its real methods; no second cold export or synthetic director.";
 }
 const double width=cold.cold["battle"]["width"];
 auto b=std::make_unique<AuditBattle>();if(room.has())b->wrapped=getattr(room,SY("battle"));else b->typed=typed72app::Session::create(std::move(cold),"crowd stack production audit");
 const double sx=map=="oasis"?552.:1992.,ground=map=="oasis"?1248.:960.,hx=map=="oasis"?888.:2184.,hy=map=="oasis"?576.:768.;
 for(const char* side:{"plant","plant2"})if(side==std::string("plant")||mode=="coop")b->fixture_set_avatar(side,{{"玩家位置",{hx,hy,0,0}},{"玩家血量",1.e8}});
 b->fixture_set_avatar("zombie",{{"玩家位置",{map=="oasis"?3888.:2880.,ground,0,0}},{"玩家血量",1.e8}});
 if(map=="flat_wall")for(int row=16;row<20;++row)for(int col=42;col<48;++col)b->fixture_ditu(row,col,{{"方块","土"},{"里方块","空"}});
 if(b->snapshot(false)["command"]!="attack")need(b->command("zombie",{{"type","command"},{"seq",1}}).empty(),"attack command rejected");
 std::set<std::string> ids;J admitted=J::array();
 for(int i=0;i<count;++i){
  double x=sx,y=ground;
  if(layout=="same"){}else if(layout=="old_epsilon")x+=double(i%4)*.1;
  else if(layout=="boundary")x=std::floor(sx/48.+.5)*48.+(i%2?.01:-.01);
  else if(layout=="wide")x-=double(i%16)*24.;
  else if(layout=="staggered"){x-=double(i%12)*12.;y-=double((i/12)%4)*24.;}
  else throw std::invalid_argument("unknown layout");
  const auto id=b->spawn("zombie:普通僵尸","zombie",x,y,1,false);
  need(bool(id),"scripted spawn budget rejected ordinal "+std::to_string(i)+"; this case cannot claim that the requested crowd entered the match");
  ids.insert(*id);b->fixture_place_zombie(*id,x,y,1);b->native_set(false,*id,{{"血量",1.e8},{"_pvp_max_hp",1.e8},{"出场",500.}});
  admitted.push_back({{"id",*id},{"x",x},{"y",y}});
 }
 J samples=J::array(),rng_samples=J::array(),natural_births=J::array();double best=ground;int max_upper=0,max_ascending=0,steps=0;bool ended=false;
 const auto started=std::chrono::steady_clock::now();
 for(int tick=0;tick<ticks;++tick){
  // Controlled target fixture only: prevent knockback from pushing the target
  // off the platform halfway through the observation interval. Unit movement
  // and every native step inside the room tick remain the production code.
  if(config.value("pin_heroes",false))for(const char* side:{"plant","plant2"})if(side==std::string("plant")||mode=="coop")
   b->fixture_set_avatar(side,{{"玩家位置",{hx,hy+9.6,0,0}},{"玩家血量",1.e8}});
  b->step();++steps;
  if(tick<12||tick%stride==0||tick==ticks-1){
   const auto native=b->native_view();J actors=J::array();int upper=0,ascending=0,cd_short=0,alive=0;
   if(config.value("track_all_mobiles",false))for(const auto& z:native["g"]["僵尸"])if(!z.value("_pvp_grave",false)&&z.value("血量",0.)>0.){
    const auto id=z.value("_pvp_id",std::string{});if(!id.empty()&&ids.insert(id).second)natural_births.push_back({{"sampled_room_step",tick},{"id",id},{"card",z.value("_pvp_card",std::string{})},{"kind",z.value("僵尸",std::string{})},{"position",z["位置"]}});
   }
   for(const auto& z:native["g"]["僵尸"])if(ids.contains(z.value("_pvp_id",std::string{}))){
    J a;for(const char* key:{"_pvp_id","位置","血量","方向","跳跃cd","出场","分兵","分裂","坚持分兵","啃咬","大蒜","冰冻","黄油","眩晕"})if(z.contains(key))a[key]=z[key];
    const double y=z["位置"][1],vy=z["位置"][3];best=std::min(best,y);upper+=y<=hy+48.;ascending+=vy<-.01;alive+=z.value("血量",0.)>0.;const double cd=z.value("跳跃cd",0.);cd_short+=cd>0.&&cd<70.;actors.push_back(std::move(a));
   }
   max_upper=std::max(max_upper,upper);max_ascending=std::max(max_ascending,ascending);const auto clock=b->clock();
   samples.push_back({{"requested_step",tick},{"room_tick",clock.room_tick},{"native_tick",clock.native_tick},{"game_seconds",clock.time},{"alive",alive},{"above_platform",upper},{"ascending",ascending},{"jump_cd_between_0_and_70",cd_short},{"avatars",native["avatars"]},{"actors",actors}});
  }
  if(tick%100==0)rng_samples.push_back({{"requested_step",tick},{"rng",b->rng_state()}});
  if(b->finished()){ended=true;break;}
 }
 const auto last=b->clock();J final_native=b->native_view();
 const double elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
 return {{"config",config},{"scenario",scenario},{"actual_room_entry",room_entry},{"run_completed",steps==ticks&&!ended},{"ended_early",ended},{"admitted_count",admitted.size()},{"admitted",admitted},{"tracked_mobile_ids",ids.size()},{"natural_births",natural_births},{"requested_steps",ticks},{"completed_steps",steps},{"room_tick",last.room_tick},{"native_tick",last.native_tick},{"game_seconds",last.time},{"sampled_lowest_feet_y",best},{"sampled_rise",ground-best},{"platform_top_y",hy},{"max_sampled_units_within_48px_of_platform_height",max_upper},{"max_sampled_ascending_units",max_ascending},{"world_width",width},{"samples",samples},{"rng_samples",rng_samples},{"final_rng",b->rng_state()},{"final_native",final_native},{"performance",b->performance_counters()},{"wall_seconds",elapsed},{"scope","Production Session; real sampled state and RNG. Short jump-CD observations are not exact helper-branch counters. No artificial unit collision/stacking rule; reaching the platform is reported, not assumed. Actual Room director pool/plan untouched when room_day is present; manually admitted crowd versus naturally observed births are separate fields."}};
}
}
int main(int argc,char** argv){
 if(argc<3||!std::getenv("PVP_USERDATA"))return 2;install_crash_handler();SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();J report;
 try{J config;std::ifstream(argv[2])>>config;report=run(config);report["audit_error"]=nullptr;}catch(const std::exception& e){print_last_cpp_throw(stderr);report={{"run_completed",false},{"audit_error",e.what()}};}
 std::ofstream(argv[1],std::ios::binary)<<report.dump();J brief=report;for(const char* k:{"samples","rng_samples","final_rng","final_native","admitted","performance"})brief.erase(k);std::cout<<brief.dump()<<std::endl;return report["audit_error"].is_null()?0:1;
}
