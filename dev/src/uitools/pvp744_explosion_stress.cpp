#include "pvp742_guest_memory_fixture.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "ui/gen/pm_world_view.h"
#include "pg/render_stats.h"
#include "sim/typed/native_frame.h"
using namespace pvz;
using J=nlohmann::json;
int main(int argc,char** argv){
 if(argc<2)return 2;auto output=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(output);
 env_set_u8("PVP_USERDATA",p8(output/"userdata"));env_set_u8("PVP742_SURFACE_MEMORY","1");env_set_u8("SDL_VIDEODRIVER","dummy");env_set_u8("SDL_AUDIODRIVER","dummy");
 SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 J records=J::array();int failed=0;const int amount=argc>2?std::stoi(argv[2]):32;
 for(bool charmed:{false,true})for(const std::string name:{"小丑僵尸","辣椒僵尸","毁灭菇僵尸","mixed"}){
  if(argc>3&&(name!=(std::string(argv[3])=="chili"?"辣椒僵尸":argv[3])||charmed))continue;
  J result={{"kind",name},{"count",amount},{"alternating_charm",charmed}};try{
   auto h=battle_from_scenario({{"fixture_flat",true},{"seed",744},{"night",true},{"durable_heroes",true}});
   auto terrain=py::json_loads(V(dump(getattr(h.battle,SY("map")))));
   auto cold=typed72app::export_cold(h.battle,744.);auto s=typed72app::Session::create(std::move(cold),"explosion-stress");
   V screen=pg::new_surface(960,640,true),world=pm_world_view::new_WorldView(Args{pg::pygame_module(),h.bridge});
   std::vector<std::string> ids;for(int i=0;i<amount;++i){const std::string kind=name=="mixed"?std::vector<std::string>{"小丑僵尸","辣椒僵尸","毁灭菇僵尸"}[i%3]:name;
    auto id=s->spawn("zombie:"+kind,"zombie",2000.+(i%8)*12.,864.,1.,false);if(!id)throw std::runtime_error("spawn failed");ids.push_back(*id);
    J values={{"血量",kind=="小丑僵尸"?-299.:0.}};if(charmed&&i%2==0)values["魅惑"]=0.;s->native_set(false,*id,values);
   }
   size_t peak_entities=0,peak_commands=0,peak_dropped=0;uint64_t peak_private=0;int rendered=0;
   for(int tick=0;tick<(argc>4?std::stoi(argv[4]):180);++tick){s->step();auto snap=s->snapshot(true,true);peak_commands=std::max(peak_commands,snap["native_frame"]["commands"].size());peak_dropped=std::max(peak_dropped,s->native_frame().dropped_commands);
    if(tick%4==0){auto native=s->native_view();peak_entities=std::max(peak_entities,native["g"]["实体"].size());
     V v=py::json_loads(V(snap.dump())),settings=py::json_loads(V(J{{"zoom",1.},{"world_quality","native"},{"replay_camera",{2136.,800.}}}.dump()));
     setitem(terrain,V("tiles"),py::json_loads(V(s->map_tiles().dump())));
     callm(world,SY("render"),Args{screen,v,V::tuple({V(0),V(0),V(960),V(640)}),V("plant"),settings,terrain,V(true)});
     if(getattr(world,SY("camera")).is_none())throw std::runtime_error("renderer did not enter world drawing");
     peak_private=std::max(peak_private,guest_memory_audit::private_bytes());
     if(getattr(world,SY("native_error")).truthy())throw std::runtime_error(py_str(getattr(world,SY("native_error"))));++rendered;
     if(tick==4)callm(pg::image_module(),SY("save"),Args{screen,V(p8(output/u8p(name+(charmed?"-charmed":"")+".png")))});
    }
   }
   if(peak_entities==0)throw std::runtime_error("fixture produced no explosion entities");
   result.update({{"passed",true},{"peak_entities",peak_entities},{"peak_commands",peak_commands},{"peak_dropped_visuals",peak_dropped},{"rendered_frames",rendered},{"surface_peak_bytes",pg::surface_memory_stats().peak_owned_bytes},{"private_peak_bytes",peak_private}});
   callm(h.battle,SY("close"),Args{});
  }catch(const std::exception& e){result["passed"]=false;result["error"]=e.what();++failed;}
  records.push_back(result);std::cerr<<result.dump()<<std::endl;std::ofstream(output/"results.json")<<J{{"failures",failed},{"checks",records}}.dump(2);
 }
 return failed?1:0;
}
