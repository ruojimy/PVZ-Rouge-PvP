#pragma once
#include "sim/typed/geometry.h"
#include <cstdint>
#include <string>
#include <vector>
namespace pvz::typed72 {
struct FumeBubble {std::string name;Motion motion;int64_t age=0,life=30;};
struct FumeState {std::vector<FumeBubble> bubbles;double last_update=0.;};
} // namespace pvz::typed72
