#include "sim/pvp/shim/pm_gc_policy.h"
#include "sim/pvp/hand/graphics.h"
#include <cmath>
#include <algorithm>
namespace pvz { namespace pm_gc_policy {
namespace {
struct NativeGcPolicy : PyObj {
    const char* type_name() const override { return "gc_policy"; }
    V method(Sym name) override {
        // No CPython generation collector exists in this standalone program.
        // Decline the optional policy explicitly; allocation remains C++ RAII.
        if(name==Sym("apply") || name==Sym("active"))return V::func([](const Args&){return V(false);});
        if(name==Sym("release"))return V::func([](const Args&){return V::none();});
        return V();
    }
};
}
V module_ns() {
    static V module=[] {
        V m=V::inst(std::make_shared<NativeGcPolicy>());
        pvz::setattr(m,Sym("supported"),V(false));
        pvz::setattr(m,Sym("backend"),V("c++-raii"));
        return m;
    }();
    return module;
}
void init() { static bool done = false; if (done) return; done = true; }
}}  // namespace pvz::pm_gc_policy
