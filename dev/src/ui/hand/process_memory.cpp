// The same measurements as performance_window.process_memory, using native APIs.
#include "ui/gen/pm_performance_window.h"
#include <fstream>
#include <sstream>
#include <map>
#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#pragma comment(lib, "psapi.lib")
#endif
namespace pvz::pm_performance_window {
V f_process_memory(const Args&) {
#ifdef _WIN32
    PROCESS_MEMORY_COUNTERS_EX row{};
    row.cb=sizeof(row);
    if (!GetProcessMemoryInfo(GetCurrentProcess(),reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&row),sizeof(row)))
        return py_dict({{V("available"),V(false)}});
    return py_dict({{V("available"),V(true)},{V("rss_bytes"),V(double(row.WorkingSetSize))},
        {V("peak_rss_bytes"),V(double(row.PeakWorkingSetSize))},{V("private_commit_bytes"),V(double(row.PrivateUsage))},
        {V("source"),V("GetProcessMemoryInfo")}});
#else
    std::ifstream file("/proc/self/status");
    if (!file) return py_dict({{V("available"),V(false)}});
    std::map<std::string,double> fields;
    for (std::string line;std::getline(file,line);) {
        auto colon=line.find(':'); if (colon==std::string::npos) continue;
        std::istringstream value(line.substr(colon+1)); double kb;
        if (value>>kb) fields[line.substr(0,colon)]=kb*1024.;
    }
    if (!fields.count("VmRSS") || !fields.count("VmHWM") || !fields.count("VmSize"))
        return py_dict({{V("available"),V(false)}});
    return py_dict({{V("available"),V(true)},{V("rss_bytes"),V(fields["VmRSS"])},
        {V("peak_rss_bytes"),V(fields["VmHWM"])},{V("private_commit_bytes"),V::none()},
        {V("virtual_bytes"),V(fields["VmSize"])},{V("source"),V("/proc/self/status")}});
#endif
}
} // namespace pvz::pm_performance_window
