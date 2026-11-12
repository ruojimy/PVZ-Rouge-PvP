#include "sim/pvp/shim/pm_expansion_assets.h"
#include "sim/pvp/hand/graphics.h"
#include <cmath>
#include <algorithm>
#include "sim/pvp/gen/pm_expansion_catalog.h"
namespace pvz { namespace pm_expansion_assets {
V f_install(const Args& A) { return V::none(); }
V cls_TemplateAtlas() {
    static V c=py::class_value(V("TemplateAtlas"),[](const Args& A){
        if(A.pos.size()>1)throw PyError("TypeError","TemplateAtlas expected at most one positional input");
        V input=V::dict();if(!A.pos.empty())for(const auto& item:py::items_vec(py::dict_of(A.pos.at(0))))input.at(item.first)=item.second;for(const auto& item:A.kw)input.at(V(item.first))=item.second;
        V getter=V::func([](const Args&){pm_expansion_catalog::init();V mapping=V::dict();for(const auto& item:py::items_vec(pm_expansion_catalog::GLADIATOR_ZOMBIES))mapping.at(item.first)=item.second.idx(0);return mapping;});
        return py::native_hook(V("core.template_atlas"),Args{input,cls_TemplateAtlas(),getter});
    });return c;
}
void init() { static bool done = false; if (done) return; done = true; }
}}  // namespace pvz::pm_expansion_assets
