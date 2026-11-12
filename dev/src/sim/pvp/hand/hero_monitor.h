#pragma once
#include "sim/pvp/pvprt.h"
#include <exception>
namespace pvz::pm_hero_guard {
size_t violation_count();
size_t reported_violation_count();
std::string last_violation();
class TickScope {
    V guard_;int uncaught_=0;
public:
    explicit TickScope(V battle);
    ~TickScope() noexcept(false);
};
class SpawnScope {
    V guard_,before_;int uncaught_=0;
public:
    explicit SpawnScope(V battle);
    ~SpawnScope() noexcept(false);
};
}
