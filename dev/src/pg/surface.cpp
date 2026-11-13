// pygame Surface / Rect / Color over SDL2 software surfaces.
#include "pg/pg.h"
#include "core/pyops.h"
#include "pg/render_stats.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <chrono>
#include <cstdlib>
#include <atomic>
#if defined(_M_X64) || defined(__SSE2__)
#include <emmintrin.h>
#elif defined(__aarch64__)
#include <arm_neon.h>
#endif

namespace pvz::pg {
static thread_local RenderStats72 stats72;
static thread_local int reference72_override=-1;
static std::atomic<uint64_t> surface_live_count{0},surface_owned_bytes{0},surface_peak_bytes{0};
SurfaceMemoryStats surface_memory_stats(){return {surface_live_count.load(),surface_owned_bytes.load(),surface_peak_bytes.load()};}
static bool surface_memory_enabled(){static const bool enabled=[]{const auto* value=std::getenv("PVP742_SURFACE_MEMORY");return value&&*value=='1';}();return enabled;}
RenderStats72 render_stats72(){return stats72;}
void reset_render_stats72(){stats72={};}
int set_render_reference72(int value){int old=reference72_override;reference72_override=value;return old;}
static bool count72(){static bool on=[] {auto e=std::getenv("PVZ72_RENDER_STATS");return e && *e=='1';}();return on;}
// One switch replays the pre-optimization software paths under identical 72
// rules, for pixel and end-to-end comparisons. No simulation ticks are skipped.
static bool render72_reference() {
    static const bool enabled=[] {const char* e=std::getenv("PVZ72_REFERENCE");return e && *e=='1';}();
    return reference72_override>=0?bool(reference72_override):enabled;
}

static bool separate_pixels(const Surface* a,const Surface* b) {
    auto ab=reinterpret_cast<uintptr_t>(a->s->pixels), bb=reinterpret_cast<uintptr_t>(b->s->pixels);
    auto ae=ab+size_t(a->s->pitch)*a->h(), be=bb+size_t(b->s->pitch)*b->h();
    return ae<=bb || be<=ab;
}

// pygame's compensated interpolation is exactly
// (source*(alpha+1) + destination*(256-alpha)) >> 8. The sum fits uint16.
// These SIMD paths preserve its integer rounding, rather than substituting
// SDL's different /255 blend. Alpha-zero hidden RGB is handled by the scalar
// path whenever the destination has per-pixel alpha.
static int blend_opaque72(uint32_t* dst,const uint32_t* src,int n) {
    int i=0;
#if defined(_M_X64) || defined(__SSE2__)
    const __m128i zero=_mm_setzero_si128(),one=_mm_set1_epi16(1),full=_mm_set1_epi16(256);
    for(;i+4<=n;i+=4) {
        __m128i s=_mm_loadu_si128(reinterpret_cast<const __m128i*>(src+i));
        __m128i d=_mm_loadu_si128(reinterpret_cast<const __m128i*>(dst+i));
        __m128i sl=_mm_unpacklo_epi8(s,zero),sh=_mm_unpackhi_epi8(s,zero);
        __m128i dl=_mm_unpacklo_epi8(d,zero),dh=_mm_unpackhi_epi8(d,zero);
        __m128i al=_mm_shufflehi_epi16(_mm_shufflelo_epi16(sl,255),255);
        __m128i ah=_mm_shufflehi_epi16(_mm_shufflelo_epi16(sh,255),255);
        sl=_mm_srli_epi16(_mm_add_epi16(_mm_mullo_epi16(sl,_mm_add_epi16(al,one)),_mm_mullo_epi16(dl,_mm_sub_epi16(full,al))),8);
        sh=_mm_srli_epi16(_mm_add_epi16(_mm_mullo_epi16(sh,_mm_add_epi16(ah,one)),_mm_mullo_epi16(dh,_mm_sub_epi16(full,ah))),8);
        _mm_storeu_si128(reinterpret_cast<__m128i*>(dst+i),_mm_or_si128(_mm_packus_epi16(sl,sh),_mm_set1_epi32(int(0xff000000u))));
    }
#elif defined(__aarch64__)
    for(;i+8<=n;i+=8) {
        uint8x8x4_t s=vld4_u8(reinterpret_cast<const uint8_t*>(src+i));
        uint8x8x4_t d=vld4_u8(reinterpret_cast<const uint8_t*>(dst+i));
        uint16x8_t a=vmovl_u8(s.val[3]),sf=vaddq_u16(a,vdupq_n_u16(1)),df=vsubq_u16(vdupq_n_u16(256),a);
        for(int c=0;c<3;++c)d.val[c]=vshrn_n_u16(vaddq_u16(vmulq_u16(vmovl_u8(s.val[c]),sf),vmulq_u16(vmovl_u8(d.val[c]),df)),8);
        d.val[3]=vdup_n_u8(255);vst4_u8(reinterpret_cast<uint8_t*>(dst+i),d);
    }
#endif
    return i;
}
// Only a scoped production materializer request contributes to this frontend's
// counters. Normal UI/client replay operations remain outside that scope.
static thread_local V transform_metrics;
V exchange_transform_metrics(const V& value){V previous=transform_metrics;transform_metrics=value;return previous;}

uint32_t display_flags();

// ------------------------------------------------------------------ Rect
struct Rect : PyObj {
    int x = 0, y = 0, w = 0, h = 0;
    const char* type_name() const override { return "Rect"; }
    bool isa(const char* c) const override { return std::string(c) == "Rect" || std::string(c) == "object"; }
    V getitem(const V& k) override {
        int64_t i = int64_t(k.num());
        if (i < 0) i += 4;
        if (i < 0 || i > 3) throw PyError("IndexError", "Invalid rect Index");
        return V(double(i == 0 ? x : i == 1 ? y : i == 2 ? w : h));
    }
    void setitem(const V& k, const V& v) override {
        int64_t i = int64_t(k.num());
        if (i < 0) i += 4;
        int n = int(v.num());
        if (i == 0) x = n; else if (i == 1) y = n; else if (i == 2) w = n; else if (i == 3) h = n;
        else throw PyError("IndexError", "Invalid rect Index");
    }
    size_t length() override { return 4; }
    V iterate() override { return V::nums({double(x), double(y), double(w), double(h)}); }
    static V pair(int a, int b) { return V::tuple({V(double(a)), V(double(b))}); }
    V property(Sym n, bool& found) override {
        found = true;
        const std::string& s = n.str();
        if (s == "x" || s == "left") return V(double(x));
        if (s == "y" || s == "top") return V(double(y));
        if (s == "w" || s == "width") return V(double(w));
        if (s == "h" || s == "height") return V(double(h));
        if (s == "right") return V(double(x + w));
        if (s == "bottom") return V(double(y + h));
        if (s == "centerx") return V(double(x + w / 2));
        if (s == "centery") return V(double(y + h / 2));
        if (s == "center") return pair(x + w / 2, y + h / 2);
        if (s == "topleft") return pair(x, y);
        if (s == "topright") return pair(x + w, y);
        if (s == "bottomleft") return pair(x, y + h);
        if (s == "bottomright") return pair(x + w, y + h);
        if (s == "midtop") return pair(x + w / 2, y);
        if (s == "midbottom") return pair(x + w / 2, y + h);
        if (s == "midleft") return pair(x, y + h / 2);
        if (s == "midright") return pair(x + w, y + h / 2);
        if (s == "size") return pair(w, h);
        found = false;
        return V();
    }
    bool set_property(Sym n, const V& v) override {
        const std::string& s = n.str();
        auto i = [&](const V& q) { return int(std::floor(q.num())); };
        if (s == "x" || s == "left") { x = i(v); return true; }
        if (s == "y" || s == "top") { y = i(v); return true; }
        if (s == "w" || s == "width") { w = i(v); return true; }
        if (s == "h" || s == "height") { h = i(v); return true; }
        if (s == "right") { x = i(v) - w; return true; }
        if (s == "bottom") { y = i(v) - h; return true; }
        if (s == "centerx") { x = i(v) - w / 2; return true; }
        if (s == "centery") { y = i(v) - h / 2; return true; }
        if (s == "center") { x = i(v.idx(0)) - w / 2; y = i(v.idx(1)) - h / 2; return true; }
        if (s == "topleft") { x = i(v.idx(0)); y = i(v.idx(1)); return true; }
        if (s == "topright") { x = i(v.idx(0)) - w; y = i(v.idx(1)); return true; }
        if (s == "bottomleft") { x = i(v.idx(0)); y = i(v.idx(1)) - h; return true; }
        if (s == "bottomright") { x = i(v.idx(0)) - w; y = i(v.idx(1)) - h; return true; }
        if (s == "midtop") { x = i(v.idx(0)) - w / 2; y = i(v.idx(1)); return true; }
        if (s == "midbottom") { x = i(v.idx(0)) - w / 2; y = i(v.idx(1)) - h; return true; }
        if (s == "midleft") { x = i(v.idx(0)); y = i(v.idx(1)) - h / 2; return true; }
        if (s == "midright") { x = i(v.idx(0)) - w; y = i(v.idx(1)) - h / 2; return true; }
        if (s == "size") { w = i(v.idx(0)); h = i(v.idx(1)); return true; }
        return false;
    }
    IRect r() const { return {x, y, w, h}; }
    V method(Sym name) override {
        auto sp = std::static_pointer_cast<Rect>(shared_from_this());
        return V::func([sp, name](const Args& a) { V out; if (!sp->call_method(name, a, out)) throw PyError("AttributeError", "Rect." + name.str()); return out; });
    }
    bool call_method(Sym name, const Args& a, V& out) override;
};

V make_rect(int x, int y, int w, int h) {
    auto r = std::make_shared<Rect>();
    r->x = x; r->y = y; r->w = w; r->h = h;
    return V::inst(r);
}

static int iv(const V& v) { return int(std::floor(v.num())); }

bool rect_from(const V& v, IRect& out) {
    if (auto* r = as<Rect>(v)) { out = r->r(); return true; }
    if (v.t == V::INST) {   // objects with a .rect attribute (pygame accepts them)
        V rr = pvz::getattr(v, Sym("rect"), V());
        if (rr.has()) return rect_from(rr, out);
        return false;
    }
    if (!(v.is_list())) return false;
    size_t n = v.len();
    if (n == 4) { out = {iv(v.idx(0)), iv(v.idx(1)), iv(v.idx(2)), iv(v.idx(3))}; return true; }
    if (n == 2 && v.idx(0).is_list() && v.idx(1).is_list()) {
        out = {iv(v.idx(0).idx(0)), iv(v.idx(0).idx(1)), iv(v.idx(1).idx(0)), iv(v.idx(1).idx(1))};
        return true;
    }
    return false;
}
IRect rect_of(const V& v) {
    IRect r;
    if (!rect_from(v, r)) throw PyError("TypeError", "Argument must be rect style object");
    return r;
}
static V rect_v(const IRect& r) { return make_rect(r.x, r.y, r.w, r.h); }
static IRect clip_rect(const IRect& a, const IRect& b) {
    int x0 = std::max(a.x, b.x), y0 = std::max(a.y, b.y);
    int x1 = std::min(a.x + a.w, b.x + b.w), y1 = std::min(a.y + a.h, b.y + b.h);
    if (x1 <= x0 || y1 <= y0) return {a.x, a.y, 0, 0};
    return {x0, y0, x1 - x0, y1 - y0};
}
static IRect union_rect(const IRect& a, const IRect& b) {
    int x0 = std::min(a.x, b.x), y0 = std::min(a.y, b.y);
    int x1 = std::max(a.x + a.w, b.x + b.w), y1 = std::max(a.y + a.h, b.y + b.h);
    return {x0, y0, x1 - x0, y1 - y0};
}
static bool collide(const IRect& a, const IRect& b) {
    return a.w > 0 && a.h > 0 && b.w > 0 && b.h > 0 &&
           a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}
static void point_of(const Args& a, int& px, int& py) {
    if (a.pos.size() >= 2) { px = iv(a.pos[0]); py = iv(a.pos[1]); return; }
    px = iv(a.pos.at(0).idx(0)); py = iv(a.pos.at(0).idx(1));
}
static IRect rect_args(const Args& a) {
    if (a.pos.size() >= 4) return {iv(a.pos[0]), iv(a.pos[1]), iv(a.pos[2]), iv(a.pos[3])};
    if (a.pos.size() == 2) return {iv(a.pos[0].idx(0)), iv(a.pos[0].idx(1)), iv(a.pos[1].idx(0)), iv(a.pos[1].idx(1))};
    return rect_of(a.pos.at(0));
}

bool Rect::call_method(Sym name, const Args& a, V& out) {
    const std::string& n = name.str();
    if (n == "__str__" || n == "__repr__") {
        out = V("Rect(" + std::to_string(x) + ", " + std::to_string(y) + ", " + std::to_string(w) + ", " + std::to_string(h) + ")");
        return true;
    }
    if (n == "__eq__" || n == "__ne__") {
        IRect other;
        bool equal = !a.pos.empty() && rect_from(a.pos[0], other) && x == other.x && y == other.y && w == other.w && h == other.h;
        out = V(n == "__eq__" ? equal : !equal);
        return true;
    }
    if (n == "copy") { out = rect_v(r()); return true; }
    if (n == "move") { int dx, dy; point_of(a, dx, dy); out = make_rect(x + dx, y + dy, w, h); return true; }
    if (n == "move_ip") { int dx, dy; point_of(a, dx, dy); x += dx; y += dy; out = V::none(); return true; }
    if (n == "inflate" || n == "inflate_ip") {
        int dx, dy; point_of(a, dx, dy);
        IRect q{x - dx / 2, y - dy / 2, w + dx, h + dy};
        if (n == "inflate") out = rect_v(q); else { x = q.x; y = q.y; w = q.w; h = q.h; out = V::none(); }
        return true;
    }
    if (n == "scale_by" || n == "scale_by_ip") {
        double fx = a.pos.at(0).is_list() ? a.pos[0].idx(0).num() : a.pos[0].num();
        double fy = a.pos[0].is_list() ? a.pos[0].idx(1).num() : (a.pos.size() > 1 ? a.pos[1].num() : fx);
        int nw = int(w * fx), nh = int(h * fy);
        IRect q{x + (w - nw) / 2, y + (h - nh) / 2, nw, nh};
        if (n == "scale_by") out = rect_v(q); else { x = q.x; y = q.y; w = q.w; h = q.h; out = V::none(); }
        return true;
    }
    if (n == "clamp" || n == "clamp_ip") {
        IRect b = rect_args(a), q = r();
        if (q.w >= b.w) q.x = b.x + b.w / 2 - q.w / 2;
        else if (q.x < b.x) q.x = b.x;
        else if (q.x + q.w > b.x + b.w) q.x = b.x + b.w - q.w;
        if (q.h >= b.h) q.y = b.y + b.h / 2 - q.h / 2;
        else if (q.y < b.y) q.y = b.y;
        else if (q.y + q.h > b.y + b.h) q.y = b.y + b.h - q.h;
        if (n == "clamp") out = rect_v(q); else { x = q.x; y = q.y; out = V::none(); }
        return true;
    }
    if (n == "clip") { out = rect_v(clip_rect(r(), rect_args(a))); return true; }
    if (n == "union") { out = rect_v(union_rect(r(), rect_args(a))); return true; }
    if (n == "union_ip") { IRect q = union_rect(r(), rect_args(a)); x = q.x; y = q.y; w = q.w; h = q.h; out = V::none(); return true; }
    if (n == "unionall" || n == "unionall_ip") {
        IRect q = r();
        for (auto& o : py::iter_list(a.pos.at(0)).items()) q = union_rect(q, rect_of(o));
        if (n == "unionall") out = rect_v(q); else { x = q.x; y = q.y; w = q.w; h = q.h; out = V::none(); }
        return true;
    }
    if (n == "fit") {
        IRect b = rect_args(a);
        double ratio = std::max(double(w) / std::max(1, b.w), double(h) / std::max(1, b.h));
        int nw = int(w / ratio), nh = int(h / ratio);
        out = make_rect(b.x + (b.w - nw) / 2, b.y + (b.h - nh) / 2, nw, nh);
        return true;
    }
    if (n == "normalize") { if (w < 0) { x += w; w = -w; } if (h < 0) { y += h; h = -h; } out = V::none(); return true; }
    if (n == "contains") {
        IRect b = rect_args(a);
        out = V(x <= b.x && y <= b.y && x + w >= b.x + b.w && y + h >= b.y + b.h && x + w > b.x && y + h > b.y);
        return true;
    }
    if (n == "collidepoint") { int px, py; point_of(a, px, py); out = V(px >= x && px < x + w && py >= y && py < y + h); return true; }
    if (n == "colliderect") { out = V(collide(r(), rect_args(a))); return true; }
    if (n == "collidelist") {
        double i = 0;
        for (auto& o : py::iter_list(a.pos.at(0)).items()) { if (collide(r(), rect_of(o))) { out = V(i); return true; } ++i; }
        out = V(-1.0);
        return true;
    }
    if (n == "collidelistall") {
        std::vector<V> hits; double i = 0;
        for (auto& o : py::iter_list(a.pos.at(0)).items()) { if (collide(r(), rect_of(o))) hits.emplace_back(i); ++i; }
        out = V::list(hits);
        return true;
    }
    if (n == "update") { IRect q = rect_args(a); x = q.x; y = q.y; w = q.w; h = q.h; out = V::none(); return true; }
    return false;
}

V rect_ctor(const Args& a) {
    if (a.pos.empty()) return make_rect(0, 0, 0, 0);
    return rect_v(rect_args(a));
}

// ------------------------------------------------------------------ Color
static const struct { const char* n; uint8_t r, g, b; } kNamed[] = {
    {"white", 255, 255, 255}, {"black", 0, 0, 0}, {"red", 255, 0, 0}, {"green", 0, 255, 0}, {"blue", 0, 0, 255},
    {"yellow", 255, 255, 0}, {"gray", 190, 190, 190}, {"grey", 190, 190, 190}, {"orange", 255, 165, 0}};

bool color_from(const V& v, SDL_Color& out) {
    if (v.is_list()) {
        size_t n = v.len();
        if (n < 3) return false;
        auto c = [](const V& q) { int x = int(q.num()); return uint8_t(x < 0 ? 0 : x > 255 ? 255 : x); };
        out = {c(v.idx(0)), c(v.idx(1)), c(v.idx(2)), n > 3 ? c(v.idx(3)) : uint8_t(255)};
        return true;
    }
    if (v.t == V::STR) {
        std::string s = v.str();
        if (!s.empty() && s[0] == '#' && s.size() >= 7) {
            auto h = [&](size_t i) { return uint8_t(std::stoi(s.substr(i, 2), nullptr, 16)); };
            out = {h(1), h(3), h(5), s.size() >= 9 ? h(7) : uint8_t(255)};
            return true;
        }
        for (auto& c : kNamed) if (s == c.n) { out = {c.r, c.g, c.b, 255}; return true; }
        return false;
    }
    if (v.t == V::NUM) {   // mapped integer colour (0xAARRGGBB as pygame map_rgb on ARGB surfaces)
        uint32_t x = uint32_t(int64_t(v.num()));
        out = {uint8_t(x >> 16), uint8_t(x >> 8), uint8_t(x), uint8_t(x >> 24)};
        return true;
    }
    if (v.t == V::INST && v.box->inst->length() >= 3) return color_from(v.box->inst->iterate(), out);
    return false;
}
SDL_Color color_of(const V& v) {
    SDL_Color c;
    if (!color_from(v, c)) throw PyError("ValueError", "invalid color argument");
    return c;
}

// ------------------------------------------------------------------ Surface
Surface::~Surface() { if(diagnostic_counted){surface_live_count.fetch_sub(1);surface_owned_bytes.fetch_sub(diagnostic_storage_bytes);}if (s) SDL_FreeSurface(s); }

static SDL_Surface* raw_surface(int w, int h) {
    SDL_Surface* s = SDL_CreateRGBSurfaceWithFormat(0, std::max(w, 0), std::max(h, 0), 32, SDL_PIXELFORMAT_ARGB8888);
    if (!s) throw PyError("error", std::string("cannot create surface: ") + SDL_GetError());
    return s;
}
V wrap_surface(SDL_Surface* s, bool srcalpha) {
    auto p = std::make_shared<Surface>();
    p->s = s;
    p->srcalpha = srcalpha;
    if(surface_memory_enabled()){
        p->diagnostic_counted=true;surface_live_count.fetch_add(1);
        p->diagnostic_storage_bytes=s&&!(s->flags&SDL_PREALLOC)?uint64_t(s->pitch)*uint64_t(s->h):0;
        const auto live=surface_owned_bytes.fetch_add(p->diagnostic_storage_bytes)+p->diagnostic_storage_bytes;
        auto peak=surface_peak_bytes.load();while(peak<live&&!surface_peak_bytes.compare_exchange_weak(peak,live)){}
    }
    return V::inst(p);
}
V new_surface(int w, int h, bool srcalpha) {
    if(count72()){++stats72.surface_allocations;stats72.allocated_bytes+=uint64_t(std::max(0,w))*std::max(0,h)*4;}
    SDL_Surface* s = raw_surface(w, h);
    SDL_FillRect(s, nullptr, srcalpha ? 0x00000000u : 0xFF000000u);
    return wrap_surface(s, srcalpha);
}
Surface* surf(const V& v) {
    auto* s = as<Surface>(v);
    if (!s) throw PyError("TypeError", "argument must be a pygame.Surface, not " + v.type_name());
    return s;
}
// Native atlases may retain immutable recipes until a physical SDL operation
// requires their pixels. The caller holds this V through the whole operation.
static V source_surface_value(const V& source) {
    if (as<Surface>(source)) return source;
    if (source.t==V::INST && source.box->inst->isa("NativeImage")) {
        V pixels=pvz::getattr(source,Sym("pixels"));
        if (!as<Surface>(pixels)) throw PyError("TypeError","native image did not materialize a pygame.Surface");
        return pixels;
    }
    return source;
}
static inline uint32_t* row(SDL_Surface* s, int y) { return reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(s->pixels) + size_t(y) * s->pitch); }
static inline uint32_t argb(SDL_Color c) { return (uint32_t(c.a) << 24) | (uint32_t(c.r) << 16) | (uint32_t(c.g) << 8) | c.b; }

