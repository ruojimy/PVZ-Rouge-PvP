// Exercise actual SDL virtual hardware and raw SDL events through the production facade.
#include "pg/pg.h"
#include "sim/pvp/pvprt.h"
#include <cstdio>
#include <cmath>
namespace pvz::cpptests {
bool joystick_contract() {
    V pg=py::stdlib_module(V("pygame")),api=pvz::getattr(pg,Sym("joystick")),events=pvz::getattr(pg,Sym("event"));
    struct Restore {
        V api,handle;int device=-1;bool owned=false;
        ~Restore() {
            try {if(handle.has())callm(handle,Sym("quit"),Args{});}catch(const PyError&){}
            if(device>=0)SDL_JoystickDetachVirtual(device);
            try {if(owned)callm(api,Sym("quit"),Args{});}catch(const PyError&){}
        }
    } restore{api};
    int checked=0;
    auto check=[&](bool ok,const char* message){++checked;if(!ok)throw PyError("AssertionError",message);};
    try {
        restore.owned=!callm(api,Sym("get_init"),Args{}).truthy();
        if(restore.owned) {
            bool rejected=false;try{callm(api,Sym("get_count"),Args{});}catch(const PyError& e){rejected=e.kind=="error";}
            check(rejected,"uninitialized joystick count is rejected");
        }
        callm(api,Sym("init"),Args{});
        check(callm(api,Sym("get_init"),Args{}).truthy() && SDL_WasInit(SDL_INIT_JOYSTICK),"real SDL subsystem initialized");
        int count=SDL_NumJoysticks();
        restore.device=SDL_JoystickAttachVirtual(SDL_JOYSTICK_TYPE_GAMECONTROLLER,2,2,1);
        check(restore.device>=0,"SDL virtual joystick attached");
        check(callm(api,Sym("get_count"),Args{})==V(count+1),"enumeration sees the actual attached SDL device");
        restore.handle=callm(api,Sym("Joystick"),Args{V(restore.device)});
        check(py_is(restore.handle,callm(api,Sym("Joystick"),Args{V(restore.device)})),"duplicate opens preserve handle identity");
        int instance=int(callm(restore.handle,Sym("get_instance_id"),Args{}).num());
        SDL_Joystick* handle=SDL_JoystickFromInstanceID(instance);
        check(handle!=nullptr,"instance id resolves to a live SDL handle");
        check(callm(restore.handle,Sym("get_init"),Args{}).truthy(),"opened handle is initialized");
        check(callm(restore.handle,Sym("get_numaxes"),Args{})==V(2) && callm(restore.handle,Sym("get_numhats"),Args{})==V(1),"control counts come from SDL");
        check(SDL_JoystickSetVirtualAxis(handle,0,16384)==0 && SDL_JoystickSetVirtualButton(handle,0,1)==0 && SDL_JoystickSetVirtualHat(handle,0,SDL_HAT_LEFTUP)==0,"SDL virtual control state set");
        SDL_JoystickUpdate();
        check(callm(restore.handle,Sym("get_axis"),Args{V(0)})==V(.5),"axis reads actual SDL state");
        check(callm(restore.handle,Sym("get_button"),Args{V(0)})==V(1),"button reads actual SDL state");
        check(callm(restore.handle,Sym("get_hat"),Args{V(0)})==V::tuple({V(-1),V(1)}),"hat reads actual SDL state");
        bool rejected=false;try{callm(restore.handle,Sym("get_axis"),Args{V(2)});}catch(const PyError& e){rejected=e.kind=="error";}
        check(rejected,"out-of-range controls are rejected");
        callm(events,Sym("clear"),Args{});
        SDL_Event raw{};raw.type=SDL_JOYHATMOTION;raw.jhat.which=instance;raw.jhat.hat=0;raw.jhat.value=SDL_HAT_RIGHTDOWN;
        check(SDL_PushEvent(&raw)==1,"raw SDL hat event queued");
        raw={};raw.type=SDL_JOYAXISMOTION;raw.jaxis.which=instance;raw.jaxis.axis=1;raw.jaxis.value=-32768;
        check(SDL_PushEvent(&raw)==1,"raw SDL axis event queued");
        raw={};raw.type=SDL_JOYBUTTONUP;raw.jbutton.which=instance;raw.jbutton.button=1;
        check(SDL_PushEvent(&raw)==1,"raw SDL button event queued");
        V rows=callm(events,Sym("get"),Args{V::tuple({V(SDL_JOYHATMOTION),V(SDL_JOYAXISMOTION),V(SDL_JOYBUTTONUP)})});
        check(rows.len()==3,"all three raw SDL events reach the native game queue");
        if(rows.len()==3) {
            V hat=rows.idx(0),axis=rows.idx(1),button=rows.idx(2);
            check(pvz::getattr(hat,Sym("joy"))==V(restore.device) && pvz::getattr(hat,Sym("instance_id"))==V(instance),"event keeps device index and instance id distinct");
            check(pvz::getattr(hat,Sym("value"))==V::tuple({V(1),V(-1)}),"event hat directions match pygame convention");
            check(std::abs(pvz::getattr(axis,Sym("value")).num()-(-32768./32767.))<1e-12,"event axis normalization matches pygame event contract");
            check(pvz::getattr(button,Sym("button"))==V(1),"button event preserves button index");
        }
        check(callm(events,Sym("event_name"),Args{pvz::getattr(pg,Sym("WINDOWHIDDEN"))})==V("WindowHidden"),"hidden window event retains its name");
        check(callm(events,Sym("event_name"),Args{pvz::getattr(pg,Sym("JOYDEVICEADDED"))})==V("JoyDeviceAdded"),"joystick add event has its actual name");
        callm(restore.handle,Sym("quit"),Args{});
        check(!callm(restore.handle,Sym("get_init"),Args{}).truthy(),"handle close clears actual initialization state");
        callm(restore.handle,Sym("init"),Args{});
        check(callm(restore.handle,Sym("get_init"),Args{}).truthy(),"explicit reinitialization reopens the SDL handle");
        printf("JOYSTICK CONTRACT: %d checks, 0 failures\n",checked);return true;
    } catch(const PyError& e) {fprintf(stderr,"JOYSTICK CONTRACT FAILED after %d checks: %s\n",checked,e.what());return false;}
}
}
