#include "pg/pg.h"
#include "core/gil.h"
#include "core/function_profile.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <chrono>
#include <fstream>
#include <iostream>
#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#pragma comment(lib,"psapi.lib")
#endif
using namespace pvz;using J=nlohmann::json;using Clock=std::chrono::steady_clock;
static double ms(Clock::time_point a,Clock::time_point b){return std::chrono::duration<double,std::milli>(b-a).count();}
static J memory(){
#ifdef _WIN32
 PROCESS_MEMORY_COUNTERS_EX p{};p.cb=sizeof(p);GetProcessMemoryInfo(GetCurrentProcess(),reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&p),sizeof(p));
 return {{"rss",p.WorkingSetSize},{"peak_rss",p.PeakWorkingSetSize},{"private_bytes",p.PrivateUsage}};
#else
 return nullptr;
#endif
}
int main(int argc,char**argv){
 if(argc!=5)return 2;const std::string scene=argv[1];const int n=std::stoi(argv[2]),ticks=std::stoi(argv[3]);
 try{
  if(n<2||ticks<1)throw std::runtime_error("invalid workload");
  SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
  const std::vector<std::string> kinds={"芦笋战机","旋转芜菁","闪电芦苇","超载芦苇","豌豆迫击炮","弹簧草","幽灵辣椒","抓人草"};
  J plants={"plant:向日葵","secret:触手"};for(const auto& k:kinds)plants.push_back("plant:"+k);
  auto h=battle_from_scenario({{"seed",742},{"fixture_flat",true},{"durable_heroes",true},{"rules",{{"plant_slots",16}}},{"decks",{{"plant",plants},{"zombie",{"zombie:脑光墓碑","zombie:普通僵尸","zombie:小鬼僵尸","zombie:巨人僵尸","zombie:海盗鹦鹉"}}}}});
  auto b=typed72app::Session::create(typed72app::export_cold(h.battle,742),"空间索敌固定场景");
  for(const char* side:{"plant","zombie"})b->fixture_set_avatar(side,{{"玩家位置",{scene=="idle"&&std::string_view(side)=="zombie"?1920.:3400.,960,0,0}},{"玩家血量",1.e8}});
  std::vector<std::string> targets,roots,attackers;const auto start=Clock::now();
  const bool idle=scene=="idle",dense=scene=="dense",churn=scene=="churn",moving=scene=="moving";
  std::string only=scene=="asparagus"||idle?"芦笋战机":scene=="grabber"?"抓人草":scene=="turnip"?"旋转芜菁":scene=="reed"?"闪电芦苇":"";
  for(int i=0;i<n;++i){
   const bool plant=i%2==0;const int k=i/2;
   const std::string name=plant?(only.empty()?kinds[size_t(k)%kinds.size()]:only):((scene=="sizes"||moving)&&k%3==0?"巨人僵尸":(scene=="sizes"||moving)&&k%3==1?"小鬼僵尸":"普通僵尸");
   const double x=plant?(idle?240.+(k%2)*48.:dense?1008.:864.+(k%8)*48.):idle?1872.+(k%2)*24.:dense?1392.:1296.+(k%32)*36.;
   const double y=960.;
   const double facing=k%2==0?1.:-1.;
   const auto id=b->spawn((plant?"plant:":"zombie:")+name,plant?"plant":"zombie",x,y,facing,false);
   if(!id)throw std::runtime_error("fixture spawn rejected: "+name);
   if(plant){b->native_set(false,*id,{{"植物血",1.e8},{"植物血上限",1.e8}});attackers.push_back(*id);if(name=="抓人草")roots.push_back(*id);}
   else {b->fixture_place_zombie(*id,x,y,facing);J f={{"出场",500},{"血量",1.e8},{"_pvp_max_hp",1.e8},{"啃咬",1.e8}};if(!moving)f["黄油"]=1.e8;b->native_set(false,*id,f);targets.push_back(*id);}
  }
  for(int round=0;round<2&&!roots.empty();++round){for(const auto& id:roots)b->native_set(false,id,{{"_pvp70_clock",10000}});b->step();}
  for(int i=0;i<15;++i)b->step();
  const auto setup_end=Clock::now(),measure_start=Clock::now();const auto before=b->performance_counters(),mem_before=memory();function_profile::reset();
  std::vector<double> times;size_t peak=0;J changes=J::array();
  for(int t=0;t<ticks;++t){
   // The same input mutations run in both processes, outside measured step work.
   if((moving||churn)&&t%7==0){const size_t j=size_t(t/7)%targets.size();const double x=double((t*173)%3456),y=144.+(t%18)*48.;b->fixture_place_zombie(targets[j],x,y,t%2?1.:-1.);changes.push_back({t,"teleport",targets[j],x,y});}
   if(churn&&t%11==0){const size_t j=size_t(t/11)%targets.size();b->native_set(false,targets[j],{{"血量",0}});const auto id=b->spawn("zombie:普通僵尸","zombie",1700.+t,864,-1,false);if(!id)throw std::runtime_error("churn admission failed");targets[j]=*id;b->fixture_place_zombie(*id,1700.+t,864,-1);b->native_set(false,*id,{{"出场",500},{"血量",1.e8},{"_pvp_max_hp",1.e8},{"黄油",1.e8}});changes.push_back({t,"replace",*id});}
   if(moving&&t%9==0&&!targets.empty()){const size_t j=size_t(t/9)%targets.size();b->native_set(false,targets[j],{{"血量",1.e8-double(t%3)*1.e5}});}
   const auto a=Clock::now();b->step();times.push_back(ms(a,Clock::now()));
   const auto counters=b->performance_counters();peak=std::max(peak,counters["native_entities"].get<size_t>());
  }
  const auto end=Clock::now();const auto after=b->performance_counters();J delta=J::object();
  for(const auto& [key,v]:after.items())if(v.is_number_unsigned()&&before.contains(key)&&before[key].is_number())delta[key]=v.get<int64_t>()-before[key].get<int64_t>();
  auto sorted=times;std::sort(sorted.begin(),sorted.end());const auto percentile=[&](double p){return sorted.at(size_t(p*(sorted.size()-1)));};
  const auto snapshot=b->snapshot();size_t alive=0;for(const auto& u:snapshot["units"])if(u["hp"].get<double>()>0.)++alive;
  J result={{"passed",!b->finished()&&alive>=size_t(n)},{"scene",scene},{"requested_units",n},{"live_units_final",alive},{"seed",742},{"room_steps",ticks},
   {"setup_seconds",ms(start,setup_end)/1000.},{"elapsed_seconds",ms(measure_start,end)/1000.},{"peak_entities",peak},{"memory_before",mem_before},{"memory_after",memory()},
   {"step_ms",{{"p50",percentile(.5)},{"p95",percentile(.95)},{"p99",percentile(.99)}}},{"step_samples_ms",times},{"counter_deltas",delta},{"counters",after},
   {"changes",changes},{"final_state",snapshot},{"final_rng",b->rng_state()},{"final_native",b->native_view()},
   {"scope","Real typed Session, 1 room step=1/30 logical second. Step measurements exclude fixture mutations, snapshot serialization and SDL rendering; timers are inclusive wall-clock CPU-work durations, not OS CPU accounting. Native C++ RAII; no Python GC."}};
  std::ofstream(argv[4],std::ios::binary)<<result.dump(2);std::cout<<J{{"scene",scene},{"units",n},{"passed",result["passed"]},{"step_ms",result["step_ms"]},{"range_queries",delta.value("range_queries",0)},{"range_candidates",delta.value("range_candidates",0)}}.dump()<<std::endl;
  callm(h.battle,SY("close"),Args{});return result["passed"].get<bool>()?0:1;
 }catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}
}
