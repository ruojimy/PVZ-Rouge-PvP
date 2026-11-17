// Pixel-owning implementation translated from native_animation.py. Match recording
// keeps its recipe storage; direct pixel API calls execute the same production classes.
#include "pg/pg.h"
#include "ui/gen/pm_native_animation_pixels.h"
#include "sim/pvp/pvprt.h"
#include "ui/gen/pm_performance.h"
#include "sim/pvp/hand/graphics.h"
#include "sim/pvp/gen/pm_native_animation.h"

namespace pvz::pm_performance {
V C_FramePixels::m_get(const Args& a) {
    const V frame=a.get(0,SY("frame"),nullptr,"get");
    const V description=a.get(1,SY("description"),nullptr,"get");
    if(!py_is(frame,a_frame))return V::none();
    const V entry=py::m_get(a_images,py::id(description));
    if(entry.is_none() || !py_is(entry.idx(0),description))return V::none();
    const V value=entry.idx(1);
    // A packet owns this frozen image. Its pixel identity must remain stable
    // across reads; the public Image.pixels property deliberately returns a
    // defensive copy for callers who may mutate it.
    if(gfx::image_of(value))return py::native_hook("graphics.recorded_image_pixels",Args{value});
    const V image_class=pvz::getattr(pm_native_animation::module_ns(),SY("NativeImage"));
    return py::isinstance_v(value,image_class).truthy()?pvz::getattr(value,SY("pixels")):value;
}
}

namespace pvz::pg {
void register_pixel_graphics_hooks() {
    py::register_native_hook("graphics.frame_pixels",[](const Args& args){return pm_performance::new_FramePixels(args);});
    py::register_native_hook("graphics.namespace", [](const Args& a) {
        return pm_native_animation_pixels::new_NamespaceGraphics(a);
    });
    py::register_native_hook("graphics.export_sources", [](const Args& a) {
        auto object = std::make_shared<pm_native_animation_pixels::C_NamespaceGraphics>();
        object->a_pg = py::stdlib_module(V("pygame"));
        object->a_sources = a.pos.at(0);
        Args keys; if (a.pos.size() > 1) keys.pos.push_back(a.pos.at(1));
        return object->m_export_assets(keys);
    });
#define PIXEL_CLASS(N) \
    py::register_native_hook("graphics.new." #N, [](const Args& a) { return pm_native_animation_pixels::new_##N(a); }); \
    py::register_native_hook("graphics.class." #N, [](const Args&) { return pm_native_animation_pixels::cls_##N(); });
    PIXEL_CLASS(NativeImage) PIXEL_CLASS(DeferredImage) PIXEL_CLASS(_DeferredTransform)
    PIXEL_CLASS(_Transforms) PIXEL_CLASS(_Draw) PIXEL_CLASS(_Pygame) PIXEL_CLASS(DrawRecorder)
#undef PIXEL_CLASS
}
} // namespace pvz::pg
