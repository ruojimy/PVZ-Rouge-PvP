// Original functions.py::位移处理. PvP periodic horizontal bounds are explicit.
#include "flood.h"
#include <cmath>

namespace pvz::typed72 {
template<class Terrain> int displace_body_impl(Motion& m,double size,const Terrain& map,double tile,double plk,bool periodic) {
    std::array<Point,6> points;
    size_t count=1;
    if(size==0)points[0]={m.x,m.y};
    else {
        points={{{m.x-tile*.3*size,m.y-tile*1.5*size},
                 {m.x-tile*.3*size,m.y-tile*.2},
                 {m.x+tile*.3*size,m.y-tile*1.5*size},
                 {m.x+tile*.3*size,m.y-tile*.2},
                 {m.x-tile*.3*size,m.y-tile*.75},
                 {m.x+tile*.3*size,m.y-tile*.75}}};
        count=6;
    }
    if(m.vx<0){m.vx+=plk*2;if(m.vx>0)m.vx=0;}
    else if(m.vx>0){m.vx-=plk*2;if(m.vx<0)m.vx=0;}
    m.vy+=plk*4;
    bool horizontal=true,vertical=true;
    const auto outside=[&](Cell c,bool open_top){
        return (!open_top&&c.y<0)||c.y>=map.rows()||(!periodic&&(c.x<0||c.x>=map.cols()));
    };
    for(size_t i=0;i<count;++i){
        const auto p=points[i];
        const auto v=terrain_cell({p.x,p.y+m.vy},tile);
        if(outside(v,true)||(v.y>=0&&!map.empty(v.y,v.x)))vertical=false;
        const auto h=terrain_cell({p.x+m.vx,p.y},tile);
        if(outside(h,true)||(h.y>=0&&!map.empty(h.y,h.x)))horizontal=false;
    }
    if(!(horizontal||vertical)){m.y-=plk*20;m.x-=m.vx;}
    int collision=0;
    if(vertical)m.y+=m.vy;
    else {
        collision=2;
        if(m.vy>0){collision=1;m.vy=-std::abs(m.vx);if(m.vy<-plk*200)m.vy=-plk*200;}
        else m.vy=0;
    }
    if(horizontal)m.x+=m.vx;
    else {if(!(vertical||horizontal))m.x-=m.vx;m.vx=0;}
    if(outside(terrain_cell({m.x-size*tile*.3,m.y},tile),false))m.x+=plk*10;
    if(outside(terrain_cell({m.x+size*tile*.3,m.y},tile),false))m.x-=plk*10;
    return collision;
}
int displace_body(Motion& m,double size,const FloodTerrain& map,double tile,double plk,bool periodic){return displace_body_impl(m,size,map,tile,plk,periodic);}
int displace_body(Motion& m,double size,const WorldTerrain& map,double tile,double plk,bool periodic){return displace_body_impl(m,size,map,tile,plk,periodic);}
} // namespace pvz::typed72