static V copy_surface(Surface* src) {
    SDL_Surface* s = raw_surface(src->w(), src->h());
    for (int y = 0; y < src->h(); ++y) std::memcpy(row(s, y), row(src->s, y), size_t(src->w()) * 4);
    V out = wrap_surface(s, src->srcalpha);
    auto* d = surf(out);
    d->alpha = src->alpha; d->has_colorkey = src->has_colorkey; d->colorkey = src->colorkey;
    return out;
}

// pygame blending on ARGB8888 (straight alpha)
static inline uint8_t clamp8(int v) { return uint8_t(v < 0 ? 0 : v > 255 ? 255 : v); }
static void blend_special(uint32_t& d, uint32_t sp, int flags) {
    int sr = (sp >> 16) & 255, sg = (sp >> 8) & 255, sb = sp & 255, sa = sp >> 24;
    int dr = (d >> 16) & 255, dg = (d >> 8) & 255, db = d & 255, da = d >> 24;
    switch (flags) {
        case 1: dr = clamp8(dr + sr); dg = clamp8(dg + sg); db = clamp8(db + sb); break;                       // BLEND_RGB_ADD
        case 2: dr = clamp8(dr - sr); dg = clamp8(dg - sg); db = clamp8(db - sb); break;                       // BLEND_RGB_SUB
        case 3: dr = (dr * sr + 255) >> 8; dg = (dg * sg + 255) >> 8; db = (db * sb + 255) >> 8; break;        // BLEND_RGB_MULT
        case 4: dr = std::min(dr, sr); dg = std::min(dg, sg); db = std::min(db, sb); break;                    // BLEND_RGB_MIN
        case 5: dr = std::max(dr, sr); dg = std::max(dg, sg); db = std::max(db, sb); break;                    // BLEND_RGB_MAX
        case 6: dr = clamp8(dr + sr); dg = clamp8(dg + sg); db = clamp8(db + sb); da = clamp8(da + sa); break;  // BLEND_RGBA_ADD
        case 7: dr = clamp8(dr - sr); dg = clamp8(dg - sg); db = clamp8(db - sb); da = clamp8(da - sa); break;  // BLEND_RGBA_SUB
        case 8: dr = (dr * sr + 255) >> 8; dg = (dg * sg + 255) >> 8; db = (db * sb + 255) >> 8; da = (da * sa + 255) >> 8; break;
        case 9: dr = std::min(dr, sr); dg = std::min(dg, sg); db = std::min(db, sb); da = std::min(da, sa); break;
        case 16: dr = std::max(dr, sr); dg = std::max(dg, sg); db = std::max(db, sb); da = std::max(da, sa); break;
        case 17: {   // BLEND_PREMULTIPLIED
            dr = sr + dr - ((dr * sa + 255) >> 8); dg = sg + dg - ((dg * sa + 255) >> 8);
            db = sb + db - ((db * sa + 255) >> 8); da = sa + da - ((da * sa + 255) >> 8);
            break;
        }
        default: break;
    }
    d = (uint32_t(da) << 24) | (uint32_t(dr) << 16) | (uint32_t(dg) << 8) | uint32_t(db);
}

