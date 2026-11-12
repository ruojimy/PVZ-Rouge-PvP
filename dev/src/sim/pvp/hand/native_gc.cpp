// Native manual collector for traceable containers. No CPython generation or
// native-instance cycle collector is advertised by this module.
#include "sim/pvp/pvprt.h"
#include <cmath>
namespace pvz {
size_t collect_container_cycles();
size_t native_live_box_count();
namespace py {
namespace {
struct NativeGC final : PyObj {
    V callbacks=V::list();bool collecting=false;
    size_t collections=0,reclaimed=0;
    const char* type_name() const override {return "module";}
    V* slot(Sym name) override {return name==Sym("callbacks")?&callbacks:nullptr;}
    V property(Sym name,bool& found) override {
        found=true;
        if(name==Sym("__name__"))return V("gc");
        if(name==Sym("native_capabilities"))return py_dict({
            {V("backend"),V("native-conservative-container-cycles")},
            {V("manual_collection"),V(true)},{V("automatic_generations"),V(false)},
            {V("native_instance_cycles"),V(false)},{V("opaque_closure_cycles"),V(false)},
            {V("weakref_callbacks"),V(false)}});
        found=false;return V();
    }
    V method(Sym name) override {
        auto self=std::static_pointer_cast<NativeGC>(shared_from_this());
        if(name==Sym("collect"))return V::func([self](const Args& a){return self->collect(a);});
        if(name==Sym("isenabled"))return V::func([](const Args& a){if(a.size() || !a.kw.empty())throw PyError("TypeError","isenabled takes no arguments");return V(false);});
        if(name==Sym("native_statistics"))return V::func([self](const Args& a){
            if(a.size() || !a.kw.empty())throw PyError("TypeError","native_statistics takes no arguments");
            return py_dict({{V("collections"),V(double(self->collections))},{V("reclaimed_containers"),V(double(self->reclaimed))},{V("live_boxes"),V(double(native_live_box_count()))}});
        });
        return V();
    }
    V collect(const Args& a) {
        if(a.pos.size()>1 || (a.pos.size() && a.has_kw(Sym("generation"))))throw PyError("TypeError","collect expects at most one generation");
        for(const auto& kw:a.kw)if(kw.first!=Sym("generation"))throw PyError("TypeError","unexpected collect keyword "+kw.first.str());
        V generation=a.pos.empty()?V(2):a.pos[0];
        for(const auto& kw:a.kw)if(kw.first==Sym("generation"))generation=kw.second;
        if(!generation.is_num() || std::floor(generation.num())!=generation.num())throw PyError("TypeError","generation must be an integer");
        if(generation.num()<0 || generation.num()>2)throw PyError("ValueError","invalid generation");
        if(collecting)throw PyError("RuntimeError","native collection is already active");
        collecting=true;struct End {bool& active;~End(){active=false;}} end{collecting};
        // A snapshot makes callback registration/removal during a callback safe.
        V observers=py::list_it(callbacks);
        V info=py_dict({{V("generation"),generation},{V("collected"),V(0)},{V("uncollectable"),V(0)},
            {V("backend"),V("native-conservative-container-cycles")},{V("scope"),V("all traceable containers; opaque roots retained")}});
        for(const V& callback:observers.items())callback.call(Args{V("start"),info});
        size_t count=collect_container_cycles();++collections;reclaimed+=count;
        info.at(V("collected"))=V(double(count));
        for(const V& callback:observers.items())callback.call(Args{V("stop"),info});
        return V(double(count));
    }
};
}
V native_gc_module() {
    static V module=V::inst(std::make_shared<NativeGC>());
    return module;
}
}
}
