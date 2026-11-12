// Original functions.py::增粒子, 无墙位移处理 and particles region.
#include "state.h"
#include "flood.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>

namespace pvz::typed72 {
void CombatRuntime::emit_particles(const std::string& name, Point position, int count,std::optional<int> direction) {
    if(particle_dispatch_required&&!particle_dispatch)throw std::logic_error("missing required native content particle dispatch");
    if(particle_dispatch){particle_dispatch->emit(*this,name,position,count,direction);return;}
    emit_particles_native(name,position,count,direction);
}
void CombatRuntime::emit_particles_native(const std::string& name, Point position, int count,std::optional<int> direction) {
    particles.push_back({name,position,count});
    if (!presentation.enabled || position.x < presentation.camera.x - tile ||
        position.x > presentation.camera.x + presentation.screen_width + tile) return;
    const auto found = presentation.atlas.find(presentation.sprite_name(name));
    if (found == presentation.atlas.end()) return;
    const auto& sprite = found->second;
    if (sprite.width <= 0 || sprite.height <= 0 || sprite.pixels.size() != size_t(sprite.width)*sprite.height)
        throw std::invalid_argument("invalid typed sprite dimensions");
    const int quarter_width = sprite.width/4, quarter_height = sprite.height/4;
    for (int i=0;i<count;++i) {
        const int facing = direction==3 ? -1 : direction==4 ? 1 : i%2 == 0 ? -1 : 1;
        int attempts = 0;
        Color color{};
        while (attempts < 10) {
            ++attempts;
            const int x = int(rng.randint(quarter_width,quarter_width*3));
            const int y = int(rng.randint(quarter_height,quarter_height*3));
            color = sprite.at(x,y);
            if (color[3] <= 0) continue;
            if (!(color[0] == 0 && color[1] == 0 && color[2] == 0)) break;
        }
        // Original discards even a successful tenth pixel sample.
        if (attempts >= 10) continue;
        const bool big_burst=!direction && count==30;
        const double vx = facing * rng.randint(big_burst?150:100,big_burst?250:200) * plk;
        const double vy = (direction==2?1:-1) * rng.randint(direction?50:big_burst?350:150,big_burst?450:250) * plk;
        particle_state.push_back({color,{position.x,position.y,vx,vy},0});
    }
}

template<class Terrain> void advance_particles_impl(CombatRuntime& w, const Terrain& map, bool draw, Point shake, std::optional<int64_t>* source_index=nullptr) {
    if (!std::isfinite(w.tile) || w.tile <= 0) throw std::invalid_argument("invalid particle tile scale");
    const double initial_size = w.tile * .15;
    for (size_t i=w.particle_state.size();i-- >0;) {
        if(source_index)*source_index=int64_t(i);
        auto& p=w.particle_state[i];
        p.age += 1;
        if (p.age == 300) continue;
        double size = initial_size;
        bool move = true;
        if (p.motion.vy > 0) {
            const Cell c=terrain_cell({p.motion.x,p.motion.y},w.tile);
            if (map.valid_row(c.y)) {
                if (!map.empty(c.y,c.x)) move=false;
                if (map.water(c.y,c.x)) p.motion.vy /= 2;
            }
        }
        if (move) {
            auto& m=p.motion;
            if (m.vx < 0) {m.vx += w.plk*1;if(m.vx>0)m.vx=0;}
            else if(m.vx>0){m.vx -= w.plk*1;if(m.vx<0)m.vx=0;}
            m.vy += w.plk*3;
            m.x += m.vx;
            m.y += m.vy;
        }
        if (draw) {
            if (p.age >= 250) size=size*(300-p.age)/50;
            w.particle_rects.push_back({p.color,p.motion.x-size/2-w.presentation.camera.x+shake.x,
                p.motion.y-size/2-w.presentation.camera.y+shake.y,size,size});
        }
    }
    // There are no cross-particle reads in this source region. Stable compaction
    // replaces repeated erase shifts while retaining source iteration/draw order.
    std::erase_if(w.particle_state,[](const Particle& p){return p.age==300;});
}
void advance_particles(CombatStages& w,const FloodTerrain& map,bool draw,Point shake){advance_particles_impl(w,map,draw,shake);}
void advance_particles(CombatRuntime& w,const WorldTerrain& map,bool draw,Point shake,std::optional<int64_t>* source_index){advance_particles_impl(w,map,draw,shake,source_index);}
} // namespace pvz::typed72
