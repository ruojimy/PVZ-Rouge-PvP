#include "sim/pvp/hand/graphics.h"
#include "sim/pvp/gen/pm_native_animation.h"
#include "core/png.h"
#include <cstring>
#include "core/fsutil.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <cstring>
#include <fstream>
#include <map>
#include <chrono>
#include "sim/pvp/shim/pm_performance.h"
#include "sim/pvp/shim/pm_expansion_assets.h"
#include "sim/pvp/shim/pm_native_multiworker.h"

namespace pvz::gfx {

namespace {
struct AtlasEntry { std::string file; int w, h; };
std::map<std::string, std::map<std::string, AtlasEntry>> g_index;
std::string g_png_dir;
// recipe key prefix -> atlas dictionary name
const std::pair<const char*, const char*> kPrefixes[] = {{"world:", "图集"}, {"ui:", "ui图集"}, {"bg:", "背景图集"}, {"near:", "近景图集"}};

// Real pixels of an untransformed atlas image (the simulation samples them: 原版 增粒子).
const png::Image* pixels_of(const Image* im) {
    if (im->r.angle != 0 || im->r.flip_y || !im->r.children.empty()) return nullptr;
    for (auto& [prefix, atlas] : kPrefixes) {
        size_t n = std::strlen(prefix);
        if (im->r.key.compare(0, n, prefix) != 0) continue;
        auto a = g_index.find(atlas);
        if (a == g_index.end()) return nullptr;
        auto e = a->second.find(im->r.key.substr(n));
        if (e == a->second.end() || e->second.w != im->w || e->second.h != im->h) return nullptr;
        static std::map<std::string, png::Image> cache;
        auto c = cache.find(e->second.file);
        if (c == cache.end()) {
            std::string err;
            c = cache.emplace(e->second.file, png::load(g_png_dir + "/" + e->second.file, &err)).first;
            if (!c->second.ok()) throw PyError("RuntimeError", "atlas pixels: " + err);
        }
        return &c->second;
    }
    return nullptr;
}
}

std::string atlas_file(const std::string& atlas, const std::string& key) {
    auto a = g_index.find(atlas);
    if (a == g_index.end()) return "";
    auto e = a->second.find(key);
    return e == a->second.end() ? std::string() : g_png_dir + "/" + e->second.file;
}
std::vector<std::string> atlas_keys(const std::string& atlas) {
    std::vector<std::string> out;
    auto a = g_index.find(atlas);
    if (a != g_index.end()) for (auto& [k, e] : a->second) out.push_back(k);
    return out;
}
void load_atlas_index(const std::string& path) {
    std::ifstream f(u8p(path), std::ios::binary);
    if (!f) return;
    g_png_dir = path.substr(0, path.find_last_of("/\\") + 1) + "_png";
    auto j = nlohmann::json::parse(f);
    for (auto it = j.begin(); it != j.end(); ++it) {
        const auto& entries = it.value();
        if (!entries.is_object()) continue;
        for (auto e = entries.begin(); e != entries.end(); ++e) {
            const auto& v = e.value();
            if (v.is_array() && v.size() >= 3 && v[1].is_number())
                g_index[it.key()][e.key()] = {v[0].get<std::string>(), v[1].get<int>(), v[2].get<int>()};
        }
    }
}

V make_image(const std::string& key, int w, int h) {
    auto p = std::make_shared<Image>();
    p->r.key = key;
    p->w = w;
    p->h = h;
    if (key == "canvas")
        p->recipe = py_dict({{V("op"), V("canvas")}, {V("size"), V::nums({double(w), double(h)})}, {V("flags"), V(65536.0)}, {V("depth"), V(32.0)}});
    else
        p->recipe = py_dict({{V("op"), V("asset")}, {V("key"), V(key)}, {V("size"), V::nums({double(w), double(h)})}});
    return V::inst(p);
}
// result of a pygame.transform operation: new recipe {op, source: describe(src), args}
static V transformed(const Image* s, const char* op, std::vector<V> args, int w, int h) {
    auto p = std::make_shared<Image>(*s);
    p->dyn.clear();
    for(const auto& field:s->dyn)if(field.first==Sym("__graphics_metrics__") || field.first==Sym("graphics") || field.first==Sym("__native_recorded_image__"))p->dyn.push_back(field);
    p->w = w; p->h = h;
    p->recipe = py_dict({{V("op"), V(op)}, {V("source"), s->describe()}, {V("args"), V::list(std::move(args))}});
    return V::inst(p);
}
Image* image_of(const V& v) { return as<Image>(v); }

static V copy_image(const Image* s) {
    auto p = std::make_shared<Image>(*s);
    p->dyn.clear();
    for(const auto& field:s->dyn)if(field.first==Sym("__graphics_metrics__") || field.first==Sym("graphics") || field.first==Sym("__native_recorded_image__"))p->dyn.push_back(field);
    return V::inst(p);
}

V Image::describe() const {
    V alpha = r.alpha == -2 || (r.alpha == -1 && !r.pixel_alpha) ? V::none() : V(double(r.alpha < 0 ? 255 : r.alpha));
    return py_dict({{V("image"), recipe}, {V("alpha"), alpha},
                    {V("colorkey"), r.colorkey}, {V("size"), V::nums({double(w), double(h)})}});
}

// pygame.Rect (integer geometry like pygame)
struct Rect : PyObj {
    double x = 0, y = 0, w = 0, h = 0;
    const char* type_name() const override { return "Rect"; }
    V getitem(const V& k) override {
        int64_t i = int64_t(k.num());
        if (i < 0) i += 4;
        return V(i == 0 ? x : i == 1 ? y : i == 2 ? w : h);
    }
    size_t length() override { return 4; }
    V iterate() override { return V::nums({x, y, w, h}); }
    V property(Sym n, bool& found) override {
        found = true;
        const std::string& s = n.str();
        if (s == "x" || s == "left") return V(x);
        if (s == "y" || s == "top") return V(y);
        if (s == "w" || s == "width") return V(w);
        if (s == "h" || s == "height") return V(h);
        if (s == "right") return V(x + w);
        if (s == "bottom") return V(y + h);
        if (s == "centerx") return V(double(int64_t(x + std::floor(w / 2))));
        if (s == "centery") return V(double(int64_t(y + std::floor(h / 2))));
        if (s == "center") return V::tuple({V(x + std::floor(w / 2)), V(y + std::floor(h / 2))});
        if (s == "topleft") return V::tuple({V(x), V(y)});
        if (s == "size") return V::tuple({V(w), V(h)});
        found = false;
        return V();
    }
    V method(Sym n) override {
        auto sp = std::static_pointer_cast<Rect>(shared_from_this());
        if (n == Sym("move")) return V::func([sp](const Args& a) {
            auto r = std::make_shared<Rect>(*sp); r->dyn.clear();
            r->x += a.pos.at(0).num(); r->y += a.pos.at(1).num();
            return V::inst(r);
        });
        if (n == Sym("copy")) return V::func([sp](const Args&) { auto r = std::make_shared<Rect>(*sp); r->dyn.clear(); return V::inst(r); });
        if (n == Sym("colliderect")) return V::func([sp](const Args& a) {
            V o = a.pos.at(0);
            double ox = rd(o, V(0.0)).num(), oy = rd(o, V(1.0)).num(), ow = rd(o, V(2.0)).num(), oh = rd(o, V(3.0)).num();
            return V(sp->x < ox + ow && ox < sp->x + sp->w && sp->y < oy + oh && oy < sp->y + sp->h);
        });
        return V();
    }
};
static V rect_of(double x, double y, double w, double h) {
    auto r = std::make_shared<Rect>();
    r->x = std::floor(x); r->y = std::floor(y); r->w = std::floor(w); r->h = std::floor(h);
    return V::inst(r);
}

static V image_metrics(const Image* image){for(const auto& field:image->dyn)if(field.first==Sym("__graphics_metrics__"))return field.second;return V();}
static void attach_metrics(Image* image,const V& metrics){if(metrics.is_dict()){image->setattr(Sym("__graphics_metrics__"),metrics);image->setattr(Sym("graphics"),metrics);image->setattr(Sym("__native_recorded_image__"),V(true));}}
static void invalidate_pixels(Image* image){auto& attrs=image->dyn;attrs.erase(std::remove_if(attrs.begin(),attrs.end(),[](const auto& field){return field.first==Sym("__materialized_pixels__");}),attrs.end());}
static V materialize_pixels(Image* image,const V& metrics){
    if(V* ready=image->find_dyn(Sym("__materialized_pixels__")))return *ready;
    if(!py::has_native_hook("graphics.materialize_image"))throw PyError("NotImplementedError","eager recorded pixels require the linked SDL materializer");
    V result=py::native_hook(V("graphics.materialize_image"),Args{image->describe(),metrics});
    image->setattr(Sym("__materialized_pixels__"),result);return result;
}
// This is the same retained pixel-equivalent budget as deferred images: each
// held transform input and output contributes area*4. It is not a heap/RSS claim.
static double retained_recipe_pixels(const V& description) {
    constexpr double limit=24.*1024*1024;double total=0;size_t nodes=0;
    std::vector<V> pending{description};
    while(!pending.empty()) {
        V item=std::move(pending.back());pending.pop_back();if(++nodes>12000)return limit+1;
        V size=item.get(V("size"));if(!size.is_list() || size.len()!=2)return limit+1;
        double bytes=size.idx(0).num()*size.idx(1).num()*4;if(!std::isfinite(bytes) || bytes<0 || total+bytes>limit)return limit+1;total+=bytes;
        V recipe=item.get(V("image"));if(!recipe.is_dict())return limit+1;
        if(const V* source=recipe.find(V("source")))pending.push_back(*source);
        if(const V* overlay=recipe.find(V("overlay")))pending.push_back(*overlay);
    }
    return total;
}
static const bool recorded_frame_pixels_hook=[] {
    py::register_native_hook("graphics.recorded_image_pixels",[](const Args& args){
        Image* image=image_of(args.pos.at(0));if(!image)throw PyError("TypeError","recorded frame pixels require a native recorded image");
        return materialize_pixels(image,image_metrics(image));
    });return true;
}();
V Image::method(Sym name) {
    auto sp = std::static_pointer_cast<Image>(shared_from_this());
    const std::string& n = name.str();
    if (n == "describe") return V::func([sp](const Args&) { return sp->describe(); });
    if (n == "get_size") return V::func([sp](const Args&) { return V::tuple({V(double(sp->w)), V(double(sp->h))}); });
    if (n == "get_width") return V::func([sp](const Args&) { return V(double(sp->w)); });
    if (n == "get_height") return V::func([sp](const Args&) { return V(double(sp->h)); });
    if(n=="frozen")return V::func([sp](const Args&){
        V output=copy_image(sp.get());if(V* pixels=sp->find_dyn(Sym("__materialized_pixels__")))output.box->inst->setattr(Sym("__materialized_pixels__"),*pixels);return output;
    });
    if(n=="retained_bytes")return V::func([sp](const Args&){
        if(V* pixels=sp->find_dyn(Sym("__materialized_pixels__")))return callm(*pixels,Sym("get_pitch"),Args{})*callm(*pixels,Sym("get_height"),Args{});
        return V(retained_recipe_pixels(sp->describe()));
    });
    if (n == "copy" || n == "convert_alpha" || n == "convert") return V::func([sp, n](const Args&) {
        V out = copy_image(sp.get()); Image* image = image_of(out);
        if (n == "convert") { image->r.pixel_alpha = false; image->r.alpha = -2; }
        else if (n == "convert_alpha") { image->r.pixel_alpha = true; if (image->r.alpha == -2) image->r.alpha = -1; }
        V metrics=image_metrics(sp.get());
        if(metrics.is_dict()) {
            bool shared=n=="copy" && metrics.get(V("copy_on_write"),V(true)).truthy() && sp->r.colorkey.is_none();
            if(shared)metrics.at(V("shared_copies"))=metrics.get(V("shared_copies"),V(0))+V(1);
            else if(py::has_native_hook("graphics.materialize_image")) {
                V pixels=materialize_pixels(sp.get(),metrics),copied=callm(pixels,Sym(n),Args{});
                image->setattr(Sym("__materialized_pixels__"),copied);
                metrics.at(V("copies"))=metrics.get(V("copies"),V(0))+V(1);
                metrics.at(V("copy_bytes"))=metrics.get(V("copy_bytes"),V(0))+callm(copied,Sym("get_pitch"),Args{})*callm(copied,Sym("get_height"),Args{});
            }else if(!metrics.get(V("lazy_pixels"),V(true)).truthy() || !metrics.get(V("copy_on_write"),V(true)).truthy())throw PyError("NotImplementedError","eager image copy requires the linked SDL materializer");
            if(!metrics.get(V("share_recipe"),V(true)).truthy())image->recipe=deepcopy(image->recipe);
        }
        return out;
    });
    if (n == "set_alpha") return V::func([sp](const Args& a) {
        invalidate_pixels(sp.get());
        if (a.pos.empty() || a.pos[0].is_none()) { sp->r.alpha = -2; return V::none(); }
        sp->r.alpha = int(a.pos[0].num());
        if (sp->r.alpha > 255) sp->r.alpha = 255;
        if (sp->r.alpha < 0) sp->r.alpha = 0;
        return V::none();
    });
    if (n == "get_alpha") return V::func([sp](const Args&) { return rd(sp->describe(), V("alpha")); });
    if (n == "get_flags") return V::func([sp](const Args&) { return V(sp->r.alpha != -2 && (sp->r.pixel_alpha || sp->r.alpha >= 0) ? 65536 : 0); });
    if (n == "get_pitch") return V::func([sp](const Args&) { return V(sp->w * 4); });
    if (n == "set_colorkey") return V::func([sp](const Args& a) {
        invalidate_pixels(sp.get());
        sp->r.colorkey = a.pos.empty() || a.pos[0].is_none() ? V::none() : pm_native_animation::f__plain(Args{a.pos[0]});
        return V::none();
    });
    if (n == "fill") return V::func([sp](const Args& a) {
        invalidate_pixels(sp.get());
        static const V none = V::none(), zero(0);
        V color = a.get(0, Sym("color"), nullptr), rect = a.get(1, Sym("rect"), &none), flags = a.get(2, Sym("special_flags"), &zero);
        V before = sp->describe();
        sp->recipe = py_dict({{V("op"), V("fill")}, {V("source"), before}, {V("color"), pm_native_animation::f__plain(Args{color})},
            {V("rect"), pm_native_animation::f__plain(Args{rect})}, {V("flags"), flags}});
        sp->r.children.emplace_back(V::none());
        return rect.is_none() ? rect_of(0, 0, sp->w, sp->h) : rect;
    });
    if (n == "lock" || n == "unlock") return V::func([](const Args&) { return V::none(); });
    if (n == "get_colorkey") return V::func([sp](const Args&) { return sp->r.colorkey; });
    if (n == "get_rect") return V::func([sp](const Args& a) {
        double x = 0, y = 0;
        for (auto& p : a.kw) {
            if (p.first == Sym("topleft")) { x = p.second.idx(0).num(); y = p.second.idx(1).num(); }
            if (p.first == Sym("center")) { x = std::floor(p.second.idx(0).num()) - std::floor(sp->w / 2.0); y = std::floor(p.second.idx(1).num()) - std::floor(sp->h / 2.0); }
        }
        return rect_of(x, y, sp->w, sp->h);
    });
    if (n == "get_bounding_rect") return V::func([sp](const Args& args) {
        if(V* ready=sp->find_dyn(Sym("__materialized_pixels__")))return callm(*ready,Sym("get_bounding_rect"),args);
        const png::Image* px = pixels_of(sp.get());
        if (!px && py::has_native_hook("graphics.materialize_image")) return callm(materialize_pixels(sp.get(),image_metrics(sp.get())), Sym("get_bounding_rect"), Args{});
        if (!px) return rect_of(0, 0, sp->w, sp->h);
        int x0 = px->w, y0 = px->h, x1 = -1, y1 = -1;   // pygame: alpha >= 1
        for (int y = 0; y < px->h; ++y)
            for (int x = 0; x < px->w; ++x)
                if (px->at(x, y)[3] >= 1) { x0 = std::min(x0, x); y0 = std::min(y0, y); x1 = std::max(x1, x); y1 = std::max(y1, y); }
        if (x1 < 0) return rect_of(0, 0, 0, 0);
        int fx0 = sp->r.flip_x ? px->w - 1 - x1 : x0;
        return rect_of(fx0, y0, x1 - x0 + 1, y1 - y0 + 1);
    });
    if (n == "get_at") return V::func([sp](const Args& a) {
        V pos = a.pos.at(0);
        int x = int(pos.idx(0).num()), y = int(pos.idx(1).num());
        if (x < 0 || y < 0 || x >= sp->w || y >= sp->h) throw PyError("IndexError", "pixel index out of range");
        if(V* ready=sp->find_dyn(Sym("__materialized_pixels__")))return callm(*ready,Sym("get_at"),a);
        const png::Image* px = pixels_of(sp.get());
        if (!px && py::has_native_hook("graphics.materialize_image")) return callm(materialize_pixels(sp.get(),image_metrics(sp.get())), Sym("get_at"), a);
        if (!px) throw PyError("NotImplementedError", "get_at on a transformed image: " + sp->r.key);
        const uint8_t* c = px->at(sp->r.flip_x ? px->w - 1 - x : x, y);
        int alpha = c[3];
        V out = V::tuple({V(double(c[0])), V(double(c[1])), V(double(c[2])), V(double(alpha))});
        out.box->color = true;   // Surface.get_at returns a pygame.Color
        return out;
    });
    if (n == "blit") return V::func([sp](const Args& a) {
        invalidate_pixels(sp.get());
        static const V none = V::none(), zero(0);
        V source = a.get(0, Sym("source"), nullptr), dest = a.get(1, Sym("dest"), nullptr), area = a.get(2, Sym("area"), &none), flags = a.get(3, Sym("special_flags"), &zero);
        Image* overlay = image_of(source);
        if (!overlay) throw PyError("TypeError", "Native image blit requires a recorded native image");
        V before = sp->describe(), description = overlay->describe();
        sp->recipe = py_dict({{V("op"), V("blit")}, {V("source"), before}, {V("overlay"), description},
            {V("dest"), pm_native_animation::f__plain(Args{dest})}, {V("area"), pm_native_animation::f__plain(Args{area})}, {V("flags"), flags}});
        sp->r.children.emplace_back(V::none());
        return rect_of(dest.idx(0).num(), dest.idx(1).num(), overlay->w, overlay->h);
    });
    if (n == "subsurface") return V::func([sp](const Args& a) {
        V img = copy_image(sp.get());
        auto* p = image_of(img);
        V rc = pm_native_animation::f__plain(Args{a.pos.at(0)});
        int x = int(rc.idx(0).num()), y = int(rc.idx(1).num()), w = int(rc.idx(2).num()), h = int(rc.idx(3).num());
        if (x < 0 || y < 0 || w < 0 || h < 0 || x + w > sp->w || y + h > sp->h) throw PyError("ValueError", "subsurface rectangle outside surface area");
        p->recipe = py_dict({{V("op"), V("crop")}, {V("source"), sp->describe()}, {V("rect"), rc}});
        p->r.children.emplace_back(V::none()); p->w = w; p->h = h;
        return img;
    });
    return V();
}

// pygame-ce 2.4 rotate output size (angle parsed as float32)
static void rotated_size(int w, int h, double angle_d, int& ow, int& oh) {
    float af = float(angle_d);
    double angle = af;
    if (std::fmod(angle, 90.0) == 0.0) {
        if (int64_t(angle / 90) % 2) { ow = h; oh = w; } else { ow = w; oh = h; }
        return;
    }
    double rad = angle * .01745329251994329;
    double c = std::cos(rad), s = std::sin(rad);
    ow = int(std::fabs(c * w) + std::fabs(s * h));
    oh = int(std::fabs(s * w) + std::fabs(c * h));
}

static V transform_ns() {
    V t = V::dict();
    t.at(V("scale")) = V::func([](const Args& a) {
        auto* s = image_of(a.pos.at(0));
        if (!s) throw PyError("TypeError", "transform.scale needs a Surface");
        int w = int(a.pos.at(1).idx(0).num()), h = int(a.pos.at(1).idx(1).num());
        return transformed(s, "scale", {V::nums({double(w), double(h)})}, w, h);
    });
    t.at(V("smoothscale"))=V::func([](const Args& a){
        auto* source=image_of(a.pos.at(0));if(!source)throw PyError("TypeError","transform.smoothscale needs a Surface");
        int w=int(a.pos.at(1).idx(0).num()),h=int(a.pos.at(1).idx(1).num());
        return transformed(source,"smoothscale",{V::nums({double(w),double(h)})},w,h);
    });
    t.at(V("flip")) = V::func([](const Args& a) {
        auto* s = image_of(a.pos.at(0));
        if (!s) throw PyError("TypeError", "transform.flip needs a Surface");
        V img = transformed(s, "flip", {a.pos.at(1), a.pos.size() > 2 ? a.pos[2] : V(false)}, s->w, s->h);
        auto* p = image_of(img);
        if (a.pos.at(1).truthy()) p->r.flip_x = !p->r.flip_x;
        if (a.pos.size() > 2 && a.pos[2].truthy()) p->r.flip_y = !p->r.flip_y;
        return img;
    });
    t.at(V("rotate")) = V::func([](const Args& a) {
        auto* s = image_of(a.pos.at(0));
        if (!s) throw PyError("TypeError", "transform.rotate needs a Surface");
        double ang = a.pos.at(1).num();
        int w, h;
        rotated_size(s->w, s->h, ang, w, h);
        V img = transformed(s, "rotate", {a.pos.at(1)}, w, h);
        image_of(img)->r.angle += ang;
        return img;
    });
    t.at(V("rotozoom")) = V::func([](const Args& a) {
        auto* s = image_of(a.pos.at(0));
        if(!s)throw PyError("TypeError","transform.rotozoom needs a Surface");
        double ang = a.pos.at(1).num(), z = a.pos.at(2).num();
        int w,h;rotated_size(int(s->w*z+.5),int(s->h*z+.5),ang,w,h);
        V img=transformed(s,"rotozoom",{a.pos.at(1),a.pos.at(2)},w,h);
        image_of(img)->r.angle+=ang;return img;
    });
    return t;
}

V* Recorder::slot(Sym name) {
    if (name == Sym("enabled")) return &enabled_v;
    if (name == Sym("entity_override")) return &override_v;
    if (name == Sym("entity_source")) return &source_v;
    if (name == Sym("tick")) return &tick_v;
    if (name == Sym("commands")) return &commands_v;
    if (name == Sym("positions")) return &positions_v;
    if (name == Sym("size")) return &size_v;
    if (name == Sym("latest_pixels")) return &latest_pixels_v;   // performance overlay pixels (off: None)
    if (name == Sym("local_pixels")) return &local_pixels_v;
    if (name == Sym("command_ms")) return &command_ms_v;
    if (name == Sym("total_commands")) return &total_commands_v;
    if (name == Sym("max_commands")) return &max_commands_v;
    return nullptr;
}

void Recorder::append_command(V command) {
    V metrics;if(V* field=find_dyn(Sym("__graphics_metrics__")))metrics=*field;
    struct CommandTimer {Recorder* recorder;bool active;std::chrono::steady_clock::time_point begin;~CommandTimer(){if(active)recorder->command_ms_v=recorder->command_ms_v+V(std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-begin).count());}} timer{this,metrics.is_dict() && metrics.get(V("profile_detail"),V(false)).truthy(),std::chrono::steady_clock::now()};

