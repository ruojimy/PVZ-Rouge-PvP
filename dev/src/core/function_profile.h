#pragma once
// Explicit diagnostics only. These inclusive timers never enter replay state.
#include <chrono>
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <map>
#include <mutex>
#include <string>
namespace pvz::function_profile {
inline bool enabled(){static const bool value=[] {const auto p=std::getenv("PVP741_PROFILE");return p&&std::string(p)=="1";}();return value;}
struct Entry {uint64_t calls=0;double total_ms=0.,max_ms=0.;};
inline std::map<std::string,Entry>& entries(){static std::map<std::string,Entry> values;return values;}
inline std::mutex& mutex(){static std::mutex value;return value;}
using Clock=std::chrono::steady_clock;
inline void record(const char* name,Clock::time_point start){
    const double ms=std::chrono::duration<double,std::milli>(Clock::now()-start).count();
    std::lock_guard lock(mutex());auto& row=entries()[name];++row.calls;row.total_ms+=ms;row.max_ms=std::max(row.max_ms,ms);
}
struct Scope {
    const char* name;Clock::time_point start;
    explicit Scope(const char* value):name(enabled()?value:nullptr){if(name)start=Clock::now();}
    ~Scope(){if(name)record(name,start);}
};
// Disjoint phases inside one function, in addition to the function's inclusive timer.
struct Phases {
    bool active=enabled();Clock::time_point start;
    Phases(){if(active)start=Clock::now();}
    void mark(const char* name){if(active){record(name,start);start=Clock::now();}}
};
inline auto snapshot(){std::lock_guard lock(mutex());return entries();}
inline void reset(){std::lock_guard lock(mutex());entries().clear();}
}
#define PVP_PROFILE_JOIN_(a,b) a##b
#define PVP_PROFILE_JOIN(a,b) PVP_PROFILE_JOIN_(a,b)
#define PVP_PROFILE_SCOPE(name) pvz::function_profile::Scope PVP_PROFILE_JOIN(pvp_function_timer_,__LINE__)(name)
