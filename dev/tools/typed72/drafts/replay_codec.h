#pragma once
#include "sim/typed/replay_driver.h"
#include "sim/typed/room_wire.h"
#include <string_view>

namespace pvz::typed72 {
struct ReplayIdentity {std::string build,catalog_hash,rules_hash;};
class ReplayAdmission {
public:
    virtual ~ReplayAdmission()=default;
    virtual void validate_map(const WireObject&)=0;
};
struct ReplayDocument {
    ReplayData playback;
    WireObject metadata,initial;
};
ReplayDocument decode_replay(std::string_view bytes,const ReplayIdentity&,const WireObject& rule_schema,ReplayAdmission&);
WireObject legacy_replay_input(const WireObject& input);
WireObject recorded_replay_input(const WireObject& input,std::string_view format);
// This helper implements the one explicitly supported R8 presentation-only
// normalization. Combat fields are never changed to satisfy an old digest.
bool normalize_r8_rope_width(WireObject& snapshot,std::string_view format,std::string_view build);
} // namespace pvz::typed72
