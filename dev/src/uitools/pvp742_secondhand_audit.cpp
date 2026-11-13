#include "pg/pg.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "sim/typed/zombie_secret_runtime.h"
#include "ui/gen/pm_world_view.h"
#include "ui/gen/pm_native_style.h"
#include "ui/hand/texture74_internal.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <fstream>
#include <iostream>
using namespace pvz;using J=nlohmann::json;
namespace {
void require(bool ok,const std::string& s){if(!ok)throw std::runtime_error(s);}
V value(const J& j){return py::json_loads(V(j.dump()));}
struct Fixture {
 BattleHandle h;std::unique_ptr<typed72app::Session> b;V art,world;
 Fixture():h(battle_from_scenario({{"seed",742},{"fixture_flat",true},{"durable_heroes",true},{"rules",{{"plant_slots",8},{"zombie_slots",32}}},
  {"decks",{{"plant",{"plant:向日葵","plant:樱桃炸弹","plant:坚果","plant:豌豆射手"}},
   {"zombie",{"zombie:脑光墓碑","zombie:普通僵尸","zombie:路障僵尸","zombie:铁桶僵尸","zombie:黑路障僵尸","zombie:黑铁桶僵尸","zombie:橄榄球僵尸","zombie:黑橄榄僵尸","zombie:角斗士巨人","zombie:钢门普通僵尸","zombie:垃圾桶僵尸","zombie:梯子僵尸","zombie:传送带僵尸","zombie:报纸僵尸","zombie:吸金磁僵尸","zsecret:二手"}}}}})){
  b=typed72app::Session::create(typed72app::export_cold(h.battle,742),"secondhand production audit");
  for(const char* side:{"plant","zombie"})b->fixture_set_avatar(side,{{"玩家位置",{3400,96,0,0}},{"玩家血量",1.e8},{"_pvp_butter",1.e8}});
  world=pm_world_view::new_WorldView(Args{pg::pygame_module(),h.bridge});art=getattr(world,SY("art"));
 }
 ~Fixture(){try{callm(h.battle,SY("close"),Args{});}catch(...){} }
 std::string spawn(const std::string& card,double x=1752,double y=960){const auto id=b->spawn(card,card.rfind("plant:",0)==0?"plant":"zombie",x,y,1,false);require(bool(id),"spawn failed "+card);return *id;}
 std::string zombie(const std::string& card,double x=1752){const auto id=spawn(card,x);b->fixture_place_zombie(id,x,960,1);b->native_set(false,id,{{"血量",1.e8},{"_pvp_max_hp",1.e8},{"出场",500.},{"黄油",1.e8}});return id;}
 J native(const std::string& id){const auto view=b->native_view();for(const auto& z:view["g"]["僵尸"])if(z.value("_pvp_id",std::string{})==id)return z;throw std::runtime_error("missing native unit "+id);}
 J unit(const std::string& id){const auto snapshot=b->snapshot(false);for(const auto& z:snapshot["units"])if(z["id"]==id)return z;throw std::runtime_error("missing public unit "+id);}
 J pickups(){return b->snapshot(false).value("zsecrets",J::object()).value("pickups",J::array());}
 J break_piece(const std::string& source,bool head,bool set_max=true){
  auto state=native(source);double top=head?unit(source)["armor_max"].get<double>():state.value("_pvp_zs_hand_max",state.value("手持血量",0.));if(top<=0.)top=state.value(head?"防具血量":"手持血量",0.);require(top>0.,"piece has no original durability: "+state.dump());
  J fields=head?J{{"防具血量",1.}}:J{{"手持血量",1.}};if(set_max)fields[head?"_pvp_armor_max":"_pvp_zs_hand_max"]=top;b->native_set(false,source,fields);
  const auto p=state["位置"];std::string attacker;
  if(head)spawn("plant:樱桃炸弹",p[0],p[1]);
  else{
   // Cherry ash damage intentionally bypasses hand pieces. Use the unchanged
   // front-facing pea surface-hit path for legal steel/ladder/newspaper breaks.
   b->fixture_place_zombie(source,p[0],p[1],-1.);attacker=spawn("plant:豌豆射手",p[0].get<double>()-144.,p[1]);b->native_set(false,attacker,{{"射",0.},{"射cd",0.}});
  }
  for(int tick=0;tick<180;++tick){b->step();if(!pickups().empty()){J item=pickups().back();item["expected_hp"]=top/2.;item["original_top"]=top;item["break_room_tick"]=b->tick();item["real_damage_path"]=head?"cherry ash to ordinary head damage":"front-facing pea surface hit";if(!attacker.empty()){b->native_set(false,attacker,{{"植物血",0.}});b->step();}return item;}}
  throw std::runtime_error("real legal hit did not leave secondhand item: "+native(source).dump());
 }
 void move(const std::string& id,double x,double y=960){require(b->fixture_place_zombie(id,x,y,1),"move fixture rejected");}
 void take(const std::string& id,const J& item){move(id,item["x"],item["y"]);b->step();require(pickups().empty(),"pickup did not disappear after eligible wearer arrived");}
 J visible(const J& item){
  V raw=callm(art,SY("raw"),Args{V(item["asset"].get<std::string>())});require(!raw.is_none(),"pickup has no actual raster: "+item.dump());V bounds=callm(raw,SY("get_bounding_rect"),Args{});require(getattr(bounds,SY("width")).num()>0&&getattr(bounds,SY("height")).num()>0,"pickup raster is fully transparent: "+item.dump());
  J battle=b->snapshot();battle["players"]["plant"]["x"]=item["x"];battle["players"]["plant"]["y"]=item["y"];battle["players"]["plant"]["hp"]=1.e8;J without=battle;without["zsecrets"]["pickups"]=J::array();
  V a=pg::new_surface(1280,720,true),c=pg::new_surface(1280,720,true),rect=callm(pg::pygame_module(),SY("Rect"),Args{V(0),V(0),V(1280),V(720)});V terrain=getattr(h.battle,SY("map"));
  callm(world,SY("render"),Args{a,value(battle),rect,V("plant"),V::dict(),terrain});callm(world,SY("render"),Args{c,value(without),rect,V("plant"),V::dict(),terrain});
  const auto left=texture74::pixels(a),right=texture74::pixels(c);size_t changed=0;for(size_t p=0;p+3<left.size();p+=4)if(left[p]!=right[p]||left[p+1]!=right[p+1]||left[p+2]!=right[p+2]||left[p+3]!=right[p+3])++changed;
  require(changed>0,"actual WorldView rendered no visible pickup pixels: "+item.dump());return {{"asset",item["asset"]},{"raw_bounds",{getattr(bounds,SY("width")).num(),getattr(bounds,SY("height")).num()}},{"different_world_pixels",changed}};
 }
};
}
int main(int argc,char**argv){
 if(argc<2||!std::getenv("PVP_USERDATA"))return 2;SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();J checks=J::array();int failures=0;
 auto test=[&](std::string name,auto fn){J row={{"name",name}};try{row["evidence"]=fn();row["passed"]=true;}catch(const std::exception& e){row["error"]=e.what();row["passed"]=false;++failures;}checks.push_back(row);J brief=row;brief.erase("evidence");std::cerr<<brief.dump()<<std::endl;};
 test("stable_dropper_identity_survives_reused_native_address",[&]()->J{typed72::CombatZombie recycled,same_id_elsewhere;recycled.source.id.set("new-unit");same_id_elsewhere.source.id.set("old-unit");typed72::ZombieSecretPickup item;item.dropper=&recycled;item.dropper_id="old-unit";require(!item.dropped_by(recycled),"reused address was mistaken for original dropper");require(item.dropped_by(same_id_elsewhere),"stable original UID was not excluded");return {{"new_uid_at_same_address_excluded",false},{"original_uid_at_other_address_excluded",true},{"scope","exact identity predicate used by production pickup loop; allocator reuse modeled explicitly"}};});
 for(const char* card:{"路障僵尸","铁桶僵尸","黑路障僵尸","黑铁桶僵尸","橄榄球僵尸","黑橄榄僵尸","角斗士巨人","南瓜头防具"})test(std::string("real_head_break_visible_pickup_")+card,[&]()->J{
  Fixture f;const bool pumpkin=std::string(card)=="南瓜头防具";const auto source=f.zombie(pumpkin?"zombie:普通僵尸":std::string("zombie:")+card),wearer=f.zombie("zombie:普通僵尸",2256);
  if(pumpkin)f.b->native_set(false,source,{{"防具","南瓜头防具"},{"防具血量",800.},{"_pvp_armor_max",800.}});
  const auto item=f.break_piece(source,true);const auto raster=f.visible(item);f.take(wearer,item);const auto worn=f.native(wearer);require(std::abs(worn["防具血量"].get<double>()-item["expected_hp"].get<double>())<1.e-8,"picked head durability differs: "+worn.dump());require(worn["防具"]==item["name"],"head type changed during pickup");if(item["asset"]=="黑路障"||item["asset"]=="黑铁桶")require(worn.value("_pvp_black_armor",std::string{})==(item["asset"]=="黑路障"?"黑路障僵尸":"黑铁桶僵尸"),"black armor marker was lost");return {{"item",item},{"visible",raster},{"wearer",worn}};
 });
 test("occupied_pumpkin_head_is_not_overwritten",[&]()->J{Fixture f;const auto source=f.zombie("zombie:路障僵尸"),wearer=f.zombie("zombie:普通僵尸",2256);f.b->native_set(false,wearer,{{"防具","南瓜头防具"},{"防具血量",800.},{"_pvp_armor_max",800.}});const auto item=f.break_piece(source,true);f.move(wearer,item["x"],item["y"]);f.b->step();const auto worn=f.native(wearer);require(worn["防具"]=="南瓜头防具"&&worn["防具血量"]==800.&&!f.pickups().empty(),"existing nonempty pumpkin slot was replaced: "+worn.dump());return {{"wearer",worn},{"pending_item",f.pickups()}};});
 for(const char* card:{"钢门普通僵尸","垃圾桶僵尸","梯子僵尸","传送带僵尸"})test(std::string("real_hand_break_visible_pickup_")+card,[&]()->J{Fixture f;const auto source=f.zombie(std::string("zombie:")+card),wearer=f.zombie("zombie:普通僵尸",2256);const auto expected=f.native(source)["手持"];const auto item=f.break_piece(source,false);const auto raster=f.visible(item);f.take(wearer,item);const auto worn=f.native(wearer);require(std::abs(worn["手持血量"].get<double>()-item["expected_hp"].get<double>())<1.e-8,"picked hand durability differs");require(worn["手持"]==expected&&worn.value("_pvp_zs_hand_kind",std::string{})==item["name"].get<std::string>(),"hand mechanics/art type changed during pickup");return {{"item",item},{"visible",raster},{"wearer",worn}};});
 test("newspaper_preserves_original_compatible_controller_rule",[&]()->J{Fixture f;const auto source=f.zombie("zombie:报纸僵尸"),ordinary=f.zombie("zombie:普通僵尸",2256);const auto item=f.break_piece(source,false);const auto raster=f.visible(item);f.move(ordinary,item["x"],item["y"]);f.b->step();require(!f.pickups().empty()&&f.native(ordinary)["手持"]=="","ordinary zombie incorrectly acquired newspaper controller");const auto newspaper=f.zombie("zombie:报纸僵尸",2256);f.b->native_set(false,newspaper,{{"手持",""},{"手持血量",0.}});f.take(newspaper,item);require(f.native(newspaper)["手持"]=="报纸","newspaper-compatible empty slot could not pick it up");return {{"item",item},{"visible",raster},{"wearer",f.native(newspaper)}};});
 test("secondhand_piece_does_not_drop_again",[&]()->J{Fixture f;const auto source=f.zombie("zombie:路障僵尸"),wearer=f.zombie("zombie:普通僵尸",2256);const auto item=f.break_piece(source,true);f.take(wearer,item);auto drops=[&]{size_t n=0;for(size_t i=0;i<f.b->log_size();++i)if(f.b->log_entry(i).value("event",std::string{})=="zsecret_armor_drop")++n;return n;};const auto before=drops();f.b->native_set(false,wearer,{{"防具血量",1.}});const auto state=f.native(wearer);f.spawn("plant:樱桃炸弹",state["位置"][0],state["位置"][1]);for(int tick=0;tick<90;++tick)f.b->step();require(f.native(wearer)["防具血量"].get<double>()<=0.,"second hit did not break secondhand armor");require(f.pickups().empty()&&drops()==before,"secondhand armor generated a third copy");return {{"first_drop_events",before},{"final_drop_events",drops()},{"wearer",f.native(wearer)}};});
 test("gifted_bucket_retains_original_max_for_secondhand_half_durability",[&]()->J{Fixture f;const auto source=f.zombie("zombie:普通僵尸");const auto magnet=f.spawn("zombie:吸金磁僵尸",1536);f.b->fixture_place_zombie(magnet,1536,960,1);f.b->native_set(false,magnet,{{"出场",500.},{"__pvz_sb_gold_magnet_zombie_cd",0.}});for(int i=0;i<2;++i)f.b->step();const auto gifted=f.native(source);require(gifted["防具"]=="铁桶"&&gifted["防具血量"]==250.,"real gold magnet did not gift the target");const auto wearer=f.zombie("zombie:普通僵尸",2256);const auto item=f.break_piece(source,true,false);f.take(wearer,item);const auto worn=f.native(wearer);require(std::abs(worn["防具血量"].get<double>()-125.)<1.e-8,"gifted armor's max fell back to last-hit remaining HP: "+worn.dump());return {{"gifted",gifted},{"item",item},{"wearer",worn}};});
 test("natural_thrown_black_bucket_imp_break_effect_drop_and_pickup",[&]()->J{Fixture f;const auto giant=f.zombie("zombie:角斗士巨人");const auto before=f.native(giant);f.b->native_set(false,giant,{{"血量",before["半血"]},{"黄油",0.}});std::string imp;for(int i=0;i<8&&imp.empty();++i){f.b->step();const auto view=f.b->native_view();for(const auto& z:view["g"]["僵尸"])if(z.value("_pvp_card",std::string{})=="zombie:小鬼僵尸")imp=z["_pvp_id"].get<std::string>();}require(!imp.empty(),"actual gladiator did not throw imp");const auto inherited=f.native(imp);require(inherited["防具"]=="铁桶"&&inherited["防具血量"]==375.&&inherited.value("_pvp_black_armor",std::string{})=="黑铁桶僵尸","thrown black armor contract lost");f.move(giant,2256);f.b->native_set(false,giant,{{"黄油",1.e8}});f.move(imp,1752);f.b->native_set(false,imp,{{"血量",1.e8},{"_pvp_max_hp",1.e8},{"出场",500.},{"黄油",1.e8}});
  const auto nut=f.spawn("plant:坚果",1800),enemy=f.zombie("zombie:普通僵尸",1824),wearer=f.zombie("zombie:普通僵尸",2448);f.b->native_set(false,enemy,{{"魅惑",1.}});const auto item=f.break_piece(imp,true);require(item["asset"]=="黑铁桶","thrown imp drop lost black art");const auto raster=f.visible(item);bool asleep=false;const auto view=f.b->native_view();for(const auto& p:view["g"]["植物"])if(p.value("_pvp_id",std::string{})==nut)asleep=p.contains("睡觉");require(asleep&&f.native(enemy).value("眩晕",0.)>1000.,"legitimate black bucket break lost sleep/stun effect");f.take(wearer,item);const auto worn=f.native(wearer);require(worn["防具血量"]==187.5&&worn.value("_pvp_black_armor",std::string{})=="黑铁桶僵尸","natural imp armor was not dropped/picked with half durability and black identity");return {{"inherited",inherited},{"item",item},{"visible",raster},{"enemy_stun",f.native(enemy).value("眩晕",0.)},{"plant_sleep",asleep},{"wearer",worn}};
 });
 for(const char* kind:{"梯子僵尸","传送带僵尸"})test(std::string("ordinary_wearer_automatically_builds_")+kind,[&]()->J{
  Fixture f;const auto source=f.zombie(std::string("zombie:")+kind),wearer=f.zombie("zombie:普通僵尸",2256);const auto item=f.break_piece(source,false);f.take(wearer,item);f.b->native_set(false,source,{{"血量",0.}});f.b->step();
  f.b->fixture_set_avatar("plant",{{"玩家位置",{2184,768,0,0}},{"玩家血量",1.e8}});f.b->fixture_set_avatar("zombie",{{"玩家位置",{2880,960,0,0}},{"玩家血量",1.e8}});
  for(int y=16;y<20;++y)for(int x=42;x<48;++x)f.b->fixture_ditu(y,x,{{"方块","土"},{"里方块","空"}});f.move(wearer,1992,960);f.b->native_set(false,wearer,{{"黄油",0.},{"跳跃cd",0.}});require(f.b->command("zombie",{{"type","command"},{"seq",1}}).empty(),"attack mode rejected");
  J placed=J::array();int first=-1;for(int tick=0;tick<300;++tick){f.b->step();const auto terrain=f.b->map_tiles();for(size_t y=0;y<terrain.size();++y)for(size_t x=0;x<terrain[y].size();++x)if(terrain[y][x].value("kind",std::string{})=="梯子块")placed.push_back({{"row",y},{"col",x},{"belt",terrain[y][x].at("native").value("_pvp_belt",false)}});if(!placed.empty()){first=tick;break;}}
  require(!placed.empty(),"ordinary pickup wearer did not build: "+f.native(wearer).dump());const bool belt=std::string(kind)=="传送带僵尸";for(const auto& cell:placed)require(cell["belt"].get<bool>()==belt,"inherited conveyor/ladder functionality differs");return {{"item",item},{"wearer",f.native(wearer)},{"first_build_tick_after_move",first},{"placed",placed}};
 });
 std::ofstream(argv[1])<<J{{"passed",failures==0},{"failures",failures},{"checks",checks},{"scope","Real Session: cherry head damage or front-facing pea surface hit breaks a one-HP piece while preserving its original max; no direct drop/pickup helper calls. Actual WorldView pixel comparison checks visibility. Taker is a normal zombie; native path/motion must place the inherited ladder/conveyor. One separate identity-predicate test explicitly models pointer reuse."}}.dump(2);return failures?1:0;
}
