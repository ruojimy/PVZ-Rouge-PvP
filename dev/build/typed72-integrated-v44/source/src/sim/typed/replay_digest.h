#pragma once
#include "sim/typed/room_wire.h"
namespace pvz::typed72 {
// Matches the effective C++ R8 json.dumps path in src/ui/stdlib.cpp,
// including its numeric spelling. It is not a new digest convention.
std::string native_replay_canonical(const WireObject&,bool sorted=true);
std::string native_replay_digest(const WireObject&);
std::string replay_sha256(const std::string&);
bool replay_snapshot_matches(const WireObject&,std::string_view expected,std::string_view format,std::string_view build);
}
