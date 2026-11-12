#include "ui/gen/pm_app.h"
#include "core/resource_paths.h"
#include "core/fsutil.h"
namespace pvz::pm_app {
V f__workspace(const Args&) { return py::path_new(Args{V(p8(native_workspace()))}); }
}
