#include "sim/pvp/shim/pm_native_multiworker.h"
#include "sim/pvp/gen/pm_native_phase_profiler.h"
#include "sim/pvp/hand/graphics.h"
#include "sim/pvp/gen/pm_native_snapshot_worker.h"
#include <cmath>
#include <algorithm>
#include <cstdlib>
namespace pvz { namespace pm_native_multiworker {
// Snapshot work uses one bounded native OS thread, frozen inputs and real futures.
V cls_SnapshotPackWorker() { return pm_native_snapshot_worker::cls_SnapshotPackWorker(); }
V f_pack_snapshot_kernel(const Args& a) { return pm_native_snapshot_worker::f_pack_snapshot_kernel(a); }
V f_pack_snapshot_profile(const Args& a) { return pm_native_snapshot_worker::f_pack_snapshot_profile(a); }
// The original phase/statistics methods execute against actual bounded samples.
V new_PhaseProfiler(const Args& a) {
    pm_native_phase_profiler::init();
    return pm_native_phase_profiler::new_PhaseProfiler(a);
}
V cls_PhaseProfiler() { pm_native_phase_profiler::init(); return pm_native_phase_profiler::cls_PhaseProfiler(); }
V f_native_kernel_status(const Args&) { V d = V::dict(); d.at(V("loaded")) = V(false); d.at(V("reason")) = V("c++ build"); return d; }
namespace {
struct SerialJobs : PyObj {
    bool closed=false;
    const char* type_name() const override { return "JobSystem"; }
    V method(Sym name) override {
        auto self=std::static_pointer_cast<SerialJobs>(shared_from_this());
        if(name==Sym("close"))return V::func([self](const Args&){self->closed=true;return V::none();});
        if(name==Sym("run"))return V::func([self](const Args&)->V {
            if(self->closed)throw PyError("RuntimeError","JobSystem is closed");
            throw PyError("NotImplementedError","generic worker kernels are not implemented in the native serial backend");
        });
        return V();
    }
};
}
V cls_JobSystem() {
    static V c=py::class_value(V("JobSystem"),[](const Args& a) {
        if(!a.pos.empty() && a.pos[0].num()!=0)throw PyError("NotImplementedError","parallel native worker backend");
        return V::inst(std::make_shared<SerialJobs>());
    });
    return c;
}
V f_configured_workers(const Args& A) { return V(0.0); }
// PVP_SIM_FASTPATH: python default on (exact serial fast paths, native_patch.bind_targets)
V f_fastpath_enabled(const Args& A) {
    static const V none=V::none();V raw=A.get(0,Sym("value"),&none);
    if(raw.is_none()){const char* env=std::getenv("PVP_SIM_FASTPATH");raw=V(std::string(env?env:"1"));}
    V text=callm(callm(py::str(raw),Sym("strip"),Args{}),Sym("lower"),Args{});
    return V(!V::tuple({V("0"),V("off"),V("false"),V("no")}).contains(text));
}
void init() { static bool done = false; if (done) return; done = true; }
}}  // namespace pvz::pm_native_multiworker
