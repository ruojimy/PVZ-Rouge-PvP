#include "ui/hand/pvp76_ui.h"
#include "sim/pvp/gen/pm_catalog.h"
#include <cmath>
namespace pvz::pvp76_ui {
namespace {
V get(const V& d,const char* k,const V& fallback=V::none()){return d.is_dict()?py::m_get(d,V(k),fallback):fallback;}
}
bool free_summon_preview(const V& app,const V& card,const V& x,const V& y){
    const V entry=get(pm_catalog::CARDS,py_str(card).c_str());
    const std::string behavior=py_str(get(entry,"behavior",V("")));
    if(behavior!="servant"&&behavior!="terraria")return false;
    V state=getattr(app,Sym("state"));const V view=getattr(app,Sym("view"));
    V map=get(get(view,"battle",V::dict()),"map");if(!map.is_dict())map=get(view,"map",V::dict());
    const double width=get(map,"width",V(0.)).num(),height=get(map,"height",V(0.)).num();
    // Same bounds as the kernel (ColdPlacement::zombie servant branch); cost and cooldown
    // are shown on the card itself, and the authority still confirms the summon.
    std::string error;
    if(!std::isfinite(x.num())||!std::isfinite(y.num())||x.num()<0.||(width>0.&&x.num()>=width)||y.num()<0.||(height>0.&&y.num()>=height))error="放置坐标无效";
    state.at(V("placement_preview"))=py_dict({{V("x"),x},{V("y"),y},{V("error"),V(error)}});
    return true;
}
}
namespace pvz::pvp76_perf {
bool typed(const V& battle){return !battle.is_none()&&py_str(pvz::getattr(battle,Sym("backend"),V("")))=="typed72";}
double zombie_count(const V& battle){
    if(typed(battle))return pvz::getattr(battle,Sym("live_mobile_zombies"),V(0.)).num();
    return py::len(py::m_get(pvz::getattr(battle,Sym("g")),V("僵尸"),V::list())).num();
}
V population(const V& app,const V& battle){
    const V room=pvz::getattr(app,Sym("room"),V::none());
    const V backlog=room.is_none()?V(0.):pvz::getattr(room,Sym("accumulator"),V(0.));
    const V tick=pvz::getattr(pvz::getattr(battle,Sym("engine")),Sym("native_tick"));
    if(!typed(battle)){
        const V g=pvz::getattr(battle,Sym("g"));double z=0,p=0;
        for(const auto& u:py::iter_list(py::m_get(g,V("僵尸"),V::list())).items())if(py::m_get(u,V("血量"),V(0.)).num()>0.)++z;
        for(const auto& u:py::iter_list(py::m_get(g,V("植物"),V::list())).items())if(py::m_get(u,V("植物血"),V(0.)).num()>0.)++p;
        return py_dict({{V("native_tick"),tick},{V("zombies"),V(z)},{V("plants"),V(p)},{V("projectiles"),py::len(py::m_get(g,V("实体"),V::list()))},{V("backlog_seconds"),backlog}});
    }
    const V view=pvz::getattr(app,Sym("view"),V::dict());const V b=view.is_dict()?py::m_get(view,V("battle"),V::dict()):V::dict();
    V units=b.is_dict()?py::m_get(b,V("units"),V::list()):V::list();if(units.is_dict())units=py::list_it(callm(units,Sym("values"),Args{}));
    double z=0,p=0;
    for(const auto& u:py::iter_list(units).items()){if(py::m_get(u,V("hp"),V(0.)).num()<=0.)continue;const auto side=py_str(py::m_get(u,V("side"),V("")));if(side.rfind("zombie",0)==0)++z;else if(side.rfind("plant",0)==0)++p;}
    const V shots=b.is_dict()?py::m_get(b,V("projectiles"),V::list()):V::list();
    return py_dict({{V("native_tick"),tick},{V("zombies"),V(z)},{V("plants"),V(p)},{V("projectiles"),py::len(shots)},{V("backlog_seconds"),backlog}});
}
}
