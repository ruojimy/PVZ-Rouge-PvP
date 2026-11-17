// Native equivalents of the original immutable snapshot kernels. Stages execute
// sequentially so later stages read the actual preceding result.
#include "sim/pvp/gen/pm_native_snapshot_worker.h"
#include "sim/pvp/hand/native_marshal.h"
#include "core/gil.h"
#include "core/snapshot_json.h"
#define Z_PREFIX
#include "zlib-1.3.2-compress/zlib.h"
#include <chrono>
#include <cstdlib>
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
V pack_detached(const Args& a,bool profile){
    const char* option=std::getenv("PVP743_SNAPSHOT_PACK");
    if((option&&std::string(option)=="0")||a.pos.size()!=1||!a.kw.empty())return pack(a,profile);
    // Copy while holding the GIL. No V (including reference counts and string
    // interning) may be accessed by the detached stages below.
    const std::string frozen=py::bytes_data(a.pos[0]);
    using clock=std::chrono::steady_clock;const auto begin=clock::now();
    double task_cpu=profile?cpu_ms():0,wall[3]{},cpu[3]{};
    std::string raw,encoded;bool supported=false;int error=Z_OK;
    {
        gil::Release release;
        auto stage=[&](int i,const auto& operation){auto start=clock::now();double c=profile?cpu_ms():0;operation();if(profile){wall[i]=std::chrono::duration<double,std::milli>(clock::now()-start).count();cpu[i]=cpu_ms()-c;}};
        stage(0,[&]{supported=snapshot_json_from_marshal(frozen,raw);});
        if(supported){
            std::string compressed;
            stage(1,[&]{uLongf size=compressBound(uLong(raw.size()));compressed.resize(size);error=compress2(reinterpret_cast<Bytef*>(compressed.data()),&size,reinterpret_cast<const Bytef*>(raw.data()),uLong(raw.size()),4);if(error==Z_OK)compressed.resize(size);});
            if(error==Z_OK)stage(2,[&]{
                static constexpr char alphabet[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
                encoded.reserve((compressed.size()+2)/3*4);
                for(size_t i=0;i<compressed.size();i+=3){unsigned n=unsigned((unsigned char)compressed[i])<<16;size_t remain=compressed.size()-i;if(remain>1)n|=unsigned((unsigned char)compressed[i+1])<<8;if(remain>2)n|=(unsigned char)compressed[i+2];encoded+=alphabet[(n>>18)&63];encoded+=alphabet[(n>>12)&63];encoded+=remain>1?alphabet[(n>>6)&63]:'=';encoded+=remain>2?alphabet[n&63]:'=';}
            });
        }
    }
    if(!supported)return pack(a,profile);
    if(error!=Z_OK)throw PyError(error==Z_MEM_ERROR?"MemoryError":"ValueError","snapshot zlib compression failed: "+std::to_string(error));
    V result=V(std::move(encoded));
    if(!profile)return V::tuple({result,V(double(raw.size()))});
    V timings=V::dict();const char* names[]={"json_encode","zlib_compress","base64_encode"};
    for(int i=0;i<3;++i){timings.at(V(std::string(names[i])+"_wall"))=V(wall[i]);timings.at(V(std::string(names[i])+"_cpu"))=V(cpu[i]);}
    timings.at(V("native_json_fast_path"))=V(1);
    timings.at(V("task_wall"))=V(std::chrono::duration<double,std::milli>(clock::now()-begin).count());timings.at(V("task_cpu"))=V(cpu_ms()-task_cpu);
    return V::tuple({result,V(double(raw.size())),timings});
}
}
V f_pack_snapshot_kernel(const Args& a) { return pack_detached(a,false); }
V f_pack_snapshot_profile(const Args& a) { return pack_detached(a,true); }
}