IRect blit(Surface* dst, Surface* src, int x, int y, const IRect* area, int flags) {
    IRect sa = area ? *area : IRect{0, 0, src->w(), src->h()};
    // clip the source area to the source surface
    if (sa.x < 0) { x -= sa.x; sa.w += sa.x; sa.x = 0; }
    if (sa.y < 0) { y -= sa.y; sa.h += sa.y; sa.y = 0; }
    sa.w = std::min(sa.w, src->w() - sa.x);
    sa.h = std::min(sa.h, src->h() - sa.y);
    SDL_Rect clip;
    SDL_GetClipRect(dst->s, &clip);
    int x0 = std::max(x, clip.x), y0 = std::max(y, clip.y);
    int x1 = std::min(x + sa.w, clip.x + clip.w), y1 = std::min(y + sa.h, clip.y + clip.h);
    if (x1 <= x0 || y1 <= y0) return {x, y, 0, 0};
    int sx0 = sa.x + (x0 - x), sy0 = sa.y + (y0 - y);
    if(count72()){++stats72.blits;stats72.blit_pixels+=uint64_t(x1-x0)*(y1-y0);}
    int amod = src->alpha < 0 ? 255 : std::clamp(src->alpha, 0, 255);
    bool dst_alpha = dst->srcalpha;
    bool vector_blend=!render72_reference() && !dst_alpha && src->srcalpha && amod==255 &&
        src->alpha!=-2 && !flags && !src->has_colorkey && separate_pixels(dst,src);
    bool opaque_copy=!render72_reference() && !flags && !src->has_colorkey &&
        (src->alpha==-2 || (!src->srcalpha && amod==255)) && separate_pixels(dst,src);
    for (int yy = y0; yy < y1; ++yy) {
        uint32_t* dp = row(dst->s, yy) + x0;
        const uint32_t* sp = row(src->s, sy0 + (yy - y0)) + sx0;
        if(opaque_copy) {
            if(src->alpha==-2 && dst_alpha)std::memcpy(dp,sp,size_t(x1-x0)*4);
            else for(int i=0;i<x1-x0;++i)dp[i]=sp[i]|0xff000000u;
            continue;
        }
        int done=vector_blend?blend_opaque72(dp,sp,x1-x0):0;
        dp+=done;sp+=done;
        for (int xx = x0+done; xx < x1; ++xx, ++dp, ++sp) {
            uint32_t p = *sp;
            if (src->has_colorkey && (p & 0x00FFFFFFu) == (src->colorkey & 0x00FFFFFFu)) continue;
            if (flags) { blend_special(*dp, p, flags); continue; }
            // -1 is the default (no blanket modulation); -2 is explicit set_alpha(None),
            // which disables blending while preserving the underlying pixel alpha channel.
            if (src->alpha == -2) { *dp = dst_alpha ? p : p | 0xFF000000u; continue; }
            // Surfaces without a pixel-alpha mask take SDL's surface-alpha path:
            // interpolate in 8 bits and write an opaque destination alpha.
            if (!src->srcalpha && amod != 255) {
                uint32_t d = *dp;
                auto component = [amod](int source, int destination) { return destination + (((source - destination) * amod) >> 8); };
                *dp = 0xFF000000u | (uint32_t(component((p >> 16) & 255, (d >> 16) & 255)) << 16) |
                    (uint32_t(component((p >> 8) & 255, (d >> 8) & 255)) << 8) | uint32_t(component(p & 255, d & 255));
                continue;
            }
            int a = src->srcalpha ? int(p >> 24) : 255;
            if (amod != 255) a = (a * amod) / 255;
            if (a == 255) { *dp = dst_alpha ? p | (src->srcalpha ? 0 : 0xFF000000u) : (p | 0xFF000000u); continue; }
            uint32_t d = *dp;
            int dr = (d >> 16) & 255, dg = (d >> 8) & 255, db = d & 255, da = d >> 24;
            int sr = (p >> 16) & 255, sg = (p >> 8) & 255, sb = p & 255;
            // pygame-ce 2.4.0 legacy alpha semantics, also independently checked against the
            // actual reference runtime. A transparent destination retains straight RGB,
            // including the hidden RGB of an alpha-zero source. Nonempty destinations use
            // pygame's compensated 8-bit component interpolation, not rounded /255.
            // https://github.com/pygame-community/pygame-ce/blob/2.4.0/src_c/surface.h
            auto blend = [a](int source, int destination) { return (((source - destination) * a + source) >> 8) + destination; };
            if (dst_alpha) {
                if (!da) { dr = sr; dg = sg; db = sb; da = a; }
                else { dr = blend(sr, dr); dg = blend(sg, dg); db = blend(sb, db); da = a + da - a * da / 255; }
            } else {
                dr = blend(sr, dr); dg = blend(sg, dg); db = blend(sb, db);
                da = 255;
            }
            *dp = (uint32_t(da) << 24) | (uint32_t(dr) << 16) | (uint32_t(dg) << 8) | uint32_t(db);
        }
    }
    return {x0, y0, x1 - x0, y1 - y0};
}

