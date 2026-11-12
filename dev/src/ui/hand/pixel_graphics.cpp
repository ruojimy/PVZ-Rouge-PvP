// Pixel-owning implementation translated from native_animation.py. Match recording
// keeps its recipe storage; direct pixel API calls execute the same production classes.
#include "pg/pg.h"
#include "ui/gen/pm_native_animation_pixels.h"
#include "sim/pvp/pvprt.h"
#include "ui/gen/pm_performance.h"

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
