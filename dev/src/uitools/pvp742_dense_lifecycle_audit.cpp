#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "core/trace.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "ui/gen/pm_app.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
#include <set>
using namespace pvz;using J=nlohmann::json;
namespace {
void require(bool b,const std::string& why){if(!b)throw std::runtime_error(why);}
V val(const J& j){return py::json_loads(V(j.dump()));}
struct Cell {int y,x;};
struct Audit {
 std::unique_ptr<typed72app::Session> b;BattleHandle h;V app;std::ofstream journal;
 J last=J::object(),milestones=J::array();int64_t serial=0;std::array<int64_t,2> seq{};size_t commands=0,renders=0,steps=0,peak=0,transforms=0;
 std::vector<Cell> sites;std::set<std::string> durable;std::string mode;
 Audit(const std::filesystem::path& prefix,std::string scene):journal(prefix.string()+".jsonl"),mode(std::move(scene)){
  J cards={"plant:坚果","plant:豌豆射手","plant:机枪射手","plant:杨桃","plant:小喷菇","plant:金盏花","plant:南瓜头","plant:阳光藤蔓","plant:忧郁藤蔓","plant:抓人草","plant:模仿者","plant:咖啡豆","plant:花盆","plant:水盆","plant:睡莲","plant:香蒲","secret:密植","secret:触手","secret:无土栽培"};
  J scene_args={{"seed",742},{"mode","coop"},{"durable_heroes",true},{"rules",{{"plant_slots",32}}},{"decks",{{"plant",cards},{"plant2",cards},{"zombie",{"zombie:普通僵尸"}}}}};
  if(mode=="oasis"){scene_args["team_map"]="ea66000000000000000000000000000a";scene_args["director"]={{"day",9},{"seed",742}};}
  else scene_args["fixture_flat"]=true;
  record("construct",scene_args);h=battle_from_scenario(scene_args);b=typed72app::Session::create(typed72app::export_cold(h.battle,742),"dense co-op lifecycle");
  for(const char* seat:{"plant","plant2"}){b->fixture_set_avatar(seat,{{"玩家位置",{100.,96.,0.,0.}},{"玩家血量",1.e8},{"_pvp_butter",1.e8}});b->fixture_player(seat,{{"resource",1.e9},{"cooldowns_replace",J::object()}});}b->sync_public();
  V pg=pg::pygame_module(),screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(720)})});app=pm_app::new_Application(Args{pg,screen,h.bridge});auto* a=as<pm_app::C_Application>(app);a->a_mode=V("guest");a->a_peer_id=V("guest");setitem(a->a_state,V("screen"),V("room"));
  const auto map=b->map_tiles();const int rows=int(map.size()),cols=int(map.at(0).size());
  for(int x=8;x<cols-8&&sites.size()<32;++x)for(int y=1;y<rows-1;++y){auto p=b->placement("plant","plant:坚果",(x+.5)*48.,(y+.5)*48.,nullptr,nullptr);if(p.at(0)==""){sites.push_back({y,x});break;}}
  require(sites.size()>=12,"not enough actual legal terrain cells");record("sites",{{"count",sites.size()},{"rows",rows},{"cols",cols}});
  for(int i=0;i<12;++i){const auto c=sites[size_t(i)%sites.size()];const auto id=b->spawn("zombie:普通僵尸","zombie",(c.x+.5)*48.+150.,(c.y+1.)*48.,-1.,false);require(bool(id),"durable target rejected");b->native_set(false,*id,{{"血量",1.e8},{"_pvp_max_hp",1.e8},{"出场",500.},{"黄油",1.e8}});durable.insert(*id);}
 }
 ~Audit(){if(!app.is_none())try{callm(app,SY("close_room"),Args{});}catch(...){}try{callm(h.battle,SY("close"),Args{});}catch(...) {}}
 void record(const char* op,J args=J::object()){last={{"serial",++serial},{"op",op},{"args",std::move(args)}};if(b)last["tick"]=b->tick();journal<<last.dump()<<'\n';journal.flush();}
 std::string command(const std::string& seat,J c){const size_t i=seat=="plant2"?1:0;c["seq"]=++seq[i];record("command",{{"seat",seat},{"input",c}});++commands;return b->command(seat,c);}
 std::vector<J> plants(Cell c){std::vector<J> out;const auto v=b->native_view();for(const auto& p:v.at("g").at("植物"))if(p.at("坐标")==J::array({c.y,c.x})&&p.value("_pvp_content",std::string{})!="抓人草触手")out.push_back(p);return out;}
 bool shell(const J& p){const auto content=p.value("_pvp_content",std::string{});return p.at("植物")=="南瓜头"||content=="抓人草"||content=="阳光藤蔓"||content=="忧郁藤蔓"||(p.at("植物")=="模仿者"&&p.value("_pvp_copy_card",std::string{})=="plant:抓人草");}
 void verify(Cell c){const auto stack=plants(c);size_t bodies=0,shells=0;for(const auto& p:stack){if(p.contains("死"))continue;if(shell(p))++shells;else if(p.at("植物")!="花盆"&&p.value("_pvp_content",std::string{})!="水盆"&&p.at("植物")!="睡莲")++bodies;}require(bodies<=3&&shells<=1,"dense cap changed");}
 void step(int count=1){for(int i=0;i<count;++i){record("step");b->step();++steps;const auto snapshot=b->snapshot(false);peak=std::max(peak,snapshot.at("units").size());require(!b->finished(),"fixture battle ended prematurely");
   for(const auto& z:snapshot.at("units"))if(z.value("side",std::string{})=="zombie"&&!durable.contains(z.at("id").get<std::string>())){const auto id=z.at("id").get<std::string>();b->native_set(false,id,{{"血量",1.e8},{"_pvp_max_hp",1.e8},{"黄油",1.e8}});durable.insert(id);}
  }}
 std::string deploy(Cell c,const std::string& card,const std::string& seat,const std::string& copy={}){
  b->fixture_player(seat,{{"resource",1.e9},{"cooldowns_replace",J::object()}});J input={{"type","deploy"},{"card",card},{"x",(c.x+.5)*48.},{"y",(c.y+.5)*48.},{"facing",1}};if(!copy.empty())input["copy"]=copy;
  const auto error=command(seat,std::move(input));require(error.empty(),"deployment "+card+" rejected: "+error);auto list=plants(c);require(!list.empty(),"deployed plant absent");const auto id=list.back().at("_pvp_id").get<std::string>();std::string owner;const auto current=b->snapshot(false);for(const auto& p:current.at("units"))if(p.at("id")==id)owner=p.value("seat",std::string{});require(owner==seat,"coop actual deployment lost seat: "+owner+" vs "+seat);
  if(card=="plant:模仿者"){b->native_set(false,id,{{"模仿cd",1.}});step();++transforms;}
  return id;
 }
 void stack(Cell c,int n){const std::string seat=n%2?"plant2":"plant";deploy(c,"plant:机枪射手",seat);deploy(c,n%3?"plant:杨桃":"plant:小喷菇",n%2?"plant":"plant2");if(n%4==0)deploy(c,"plant:模仿者",seat,"plant:机枪射手");else deploy(c,n%4==1?"plant:金盏花":"plant:豌豆射手",seat);
  const char* shells[]={"plant:南瓜头","plant:阳光藤蔓","plant:忧郁藤蔓","plant:抓人草"};if(n%5==0)deploy(c,"plant:模仿者",seat,"plant:抓人草");else deploy(c,shells[n%4],seat);
  verify(c);b->fixture_player(seat,{{"cooldowns_replace",J::object()}});const auto extra=command(seat,{{"type","deploy"},{"card","plant:坚果"},{"x",(c.x+.5)*48.},{"y",(c.y+.5)*48.}});require(!extra.empty(),"fourth body unexpectedly accepted");
 }
 void coffee(Cell c,int n){auto stack=plants(c);for(const auto& p:stack)b->native_set(false,p.at("_pvp_id"),{{"睡觉",0.}});const auto seat=n%2?"plant2":"plant";b->fixture_player(seat,{{"cooldowns_replace",J::object()}});require(command(seat,{{"type","deploy"},{"card","plant:咖啡豆"},{"x",(c.x+.5)*48.},{"y",(c.y+.5)*48.}}).empty(),"full-stack coffee rejected");for(const auto& p:plants(c))require(!p.contains("睡觉"),"coffee did not wake the whole cell");}
 void empty(Cell c,int n){for(int i=0;i<8&&!plants(c).empty();++i){const auto seat=n%2?"plant2":"plant";const bool right=(i%2)!=0;const auto error=command(seat,{{"type","shovel"},{"x",(c.x+.5)*48.},{"y",(c.y+.5)*48.},{"right",right}});require(error.empty(),"shovel rejected: "+error);step();}require(plants(c).empty(),"stack did not fully clear");}
 void terminal_deaths(){
  const Cell base{19,50},above{18,50};
  deploy(base,"plant:花盆","plant2");stack(above,103);step(2);render();empty(base,1);step(2);require(plants(above).empty(),"removing a real pot did not retire unsupported stacked plants and heads");milestones.push_back({{"stage","pot_support_removed"},{"tick",b->tick()}});
  deploy(base,"plant:水盆","plant");deploy(base,"plant:睡莲","plant2");stack(above,104);step(2);render();empty(base,0);step(2);require(plants(above).empty(),"removing a basin/lily left unsupported live stacked bodies");milestones.push_back({{"stage","basin_lily_support_removed"},{"tick",b->tick()}});
  size_t previous=0;for(const auto c:sites)previous+=plants(c).size();size_t blasts=0;
  for(size_t i=2;i<sites.size();i+=6){const auto c=sites[i];record("native_clown_detonation",{{"cell",{c.y,c.x}}});const auto id=b->spawn("zombie:小丑僵尸","zombie",(c.x+.5)*48.,(c.y+1.)*48.,-1.,false);require(bool(id),"clown death fixture spawn rejected");durable.insert(*id);b->native_set(false,*id,{{"出场",500.},{"血量",-299.}});step(3);render();++blasts;}
  size_t remaining=0;for(const auto c:sites)remaining+=plants(c).size();require(remaining<previous,"real native explosions did not reach dense plants");milestones.push_back({{"stage","native_explosion_support_and_plant_deaths"},{"blasts",blasts},{"before_plants",previous},{"after_plants",remaining},{"tick",b->tick()}});
 }
 void render(){record("application_render");auto* a=as<pm_app::C_Application>(app);const auto snapshot=b->snapshot(true);const V raw_map=getattr(h.battle,SY("map"));const auto map=J::parse(dump(raw_map.is_dict()?raw_map:callm(raw_map,SY("to_dict"),Args{})));a->a_view=val({{"phase","battle"},{"mode","coop"},{"revision",serial},{"members",{{"host","plant"},{"guest","plant2"}}},{"match_members",{{"host","plant"},{"guest","plant2"}}},{"battle",snapshot},{"map",map}});callm(app,SY("render"),Args{});++renders;
  const auto world=getattr(a->a_renderer,SY("world"),V::none());require(!world.is_none(),"Application did not create its battle WorldView");const auto error=getattr(world,SY("native_error"),V("")).str();require(error.empty(),"real WorldView caught rendering failure: "+error);
 }
 J run(int rounds){for(size_t i=0;i<sites.size();++i)stack(sites[i],int(i));step(3);render();milestones.push_back({{"stage","initial_dense"},{"tick",b->tick()},{"units",b->snapshot(false).at("units").size()}});if(mode=="terminal")terminal_deaths();
  for(int n=0;n<rounds;++n){const auto c=sites[size_t(n)%sites.size()];empty(c,n);stack(c,n+100);coffee(c,n);step(2);verify(c);if(n%8==0)render();if(n%20==0)milestones.push_back({{"round",n},{"tick",b->tick()},{"units",b->snapshot(false).at("units").size()}});}
  if(mode=="oasis"){const auto before=b->coop_map_night();require(before.has_value(),"real coop cycle was not bound");for(int i=0;i<4000&&b->coop_map_night()==before;++i)step();require(b->coop_map_night()!=before,"coop cycle did not transition");render();milestones.push_back({{"stage","coop_cycle_transition"},{"night",b->coop_map_night().value()},{"tick",b->tick()}});}
  return {{"passed",true},{"mode",mode},{"rounds",rounds},{"commands",commands},{"steps",steps},{"application_renders",renders},{"imitations",transforms},{"peak_units",peak},{"milestones",milestones},{"last",last},{"final_native",b->native_view()},{"final_rng",b->rng_state()}};
 }
};
}
int main(int argc,char** argv){if(argc!=4||!std::getenv("PVP_USERDATA"))return 2;pvz::install_crash_handler();const auto prefix=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(prefix.parent_path());SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();std::unique_ptr<Audit> a;J out;int code=0;try{a=std::make_unique<Audit>(prefix,argv[2]);out=a->run(std::stoi(argv[3]));}catch(const std::exception& e){pvz::print_last_cpp_throw(stderr);out={{"passed",false},{"error",e.what()}};if(a)out["last"]=a->last;code=1;}std::ofstream(prefix.string()+".json")<<out.dump(2);J brief=out;brief.erase("final_native");brief.erase("final_rng");std::cout<<brief.dump()<<std::endl;return code;}