static IRect fill(Surface* d, SDL_Color c, const IRect* r, int flags) {
    SDL_Rect clip;
    SDL_GetClipRect(d->s, &clip);
    IRect q = r ? *r : IRect{0, 0, d->w(), d->h()};
    IRect cl = clip_rect(q, {clip.x, clip.y, clip.w, clip.h});
    if (cl.w <= 0 || cl.h <= 0) return {q.x, q.y, 0, 0};
    uint32_t px = argb(c);
    if (!d->srcalpha) px |= 0xFF000000u;
    for (int y = cl.y; y < cl.y + cl.h; ++y) {
        uint32_t* p = row(d->s, y) + cl.x;
        for (int x = 0; x < cl.w; ++x) {
            if (flags) blend_special(p[x], px, flags); else p[x] = px;
        }
    }
    return cl;
}

static V subsurface(const V& self, Surface* src, const IRect& r) {
    if (r.x < 0 || r.y < 0 || r.x + r.w > src->w() || r.y + r.h > src->h() || r.w < 0 || r.h < 0)
        throw PyError("ValueError", "subsurface rectangle outside surface area");
    uint8_t* base = static_cast<uint8_t*>(src->s->pixels) + size_t(r.y) * src->s->pitch + size_t(r.x) * 4;
    SDL_Surface* s = SDL_CreateRGBSurfaceWithFormatFrom(base, r.w, r.h, 32, src->s->pitch, SDL_PIXELFORMAT_ARGB8888);
    V out = wrap_surface(s, src->srcalpha);
    auto* d = surf(out);
    d->parent = self;
    d->off_x = src->off_x + r.x; d->off_y = src->off_y + r.y;
    d->alpha = src->alpha; d->has_colorkey = src->has_colorkey; d->colorkey = src->colorkey;
    return out;
}

