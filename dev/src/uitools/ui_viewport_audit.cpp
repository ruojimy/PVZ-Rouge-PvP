// Bounded SDL touch/viewport audit; run with isolated PVP_USERDATA.
// ui_viewport_audit report.json width height ui_scale
// This exercises the desktop SDL facade with Android touch state, not JNI/GPU.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/pvprt.h"
#include "sim/pvp/battle_api.h"
#include "ui/gen/pm_app.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <cmath>
#include <cstdlib>
#include <cstdio>
#include <fstream>
#include <stdexcept>
#include <string>
using namespace pvz;
using J=nlohmann::json;
namespace pvz { void install_crash_handler(); }
namespace {
V tuple(std::initializer_list<V> values){return V::tuple(values);}
void require(bool pass,const std::string& text){if(!pass)throw std::runtime_error(text);}
J js(const V& value){try{return J::parse(dump(value));}catch(...){return py_str(value);}}
struct Audit {
    V app;int width=1280,height=720,finger=0;double scale=1;
    J checks=J::array(),events=J::array();
    V state(){return getattr(app,SY("state"));}
    V view(){return getattr(app,SY("view"));}
    V room(){return getattr(app,SY("room"));}
    V touch(){return getattr(app,SY("touch"));}
    V revision(){return getattr(room(),SY("revision"));}
    V screen(){return py::m_get(state(),SV("screen"));}
    V size(){return callm(getattr(app,SY("surface")),SY("get_size"),Args{});}
    J snap(){return {{"screen",js(screen())},{"revision",js(py::m_get(view(),SV("revision")))},
        {"pointer_capture",js(getattr(app,SY("pointer_capture")))},{"fingers",js(getattr(touch(),SY("fingers")))},
        {"physical_size",js(size())},{"scale_x",js(getattr(app,SY("scale_x")))},{"scale_y",js(getattr(app,SY("scale_y")))},
        {"pending_ban",js(py::m_get(state(),SV("pending_ban")))},{"focused",js(py::m_get(state(),SV("focused")))}};}
    void check(const char* id,bool pass,const std::string& detail=""){
        checks.push_back({{"id",id},{"passed",pass},{"detail",detail},{"snapshot",snap()}});
        fprintf(stderr,"%s %s %s\n",pass?"PASS":"FAIL",id,detail.c_str());fflush(stderr);
    }
    void render(){callm(app,SY("render"),Args{});}
    void step(double dt){require(dt<=.25,"Audit dt exceeds normal frame cap");callm(app,SY("step"),Args{V(dt)});}
    V rect(V action){render();V controls=getattr(getattr(app,SY("renderer")),SY("controls"));
        for(const V& c:py::iter_list(controls).items())if(c.idx(1)==action)return c.idx(0);
        throw std::runtime_error("Missing control: "+dump(action));}
    V normalized(V action){V p=getattr(rect(action),SY("center")),wh=size();
        double x=p.idx(0).num()/getattr(app,SY("scale_x")).num()/wh.idx(0).num();
        double y=p.idx(1).num()/getattr(app,SY("scale_y")).num()/wh.idx(1).num();
        require(x>=0&&x<1&&y>=0&&y<1,"Control center outside physical surface: "+dump(action));
        return tuple({V(x),V(y)});}
    void push(SDL_Event& event,const char* label){require(SDL_PushEvent(&event)==1,"SDL_PushEvent rejected event");
        callm(app,SY("handle_events"),Args{});events.push_back({{"label",label},{"sdl_type",event.type},{"snapshot",snap()}});}
    void finger_event(Uint32 type,V pos,const char* label){SDL_Event e{};e.type=type;e.tfinger.touchId=88;
        e.tfinger.fingerId=finger;e.tfinger.x=float(pos.idx(0).num());e.tfinger.y=float(pos.idx(1).num());
        e.tfinger.pressure=type==SDL_FINGERUP?0.f:1.f;push(e,label);}
    V down(V action){V p=normalized(action);++finger;finger_event(SDL_FINGERDOWN,p,"finger_down");return p;}
    void up(V p){finger_event(SDL_FINGERUP,p,"finger_up");}
    void click(V action){V p=down(action);step(.016);up(p);render();}
    void lifecycle(Uint32 type,const char* label){SDL_Event e{};e.type=type;push(e,label);}
    void geometry(int w,int h){V pg=getattr(app,SY("pg"));V surface=callm(getattr(pg,SY("display")),SY("set_mode"),Args{tuple({V(w),V(h)})});
        setattr(app,SY("surface"),surface);callm(app,SY("handle_events"),Args{});setitem(state(),SV("ui_scale"),V(scale));
        callm(app,SY("apply_scale"),Args{});render();}
    void run(){
        setitem(state(),SV("touch_mode"),V(true));setitem(state(),SV("android"),V(true));setattr(app,SY("android"),V(true));
        geometry(width,height);
        check("requested_physical_surface",size()==tuple({V(width),V(height)}),"Desktop SDL canvas; normalized touch coordinates remain in [0,1)");
        click(tuple({SV("menu"),SV("local")}));check("create_local_from_touch",!room().is_none());
        click(tuple({SV("confirm_map")}));check("confirm_map_from_touch",py::m_get(view(),SV("phase"))==SV("banning"));
        V card=tuple({SV("card"),SV("zombie:稻草人")}),advance=tuple({SV("advance")});
        (void)normalized(card);check("draft_card_on_surface",true);
        V original=revision();V p=down(card);step(.245);step(.245);
        check("hold_049_does_not_submit",revision()==original&&screen()==SV("room")&&!py::m_get(state(),SV("pending_ban")).truthy());
        up(p);render();(void)normalized(advance);check("release_049_previews",py::m_get(state(),SV("pending_ban"))==card.idx(1)&&revision()==original,
            "After the preview, the confirmation control is present and its center is inside the physical surface");
        p=down(card);step(.25);step(.25);step(.01);
        check("hold_051_opens_detail",screen()==SV("almanac")&&py::m_get(state(),SV("detail"))==card.idx(1)&&revision()==original,
            "0.5s threshold is the documented right-click detail gesture, not a card confirmation");
        up(p);check("long_release_does_not_submit",screen()==SV("almanac")&&revision()==original);
        click(tuple({SV("menu"),SV("back")}));check("detail_back_from_touch",screen()==SV("room"));
        p=down(advance);step(.016);
        V pg=getattr(app,SY("pg"));(void)callm(getattr(pg,SY("display")),SY("set_mode"),Args{tuple({V(width-16),V(height)})});
        SDL_Event e{};e.type=SDL_WINDOWEVENT;e.window.event=SDL_WINDOWEVENT_SIZE_CHANGED;e.window.data1=width-16;e.window.data2=height;
        push(e,"window_size_changed");
        check("resize_clears_capture",!getattr(app,SY("pointer_capture")).truthy()&&!getattr(touch(),SY("fingers")).truthy());
        up(p);check("resize_stale_up_is_ignored",revision()==original);
        geometry(width,height);click(advance);
        check("card_confirmation_advances",revision()!=original&&py::in(card.idx(1),getattr(room(),SY("bans"))));
        for(int i=0;i<12;++i)step(.016);
        check("post_confirmation_render_frames",true,"12 real step/render frames, including the cold zombie-secret/taco page");
        V before_background=revision();p=down(tuple({SV("skip_ban")}));step(.016);lifecycle(SDL_APP_WILLENTERBACKGROUND,"app_background");
        bool background_unfocused=!py::m_get(state(),SV("focused")).truthy();
        check("background_clears_capture",!getattr(app,SY("pointer_capture")).truthy()&&!getattr(touch(),SY("fingers")).truthy()&&background_unfocused);
        up(p);check("background_stale_up_is_ignored",revision()==before_background);
        lifecycle(SDL_APP_DIDENTERFOREGROUND,"app_foreground");
        check("foreground_restores_focus",background_unfocused&&py::m_get(state(),SV("focused")).truthy(),
            "Requires the prior SDL background event to have actually removed focus; already-focused is insufficient");
        const Uint32 types[]={SDL_APP_WILLENTERBACKGROUND,SDL_APP_DIDENTERBACKGROUND,SDL_APP_WILLENTERFOREGROUND,
            SDL_APP_DIDENTERFOREGROUND,SDL_RENDER_TARGETS_RESET,SDL_RENDER_DEVICE_RESET};
        const char* ids[]={"converter_will_background","converter_did_background","converter_will_foreground",
            "converter_did_foreground","converter_targets_reset","converter_device_reset"};
        V event_module=getattr(getattr(app,SY("pg")),SY("event"));
        for(int i=0;i<6;++i){
            SDL_Event event{};event.type=types[i];require(SDL_PushEvent(&event)==1,"SDL rejected converter probe");
            V converted=callm(event_module,SY("get"),Args{});bool found=false;
            for(const V& value:converted.items())if(getattr(value,SY("type"))==V(double(types[i])))found=true;
            check(ids[i],found,"Direct raw-SDL to pygame Event conversion; render probes do not claim real GPU loss recovery");
        }
    }
};
}
int main(int argc,char** argv){
    if(argc!=5)return 2;SDL_SetMainReady();install_crash_handler();gil::init();data::set_data_dir("extract/data");py::g_real_clock=true;
    require(std::getenv("PVP_USERDATA")!=nullptr,"Isolated PVP_USERDATA is required");
    pg::install_pygame();init_pvp_modules();pm_app::init();Audit audit;audit.width=std::stoi(argv[2]);audit.height=std::stoi(argv[3]);audit.scale=std::stod(argv[4]);
    std::string fatal;try{V callback=V::func([&](const Args& args)->V{if(int(args.pos.at(1).num())!=2)return V::none();audit.app=args.pos.at(0);
        audit.run();setattr(audit.app,SY("running"),V(false));return V::none();});pm_app::f_run(Args({},{{SY("auto_test"),callback}}));
    }catch(const std::exception& e){fatal=e.what();fprintf(stderr,"FATAL %s\n",fatal.c_str());}
    int passed=0;for(const auto& c:audit.checks)if(c["passed"].get<bool>())++passed;
    J report={{"passed",fatal.empty()&&passed==22},{"planned",22},{"completed",audit.checks.size()},{"pass_count",passed},
        {"fail_count",audit.checks.size()-passed},{"unrun_count",22-audit.checks.size()},{"fatal",fatal},
        {"physical_size_requested",{audit.width,audit.height}},{"ui_scale",audit.scale},{"input","SDL_FINGERDOWN/UP via Application.handle_events"},
        {"platform_scope","Windows SDL facade with Android touch state; Android JNI/GPU/OS physical acceptance remains separate"},
        {"checks",audit.checks},{"events",audit.events}};
    std::ofstream out(u8p(argv[1]),std::ios::binary);out<<report.dump(2)<<'\n';out.close();return report["passed"].get<bool>()&&!out.fail()?0:1;
}
