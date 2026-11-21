#include "ui/hand/pvp75_ui.h"
#include "pg/pg.h"
#include <cmath>
#include <string>
namespace pvz::pvp75_ui {
namespace {
constexpr double pi=3.14159265358979323846;
V get(const V& d,const char* k,const V& fallback=V::none()){return d.is_dict()?py::m_get(d,V(k),fallback):fallback;}
V battle(const V& app){V b=get(getattr(app,Sym("view")),"battle");return b.is_dict()?b:V::dict();}
std::string active(const V& app){return py_str(get(getattr(app,Sym("state")),"active_side",V("plant")));}
bool plant_seat(const std::string& s){return s.rfind("plant",0)==0;}
bool local(const V& app,const std::string& seat){return py::in(V(seat),callm(app,Sym("local_sides"),Args{}));}
double width(const V& app){
    V map=get(battle(app),"map");if(!map.is_dict())map=get(getattr(app,Sym("view")),"map");
    return get(map,"width",V(3456.)).num();
}
void input(const V& app,const std::string& seat,const char* type,std::vector<std::pair<Sym,V>> kw={}){
    callm(app,Sym("input"),Args(ArgVec{V(seat),V(type)},std::move(kw)));
}
void message(const V& app,const std::string& text){callm(app,Sym("message"),Args{V(text)});}
void clear_hand(const V& app){
    callm(getattr(app,Sym("state")),Sym("update"),Args(ArgVec{},{{Sym("selected_card"),V::none()},{Sym("shovel"),V(false)},
        {Sym("teleport"),V(false)},{Sym("grave"),V::none()},{Sym("copy"),V::none()}}));
}
}
bool laser_aiming(const V& app){
    const auto seat=active(app);if(!plant_seat(seat)||!local(app,seat))return false;
    return get(get(get(battle(app),"players",V::dict()),seat.c_str(),V::dict()),"laser_aim").truthy();
}
V laser_at(const V& app,const V& x,const V& y){
    V units=get(battle(app),"units",V::list());
    if(units.is_dict())units=py::list_it(callm(units,Sym("values"),Args{}));
    const double w=width(app),px=x.num(),py_=y.num();
    for(const auto& u:py::iter_list(units).items()){
        if(py_str(get(u,"side"))!="plant"||py_str(get(u,"card_id"))!="plant:激光豆"||get(u,"hp",V(0.)).num()<=0.)continue;
        const double dx=std::fmod(std::fmod(get(u,"x").num()-px+w/2.,w)+w,w)-w/2.;
        if(std::abs(dx)<30.&&std::abs(get(u,"y").num()-py_-20.)<50.)return u;
    }
    return V::none();
}
void cancel(const V& app){if(laser_aiming(app))input(app,active(app),"laser_cancel");}
bool world_click(const V& app,const V& pos,const V& right){
    const V state=getattr(app,Sym("state"));const auto seat=active(app);
    if(!plant_seat(seat)||!local(app,seat)||get(state,"teleport").truthy()||get(state,"rally").truthy())return false;
    const bool aiming=laser_aiming(app);
    if(right.truthy()){
        if(!aiming)return false;
        input(app,seat,"laser_cancel");clear_hand(app);message(app,"已取消激光豆瞄准");return true;
    }
    if(get(state,"shovel").truthy())return false;
    const V point=callm(getattr(app,Sym("renderer")),Sym("world_point"),Args{pos});
    if(!point.truthy())return false;
    const V x=point.idx(0),y=point.idx(1);const V bean=laser_at(app,x,y);
    if(!aiming&&bean.is_none())return false;
    // Each launcher keeps its own state: a cannon click while aiming goes to the cannon.
    if(aiming&&bean.is_none()&&callm(app,Sym("cannon_at"),Args{x,y}).truthy()){input(app,seat,"laser_cancel");return false;}
    clear_hand(app);
    if(!bean.is_none()&&callm(app,Sym("cannon_aiming"),Args{}).truthy())input(app,"plant","cannon_cancel");
    // A click on a bean names it, so the whole sprite (which reaches above its own cell) counts.
    std::vector<std::pair<Sym,V>> kw{{Sym("x"),x},{Sym("y"),y}};if(!bean.is_none())kw.push_back({Sym("target"),get(bean,"id")});
    const V error=callm(app,Sym("input"),Args(ArgVec{V(seat),V("laser")},std::move(kw)));
    if(error.truthy())message(app,py_str(error));
    else if(!aiming)message(app,"激光豆：左键点选面朝方向±80°、8到20格内的目标点发射，右键取消；再次点击这株激光豆停止发射。");
    else message(app,"");
    return true;
}
bool blocks_jump(const V& app,const V& pos){
    if(laser_aiming(app))return true;
    const V point=callm(getattr(app,Sym("renderer")),Sym("world_point"),Args{pos});
    return point.truthy()&&!laser_at(app,point.idx(0),point.idx(1)).is_none();
}
void diagnostic_lasers(const V& app,const V& b,const V& config){
    if(py_str(get(config,"scenario"))!="laser")return;
    const int count=int(get(config,"lasers",V(10.)).num());if(count<0||count>40)throw std::runtime_error("Diagnostic laser count invalid");
    const double hp=get(config,"unit_hp",V(100000000.)).num(),tile=48.;
    // extra_zombies: [card id, ...] durable extra zombies among the 普通僵尸 (armour / split head-body art).
    const V extra=get(config,"extra_zombies",V::list());
    if(extra.is_list())for(size_t k=0;k<size_t(extra.len());++k){
        const V key=extra.idx(int64_t(k));const double x=2310.+double(k%25)*8.;
        const V obj=callm(b,Sym("spawn"),Args(ArgVec{key,V("zombie"),V(x),V(960.)},{{Sym("facing"),V(-1.)}}));
        if(!obj.truthy())throw std::runtime_error("Diagnostic extra zombie spawn failed: "+py_str(key));
        callm(py::m_get(getattr(b,Sym("_native_objects")),get(obj,"id")),Sym("update"),Args{py_dict({{V("血量"),V(hp)},{V("_pvp_max_hp"),V(hp)},{V("防具血量"),V(hp)},{V("手持血量"),V(hp)}})});
    }
    for(int i=0;i<count;++i){
        // One bean per cell; each beam 17 cells right, 0 to 8 cells up (rotated art).
        // laser_column (default 30): beans just left of the zombies, inside the default camera view.
        // Beans 21-40 continue leftwards on the same (supported) row.
        const double x=(get(config,"laser_column",V(30.)).num()+i%20-20.*double(i/20)+.5)*tile,y=960.;
        const V obj=callm(b,Sym("spawn"),Args(ArgVec{V("plant:激光豆"),V("plant"),V(x),V(y)},{{Sym("facing"),V(1.)}}));
        if(!obj.truthy())throw std::runtime_error("Diagnostic laser spawn failed");
        const V id=get(obj,"id");
        callm(py::m_get(getattr(b,Sym("_native_objects")),id),Sym("update"),Args{py_dict({{V("植物血"),V(hp)},{V("植物血上限"),V(hp)}})});
        // Straight to the battle after the probe's neutral seq-1 inputs: sequences 2, 3, 4...
        const auto send=[&](V payload){payload.at(V("seq"))=V(double(2+2*i+(payload.contains(V("target"))?0:1)));payload.at(V("type"))=V("laser");
            return callm(b,Sym("command_input"),Args{V("plant"),payload});};
        V e=send(py_dict({{V("target"),id},{V("x"),V(x)},{V("y"),V(y)}}));
        if(e.truthy())throw std::runtime_error("Diagnostic laser aim: "+py_str(e));
        callm(b,Sym("step"),Args{});
        // laser_miss: 45 degrees up over the zombies (same on-screen beams, no hits).
        const bool miss=get(config,"laser_miss",V(false)).truthy();
        e=send(miss?py_dict({{V("x"),V(x+8.*tile)},{V("y"),V(y-24.-8.*tile)}}):py_dict({{V("x"),V(x+17.*tile)},{V("y"),V(y-24.-(i%5)*2.*tile)}}));
        if(e.truthy())throw std::runtime_error("Diagnostic laser fire: "+py_str(e));
        callm(b,Sym("step"),Args{});
    }
}
void draw_laser_ring(const V& r,const V& view,const V& state,const V& game,const V& terrain,const V& players,const V& side){
    (void)game;
    if(!terrain.truthy()||!players.is_dict())return;
    const V camera=getattr(r,Sym("camera"),V::none());if(!camera.truthy())return;
    const auto seat=py_str(side);if(!plant_seat(seat)||!py::in(side,get(view,"local_sides",V::list({side}))))return;
    const V aim=get(get(players,seat.c_str(),V::dict()),"laser_aim");if(!aim.is_dict())return;
    const double tile=get(terrain,"tile_size",V(48.)).num(),scale=camera.idx(2).num();
    const V center=callm(getattr(r,Sym("world")),Sym("point"),Args{get(aim,"x"),get(aim,"y")});
    const double cx=center.idx(0).num(),cy=center.idx(1).num();
    const double inner=get(aim,"min",V(8.)).num()*tile*scale,outer=get(aim,"max",V(20.)).num()*tile*scale;
    const double half=get(aim,"angle",V(80.)).num()*pi/180.,base=get(aim,"facing",V(1.)).num()<0.?pi:0.;
    const V pg=getattr(r,Sym("pg"));const V screen=getattr(r,Sym("screen"));const V draw=getattr(pg,Sym("draw"));
    const int w=int(outer*2.)+8;const int left=int(std::lround(cx))-w/2,top=int(std::lround(cy))-w/2;
    const V clip=callm(callm(pg,Sym("Rect"),Args{V(left),V(top),V(w),V(w)}),Sym("clip"),Args{callm(screen,Sym("get_rect"),Args{})});
    const int cw=int(getattr(clip,Sym("w")).num()),ch=int(getattr(clip,Sym("h")).num());if(cw<=0||ch<=0)return;
    // Reused while the clipped size holds (a fresh full-screen alpha surface per frame is costly).
    static V overlay;static int ow=0,oh=0;
    if(!overlay.has()||ow!=cw||oh!=ch){overlay=callm(pg,Sym("Surface"),Args{V::tuple({V(cw),V(ch)}),getattr(pg,Sym("SRCALPHA"))});ow=cw;oh=ch;}
    callm(overlay,Sym("fill"),Args{V::tuple({V(0),V(0),V(0),V(0)})});
    const double ox=left-getattr(clip,Sym("x")).num()+w/2.,oy=top-getattr(clip,Sym("y")).num()+w/2.;
    V points=V::list();constexpr int steps=48;
    for(int i=0;i<=steps;++i){const double a=base-half+2.*half*i/steps;points.append(V::tuple({V(ox+std::cos(a)*outer),V(oy+std::sin(a)*outer)}));}
    for(int i=steps;i>=0;--i){const double a=base-half+2.*half*i/steps;points.append(V::tuple({V(ox+std::cos(a)*inner),V(oy+std::sin(a)*inner)}));}
    const int line=std::max(2,int(std::lround(tile*scale*.06)));
    callm(draw,Sym("polygon"),Args{overlay,V::tuple({V(60),V(220),V(90),V(80)}),points});
    callm(draw,Sym("polygon"),Args{overlay,V::tuple({V(80),V(240),V(110),V(220)}),points,V(line)});
    // Too close: the same ±80° sector from the eye up to the minimum range (red).
    V near=V::list();near.append(V::tuple({V(ox),V(oy)}));
    for(int i=0;i<=steps;++i){const double a=base-half+2.*half*i/steps;near.append(V::tuple({V(ox+std::cos(a)*inner),V(oy+std::sin(a)*inner)}));}
    callm(draw,Sym("polygon"),Args{overlay,V::tuple({V(230),V(60),V(50),V(70)}),near});
    callm(draw,Sym("polygon"),Args{overlay,V::tuple({V(240),V(70),V(60),V(230)}),near,V(line)});
    callm(screen,Sym("blit"),Args{overlay,V::tuple({getattr(clip,Sym("x")),getattr(clip,Sym("y"))})});
    // Same red crosshair as the cob cannon's aiming state, at the pointer.
    if(get(state,"touch_mode").truthy())return;
    const V mark=callm(r,Sym("artwork"),Args{V("轰炸")});if(mark.is_none())return;
    const V mouse=callm(getattr(pg,Sym("mouse")),Sym("get_pos"),Args{});
    const int size=std::max(16,int(std::lround(tile*scale)));
    callm(screen,Sym("blit"),Args{callm(getattr(pg,Sym("transform")),Sym("scale"),Args{mark,V::tuple({V(size),V(size)})}),
        V::tuple({V(mouse.idx(0).num()-size/2),V(mouse.idx(1).num()-size/2)})});
}
}
