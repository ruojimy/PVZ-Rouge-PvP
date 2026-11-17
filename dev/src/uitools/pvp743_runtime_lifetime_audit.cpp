// Ownership regressions: real battle/preview construction, no cycle collector.
#include "pg/pg.h"
#include "pg/render_stats.h"
#include "core/gil.h"
#include "core/trace.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_preview.h"
#include <fstream>
#include <iostream>
#include <map>
using namespace pvz;using J=nlohmann::json;
namespace pvz { size_t native_live_box_count(); }
namespace pvz::typed72app { V wrap_battle(const V&);void start_battle_session(const V&); }
namespace {
void require(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
J scenario(bool coop){
 J s={{"seed",743},{"durable_heroes",true}};
 if(coop){s["mode"]="coop";s["campaign_deck"]=true;s["director"]={{"day",8},{"seed",743}};}
 return s;
}
J lifetime(bool coop){
 J counts=J::array();uint64_t warm_surfaces=0,warm_bytes=0;size_t warm_boxes=0;
 for(int round=0;round<8;++round){
  std::map<std::string,std::weak_ptr<PyObj>> weak;V retired_region;
  {
   auto h=battle_from_scenario(scenario(coop));weak["battle"]=h.battle.box->inst;
   for(const char* name:{"engine","g","patch","targets","recorder","graphics","director","scripted_spawn_budget","jobs","gravebusters","audio"}){
    const V value=getattr(h.battle,Sym(name),V::none());if(value.is_inst())weak[name]=value.box->inst;
   }
   const V director=getattr(h.battle,SY("director"),V::none());
   if(director.is_inst()){
    const V cycle=getattr(director,SY("cycle"),V::none());
    if(cycle.is_inst())weak["coop_cycle"]=cycle.box->inst;
   }
   retired_region=py::m_get(getattr(getattr(h.battle,SY("engine")),SY("regions")),V("zombie_coordinates"));
   V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);
   for(int i=0;i<5;++i)callm(b,SY("step"),Args{});
   const V snapshot=callm(b,SY("snapshot"),Args{});const std::string before=dump(snapshot);
   callm(b,SY("close"),Args{});callm(b,SY("close"),Args{});
   require(dump(snapshot)==before,"close mutated a published snapshot");
  }
  for(const auto& [name,value]:weak)require(value.expired(),("retired "+name+" remains alive").c_str());
  bool expired=false;try{retired_region.call(Args{});}catch(const PyError& e){expired=e.kind=="RuntimeError"&&std::string(e.what()).find("namespace has expired")!=std::string::npos;}
  require(expired,"retained region did not reject an expired namespace");retired_region.del();
  const auto s=pg::surface_memory_stats();const size_t boxes=native_live_box_count();
  if(round==1){warm_surfaces=s.live_surfaces;warm_bytes=s.owned_bytes;warm_boxes=boxes;}
  if(round>1){require(s.live_surfaces==warm_surfaces&&s.owned_bytes==warm_bytes,"closed sessions retain SDL surfaces");require(boxes==warm_boxes,"closed sessions retain V boxes");}
  counts.push_back({{"round",round+1},{"surfaces",s.live_surfaces},{"surface_bytes",s.owned_bytes},{"boxes",boxes}});
 }
 return counts;
}
J previews(bool coop){
 auto h=battle_from_scenario(scenario(coop));V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);
 V snapshot=callm(b,SY("snapshot"),Args({},{{SY("include_map"),V(true)}}));
 V view=py_dict({{V("battle"),snapshot},{V("rules"),getattr(b,SY("rules"))},{V("bans"),V::list({})}});
 auto once=[&]{V preview=pm_preview::C_PreviewBattle::m_from_snapshot(Args({view},{{SY("bridge"),h.bridge}}));callm(preview,SY("placement"),Args{V("plant"),V("plant:豌豆射手"),V(1900.),V(960.),V::none(),V::none()});};
 for(int i=0;i<8;++i)once();
 const size_t boxes=native_live_box_count();const auto surfaces=pg::surface_memory_stats();
 for(int i=0;i<2000;++i)once();
 require(native_live_box_count()==boxes,"placement previews retain V boxes");
 require(pg::surface_memory_stats().live_surfaces==surfaces.live_surfaces,"placement previews retain SDL surfaces");
 callm(b,SY("close"),Args{});return {{"previews",2000},{"retained_boxes",0},{"retained_surfaces",0}};
}
J frame_unwind(){
 auto h=battle_from_scenario(scenario(false));V engine=getattr(h.battle,SY("engine")),ns=getattr(engine,SY("g"));Match& G=match_of(ns);
 const V previous=G.__self_ns,saved=G.l;G.l=V(-1000000.);bool threw=false;
 try{callm(engine,SY("execute"),Args{V("zombie_coordinates")});}catch(const PyError&){threw=true;}
 G.l=saved;require(threw,"fixture failed to throw inside a region");
 require(py_is(G.__self_ns,previous),"region exception retained its globals");
 require(py::m_get(py::getframe(),V("f_code")).is_none(),"region exception retained its frame");
 callm(h.battle,SY("close"),Args{});return {{"exception_restored_globals",true},{"exception_popped_frame",true}};
}
}
int main(int argc,char** argv){
 if(argc!=2||!std::getenv("PVP_USERDATA"))return 2;
 SDL_SetMainReady();install_crash_handler();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 J rows=J::array();int failed=0;
 auto run=[&](const char* name,auto test){try{rows.push_back({{"case",name},{"pass",true},{"evidence",test()}});}catch(const std::exception& e){++failed;rows.push_back({{"case",name},{"pass",false},{"error",e.what()}});}};
 run("region_exception_unwind",frame_unwind);
 run("duel_previews",[]{return previews(false);});run("coop_previews",[]{return previews(true);});
 run("duel_close_and_restart",[]{return lifetime(false);});run("coop_close_and_restart",[]{return lifetime(true);});
 J report={{"cases",rows},{"passed",rows.size()-failed},{"failed",failed}};
 std::ofstream(argv[1])<<report.dump(2);std::cout<<report.dump(2)<<std::endl;return failed?1:0;
}
