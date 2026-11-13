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
double milliseconds(Clock::time_point a,Clock::time_point b){return std::chrono::duration<double,std::milli>(b-a).count();}
J memory(){
#ifdef _WIN32
 PROCESS_MEMORY_COUNTERS_EX p{};p.cb=sizeof(p);GetProcessMemoryInfo(GetCurrentProcess(),reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&p),sizeof(p));
 return {{"rss",p.WorkingSetSize},{"peak_rss",p.PeakWorkingSetSize},{"private_bytes",p.PrivateUsage}};
#else
 return nullptr;
#endif
}
int main(int argc,char**argv){
 if(argc<5)return 2;const std::string scene=argv[1];const int units=std::stoi(argv[2]),ticks=std::stoi(argv[3]);
 try{
  SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
  J decks={{"plant",{"plant:向日葵","plant:机枪射手","plant:坚果","plant:火炬树桩"}},
    {"zombie",{"zombie:脑光墓碑","zombie:普通僵尸","zombie:机枪僵尸","zombie:小鬼僵尸","zombie:巨人僵尸"}}};
  if(scene=="grabber")decks["plant"]={"plant:向日葵","plant:抓人草","secret:触手"};
  auto h=battle_from_scenario({{"seed",741},{"fixture_flat",true},{"durable_heroes",true},{"decks",decks}});
  auto b=typed72app::Session::create(typed72app::export_cold(h.battle,741),"性能固定场景");
  for(const char* side:{"plant","zombie"})b->fixture_set_avatar(side,{{"玩家位置",{1700,960,0,0}},{"玩家血量",1.e8}});
  const bool zombie_shots=scene=="zombie"||scene=="charmed";const bool dense=scene=="dense"||scene=="contact",mixed=scene=="sizes";
  std::vector<std::string> targets,roots;const auto start=Clock::now();
  for(int i=0;i<units;++i){
   const bool shooting=i%2==0;const bool z=shooting?zombie_shots:!zombie_shots;
   const char* kind=z?(shooting?"zombie:机枪僵尸":mixed?(i%4==1?"zombie:小鬼僵尸":"zombie:巨人僵尸"):"zombie:普通僵尸"):
     shooting?(scene=="grabber"?"plant:抓人草":"plant:机枪射手"):"plant:坚果";
   const double x=shooting?(scene=="grabber"?1930.+(i/2%8)*48.:dense?1008.:864.+(i/2%8)*48.):(scene=="contact"?1296.:dense?2208.:2400.+(i/2%24)*12.);
   const auto id=b->spawn(kind,z?"zombie":"plant",x,960,1,false);if(!id)throw std::runtime_error("stress spawn rejected");
   if(z){b->fixture_place_zombie(*id,x,960,1);J fields={{"出场",500},{"血量",1.e8},{"_pvp_max_hp",1.e8},{"啃咬",1.e8}};
    if(shooting){fields["植物僵尸射cd"]=0;if(scene=="charmed")fields["魅惑"]=200;}else fields["黄油"]=1.e8;
    b->native_set(false,*id,fields);
   }else b->native_set(false,*id,{{"植物血",1.e8},{"植物血上限",1.e8},{"射cd",shooting?0.:1.e8}});
   if(!shooting)targets.push_back(*id);
   if(shooting&&scene=="grabber")roots.push_back(*id);
  }
  for(int round=0;round<2&&!roots.empty();++round){for(const auto& id:roots)b->native_set(false,id,{{"_pvp70_clock",10000}});b->step();}
  // Charmed peas target hostile zombies, so replace the passive plant half
  // with enemies while keeping the requested population explicit in evidence.
  if(scene=="charmed")for(const auto& id:targets)b->native_set(false,id,{{"植物血",0}});
  if(scene=="charmed")for(size_t i=0;i<targets.size();++i){const double x=2400.+(i%24)*12.;const auto id=b->spawn("zombie:普通僵尸","zombie",x,960,1,false);if(!id)throw std::runtime_error("charmed enemy spawn rejected");b->fixture_place_zombie(*id,x,960,1);b->native_set(false,*id,{{"出场",500},{"血量",1.e8},{"_pvp_max_hp",1.e8},{"黄油",1.e8},{"啃咬",1.e8}});}
  if(scene=="obstacles")for(int x=20;x<45;x+=5)for(int y=16;y<20;++y)b->fixture_ditu(y,x,{{"方块","土"},{"里方块","空"}});
  size_t peak=0;for(int i=0;i<8;++i){b->step();peak=std::max(peak,b->performance_counters()["native_entities"].get<size_t>());}
  const auto setup_end=Clock::now();const auto before=b->performance_counters();const auto mem_before=memory();function_profile::reset();
  std::vector<double> times;J populations=J::array();
  for(int i=0;i<ticks;++i){
   const auto a=Clock::now();b->step();const auto c=Clock::now();times.push_back(milliseconds(a,c));
   const auto counters=b->performance_counters();peak=std::max(peak,counters["native_entities"].get<size_t>());
   if(i%15==0)populations.push_back({{"room_step",i},{"native_entities",counters["native_entities"]}});
   if(scene=="churn"&&i%10==0){const size_t n=size_t(i/10)%targets.size();b->native_set(false,targets[n],{{"血量",0}});
    const auto id=b->spawn("zombie:普通僵尸","zombie",2500.+i,960,-1,false);if(!id)throw std::runtime_error("churn admission failed");targets[n]=*id;b->fixture_place_zombie(*id,2500.+i,960,-1);b->native_set(false,*id,{{"血量",1.e8},{"_pvp_max_hp",1.e8},{"黄油",1.e8}});}
  }
  const auto after=b->performance_counters();J delta=J::object();for(const auto& [key,value]:after.items())if(value.is_number_unsigned()&&before.contains(key)&&before[key].is_number())delta[key]=value.get<int64_t>()-before[key].get<int64_t>();
  auto ordered=times;std::sort(ordered.begin(),ordered.end());const auto percentile=[&](double p){return ordered.at(size_t(p*(ordered.size()-1)));};
  const auto snapshot=b->snapshot();size_t live=0;for(const auto& u:snapshot["units"])if(u["hp"].get<double>()>0.)++live;
  J result={{"passed",!b->finished()&&live>=size_t(units-((scene=="churn")?1:0))},{"scene",scene},{"requested_units",units},{"live_units_final",live},
   {"room_steps",ticks},{"setup_seconds",milliseconds(start,setup_end)/1000.},{"peak_entities",peak},{"memory_before",mem_before},{"memory_after",memory()},
   {"step_cpu_ms",{{"p50",percentile(.5)},{"p95",percentile(.95)},{"p99",percentile(.99)}}},{"step_samples_ms",times},
   {"counter_deltas",delta},{"counters",after},{"population",populations},{"final_state",snapshot},{"final_rng",b->rng_state()},
   {"scope","Actual typed Session; one room step = 1/30 logical second, no SDL rendering. Fixture writes excluded from step CPU. Native updates use C++ RAII, no Python GC."}};
  result["final_native"]=b->native_view();result["final_native"]["g"].erase("ditu");
  std::ofstream(argv[4],std::ios::binary)<<result.dump(2);std::cout<<J{{"scene",scene},{"units",units},{"peak_entities",peak},{"live",live},{"step_cpu_ms",result["step_cpu_ms"]},{"passed",result["passed"]}}.dump()<<std::endl;
  callm(h.battle,SY("close"),Args{});return result["passed"].get<bool>()?0:1;
 }catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}
}
