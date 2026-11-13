#pragma once
#include "sim/pvp/pvprt.h"

namespace pvz::seat_view {
// Network HUDs exchange the local secondary seat with its team's primary key.
// Members / profiles retain authority seat IDs. Undo that view-only exchange
// when a screen lists players by authority seat; never rewrite the snapshot.
inline V player_for_authority_seat(const V& battle, const V& seat) {
    const V players = py::m_get(battle, SV("players"), py_dict({}));
    const V local = py::m_get(battle, SV("local_seat"));
    V key = seat;
    if (local == SV("plant2") || local == SV("zombie2")) {
        const V team = local == SV("plant2") ? SV("plant") : SV("zombie");
        if (py::in(local, players) && py::in(team, players)) {
            if (seat == team) key = local;
            else if (seat == local) key = team;
        }
    }
    return py::m_get(players, key, py_dict({}));
}
}
