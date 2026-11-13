#include "core/function_profile.h"
#include "sim/typed/spatial_mode.h"
#include "sim/typed/path_tracking.h"
#include "core/pymath.h"

namespace pvz::typed72 {
namespace {
bool has(const std::vector<std::string>& values,const std::string& name){
    return std::find(values.begin(),values.end(),name)!=values.end();
}
}
void PathTracking::initialize(Point hero){
    const auto& map=world_.terrain;
    for(auto& f:navigation_.flood){
        f=FloodState{};f.field->assign(size_t(map.rows())*map.cols(),1);f.sign=-1;
    }
    for(size_t i=0;i<navigation_.flood.size();++i)navigation_.chase_fields[i]=navigation_.flood[i].field;
    navigation_.target_plant=-1;
    navigation_.hero_cell=terrain_cell(hero,world_.runtime.tile);
    navigation_.target_position=navigation_.hero_cell;
    world_.heroes.globals.wjx.set(double(navigation_.hero_cell.x));
    world_.heroes.globals.wjy.set(double(navigation_.hero_cell.y));
    navigation_.initialized=true;
}
void PathTracking::choose_target(PathMode mode){
    PVP_PROFILE_SCOPE("PathTracking::choose_target");
    auto& n=navigation_;const auto& map=world_.terrain;
    n.output_plants=0;n.target_plant=-1;
    if(mode==PathMode::attack_plants){
        const auto& plants=*world_.plant_roster;
        if(phase_active_&&phase_choice_&&spatial741_enabled()){n.output_plants=phase_choice_->outputs;n.target_plant=phase_choice_->index;++target_cache_hits;}else{
        ++target_scans;target_candidates+=plants.size();
        for(size_t i=0;i<plants.size();++i){
            const auto& p=*plants[i];const auto c=p.cell;
            if(!has(rules_.targets,p.kind) || p.sleep.present())continue;
            if(!map.outside(c.y-1,c.x) && !map.empty(c.y-1,c.x))continue;
            if(!has(rules_.producers,p.kind))++n.output_plants;
            if(n.target_plant==-1)n.target_plant=int64_t(i);
        }
        if(phase_active_&&spatial741_enabled())phase_choice_=PlantChoice{n.target_plant,n.output_plants};
        }
        if(n.target_plant!=-1){
            if(n.hold_plant>0.)--n.hold_plant;
            n.target_position=plants.at(size_t(n.target_plant))->cell;
        }else{
            n.hold_plant=500.;
            if(!map.outside(n.hero_cell.y,n.hero_cell.x))n.target_position=n.hero_cell;
        }
    }
    n.running=std::max(1.,py::floordiv(6.-n.output_plants,2.));
}
void PathTracking::advance(Point hero,PathMode mode){
    PVP_PROFILE_SCOPE("PathTracking::advance");
    if(!navigation_.initialized)initialize(hero);
    const auto& map=world_.terrain;auto& n=navigation_;
    n.hero_cell=terrain_cell(hero,world_.runtime.tile);
    const auto seed=player_flood_seed(hero,world_.runtime.tile);
    advance_flood(map,n.flood[0],{false,false,seed,map.water_surface});
    choose_target(mode);
    advance_flood(map,n.flood[1],{true,n.target_plant!=-1,n.target_position,map.water_surface});
    for(auto& f:n.flood)for(auto& cell:*f.queue)cell.x=map.wrap(cell.x);
    // Only tracking outputs survive NativePhysics._tracking_call. Scratch
    // loop/source indices and the selected hero's animation are restored.
    world_.heroes.globals.wjx.set(double(n.hero_cell.x));
    world_.heroes.globals.wjy.set(double(n.hero_cell.y));
}
} // namespace pvz::typed72
