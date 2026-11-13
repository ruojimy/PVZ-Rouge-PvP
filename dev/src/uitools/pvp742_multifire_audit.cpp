// Actual production generation + isolated single-shot damage and draw evidence.
#include "pg/pg.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
#include <map>
#include <cmath>
using namespace pvz; using J=nlohmann::json;
static void require(bool ok,const std::string& message){if(!ok)throw std::runtime_error(message);}
static void assets(const J& j,std::map<std::string,int>& found){
 if(j.is_object()){
  if(j.value("op",std::string{})=="asset"&&j.contains("key"))++found[j["key"].get<std::string>()];
  for(const auto& [key,value]:j.items())assets(value,found);
 }else if(j.is_array())for(const auto& value:j)assets(value,found);
}
static bool ends(const std::string& key,const std::string& name){return key==name||key.ends_with(":"+name);}
static double hp(typed72app::Session& b,const std::string& id){
 const auto snap=b.snapshot(false);for(const auto& u:snap["units"])if(u["id"]==id)return u["hp"].get<double>();
 throw std::runtime_error("target missing: "+id);
}
int main(int argc,char** argv){
 if(argc!=2)return 2; SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 J rows=J::array();int failures=0;
 for(const char* source:{"plant:三向射手","plant:裂荚射手","plant:豌豆迫击炮"})for(bool multi:{false,true})for(bool blue:{false,true})for(const char* mode:{"units","hero_direct","hero_splash"}){
  J row={{"source",source},{"multi_red",multi},{"blue_torch_secret",blue},{"mode",mode}};
  try{
   J deck={"plant:向日葵",source,"plant:火炬树桩"};if(multi)deck.push_back("secret:三向蓝火");if(blue)deck.push_back("secret:蓝火");
   auto handle=battle_from_scenario({{"seed",742},{"durable_heroes",true},{"decks",{{"plant",deck},{"zombie",{"zombie:脑光墓碑","zombie:普通僵尸"}}}}});
   auto b=typed72app::Session::create(typed72app::export_cold(handle.battle,742),"家院");
   const double health=1000000.;
   const auto sethero=[&](const char* side,double x,double y,bool reset){J state={{"玩家位置",{x,y,0,0}}};if(reset)state["玩家血量"]=health;b->fixture_set_avatar(side,state);};
   sethero("plant",3500,864,true);sethero("zombie",3500,864,true);
   const auto plant=b->spawn(source,"plant",2136,864,1,false);require(bool(plant),"source spawn failed");
   const auto target=b->spawn("zombie:普通僵尸","zombie",2856,864,-1,false);require(bool(target),"trigger target missing");
   b->fixture_place_zombie(*target,2856,864,-1);b->native_set(false,*target,{{"血量",health},{"_pvp_max_hp",health},{"黄油",1000000},{"啃咬",1000000}});
   const auto neighbor=b->spawn("zombie:普通僵尸","zombie",2880,864,-1,false);require(bool(neighbor),"splash neighbor missing");
   b->fixture_place_zombie(*neighbor,2880,864,-1);b->native_set(false,*neighbor,{{"血量",health},{"_pvp_max_hp",health},{"黄油",1000000},{"啃咬",1000000}});
   std::optional<size_t> selected;J generated;
   for(int tick=0;tick<120&&!selected;++tick){
    sethero("plant",3500,864,false);sethero("zombie",3500,864,false);b->step();
    const auto list=b->native_view()["g"]["实体"];
    for(size_t i=0;i<list.size();++i){const auto name=list[i].value("名",std::string{});if(name=="豌豆"||name=="火豆"||name=="蓝火豆"){selected=i;generated=list;break;}}
   }
   require(bool(selected),"plant did not generate a pea");row["generated_projectiles"]=generated;
   const auto projectile=generated.at(*selected);
   require(projectile.value("名",std::string{})==(multi?"火豆":"豌豆"),"actual generated projectile kind is wrong");
   if(multi){require(projectile.value("_pvp_fire_color",std::string{})=="fire","multi-red lost explicit fire colour");require(projectile.value("_pvp_multi_red",false),"multi-red marker absent");}
   // Split-pea / mortar can construct at the end of the room tick, after its
   // last draw boundary. Observe their complete volley on the following tick.
   b->native_set(false,*plant,{{"射cd",1000000}});b->step();
   generated=b->native_view()["g"]["实体"];selected.reset();
   for(size_t i=0;i<generated.size();++i){const auto name=generated[i].value("名",std::string{});if(name=="豌豆"||name=="火豆"||name=="蓝火豆"){selected=i;break;}}
   require(bool(selected),"generated volley disappeared before the draw boundary");
   // Observe the whole real volley before any isolation fixture changes it.
   std::map<std::string,int> volley_assets;assets(b->reference_native_frame(),volley_assets);row["volley_frame_assets"]=volley_assets;
   if(multi){
    int shots=0,bodies=0,trails=0,blue_assets=0;
    for(const auto& shot:generated)if(shot.value("_pvp_multi_red",false))++shots;
    for(const auto& [key,count]:volley_assets){if(ends(key,"火豆"))bodies+=count;if(key.find("火尾")!=std::string::npos)trails+=count;if(key.find("蓝火")!=std::string::npos)blue_assets+=count;}
    row["volley_counts"]={{"shots",shots},{"bodies",bodies},{"trails",trails},{"blue_assets",blue_assets}};
    require(bodies==shots&&trails==shots&&blue_assets==0,"real whole volley body / trail colour or multiplicity mismatch");
    if(std::string(source)=="plant:豌豆迫击炮")require(shots==5,"mortar production volley changed");
   }
   // Retain the actual generated object, preserving source identity / colour.
   const auto rng=b->rng_state();b->fixture_entity(*selected,{{"位置",{2600,720,1,0}}},true);require(b->rng_state()==rng,"fixture consumed RNG");
   b->native_set(false,*plant,{{"射cd",1000000}});b->step();
   const auto frame=b->reference_native_frame();std::map<std::string,int> names;assets(frame,names);row["frame_assets"]=names;
   int bodies=0,trails=0,blue_assets=0;
   for(const auto& [key,count]:names){if(ends(key,"火豆"))bodies+=count;if(key.find("火尾")!=std::string::npos)trails+=count;if(key.find("蓝火")!=std::string::npos)blue_assets+=count;}
   if(multi){require(bodies==1,"single generated red shot has no red body / has duplicate bodies");require(trails==1,"single red shot has duplicate or missing trails");require(blue_assets==0,"global blue-torch secret recoloured a multi-red shot");}
   if(std::string(mode)=="hero_direct"){
    b->fixture_place_zombie(*target,3200,864,-1);b->fixture_place_zombie(*neighbor,3250,864,-1);sethero("zombie",2856,864,false);
   }else if(std::string(mode)=="hero_splash"){
    b->fixture_place_zombie(*neighbor,3250,864,-1);sethero("zombie",2880,864,false);
   }
   b->fixture_entity(0,{{"位置",{2856,840,0,0}}},true);
   const double target_before=hp(*b,*target),neighbor_before=hp(*b,*neighbor),hero_before=b->players()["zombie"]["hp"].get<double>();
   b->step();
   const double target_loss=target_before-hp(*b,*target),neighbor_loss=neighbor_before-hp(*b,*neighbor),hero_loss=hero_before-b->players()["zombie"]["hp"].get<double>();
   row["target_damage"]=target_loss;row["neighbor_damage"]=neighbor_loss;row["hero_damage"]=hero_loss;
   const double direct=multi?20.:10.,splash=multi?20./3.:0.;
   if(std::string(mode)=="units"){
    require(std::abs(target_loss-direct)<1e-6,"single-shot unit direct damage mismatch / direct was splashed twice");
    require(std::abs(neighbor_loss-splash)<1e-6,"unit splash mismatch");
   }else if(std::string(mode)=="hero_direct")require(std::abs(hero_loss-(multi?6.:4.))<1e-6,"hero direct mismatch / direct hero received own splash");
   else {require(std::abs(target_loss-direct)<1e-6,"splash primary unit direct mismatch");require(std::abs(hero_loss-(multi?1.5:0.))<1e-6,"hero splash mismatch");}
   row["passed"]=true;callm(handle.battle,SY("close"),Args{});
  }catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();++failures;}
  std::cout<<row.dump()<<'\n';rows.push_back(row);
 }
 std::ofstream(argv[1],std::ios::binary)<<J{{"passed",failures==0},{"failures",failures},{"cases",rows}}.dump(2);return failures?1:0;
}
