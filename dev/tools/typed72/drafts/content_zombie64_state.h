#pragma once
#include "sim/typed/field.h"
#include <memory>
#include <string>

namespace pvz::typed72 {
struct RedeyeGrab {Field<std::string> id;double ticks=0.;};
struct ContentZombie64State {
    Field<double> throw_clock;
    Field<std::shared_ptr<RedeyeGrab>> grab;
    Field<std::string> thrown_by,grabbed_by,hand_kind;
    Field<bool> split,sticky;
};
} // namespace pvz::typed72
