#include "sim/typed/zombie_phase.h"
#include "sim/typed/phase_context.h"

namespace pvz::typed72 {
void ZombiePhase::switch_plant(Seat seat) {
    if(world_.heroes.aliases[seat_index(Seat::plant)]==seat_index(seat))return;
    services_.release_pending_destination();
    world_.heroes.switch_plant_globals(seat);
}

void ZombiePhase::zombie_gate(size_t index) {
    if(entry_) {
        const auto target=world_.targets->at(index);
        if(!target.unit)throw std::logic_error("hero in mobile zombie gate");
        const auto& position=target.unit->body.motion.get();
        switch_plant(nearest_plant_seat(world_,{position.x,position.y-world_.runtime.tile*.5},present_));
        paths_.switch_for(*target.unit,present_);
    }
    services_.zombie_gate(index);
}

void ZombiePhase::mobile_actions(bool multi_plant) {
    auto& heroes=world_.heroes;
    if(multi_plant) {
        const auto& position=*heroes.heroes.at(seat_index(Seat::plant)).value().frame.position.get();
        entry_=nearest_plant_seat(world_,{position.x,position.y},present_);
        heroes.select_plant_seat(*entry_);
        paths_.begin_zombies();
    }
    const auto restore_alias=[&] {
        if(!entry_)return;
        paths_.end_zombies();
        heroes.select_plant_seat(Seat::plant);
        entry_.reset();
    };
    try {
        HeroContext context(heroes,{Seat::plant,Seat::zombie,CombatPhase::zombies,{},{}});
        HiddenGhostCells hidden(world_);
        const auto switch_back=[&]{if(entry_)switch_plant(*entry_);};
        try {
            actions_.run();
            services_.finish_content_zombie();
            services_.finish_expansion_zombie();
        }catch(...) {
            switch_back();
            throw;
        }
        switch_back();
        hidden.close();
        context.close();
    }catch(...) {
        restore_alias();
        throw;
    }
    restore_alias();
}

std::vector<ZombieRef> ZombiePhase::run(std::span<const Seat> present,bool multi_plant) {
    present_=present;
    std::vector<ZombieRef> graves,barrels;
    auto mobiles=std::make_shared<TargetRoster>();
    const auto original=world_.targets;
    mobiles->reserve(original->size());
    for(const auto& target:*original) {
        if(!target.unit){mobiles->push_back(target);continue;}
        const auto& unit=target.unit;
        if(unit->orphan_barrel && unit->body.hp>0.)barrels.push_back(unit);
        if(unit->protection.grave) {
            if(unit->body.hp>0. && !unit->body.ash.present())graves.push_back(unit);
        }else if(!unit->orphan_barrel)mobiles->push_back(target);
    }
    world_.targets=std::move(mobiles);
    world_.suspended_graves=graves;
    world_.suspended_graves.insert(world_.suspended_graves.end(),barrels.begin(),barrels.end());
    const auto restore_stationary=[&] {
        taunts_.restore();
        paths_.restore_rally();
        // Use the currently installed roster. A summon or content callback
        // may have replaced the list while the mobile region was running.
        for(const auto& unit:graves)world_.targets->push_back(CombatTarget::zombie(unit));
        for(const auto& unit:barrels)world_.targets->push_back(CombatTarget::zombie(unit));
        world_.suspended_graves.clear();
    };
    try {mobile_actions(multi_plant);}
    catch(...) {restore_stationary();throw;}
    restore_stationary();
    return graves;
}
} // namespace pvz::typed72