    if (!enabled_v.truthy()) return;
    if (double(commands_v.len()) >= max_commands_v.num()) throw PyError("NativeGraphicsError", "Native draw command limit exceeded");
    V source = override_v;
    if (source.is_none() && !source_v.is_none()) source = source_v.call(Args{});
    if (source.is_obj() || source.is_dict()) {
        V id = source.get(V("_pvp_id"), V::none());
        if (id.is_str() && id.truthy()) {
            V position = source.get(V(py::startswith(id, V("hero:")) ? "玩家位置" : "位置"), V::none());
            if (!position.is_none()) {
                command.at(V("entity")) = id;
                positions_v.at(id) = V::list({position.idx(0), position.idx(1)});
            }
        }
    }
    commands_v.append(command);
    total_commands_v = total_commands_v + V(1);
}

V Recorder::method(Sym name) {
    auto sp = std::static_pointer_cast<Recorder>(shared_from_this());
    const std::string& n = name.str();
    if (n == "begin_frame") return V::func([sp](const Args& a) {
        sp->tick = int(a.pos.at(0).num());
        sp->tick_v = a.pos.at(0);
        sp->positions_v = V::dict();
        sp->commands_v = V::list();
        sp->override_v = V::none();
        V metrics;if(V* owner=sp->find_dyn(Sym("__graphics_metrics__")))metrics=*owner;
        sp->local_pixels_v=metrics.is_dict() && metrics.get(V("local_pixels"),V(false)).truthy() && py::has_native_hook("graphics.frame_pixels")?py::native_hook(V("graphics.frame_pixels"),Args{}):V::none();
        return V::none();
    });
    if (n == "blit") return V::func([sp](const Args& a) {
        auto* img = image_of(a.pos.at(0));
        double x = a.pos.at(1).idx(0).num(), y = a.pos.at(1).idx(1).num();
        V rect = rect_of(x, y, img ? img->w : 0, img ? img->h : 0);
        if (sp->enabled_v.has() && !sp->enabled_v.truthy()) return rect;
        V cmd = py_dict({{V("op"), V("image")}, {V("surface"), img ? img->describe() : V::none()}, {V("pos"), V::nums({x, y})},
                         {V("area"), a.pos.size() > 2 ? a.pos[2] : V::none()}, {V("flags"), a.pos.size() > 3 ? a.pos[3] : V(0.0)}});
        if(!img)throw PyError("NativeGraphicsError","recorded blit requires a registered native image");
        if(!sp->local_pixels_v.is_none())callm(sp->local_pixels_v,Sym("add"),Args{cmd.get(V("surface")),a.pos.at(0)});
        sp->append_command(cmd);
        return rect;
    });
    if (n == "fill") return V::func([sp](const Args& a) {
        static const V none = V::none(), zero(0);
        sp->append_command(py_dict({{V("op"), V("fill")}, {V("color"), pm_native_animation::f__plain(Args{a.get(0, Sym("color"), nullptr)})},
            {V("rect"), pm_native_animation::f__plain(Args{a.get(1, Sym("rect"), &none)})}, {V("flags"), a.get(2, Sym("special_flags"), &zero)}}));
        return rect_of(0, 0, sp->width, sp->height);
    });
    if (n == "primitive") return V::func([sp](const Args& a) {
        sp->append_command(py_dict({{V("op"), V("primitive")}, {V("primitive"), a.pos.at(0)},
            {V("args"), pm_native_animation::f__plain(Args{a.pos.size() > 1 ? a.pos[1] : V::list()})},
            {V("kwargs"), a.pos.size() > 2 ? pm_native_animation::f__plain(Args{a.pos[2]}) : V::dict()}}));
        return rect_of(0, 0, sp->width, sp->height);
    });
    if (n == "snapshot") return V::func([sp](const Args&) {
        V frame=py_dict({{V("protocol"), V("native-draw-v1")}, {V("tick"), sp->tick_v}, {V("tile"), sp->tile_v},
                        {V("commands"), sp->commands_v}, {V("positions"), sp->positions_v}});
        sp->latest_pixels_v=sp->local_pixels_v;
        if(!sp->latest_pixels_v.is_none())pvz::setattr(sp->latest_pixels_v,Sym("frame"),frame);
        return frame;
    });
    if (n == "get_size") return V::func([sp](const Args&) { return V::tuple({V(double(sp->width)), V(double(sp->height))}); });
    if (n == "get_width") return V::func([sp](const Args&) { return V(double(sp->width)); });
    if (n == "get_height") return V::func([sp](const Args&) { return V(double(sp->height)); });
    if (n == "get_rect") return V::func([sp](const Args&) { return rect_of(0, 0, sp->width, sp->height); });
    return V();
}