V Surface::method(Sym name) {
    auto sp = std::static_pointer_cast<Surface>(shared_from_this());
    static const char* known[] = {"blit", "blits", "fill", "get_size", "get_width", "get_height", "get_rect", "copy", "convert",
        "convert_alpha", "set_alpha", "get_alpha", "set_colorkey", "get_colorkey", "subsurface", "get_at", "set_at", "set_clip",
        "get_clip", "get_flags", "lock", "unlock", "get_bounding_rect", "get_parent", "get_abs_offset", "get_offset", "scroll",
        "get_bitsize", "get_bytesize", "map_rgb", "unmap_rgb", "premul_alpha", "get_locked", "mustlock", "get_pitch", "get_masks"};
    for (auto* k : known) if (name.str() == k)
        return V::func([sp, name](const Args& a) { V out; sp->call_method(name, a, out); return out; });
    return V();
}

bool Surface::call_method(Sym name, const Args& a, V& out) {
    const std::string& n = name.str();
    if (n == "blit") {
        V source=source_surface_value(a.get(0, Sym("source"), nullptr, "blit"));
        Surface* src = surf(source);
        V dest = a.get(1, Sym("dest"), nullptr, "blit");
        int x, y;
        IRect dr;
        if (rect_from(dest, dr) && dest.t == V::INST) { x = dr.x; y = dr.y; }
        else if (dest.is_list() && dest.len() == 4) { x = iv(dest.idx(0)); y = iv(dest.idx(1)); }
        else { x = iv(dest.idx(0)); y = iv(dest.idx(1)); }
        static const V none_v = V::none(), zero_v(0.0);
        V area = a.get(2, Sym("area"), &none_v);
        int flags = int(a.get(3, Sym("special_flags"), &zero_v).num());
        IRect ar;
        IRect res = blit(this, src, x, y, area.is_none() ? nullptr : (ar = rect_of(area), &ar), flags);
        out = rect_v(res);
        return true;
    }
    if (n == "blits") {
        std::vector<V> res;
        for (auto& item : py::iter_list(a.pos.at(0)).items()) {
            Args sub;
            for (auto& x : py::iter_list(item).items()) sub.pos.push_back(x);
            V r; call_method(Sym("blit"), sub, r); res.push_back(r);
        }
        out = (a.pos.size() > 1 && !a.pos[1].truthy()) ? V::none() : V::list(res);
        return true;
    }
    if (n == "fill") {
        SDL_Color c = color_of(a.pos.at(0));
        static const V none_v = V::none(), zero_v(0.0);
        V r = a.get(1, Sym("rect"), &none_v);
        int flags = int(a.get(2, Sym("special_flags"), &zero_v).num());
        IRect q;
        out = rect_v(fill(this, c, r.is_none() ? nullptr : (q = rect_of(r), &q), flags));
        return true;
    }
    if (n == "get_size") { out = V::tuple({V(double(w())), V(double(h()))}); return true; }
    if (n == "get_width") { out = V(double(w())); return true; }
    if (n == "get_height") { out = V(double(h())); return true; }
    if (n == "get_rect" || n == "get_frect") {
        V r = make_rect(0, 0, w(), h());
        for (auto& p : a.kw) pvz::setattr(r, p.first, p.second);
        out = r;
        return true;
    }
    if (n == "copy" || n == "convert" || n == "convert_alpha") {
        out = copy_surface(this);
        if (n == "copy" && ((srcalpha && alpha == -2) || (!srcalpha && alpha == 255))) surf(out)->alpha = -1;
        if (n == "convert_alpha") { surf(out)->srcalpha = true; if (surf(out)->alpha == -2) surf(out)->alpha = -1; }
        if (n == "convert") {
            Surface* d = surf(out);
            // SDL conversion to the display format removes blending. Its unused high
            // byte retains blanket alpha and is copied if later blitted to RGBA.
            uint32_t a = uint32_t(alpha < 0 ? 255 : alpha) << 24;
            for (int y = 0; y < d->h(); ++y) { uint32_t* p = row(d->s, y); for (int x = 0; x < d->w(); ++x) p[x] = (p[x] & 0xFFFFFFu) | a; }
            d->srcalpha = false; d->alpha = -2;
        }
        return true;
    }
    if (n == "set_alpha") { alpha = a.pos.empty() || a.pos[0].is_none() ? -2 : std::clamp(int(a.pos[0].num()), 0, 255); out = V::none(); return true; }
    if (n == "get_alpha") { out = alpha == -2 ? V::none() : alpha < 0 ? (srcalpha ? V(255.0) : V::none()) : V(double(alpha)); return true; }
    if (n == "set_colorkey") {
        if (a.pos.empty() || a.pos[0].is_none()) has_colorkey = false;
        else { has_colorkey = true; colorkey = argb(color_of(a.pos[0])) | 0xFF000000u; }
        out = V::none();
        return true;
    }
    if (n == "get_colorkey") {
        out = has_colorkey ? V::tuple({V(double((colorkey >> 16) & 255)), V(double((colorkey >> 8) & 255)), V(double(colorkey & 255)), V(255.0)}) : V::none();
        return true;
    }
    if (n == "subsurface") { out = subsurface(self(), this, a.pos.size() >= 4 ? rect_args(a) : rect_args(a)); return true; }
    if (n == "get_at") {
        V p = a.pos.at(0);
        int x = iv(p.idx(0)), y = iv(p.idx(1));
        if (x < 0 || y < 0 || x >= w() || y >= h()) throw PyError("IndexError", "pixel index out of range");
        uint32_t c = row(s, y)[x];
        out = V::tuple({V(double((c >> 16) & 255)), V(double((c >> 8) & 255)), V(double(c & 255)), V(double(srcalpha ? (c >> 24) : 255))});
        out.box->color = true;   // pygame Surface.get_at returns a Color
        return true;
    }
    if (n == "set_at") {
        V p = a.pos.at(0);
        int x = iv(p.idx(0)), y = iv(p.idx(1));
        SDL_Rect clip; SDL_GetClipRect(s, &clip);
        if (x >= clip.x && y >= clip.y && x < clip.x + clip.w && y < clip.y + clip.h) {
            uint32_t c = argb(color_of(a.pos.at(1)));
            row(s, y)[x] = srcalpha ? c : (c | 0xFF000000u);
        }
        out = V::none();
        return true;
    }
    if (n == "set_clip") {
        if (a.pos.empty() || a.pos[0].is_none()) SDL_SetClipRect(s, nullptr);
        else { IRect r = rect_args(a); SDL_Rect q{r.x, r.y, r.w, r.h}; SDL_SetClipRect(s, &q); }
        out = V::none();
        return true;
    }
    if (n == "get_clip") { SDL_Rect q; SDL_GetClipRect(s, &q); out = make_rect(q.x, q.y, q.w, q.h); return true; }
    if (n == "get_flags") { out = V(double((is_display?display_flags():0u) | uint32_t((alpha != -2 && (srcalpha || alpha >= 0)) ? 0x00010000 : 0))); return true; }
    if (n == "lock" || n == "unlock") { out = V::none(); return true; }
    if (n == "get_locked" || n == "mustlock") { out = V(false); return true; }
    if (n == "get_bitsize") { out = V(32.0); return true; }
    if (n == "get_bytesize") { out = V(4.0); return true; }
    if (n == "get_pitch") { out = V(double(s->pitch)); return true; }
    if (n == "get_parent") { out = parent.has() ? parent : V::none(); return true; }
    if (n == "get_offset") { out = V::tuple({V(double(parent.has() ? off_x : 0)), V(double(parent.has() ? off_y : 0))}); return true; }
    if (n == "get_abs_offset") { out = V::tuple({V(double(off_x)), V(double(off_y))}); return true; }
    if (n == "map_rgb") { out = V(double(argb(color_of(a.pos.at(0))))); return true; }
    if (n == "unmap_rgb") { uint32_t c = uint32_t(int64_t(a.pos.at(0).num())); out = V::tuple({V(double((c >> 16) & 255)), V(double((c >> 8) & 255)), V(double(c & 255)), V(double(c >> 24))}); return true; }
    if (n == "get_bounding_rect") {
        static const V default_alpha(1);int min_alpha=int(a.get(0,Sym("min_alpha"),&default_alpha).num());
        int x0 = w(), y0 = h(), x1 = -1, y1 = -1;
        for (int y = 0; y < h(); ++y) {
            const uint32_t* p = row(s, y);
            for (int x = 0; x < w(); ++x)
                if (int(srcalpha ? p[x] >> 24 : 255) >= min_alpha) { x0 = std::min(x0, x); y0 = std::min(y0, y); x1 = std::max(x1, x); y1 = std::max(y1, y); }
        }
        out = x1 < 0 ? make_rect(0, 0, 0, 0) : make_rect(x0, y0, x1 - x0 + 1, y1 - y0 + 1);
        return true;
    }
    if (n == "scroll") {
        static const V zero_v(0.0);
        int dx = int(a.get(0, Sym("dx"), &zero_v).num()), dy = int(a.get(1, Sym("dy"), &zero_v).num());
        V tmp = copy_surface(this);
        Surface* t = surf(tmp);
        blit(this, t, dx, dy, nullptr, 0);
        out = V::none();
        return true;
    }
    if (n == "premul_alpha") {
        V c = copy_surface(this);
        Surface* d = surf(c);
        for (int y = 0; y < d->h(); ++y) {
            uint32_t* p = row(d->s, y);
            for (int x = 0; x < d->w(); ++x) {
                uint32_t q = p[x]; int al = q >> 24;
                p[x] = (q & 0xFF000000u) | (uint32_t((((q >> 16) & 255) * al + 127) / 255) << 16) |
                       (uint32_t((((q >> 8) & 255) * al + 127) / 255) << 8) | uint32_t(((q & 255) * al + 127) / 255);
            }
        }
        out = c;
        return true;
    }
    if (n == "get_masks") { out = V::tuple({V(double(0x00FF0000)), V(double(0x0000FF00)), V(double(0x000000FF)), V(double(0xFF000000u))}); return true; }
    return false;
}

