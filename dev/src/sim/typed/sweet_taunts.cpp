#include "sim/typed/sweet_taunts.h"
#include "sim/typed/projectile_rules.h"
#include <algorithm>
#include <cmath>
#include <set>

namespace pvz::typed72 {
namespace {
bool living(const CombatPlant& plant) {
    return plant.hp.or_missing(0.)>0. && !plant.dead.present();
}
}
Point SweetTaunts::point(const CombatPlant& plant)const {
    return {(plant.cell.x+.5)*world_.runtime.tile,(plant.cell.y+1.)*world_.runtime.tile};
}
std::optional<std::string> SweetTaunts::key(const CombatPlant& plant) {
    const auto& id=plant.source.id;
    return id.present() && !id.is_null()?std::optional{id.get()}:std::nullopt;
}
std::vector<PlantRef> SweetTaunts::potatoes()const {
    std::vector<PlantRef> result;
    for(const auto& plant:*world_.plant_roster) {
        const auto& content=plant->source.content;
        if(content.present() && !content.is_null() && content.get()=="甜薯" && living(*plant))
            result.push_back(plant);
    }
    return result;
}
void SweetTaunts::update() {
    potatoes_=potatoes();
    dirty_=false;
    std::set<std::optional<std::string>> alive;
    for(const auto& plant:potatoes_)alive.insert(key(*plant));
    std::erase_if(fields_,[&](const auto& field){return !alive.contains(field.first);});
    baseline_=banks_.capture();
    try {
        for(const auto& plant:potatoes_) {
            const auto id=key(*plant);
            const auto found=fields_.find(id);
            PathSnapshot field;
            if(found==fields_.end()) {
                field=banks_.independent(*baseline_);
                field.flood[0].queue=std::make_shared<std::vector<Cell>>();
                field.flood[0].cooldown=0;
            }else field=found->second;
            banks_.restore(field);
            paths_.advance(point(*plant),PathMode::follow_hero);
            fields_.insert_or_assign(id,banks_.capture());
        }
    }catch(...){banks_.restore(*baseline_);throw;}
    banks_.restore(*baseline_);
}
PlantRef SweetTaunts::taunting(const ContentTarget& target)const {
    const auto fresh=dirty_?potatoes():std::vector<PlantRef>{};
    const auto& candidates=dirty_?fresh:potatoes_;
    if(candidates.empty())return {};
    const auto* combat=std::get_if<CombatTarget>(&target);
    if(!combat || combat->is_hero())return {};
    const auto& unit=*combat->unit;
    if(unit.protection.grave || unit.body.hp<=0.)return {};
    const auto owner=world_.heroes.owner(source_ref(combat->unit));
    const auto& position=unit.body.motion.get();
    const auto tile=world_.runtime.tile,width=world_.world_width.get();
    PlantRef best;
    double best_distance=0.;
    for(const auto& plant:candidates) {
        if(!living(*plant) || world_.heroes.owner(source_ref(plant))==owner)continue;
        const auto goal=point(*plant);
        const auto distance=std::hypot(wrap_delta(position.x,goal.x,width),goal.y-tile*.5-(position.y-tile));
        if(distance>radius_*tile+1e-9)continue;
        bool replace=!best || distance<best_distance;
        if(best && distance==best_distance) {
            const auto& id=plant->source.id;
            const auto& old=best->source.id;
            if(id.is_null()!=old.is_null())throw std::logic_error("None potato tie identifier");
            replace=!id.is_null() && id.or_missing("")<old.or_missing("");
        }
        if(replace){best=plant;best_distance=distance;}
    }
    return best;
}
void SweetTaunts::apply(const ZombieRef& zombie) {
    const auto potato=taunting(CombatTarget::zombie(zombie));
    if(!potato)return;
    const auto id=key(*potato);
    if(id)zombie->taunted_by.set(*id);else zombie->taunted_by.set_null();
    const auto field=fields_.find(id);
    if(field!=fields_.end()) {
        const auto name=zombie->source.content.or_missing("");
        const bool flying=name.find("海盗鹦鹉")!=std::string::npos || name.find("乌鸦")!=std::string::npos;
        if(!flying) {
            saved_=baseline_?baseline_->chase:banks_.capture_chase();
            banks_.restore_chase(field->second.chase);
        }
    }
    const auto tile=world_.runtime.tile;
    const auto& position=zombie->body.motion.get();
    const int row=int(std::floor(position.y/tile));
    const auto column=int64_t(std::floor(position.x/tile));
    for(int y=row-3;y<row+2;++y) {
        if(!world_.terrain.valid_row(y))continue;
        const auto& line=world_.terrain.grid.at(size_t(y));
        if(line.empty())throw std::domain_error("empty taunt terrain row");
        const auto width=int64_t(line.size());
        for(auto x=column-2;x<column+3;++x) {
            const auto wrapped=(x%width+width)%width;
            const auto cell=line.at(size_t(wrapped));
            if(cell->plant.present() && !(potato->cell.y==y && potato->cell.x==wrapped)) {
                hidden_.push_back({cell,cell->plant});cell->plant.erase();
            }
        }
    }
}
void SweetTaunts::restore() {
    if(saved_){banks_.restore_chase(*saved_);saved_.reset();}
    for(auto at=hidden_.rbegin();at!=hidden_.rend();++at)at->tile->plant=at->marker;
    hidden_.clear();
}
std::optional<ContentTarget> SweetTaunts::taunt_target(const ContentTarget& source,std::optional<ContentTarget> fallback) {
    const auto potato=taunting(source);
    return potato?std::optional<ContentTarget>{potato}:fallback;
}
} // namespace pvz::typed72
