#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/typed_battle.h"
#include "ui/gen/pm_world_view.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <filesystem>
#include <fstream>
#include <iostream>
using namespace pvz;using J=nlohmann::json;
V val(const J& j){return py::stdlib_call(SV("json.loads"),Args{V(j.dump())});}
J snapshot(V b){return J::parse(py_str(py::stdlib_call(SV("json.dumps"),Args{callm(b,SY("snapshot"),Args({},{{SY("include_map"),V(true)}}))})));}
int main(int argc,char**argv){if(argc!=2)return 2;const auto out=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(out);SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();V pg=py::stdlib_module(SV("pygame"));V screen=callm(getattr(pg,SY("display")),SY("set_mode"),Args{V::tuple({V(1280),V(640)})});J rows=J::array();int failures=0;
 auto capture=[&](const std::string& name,const J& state,V bridge,double cx=2136.,double cy=800.,double zoom=1.5){V w=pm_world_view::new_WorldView(Args{pg,bridge});callm(w,SY("render"),Args{screen,val(state),V::tuple({V(0),V(0),V(1280),V(640)}),SV("plant"),val({{"zoom",zoom},{"world_quality","native"},{"replay_camera",{cx,cy}}}),V::none(),V(true)});if(getattr(w,SY("native_error")).truthy())throw std::runtime_error(py_str(getattr(w,SY("native_error"))));callm(getattr(pg,SY("image")),SY("save"),Args{screen,V(p8(out/u8p(name+".png")))});std::ofstream(out/u8p(name+".json"))<<state.dump();};
 auto test=[&](const std::string& name,auto fn){J r={{"name",name}};try{r["evidence"]=fn();r["passed"]=true;}catch(const std::exception&e){r["passed"]=false;r["error"]=e.what();++failures;}rows.push_back(r);std::cerr<<r.dump()<<std::endl;};
 for(const auto* kind:{"原始豌豆射手","甜椒投手","回旋镖射手","三向射手"})test(std::string("copy_")+kind,[&]()->J{
  std::string key=std::string("plant:")+kind;J sc={{"seed",3},{"clear_cooldowns",true},{"durable_heroes",true},{"rules",{{"plant_start",3000},{"night_plant_start",3000}}}};sc["decks"]={{"plant",{key,"plant:模仿者","plant:向日葵","secret:肆意模仿"}},{"zombie",{"zombie:普通僵尸","zombie:脑光墓碑"}}};auto h=battle_from_scenario(sc);V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);callm(b,SY("spawn"),Args{V(key),SV("plant"),V(2088.),V(864.),V(1.)});V e=callm(b,SY("command_input"),Args{SV("plant"),val({{"type","deploy"},{"seq",1},{"card","plant:模仿者"},{"copy",key},{"x",2136.},{"y",840.}})});if(e.truthy())throw std::runtime_error(py_str(e));J state;std::string copy_id;
  for(int t=0;t<250&&copy_id.empty();++t){callm(b,SY("step"),Args{});state=snapshot(b);for(const auto& u:state["units"])if(u["card_id"]==key&&u.value("temporary",false))copy_id=u["id"].get<std::string>();}
  if(copy_id.empty())throw std::runtime_error("copy did not transform");callm(b,SY("step"),Args{V(2)});state=snapshot(b);const auto art=state["native_frame"]["commands"].dump();
  capture(std::string("copy-")+kind,state,h.bridge,2112.,800.,2.);
  const std::string expected=std::string(kind)+(std::string(kind)=="三向射手"?"头":"")+"-黑白";
  if(art.find(expected)==std::string::npos)throw std::runtime_error("copied artwork missing "+expected);callm(b,SY("close"),Args{});return {{"copy_id",copy_id},{"gray",true},{"card_id",key}};
 });
 test("asparagus_barrage",[&]()->J{auto h=battle_from_scenario({{"seed",3},{"durable_heroes",true}});V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);callm(b,SY("spawn"),Args{SV("plant:芦笋战机"),SV("plant"),V(2136.),V(864.),V(1.)});V z=callm(b,SY("spawn"),Args{SV("zombie:普通僵尸"),SV("zombie"),V(2650.),V(864.),V(-1.)});V raw=rd(getattr(b,SY("_native_objects")),rd(z,SV("id")));setitem(raw,SV("出场"),V(500.));setitem(raw,SV("血量"),V(100000.));setitem(raw,SV("黄油"),V(100000.));J state;bool found=false;int tick=0;for(;tick<900&&!found;++tick){callm(b,SY("step"),Args{});state=snapshot(b);found=state["native_frame"]["commands"].dump().find("芦笋线弹")!=std::string::npos;}if(!found)throw std::runtime_error("no flying projectile draw commands");capture("asparagus-barrage",state,h.bridge,2300.,760.,1.5);callm(b,SY("close"),Args{});return {{"first_visible_room_tick",tick}};});
 test("dropped_armour",[&]()->J{auto h=battle_from_scenario({{"seed",3}});V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);J s=snapshot(b);s["native_frame"]["commands"]=J::array();s["zsecrets"]["pickups"]=J::array();int i=0;for(const auto* name:{"路障","铁桶","黑路障","黑铁桶","橄榄球头盔","黑橄榄球头盔","南瓜头防具","钢门","垃圾桶","梯子","传送带"})s["zsecrets"]["pickups"].push_back({{"id","zs"+std::to_string(++i)},{"name",name},{"asset",name},{"x",1800.+i*60.},{"y",864.}});capture("dropped-armour",s,h.bridge,2160.,800.,1.5);callm(b,SY("close"),Args{});return {{"pieces",i}};});
 for(const auto* count:{"one","three"})test(std::string("grabber_")+count,[&]()->J{auto h=battle_from_scenario({{"seed",3}});std::ifstream f("test_results/pvp73/r3-hotfix-audit.json."+std::string(count)+".json");J s=J::parse(f);capture(std::string("grabber-")+count,s,h.bridge,2200.,780.,1.5);callm(h.battle,SY("close"),Args{});return {{"rendered",true}};});
 std::ofstream(out/"summary.json")<<J{{"passed",failures==0},{"failures",failures},{"checks",rows}}.dump(2);return failures?1:0;
}