V surface_ctor(const Args& a) {
    V size = a.get(0, Sym("size"), nullptr, "Surface");
    static const V zero_v(0.0);
    int flags = int(a.get(1, Sym("flags"), &zero_v).num());
    return new_surface(iv(size.idx(0)), iv(size.idx(1)), (flags & 0x00010000) != 0);
}

// ------------------------------------------------------------------ transform
static V scale_nearest(Surface* src, int nw, int nh) {
    if (nw < 0 || nh < 0) throw PyError("ValueError", "Cannot scale to negative size");
    V out = new_surface(nw, nh, src->srcalpha);
    Surface* d = surf(out);
    d->alpha = src->alpha; d->has_colorkey = src->has_colorkey; d->colorkey = src->colorkey;
    if (!src->srcalpha && src->alpha == 255) d->alpha = -1;
    if (!nw || !nh || !src->w() || !src->h()) return out;
    // pygame-ce 2.4.0 delegates scale() to SDL_SoftStretch. Its pixel-center
    // sampling differs from the former edge-anchored fixed-step loop.
    if (SDL_SoftStretch(src->s, nullptr, d->s, nullptr) != 0) throw PyError("error", SDL_GetError());
    return out;
}

static V scale_smooth(Surface* src, int nw, int nh) {
    if (nw < 0 || nh < 0) throw PyError("ValueError", "Cannot scale to negative size");
    V out = new_surface(nw, nh, src->srcalpha);
    Surface* d = surf(out);
    d->alpha = src->alpha;
    int sw = src->w(), sh = src->h();
    if (!nw || !nh || !sw || !sh) return out;
    // area-averaging (shrink) / bilinear (expand), per axis like pygame's smoothscale
    for (int y = 0; y < nh; ++y) {
        double fy0 = double(y) * sh / nh, fy1 = double(y + 1) * sh / nh;
        uint32_t* dp = row(d->s, y);
        for (int x = 0; x < nw; ++x) {
            double fx0 = double(x) * sw / nw, fx1 = double(x + 1) * sw / nw;
            double acc[4] = {0, 0, 0, 0}, wsum = 0;
            if (fx1 - fx0 <= 1.0 && fy1 - fy0 <= 1.0) {
                // bilinear at the pixel centre
                double cx = (fx0 + fx1) / 2 - .5, cy = (fy0 + fy1) / 2 - .5;
                int ix = int(std::floor(cx)), iy = int(std::floor(cy));
                double tx = cx - ix, ty = cy - iy;
                for (int k = 0; k < 4; ++k) {
                    int px = std::clamp(ix + (k & 1), 0, sw - 1), py = std::clamp(iy + (k >> 1), 0, sh - 1);
                    double wgt = ((k & 1) ? tx : 1 - tx) * ((k >> 1) ? ty : 1 - ty);
                    uint32_t c = row(src->s, py)[px];
                    double al = src->srcalpha ? (c >> 24) : 255;
                    acc[0] += ((c >> 16) & 255) * wgt * al; acc[1] += ((c >> 8) & 255) * wgt * al; acc[2] += (c & 255) * wgt * al;
                    acc[3] += al * wgt; wsum += wgt;
                }
            } else {
                for (int py = int(fy0); py < int(std::ceil(fy1)) && py < sh; ++py) {
                    double wy = std::min(fy1, py + 1.0) - std::max(fy0, double(py));
                    const uint32_t* sp = row(src->s, py);
                    for (int px = int(fx0); px < int(std::ceil(fx1)) && px < sw; ++px) {
                        double wgt = wy * (std::min(fx1, px + 1.0) - std::max(fx0, double(px)));
                        uint32_t c = sp[px];
                        double al = src->srcalpha ? (c >> 24) : 255;
                        acc[0] += ((c >> 16) & 255) * wgt * al; acc[1] += ((c >> 8) & 255) * wgt * al; acc[2] += (c & 255) * wgt * al;
                        acc[3] += al * wgt; wsum += wgt;
                    }
                }
            }
            double a = wsum > 0 ? acc[3] / wsum : 0;
            int r = a > 0 ? int(acc[0] / acc[3] + .5) : 0, g = a > 0 ? int(acc[1] / acc[3] + .5) : 0, b = a > 0 ? int(acc[2] / acc[3] + .5) : 0;
            dp[x] = (uint32_t(clamp8(int(a + .5))) << 24) | (uint32_t(clamp8(r)) << 16) | (uint32_t(clamp8(g)) << 8) | uint32_t(clamp8(b));
        }
    }
    return out;
}

