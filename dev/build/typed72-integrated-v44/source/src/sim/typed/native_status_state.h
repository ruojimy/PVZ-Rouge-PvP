#pragma once
#include "sim/typed/allegiance.h"
#include "sim/typed/field.h"
#include <memory>
#include <string>
#include <utility>
#include <vector>

namespace pvz::typed72 {
struct PoisonLayer {
    double until=0.,next=0.;
    Seat owner=Seat::plant;
};
// Strength insertion order is observable when both pulses kill on one tick.
// Retained layer references survive synchronous replacement by a new hit.
using PoisonLayers=std::vector<std::pair<int,std::shared_ptr<PoisonLayer>>>;
struct PoisonState {
    Field<int> level;
    Field<double> until,next;
    Field<Seat> owner;
    // Old records store only the four summary fields. They are normalized
    // lazily at the same entry as NativeStatus.layers in the frozen source.
    Field<std::shared_ptr<PoisonLayers>> layers;
    bool empty()const noexcept {
        return !level.present() && !until.present() && !next.present() && !owner.present() && !layers.present();
    }
};
using PoisonSlot=Field<std::shared_ptr<PoisonState>>;
struct ZombiePoisonState {
    PoisonSlot poison;
    Field<bool> killed,armor_triggered;
    Field<std::string> imp_armor;
    Field<double> imp_armor_hp;
};
} // namespace pvz::typed72
