#include "sim/typed/entity_phase.h"
#include "sim/typed/plant_lookup.h"
#include <cmath>
#include <set>

namespace pvz::typed72 {
namespace {
class HiddenGhostCells {
public:
    HiddenGhostCells(TypedBattleState& world,bool hide) {
        if(!hide)return;
        std::set<std::pair<int,int64_t>> occupied;
        const auto& roster=*world.plant_roster;
        for(const auto& p:roster)if(september_targetable(*p))occupied.emplace(p->cell.y,p->cell.x);
        saved_.reserve(roster.size());
        for(const auto& p:roster) {
            if(occupied.contains({p->cell.y,p->cell.x}))continue;
            const auto equals=[](const Field<std::string>& f,std::string_view v){return f.present()&&!f.is_null()&&f.get()==v;};
            if(!equals(p->source.content,"幽灵辣椒") &&
               !(p->kind=="模仿者" && equals(p->copy_card,"plant:幽灵辣椒")))continue;
            const auto cell=world.terrain.at(p->cell.y,world.terrain.wrap(p->cell.x));
            if(cell && cell->plant.present()){saved_.emplace_back(cell,cell->plant);cell->plant.erase();}
        }
    }
    ~HiddenGhostCells(){for(const auto& [cell,flag]:saved_)cell->plant=flag;}
private:
    std::vector<std::pair<TileRef,Field<bool>>> saved_;
};
}
Seat EntityPhase::nearest_plant(Point point)const {
    const auto& heroes=world_.heroes;const double width=world_.world_width.get();
    std::optional<std::pair<double,Seat>> best;
    for(const auto seat:seats_for(world_.mode)) {
        if(team_of(seat)!=Seat::plant || heroes.players[seat_index(seat)].value().hp<=0.)continue;
        const auto& p=*heroes.heroes[seat_index(seat)].value().frame.position.get();
        const auto key=std::pair{std::hypot(wrap_delta(point.x,p.x,width),point.y-p.y),seat};
        if(!best || key<*best)best=key;
    }
    return best?best->second:Seat::plant;
}
void EntityPhase::switch_dave(Seat seat) {
    if(world_.heroes.aliases[seat_index(Seat::plant)]==seat_index(seat))return;
    services_.release_pending_destination();world_.heroes.switch_plant_globals(seat);
}
void EntityPhase::tracking_gate(size_t index) {
    const auto e=world_.runtime.entities.list()->at(index);
    if(entry_){const auto& p=e->motion.get();switch_dave(nearest_plant({p.x,p.y-world_.runtime.tile*.5}));}
    auto& art=world_.runtime.presentation.source_art;
    art.clear();tracking_.restore();
    const auto source=TrackingSource::from(e);tracking_.begin(source);
    if(e->art_name.present() && !e->art_name.is_null() && !e->art_name.get().empty()) {
        for(const char* suffix:{"","-受伤","-冰冻","-灰烬","-魅惑"}) {
            std::string old=e->kind+suffix,replacement=e->art_name.get()+suffix;
            if(services_.has_sprite(old)&&services_.has_sprite(replacement))art.emplace(std::move(old),std::move(replacement));
        }
    }
    if(e->tracking.present())tracking_.tracking_index(source);
}
EntitySprite EntityPhase::sprite(EntitySprite s)const {
    if(const auto* name=std::get_if<std::string>(&s))return world_.runtime.presentation.sprite_name(*name);
    return s;
}
void EntityPhase::draw(EntityDraw d){d.sprite=sprite(std::move(d.sprite));services_.draw(std::move(d));}
void EntityPhase::alpha(const EntitySprite& s,double a){services_.alpha(sprite(s),a);}
void EntityPhase::run_owner(Seat owner) {
    auto& heroes=world_.heroes;
    const bool switching=owner==Seat::zombie && (world_.mode==MatchMode::duo || world_.mode==MatchMode::coop);
    if(switching){
        const auto& p=*heroes.heroes[seat_index(Seat::plant)].value().frame.position.get();
        entry_=nearest_plant({p.x,p.y});heroes.select_plant_seat(*entry_);
    }
    struct RestoreAlias {
        HeroCombat& heroes;std::optional<Seat>& entry;
        ~RestoreAlias(){if(entry){heroes.select_plant_seat(Seat::plant);entry.reset();}}
    } alias{heroes,entry_};
    HeroContext context(heroes,{owner==Seat::plant?Seat::zombie:Seat::plant,owner,CombatPhase::entities,{},{}});
    HiddenGhostCells hidden(world_,owner==Seat::zombie);
    const auto finish=[&]{
        if(entry_)switch_dave(*entry_);
        world_.runtime.presentation.source_art.clear();tracking_.restore();
    };
    try{region_.run();}catch(...){finish();throw;}
    finish();
}
void EntityPhase::run() {
    tracking_.target_index();
    torches_.tick();torches_.ignite_charmed_peas();
    auto& entities=world_.runtime.entities;
    const auto original=entities.list();
    auto completed=std::make_shared<EntityRoster>();completed->reserve(original->size());
    try {
        for(const Seat owner:{Seat::plant,Seat::zombie}) {
            auto list=std::make_shared<EntityRoster>();
            for(const auto& e:*original) {
                const auto& field=e->source.owner;
                if((!field.present() && owner==Seat::plant) ||
                   (field.present() && !field.is_null() && field.get()==seat_name(owner)))list->push_back(e);
            }
            entities.exchange_view(std::move(list));
            run_owner(owner);
            const auto done=entities.list();
            completed->insert(completed->end(),done->begin(),done->end());
        }
        entities.replace(std::move(completed));
    }catch(...) {
        // Restore the owning list before propagating a failed tick to the
        // match. Never resume simulation using a half-completed owner view.
        entities.replace(original);throw;
    }
}
} // namespace pvz::typed72