static V draw_ns(std::shared_ptr<Recorder> rec) {
    V d = V::dict();
    for (const char* prim : {"line", "lines", "aaline", "aalines", "polygon", "rect", "circle", "ellipse", "arc"}) {
        std::string name = prim;
        d.at(V(prim)) = V::func([rec, name](const Args& a) {
            if (a.pos.empty()) throw PyError("TypeError", "Draw primitive requires a surface");
            std::vector<V> rest(a.pos.begin() + 1, a.pos.end());
            V kwargs = V::dict(); for (auto& [key, value] : a.kw) kwargs.at(V(key)) = value;
            if (as<Recorder>(a.pos.at(0)) == rec.get()) {
                return rec->method(Sym("primitive")).call(Args{V(name), V::list(rest), kwargs});
            } else if (auto* img = image_of(a.pos.at(0))) {
                invalidate_pixels(img);
                V before = img->describe();
                img->recipe = py_dict({{V("op"), V("draw")}, {V("source"), before}, {V("primitive"), V(name)},
                    {V("args"), pm_native_animation::f__plain(Args{V::list(rest)})}, {V("kwargs"), pm_native_animation::f__plain(Args{kwargs})}});
                img->r.children.emplace_back(V::none());
            }
            return rect_of(0, 0, 0, 0);
        });
    }
    return d;
}