static V flip_surface(Surface* src, bool fx, bool fy) {
    V out = new_surface(src->w(), src->h(), src->srcalpha);
    Surface* d = surf(out);
    d->alpha = src->alpha; d->has_colorkey = src->has_colorkey; d->colorkey = src->colorkey;
    for (int y = 0; y < src->h(); ++y) {
        const uint32_t* sp = row(src->s, fy ? src->h() - 1 - y : y);
        uint32_t* dp = row(d->s, y);
        for (int x = 0; x < src->w(); ++x) dp[x] = sp[fx ? src->w() - 1 - x : x];
    }
    return out;
}

// pygame transform.rotate (32 bpp path, transform.c rotate / rotate90)
static V rotate_surface(Surface* src, double angle) {
    uint32_t bg = src->has_colorkey ? src->colorkey : (src->srcalpha ? 0u : 0xFF000000u);
    int sw = src->w(), sh = src->h();
    double a = std::fmod(angle, 360.0);
    if (a < 0) a += 360.0;
    if (std::fmod(angle, 90.0) == 0) {
        int turns = int(a / 90.0) % 4;
        int nw = (turns % 2) ? sh : sw, nh = (turns % 2) ? sw : sh;
        V out = new_surface(nw, nh, src->srcalpha);
        Surface* d = surf(out);
        d->alpha = src->alpha; d->has_colorkey = src->has_colorkey; d->colorkey = src->colorkey;
        for (int y = 0; y < nh; ++y) {
            uint32_t* dp = row(d->s, y);
            for (int x = 0; x < nw; ++x) {
                int sx, sy;
                switch (turns) {   // counter-clockwise
                    case 0: sx = x; sy = y; break;
                    case 1: sx = sw - 1 - y; sy = x; break;
                    case 2: sx = sw - 1 - x; sy = sh - 1 - y; break;
                    default: sx = y; sy = sh - 1 - x; break;
                }
                dp[x] = row(src->s, sy)[sx];
            }
        }
        return out;
    }
    double rad = angle * .01745329251994329;
    double sangle = std::sin(rad), cangle = std::cos(rad);
    double cx = cangle * sw, cy = cangle * sh, sx = sangle * sw, sy = sangle * sh;
    int nxmax = int(std::max({std::fabs(cx + sy), std::fabs(cx - sy), std::fabs(-cx + sy), std::fabs(-cx - sy)}));
    int nymax = int(std::max({std::fabs(sx + cy), std::fabs(sx - cy), std::fabs(-sx + cy), std::fabs(-sx - cy)}));
    V out = new_surface(nxmax, nymax, src->srcalpha);
    Surface* d = surf(out);
    d->alpha = src->alpha; d->has_colorkey = src->has_colorkey; d->colorkey = src->colorkey;
    int dw = nxmax, dh = nymax;
    int ccy = dh / 2;
    int xd = (sw - dw) << 15, yd = (sh - dh) << 15;
    int isin = int(sangle * 65536), icos = int(cangle * 65536);
    int ax = (dw << 15) - int(cangle * ((dw - 1) << 15));
    int ay = (dh << 15) - int(sangle * ((dw - 1) << 15));
    int xmaxval = (sw << 16) - 1, ymaxval = (sh << 16) - 1;
    for (int y = 0; y < dh; ++y) {
        uint32_t* dp = row(d->s, y);
        int dx = (ax + (isin * (ccy - y))) + xd;
        int dy = (ay - (icos * (ccy - y))) + yd;
        for (int x = 0; x < dw; ++x) {
            if (dx < 0 || dy < 0 || dx > xmaxval || dy > ymaxval) dp[x] = bg;
            else dp[x] = row(src->s, dy >> 16)[dx >> 16];
            dx += icos; dy += isin;
        }
    }
    return out;
}

