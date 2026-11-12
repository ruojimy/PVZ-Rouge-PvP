#include "sim/typed/grave_binding.h"
#include "sim/typed/terrain_effects.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <unordered_set>

namespace pvz::typed72 {
namespace {
bool same_cell(Cell a,Cell b){return a.x==b.x && a.y==b.y;}
bool completion(const CombatPlant& plant) {
    return plant.grave_eating.present() && !plant.grave_eating.is_null() && plant.grave_eating.get()==1000.;
}
}
ZombieRef GraveBinding::resolve(const std::string& id)const {
    const auto found=world_.native_objects.get(id);
    if(!found)return {};
    const auto* zombie=std::get_if<ZombieRef>(&*found);
    return zombie?*zombie:ZombieRef{};
}
Cell GraveBinding::target_cell(const CombatZombie& target)const {
    const auto tile=world_.runtime.tile;
    const auto width=world_.terrain.cols()*tile;
    const auto& point=target.body.motion.get();
    return {int(std::floor((point.y-.001)/tile)),int64_t(std::floor(py::mod(point.x,width)/tile))};
}
bool GraveBinding::valid(const Link& link)const {
    const auto target=resolve(link.target_id);
    if(target!=link.target || !target->protection.grave || target->body.hp<=0. || target->body.dead.present())return false;
    const auto& owner=target->source.owner;
    return (!owner.present() || (!owner.is_null() && owner.get()=="zombie")) &&
        !target->source.charmed.present() && same_cell(target_cell(*target),link.cell);
}
void GraveBinding::event(GraveBindingEventKind kind,const Link& link,GraveBindingReason reason) {
    services_.grave_event({kind,link.plant->source.id,link.target_id,world_.heroes.tick,reason});
}
void GraveBinding::attach(const PlantRef& plant,std::string target_id) {
    if(closed_)throw std::logic_error("native grave binding is closed");
    if(!plant || plant->kind!="墓碑吞噬者" || plant->hp.or_missing(0.)<=0. || plant->dead.present() ||
       std::find(world_.plant_roster->begin(),world_.plant_roster->end(),plant)==world_.plant_roster->end())
        throw std::invalid_argument("expected a live original grave buster");
    if(by_plant_.contains(plant.get()))throw std::invalid_argument("grave buster already has a target");
    const auto target=resolve(target_id);
    if(!target)throw std::invalid_argument("target grave is unavailable");
    auto link=std::make_shared<Link>(Link{plant,target,std::move(target_id),plant->cell});
    if(!valid(*link) || std::any_of(links_.begin(),links_.end(),[&](const auto& other){return other->target==target;}))
        throw std::invalid_argument("target must be a live unclaimed enemy grave in the planted cell");
    links_.push_back(link);
    try{by_plant_.emplace(plant.get(),std::prev(links_.end()));}
    catch(...){links_.pop_back();throw;}
    plant->grave_target.set(link->target_id);
    event(GraveBindingEventKind::started,*link);
}
void GraveBinding::erase(const PlantRef& plant) {
    const auto found=by_plant_.find(plant.get());
    if(found==by_plant_.end())return;
    links_.erase(found->second);by_plant_.erase(found);
}
void GraveBinding::cancel(const Link& link,GraveBindingReason reason) {
    erase(link.plant);
    cancelled_[link.plant.get()]=link.plant;
    link.plant->hp.set(0.);link.plant->dead.set(DeathMarker(0.));
    event(GraveBindingEventKind::cancelled,link,reason);
}
void GraveBinding::before_native_tick() {
    if(closed_ || (links_.empty() && cancelled_.empty()))return;
    std::unordered_set<CombatPlant*> present;
    for(const auto& plant:*world_.plant_roster)present.insert(plant.get());
    std::erase_if(cancelled_,[&](const auto& entry){return !present.contains(entry.first);});
    const std::vector<std::shared_ptr<Link>> snapshot(links_.begin(),links_.end());
    for(const auto& link:snapshot) {
        const auto& plant=link->plant;
        if(!present.contains(plant.get()) || plant->hp.or_missing(0.)<=0. || plant->dead.present())
            cancel(*link,GraveBindingReason::plant_unavailable);
        else if(!valid(*link))cancel(*link,GraveBindingReason::target_unavailable);
    }
}
void GraveBinding::remove_completion_coin(const CombatPlant& plant) {
    if(actions_.coins.empty())return;
    const auto& last=actions_.coins.back();
    const auto tile=world_.runtime.tile;
    if(last.kind=="银币" && last.motion.x==(plant.cell.x+.5)*tile && last.motion.y==(plant.cell.y+.5)*tile)
        actions_.coins.pop_back();
}
void GraveBinding::destroy(Cell cell) {
    PlantRef plant;
    const auto index=world_.heroes.source_index;
    if(depth_ && index && *index>=0 && uint64_t(*index)<world_.plant_roster->size())
        plant=world_.plant_roster->at(size_t(*index));
    if(plant && cancelled_.contains(plant.get()) && same_cell(plant->cell,cell) && completion(*plant)) {
        remove_completion_coin(*plant);return;
    }
    const auto found=plant?by_plant_.find(plant.get()):by_plant_.end();
    if(found!=by_plant_.end()) {
        const auto link=*found->second;
        if(same_cell(cell,link->cell) && completion(*plant)) {
            if(!valid(*link)) {
                remove_completion_coin(*plant);cancel(*link,GraveBindingReason::target_unavailable);return;
            }
            erase(plant);link->target->body.hp=0.;
            services_.grave_consumed(link->target,plant);
            event(GraveBindingEventKind::consumed,*link);
            return;
        }
    }
    destroy_pvp_block(world_,terrain_,cell);
}
std::shared_ptr<const GraveBinding::Link> GraveBinding::draw_target(size_t index)const {
    if(index>=world_.plant_roster->size())return {};
    const auto found=by_plant_.find(world_.plant_roster->at(index).get());
    if(found==by_plant_.end() || !valid(**found->second))return {};
    return *found->second;
}
void GraveBinding::close() {
    if(closed_)return;
    for(const auto& link:links_) {
        link->plant->hp.set(0.);link->plant->dead.set(DeathMarker(0.));
    }
    links_.clear();by_plant_.clear();cancelled_.clear();closed_=true;
}
} // namespace pvz::typed72
