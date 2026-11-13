#include "sim/typed/content_lantern.h"
#include "sim/typed/projectile_rules.h"
namespace pvz::typed72 {
void ContentLantern::pulses() {
    if(!phototherapy_)return;const auto plants=world_.plant_roster;
    for(size_t i=0;i<plants->size();++i) {
        const auto plant=plants->at(i);if(plant->kind!="路灯花"||plant->hp.or_missing(0.)<=0.||plant->dead.present())continue;
        const auto timer=plant->lamp,previous=plant->content_state.lantern_timer;
        if(timer.present())plant->content_state.lantern_timer=timer;else plant->content_state.lantern_timer.set_null();
        if(timer.present()&&!timer.is_null()&&previous.present()&&!previous.is_null()&&timer.get()>previous.get())burn(plant);
    }
}
void ContentLantern::burn(const PlantRef& plant) {
    const auto cell=plant->cell;const double tile=world_.runtime.tile;const Point center{(cell.x+.5)*tile,(cell.y+.5)*tile};
    const auto owner=world_.heroes.owner(source_ref(plant));std::vector<Field<std::string>> woken;
    const auto roster=world_.plant_roster;for(size_t i=0;i<roster->size();++i) {
        const auto target=roster->at(i);
        if(target->hp.or_missing(0.)<=0.||target->dead.present()||!target->sleep.present()||world_.heroes.owner(source_ref(target))!=owner)continue;
        if(std::abs(wrap_delta(double(cell.x),double(target->cell.x),double(world_.terrain.cols())))>3.||std::abs(target->cell.y-cell.y)>3.)continue;
        target->sleep.erase();woken.push_back(target->source.id);PlantRef root=target;
        if(ContentPlants70::is_head(target)) {
            root.reset();const auto& parent=target->content70.parent;
            if(parent.present()&&!parent.is_null())if(const auto value=world_.native_objects.get(parent.get()))if(const auto* p=std::get_if<PlantRef>(&*value))root=*p;
        }
        if(root&&root->source.content.present()&&!root->source.content.is_null()&&root->source.content.get()=="抓人草") {
            root->sleep.erase();root->content70.was_asleep.set(true);for(const auto& head:plants70_.heads(root))head->sleep.erase();
        }
    }
    if(!woken.empty())events_.lantern_wake(plant->source.id,woken);size_t hit=0;
    for(const auto& target:queries_.enemies_in_box(source_ref(plant),{center.x-3.*tile,center.y-3.*tile,center.x+3.*tile,center.y+3.*tile}))if(const auto* body=std::get_if<CombatTarget>(&target);body&&body->unit) {
        ++queries_.range_exact_tests;
        if(world_.heroes.owner(source_ref(body->unit))==owner)continue;const auto p=body->unit->body.motion.get();
        if(std::abs(wrap_delta(center.x,p.x,world_.world_width.get()))<=3.*tile&&std::abs(p.y-tile*.5-center.y)<=3.*tile) {
            targets_.damage(source_ref(plant),target,12.,plant->facing);++hit;
        }
    }
    if(hit)events_.lantern_burn(plant->source.id,hit);
}
} // namespace pvz::typed72
