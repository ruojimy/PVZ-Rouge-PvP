#include "pg/pg.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_maps.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "ui/gen/pm_replay.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
using namespace pvz;using J=nlohmann::json;
V val(const J& j){return py::stdlib_call(SV("json.loads"),Args{V(j.dump())});}
J snapshot(V b){return J::parse(py_str(py::stdlib_call(SV("json.dumps"),Args{callm(b,SY("snapshot"),Args({},{{SY("include_map"),V(true)}}))})));}
int main(int argc,char**argv){if(argc!=2)return 2;SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();try{
 V pg=py::stdlib_module(SV("pygame"));callm(getattr(pg,SY("display")),SY("set_mode"),Args{V::tuple({V(640),V(480)})});auto h=battle_from_scenario({{"seed",7}});callm(h.battle,SY("close"),Args{});
 V tiles=V::list();for(int y=0;y<16;++y){V row=V::list();for(int x=0;x<32;++x)row.append(pm_maps::f__cell(Args{val({{"方块",y>=10?"土":"空"},{"里方块","空"}}),V::tuple({SV("空"),SV("水"),SV("花盆块"),SV("梯子块"),SV("坟墓")})}));tiles.append(row);}
 V terrain=pm_maps::new_MapSnapshot(Args({SV("家院"),V(1),SV("controlled-test-native-cells"),tiles},{{SY("spawns"),val({{"plant",{400.,480.}},{"zombie",{1000.,480.}}})},{SY("source"),SV("test-controlled-native-cells")}}));
 V decks=val({{"plant",{"plant:花盆","plant:豌豆射手"}},{"zombie",{"zombie:脑光墓碑","zombie:普通僵尸"}}});
 V rules=py::dict_of(pm_catalog::RULES,{{SV("tick_rate"),V(60)},{SV("plant_start"),V(5000)},{SV("zombie_start"),V(5000)}});
 V b=callm(pm_replay::module_ns(),SY("NativeBattle"),Args({terrain,decks,rules},{{SY("seed"),V(7)},{SY("bridge"),h.bridge},{SY("pygame"),pg}}));V rec=pm_replay::new_Recording(Args{b,V(7),decks,V::list()});
 for(int t=0;t<360;++t){if(t==0||t==10||t==120)callm(b,SY("command_input"),Args{SV("plant"),val({{"type","move"},{"seq",t+1},{"move",1},{"jump",true},{"edge",true}})});if(t==180){callm(b,SY("command_input"),Args{SV("plant"),val({{"type","deploy"},{"seq",t+1},{"card","plant:豌豆射手"},{"x",360.},{"y",456.},{"facing",1.}})});callm(b,SY("command_input"),Args{SV("zombie"),val({{"type","deploy"},{"seq",1},{"card","zombie:脑光墓碑"},{"x",600.},{"y",456.}})});}if(t==240)callm(b,SY("clear_input"),Args{SV("plant")});callm(b,SY("step"),Args{});if(t==299)std::ofstream(std::string(argv[1])+".reference.json")<<snapshot(b).dump();}
 const auto path=std::string(argv[1])+".recording.json";callm(rec,SY("export"),Args{V(path)});callm(b,SY("close"),Args{});V data=pm_replay::f_read_recording(Args{V(path)});V p=pm_replay::new_Playback(Args{data,h.bridge,pg});callm(p,SY("seek"),Args{V(300)});for(int n=0;n<50&&!getattr(p,SY("target")).is_none()&&!getattr(p,SY("error")).truthy();++n)callm(p,SY("update"),Args({V(0.)},{{SY("max_steps"),V(1000)},{SY("budget"),V(1.)}}));std::ofstream(std::string(argv[1])+".typed.json")<<snapshot(getattr(p,SY("battle"))).dump();std::cerr<<"error="<<py_str(getattr(p,SY("error")))<<std::endl;bool ok=!getattr(p,SY("error")).truthy();callm(p,SY("close"),Args{});return ok?0:1;
 }catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 2;}}
