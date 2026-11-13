#include "pg/pg.h"
#include "core/gil.h"
#include "core/trace.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "ui/gen/pm_world_view.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
#include <map>
#include <unordered_map>
using namespace pvz;using J=nlohmann::json;
namespace {
void need(bool ok,const std::string& text){if(!ok)throw std::runtime_error(text);}
struct Fixture {
 BattleHandle h;std::unique_ptr<typed72app::Session> b;V world,screen,rect;
 explicit Fixture(bool poison=false):h(battle_from_scenario({{"seed",74214},{"fixture_flat",true},{"night",poison},{"durable_heroes",true},{"rules",{{"plant_slots",32},{"zombie_slots",32}}},
  {"decks",{{"plant",poison?J::array({"plant:大喷菇","plant:回旋镖射手","plant:坚果","plant:抓人草","plant:芦笋战机","secret:毒镖","secret:毒气"}):J::array({"plant:坚果","plant:抓人草","plant:芦笋战机"})},
    {"zombie",{"zombie:脑光墓碑","zombie:普通僵尸","zombie:黑铁桶僵尸","zombie:雪人僵尸","zsecret:二手"}}}}})){
  b=typed72app::Session::create(typed72app::export_cold(h.battle,74214),"map key production audit");
  for(const char* side:{"plant","zombie"})b->fixture_set_avatar(side,{{"玩家位置",{3400,96,0,0}},{"玩家血量",1.e8},{"_pvp_butter",1.e8}});
  if(b->snapshot(false).at("command")!="attack")need(b->command("zombie",{{"type","command"},{"seq",1}}).empty(),"fixture attack command rejected");
  world=pm_world_view::new_WorldView(Args{pg::pygame_module(),h.bridge});screen=pg::new_surface(640,360,true);rect=callm(pg::pygame_module(),SY("Rect"),Args{V(0),V(0),V(640),V(360)});
 }
 ~Fixture(){try{callm(h.battle,SY("close"),Args{});}catch(...){} }
 std::string spawn(const std::string& card,double x,double y=960.){const auto id=b->spawn(card,card.rfind("plant:",0)==0?"plant":"zombie",x,y,1.,false);need(bool(id),"spawn rejected "+card);return *id;}
 std::string zombie(const std::string& card,double x,double y=960.){const auto id=spawn(card,x,y);b->fixture_place_zombie(id,x,y,-1.);b->native_set(false,id,{{"血量",1.e8},{"_pvp_max_hp",1.e8},{"出场",500.},{"黄油",1.e8}});return id;}
 J draw(double x=1200.,double y=960.){
  auto view=b->snapshot();need(view.contains("native_frame"),"snapshot lost production frame");view["players"]["plant"]["x"]=x;view["players"]["plant"]["y"]=y;view["players"]["plant"]["hp"]=1.e8;
  callm(world,SY("render"),Args{screen,py::json_loads(V(view.dump())),rect,V("plant"),V::dict(),getattr(h.battle,SY("map"))});return view;
 }
};
}
int main(int argc,char**argv){
 if(argc<2||!std::getenv("PVP_USERDATA"))return 2;install_crash_handler();SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 J checks=J::array();int failures=0;auto test=[&](std::string name,auto fn){J r={{"name",name}};try{r["evidence"]=fn();r["passed"]=true;}catch(const std::exception& e){print_last_cpp_throw(stderr);r["passed"]=false;r["error"]=e.what();++failures;}checks.push_back(r);J shortrow=r;shortrow.erase("evidence");std::cerr<<shortrow.dump()<<std::endl;};
 test("toolchain_exception_fingerprint",[]()->J{std::string ordered,hashed;try{std::map<int,int> m;(void)m.at(7);}catch(const std::out_of_range& e){ordered=e.what();}try{std::unordered_map<int,int> m;(void)m.at(7);}catch(const std::out_of_range& e){hashed=e.what();}need(!ordered.empty()&&!hashed.empty()&&ordered!=hashed,"map exception fingerprints are not distinct");return {{"std_map_missing_key",ordered},{"std_unordered_map_missing_key",hashed},{"expected_exceptions_only",true}};});
 test("real_poison_levels_and_repeated_world_draw",[]()->J{Fixture f(true);const auto p1=f.spawn("plant:大喷菇",768.),p2=f.spawn("plant:回旋镖射手",1920.);f.b->native_set(false,p1,{{"射",0.},{"射cd",0.}});f.b->native_set(false,p2,{{"射",0.},{"射cd",0.}});f.zombie("zombie:普通僵尸",864.);f.zombie("zombie:黑铁桶僵尸",2112.);int level1=0,level2=0,frames=0;for(int i=0;i<150;++i){f.b->step();auto s=f.b->snapshot(false);for(const auto& u:s["units"]){const int level=u.value("poison_level",0);need(level>=0&&level<=2,"natural poison admitted invalid level");level1+=level==1;level2+=level==2;}if(i%5==0){f.draw(i%10?1920.:768.);++frames;}}need(level1>0&&level2>0,"real projectile path did not exercise both poison tint keys: "+J{{"level1",level1},{"level2",level2}}.dump());return {{"room_ticks",150},{"actual_world_frames",frames},{"level1_observations",level1},{"level2_observations",level2}};});
 test("more_than_64_distinct_yeti_goal_cells",[]()->J{
  Fixture f;int created=0;
  for(int col=0;col<70;++col){
   const double x=24.+col*48.;
   f.spawn("plant:坚果",x,960.);f.zombie("zombie:雪人僵尸",x+12.,960.);++created;
  }
  int frames=0;size_t unique_max=0;J last_native;
  for(int tick=0;tick<18;++tick){
   f.b->step();last_native=f.b->native_view();std::map<std::string,bool> goals;
   for(const auto& z:last_native["g"]["僵尸"])if(z.contains("_pvp_target")&&!z["_pvp_target"].is_null())goals[z["_pvp_target"].dump()]=true;
   unique_max=std::max(unique_max,goals.size());if(tick%3==0){f.draw(1600.,600.);++frames;}
  }
  if(created!=70||unique_max<=64)throw std::runtime_error("fixture did not select more than 64 distinct plant goals: "+J{{"unique_max",unique_max},{"command",f.b->snapshot(false)["command"]},{"first_zombie",last_native["g"]["僵尸"].empty()?J(nullptr):last_native["g"]["僵尸"][0]},{"first_plant",last_native["g"]["植物"].empty()?J(nullptr):last_native["g"]["植物"][0]}}.dump());
  return {{"distinct_plants",70},{"yeti_count",70},{"room_ticks",18},{"world_frames",frames},{"selected_unique_target_records_max",unique_max},{"scope","Observed more than 64 distinct selected plants in separate cells; no claim of measured internal cache rebuild count."}};
 });
 test("mixed_dense_sessions_create_draw_destroy",[]()->J{int spawns=0,frames=0;for(int round=0;round<4;++round){Fixture f;for(int i=0;i<24;++i){const auto card=i%3==0?"plant:抓人草":i%3==1?"plant:芦笋战机":"plant:坚果";f.spawn(card,576.+(i%8)*144.,960.-(i/8)*96.);f.zombie(i%2?"zombie:黑铁桶僵尸":"zombie:普通僵尸",1968.+(i%8)*48.,960.-(i/8)*96.);spawns+=2;}for(int tick=0;tick<12;++tick){f.b->step();f.draw();++frames;}}return {{"independent_sessions",4},{"real_spawns",spawns},{"actual_world_frames",frames},{"scope","Deterministic bounded reproduction attempts, not proof that a rare live cooperative crash cannot occur."}};});
 const J report={{"passed",failures==0},{"failures",failures},{"checks",checks},{"scope","Real production Session and WorldView; isolated SDL dummy userdata. No current game interaction, no map exceptions swallowed in production, no default key insertion repair."}};std::ofstream(argv[1])<<report.dump(2);return failures?1:0;
}
