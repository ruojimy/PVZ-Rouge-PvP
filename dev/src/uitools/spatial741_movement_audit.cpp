#include "pg/pg.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
using namespace pvz;using J=nlohmann::json;
int main(int argc,char**argv){
 if(argc<2)return 2;SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 auto h=battle_from_scenario({{"seed",743},{"fixture_flat",true},{"durable_heroes",true}});const auto cold=typed72app::export_cold(h.battle,743);
 J rows=J::array();int failures=0;
 for(const char* kind:{"梯子僵尸","传送带僵尸","矿工僵尸","潜水僵尸","海豚僵尸","气球僵尸","飞贼僵尸","撑杆跳僵尸","黑撑杆僵尸","蹦蹦僵尸","雪人僵尸","海盗鹦鹉","乌鸦","雪橇车僵尸","投篮车僵尸","小鬼炮","滚桶僵尸","钩索僵尸","稻草人","舞王僵尸","黑橄榄僵尸","红眼巨人","豌豆僵尸"})for(const char* mode:{"attack","follow","rally","charmed"}){
  if(argc>2)continue;
  J row={{"kind",kind},{"mode",mode}};try{
   auto fixture=cold;if(std::string(kind)=="潜水僵尸"||std::string(kind)=="海豚僵尸")fixture.cold["globals"]["水平面"]=17;
   auto b=typed72app::Session::create(std::move(fixture),"性能固定场景");
   b->fixture_set_avatar("plant",{{"玩家位置",{1680,960,0,0}},{"玩家血量",1.e8}});b->fixture_set_avatar("zombie",{{"玩家位置",{2880,960,0,0}},{"玩家血量",1.e8}});
   if(std::string(kind)=="潜水僵尸"||std::string(kind)=="海豚僵尸")for(int y=17;y<20;++y)for(int x=40;x<52;++x)b->fixture_ditu(y,x,{{"方块","水"},{"里方块","空"}});
   else for(int y=18;y<20;++y)b->fixture_ditu(y,42,{{"方块","土"},{"里方块","空"}});
   for(const auto& plant:{std::pair{"plant:坚果",2040.},std::pair{"plant:甜薯",1944.}}){const auto id=b->spawn(plant.first,"plant",plant.second,960,1,false);if(!id)throw std::runtime_error("movement plant fixture rejected");b->native_set(false,*id,{{"植物血",1.e8},{"植物血上限",1.e8}});}
   const auto grave=b->spawn("zombie:脑光墓碑","zombie",2808,960,-1,false);if(!grave)throw std::runtime_error("grave spawn failed");
   const auto source=b->spawn(std::string("zombie:")+kind,"zombie",2180,960,-1,false);if(!source)throw std::runtime_error("special spawn rejected");
   // Preserve bungee's independent rope entry; all others begin fully entered.
   if(std::string(kind)!="飞贼僵尸")b->fixture_place_zombie(*source,2180,960,-1);
   J fields={{"血量",1.e8},{"_pvp_max_hp",1.e8}};if(std::string(kind)!="飞贼僵尸")fields["出场"]=500;if(std::string(mode)=="charmed")fields["魅惑"]=200;b->native_set(false,*source,fields);
   const auto ally=b->spawn("zombie:普通僵尸","zombie",2160,960,-1,false);if(!ally)throw std::runtime_error("ally spawn failed");b->fixture_place_zombie(*ally,2160,960,-1);b->native_set(false,*ally,{{"血量",1.e8},{"_pvp_max_hp",1.e8}});
   const std::string wanted=std::string(mode)=="attack"?"attack":"follow";if(b->snapshot()["command"]!=wanted){const auto error=b->command("zombie",{{"type","command"},{"seq",1}});if(!error.empty())throw std::runtime_error(error);}
   if(std::string(mode)=="rally"){const auto error=b->command("zombie",{{"type","rally"},{"seq",2},{"x",2900},{"y",950}});if(!error.empty())throw std::runtime_error(error);}
   J trail=J::array();for(int i=0;i<120;++i){if(i==60)b->fixture_ditu(18,42,{{"方块","空"},{"里方块","空"}});b->step();if(i%10==0){auto v=b->native_view();v["g"].erase("ditu");trail.push_back(std::move(v));}}
   row["trail"]=trail;row["state"]=b->snapshot();row["rng"]=b->rng_state();row["terrain"]=b->map_tiles();row["passed"]=!b->finished();if(b->finished())throw std::runtime_error("movement fixture ended early");
  }catch(const std::exception&e){row["passed"]=false;row["error"]=e.what();++failures;}
  std::cout<<J{{"kind",kind},{"mode",mode},{"passed",row["passed"]},{"error",row.value("error",std::string{})}}.dump()<<std::endl;rows.push_back(row);
 }
 // Flyers must intercept the first opposing entity on the route to a flag
 // or their Dave; sweet potato explicitly overrides the interception.
 for(const char* kind:{"海盗鹦鹉","乌鸦"})for(const char* order:{"follow","rally"})for(const char* blocking:{"none","plant","charmed","dave","sweet"}){
  std::cerr<<"FLYER "<<kind<<" "<<order<<" "<<blocking<<std::endl;
  J row={{"kind",kind},{"mode",order},{"blocking",blocking}};try{
   auto b=typed72app::Session::create(cold,"性能固定场景");
   b->fixture_set_avatar("plant",{{"玩家位置",{1600,960,0,0}},{"玩家血量",1.e8}});b->fixture_set_avatar("zombie",{{"玩家位置",{2900,960,0,0}},{"玩家血量",1.e8}});
   const auto source=b->spawn(std::string("zombie:")+kind,"zombie",2180,960,1,false);if(!source)throw std::runtime_error("flyer spawn rejected");b->fixture_place_zombie(*source,2180,960,1);b->native_set(false,*source,{{"出场",500}});
   std::optional<std::string> blocker;const std::string which=blocking;
   if(which=="plant"||which=="sweet"){
    blocker=b->spawn(which=="sweet"?"plant:甜薯":"plant:坚果","plant",which=="sweet"?2136.:2736.,which=="sweet"?864.:960.,1,false);
    if(!blocker)throw std::runtime_error("flyer blocker plant rejected");b->native_set(false,*blocker,{{"植物血",1.e8},{"植物血上限",1.e8}});
    if(which=="sweet")b->fixture_ditu(18,44,{{"方块","土"},{"里方块","空"}});
   }else if(which=="charmed"){
    blocker=b->spawn("zombie:普通僵尸","zombie",2736,960,1,false);if(!blocker)throw std::runtime_error("charmed blocker rejected");b->fixture_place_zombie(*blocker,2736,960,1);b->native_set(false,*blocker,{{"出场",500},{"血量",1.e8},{"_pvp_max_hp",1.e8},{"魅惑",200},{"黄油",1.e8}});
   }else if(which=="dave")b->fixture_set_avatar("plant",{{"玩家位置",{2736,984,0,0}},{"玩家血量",1.e8}});
   const J command=std::string(order)=="follow"?J{{"type","move"},{"seq",1},{"move",0},{"jump",false}}:J{{"type","rally"},{"seq",2},{"x",2900},{"y",950}};
   const auto error=b->command("zombie",command);if(!error.empty())throw std::runtime_error(error);b->step();
   const auto v=b->native_view();std::string target;J flyer;
   for(const auto& z:v["g"]["僵尸"])if(z.value("_pvp_id",std::string{})==*source){flyer=z;target=z.value("_pvp_target",std::string{});}
   row["selected_target"]=target;row["expected_blocker"]=blocker?J(*blocker):J(nullptr);row["flyer"]=flyer;
   if(blocker&&target!=*blocker)throw std::runtime_error("flyer skipped its blocking/taunting entity");
   if(which=="dave"&&target!="hero:plant")throw std::runtime_error("flyer skipped Plant Dave on its route");
   if(target.empty())throw std::runtime_error("flyer has no destination");row["passed"]=true;
  }catch(const std::exception&e){row["passed"]=false;row["error"]=e.what();++failures;}rows.push_back(row);
 }
 // A behavior assertion in addition to old/new trajectory equality: plants
 // stand between the yeti and Dave, and must never become its bite targets.
 J head={{"kind","斩首行动雪人"}};try{
  auto b=typed72app::Session::create(cold,"性能固定场景");b->fixture_set_avatar("plant",{{"玩家位置",{1800,960,0,0}},{"玩家血量",1.e8}});
  const auto p=b->spawn("plant:坚果","plant",2136,960,1,false);const auto z=b->spawn("zombie:雪人僵尸","zombie",2160,960,-1,false);if(!p||!z)throw std::runtime_error("headhunt fixture spawn failed");
  b->native_set(false,*p,{{"植物血",1000},{"植物血上限",1000}});b->fixture_place_zombie(*z,2160,960,-1);b->native_set(false,*z,{{"血量",1.e8},{"_pvp_max_hp",1.e8},{"_pvp_zs_headhunt",true}});
  J trail=J::array();for(int i=0;i<120;++i){b->step();if(i%10==0){auto v=b->native_view();v["g"].erase("ditu");trail.push_back(std::move(v));}}
  const auto s=b->snapshot();double hp=-1.;for(const auto& u:s["units"])if(u["id"]==*p)hp=u["hp"];
  head["plant_hp"]=hp;head["trail"]=trail;head["state"]=s;head["rng"]=b->rng_state();if(hp!=1000.)throw std::runtime_error("headhunt yeti bit a plant");head["passed"]=true;
 }catch(const std::exception&e){head["passed"]=false;head["error"]=e.what();++failures;}rows.push_back(head);
 std::ofstream(argv[1],std::ios::binary)<<J{{"passed",failures==0},{"failures",failures},{"cases",rows},{"scope","Production trajectories with water, obstacles, live terrain edits, friendly companion and attack/follow/rally/charm. Equality does not prove every long-period ability triggered."}}.dump();
 callm(h.battle,SY("close"),Args{});return failures?1:0;
}
