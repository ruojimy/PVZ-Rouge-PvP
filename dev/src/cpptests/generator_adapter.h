#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz::py {
struct TestGenFactory : PyObj {
    std::function<PyGen(GenCtl&)> factory;
    GenCtl control;
};
inline V make_test_gen(GenKind kind, std::function<PyGen(GenCtl&)> factory) {
    auto owner = std::make_shared<TestGenFactory>();
    owner->factory = std::move(factory);
    auto generator = owner->factory(owner->control);
    return make_gen(kind, std::move(generator), owner);
}
}
