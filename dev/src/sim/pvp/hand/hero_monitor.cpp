// Native hooks call the translated reference monitor at the actual static C++
// step/spawn boundaries; replacing Python method descriptors would miss them.
#include "sim/pvp/hand/hero_monitor.h"
#include "sim/pvp/shim/pm_hero_guard.h"
#include "core/fsutil.h"
#include <cstdlib>
#include <fstream>
namespace pvz::pm_hero_guard {
namespace {
thread_local size_t violations_=0;
thread_local size_t reported_=0;
thread_local std::string last_;
bool active(const V& guard){return guard.has() && !guard.is_none();}
}
size_t violation_count(){return violations_;}
size_t reported_violation_count(){return reported_;}
std::string last_violation(){return last_;}
V f_enabled(const Args&) {
    const char* value=std::getenv("PVP_HERO_GUARD");
    return V(value && *value && std::string(value)!="0");
}
V f_install(const Args& a) {
    V battle=a.get(0,Sym("battle"),nullptr,"install");
    V prior=pvz::getattr(battle,Sym("hero_guard"),V::none());
    if(!f_enabled(Args{}).truthy()) {
        if(!active(prior))pvz::setattr(battle,Sym("hero_guard"),V::none());
        return V::none();
    }
    if(active(prior))return V::none();
    V guard=new_HeroGuard(Args{battle});pvz::setattr(battle,Sym("hero_guard"),guard);
    callm(guard,Sym("check"),Args{V("init")});
    return guard;
}
V C_HeroGuard::m_violation(const Args& a) {
    V kind=a.get(0,Sym("kind"),nullptr,"violation");
    V message=a.get(1,Sym("message"),nullptr,"violation");
    ++violations_;last_=py_str(kind)+": "+py_str(message);
    V row=py_dict({{V("kind"),kind},{V("message"),message},
        {V("tick"),pvz::getattr(a_b,Sym("tick"),V::none())},
        {V("native_tick"),pvz::getattr(pvz::getattr(a_b,Sym("engine"),V::none()),Sym("native_tick"),V::none())},
        {V("mode"),pvz::getattr(a_b,Sym("mode"),V::none())},
        {V("backend"),V("native-cpp")}});
    a_violations.append(row);
    if(const char* path=std::getenv("PVP_HERO_GUARD_LOG")) {
        ++reported_;
        std::ofstream out(u8p(path),std::ios::binary|std::ios::app);
        if(out)out<<py::stdlib_call(V("json.dumps"),Args{row}).str()<<'\n';
    }
    throw PyError("HeroIsolationError","[hero_guard:"+py_str(kind)+"] "+py_str(message),{"AssertionError"});
}
TickScope::TickScope(V battle):guard_(pvz::getattr(battle,Sym("hero_guard"),V::none())),uncaught_(std::uncaught_exceptions()) {
    if(active(guard_))callm(guard_,Sym("mark_positions"),Args{});
}
TickScope::~TickScope() noexcept(false) {
    if(active(guard_) && std::uncaught_exceptions()==uncaught_)callm(guard_,Sym("check"),Args{V("native_tick")});
}
SpawnScope::SpawnScope(V battle):guard_(pvz::getattr(battle,Sym("hero_guard"),V::none())),uncaught_(std::uncaught_exceptions()) {
    if(active(guard_))before_=callm(guard_,Sym("globals_snapshot"),Args{});
}
SpawnScope::~SpawnScope() noexcept(false) {
    if(!active(guard_) || std::uncaught_exceptions()!=uncaught_)return;
    V after=callm(guard_,Sym("globals_snapshot"),Args{});
    if(before_!=after)callm(guard_,Sym("violation"),Args{V("spawn"),V("spawn changed the selected global player")});
    callm(guard_,Sym("check"),Args{V("spawn")});
}
}
