#include "pg/pg.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "ui/gen/pm_app.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <fstream>
#include <iostream>
using namespace pvz;using J=nlohmann::json;
namespace {
void require(bool b,const std::string& s){if(!b)throw std::runtime_error(s);}
struct Fixture {
 BattleHandle h;std::unique_ptr<typed72app::Session> b;
 Fixture(bool secret=true,const std::string& mode="duel"):h(battle_from_scenario({{"seed",742},{"fixture_flat",true},{"mode",mode},
  {"decks",{{"plant",{"plant:坚果","plant:向日葵"}},{"zombie",secret?J{"zombie:脑光墓碑","zombie:普通僵尸","zombie:小丑僵尸","zsecret:自爆"}:J{"zombie:脑光墓碑","zombie:普通僵尸","zombie:小丑僵尸"}}}}})){
  b=typed72app::Session::create(typed72app::export_cold(h.battle,742),"self-destruct actual production audit");
  for(const char* seat:mode=="duo"?std::vector<const char*>{"plant","plant2","zombie","zombie2"}:std::vector<const char*>{"plant","zombie"})b->fixture_set_avatar(seat,{{"玩家位置",{3400,96,0,0}},{"_pvp_butter",1.e8}});
 }
 ~Fixture(){try{callm(h.battle,SY("close"),Args{});}catch(...){} }
 std::string spawn(const std::string& card,const std::string& side,double x,double y=960){const auto id=b->spawn(card,side,x,y,side=="plant"?1:-1,false);require(bool(id),"spawn rejected: "+card);return *id;}
 std::string zombie(double hp,double x=1728,const std::string& seat="zombie",const std::string& card="zombie:普通僵尸"){
  const auto id=spawn(card,seat,x);b->fixture_place_zombie(id,x,960,-1);b->native_set(false,id,{{"出场",500},{"血量",hp},{"_pvp_max_hp",hp},{"黄油",1.e8}});return id;
 }
 std::string plant(double x=1752){const auto id=spawn("plant:坚果","plant",x);b->native_set(false,id,{{"植物血",10000},{"植物血上限",10000}});return id;}
 double hp(const std::string& id){const auto snapshot=b->snapshot(false);for(const auto& u:snapshot["units"])if(u["id"]==id)return u["hp"];return 0.;}
 J blast_events(){J out=J::array();for(size_t i=0;i<b->log_size();++i){const auto e=b->log_entry(i);if(e.value("event",std::string{})=="zsecret_blast")out.push_back(e);}return out;}
 std::string detonate(const std::string& id,const std::string& seat="zombie",int seq=1){return b->command(seat,{{"type","detonate"},{"seq",seq},{"target",id}});}
 std::string deploy_second_seat_source(){
  b->fixture_player("zombie2",{{"resource",10000.}});b->fixture_set_avatar("zombie2",{{"玩家位置",{1728,960,0,0}}});b->sync_public();
  auto error=b->command("zombie2",{{"type","deploy"},{"seq",1},{"card","zombie:脑光墓碑"},{"x",1728.},{"y",960.},{"facing",-1}});require(error.empty(),"second-seat grave deployment: "+error);
  std::string grave;const auto first=b->snapshot(false);for(const auto& u:first["units"])if(u["card_id"]=="zombie:脑光墓碑")grave=u["id"].get<std::string>();require(!grave.empty(),"second-seat grave missing");
  error=b->command("zombie2",{{"type","deploy"},{"seq",2},{"card","zombie:普通僵尸"},{"x",1728.},{"y",960.},{"grave",grave},{"facing",-1}});require(error.empty(),"second-seat zombie deployment: "+error);
  std::string id;const auto second=b->snapshot(false);for(const auto& u:second["units"])if(u["card_id"]=="zombie:普通僵尸"){id=u["id"].get<std::string>();require(u.value("seat",std::string{})=="zombie2","deployment did not retain actual second seat");}require(!id.empty(),"second-seat source missing");b->native_set(false,id,{{"血量",76.},{"出场",500.}});return id;
 }
};
}
int main(int argc,char**argv){
 if(argc<2||!std::getenv("PVP_USERDATA"))return 2;SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 J checks=J::array();int failures=0;auto test=[&](std::string name,auto fn){J row={{"name",name}};try{row["evidence"]=fn();row["passed"]=true;}catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();++failures;}checks.push_back(row);J brief=row;brief.erase("evidence");std::cerr<<brief.dump()<<std::endl;};
 test("current_hp_ceiling_and_real_plant_damage",[&]{J samples=J::array();for(double hp:{1.,25.,25.1,50.,51.,76.,500.}){Fixture f;const auto nut=f.plant(),source=f.zombie(hp);const double before=f.hp(nut);const auto error=f.detonate(source);const double after=f.hp(nut),want=std::ceil(hp/25.);const auto events=f.blast_events();require(error.empty(),"detonate rejected: "+error);require(std::abs(before-after-want)<1.e-8,"plant damage differs: "+J{{"hp",hp},{"before",before},{"after",after},{"want",want},{"events",events}}.dump());require(f.hp(source)<=0.,"source did not die");require(!events.empty()&&events.back()["damage"]==want,"blast event contract differs");require(!f.detonate(source,"zombie",2).empty(),"dead source allowed to repeat explosion");samples.push_back({{"hp",hp},{"damage",before-after},{"expected",want},{"event",events.back()}});}return samples;});
 test("enemy_plants_hero_charmed_tenfold_and_allied_immunity",[&]{Fixture f;const auto nut=f.plant(),far=f.plant(1968),source=f.zombie(76.),friendly=f.zombie(10000.,1776),charmed=f.zombie(10000.,1800);
  f.b->native_set(false,charmed,{{"魅惑",1.}});f.b->fixture_set_avatar("plant",{{"玩家位置",{1728,960,0,0}}});f.b->fixture_set_avatar("zombie",{{"玩家位置",{1728,960,0,0}}});
  const auto before=f.b->players();require(f.detonate(source).empty(),"blast rejected");const auto players=f.b->players();J out={{"plant_damage",10000.-f.hp(nut)},{"outside_plant_damage",10000.-f.hp(far)},{"charmed_damage",10000.-f.hp(charmed)},{"friendly_damage",10000.-f.hp(friendly)},
   {"plant_hero_damage",before["plant"]["hp"].get<double>()-players["plant"]["hp"].get<double>()},{"zombie_hero_damage",before["zombie"]["hp"].get<double>()-players["zombie"]["hp"].get<double>()},{"events",f.blast_events()}};
  require(out["plant_damage"]==4.&&out["charmed_damage"]==40.&&out["plant_hero_damage"]==4.,"enemy damage differs: "+out.dump());require(out["outside_plant_damage"]==0.&&out["friendly_damage"]==0.&&out["zombie_hero_damage"]==0.,"friendly/range contract differs: "+out.dump());return out;});
 test("radius_boundary_and_periodic_seam",[&]{J cases=J::array();for(double offset:{115.1,115.3}){Fixture f;const auto nut=f.plant();const auto source=f.zombie(25.,1752.+offset);require(f.detonate(source).empty(),"boundary detonate rejected");const double damage=10000.-f.hp(nut);require(damage==(offset<115.2?1.:0.),"2.4-tile boundary changed");cases.push_back({{"distance",offset},{"damage",damage}});}Fixture f;const auto nut=f.plant(24.),source=f.zombie(25.,3446.);require(f.detonate(source).empty(),"seam detonate rejected");require(10000.-f.hp(nut)==1.,"periodic seam lost explosion");cases.push_back({{"periodic_width",3456},{"distance",34},{"damage",10000.-f.hp(nut)}});return cases;});
 test("secret_missing_charmed_source_grave_and_teammate_rejected",[&]{J cases=J::array();{Fixture f(false);const auto z=f.zombie(76.);require(!f.detonate(z).empty()&&f.hp(z)>0.,"ordinary zombie detonated without secret");cases.push_back("secret absent rejected");}{Fixture f;const auto z=f.zombie(76.);f.b->native_set(false,z,{{"魅惑",1.}});require(!f.detonate(z).empty()&&f.hp(z)>0.,"charmed source accepted by old owner");cases.push_back("charmed source rejected");}{Fixture f;const auto z=f.spawn("zombie:脑光墓碑","zombie",1728);require(!f.detonate(z).empty()&&f.hp(z)>0.,"grave detonated");cases.push_back("grave rejected");}{Fixture f(true,"duo");const auto z=f.deploy_second_seat_source();require(!f.detonate(z,"zombie").empty()&&f.hp(z)>0.,"teammate source accepted");require(f.detonate(z,"zombie2",3).empty()&&f.hp(z)<=0.,"actual second-seat owner could not detonate");cases.push_back("duo own seat only, real grave and mobile deployment");}return cases;});
 test("ordinary_death_does_not_automatically_fire_manual_secret",[&]{Fixture f;const auto nut=f.plant(),source=f.zombie(76.);f.b->native_set(false,source,{{"血量",0.}});for(int i=0;i<4;++i)f.b->step();require(f.hp(nut)==10000.&&f.blast_events().empty(),"manual secret unexpectedly attached to natural death");return J{{"plant_hp",f.hp(nut)},{"automatic_blasts",f.blast_events().size()},{"description_trigger","click an own living zombie"}};});
 test("production_ui_selects_real_mobile_and_sends_detonate",[&]{Fixture f;const auto nut=f.plant(),source=f.zombie(76.);V pg=pg::pygame_module(),screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(720)})});V app=pm_app::new_Application(Args{pg,screen,f.h.bridge});auto* application=as<pm_app::C_Application>(app);
  J view={{"phase","battle"},{"revision",1},{"members",{{"host","plant"},{"guest","zombie"}}},{"battle",f.b->snapshot(false)},{"map",J::parse(dump(getattr(f.h.battle,SY("map"))))}};application->a_view=py::json_loads(V(view.dump()));application->a_mode=V("guest");application->a_peer_id=V("guest");V sent=V::none();auto wire=std::make_shared<PyObj>();V transport=V::inst(wire);setattr(transport,SY("send"),V::func([&](const Args& a){sent=a.pos.at(0);return V(true);}));application->a_transport=transport;
  V selected=callm(app,SY("detonate_target_at"),Args{V("zombie"),V(1728),V(936),V(3456)});require(!selected.is_none()&&py::m_get(selected,V("id"))==V(source),"real typed snapshot cannot be clicked for self destruct");require(!callm(app,SY("input"),Args({V("zombie"),V("detonate")},{{SY("target"),V(source)}})).truthy(),"real Application rejected self destruct input");
  const J packet=J::parse(dump(sent));require(packet["type"]=="room_command"&&packet["payload"]["type"]=="input"&&packet["payload"]["input"]["type"]=="detonate","UI produced wrong wire envelope");const auto error=f.b->command("zombie",packet["payload"]["input"]);require(error.empty()&&10000.-f.hp(nut)==4.,"UI-to-Session detonate did not hurt plant");application->a_transport=V::none();callm(app,SY("close_room"),Args{});return J{{"selected",source},{"packet",packet},{"plant_damage",10000.-f.hp(nut)}};});
 test("clown_retains_native_detonation_branch",[&]{Fixture f;const auto source=f.zombie(500.,1728,"zombie","zombie:小丑僵尸");f.b->fixture_set_avatar("plant",{{"玩家位置",{1728,960,0,0}}});const double before=f.b->players()["plant"]["hp"];require(f.detonate(source).empty(),"clown detonate rejected");require(f.hp(source)==-299.,"clown was routed through ordinary secret amount");for(int i=0;i<2;++i)f.b->step();const double after=f.b->players()["plant"]["hp"];require(after<before&&f.blast_events().empty(),"native clown explosion lost damage or used ordinary secret");return J{{"hero_damage",before-after},{"ordinary_secret_events",f.blast_events().size()}};});
 J report={{"passed",failures==0},{"failures",failures},{"checks",checks},{"scope","Real production typed Session command(detonate), not a reimplementation of damage. Current almanac and existing regression define manual clicking, not explosion on every natural death. No user game or data touched."}};std::ofstream(argv[1])<<report.dump(2);return failures?1:0;
}
