// pygame-compatible facade over SDL2 for the translated PvP71 UI modules.
//
// The UI code (app.py, rendering.py, world_view.py, lobby_room.py ...) is translated by
// tools/pvp2cpp.py and talks to "pygame" through this module object: py::stdlib_module("pygame")
// resolves here once install_pygame() ran. Surfaces are SDL software surfaces (ARGB8888);
// the display surface is uploaded to a streaming texture on flip().
#pragma once
#include "core/pyobj.h"
#include "sim/pyrt.h"
#include <SDL.h>
#include <string>

namespace pvz::pg {

struct Surface : PyObj {
    SDL_Surface* s = nullptr;
    bool srcalpha = false;          // per-pixel alpha (SRCALPHA)
    int alpha = -1;                 // surface alpha (set_alpha), -1 = none
    bool has_colorkey = false;
    uint32_t colorkey = 0;
    V parent;                       // subsurface: keeps the pixel owner alive
    int off_x = 0, off_y = 0;       // subsurface offset in the parent
    bool is_display = false;
    uint64_t diagnostic_storage_bytes = 0;
    bool diagnostic_counted = false;
    ~Surface() override;
    const char* type_name() const override { return "Surface"; }
    bool isa(const char* c) const override { return std::string(c) == "Surface" || std::string(c) == "object"; }
    V method(Sym name) override;
    bool call_method(Sym name, const Args& a, V& out) override;
    int w() const { return s ? s->w : 0; }
    int h() const { return s ? s->h : 0; }
};

// new ARGB8888 surface (alpha channel always present; srcalpha decides blending semantics)
V new_surface(int w, int h, bool srcalpha);
V wrap_surface(SDL_Surface* s, bool srcalpha);   // takes ownership
Surface* surf(const V& v);                       // Surface or TypeError

struct IRect { int x = 0, y = 0, w = 0, h = 0; };
V make_rect(int x, int y, int w, int h);
bool rect_from(const V& v, IRect& out);          // Rect / (x,y,w,h) / ((x,y),(w,h))
IRect rect_of(const V& v);                       // TypeError on failure
bool color_from(const V& v, SDL_Color& out);     // (r,g,b[,a]) / Color / name
SDL_Color color_of(const V& v);

// module construction: attribute-access object over a name -> value table
struct Module : PyObj {
    std::string name;
    std::vector<std::pair<Sym, V>> attrs;
    const char* type_name() const override { return "module"; }
    V property(Sym n, bool& found) override {
        for (auto& p : attrs) if (p.first == n) { found = true; return p.second; }
        found = false; return V();
    }
    bool set_property(Sym n, const V& v) override {
        for (auto& p : attrs) if (p.first == n) { p.second = v; return true; }
        attrs.emplace_back(n, v); return true;
    }
    bool call_method(Sym n, const Args& a, V& out) override {
        for (auto& p : attrs) if (p.first == n) { out = p.second.call(a); return true; }
        return false;
    }
    void add(const char* n, V v) { attrs.emplace_back(Sym(n), std::move(v)); }
    void fn(const char* n, Fn f) { attrs.emplace_back(Sym(n), V::func(std::move(f))); }
};
V new_module(const char* name);
// a path handed to SDL (IMG / Mix / TTF / RWFromFile): on Android SDL resolves relative paths inside the
// APK assets, but the game data is unpacked into the cwd (internal storage) -> make it absolute there
std::string sdl_path(const std::string& p);
Module* module_of(const V& m);
V pygame_module();                               // the "pygame" module object
V surface_type();                                // pygame.Surface constructor
V rect_type();                                   // pygame.Rect constructor
void install_pygame();                           // route py::stdlib_module("pygame") here (+ install_stdlib)
void install_stdlib();                           // os / time / io / base64 / zlib / json ... (src/ui/stdlib.cpp)
V draw_module();
V transform_module();
V font_module();
V image_module();
V display_module();
V event_module();
V key_module();
V mouse_module();
V time_module();
V mixer_module();
V scrap_module();
void add_constants(V& module);                   // K_*, KMOD_*, event types, flags

// blit helper shared by Surface.blit and the native draw replay
IRect blit(Surface* dst, Surface* src, int x, int y, const IRect* area, int special_flags);

// display state for the app loop
SDL_Window* window();
void present();                                  // display.flip()

}  // namespace pvz::pg
