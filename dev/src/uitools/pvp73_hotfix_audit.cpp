#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/typed_battle.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "sim/pvp/gen/pm_maps.h"
#include "ui/gen/pm_native_style.h"
#include "ui/gen/pm_replay.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
using namespace pvz;using J=nlohmann::json;
J json(const V& v){return J::parse(py_str(py::stdlib_call(SV("json.dumps"),Args{v})));}
V value(const J& j){return py::stdlib_call(SV("json.loads"),Args{V(j.dump())});}
J snap(const V& b){return json(callm(b,SY("snapshot"),Args({},{{SY("include_map"),V(true)}})));}
void require(bool ok,const std::string& message){if(!ok)throw std::runtime_error(message);}
int main(int argc,char**argv){
 if(argc!=2)return 2;SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 J report=J::array();int failures=0;auto test=[&](std::string name,auto fn){J r={{"name",name}};try{r["evidence"]=fn();r["passed"]=true;}catch(const std::exception&e){r["passed"]=false;r["error"]=e.what();++failures;}report.push_back(r);std::cerr<<r.dump()<<std::endl;};
 for(bool focused:{false,true})for(double hp:{300.,151.,150.,149.})test(std::string(focused?"garlic_focused_":"garlic_")+std::to_string(int(hp)),[&]()->J{
  J sc={{"seed",3},{"durable_heroes",true}};
  sc["decks"]={{"plant",{"plant:大蒜","plant:向日葵"}},{"zombie",{"zombie:普通僵尸","zombie:脑光墓碑"}}};if(focused)sc["decks"]["zombie"].push_back("zsecret:专注啃咬");
  auto h=battle_from_scenario(sc);
  V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);
  callm(b,SY("spawn"),Args{SV("plant:大蒜"),SV("plant"),V(2136.),V(864.),V(1.)});
  V zu=callm(b,SY("spawn"),Args{SV("zombie:墓碑吞噬者僵尸"),SV("zombie"),V(2088.),V(864.),V(1.)});
  const V zid=rd(zu,SV("id"));callm(b,SY("fixture_place_zombie"),Args{zid,V::list({V(2088.),V(864.)}),V(1.)});
  V z=rd(getattr(b,SY("_native_objects")),zid);setitem(z,SV("血量"),V(hp));setitem(z,SV("出场"),V(500.));
  if(focused){setitem(z,SV("黄油"),V(2000.));for(int t=0;t<180;++t)callm(b,SY("step"),Args{});z=rd(getattr(b,SY("_native_objects")),zid);setitem(z,SV("黄油"),V(0.));}
  double before=-1,after=-1;J drops=J::array();
  for(int t=0;t<450;++t){auto s=snap(b);bool exists=false;for(const auto& p:s["units"])if(p.value("card_id",std::string{})=="plant:大蒜"){exists=true;double now=p["hp"];if(before<0)before=now;else if(now!=after&&now<before)drops.push_back({{"tick",t},{"hp",now}});after=now;}if(!exists&&before>=0)after=0.;if(after>=0&&after<before){std::ofstream(std::string(argv[1])+".garlic"+std::to_string(int(hp))+".json")<<s.dump();break;}callm(b,SY("step"),Args{});}require(before>=0,"garlic not spawned");
  std::ofstream(std::string(argv[1])+".garlic-final"+std::to_string(int(hp))+".json")<<snap(b).dump();callm(b,SY("close"),Args{});double damage=before-after;require(damage==(hp>150.?3.:6.)*(focused?2.:1.),"garlic damage "+std::to_string(damage));return {{"attacker_hp",hp},{"focused",focused},{"before",before},{"after",after},{"single_contact_damage",damage},{"changes",drops}};
 });
 for(double hp:{300.,150.})test("charmed_bite_"+std::to_string(int(hp)),[&]()->J{
  auto h=battle_from_scenario({{"seed",3},{"night",true},{"durable_heroes",true}});V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);
  callm(b,SY("spawn"),Args{SV("plant:魅惑菇"),SV("plant"),V(2136.),V(864.),V(1.)});
  V attacker=callm(b,SY("spawn"),Args{SV("zombie:墓碑吞噬者僵尸"),SV("zombie"),V(2088.),V(864.),V(1.)});
  V a=rd(getattr(b,SY("_native_objects")),rd(attacker,SV("id")));setitem(a,SV("出场"),V(500.));setitem(a,SV("血量"),V(hp));
  bool charmed=false;for(int n=0;n<200&&!charmed;++n){callm(b,SY("step"),Args{});V rec=rd(getattr(b,SY("_native_objects")),rd(attacker,SV("id")));charmed=py::in(SV("魅惑"),rec);}
  require(charmed,"gravebuster did not eat the hypno-shroom");for(int n=0;n<35;++n)callm(b,SY("step"),Args{});
  callm(b,SY("fixture_place_zombie"),Args{rd(attacker,SV("id")),V::list({V(2136.),V(864.)}),V(1.)});a=rd(getattr(b,SY("_native_objects")),rd(attacker,SV("id")));setitem(a,SV("啃咬"),V(0.));
  V target=callm(b,SY("spawn"),Args{SV("zombie:普通僵尸"),SV("zombie"),V(2150.),V(864.),V(-1.)});
  V o=rd(getattr(b,SY("_native_objects")),rd(target,SV("id")));setitem(o,SV("出场"),V(500.));setitem(o,SV("血量"),V(1000.));double after=1000.;
  for(int n=0;n<100&&after==1000.;++n){callm(b,SY("step"),Args{});const auto state=snap(b);for(const auto& u:state["units"])if(u["id"]==py_str(rd(target,SV("id"))))after=u["hp"];}
  callm(b,SY("close"),Args{});double damage=1000.-after;require(damage==(hp>150.?30.:60.),"charmed bite "+std::to_string(damage));return {{"attacker_hp",hp},{"zombie_damage",damage}};
 });
 test("subsidy_opening",[&]()->J{J amounts=J::array();for(bool enabled:{false,true}){J sc={{"seed",7}};sc["decks"]={{"plant",{"plant:向日葵","plant:豌豆射手"}},{"zombie",{"zombie:普通僵尸","zombie:脑光墓碑"}}};if(enabled)sc["decks"]["zombie"].push_back("zsecret:补贴");auto h=battle_from_scenario(sc);V b=typed72app::wrap_battle(h.battle);auto s=snap(b);amounts.push_back(s["players"]["zombie"]["resource"]);callm(b,SY("close"),Args{});}require(amounts[0]==amounts[1],"opening resources differ");return amounts;});
 for(bool tentacles:{false,true})test(tentacles?"imitated_grabber_three_heads":"imitated_grabber_one_head",[&]()->J{
  J sc={{"seed",3},{"durable_heroes",true},{"clear_cooldowns",true},{"rules",{{"plant_start",3000},{"night_plant_start",3000}}}};sc["decks"]={{"plant",{"plant:模仿者","plant:抓人草","plant:向日葵","plant:豌豆射手","secret:肆意模仿"}},{"zombie",{"zombie:普通僵尸","zombie:脑光墓碑"}}};if(tentacles)sc["decks"]["plant"].push_back("secret:触手");
  auto h=battle_from_scenario(sc);V b=typed72app::wrap_battle(h.battle);V e=callm(b,SY("command_input"),Args{SV("plant"),value({{"type","deploy"},{"seq",1},{"card","plant:模仿者"},{"copy","plant:抓人草"},{"x",2136.},{"y",840.}})});require(!e.truthy(),py_str(e));
  for(int t=0;t<2700;++t)callm(b,SY("step"),Args{});auto s=snap(b);int roots=0,heads=0;for(const auto& u:s["units"]){if(u.value("card_id",std::string{})=="plant:抓人草")++roots;if(u.value("card_id",std::string{})=="plant:抓人草触手")++heads;}
  std::ofstream(std::string(argv[1])+"."+(tentacles?"three":"one")+".json")<<s.dump();callm(b,SY("close"),Args{});require(roots==1&&heads==(tentacles?3:1),"roots="+std::to_string(roots)+" heads="+std::to_string(heads));return {{"roots",roots},{"heads",heads},{"ticks",2700}};
 });
 test("replay_speed_seek_and_corruption",[&]()->J{
  J decks={{"plant",{"plant:向日葵","plant:豌豆射手"}},{"zombie",{"zombie:脑光墓碑","zombie:普通僵尸"}}};
  auto h=battle_from_scenario({{"seed",301},{"decks",decks}});V b=typed72app::wrap_battle(h.battle);
  V terrain=callm(pm_maps::f_build_snapshot(Args{h.bridge,SV("家院"),V(301)}),SY("to_dict"),Args{});
  V rec=pm_replay::new_Recording(Args{b,V(301),value(decks),V::list(),terrain});
  for(int t=0;t<1800;){int count=std::min(7,1800-t);if(t>200&&t<220)callm(b,SY("command_input"),Args{SV("plant"),value({{"type","deploy"},{"card","plant:向日葵"},{"seq",t},{"x",2136.},{"y",840.}})});callm(b,SY("step"),Args{V(count)});t+=count;if(t%11==0)(void)snap(b);}
  const auto path=std::string(argv[1])+".replay.json";callm(rec,SY("export"),Args{V(path)});callm(b,SY("close"),Args{});
  V data=pm_replay::f_read_recording(Args{V(path)});V p=pm_replay::new_Playback(Args{data,h.bridge});J seeks=J::array();
  for(int target:{700,120,1500,0,901,350,1799,299,1800}){setattr(p,SY("speed"),V(8.));callm(p,SY("seek"),Args{V(target)});for(int n=0;n<1000&&!getattr(p,SY("target")).is_none()&&!getattr(p,SY("error")).truthy();++n)callm(p,SY("update"),Args({V(.12)},{{SY("max_steps"),V(37)},{SY("budget"),V(1.)}}));require(!getattr(p,SY("error")).truthy(),py_str(getattr(p,SY("error"))));require(getattr(getattr(p,SY("battle")),SY("tick")).num()==target,"seek target missed");seeks.push_back(target);}
  require(getattr(p,SY("verified")).truthy(),"final replay hash not verified");callm(p,SY("close"),Args{});
  V bad=py::stdlib_call(SV("copy.deepcopy"),Args{data});for(const V& op:rd(bad,SV("operations")).items())if(rd(op,SV("kind"))==SV("check")){wr(op,SV("sha256"))=V(std::string(64,'0'));break;}
  p=pm_replay::new_Playback(Args{bad,h.bridge});callm(p,SY("seek"),Args{V(1800)});for(int n=0;n<100&&!getattr(p,SY("error")).truthy();++n)callm(p,SY("update"),Args({V(0.)},{{SY("max_steps"),V(1000)},{SY("budget"),V(1.)}}));require(getattr(p,SY("error")).truthy(),"corrupt recording accepted");callm(p,SY("close"),Args{});return {{"seek_targets",seeks},{"speed",8},{"all_checks_and_final_verified",true},{"corruption_rejected",true}};
 });
 test("armour_visible_bounds",[&]()->J{auto h=battle_from_scenario({{"seed",3}});V pg=py::stdlib_module(SV("pygame"));callm(getattr(pg,SY("display")),SY("set_mode"),Args{V::tuple({V(640),V(480)})});V art=pm_native_style::new_NativeArt(Args{pg,h.bridge});J rows=J::array();for(const auto* name:{"路障","铁桶","黑路障","黑铁桶","橄榄球头盔","黑橄榄球头盔","南瓜头防具","钢门","垃圾桶","梯子","传送带"}){V image=callm(art,SY("raw"),Args{V(name)});require(!image.is_none(),std::string("missing armour ")+name);V box=callm(image,SY("get_bounding_rect"),Args{});int w=int(getattr(box,SY("width")).num()),ht=int(getattr(box,SY("height")).num());require(w>0&&ht>0,std::string("transparent armour ")+name);rows.push_back({{"asset",name},{"bounds",{w,ht}}});}callm(h.battle,SY("close"),Args{});return rows;});
 std::ofstream(argv[1])<<J{{"passed",failures==0},{"failures",failures},{"checks",report}}.dump(2);return failures?1:0;
}
