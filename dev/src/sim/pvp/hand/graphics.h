// Native drawing bridge for the translated original draw code (replaces pvp/native_animation's
// NamespaceGraphics / DrawRecorder / _Pygame / NativeImage).
//   * Image: an atlas key plus a transform recipe (scale / flip / rotate / alpha) and its size.
//   * screen (DrawRecorder): records blit/fill/primitive commands per native frame for the renderer.
//   * pygame facade: transform.*, Surface(), draw.*, Rect(), constants.
#pragma once
#include "sim/pvp/pvprt.h"
#include <string>
#include <vector>

namespace pvz::gfx {
struct AtlasPixelCacheStats { uint64_t entries=0,bytes=0; };
AtlasPixelCacheStats sampled_atlas_pixel_cache_stats();
AtlasPixelCacheStats native_bridge_surface_cache_stats();

struct Recipe {
    std::string key;            // base asset ("world:<name>", "ui:<name>", "canvas")
    double sx = 1, sy = 1;      // not used for size; size is explicit
    bool flip_x = false, flip_y = false;
    double angle = 0;           // degrees (pygame.transform.rotate)
    int alpha = -1;             // -1 = per-pixel only
    bool pixel_alpha = true;
    V colorkey = V::none();
    std::vector<V> children;    // blits onto a canvas: [image recipe dump, pos]
};

struct Image : PyObj {
    Recipe r;
    int w = 0, h = 0;
    V recipe;                       // python NativeImage.recipe (asset / transform chain)
    V property(Sym name, bool& found) override {
        if (name == Sym("recipe")) { found = true; return recipe; }
        if (name == Sym("pixels")) { found = true; return callm(py::native_hook(V("graphics.recorded_image_pixels"), Args{self()}),Sym("copy"),Args{}); }
        found = false; return V();
    }
    const char* type_name() const override { return "Surface"; }
    bool isa(const char* c) const override { return std::string(c) == "Surface" || std::string(c) == "NativeImage" || std::string(c) == "object"; }
    V method(Sym name) override;
    V describe() const;
};
V make_image(const std::string& key, int w, int h);
Image* image_of(const V& v);

struct Command {
    enum Kind { IMAGE, FILL, PRIMITIVE } kind;
    V image;          // Image instance (for IMAGE)
    double x = 0, y = 0;
    V extra;          // area / color / primitive args
    std::string entity;
};

struct Recorder : PyObj {
    int tick = 0;
    bool enabled = true;
    std::vector<Command> commands;
    V entity_source;      // callable -> current source dict
    V entity_override;
    int width = 1024, height = 768;
    const char* type_name() const override { return "DrawRecorder"; }
    V* slot(Sym name) override;
    V method(Sym name) override;
    void append_command(V command);
    V commands_v = V::list();
    V enabled_v = V(true), override_v = V::none(), source_v = V::none(), tick_v = V(0.0), positions_v = V::dict(), size_v = V::tuple({V(1024.0), V(768.0)});
    V latest_pixels_v = V::none(), local_pixels_v = V::none(), command_ms_v = V(0.0), total_commands_v = V(0.0), max_commands_v = V(12000.0);
    V tile_v = V(48);
};

// Install pygame facade, screen recorder and atlas images into the match namespace.
// Returns the recorder (V instance).
V install_graphics(Match& G, int tile);
V make_pygame();
void install_atlases(Match& G);
// Load atlas sizes from extract/assets/index.json (or data/atlas_index.json)
void load_atlas_index(const std::string& path);
// baked atlas file for (atlas, key), e.g. ("图集", "向日葵") -> ".../_png/xxxx.png"; empty if unknown
std::string atlas_file(const std::string& atlas, const std::string& key);
std::vector<std::string> atlas_keys(const std::string& atlas);

}  // namespace pvz::gfx
