// Exercise the real SDL button -> input -> render order, not an out-of-frame action call.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "core/trace.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "ui/gen/pm_app.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
#include <cstdlib>
using namespace pvz;
using J=nlohmann::json;
static void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
static void click(const V& app,const char* name,const V& parameter=V()){
    V action=parameter.has()?V::tuple({V(name),parameter}):V::tuple({V(name)});
    V position;
    const V controls=getattr(getattr(app,SY("renderer")),SY("controls"));
    for(const V& row:py::iter_list(controls).items())if(row.idx(1)==action){position=getattr(row.idx(0),SY("center"));break;}
    require(position.has(),"requested performance button is not drawn");
    const V pg=getattr(app,SY("pg")),events=getattr(pg,SY("event"));
    for(const char* type:{"MOUSEBUTTONDOWN","MOUSEBUTTONUP"}){
        V event=callm(events,SY("Event"),Args({getattr(pg,Sym(type))},{{SY("pos"),position},{SY("button"),V(1)}}));
        callm(events,SY("post"),Args{event});
    }
}
int main(int argc,char** argv){
    if(argc!=2||!std::getenv("PVP_USERDATA")){std::cerr<<"report path and isolated PVP_USERDATA required\n";return 2;}
    SDL_SetMainReady();install_crash_handler();gil::init();data::set_data_dir("extract/data");py::g_real_clock=true;pg::install_pygame();
    J cases=J::array();int failed=0;
    try{init_pvp_modules();pm_app::init();
        for(bool detail:{false,true}){
            J row={{"initial_detail",detail}};
            std::weak_ptr<PyObj> retired;
            try{
                V callback=V::func([&](const Args& args){
                    const V app=args.pos.at(0);const int frame=int(args.pos.at(1).num());
                    V state=getattr(app,SY("state")),prof=getattr(app,SY("profiler"));
                    if(frame==1)callm(app,SY("action"),Args{V::tuple({V("menu"),V("performance")})});
                    if(frame==3||frame==14)click(app,"perf_start",V(detail));
                    if(frame==4||frame==7||frame==10||frame==15){
                        require(!prof.is_none(),"button did not start recording");
                        require(getattr(prof,SY("frame_count")).num()==0.,"partial startup frame was recorded");
                        require(getattr(prof,SY("detail"))==V(frame==7||frame==10?!detail:detail),"recording mode did not switch");
                    }
                    if(frame==5||frame==8||frame==16)require(getattr(prof,SY("frame_count")).num()==1.,"first complete frame was not recorded");
                    if(frame==6){retired=prof.box->inst;click(app,"perf_start",V(!detail));}
                    if(frame==7)require(retired.expired(),"replaced profiler retained a self cycle");
                    if(frame==9){click(app,"perf_start",V(detail));click(app,"perf_start",V(!detail));}
                    if(frame==11)click(app,"perf_export");
                    if(frame==12||frame==17){retired=prof.box->inst;click(app,"perf_stop");}
                    if(frame==13){
                        require(prof.is_none(),"stop button retained profiler");
                        require(retired.expired(),"stopped profiler retained a self cycle");
                        J saved;std::ifstream(u8p(py_str(py::m_get(state,V("performance_path")))) )>>saved;
                        require(saved.at("frames").get<int>()>0,"export has no complete samples");
                        row["exported_frames"]=saved.at("frames");
                    }
                    if(frame==18){require(prof.is_none(),"second stop failed");require(retired.expired(),"restarted profiler retained a self cycle");setattr(app,SY("running"),V(false));}
                    return V::none();
                });
                pm_app::f_run(Args({},{{SY("auto_test"),callback}}));row["passed"]=true;
            }catch(const std::exception& error){row["passed"]=false;row["error"]=error.what();++failed;print_last_cpp_throw(stderr);}
            cases.push_back(row);std::cerr<<row.dump()<<'\n';
        }
    }catch(const std::exception& error){cases.push_back({{"passed",false},{"error",error.what()}});++failed;}
    std::ofstream(u8p(argv[1]))<<J{{"cases",cases},{"failed",failed},{"backend","real SDL event queue and Application::step/render"}}.dump(2)<<'\n';
    return failed?1:0;
}