static V module_with(std::initializer_list<std::pair<const char*, Fn>> fns) {
    V m = new_module("pygame.transform");
    for (auto& [n, f] : fns) module_of(m)->fn(n, f);
    return m;
}

// pygame transform.scale/smoothscale(surface, size, dest_surface): the result is written into dest
static V into_dest(const Args& a, V result) {
    const V* d = a.pos.size() > 2 ? &a.pos[2] : nullptr;
    for (auto& [k, v] : a.kw) if (k.str() == "dest_surface" || k.str() == "dest") d = &v;
    if (!d || d->is_none()) return result;
    Surface* dst = surf(*d);
    Surface* src = surf(result);
    SDL_BlendMode old; SDL_GetSurfaceBlendMode(src->s, &old);
    SDL_SetSurfaceBlendMode(src->s, SDL_BLENDMODE_NONE);
    SDL_BlitSurface(src->s, nullptr, dst->s, nullptr);
    SDL_SetSurfaceBlendMode(src->s, old);
    return *d;
}

static V scale_into72(const Args& a,Surface* src,int nw,int nh,bool smooth) {
    const V* dest=a.pos.size()>2?&a.pos[2]:nullptr;
    for(auto& [key,value]:a.kw)if(key==Sym("dest_surface") || key==Sym("dest"))dest=&value;
    if(dest && !dest->is_none()) {
        Surface* dst=surf(*dest);
        if(dst->w()!=nw || dst->h()!=nh)throw PyError("ValueError","Destination surface not the given width or height");
        SDL_Rect clip;SDL_GetClipRect(dst->s,&clip);
        if(!render72_reference() && !smooth && nw>0 && nh>0 && src->w()>0 && src->h()>0 &&
            !src->has_colorkey && separate_pixels(src,dst) && src->s->format->format==dst->s->format->format &&
            clip.x==0 && clip.y==0 && clip.w==nw && clip.h==nh) {
            if(SDL_SoftStretch(src->s,nullptr,dst->s,nullptr))throw PyError("error",SDL_GetError());
            if(count72()){++stats72.direct_scales;stats72.avoided_copy_bytes+=uint64_t(nw)*nh*4;}
            return *dest;
        }
    }
    return into_dest(a,smooth?scale_smooth(src,nw,nh):scale_nearest(src,nw,nh));
}
V transform_module() {
    static V m = module_with({
        {"scale", [](const Args& a) {
            V source=source_surface_value(a.pos.at(0)); Surface* s = surf(source);
            V size = a.get(1, Sym("size"), nullptr, "scale");
            return scale_into72(a,s,iv(size.idx(0)),iv(size.idx(1)),false);
        }},
        {"scale_by", [](const Args& a) {
            V source=source_surface_value(a.pos.at(0)); Surface* s = surf(source);
            V f = a.pos.at(1);
            double fx = f.is_list() ? f.idx(0).num() : f.num(), fy = f.is_list() ? f.idx(1).num() : fx;
            return scale_nearest(s, int(s->w() * fx), int(s->h() * fy));
        }},
        {"smoothscale", [](const Args& a) {
            V source=source_surface_value(a.pos.at(0)); Surface* s = surf(source);
            V size = a.get(1, Sym("size"), nullptr, "smoothscale");
            return scale_into72(a,s,iv(size.idx(0)),iv(size.idx(1)),true);
        }},
        {"smoothscale_by", [](const Args& a) {
            V source=source_surface_value(a.pos.at(0)); Surface* s = surf(source);
            V f = a.pos.at(1);
            double fx = f.is_list() ? f.idx(0).num() : f.num(), fy = f.is_list() ? f.idx(1).num() : fx;
            return scale_smooth(s, int(s->w() * fx), int(s->h() * fy));
        }},
        {"flip", [](const Args& a) {
            static const V f(false);
            V source=source_surface_value(a.pos.at(0));
            return flip_surface(surf(source), a.get(1, Sym("flip_x"), &f).truthy(), a.get(2, Sym("flip_y"), &f).truthy());
        }},
        {"rotate", [](const Args& a) { V source=source_surface_value(a.pos.at(0)); return rotate_surface(surf(source), a.get(1, Sym("angle"), nullptr, "rotate").num()); }},
        {"rotozoom", [](const Args& a) {
            V source=source_surface_value(a.pos.at(0)); Surface* s = surf(source);
            double angle = a.pos.at(1).num(), zoom = a.pos.at(2).num();
            V z = scale_smooth(s, int(s->w() * zoom + .5), int(s->h() * zoom + .5));
            return angle == 0 ? z : rotate_surface(surf(z), angle);
        }},
        {"get_smoothscale_backend", [](const Args&) { return V("GENERIC"); }},
        {"set_smoothscale_backend", [](const Args&) { return V::none(); }},
    });
    static bool measured=[] {
        auto* module=module_of(m);
        for(auto& entry:module->attrs) {
            const std::string& name=entry.first.str();
            if(name=="scale" || name=="smoothscale" || name=="scale_by" || name=="smoothscale_by" || name=="flip" || name=="rotate" || name=="rotozoom") {
                V implementation=entry.second;
                entry.second=V::func([implementation](const Args& args){
                    V metrics=transform_metrics;bool timed=metrics.is_dict() && metrics.get(V("profile_detail"),V(false)).truthy();
                    auto started=timed?std::chrono::steady_clock::now():std::chrono::steady_clock::time_point{};V output=implementation.call(args);
                    if(metrics.is_dict()) {
                        metrics.at(V("executions"))=metrics.get(V("executions"),V(0))+V(1);
                        Surface* surface=surf(output);metrics.at(V("output_pixels"))=metrics.get(V("output_pixels"),V(0))+V(double(surface->w())*surface->h());
                        if(timed)metrics.at(V("pixel_ms"))=metrics.get(V("pixel_ms"),V(0))+V(std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count());
                    }
                    return output;
                });
            }
        }
        return true;
    }();
    (void)measured;return m;
}

V surface_type() { static V t = V::func(surface_ctor); return t; }
V rect_type() { static V t = V::func(rect_ctor); return t; }

}  // namespace pvz::pg
