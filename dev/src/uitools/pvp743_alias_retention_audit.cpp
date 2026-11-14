// Real production Session: repeated custom-zombie atlas aliases must not retain
// fixture JSON. The same executable source is linked before/after observer elision.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/alloc.h"
#include "core/trace.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "sim/typed/native_frame.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
#include <chrono>
using namespace pvz;using J=nlohmann::json;
namespace {
void require(bool ok,const std::string& what){if(!ok)throw std::runtime_error(what);}
J frame_pixels(const typed72::NativeFrame& frame){
 uint64_t hash=1469598103934665603ull;size_t images=0,painted=0;
 for(const auto& c:frame.commands)if(c.image){
  const auto& p=typed72::NativeArtStore::pixels(c.image);++images;
  hash^=uint64_t(p.width);hash*=1099511628211ull;hash^=uint64_t(p.height);hash*=1099511628211ull;
  for(const auto& x:p.pixels){for(const auto value:x){hash^=uint64_t(value);hash*=1099511628211ull;}painted+=x[3]>0;}
 }
 return {{"hash",hash},{"images",images},{"nontransparent_pixels",painted}};
}
struct Fixture {
 BattleHandle handle;std::unique_ptr<typed72app::Session> battle;
 Fixture():handle(battle_from_scenario({{"seed",74314},{"fixture_flat",true},{"night",true},{"durable_heroes",true},
  {"decks",{{"plant",{"plant:向日葵","plant:原始豌豆射手","plant:火炬树桩"}},{"zombie",{"zombie:脑光墓碑","zombie:普通僵尸","zombie:海盗船长","zombie:乌鸦"}}}}})){
  battle=typed72app::Session::create(typed72app::export_cold(handle.battle,74314),"custom alias retention");
  for(const char* side:{"plant","zombie"})battle->fixture_set_avatar(side,{{"玩家位置",{3500,960,0,0}},{"玩家血量",1.e8},{"_pvp_butter",1.e8}});
 }
 ~Fixture(){try{callm(handle.battle,SY("close"),Args{});}catch(...) {}}
 std::string zombie(const std::string& key,double x){auto id=battle->spawn("zombie:"+key,"zombie",x,960,-1,false);require(bool(id),"spawn rejected "+key);battle->fixture_place_zombie(*id,x,960,-1);battle->native_set(false,*id,{{"出场",500.},{"血量",1.e8},{"_pvp_max_hp",1.e8},{"黄油",1.e8},{"啃咬",1.e8}});return *id;}
};
J contract(typed72app::Session& b){return {{"snapshot",b.snapshot(false)},{"native",b.native_view()},{"rng",b.rng_state()},{"frame",b.reference_native_frame()},{"pixels",frame_pixels(b.native_frame())}};}
}
int main(int argc,char** argv){
 if(argc!=3||!std::getenv("PVP_USERDATA"))return 2;const bool expect_elided=std::string(argv[2])=="elided";
 pvz::install_crash_handler();SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 J report;try{
  {Fixture f;f.zombie("海盗船长",1680);f.zombie("乌鸦",2000);J samples=J::array();
   native_alloc_trace_start();const auto start=std::chrono::steady_clock::now();
   for(int room=0;room<=1200;++room){if(room)f.battle->step();require(!f.battle->finished(),"fixture battle ended early");
    if(room==0||room==12||room==120||room==1200){uint64_t live=0,peak=0;native_alloc_trace_read(live,peak);
     const auto retained=f.battle->fixture_retention();const auto alias=retained.at("aliases64").get<size_t>();
     if(expect_elided)require(alias==0,"production retained custom alias fixture history");
     if(room==1200&&!expect_elided)require(alias>=10000,"baseline did not execute repeated alias observer");
     samples.push_back({{"room_tick",room},{"native_tick",f.battle->clock().native_tick},{"retention",retained},{"requested_live",live},{"requested_peak",peak},
       {"contract",contract(*f.battle)}});
    }
   }
   require(f.battle->clock().native_tick==10000,"expected exactly 10000 native ticks");
   report["custom"]={{"samples",samples},{"wall_seconds",std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()}};
  }
  // A real primal shot crosses a real torch, then hits a durable target.
  {Fixture f;const auto source=f.battle->spawn("plant:原始豌豆射手","plant",2136,960,1,false);
   require(bool(source),"primal spawn rejected");require(bool(f.battle->spawn("plant:火炬树桩","plant",2232,960,1,false)),"torch spawn rejected");
   f.battle->native_set(false,*source,{{"射",0.},{"射cd",0.}});
   const auto target=f.zombie("普通僵尸",2376);bool lit=false;double loss=0;J samples=J::array();
   for(int i=0;i<150&&!loss;++i){f.battle->step();f.battle->native_set(false,*source,{{"射cd",1.e8}});
    const auto native=f.battle->native_view();for(const auto& e:native["g"]["实体"])if(e.value("名",std::string{})=="火豆")lit=true;
    const auto snapshot=f.battle->snapshot(false);for(const auto& u:snapshot["units"])if(u["id"]==target)loss=1.e8-u["hp"].get<double>();
    if(i==0||lit||loss)samples.push_back({{"room_tick",i+1},{"contract",contract(*f.battle)}});
   }
   report["primal_fire"]={{"ignited",lit},{"damage",loss},{"samples",samples}};
   require(lit&&loss==60.,"primal torch conversion/direct damage changed");
  }
  report["passed"]=true;report["observer_elided"]=expect_elided;
 }catch(const std::exception& e){report["passed"]=false;report["error"]=e.what();pvz::print_last_cpp_throw(stderr);}
 std::ofstream(argv[1],std::ios::binary)<<report.dump(2);std::cerr<<J{{"passed",report.value("passed",false)},{"error",report.value("error",std::string{})}}.dump()<<std::endl;return report.value("passed",false)?0:1;
}