// Like Python _Pygame.__getattr__, delegate non-recording members to the
// installed pygame backend. Headless callers have no such backend.
struct PygameFacade : PyObj {
    V members = V::dict();
    const char* type_name() const override { return "pygame"; }
    V property(Sym n, bool& found) override {
        const V* p = members.find(V(n));
        if (p && p->has()) { found = true; return *p; }
        found = true;
        V backend=py::stdlib(V("pygame"));
        if(backend.has() && backend.t!=V::FUNC)return pvz::getattr(backend,n);
        throw PyError("AttributeError","headless pygame backend has no attribute '"+n.str()+"'");
    }
};
static std::shared_ptr<Recorder> g_last_recorder;
struct MeasuredTransforms : PyObj {
    V operations,metrics;
    const char* type_name()const override{return "NativeRecipeTransforms";}
    V* slot(Sym name)override{if(const V* field=metrics.find(V(name)))return &metrics.at(V(name));return nullptr;}
    V method(Sym name)override{const V* field=operations.find(V(name));return field?*field:V();}
    bool call_method(Sym name,const Args& args,V& out)override{V function=method(name);if(!function.has())return false;out=function.call(args);return true;}
};
V make_pygame() {
    V metrics=V::dict();
    for(const char* name:{"hits","misses","evictions","cache_bytes","executions","output_pixels","deferred","pixel_ms","copies","copy_bytes","shared_copies"})metrics.at(V(name))=V(0);
    for(const auto& flag:{std::pair<const char*,const char*>{"lazy_pixels","LAZY_PIXELS"},{"copy_on_write","IMAGE_COW"},{"share_recipe","SHARE_RECIPE"}})metrics.at(V(flag.first))=pm_performance::f_enabled(Args{V(flag.second)});
    metrics.at(V("cache_enabled"))=pm_native_multiworker::f_fastpath_enabled(Args{});
    metrics.at(V("defer_capture"))=V(false);metrics.at(V("profile_detail"))=V(false);
    metrics.at(V("loaded_sources"))=V::dict();
    metrics.at(V("local_pixels"))=V(py::has_native_hook("graphics.frame_pixels") && pm_performance::f_enabled(Args{V("LOCAL_PIXELS")}).truthy());
    metrics.at(V("counter_scope"))=V("native recipe frontend: requests, physical copies and successful SDL materializer transforms; no frontend transform cache; client replay and public detached pixel snapshots excluded; timings only in detailed mode");
    auto f = std::make_shared<PygameFacade>();
    auto rec = std::make_shared<Recorder>();
    g_last_recorder = rec;
    V& pg = f->members;
    pg.at(V("__graphics_metrics__"))=metrics;rec->setattr(Sym("__graphics_metrics__"),metrics);
    auto measured=std::make_shared<MeasuredTransforms>();measured->operations=transform_ns();measured->metrics=metrics;
    for(auto& operation:measured->operations.kv()) {
        V implementation=operation.second;
        operation.second=V::func([implementation,metrics](const Args& args) mutable {
            V result=implementation.call(args);Image* image=image_of(result);attach_metrics(image,metrics);
            metrics.at(V("misses"))=metrics.get(V("misses"),V(0))+V(1);
            bool deferred=metrics.get(V("cache_enabled"),V(true)).truthy() && (metrics.get(V("lazy_pixels"),V(true)).truthy() || metrics.get(V("defer_capture"),V(false)).truthy());
            if(deferred)metrics.at(V("deferred"))=metrics.get(V("deferred"),V(0))+V(1);else materialize_pixels(image,metrics);
            return result;
        });
    }
    pg.at(V("transform"))=V::inst(measured);
    pg.at(V("draw")) = draw_ns(rec);
    pg.at(V("SRCALPHA")) = V(65536.0);
    pg.at(V("BLEND_RGB_MAX")) = V(5.0);
    for (auto [name,flag] : {std::pair<const char*,int>{"BLEND_ADD",1}, {"BLEND_RGB_ADD",1},
            {"BLEND_SUB",2},{"BLEND_RGB_SUB",2},{"BLEND_MULT",3},{"BLEND_RGB_MULT",3},
            {"BLEND_MIN",4},{"BLEND_RGB_MIN",4},{"BLEND_MAX",5},{"BLEND_RGBA_ADD",6},
            {"BLEND_RGBA_SUB",7},{"BLEND_RGBA_MULT",8},{"BLEND_RGBA_MIN",9},
            {"BLEND_RGBA_MAX",16},{"BLEND_PREMULTIPLIED",17},{"BLEND_ALPHA_SDL2",18}})
        pg.at(V(name))=V(flag);
    pg.at(V("Surface")) = V::func([metrics](const Args& a) {
        int w = int(a.pos.at(0).idx(0).num()), h = int(a.pos.at(0).idx(1).num());
        static const V zero(0), depth(32);
        V flags = a.get(1, Sym("flags"), &zero);
        V image = make_image("canvas", w, h); Image* native = image_of(image);
        attach_metrics(native,metrics);
        native->r.pixel_alpha = (int(flags.num()) & 65536) != 0;
        native->recipe.at(V("flags")) = flags;
        native->recipe.at(V("depth")) = a.get(2, Sym("depth"), &depth);
        return image;
    });
    pg.at(V("Rect")) = V::func([](const Args& a) {
        if (a.pos.size() >= 4) return rect_of(a.pos[0].num(), a.pos[1].num(), a.pos[2].num(), a.pos[3].num());
        if (a.pos.size() == 2) return rect_of(a.pos[0].idx(0).num(), a.pos[0].idx(1).num(), a.pos[1].idx(0).num(), a.pos[1].idx(1).num());
        return a.pos.at(0);
    });
    pg.at(V("Color")) = V::func([](const Args& a) {
        // pygame.Color: always four channels (alpha 255 by default), tuple-equal, with .r .g .b .a
        std::vector<V> ch = a.pos;
        if (ch.size() == 1 && (ch[0].t == V::LIST || ch[0].t == V::TUPLE)) ch = ch[0].box->items;
        bool numeric = ch.size() == 3 || ch.size() == 4;
        for (auto& c : ch) numeric = numeric && c.is_num();
        if (!numeric) return V::tuple(a.pos);   // named / hex colours are not used by the recorded native code
        if (ch.size() == 3) ch.push_back(V(255.0));
        V out = V::tuple(ch);
        out.box->color = true;
        return out;
    });
    V font = V::dict();
    font.at(V("get_init")) = V::func([](const Args&) { return V(true); });
    font.at(V("init")) = V::func([](const Args&) { return V::none(); });
    pg.at(V("font")) = font;
    V display = V::dict();
    display.at(V("get_surface")) = V::func([](const Args&) { return make_image("display", 1, 1); });
    display.at(V("init")) = V::func([](const Args&) { return V::none(); });
    display.at(V("set_mode")) = V::func([](const Args&) { return make_image("display", 1, 1); });
    pg.at(V("display")) = display;
    pg.at(V("HIDDEN")) = V(0.0);
    pg.at(V("__recorder__")) = V::inst(rec);
    return V::inst(f);
}

