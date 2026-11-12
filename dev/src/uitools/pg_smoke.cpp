// Smoke test of the pygame facade: draws primitives, CJK text and atlas images through the same
// V-level calls the translated UI code makes, saves a screenshot, and exits.
//   pg_smoke [out.png] [seconds]
#include "pg/pg.h"
#include "sim/pvp/pvprt.h"
#include <cstdio>

using namespace pvz;

static V attr(const V& o, const char* path) {
    V cur = o;
    std::string p(path);
    size_t a = 0;
    while (a <= p.size()) {
        size_t b = p.find('.', a);
        if (b == std::string::npos) b = p.size();
        cur = pvz::getattr(cur, Sym(p.substr(a, b - a)));
        a = b + 1;
    }
    return cur;
}
static V tup(std::initializer_list<double> xs) { std::vector<V> v; for (double x : xs) v.emplace_back(x); return V::tuple(v); }

int main(int argc, char** argv) {
    SDL_SetMainReady();
    std::string out = argc > 1 ? argv[1] : "pg_smoke.png";
    double seconds = argc > 2 ? atof(argv[2]) : 1.0;
    try {
        pg::install_pygame();
        V pygame = py::stdlib_module(V("pygame"));
        attr(pygame, "init").call(Args{});
        V screen = attr(pygame, "display.set_mode").call(Args{tup({960, 640})});
        attr(pygame, "display.set_caption").call(Args{V("pg_smoke 植物大战僵尸")});
        callm(screen, Sym("fill"), Args{tup({40, 70, 40})});
        V draw = attr(pygame, "draw");
        callm(draw, Sym("rect"), Args{screen, tup({200, 180, 60}), tup({20, 20, 200, 80})});
        callm(draw, Sym("rect"), Args({screen, tup({255, 255, 255}), tup({240, 20, 200, 80}), V(3.0)}, {{Sym("border_radius"), V(12.0)}}));
        callm(draw, Sym("circle"), Args{screen, tup({250, 80, 80}), tup({520, 60}), V(40.0)});
        callm(draw, Sym("circle"), Args{screen, tup({80, 80, 250}), tup({620, 60}), V(40.0), V(6.0)});
        callm(draw, Sym("ellipse"), Args{screen, tup({200, 200, 50}), tup({680, 20, 120, 80})});
        callm(draw, Sym("polygon"), Args{screen, tup({120, 220, 255}), V::list({tup({820, 100}), tup({880, 20}), tup({940, 100})})});
        callm(draw, Sym("line"), Args{screen, tup({255, 255, 0}), tup({20, 120}), tup({940, 140}), V(3.0)});
        V font = attr(pygame, "font.SysFont").call(Args{V("microsoftyahei,simhei,arial"), V(28.0)});
        V text = callm(font, Sym("render"), Args{V("植物大战僵尸 · 横版对战 C++ 版"), V(true), tup({255, 255, 255})});
        callm(screen, Sym("blit"), Args{text, tup({20, 160})});
        V size = callm(font, Sym("size"), Args{V("测试 Test")});
        printf("font size of '测试 Test': %s\n", py_str(size).c_str());
        // atlas images from the baked PvP71 assets
        V img = attr(pygame, "image.load").call(Args{V("extract/assets/_png/57e085b26dcb2c76.png")});
        img = callm(img, Sym("convert_alpha"), Args{});
        printf("image size %s\n", py_str(callm(img, Sym("get_size"), Args{})).c_str());
        V tr = attr(pygame, "transform");
        callm(screen, Sym("blit"), Args{img, tup({20, 220})});
        callm(screen, Sym("blit"), Args{callm(tr, Sym("scale"), Args{img, tup({192, 192})}), tup({140, 220})});
        callm(screen, Sym("blit"), Args{callm(tr, Sym("flip"), Args{img, V(true), V(false)}), tup({360, 220})});
        callm(screen, Sym("blit"), Args{callm(tr, Sym("rotate"), Args{img, V(30.0)}), tup({480, 220})});
        callm(screen, Sym("blit"), Args{callm(tr, Sym("smoothscale"), Args{img, tup({60, 60})}), tup({640, 220})});
        V half = callm(img, Sym("copy"), Args{});
        callm(half, Sym("set_alpha"), Args{V(110.0)});
        callm(screen, Sym("blit"), Args{half, tup({720, 220})});
        V sub = callm(img, Sym("subsurface"), Args{tup({0, 0, 48, 48})});
        callm(screen, Sym("blit"), Args{sub, tup({840, 220})});
        V alpha_layer = attr(pygame, "Surface").call(Args{tup({300, 120}), attr(pygame, "SRCALPHA")});
        callm(alpha_layer, Sym("fill"), Args{tup({0, 0, 0, 128})});
        callm(screen, Sym("blit"), Args{alpha_layer, tup({600, 460})});
        V r = attr(pygame, "Rect").call(Args{V(10.0), V(20.0), V(30.0), V(40.0)});
        printf("rect center %s right %s collide %s\n", py_str(pvz::getattr(r, Sym("center"))).c_str(),
               py_str(pvz::getattr(r, Sym("right"))).c_str(), py_str(callm(r, Sym("collidepoint"), Args{tup({15, 25})})).c_str());
        attr(pygame, "display.flip").call(Args{});
        attr(pygame, "image.save").call(Args{screen, V(out)});
        V clock = attr(pygame, "time.Clock").call(Args{});
        Uint32 end = SDL_GetTicks() + Uint32(seconds * 1000);
        int frames = 0;
        while (SDL_GetTicks() < end) {
            for (auto& e : py::iter_list(attr(pygame, "event.get").call(Args{})).items())
                if (pvz::getattr(e, Sym("type")).num() == attr(pygame, "QUIT").num()) end = 0;
            attr(pygame, "display.flip").call(Args{});
            callm(clock, Sym("tick"), Args{V(60.0)});
            ++frames;
        }
        printf("ok, %d frames, screenshot %s\n", frames, out.c_str());
    } catch (PyError& e) {
        fprintf(stderr, "PyError %s\n", e.what());
        return 2;
    }
    return 0;
}
