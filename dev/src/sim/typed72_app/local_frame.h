#pragma once
// Main-thread local display boundary. Never a network/replay snapshot and never
// thread-safe: the V projections and native lazy pixel handles stay on one owner.
#include "core/pyobj.h"
#include <functional>
namespace pvz::typed72 {struct NativeFrame;}
namespace pvz::typed72app {
struct LocalFrameStats {uint64_t frames=0,projected=0,considered=0,culled=0,full_fallbacks=0;};
struct LocalCommandBounds {bool image;double x,y;int width,height;std::string entity,layer;};
V make_local_frame(const typed72::NativeFrame&,const std::shared_ptr<LocalFrameStats>&);
// Returns the original value for an ordinary protocol frame. Private render
// shells are only consumed synchronously by DrawReplay, never published.
V select_local_frame(const V&,const std::function<bool(const LocalCommandBounds&)>&);
}