void install_atlases(Match& G) {
    auto fill = [&](V& target, const char* atlas, const char* prefix) {
        V d = V::dict();
        auto it = g_index.find(atlas);
        if (it != g_index.end())
            for (auto& [k, e] : it->second) if(k.rfind("@native-scale-source/",0)!=0) d.at(V(k)) = make_image(std::string(prefix) + k, e.w, e.h);
        target = d;
    };
    fill(G.图集, "图集", "world:");
    fill(G.ui图集, "ui图集", "ui:");
    fill(G.背景图集, "背景图集", "bg:");
    fill(G.近景图集, "近景图集", "near:");
}

V install_graphics(Match& G, int tile) {
    V pg = G.pygame;
    auto* f = as<PygameFacade>(pg);
    if (!f) { pg = make_pygame(); f = as<PygameFacade>(pg); }
    V recv = f->members.get(V("__recorder__"));
    as<Recorder>(recv)->tile_v = V(tile);
    V metrics=f->members.get(V("__graphics_metrics__"));
    for(V* atlas:{&G.图集,&G.ui图集,&G.背景图集,&G.近景图集})if(atlas->is_dict())for(const auto& entry:atlas->kv())if(Image* image=image_of(entry.second))attach_metrics(image,metrics);
    // Match-specific pixel assets must be the recording namespace's real
    // replay sources as well as the image's local cached pixels.
    V loaded_sources=metrics.get(V("loaded_sources"));
    for(V* atlas:{&G.图集,&G.ui图集,&G.背景图集,&G.近景图集})if(atlas->is_dict())for(const auto& entry:atlas->kv())if(Image* image=image_of(entry.second))if(V* cached=image->find_dyn(Sym("__materialized_pixels__")))loaded_sources.at(V(image->r.key))=callm(*cached,Sym("copy"),Args{});
    G.图集=pm_expansion_assets::cls_TemplateAtlas().call(Args{G.图集});
    G.pygame = pg;
    G.screen = recv;
    G.摄像机 = V::nums({0, 0});
    G.抖屏 = V::nums({0, 0, 0});
    G.补帧 = V(0.0);
    G.不显 = V::func([](const Args&) { return V(false); });
    // Register real PNG pixels returned by the original isolated IO helpers.
    // These source Surfaces stay local; only the explicit asset key enters JSON.
    for(V* slot:{&G.加载图,&G.加载原图}) {
        V original=*slot;
        *slot=V::func([original,metrics](const Args& args) mutable {
            V pixels=original.call(args);if(image_of(pixels))return pixels;
            int w=int(callm(pixels,Sym("get_width"),Args{}).num()),h=int(callm(pixels,Sym("get_height"),Args{}).num());
            std::string key="world:@load/"+py::str(args.pos.at(0)).str()+"/"+std::to_string(w)+"x"+std::to_string(h);
            V output=make_image(key,w,h);Image* image=image_of(output);attach_metrics(image,metrics);
            V alpha=callm(pixels,Sym("get_alpha"),Args{});image->r.alpha=alpha.is_none()?-2:int(alpha.num());
            image->r.pixel_alpha=(int(callm(pixels,Sym("get_flags"),Args{}).num())&65536)!=0;
            image->r.colorkey=pm_native_animation::f__plain(Args{callm(pixels,Sym("get_colorkey"),Args{})});
            V source_copy=callm(pixels,Sym("copy"),Args{}),image_copy=callm(pixels,Sym("copy"),Args{});
            V loaded=metrics.get(V("loaded_sources"));loaded.at(V(key))=source_copy;image->setattr(Sym("__materialized_pixels__"),image_copy);
            metrics.at(V("copies"))=metrics.get(V("copies"),V(0))+V(2);
            metrics.at(V("copy_bytes"))=metrics.get(V("copy_bytes"),V(0))+V(2)*callm(pixels,Sym("get_pitch"),Args{})*callm(pixels,Sym("get_height"),Args{});
            return output;
        });
    }
    (void)tile;
    return recv;
}

}  // namespace pvz::gfx
