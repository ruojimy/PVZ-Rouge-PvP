#pragma once
#include "sim/typed/ai_observation_builder.h"
#include "sim/typed/room_wire.h"
namespace pvz::typed72 {
// Optional diagnostic/remote-brain boundary; local controllers consume the
// typed observation directly and never serialize during their control step.
WireObject encode_ai_observation(const AiObservation&);
}
