// Visible reproduction against the linked production runtime, isolated userdata.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "ui/gen/pm_app.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <fstream>
#include <cstdlib>
using namespace pvz;
int main(int argc,char**argv){
 if(argc!=3||!std::getenv("PVP_USERDATA"))return 2;
 auto out=u8p(argv[1]);std::filesystem::create_directories(out);std::string path=argv[2];
 nlohmann::json report;report["frames"]=nlohmann::json::array();int last=-1;bool started=false;
 auto save=[&]{std::ofstream f(out/"report.json");f<<report.dump(2);};
 try{
 SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");py::g_real_clock=true;pg::install_pygame();init_pvp_modules();pm_app::init();
 V cb=V::func([&](const Args&A){V app=A.pos.at(0);int frame=int(A.pos.at(1).num());
 if(frame==3){callm(app,SY("action"),Args{V::tuple({SV("replay_open"),V(path)})});
 V pb=getattr(app,SY("playback"));if(pb.is_none())throw std::runtime_error(py_str(rd(getattr(app,SY("state")),SV("message"))));
 setitem(getattr(app,SY("state")),SV("replay_camera_mode"),SV("zombie"));setitem(getattr(app,SY("state")),SV("replay_zoom"),V(.65));
 callm(pb,SY("seek"),Args{V(1660)});callm(getattr(getattr(app,SY("pg")),SY("display")),SY("set_caption"),Args{SV("PVZ bug reproduction - original R8 replay - isolated saves")});}
 if(frame<4)return V::none();V pb=getattr(app,SY("playback"));V battle=getattr(pb,SY("battle"));int tick=int(getattr(battle,SY("tick")).num());
 if(!started && getattr(pb,SY("target")).is_none()){started=true;setattr(pb,SY("playing"),V(true));}
 if(started&&tick!=last){last=tick;V r=getattr(app,SY("renderer")),world=getattr(r,SY("world"));V snap=callm(battle,SY("snapshot"),Args{});
 std::string error=py_str(getattr(world,SY("native_error"),SV("")));
 report["frames"].push_back({{"tick",tick},{"native_error",error},{"audit_error",py_str(py::m_get(snap,SV("audit_error"),SV("")))},{"commands",py::m_get(py::m_get(snap,SV("native_frame"),V::dict()),SV("commands"),V::list()).len()}});
 if(tick%30<2||!error.empty()){callm(getattr(getattr(app,SY("pg")),SY("image")),SY("save"),Args{getattr(r,SY("screen")),V(p8(out/("frame-"+std::to_string(tick)+".png")))});save();}
 if(tick>=2450){report["completed"]=true;setattr(app,SY("running"),V(false));save();}}
 return V::none();});pm_app::f_run(Args({},{{SY("auto_test"),cb}}));
 }catch(const std::exception&e){report["fatal"]=e.what();save();return 1;}save();return 0;
}
