#pragma once
#include "sim/typed/targets.h"

namespace pvz::typed72 {
// The owner's Dave remains eligible for the original utility branch while
// the normal plant pass targets the opposing Dave.
void owner_umbrella_effects(TypedBattleState&,bool after,std::span<const Seat> room_seats);
} // namespace pvz::typed72
