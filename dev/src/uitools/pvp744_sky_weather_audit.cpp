// Production battle regression: sky weather, starting night and co-op phase boundaries.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/typed_battle.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include <fstream>
#include <iostream>
#include <map>
#include <set>
using namespace pvz;using J=nlohmann::json;
namespace {
J json(const V& v){return J::parse(dump(v));}
V value(const J& j){return py::json_loads(V(j.dump()));}
void need(bool ok,const std::string& text){if(!ok)throw std::runtime_error(text);}
struct Close {V b;~Close(){try{callm(b,SY("close"),Args{});}catch(...){}}};
struct Seen {
 std::map<std::string,std::set<std::string>> ids;
 std::map<int,size_t> sky_phases;
 std::map<int,double> first_sky;
 void observe(const J& s){
  const auto add=[&](const J& r,bool income){
   const auto source=r.value("source",std::string{});if(source.empty())return;
   const auto id=r.at(income?"resource_id":"id").get<std::string>();
   if(ids[source].insert(id).second&&source=="sky"){
    const double time=income?r.at("time").get<double>():r.at("born").get<double>();
    const int phase=int(time/120.);++sky_phases[phase];
    if(!first_sky.contains(phase))first_sky[phase]=time;
   }
  };
  for(const auto& r:s.at("resources"))add(r,false);
  for(const auto& e:s.at("events"))if(e.value("event",std::string{})=="income")add(e,true);
 }
 size_t count(const char* source){return ids[source].size();}
};
J scenario(const char* mode,bool night,const char* weather,bool secret=false){
 J plant={"plant:向日葵","plant:豌豆射手"};if(secret)plant.push_back("secret:阳光");
 J decks={{"plant",plant},{"zombie",{"zombie:普通僵尸","zombie:脑光墓碑"}}};
 if(std::string(mode)=="duo"||std::string(mode)=="coop")decks["plant2"]={"plant:向日葵","plant:坚果"};
 if(std::string(mode)=="duo")decks["zombie2"]={"zombie:路障僵尸","zombie:脑光墓碑"};
 return {{"seed",744},{"mode",mode},{"night",night},{"weather",weather},{"decks",decks},{"durable_heroes",true},
         {"rules",{{"sky_interval",1.},{"day_brain_interval",1.},{"sun_lifetime",100000.},{"deathmatch_seconds",100000.}}}};
}
J snapshot(const V& b){return json(callm(b,SY("snapshot"),Args({},{{SY("include_map"),V(true)}})));}
}
int main(int argc,char** argv){
 if(argc<2)return 2;
 const auto out=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(out);
 env_set_u8("PVP_USERDATA",p8(out/"userdata"));env_set_u8("SDL_VIDEODRIVER","dummy");env_set_u8("SDL_AUDIODRIVER","dummy");
 SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 const bool static_only=argc>2&&std::string(argv[2])=="--static-only";
 J checks=J::array();int failures=0;
 const auto test=[&](const std::string& name,auto fn){J row={{"name",name}};try{row["evidence"]=fn();row["passed"]=true;}catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();++failures;}checks.push_back(row);std::cerr<<row.dump()<<std::endl;};
 for(const char* mode:{"duel","duo","coop","pve"})for(bool night:{false,true})for(const char* weather:{"clear","rain"}){
  test(std::string(mode)+(night?"_night_":"_day_")+weather,[&]()->J{
   auto h=battle_from_scenario(scenario(mode,night,weather));const J before=json(getattr(h.battle,SY("map"))).at("environment");
   V b=typed72app::wrap_battle(h.battle);Close close{b};typed72app::start_battle_session(b);
   const V sunflower=callm(b,SY("spawn"),Args{V("plant:向日葵"),V("plant"),V(2136.),V(864.),V(1.)});need(!sunflower.is_none(),"sunflower fixture failed");
   Seen seen;for(int tick=0;tick<240;++tick){callm(b,SY("step"),Args{});seen.observe(snapshot(b));}
   const J after=snapshot(b);const bool allowed=!night&&std::string(weather)=="clear";
   const bool zombie_seats=std::string(mode)=="duel"||std::string(mode)=="duo";
   J evidence={{"sky",seen.count("sky")},{"producer",seen.count("native_producer")},{"day_income",seen.count("day_income")},{"environment_unchanged",before==after.at("map").at("environment")}};
   need((seen.count("sky")>0)==allowed,"sky weather mismatch: "+evidence.dump());
   need((seen.count("day_income")>0)==(!night&&zombie_seats),"daytime brain income mismatch: "+evidence.dump());
   need(seen.count("native_producer")>0,"weather blocked sunflower production: "+evidence.dump());
   need(before==after.at("map").at("environment"),"static environment changed: "+evidence.dump());return evidence;
  });
 }
 if(!static_only){
  for(bool initial_night:{false,true})for(const char* weather:{"clear","rain"}){
   test(std::string("coop_cycle_")+(initial_night?"night_":"day_")+weather,[&]()->J{
    J sc=scenario("coop",initial_night,weather);sc["campaign_deck"]=true;sc["director"]={{"day",1},{"seed",744}};
    auto h=battle_from_scenario(sc);V director=getattr(h.battle,SY("director"));
    // Postpone waves only in this fixture; the real co-op clock and weather run normally.
    J plan=json(getattr(director,SY("plan")));need(!plan.empty(),"no wave fixture");plan[0]["time"]=100000.;setattr(director,SY("plan"),value(plan));
    V b=typed72app::wrap_battle(h.battle);Close close{b};typed72app::start_battle_session(b);
    Seen seen;J phases=J::array();
    for(int tick=1;tick<=7236;++tick){
     callm(b,SY("step"),Args{});
     // Fewer projections away from boundaries; no more than 8 ticks between observations.
     if(tick%8&&tick%3600!=0)continue;
     const auto s=snapshot(b);need(s.at("result").is_null(),"co-op fixture ended early");seen.observe(s);
     const auto t=s.at("time").get<double>();const bool night=initial_night^(int(t/120.)%2!=0);
     need(s.at("map").at("environment").at("night")==night,"co-op map phase drift");
     need(s.at("team").at("daylight").at("night")==night,"co-op director phase drift");
     need(s.at("map").at("environment").value("weather",std::string("clear"))==weather,"co-op weather changed");
     if(tick%3600==0)phases.push_back({{"time",t},{"night",night},{"sky_total",seen.count("sky")}});
    }
    for(int phase=0;phase<3;++phase){
     const bool night=initial_night^(phase%2!=0),allowed=!night&&std::string(weather)=="clear";
     need((seen.sky_phases[phase]>0)==allowed,"co-op sky phase "+std::to_string(phase)+" count="+std::to_string(seen.sky_phases[phase]));
     if(phase&&allowed)need(seen.first_sky.at(phase)>=phase*120.+1.-1./30.-1e-8,"dawn inherited blocked sky progress");
    }
    return {{"sky_by_phase",seen.sky_phases},{"first_sky_by_phase",seen.first_sky},{"boundaries",phases},{"real_simulated_seconds",getattr(b,SY("time")).num()}};
   });
  }
  for(const char* mode:{"duo","coop"})for(const char* weather:{"clear","rain"}){
   test(std::string(mode)+"_shared_sky_"+weather,[&]()->J{
    auto h=battle_from_scenario(scenario(mode,false,weather,true));V b=typed72app::wrap_battle(h.battle);Close close{b};
    const auto before=snapshot(b).at("players");Seen seen;for(int i=0;i<60;++i){callm(b,SY("step"),Args{});seen.observe(snapshot(b));}
    const auto after=snapshot(b).at("players");J income=J::object();
    for(const char* side:{"plant","plant2"}){const double delta=after.at(side).at("resource").get<double>()-before.at(side).at("resource").get<double>();income[side]=delta;need(delta==(std::string(weather)=="clear"?30.:0.),"shared sky secret income mismatch: "+income.dump());}
    return {{"income",income},{"sky",seen.count("sky")}};
   });
  }
  test("historical_cold_night_fallback",[&]()->J{
   auto h=battle_from_scenario(scenario("duel",true,"clear"));auto cold=typed72app::export_cold(h.battle,744.);cold.cold.at("battle").erase("map_environment");
   auto session=typed72app::Session::create(std::move(cold),"night-fallback");Seen seen;
   for(int i=0;i<60;++i){session->step();seen.observe(session->snapshot(false,false));}
   need(!seen.count("sky")&&!seen.count("day_income"),"old cold globals lost night");return {{"sky",seen.count("sky")},{"day_income",seen.count("day_income")}};
  });
 }
 J result={{"passed",failures==0},{"failures",failures},{"checks",checks},{"packaged",false}};
 std::ofstream(out/"results.json",std::ios::binary)<<result.dump(2)<<'\n';return failures?1:0;
}
