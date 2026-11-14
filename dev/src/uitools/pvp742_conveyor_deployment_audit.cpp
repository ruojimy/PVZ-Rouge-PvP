// Normal Room commands and actual co-op director entry, never the user's room.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/trace.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/typed_battle.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "sim/pvp/gen/pm_maps.h"
#include "ui/gen/pm_room.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
#include <set>
using namespace pvz;using J=nlohmann::json;
namespace {
void require(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
V value(const J& j){return py::json_loads(V(j.dump()));}
J json(const V& v){return J::parse(dump(v));}
V wall_map(){
 V rows=V::list();for(int y=0;y<24;++y){V row=V::list();for(int x=0;x<72;++x){const bool solid=y>=20||(y>=16&&x>=42&&x<48);row.append(pm_maps::f__cell(Args{value({{"方块",solid?"土":"空"},{"里方块","空"}}),V::tuple({SV("空"),SV("水"),SV("花盆块"),SV("梯子块"),SV("坟墓")})}));}rows.append(row);}
 return pm_maps::new_MapSnapshot(Args({SV("传送带正常部署高台"),V(742),SV("conveyor-normal-entry-742"),rows},{{SY("spawns"),value({{"plant",{2184,768}},{"zombie",{1944,960}}})},{SY("environment"),value({{"night",true},{"weather","clear"}})},{SY("source"),SV("conveyor-normal-entry-742")}}));
}
J trim(J z){for(auto it=z.begin();it!=z.end();){if(it.key()!="_pvp_id"&&it.key()!="_pvp_card"&&it.key()!="_pvp_content"&&it.key()!="僵尸"&&it.key()!="位置"&&it.key()!="出场"&&it.key()!="跳跃cd"&&it.key()!="分兵"&&it.key()!="分裂"&&it.key()!="手持"&&it.key()!="手持血量"&&it.key()!="血量"&&it.key()!="魅惑"&&it.key()!="_pvp_zs_hand_kind"&&it.key()!="_pvp_wave")it=z.erase(it);else++it;}return z;}
struct Fixture {
 BattleHandle h;V room,b;pm_room::C_Room* r;int64_t seq_z=0,seq_p=0;J commands=J::array();
 explicit Fixture(bool coop=false):h(battle_from_scenario({{"seed",742},{"rules",{{"plant_slots",16},{"zombie_slots",16},{"plant_start",100000},{"night_plant_start",100000},{"zombie_start",100000},{"night_zombie_start",100000}}},{"night",true},{"durable_heroes",true},{"decks",{{"plant",{"plant:向日葵","plant:魅惑菇","plant:花盆"}},{"zombie",{"zombie:脑光墓碑","zombie:梯子僵尸","zombie:传送带僵尸"}}}}})){
  room=pm_room::new_Room(Args{h.bridge,getattr(h.battle,SY("rules"))});r=as<pm_room::C_Room>(room);r->a_rules=getattr(h.battle,SY("rules"));r->a_map=wall_map();r->a_seed=V(742);r->a_replay_enabled=V(false);r->a_bans=V::list();r->a_decks=V::dict();
  for(const auto& pair:py::items_vec(getattr(h.battle,SY("players"))))setitem(r->a_decks,pair.first,py::list_it(rd(pair.second,SV("deck"))));
  r->a_members=value(coop?J{{"host","plant"},{"guest","plant2"}}:J{{"host","zombie"},{"guest","plant"}});r->a_connected=value({{"host",true},{"guest",true}});r->a_mode=V(coop?"coop":"duel");
  if(coop){r->a_pve=value({{"day",10},{"seed",742},{"deck",{"plant:向日葵","plant:魅惑菇","plant:花盆"}},{"max_zombies",40},{"start_sun",100000}});callm(room,SY("_start_pve"),Args{});}else callm(room,SY("_start_battle"),Args{});
  b=r->a_battle;typed72app::start_battle_session(b);r->a_phase=SV("battle");r->a_recording=V::none();r->a_loaded=value(coop?J{{"plant",true},{"plant2",true}}:J{{"plant",true},{"zombie",true}});
  avatar("plant",2184,768);if(coop)avatar("plant2",2208,768);else avatar("zombie",1944,960);
  if(!coop)for(const char* side:{"plant","zombie"})setitem(rd(getattr(b,SY("players")),V(side)),SV("cooldowns"),V::dict());
 }
 ~Fixture(){try{callm(b,SY("close"),Args{});callm(h.battle,SY("close"),Args{});}catch(...) {}}
 void avatar(const char* side,double x,double y){callm(b,SY("fixture_set_avatar"),Args{V(side),value({{"玩家位置",{x,y,0,0}},{"玩家血量",1.e8}})});}
 void send(bool plant,J input){input["seq"]=plant?++seq_p:++seq_z;const auto peer=plant?"guest":"host";const auto result=py_str(callm(room,SY("command"),Args{V(peer),value({{"type","input"},{"input",input}})}));commands.push_back({{"peer",peer},{"input",input},{"error",result}});require(result.empty(),"Room.command rejected: "+result+" input="+input.dump());}
 J zombies(){return json(rd(getattr(b,SY("g")),SV("僵尸")));}
 J get(const std::string& id){for(auto z:zombies())if(z.value("_pvp_id",std::string{})==id)return z;return nullptr;}
 std::string deploy(const char* card,double x,double y,const std::string& grave={},bool plant=false){std::set<std::string> before;for(auto z:zombies())before.insert(z.value("_pvp_id",std::string{}));J input={{"type","deploy"},{"card",card},{"x",x},{"y",y},{"facing",1}};if(!grave.empty())input["grave"]=grave;send(plant,input);for(auto z:zombies())if(!before.contains(z.value("_pvp_id",std::string{})))return z.at("_pvp_id");if(plant)return {};throw std::runtime_error("deployed zombie absent");}
 void step(){callm(b,SY("step"),Args{});require(!getattr(b,SY("result")).truthy(),"match ended during conveyor fixture");}
 J ladders(){J out=J::array();const V grid=rd(getattr(b,SY("g")),SV("ditu"));for(int y=0;y<int(grid.len());++y){const V row=grid.idx(y);for(int x=0;x<int(row.len());++x){const V cell=row.idx(x);if(py::m_get(cell,SV("方块"))==SV("梯子块"))out.push_back({{"row",y},{"col",x},{"belt",py::m_get(cell,SV("_pvp_belt"),V(false)).truthy()}});}}return out;}
};
}
int main(int argc,char**argv){
 if(argc<2||!std::getenv("PVP_USERDATA"))return 2;install_crash_handler();SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();J cases=J::array();int failures=0;
 auto test=[&](std::string name,auto fn){J row={{"name",name}};try{row["evidence"]=fn();row["passed"]=true;}catch(const std::exception&e){print_last_cpp_throw(stderr);row["passed"]=false;row["error"]=e.what();++failures;}std::cerr<<J{{"name",name},{"passed",row["passed"]},{"error",row.value("error",std::string{})}}.dump()<<std::endl;cases.push_back(std::move(row));};
 for(const char* kind:{"梯子僵尸","传送带僵尸"})for(const char* mode:{"attack","follow","rally","hypnotized"})test(std::string("Room_command_")+kind+"_"+mode,[&]()->J{
  Fixture f;const auto grave=f.deploy("zombie:脑光墓碑",1944,960);const auto id=f.deploy((std::string("zombie:")+kind).c_str(),1992,960,grave);const J born=trim(f.get(id));
  const bool charm=std::string(mode)=="hypnotized";
  if(charm)f.deploy("plant:魅惑菇",1992,936,{},true);
  if(std::string(mode)=="follow"||charm){f.avatar("zombie",2184,768);if(py_str(getattr(f.b,SY("command")))!="follow")f.send(false,{{"type","command"}});}
  else if(std::string(mode)=="attack"){if(py_str(getattr(f.b,SY("command")))!="attack")f.send(false,{{"type","command"}});}
  else f.send(false,{{"type","rally"},{"x",2184},{"y",768}});
  if(charm)f.avatar("plant",1008,960);
  J trail=J::array(),placed=J::array();int first=-1,entered=-1,charmed_at=-1;
  for(int t=0;t<1200;++t){f.step();const auto z=f.get(id);require(!z.is_null(),"builder disappeared at roomtick "+std::to_string(t));if(z.value("出场",0.)==500.&&entered<0)entered=t;if(z.contains("魅惑")&&charmed_at<0)charmed_at=t;if(t%15==0)trail.push_back({{"tick",t},{"builder",trim(z)}});placed=f.ladders();if(!placed.empty()){first=t;break;}}
  const bool belt=std::string(kind)=="传送带僵尸";J result={{"birth",born},{"first_entry_500",entered},{"charmed_at",charmed_at},{"first_placement",first},{"placed",placed},{"last",trim(f.get(id))},{"commands",f.commands},{"trail",trail}};
  // Preserve all failure trajectories so a normal-entry failure is reviewable.
  std::ofstream(u8p(std::string(argv[1])+"."+kind+"."+mode+".json"))<<result.dump(2);
  if(charm)require(charmed_at>=0,"actual Hypnoshroom bite never charmed builder");require(first>=0,"normal-entry builder never placed terrain; see trajectory sidecar");for(const auto& p:placed)require(p.at("belt")==belt,"wrong facility marker");return result;
 });
 test("Room_start_pve_day10_unmodified_pool",[&]()->J{
  Fixture f(true);J first=J::object(),trail=J::array(),placed=J::array(),births=J::array();int convey_count=0;std::set<std::string> seen;int elapsed=0,retired=0;
  for(int t=0;t<3600;++t){f.step();elapsed=t+1;for(auto z:f.zombies()){const auto id=z.value("_pvp_id",std::string{});if(seen.insert(id).second)births.push_back({{"tick",t},{"unit",trim(z)}});if(z.value("_pvp_card",std::string{})=="zombie:传送带僵尸"){if(first.empty()){first=trim(z);++convey_count;}if(t%30==0)trail.push_back({{"tick",t},{"builder",trim(z)}});}else if(!z.contains("_pvp_grave")&&z.value("血量",0.)>0.){setitem(rd(getattr(f.b,SY("_native_objects")),V(id)),SV("血量"),V(0));++retired;}}
   placed=f.ladders();if(std::any_of(placed.begin(),placed.end(),[](const J&p){return p.value("belt",false);}))break;}
  J result={{"day",10},{"seed",742},{"room_steps",elapsed},{"naturally_observed_conveyors",convey_count},{"first_conveyor",first},{"placed",placed},{"trail",trail},{"births",births},{"background_units_retired_by_fixture",retired},{"scope","Unmodified actual day10 pool/RNG/plan; non-conveyor background bodies retired by HP0 fixture to permit later waves, builders untouched"}};std::ofstream(std::string(argv[1])+".natural-coop.json")<<result.dump(2);require(convey_count>0,"unmodified day10 wave did not sample conveyor within bounded window; coverage not achieved");require(std::any_of(placed.begin(),placed.end(),[](const J&p){return p.value("belt",false);}),"natural co-op conveyor never placed belt; see sidecar");return result;
 });
 test("Session_actual_director_spawn_single_conveyor",[&]()->J{
  auto h=battle_from_scenario({{"seed",742},{"fixture_flat",true},{"mode","coop"},{"durable_heroes",true},{"director",{{"day",10},{"seed",742}}}});auto cold=typed72app::export_cold(h.battle,742);auto& d=cold.cold.at("director");
  J selected;for(const auto& e:d.at("pool"))if(e.at(0)=="zombie:传送带僵尸")selected=e;require(!selected.is_null(),"actual day10 pool lacks conveyor");d["pool"]=J::array({selected});d["points"]=J::array({J::array({1992.,960.})});d["plan"]=J::array({J{{"time",0.},{"budget",225},{"flag",false}}});d["next_wave"]=0;
  auto b=typed72app::Session::create(std::move(cold),"isolated production director path");for(int y=16;y<20;++y)for(int x=42;x<48;++x)b->fixture_ditu(y,x,{{"方块","土"},{"里方块","空"}});for(const char* seat:{"plant","plant2"})b->fixture_set_avatar(seat,{{"玩家位置",{2184,768,0,0}},{"玩家血量",1.e8}});
  J birth,trail=J::array(),placed=J::array();std::string id;int first=-1;
  for(int t=0;t<600;++t){b->step();const auto view=b->native_view();for(auto z:view.at("g").at("僵尸"))if(z.value("_pvp_card",std::string{})=="zombie:传送带僵尸"){if(id.empty()){id=z.at("_pvp_id");birth=trim(z);}if(t%15==0)trail.push_back({{"tick",t},{"unit",trim(z)}});}const auto tiles=b->map_tiles();for(size_t y=0;y<tiles.size();++y)for(size_t x=0;x<tiles[y].size();++x)if(tiles[y][x].value("kind",std::string{})=="梯子块")placed.push_back({{"row",y},{"col",x},{"belt",tiles[y][x].at("native").value("_pvp_belt",false)}});if(!placed.empty()){first=t;break;}}
  J result={{"birth",birth},{"first_placement",first},{"placed",placed},{"trail",trail},{"scope","Actual day10 exported director; single-entry test pool and zero-time one-unit plan, natural ColdAdmission entry untouched; not a random campaign coverage claim"}};std::ofstream(std::string(argv[1])+".isolated-director.json")<<result.dump(2);callm(h.battle,SY("close"),Args{});require(first>=0,"isolated production director conveyor never placed terrain");for(const auto&p:placed)require(p.value("belt",false),"director conveyor produced ordinary ladder");return result;
 });
 std::ofstream(argv[1])<<J{{"passed",failures==0},{"failures",failures},{"cases",cases},{"scope","Real Room command and _start_pve; no native entry500/placement override on tested builders; heroes/terrain/start funds are controlled fixture. Actual Hypnoshroom conversion. No production changes."}}.dump(2);return failures?1:0;
}
