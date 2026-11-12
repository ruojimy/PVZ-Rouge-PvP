// SDL-backed pygame joystick operations used by the native menu controller owner.
#include "pg/pg.h"
#include <algorithm>
#include <cmath>
#include <vector>
namespace pvz::pg {
namespace {
struct Joystick;
std::vector<std::weak_ptr<Joystick>> handles;
void require_subsystem() {
    if(!SDL_WasInit(SDL_INIT_JOYSTICK))throw PyError("error","joystick system not initialized");
}
void arity(const Args& a,size_t count) {
    if(a.pos.size()!=count || !a.kw.empty())throw PyError("TypeError","incorrect joystick argument count");
}
struct Joystick : PyObj {
    SDL_Joystick* handle=nullptr;
    int instance=-1;
    int index;
    explicit Joystick(int i):index(i){}
    ~Joystick() override { close(); }
    const char* type_name() const override { return "Joystick"; }
    void close() { if(handle) { if(SDL_WasInit(SDL_INIT_JOYSTICK) && SDL_JoystickFromInstanceID(instance)==handle)SDL_JoystickClose(handle);handle=nullptr; } }
    void open() {
        require_subsystem();
        if(!handle)handle=SDL_JoystickOpen(index);
        if(!handle)throw PyError("error",SDL_GetError());
        instance=SDL_JoystickInstanceID(handle);
    }
    SDL_Joystick* checked() { require_subsystem();if(!handle)throw PyError("error","Joystick not initialized");return handle; }
    bool call_method(Sym name,const Args& a,V& out) override {
        const auto& n=name.str();
        if(n=="init") { arity(a,0);open();out=V::none();return true; }
        if(n=="quit") { arity(a,0);require_subsystem();close();out=V::none();return true; }
        if(n=="get_init") { arity(a,0);out=V(handle!=nullptr);return true; }
        if(n=="get_id") { arity(a,0);out=V(index);return true; }
        if(n=="get_instance_id") { arity(a,0);out=V(SDL_JoystickInstanceID(checked()));return true; }
        if(n=="get_name") { arity(a,0);const char* value=SDL_JoystickName(checked());out=V(value?value:"");return true; }
        if(n=="get_guid") { arity(a,0);char value[33];SDL_JoystickGetGUIDString(SDL_JoystickGetGUID(checked()),value,sizeof value);out=V(value);return true; }
        if(n=="get_numaxes") { arity(a,0);out=V(SDL_JoystickNumAxes(checked()));return true; }
        if(n=="get_numbuttons") { arity(a,0);out=V(SDL_JoystickNumButtons(checked()));return true; }
        if(n=="get_numhats") { arity(a,0);out=V(SDL_JoystickNumHats(checked()));return true; }
        if(n=="get_axis" || n=="get_button" || n=="get_hat") {
            arity(a,1);double value=a.pos[0].num();
            if(value!=std::floor(value))throw PyError("TypeError","joystick index must be an integer");
            auto* h=checked();int limit=n=="get_axis"?SDL_JoystickNumAxes(h):(n=="get_button"?SDL_JoystickNumButtons(h):SDL_JoystickNumHats(h));
            if(value<0 || value>=limit)throw PyError("error","Invalid joystick control index");
            int i=int(value);
            if(n=="get_axis")out=V(SDL_JoystickGetAxis(h,i)/32768.0);
            else if(n=="get_button")out=V(int(SDL_JoystickGetButton(h,i)));
            else {int v=SDL_JoystickGetHat(h,i);out=V::tuple({V(v&SDL_HAT_RIGHT?1:(v&SDL_HAT_LEFT?-1:0)),V(v&SDL_HAT_UP?1:(v&SDL_HAT_DOWN?-1:0))});}
            return true;
        }
        return false;
    }
    V method(Sym name) override {
        const auto& n=name.str();
        if(n!="init" && n!="quit" && n!="get_init" && n!="get_id" && n!="get_instance_id" && n!="get_name" && n!="get_guid" && n!="get_numaxes" && n!="get_numbuttons" && n!="get_numhats" && n!="get_axis" && n!="get_button" && n!="get_hat")return V();
        auto self=std::static_pointer_cast<Joystick>(shared_from_this());
        return V::func([self,name](const Args& a){V out;self->call_method(name,a,out);return out;});
    }
};
}
void joystick_init() {
    if(!SDL_WasInit(SDL_INIT_JOYSTICK)) {
        if(SDL_InitSubSystem(SDL_INIT_JOYSTICK)<0)throw PyError("error",SDL_GetError());
        SDL_JoystickEventState(SDL_ENABLE);
    }
}
void joystick_quit() {
    for(auto& weak:handles)if(auto handle=weak.lock())handle->close();
    handles.clear();
    if(SDL_WasInit(SDL_INIT_JOYSTICK))SDL_QuitSubSystem(SDL_INIT_JOYSTICK);
}
int joystick_device_index(int instance) {
    for(auto& weak:handles)if(auto item=weak.lock())if(item->handle && SDL_JoystickInstanceID(item->handle)==instance)return item->index;
    return -1;
}
V joystick_module() {
    V module=new_module("pygame.joystick");auto* m=module_of(module);
    m->fn("init",[](const Args& a){arity(a,0);joystick_init();return V::none();});
    m->fn("quit",[](const Args& a){arity(a,0);joystick_quit();return V::none();});
    m->fn("get_init",[](const Args& a){arity(a,0);return V(SDL_WasInit(SDL_INIT_JOYSTICK)!=0);});
    m->fn("get_count",[](const Args& a){arity(a,0);require_subsystem();return V(SDL_NumJoysticks());});
    m->fn("Joystick",[](const Args& a){
        arity(a,1);require_subsystem();double index=a.pos[0].num();
        if(index!=std::floor(index))throw PyError("TypeError","device index must be an integer");
        if(index<0 || index>=SDL_NumJoysticks())throw PyError("error","Invalid joystick device number");
        int instance=SDL_JoystickGetDeviceInstanceID(int(index));
        handles.erase(std::remove_if(handles.begin(),handles.end(),[](const auto& weak){return weak.expired();}),handles.end());
        for(auto& weak:handles)if(auto item=weak.lock())if(item->handle && SDL_JoystickInstanceID(item->handle)==instance)return V::inst(item);
        auto item=std::make_shared<Joystick>(int(index));item->open();handles.push_back(item);return V::inst(item);
    });
    return module;
}
}
