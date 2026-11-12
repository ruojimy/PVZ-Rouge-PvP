#include "ui/gen/pm_performance_probe.h"
#include "ui/gen/pm_original_pacing.h"
#include "ui/gen/pm_android_original_game.h"
// Native binding of the actual shared touch/keyboard control layer.
#include "pg/pg.h"
#include "sim/pvp/pvprt.h"
#include "ui/gen/pm_android_original_touch.h"
namespace pvz::pg {
void register_android_native_modules() {
    V module=new_module("modkit.android.original_touch");
    module_of(module)->add("OriginalTouch",pm_android_original_touch::cls_OriginalTouch());
    module_of(module)->add("PressedKeys",pm_android_original_touch::cls_PressedKeys());
    module_of(module)->fn("install",[](const Args& a){pm_android_original_touch::init();return pm_android_original_touch::f_install(a);});
    py::register_module("modkit.android.original_touch",module);
    V probe=new_module("modkit.android.performance_probe");
    module_of(probe)->add("Driver",pm_performance_probe::cls_Driver());
    module_of(probe)->fn("run",[](const Args& a){pm_performance_probe::init();return pm_performance_probe::f_run(a);});
    py::register_module("modkit.android.performance_probe",probe);
    V pacing=new_module("modkit.android.original_pacing");
    module_of(pacing)->add("OriginalPacing",pm_original_pacing::cls_OriginalPacing());
    module_of(pacing)->fn("arm",[](const Args& a){pm_original_pacing::init();return pm_original_pacing::f_arm(a);});
    py::register_module("modkit.android.original_pacing",pacing);
    V original=py::stdlib_module(V("modkit.android.original_game"));
    module_of(original)->add("os",py::stdlib_module(V("os")));
    module_of(original)->fn("persistent_home",[](const Args& a){pm_android_original_game::init();return pm_android_original_game::f_persistent_home(a);});
    module_of(original)->fn("asset_root",[](const Args& a){pm_android_original_game::init();return pm_android_original_game::f_asset_root(a);});
    V modkit=py::stdlib_module(V("modkit"));
    pvz::setattr(pvz::getattr(modkit,Sym("android")),Sym("original_touch"),module);
    pvz::setattr(pvz::getattr(modkit,Sym("android")),Sym("performance_probe"),probe);
    pvz::setattr(pvz::getattr(modkit,Sym("android")),Sym("original_pacing"),pacing);
}
}
