// Reproduce reported gameplay through the production app, with isolated saves.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "ui/gen/pm_app.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <chrono>
#include <fstream>
#include <cstdio>
#include <cstdlib>
using namespace pvz;
using J=nlohmann::json;
int main(int argc,char**argv) {
    if(argc!=3 || !std::getenv("PVP_USERDATA"))return 2;
    auto out=u8p(argv[1]);std::filesystem::create_directories(out);
    std::string replay=argv[2];J report;int code=0;
    auto save=[&](){std::ofstream f(out/"report.json",std::ios::binary);f<<report.dump(2);};
    try {
        SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");py::g_real_clock=true;
        pg::install_pygame();init_pvp_modules();pm_app::init();
        V cb=V::func([&](const Args&A){
            V app=A.pos.at(0);if(A.pos.at(1).num()!=3)return V::none();
            V renderer=getattr(app,SY("renderer")), pg=getattr(app,SY("pg"));
            report["asset_dir"]=py_str(getattr(renderer,SY("asset_dir")));
            for(const char* name:{"石化火炬","石化火炬-蓝火","石化火炬-桩","火炬树桩-秃"}) {
                V image=callm(renderer,SY("artwork"),Args{V(name)});
                report["artwork"][name]=!image.is_none();
                if(!image.is_none())callm(getattr(pg,SY("image")),SY("save"),Args{image,V(p8(out/u8p(std::string(name)+".png")))});
            }
            V audio=getattr(app,SY("game_audio"));
            report["audio_root"]=py_str(getattr(audio,SY("root")));
            report["sound_files"]=getattr(audio,SY("files")).len();
            report["mixer"]=dump(callm(getattr(pg,SY("mixer")),SY("get_init"),Args{}));
            report["sound_load_failures"]=J::array();
            for(auto& kv:getattr(audio,SY("files")).kv()) {
                try {V sound=callm(getattr(pg,SY("mixer")),SY("Sound"),Args{py::str(kv.second)});
                    if(callm(sound,SY("get_length"),Args{}).num()<=0)report["sound_load_failures"].push_back({{"name",py_str(kv.first)},{"error","empty sound"}});
                }catch(const std::exception&e){report["sound_load_failures"].push_back({{"name",py_str(kv.first)},{"error",e.what()}});}
            }
            save();
            callm(app,SY("action"),Args{V::tuple({SV("replay_open"),V(replay)})});
            V pb=getattr(app,SY("playback"));if(pb.is_none())throw std::runtime_error("Replay failed to open");
            setitem(getattr(app,SY("state")),SV("replay_camera_mode"),SV("plant"));
            setitem(getattr(app,SY("state")),SV("zoom"),V(0.65));
            V b=getattr(pb,SY("battle"));int ticks=int(rd(getattr(pb,SY("data")),SV("ticks")).num());
            callm(pb,SY("seek"),Args{V(ticks)});
            auto start=std::chrono::steady_clock::now();
            auto milliseconds=[](auto t){return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-t).count();};
            J step_ms=J::array();
            report["frames"]=J::array();
            for(int i=0;i<=ticks;++i) {
                int tick=int(getattr(b,SY("tick")).num());
                int stride=std::getenv("PVZ_AUDIT_STRIDE")?std::atoi(std::getenv("PVZ_AUDIT_STRIDE")):25;
                if(tick%stride==0 || tick==ticks || tick==2091 || tick==2093 || tick==2100 || tick==2130) {
                    auto render_start=std::chrono::steady_clock::now();callm(app,SY("render"),Args{});double app_ms=milliseconds(render_start);
                    V world=getattr(renderer,SY("world")), snap=callm(b,SY("snapshot"),Args({},{{SY("include_map"),V(true)}}));
                    V screen=getattr(renderer,SY("screen"));
                    auto recipe_start=std::chrono::steady_clock::now();callm(world,SY("render"),Args{screen,snap,callm(screen,SY("get_rect"),Args{}),SV("plant"),getattr(app,SY("state"))});double recipe_ms=milliseconds(recipe_start);
                    V image_api=getattr(pg,SY("image"));
                    std::string reference=py::bytes_data(callm(image_api,SY("tobytes"),Args{getattr(renderer,SY("screen")),SV("RGBA")}));
                    setattr(world,SY("local_pixels"),getattr(getattr(b,SY("recorder")),SY("latest_pixels")));
                    auto local_start=std::chrono::steady_clock::now();callm(world,SY("render"),Args{screen,snap,callm(screen,SY("get_rect"),Args{}),SV("plant"),getattr(app,SY("state"))});double local_ms=milliseconds(local_start);
                    std::string local=py::bytes_data(callm(image_api,SY("tobytes"),Args{getattr(renderer,SY("screen")),SV("RGBA")}));
                    std::string error=py_str(getattr(world,SY("native_error"),SV("")));
                    try { callm(getattr(world,SY("_native_replay")),SY("render"),Args({screen,rd(snap,SV("native_frame"))},{{SY("point"),getattr(world,SY("point"))},{SY("scale"),rd(getattr(world,SY("camera")),V(2))},{SY("clip"),callm(screen,SY("get_rect"),Args{})},{SY("layer"),SV("foreground")}})); }
                    catch(const std::exception&e){error=e.what();}
                    J row={{"tick",tick},{"render_error",error},{"audit_error",py_str(py::m_get(snap,SV("audit_error"),SV("")))},
                        {"commands",py::m_get(py::m_get(snap,SV("native_frame"),V::dict()),SV("commands"),V::list()).len()}};
                    row["local_equals_recipe"]=local==reference;
                    row["app_render_ms"]=app_ms;row["recipe_world_ms"]=recipe_ms;row["local_world_ms"]=local_ms;
                    row["local_pixels"]=!getattr(world,SY("local_pixels")).is_none();
                    report["frames"].push_back(row);
                    if(!error.empty() || local!=reference || tick%500==0 || tick==ticks || (tick>=2091 && tick<=2130)) {
                        std::ofstream f(out/("state-"+std::to_string(tick)+".json"),std::ios::binary);f<<dump(snap);
                        callm(getattr(pg,SY("image")),SY("save"),Args{getattr(renderer,SY("screen")),V(p8(out/("frame-"+std::to_string(tick)+".png")))});
                    }
                    setattr(world,SY("local_pixels"),V::none());
                    fprintf(stderr,"tick=%d commands=%zu error=%s\n",tick,size_t(row["commands"]),error.c_str());fflush(stderr);save();
                    if(!error.empty() || local!=reference){code=1;break;}
                }
                if(tick==ticks)break;
                auto step_start=std::chrono::steady_clock::now();callm(pb,SY("update"),Args({V(0)},{{SY("max_steps"),V(1)},{SY("budget"),V(1)}}));step_ms.push_back(milliseconds(step_start));
                if(getattr(pb,SY("error")).truthy()){
                    V legacy=py::deepcopy(callm(b,SY("snapshot"),Args({},{{SY("include_map"),V(true)}})));
                    for(const auto& command:rd(rd(legacy,SV("native_frame")),SV("commands")).items())if(py::m_get(command,SV("primitive"))==SV("line"))setitem(rd(command,SV("args")),V(3),V());
                    report["legacy_missing_width_hash"]=py_str(pm_catalog::f_digest(Args{legacy}));
                    report["failed_tick"]=getattr(b,SY("tick")).num();
                    for(const auto& op:rd(getattr(pb,SY("data")),SV("operations")).items())if(rd(op,SV("tick"))==getattr(b,SY("tick"))&&rd(op,SV("kind"))==SV("check"))report["expected_hash"]=py_str(rd(op,SV("sha256")));
                    throw std::runtime_error(py_str(getattr(pb,SY("error"))));
                }
            }
            report["elapsed_seconds"]=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
            report["step_ms"]=step_ms;
            report["verified"]=getattr(pb,SY("verified")).truthy();
            report["final_tick"]=getattr(b,SY("tick")).num();
            callm(pb,SY("close"),Args{});setattr(app,SY("playback"),V::none());
            setattr(app,SY("running"),V(false));save();return V::none();
        });
        pm_app::f_run(Args({},{{SY("auto_test"),cb}}));
    }catch(const std::exception&e){report["fatal"]=e.what();code=1;}
    report["exit_code"]=code;save();return code;
}
