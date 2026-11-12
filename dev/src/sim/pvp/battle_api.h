// Entry points for building and stepping a translated PvP battle from C++.
#pragma once
#include "sim/pvp/pvprt.h"
#include <nlohmann/json.hpp>
#include <ostream>

namespace pvz {

struct BattleHandle {
    V battle;    // pm_native_battle::C_NativeBattle instance
    V bridge;
};

// Initialise every translated module (idempotent).
void init_pvp_modules();

// Same construction as tools/oracle_record.py build(): map/seed/weather/night/decks/setup.
BattleHandle battle_from_scenario(const nlohmann::json& sc);

// Step `room_ticks` room ticks; write one JSON line per native tick (oracle format).
void battle_record_jsonl(BattleHandle& b, const nlohmann::json& sc, std::ostream& out);

}  // namespace pvz
