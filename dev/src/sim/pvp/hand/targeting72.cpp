// Typed geometry for the real content target/route path. Authoritative unit
// records remain live; this is a read-only boundary, never a per-tick mirrored
// world. No RNG, ordering, proxy writes or lifetime ownership is changed.
#include "sim/pvp/gen/pm_native_content.h"
#include "core/pymath.h"
#include <cmath>
#include <cstdlib>
#include <limits>

namespace pvz::pm_native_content {
namespace {
struct Point {double x,y;};
bool reference() {static bool enabled=[] {auto e=std::getenv("PVZ72_REFERENCE");return e && *e=='1';}();return enabled;}
double delta(double a,double b,double width){return py::mod(b-a+width/2.,width)-width/2.;}
Point unpack(const V& p){return {p.idx(0).num(),p.idx(1).num()};}
Point point(C_NativeContent* c,const V& obj,double tile) {
    if(V* override=c->find_dyn(SY("point"));override && override->has())return unpack(override->call(Args{obj}));
    const V* kind=obj.find(SV("_pvp_content"));
    if(kind && *kind==SV("抓人草触手"))return unpack(rd(obj,SV("_pvp_head_point")));
    if(const V* plant=obj.find(SV("植物"));plant && plant->has()) {
        const V& cell=rd(obj,SV("坐标"));
        return {(cell.idx(1).num()+.5)*tile,(cell.idx(0).num()+.45)*tile};
    }
    if(kind && (*kind==SV("海盗鹦鹉") || *kind==SV("乌鸦")))return unpack(c->m_point(Args{obj}));
    const V& pos=rd(obj,SV("位置"));return {pos.idx(0).num(),pos.idx(1).num()-tile};
}
double distance2(Point a,Point b,double width){double x=delta(a.x,b.x,width),y=b.y-a.y;return x*x+y*y;}
V route(C_NativeContent* c,const V& source,const V& goal,const V& candidates,double tile,double width) {
    if(goal.is_none())return goal;
    Point a=point(c,source,tile),b=point(c,goal,tile);
    double dx=delta(a.x,b.x,width),dy=b.y-a.y,length2=dx*dx+dy*dy;
    if(length2<=1e-12)return goal;
    V chosen=goal;double first=1.;const double radius2=(tile*.65)*(tile*.65);
    for(const V& unit:candidates.items()) {
        if(py_is(unit,goal))continue;
        Point p=point(c,unit,tile);double x=delta(a.x,p.x,width),y=p.y-a.y;
        double along=(x*dx+y*dy)/length2;
        if(along<0. || along>=first)continue;
        double ex=x-along*dx,ey=y-along*dy;
        if(ex*ex+ey*ey<=radius2){chosen=unit;first=along;}
    }
    return chosen;
}
}
V C_NativeContent::m_route_target(const Args& A) {
    if(reference())return m_route_target_dynamic(A);
    V source=A.get(0,SY("source"),nullptr),goal=A.get(1,SY("goal"),nullptr),list=A.get(2,SY("candidates"),nullptr);
    return route(this,source,goal,list,pvz::getattr(a_b,SY("tile")).num(),pvz::getattr(a_b,SY("width")).num());
}
V C_NativeContent::m_nearest(const Args& A) {
    if(reference())return m_nearest_dynamic(A);
    V source=A.get(0,SY("source"),nullptr);
    V candidates;
    if(V* override=find_dyn(SY("enemies"));override && override->has())candidates=override->call(Args{source});
    else candidates=m_enemies(Args{source});
    const double tile=pvz::getattr(a_b,SY("tile")).num(),width=pvz::getattr(a_b,SY("width")).num();
    Point origin=point(this,source,tile);
    bool nohero=source.get(SV("_pvp_no_hero_attack"),V(false)).truthy();
    bool charmed=source.contains(SV("魅惑"));
    V best=V::none(),hero=V::none();
    double best2=std::numeric_limits<double>::infinity(),hero2=best2;
    for(const V& unit:candidates.items()) {
        bool ishero=unit.get(SV("_pvp_hero"),V(false)).truthy();
        if(nohero && ishero)continue;
        double d=distance2(origin,point(this,unit,tile),width);
        if(d<best2){best2=d;best=unit;}
        if(charmed && ishero && d<hero2){hero2=d;hero=unit;}
    }
    if(charmed && !hero.is_none()) {
        if(V* override=find_dyn(SY("route_target"));override && override->has())best=override->call(Args{source,hero,candidates});
        else best=route(this,source,hero,candidates,tile,width);
    }
    return callm(a_pvp64,SY("taunt_target"),Args{source,best});
}
} // namespace pvz::pm_native_content
