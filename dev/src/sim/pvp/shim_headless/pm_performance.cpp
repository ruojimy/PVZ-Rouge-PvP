#include "sim/pvp/shim/pm_performance.h"
#include "sim/pvp/hand/graphics.h"
#include <cmath>
#include <algorithm>
#include <cstdlib>
#include <cctype>
namespace pvz { namespace pm_performance {
V f_enabled(const Args& A) {
    std::string name="PVP_"+A.get(0,Sym("name"),nullptr).str();const char* value=std::getenv(name.c_str());
    std::string raw=value?value:"1";for(char& ch:raw)ch=char(std::tolower(static_cast<unsigned char>(ch)));
    return V(raw!="0" && raw!="false" && raw!="off" && raw!="no");
}
V cls_FramePixels() { static V c = V::func([](const Args& A) { return py::noop_module(SV("FramePixels")); }); return c; }
void init() { static bool done = false; if (done) return; done = true; }
}}  // namespace pvz::pm_performance
