// pygame.font over SDL_ttf.
#include "pg/pg.h"
#include "core/fsutil.h"
#include "core/resource_paths.h"
#include <SDL_ttf.h>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <map>

namespace pvz::pg {
namespace {

bool g_font_init = false;

// font search: an explicit file, the bundled fonts/ folder, then the system font folders
std::string fonts_dir_windows() {
    std::string w;
    if (!env_u8("WINDIR", w)) w = "C:/Windows";
    return w + "/Fonts";
}
std::string find_font_file(const std::string& name) {
    static const std::map<std::string, std::vector<std::string>> known = {
        {"microsoftyahei", {"msyh.ttc", "msyh.ttf"}}, {"simhei", {"simhei.ttf"}}, {"arial", {"arial.ttf"}},
        {"notosanscjk", {"NotoSansCJK-Regular.ttc", "NotoSansSC-Regular.otf"}}, {"simsun", {"simsun.ttc"}},
        {"freesansbold", {"freesansbold.ttf"}}, {"consolas", {"consola.ttf"}}, {"segoeui", {"segoeui.ttf"}}};
    std::vector<std::string> dirs = {"fonts", fonts_dir_windows(), "/system/fonts", "/usr/share/fonts/truetype"};
    auto it = known.find(name);
    std::vector<std::string> files = it != known.end() ? it->second : std::vector<std::string>{name + ".ttf", name + ".ttc", name + ".otf"};
    for (auto& d : dirs)
        for (auto& f : files) {
            std::error_code ec;
            if (std::filesystem::exists(u8p(d + "/" + f), ec)) return d + "/" + f;
        }
    return "";
}
std::string default_font_file() {
    for (const char* n : {"cjk", "microsoftyahei", "simhei", "notosanscjk", "arial"}) {
        std::string f = n == std::string("cjk") ? (std::filesystem::exists(u8p("fonts/cjk.ttf")) ? std::string("fonts/cjk.ttf") : "") : find_font_file(n);
        if (!f.empty()) return f;
    }
    return "";
}
std::string bundled_default_font() {
    for (const auto& base : {std::filesystem::path("."), native_executable_directory(), native_workspace()}) {
        auto file = base / "fonts" / "freesansbold.ttf";
        std::error_code ec;
        if (std::filesystem::is_regular_file(file, ec)) return p8(file);
    }
    throw PyError("FileNotFoundError", "bundled default font freesansbold.ttf not found");
}
std::string normalize(std::string s) {
    std::string o;
    for (char c : s) if (c != ' ' && c != '_' && c != '-') o += char(std::tolower(static_cast<unsigned char>(c)));
    return o;
}
std::string match_font(const V& names) {
    std::vector<std::string> list;
    if (names.t == V::STR) {
        std::string s = names.str(), cur;
        for (char c : s) { if (c == ',') { list.push_back(cur); cur.clear(); } else cur += c; }
        list.push_back(cur);
    } else if (names.is_list()) {
        for (auto& n : names.items()) list.push_back(n.str());
    }
    for (auto& n : list) { std::string f = find_font_file(normalize(n)); if (!f.empty()) return f; }
    return "";
}

std::string path_str(const V& v) {
    if (v.t == V::STR) return v.str();
    return py_str(v);   // pathlib.Path -> its text
}

struct Font : PyObj {
    TTF_Font* f = nullptr;
    int size = 0;
    bool bold = false, italic = false, underline = false;
    ~Font() override { if (f && TTF_WasInit()) TTF_CloseFont(f); }
    const char* type_name() const override { return "Font"; }
    bool isa(const char* c) const override { return std::string(c) == "Font" || std::string(c) == "object"; }
    void apply_style() {
        int st = (bold ? TTF_STYLE_BOLD : 0) | (italic ? TTF_STYLE_ITALIC : 0) | (underline ? TTF_STYLE_UNDERLINE : 0);
        if (TTF_GetFontStyle(f) != st) TTF_SetFontStyle(f, st);
    }
    V method(Sym name) override {
        auto sp = std::static_pointer_cast<Font>(shared_from_this());
        return V::func([sp, name](const Args& a) { V out; if (!sp->call_method(name, a, out)) throw PyError("AttributeError", "Font." + name.str()); return out; });
    }
    bool call_method(Sym name, const Args& a, V& out) override {
        const std::string& n = name.str();
        if (n == "render") {
            V text = a.get(0, Sym("text"), nullptr, "render");
            std::string t = text.is_none() ? std::string() : (text.t == V::STR ? text.str() : py_str(text));
            bool aa = a.get(1, Sym("antialias"), nullptr, "render").truthy();
            SDL_Color fg = color_of(a.get(2, Sym("color"), nullptr, "render"));
            static const V none_v = V::none();
            V bgv = a.get(3, Sym("bgcolor"), &none_v);
            apply_style();
            static const V wrap_default(0);
            V wrap=a.get(4, Sym("wraplength"), &wrap_default);
            if (!wrap.is_num() || wrap.num()!=std::trunc(wrap.num())) throw PyError("TypeError","wraplength must be an integer");
            if (wrap.num()<0) throw PyError("ValueError","wraplength must be non-negative");
            if (wrap.num()>double(UINT32_MAX)) throw PyError("OverflowError","wraplength is too large");
            Uint32 wraplength=Uint32(wrap.num());
            if (t.empty()) {
                out = new_surface(0, TTF_FontHeight(f), bgv.is_none());
                if (!bgv.is_none()) { SDL_Color b = color_of(bgv); SDL_FillRect(surf(out)->s, nullptr, (uint32_t(255) << 24) | (b.r << 16) | (b.g << 8) | b.b); }
                return true;
            }
            SDL_Surface* r;
            if (!bgv.is_none()) {
                SDL_Color bg = color_of(bgv);
                r = aa ? TTF_RenderUTF8_Shaded_Wrapped(f, t.c_str(), fg, bg, wraplength) : TTF_RenderUTF8_Solid_Wrapped(f, t.c_str(), fg, wraplength);
                if (r && !aa) { SDL_SetColorKey(r,0,0); r->format->palette->colors[0]=bg; }
            } else {
                r = aa ? TTF_RenderUTF8_Blended_Wrapped(f, t.c_str(), fg, wraplength) : TTF_RenderUTF8_Solid_Wrapped(f, t.c_str(), fg, wraplength);
            }
            if (!r) throw PyError("error", std::string("text render failed: ") + TTF_GetError());
            SDL_Surface* c = SDL_ConvertSurfaceFormat(r, SDL_PIXELFORMAT_ARGB8888, 0);
            SDL_FreeSurface(r);
            if (!c) throw PyError("error", SDL_GetError());
            SDL_SetSurfaceBlendMode(c, SDL_BLENDMODE_NONE);
            bool alpha = bgv.is_none();
            if (!alpha) {   // shaded / opaque: force alpha 255
                for (int y = 0; y < c->h; ++y) { auto* p = reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(c->pixels) + size_t(y) * c->pitch); for (int x = 0; x < c->w; ++x) p[x] |= 0xFF000000u; }
            } else if (!aa) {   // Solid renders a palette surface with a colour key: converted, key pixels must become transparent
                // (SDL_ConvertSurfaceFormat keeps alpha 0 for keyed pixels only with blending set up; normalise)
            }
            out = wrap_surface(c, alpha);
            return true;
        }
        if (n == "size") {
            V text = a.pos.at(0);
            std::string t = text.t == V::STR ? text.str() : py_str(text);
            apply_style();
            int w = 0, h = 0;
            if (t.empty()) h = TTF_FontHeight(f); else TTF_SizeUTF8(f, t.c_str(), &w, &h);
            out = V::tuple({V(double(w)), V(double(h))});
            return true;
        }
        if (n == "get_linesize") { out = V(double(TTF_FontLineSkip(f))); return true; }
        if (n == "get_height") { out = V(double(TTF_FontHeight(f))); return true; }
        if (n == "get_ascent") { out = V(double(TTF_FontAscent(f))); return true; }
        if (n == "get_descent") { out = V(double(TTF_FontDescent(f))); return true; }
        if (n == "set_bold") { bold = a.pos.at(0).truthy(); out = V::none(); return true; }
        if (n == "get_bold") { out = V(bold); return true; }
        if (n == "set_italic") { italic = a.pos.at(0).truthy(); out = V::none(); return true; }
        if (n == "get_italic") { out = V(italic); return true; }
        if (n == "set_underline") { underline = a.pos.at(0).truthy(); out = V::none(); return true; }
        if (n == "get_underline") { out = V(underline); return true; }
        if (n == "metrics") {
            std::string t = a.pos.at(0).str();
            std::vector<V> res;
            size_t i = 0;
            while (i < t.size()) {   // per code point
                unsigned char c0 = static_cast<unsigned char>(t[i]);
                uint32_t cp; int len;
                if (c0 < 0x80) { cp = c0; len = 1; }
                else if (c0 < 0xE0) { cp = c0 & 0x1F; len = 2; }
                else if (c0 < 0xF0) { cp = c0 & 0x0F; len = 3; }
                else { cp = c0 & 0x07; len = 4; }
                for (int k = 1; k < len && i + k < t.size(); ++k) cp = (cp << 6) | (static_cast<unsigned char>(t[i + k]) & 0x3F);
                i += size_t(len);
                int minx, maxx, miny, maxy, adv;
                if (TTF_GlyphMetrics32(f, cp, &minx, &maxx, &miny, &maxy, &adv) == 0)
                    res.push_back(V::tuple({V(double(minx)), V(double(maxx)), V(double(miny)), V(double(maxy)), V(double(adv))}));
                else res.push_back(V::none());
            }
            out = V::list(res);
            return true;
        }
        return false;
    }
};

V open_font(const std::string& file, int size) {
    if (!g_font_init) { TTF_Init(); g_font_init = true; }
    std::string f = file.empty() ? default_font_file() : file;
    if (f.empty()) throw PyError("FileNotFoundError", "no usable font file");
    auto p = std::make_shared<Font>();
    p->size = std::max(1, size);
    p->f = TTF_OpenFont(sdl_path(f).c_str(), p->size);
    if (!p->f) throw PyError("FileNotFoundError", "cannot open font " + f + ": " + TTF_GetError());
    return V::inst(p);
}

}  // namespace

