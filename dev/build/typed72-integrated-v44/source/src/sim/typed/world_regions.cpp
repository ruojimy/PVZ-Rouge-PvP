#include "sim/typed/world_regions.h"
#include "core/pymath.h"
#include <cmath>
#include <cmath>

// std::numbers::pi without <numbers> (clang 14 libc++); same double value.
constexpr double pvz_typed72_pi=3.141592653589793238462643383279502884;
namespace pvz::typed72 {
void WorldRegions::water_animation(){
    auto& g=world_.heroes.globals;
    if(g.water_ice.get()==0. && ++state_.water_wave>=500.)state_.water_wave=0.;
    g.angle.set(pvz_typed72_pi*(state_.water_wave/500.));
    state_.water_offset=std::sin(g.angle.get())*world_.runtime.tile*.1;
}
void WorldRegions::important_blocks(){
    auto& map=world_.terrain;auto& w=world_.runtime;auto& g=world_.heroes.globals;
    for(size_t index=map.important.size();index-- >0;){
        world_.heroes.source_index=int64_t(index);
        const auto entry=map.important.at(index);const auto [row,col]=entry.cell;
        if(entry.block=="坟墓"){
            auto& growing=map.native_at(row,col).growing.get();++growing;
            if(py::mod(growing,50.)==0.){
                g.xx.set(col*w.tile);g.yy.set(row*w.tile);
                const auto y=timed_coordinate(g.yy.get()+w.tile,g.yy.get(),200.,growing);
                w.emit_particles(map.native_at(row+1,col).block.get(),{col*w.tile+w.tile*.5,y+w.tile},4);
            }
            if(map.native_at(row,col).growing.get()==200.)map.important.erase(map.important.begin()+index);
        }
        if(entry.block=="雪"){
            auto& gone=map.native_at(row,col).snow_gone;
            if(!gone.present())map.important.erase(map.important.begin()+index);
            else if(++gone.get()==10000.){
                destroy_pvp_block(world_,plants_,entry.cell);
                map.native_at(row,col).snow_gone.erase();
                w.sound("雪",{col*w.tile+w.tile*.5,row*w.tile+w.tile*.5,0.,0.});
                map.important.erase(map.important.begin()+index);
            }
        }
    }
}
void WorldRegions::ice_clock(){
    auto& h=world_.heroes;
    h.globals.water_ice.set(h.water_ice);
    if(h.globals.water_ice.get()>0.)--h.globals.water_ice.get();
    h.water_ice=h.globals.water_ice.get();
}
void WorldRegions::sun_motion(NativeSun& sun){
    auto& w=world_.runtime;++sun.animation;
    state_.landing=displace_body(sun.motion,0.,world_.terrain,w.tile,w.plk,world_.terrain.periodic_x);
    if(sun.motion.vy>w.plk*50.)sun.motion.vy=w.plk*50.;
    ++sun.age;
}
} // namespace pvz::typed72
