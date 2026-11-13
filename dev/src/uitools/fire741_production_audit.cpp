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
void require(bool value,const std::string& message){if(!value)throw std::runtime_error(message);}
int main(int argc,char**argv){
 if(argc<2)return 2;SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();J rows=J::array();int failures=0;
 for(const char* source:{"plant:豌豆射手","plant:原始豌豆射手","zombie:豌豆僵尸","zombie:机枪僵尸"})for(bool charm:{false,true})for(int fire=0;fire<3;++fire){
  const bool plant=std::string(source).starts_with("plant:");if(plant&&charm)continue;J row={{"source",source},{"charmed",charm},{"fire",fire}};
  try{
   J plants={"plant:向日葵","plant:豌豆射手","plant:火炬树桩"};if(fire==2)plants.push_back("secret:蓝火");
   auto h=battle_from_scenario({{"seed",741},{"durable_heroes",true},{"decks",{{"plant",plants},{"zombie",{"zombie:脑光墓碑","zombie:豌豆僵尸","zombie:机枪僵尸"}}}}});
   auto cold=typed72app::export_cold(h.battle,741);const double plk=cold.cold.at("globals").at("plk").get<double>();
   auto b=typed72app::Session::create(std::move(cold),"家院");
   for(const char* side:{"plant","zombie"})b->fixture_set_avatar(side,{{"玩家位置",{3200,864,0,0}},{"玩家血量",1000000}});
   const auto src=b->spawn(source,plant?"plant":"zombie",2136,864,1,false);require(bool(src),"source spawn failed");
   if(plant)b->native_set(false,*src,{{"射",0},{"射cd",0}});
   else {b->fixture_place_zombie(*src,2136,864,1);J fields={{"血量",1000000},{"啃咬",1000000},{"植物僵尸射cd",0},{"植物僵尸连发",0}};if(charm)fields["魅惑"]=200;b->native_set(false,*src,fields);}
   std::optional<std::string> torch;if(fire)torch=b->spawn("plant:火炬树桩","plant",2232,864,1,false);
   const bool enemy_zombie=plant||charm;const auto target=b->spawn(enemy_zombie?"zombie:普通僵尸":"plant:坚果",enemy_zombie?"zombie":"plant",2376,864,-1,false);require(bool(target),"target spawn failed");
   const double hp=1000000.;if(enemy_zombie){b->fixture_place_zombie(*target,2376,864,-1);b->native_set(false,*target,{{"血量",hp},{"_pvp_max_hp",hp},{"黄油",1000000},{"啃咬",1000000}});}else b->native_set(false,*target,{{"植物血",hp},{"植物血上限",hp}});
   // A zombie keeps its sub-cell position. Two plants share a cell here to
   // exercise direct-hit exclusion and one splash on the second live record;
   // a snapped adjacent cell is beyond the early impact's forward radius.
   const auto neighbor=b->spawn(enemy_zombie?"zombie:普通僵尸":"plant:坚果",enemy_zombie?"zombie":"plant",enemy_zombie?2400:2376,864,-1,false);require(bool(neighbor),"splash neighbor spawn failed");
   if(enemy_zombie){b->fixture_place_zombie(*neighbor,2400,864,-1);b->native_set(false,*neighbor,{{"血量",hp},{"_pvp_max_hp",hp},{"黄油",1000000},{"啃咬",1000000}});}else b->native_set(false,*neighbor,{{"植物血",hp},{"植物血上限",hp}});
   std::optional<std::string> ally;if(enemy_zombie){ally=b->spawn("zombie:普通僵尸","zombie",2376,864,-1,false);b->fixture_place_zombie(*ally,2376,864,-1);b->native_set(false,*ally,{{"血量",hp},{"_pvp_max_hp",hp},{"黄油",1000000},{"啃咬",1000000},{"魅惑",200}});}
   bool lit=false;double loss=0.,ally_loss=0.,neighbor_loss=0.;J trails=J::array();
   for(int n=0;n<150&&!loss;++n){b->step();if(!plant)b->native_set(false,*src,{{"植物僵尸射cd",1000000},{"植物僵尸连发",0}});else b->native_set(false,*src,{{"射cd",1000000}});
    const auto native=b->native_view();for(const auto& e:native["g"]["实体"]){const auto name=e.value("名",e.value("实体",std::string{}));if(name=="火豆"||name=="蓝火豆"||!e.value("__pvz_sb_zombie_pea_fire",std::string{}).empty())lit=true;if(n%20==0)trails.push_back(e);}
    const auto snap=b->snapshot();for(const auto& u:snap["units"]){if(u["id"]==*target)loss=hp-u["hp"].get<double>();if(ally&&u["id"]==*ally)ally_loss=hp-u["hp"].get<double>();if(u["id"]==*neighbor)neighbor_loss=hp-u["hp"].get<double>();}
   }
   row["damage"]=loss;row["ally_damage"]=ally_loss;row["neighbor_damage"]=neighbor_loss;row["ignited"]=lit;row["performance"]=b->performance_counters();row["projectile_samples"]=trails;
   double expected=0.;if(plant)expected=std::string(source)=="plant:原始豌豆射手"?30.*(fire+1):10.*(fire+1);else if(charm)expected=fire==0?10.:fire==1?40.:60.;else expected=2.*(fire+1);
   require(std::abs(loss-expected)<1.e-6,"direct damage differs from the full-regression contract");
   require(std::abs(neighbor_loss-(fire?expected/3.:0.))<1.e-6,"splash/direct-exclusion mismatch");
   if(std::string(source)=="plant:原始豌豆射手"){
    const auto perf=b->performance_counters();const int count=fire==2?2:1;const double scale=fire==2?1.5:fire==1?1.25:1.;
    require(perf["primal_knock_targets"]==count,"primal knockback radius/dedup mismatch");
    require(std::abs(perf["primal_knock_velocity"].get<double>()-count*2.*plk*200.*scale)<1.e-6,"primal applied velocity multiplier mismatch");
   }
   require(loss>0.,"projectile never hit");require(fire?lit:!lit,"torch conversion mismatch");require(ally_loss==0.,"charmed projectile hit its ally");row["passed"]=true;callm(h.battle,SY("close"),Args{});
  }catch(const std::exception&e){row["passed"]=false;row["error"]=e.what();++failures;}
  std::cout<<row.dump()<<std::endl;rows.push_back(row);
 }
 std::ofstream(argv[1],std::ios::binary)<<J{{"passed",failures==0},{"failures",failures},{"cases",rows}}.dump(2);return failures?1:0;
}