V font_module() {
    static V m = [] {
        V mod = new_module("pygame.font");
        Module* md = module_of(mod);
        md->fn("init", [](const Args&) { if (!g_font_init) { TTF_Init(); g_font_init = true; } return V::none(); });
        md->fn("get_init", [](const Args&) { return V(g_font_init); });
        md->fn("quit", [](const Args&) { return V::none(); });   // fonts stay valid for the process lifetime
        md->fn("Font", [](const Args& a) {
            static const V none_v = V::none(), size20(20.0);
            V file = a.get(0, Sym("file"), &none_v);
            int size = int(a.get(1, Sym("size"), &size20).num());
            // pygame-ce 2.4.0 font.c: only None uses the bundled font's 11/16 size.
            if (file.is_none()) return open_font(bundled_default_font(), std::max(1, int(std::max(1, size) * .6875)));
            if (path_str(file) == "freesansbold.ttf" && !std::filesystem::exists(u8p(path_str(file))))
                return open_font(bundled_default_font(), size);
            return open_font(path_str(file), size);
        });
        md->fn("SysFont", [](const Args& a) {
            V names = a.pos.at(0);
            int size = int(a.get(1, Sym("size"), nullptr, "SysFont").num());
            static const V f(false);
            V font = open_font(match_font(names), size);
            if (a.get(2, Sym("bold"), &f).truthy()) as<Font>(font)->bold = true;
            if (a.get(3, Sym("italic"), &f).truthy()) as<Font>(font)->italic = true;
            return font;
        });
        md->fn("match_font", [](const Args& a) {
            std::string f = match_font(a.pos.at(0));
            return f.empty() ? V::none() : V(f);
        });
        md->fn("get_fonts", [](const Args&) { return V::list({V("microsoftyahei"), V("simhei"), V("arial")}); });
        md->fn("get_default_font", [](const Args&) { return V("freesansbold.ttf"); });
        return mod;
    }();
    return m;
}

}  // namespace pvz::pg
