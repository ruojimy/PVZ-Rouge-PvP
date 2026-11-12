#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz::typed72app {
// Wrap a freshly constructed V NativeBattle. The returned object has the NativeBattle members
// the room uses (tick, dt, result, players, log, rules, map, audit_error, terrain_revision,
// ai_subsidy_seats, step, snapshot, command_input, clear_input, close). Until the first step or
// command it reads the V battle (cold state); from then on every step, command and snapshot
// runs in the typed session. There is no V fallback for the battle.
V wrap_battle(const V& native_battle);
// Always "typed72": the shipped battle has no V backend.
const char* battle_backend();
// Start the typed session of a wrapped battle now (the room calls it when every seat has
// loaded); a no-op for anything else or an already started session.
void start_battle_session(const V& battle);
} // namespace pvz::typed72app
