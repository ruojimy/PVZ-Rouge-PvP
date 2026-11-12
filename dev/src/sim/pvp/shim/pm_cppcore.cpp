#include "sim/pvp/shim/pm_cppcore.h"
#include "sim/pvp/hand/graphics.h"
#include <cmath>
#include <algorithm>
namespace pvz { namespace pm_cppcore {
namespace {
V attrs(Sym name) {
    const std::string& key=name.str();
    if(key=="status")return V::func(f_status);if(key=="configure_final_regions")return V::func(f_configure_final_regions);
    if(key=="copy_module")return V::func(f_copy_module);if(key=="fast_deepcopy")return V::func(f_fast_deepcopy);
    if(key=="native")return V::func(f_native);if(key=="native_for")return V::func(f_native_for);return V();
}
}
V module_ns(){init();return py::module_ns(V("cppcore"));}
V f_configure_final_regions(const Args& A) { return V::none(); }
V f_copy_module(const Args& A) { return py::stdlib_module(SV("copy")); }
V f_fast_deepcopy(const Args& A) { return A.pos.empty()?V::none():pvz::deepcopy(A.pos[0]); }
V f_native(const Args& A) { return V::none(); }
V f_status(const Args&) { V d = V::dict(); d.at(V("active")) = V(false); d.at(V("reason")) = V("c++ build"); return d; }
V f_native_for(const Args& A) { return V::none(); }
void init() { static bool done=false;if(done)return;done=true;py::register_module_attrs("cppcore",attrs);py::note_module_loaded("pvp.cppcore"); }
}}  // namespace pvz::pm_cppcore
