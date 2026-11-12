// Native equivalents of the original immutable snapshot kernels. Stages execute
// sequentially so later stages read the actual preceding result.
#include "sim/pvp/gen/pm_native_snapshot_worker.h"
#include "sim/pvp/hand/native_marshal.h"
#include <chrono>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#else
#include <time.h>
#endif
namespace pvz::pm_native_snapshot_worker {
namespace {
double cpu_ms() {
#ifdef _WIN32
    FILETIME creation, exit, kernel, user;
    if (!GetProcessTimes(GetCurrentProcess(), &creation, &exit, &kernel, &user))
        throw PyError("OSError", "GetProcessTimes failed");
    auto ticks=[](const FILETIME& t) { return (uint64_t(t.dwHighDateTime)<<32)|t.dwLowDateTime; };
    return double(ticks(kernel)+ticks(user))/10000.;
#else
    timespec t{};
    if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &t)) throw PyError("OSError", "process CPU clock failed");
    return double(t.tv_sec)*1000.+double(t.tv_nsec)/1e6;
#endif
}
V pack(const Args& a, bool profile) {
    using clock=std::chrono::steady_clock;
    const auto begin=clock::now();
    const double cpu_begin=profile?cpu_ms():0;
    V timings=V::dict();
    V value=py::native_marshal_loads(a);
    auto stage=[&](const char* name, const auto& operation) {
        const auto wall=clock::now(); const double cpu=profile?cpu_ms():0;
        V result=operation();
        if(profile) {
            const double elapsed=std::chrono::duration<double,std::milli>(clock::now()-wall).count();
            timings.at(V(std::string(name)+"_wall"))=V(elapsed);
            timings.at(V(std::string(name)+"_cpu"))=V(cpu_ms()-cpu);
        }
        return result;
    };
    V raw=stage("json_encode",[&] {
        V text=py::stdlib_call(V("json.dumps"),Args({value},{{Sym("ensure_ascii"),V(false)},
            {Sym("separators"),V::tuple({V(","),V(":" )})},{Sym("allow_nan"),V(false)}}));
        return callm(text,Sym("encode"),Args{V("utf-8")});
    });
    V compressed=stage("zlib_compress",[&] { return py::stdlib_call(V("zlib.compress"),Args{raw,V(4)}); });
    V encoded=stage("base64_encode",[&] {
        return callm(py::stdlib_call(V("base64.b64encode"),Args{compressed}),Sym("decode"),Args{V("ascii")});
    });
    if(!profile)return V::tuple({encoded,py::len(raw)});
    timings.at(V("task_wall"))=V(std::chrono::duration<double,std::milli>(clock::now()-begin).count());
    // Like Python time.process_time(), CPU timings cover the whole process.
    timings.at(V("task_cpu"))=V(cpu_ms()-cpu_begin);
    return V::tuple({encoded,py::len(raw),timings});
}
}
V f_pack_snapshot_kernel(const Args& a) { return pack(a,false); }
V f_pack_snapshot_profile(const Args& a) { return pack(a,true); }
}
