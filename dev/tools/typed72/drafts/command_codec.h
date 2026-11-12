#pragma once
#include "sim/typed/command_input.h"
#include <nlohmann/json.hpp>
namespace pvz::typed72 {
// JSON belongs only at admission/network/replay boundaries, never in step().
CommandAttempt decode_command(const nlohmann::json&);
nlohmann::json encode_generated_command(int64_t sequence,const CommandPayload&);
}
