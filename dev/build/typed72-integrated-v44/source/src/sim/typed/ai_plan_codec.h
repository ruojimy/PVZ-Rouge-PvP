#pragma once
#include "sim/typed/ai_controls.h"
#include "sim/typed/room_wire.h"
namespace pvz::typed72 {
AiPlan decode_ai_plan(const WireObject&,std::span<const std::string> deck);
}
