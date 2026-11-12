// pygame display / event / key / mouse / time / mixer / scrap / image and the module object.
#include "pg/pg.h"
#include "core/fsutil.h"
#include "core/resource_paths.h"
#include "core/pyops.h"
#include "sim/pvp/pvprt.h"
#include <SDL_image.h>
#include <SDL_mixer.h>
#ifndef _WIN32
#include <unistd.h>
#endif
#include "core/gil.h"
#include <algorithm>
#include <cmath>
#include <deque>
#include <map>

namespace pvz::pg {
V joystick_module();
void joystick_init();
void joystick_quit();
int joystick_device_index(int);

// ------------------------------------------------------------------ module object
V new_module(const char* name) { auto p = std::make_shared<Module>(); p->name = name; return V::inst(p); }
Module* module_of(const V& m) { return as<Module>(m); }
std::string sdl_path(const std::string& p) {
    auto requested=u8p(p);
    if(requested.is_relative() && !std::filesystem::exists(requested)) {
        auto it=requested.begin();
        if(it!=requested.end() && (*it==u8p("图片") || *it==u8p("音效") || *it==u8p("音乐"))) {
            bool parent=false;for(const auto& part:requested)if(part=="..")parent=true;
            if(!parent) {auto bundled=native_image_directory().parent_path()/requested;if(std::filesystem::is_regular_file(bundled))return p8(bundled);}
        }
    }

#ifdef __ANDROID__
    if (!p.empty() && p[0] != '/') {
        char buf[4096];
        if (getcwd(buf, sizeof buf)) return std::string(buf) + "/" + p;
    }
#endif
    return p;
}

namespace {
int iv(const V& v) { return int(std::floor(v.num())); }
std::string path_str(const V& v) { return v.t == V::STR ? v.str() : py_str(v); }
V tup2(double a, double b) { return V::tuple({V(a), V(b)}); }

// ------------------------------------------------------------------ display
struct Display {
    SDL_Window* win = nullptr;
    SDL_Renderer* ren = nullptr;
    SDL_Texture* tex = nullptr;
    V screen;
    int lw = 0, lh = 0;
    int flags = 0;
    std::string caption = "pygame window", icon_caption = "pygame";
} g_disp;
bool g_inited = false;
Uint32 g_start_ticks = 0;

constexpr int F_FULLSCREEN = int(0x80000000u), F_RESIZABLE = 0x10, F_NOFRAME = 0x20, F_SCALED = 0x200, F_SRCALPHA = 0x10000;

void ensure_init() {
    if (g_inited) return;
    SDL_SetHint(SDL_HINT_IME_SHOW_UI, "1");
    SDL_SetHint(SDL_HINT_ALLOW_TOPMOST, "0");   // team_chat.enable_ime_ui (python sets it through ctypes)
#ifdef __ANDROID__
    SDL_SetHint(SDL_HINT_TOUCH_MOUSE_EVENTS, "0");   // the touch layer reads FINGER events (python: touch_hotfix guard)
    SDL_SetHint(SDL_HINT_ANDROID_TRAP_BACK_BUTTON, "1");
#endif
    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_TIMER | SDL_INIT_EVENTS);
    g_start_ticks = SDL_GetTicks();
    g_inited = true;
}

V set_mode(int w, int h, int flags) {
    ensure_init();
    if (w <= 0 || h <= 0) {
        SDL_DisplayMode dm;
        if (SDL_GetDesktopDisplayMode(0, &dm) == 0) { w = dm.w; h = dm.h; } else { w = 1280; h = 800; }
    }
    Uint32 wf = SDL_WINDOW_SHOWN | SDL_WINDOW_ALLOW_HIGHDPI;
    if (flags & F_RESIZABLE) wf |= SDL_WINDOW_RESIZABLE;
    if (flags & F_NOFRAME) wf |= SDL_WINDOW_BORDERLESS;
    if (!g_disp.win) {
        g_disp.win = SDL_CreateWindow(g_disp.caption.c_str(), SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, w, h, wf);
        if (!g_disp.win) throw PyError("error", std::string("cannot open window: ") + SDL_GetError());
        SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "1");
        g_disp.ren = SDL_CreateRenderer(g_disp.win, -1, SDL_RENDERER_ACCELERATED);
        if (!g_disp.ren) g_disp.ren = SDL_CreateRenderer(g_disp.win, -1, SDL_RENDERER_SOFTWARE);
    } else {
        SDL_SetWindowFullscreen(g_disp.win, 0);
        SDL_SetWindowBordered(g_disp.win, (flags & F_NOFRAME) ? SDL_FALSE : SDL_TRUE);
        SDL_SetWindowResizable(g_disp.win, (flags & F_RESIZABLE) ? SDL_TRUE : SDL_FALSE);
        SDL_SetWindowSize(g_disp.win, w, h);
    }
    if(!g_disp.ren){g_disp.ren=SDL_CreateRenderer(g_disp.win,-1,SDL_RENDERER_ACCELERATED);if(!g_disp.ren)g_disp.ren=SDL_CreateRenderer(g_disp.win,-1,SDL_RENDERER_SOFTWARE);if(!g_disp.ren)throw PyError("error",std::string("cannot create renderer: ")+SDL_GetError());}
    if (flags & F_FULLSCREEN) SDL_SetWindowFullscreen(g_disp.win, SDL_WINDOW_FULLSCREEN_DESKTOP);
    if (g_disp.tex) SDL_DestroyTexture(g_disp.tex);
    g_disp.tex = SDL_CreateTexture(g_disp.ren, SDL_PIXELFORMAT_ARGB8888, SDL_TEXTUREACCESS_STREAMING, w, h);
    SDL_RenderSetLogicalSize(g_disp.ren, w, h);
    g_disp.lw = w; g_disp.lh = h; g_disp.flags = flags;
    V next_screen=new_surface(w,h,false);
    if(g_disp.screen.t==V::INST && as<Surface>(g_disp.screen)) {
        // SDL/pygame's display Surface retains its identity when its mode changes.
        Surface* current=surf(g_disp.screen);Surface* next=surf(next_screen);
        std::swap(current->s,next->s);current->srcalpha=next->srcalpha;current->alpha=next->alpha;
        current->has_colorkey=false;current->colorkey=0;current->parent=V();current->off_x=current->off_y=0;
    } else g_disp.screen=next_screen;
    surf(g_disp.screen)->is_display=true;
    return g_disp.screen;
}

void map_mouse(int wx, int wy, int& lx, int& ly) {
    if (!g_disp.ren) { lx = wx; ly = wy; return; }
    float fx, fy;
    SDL_RenderWindowToLogical(g_disp.ren, wx, wy, &fx, &fy);
    lx = int(std::floor(fx)); ly = int(std::floor(fy));
}

// ------------------------------------------------------------------ events
constexpr int E_ACTIVEEVENT = 32768, E_VIDEORESIZE = 32769, E_VIDEOEXPOSE = 32770, E_USEREVENT = 32866;
constexpr int E_WINDOWSHOWN = 32774, E_WINDOWHIDDEN = 32775, E_WINDOWEXPOSED = 32776, E_WINDOWMOVED = 32777,
              E_WINDOWRESIZED = 32778, E_WINDOWSIZECHANGED = 32779, E_WINDOWMINIMIZED = 32780, E_WINDOWMAXIMIZED = 32781,
              E_WINDOWRESTORED = 32782, E_WINDOWENTER = 32783, E_WINDOWLEAVE = 32784, E_WINDOWFOCUSGAINED = 32785,
              E_WINDOWFOCUSLOST = 32786, E_WINDOWCLOSE = 32787;

struct Event : PyObj {
    int type = 0;
    V d = V::dict();
    const char* type_name() const override { return "Event"; }
    bool isa(const char* c) const override { return std::string(c) == "Event" || std::string(c) == "EventType" || std::string(c) == "object"; }
    V property(Sym n, bool& found) override {
        found = true;
        if (n == Sym("type")) return V(double(type));
        if (n == Sym("dict") || n == Sym("__dict__")) return d;
        const V* v = d.find(V(n));
        if (v && v->has()) return *v;
        found = false;
        return V();
    }
    bool set_property(Sym n, const V& v) override { if (n == Sym("type")) return false; d.at(V(n)) = v; return true; }
};
V make_event(int type, V d = V()) {
    auto e = std::make_shared<Event>();
    e->type = type;
    if (d.has() && d.is_dict()) e->d = d;
    return V::inst(e);
}
void set(V& ev, const char* k, V v) { as<Event>(ev)->d.at(V(k)) = std::move(v); }

std::deque<V> g_posted;
int g_repeat_delay = 0, g_repeat_interval = 0;
std::map<int, bool> g_blocked;

std::string key_unicode(SDL_Keycode k, Uint16 mod) {
    if (mod & (KMOD_CTRL | KMOD_ALT | KMOD_GUI)) return "";
    if (k == SDLK_RETURN || k == SDLK_KP_ENTER) return "\r";
    if (k == SDLK_TAB) return "\t";
    if (k == SDLK_BACKSPACE) return "\b";
    if (k == SDLK_ESCAPE) return "\x1b";
    if (k < 32 || k >= 127) return "";
    char c = char(k);
    bool shift = (mod & KMOD_SHIFT) != 0, caps = (mod & KMOD_CAPS) != 0;
    if (c >= 'a' && c <= 'z') { if (shift != caps) c = char(c - 32); return std::string(1, c); }
    if (shift) {
        static const char* from = "1234567890-=[]\\;',./`";
        static const char* to = "!@#$%^&*()_+{}|:\"<>?~";
        for (int i = 0; from[i]; ++i) if (from[i] == c) return std::string(1, to[i]);
    }
    return std::string(1, c);
}

void push_converted(const SDL_Event& e, std::vector<V>& out) {
    switch (e.type) {
        case SDL_QUIT: out.push_back(make_event(SDL_QUIT)); break;
        // Application already handles these no-payload SDL notifications.
        // Preserve them so background cancels captured input and the display
        // backend can revalidate after foreground or renderer loss.
        case SDL_APP_WILLENTERBACKGROUND:
        case SDL_APP_DIDENTERBACKGROUND:
        case SDL_APP_WILLENTERFOREGROUND:
        case SDL_APP_DIDENTERFOREGROUND:
        case SDL_RENDER_TARGETS_RESET:
        case SDL_RENDER_DEVICE_RESET:
            out.push_back(make_event(e.type)); break;
        case SDL_KEYDOWN: case SDL_KEYUP: {
            if (e.key.repeat && e.type == SDL_KEYDOWN && g_repeat_delay == 0) break;   // pygame: no key repeat unless set_repeat
            V ev = make_event(e.type);
            set(ev, "key", V(double(e.key.keysym.sym)));
            set(ev, "mod", V(double(e.key.keysym.mod)));
            set(ev, "scancode", V(double(e.key.keysym.scancode)));
            set(ev, "unicode", V(e.type == SDL_KEYDOWN ? key_unicode(e.key.keysym.sym, e.key.keysym.mod) : std::string()));
            set(ev, "window", V::none());
            out.push_back(ev);
            break;
        }
        case SDL_TEXTINPUT: { V ev = make_event(SDL_TEXTINPUT); set(ev, "text", V(std::string(e.text.text))); set(ev, "window", V::none()); out.push_back(ev); break; }
        case SDL_TEXTEDITING: {
            V ev = make_event(SDL_TEXTEDITING);
            set(ev, "text", V(std::string(e.edit.text))); set(ev, "start", V(double(e.edit.start))); set(ev, "length", V(double(e.edit.length)));
            out.push_back(ev);
            break;
        }
        case SDL_MOUSEMOTION: {
            V ev = make_event(SDL_MOUSEMOTION);
            set(ev, "pos", tup2(e.motion.x, e.motion.y));
            set(ev, "rel", tup2(e.motion.xrel, e.motion.yrel));
            Uint32 b = e.motion.state;
            set(ev, "buttons", V::tuple({V(double((b & SDL_BUTTON_LMASK) ? 1 : 0)), V(double((b & SDL_BUTTON_MMASK) ? 1 : 0)), V(double((b & SDL_BUTTON_RMASK) ? 1 : 0))}));
            set(ev, "touch", V(e.motion.which == SDL_TOUCH_MOUSEID));
            set(ev, "window", V::none());
            out.push_back(ev);
            break;
        }
        case SDL_MOUSEBUTTONDOWN: case SDL_MOUSEBUTTONUP: {
            V ev = make_event(e.type);
            set(ev, "pos", tup2(e.button.x, e.button.y));
            set(ev, "button", V(double(e.button.button)));
            set(ev, "touch", V(e.button.which == SDL_TOUCH_MOUSEID));
            set(ev, "window", V::none());
            out.push_back(ev);
            break;
        }
        case SDL_MOUSEWHEEL: {
            V ev = make_event(SDL_MOUSEWHEEL);
            int y = e.wheel.direction == SDL_MOUSEWHEEL_FLIPPED ? -e.wheel.y : e.wheel.y;
            set(ev, "x", V(double(e.wheel.x))); set(ev, "y", V(double(y)));
            set(ev, "precise_x", V(double(e.wheel.preciseX))); set(ev, "precise_y", V(double(e.wheel.preciseY)));
            set(ev, "flipped", V(e.wheel.direction == SDL_MOUSEWHEEL_FLIPPED)); set(ev, "touch", V(false)); set(ev, "window", V::none());
            out.push_back(ev);
            // pygame 2 also reports the legacy wheel buttons 4 / 5
            int mx, my; SDL_GetMouseState(&mx, &my); int lx, ly; map_mouse(mx, my, lx, ly);
            if (y != 0) {
                for (int t : {SDL_MOUSEBUTTONDOWN, SDL_MOUSEBUTTONUP}) {
                    V b = make_event(t);
                    set(b, "pos", tup2(lx, ly)); set(b, "button", V(y > 0 ? 4.0 : 5.0)); set(b, "touch", V(false)); set(b, "window", V::none());
                    out.push_back(b);
                }
            }
            break;
        }
        case SDL_JOYAXISMOTION: case SDL_JOYBALLMOTION: case SDL_JOYHATMOTION:
        case SDL_JOYBUTTONDOWN: case SDL_JOYBUTTONUP: {
            V ev=make_event(e.type);int instance=e.jaxis.which;
            set(ev,"joy",V(joystick_device_index(instance)));set(ev,"instance_id",V(instance));
            if(e.type==SDL_JOYAXISMOTION) {set(ev,"axis",V(int(e.jaxis.axis)));set(ev,"value",V(e.jaxis.value/32767.0));}
            else if(e.type==SDL_JOYBALLMOTION) {set(ev,"ball",V(int(e.jball.ball)));set(ev,"rel",tup2(e.jball.xrel,e.jball.yrel));}
            else if(e.type==SDL_JOYHATMOTION) {int v=e.jhat.value;set(ev,"hat",V(int(e.jhat.hat)));set(ev,"value",tup2(v&SDL_HAT_RIGHT?1:(v&SDL_HAT_LEFT?-1:0),v&SDL_HAT_UP?1:(v&SDL_HAT_DOWN?-1:0)));}
            else set(ev,"button",V(int(e.jbutton.button)));
            out.push_back(ev);break;
        }
        case SDL_JOYDEVICEADDED: case SDL_JOYDEVICEREMOVED: {
            V ev=make_event(e.type);
            if(e.type==SDL_JOYDEVICEADDED) {
                set(ev,"device_index",V(e.jdevice.which));char guid[33];
                SDL_JoystickGetGUIDString(SDL_JoystickGetDeviceGUID(e.jdevice.which),guid,sizeof guid);set(ev,"guid",V(guid));
            } else set(ev,"instance_id",V(e.jdevice.which));
            out.push_back(ev);break;
        }
        case SDL_FINGERDOWN: case SDL_FINGERUP: case SDL_FINGERMOTION: {
            V ev = make_event(e.type);
            set(ev, "touch_id", V(double(e.tfinger.touchId))); set(ev, "finger_id", V(double(e.tfinger.fingerId)));
            set(ev, "x", V(double(e.tfinger.x))); set(ev, "y", V(double(e.tfinger.y)));
            set(ev, "dx", V(double(e.tfinger.dx))); set(ev, "dy", V(double(e.tfinger.dy)));
            set(ev, "pressure", V(double(e.tfinger.pressure)));
            out.push_back(ev);
            break;
        }
        case SDL_WINDOWEVENT: {
            int t = 0;
            switch (e.window.event) {
                case SDL_WINDOWEVENT_SHOWN: t = E_WINDOWSHOWN; break;
                case SDL_WINDOWEVENT_HIDDEN: t = E_WINDOWHIDDEN; break;
                case SDL_WINDOWEVENT_EXPOSED: t = E_WINDOWEXPOSED; out.push_back(make_event(E_VIDEOEXPOSE)); break;
                case SDL_WINDOWEVENT_MOVED: t = E_WINDOWMOVED; break;
                case SDL_WINDOWEVENT_RESIZED: t = E_WINDOWRESIZED; break;
                case SDL_WINDOWEVENT_SIZE_CHANGED: t = E_WINDOWSIZECHANGED; break;
                case SDL_WINDOWEVENT_MINIMIZED: t = E_WINDOWMINIMIZED; break;
                case SDL_WINDOWEVENT_MAXIMIZED: t = E_WINDOWMAXIMIZED; break;
                case SDL_WINDOWEVENT_RESTORED: t = E_WINDOWRESTORED; break;
                case SDL_WINDOWEVENT_ENTER: t = E_WINDOWENTER; break;
                case SDL_WINDOWEVENT_LEAVE: t = E_WINDOWLEAVE; break;
                case SDL_WINDOWEVENT_FOCUS_GAINED: t = E_WINDOWFOCUSGAINED; break;
                case SDL_WINDOWEVENT_FOCUS_LOST: t = E_WINDOWFOCUSLOST; break;
                case SDL_WINDOWEVENT_CLOSE: t = E_WINDOWCLOSE; break;
                default: break;
            }
            if (e.window.event == SDL_WINDOWEVENT_FOCUS_GAINED || e.window.event == SDL_WINDOWEVENT_FOCUS_LOST) {
                V a = make_event(E_ACTIVEEVENT);
                set(a, "gain", V(e.window.event == SDL_WINDOWEVENT_FOCUS_GAINED ? 1.0 : 0.0)); set(a, "state", V(2.0));
                out.push_back(a);
            }
            if (e.window.event == SDL_WINDOWEVENT_RESIZED) {
                V r = make_event(E_VIDEORESIZE);
                set(r, "size", tup2(e.window.data1, e.window.data2)); set(r, "w", V(double(e.window.data1))); set(r, "h", V(double(e.window.data2)));
                out.push_back(r);
            }
            if (t) {
                V ev = make_event(t);
                if (t == E_WINDOWRESIZED || t == E_WINDOWSIZECHANGED || t == E_WINDOWMOVED) { set(ev, "x", V(double(e.window.data1))); set(ev, "y", V(double(e.window.data2))); }
                set(ev, "window", V::none());
                out.push_back(ev);
            }
            break;
        }
        default: break;
    }
}

std::vector<V> pump_all() {
    ensure_init();
    std::vector<V> out;
    while (!g_posted.empty()) { out.push_back(g_posted.front()); g_posted.pop_front(); }
    SDL_Event e;
    while (SDL_PollEvent(&e)) push_converted(e, out);
    std::vector<V> kept;
    for (auto& ev : out) if (!g_blocked[as<Event>(ev)->type]) kept.push_back(ev);
    return kept;
}

bool type_matches(int type, const V& filter) {
    if (filter.is_none() || !filter.has()) return true;
    if (filter.is_list()) { for (auto& t : filter.items()) if (int(t.num()) == type) return true; return false; }
    return int(filter.num()) == type;
}

const char* event_name(int t) {
    switch (t) {
        case SDL_QUIT: return "Quit"; case SDL_KEYDOWN: return "KeyDown"; case SDL_KEYUP: return "KeyUp";
        case SDL_TEXTINPUT: return "TextInput"; case SDL_TEXTEDITING: return "TextEditing";
        case SDL_MOUSEMOTION: return "MouseMotion"; case SDL_MOUSEBUTTONDOWN: return "MouseButtonDown"; case SDL_MOUSEBUTTONUP: return "MouseButtonUp";
        case SDL_MOUSEWHEEL: return "MouseWheel"; case E_ACTIVEEVENT: return "ActiveEvent"; case E_VIDEORESIZE: return "VideoResize";
        case E_VIDEOEXPOSE: return "VideoExpose"; case SDL_FINGERDOWN: return "FingerDown"; case SDL_FINGERUP: return "FingerUp";
        case SDL_FINGERMOTION: return "FingerMotion"; case E_WINDOWFOCUSLOST: return "WindowFocusLost"; case E_WINDOWFOCUSGAINED: return "WindowFocusGained";
        case E_WINDOWSHOWN: return "WindowShown";
        case E_WINDOWHIDDEN: return "WindowHidden";
        case E_WINDOWEXPOSED: return "WindowExposed";
        case E_WINDOWMOVED: return "WindowMoved";
        case E_WINDOWRESIZED: return "WindowResized";
        case E_WINDOWSIZECHANGED: return "WindowSizeChanged";
        case E_WINDOWMINIMIZED: return "WindowMinimized";
        case E_WINDOWMAXIMIZED: return "WindowMaximized";
        case E_WINDOWRESTORED: return "WindowRestored";
        case E_WINDOWENTER: return "WindowEnter";
        case E_WINDOWLEAVE: return "WindowLeave";
        case E_WINDOWCLOSE: return "WindowClose";
        case SDL_JOYAXISMOTION: return "JoyAxisMotion";
        case SDL_JOYBALLMOTION: return "JoyBallMotion";
        case SDL_JOYHATMOTION: return "JoyHatMotion";
        case SDL_JOYBUTTONDOWN: return "JoyButtonDown";
        case SDL_JOYBUTTONUP: return "JoyButtonUp";
        case SDL_JOYDEVICEADDED: return "JoyDeviceAdded";
        case SDL_JOYDEVICEREMOVED: return "JoyDeviceRemoved";
        default: return t >= E_USEREVENT ? "UserEvent" : "Unknown";
    }
}

// ------------------------------------------------------------------ key state
struct Pressed : PyObj {
    const char* type_name() const override { return "ScancodeWrapper"; }
    V getitem(const V& k) override {
        int n = 0;
        const Uint8* st = SDL_GetKeyboardState(&n);
        int code = int(k.num());
        SDL_Scancode sc = code < 512 && code >= 0 && code != ' ' && (code < 'a' || code > 'z') && (code < '0' || code > '9') && code > 127
            ? SDL_Scancode(code) : SDL_GetScancodeFromKey(SDL_Keycode(code));
        return V(sc >= 0 && sc < n && st[sc] != 0);
    }
    size_t length() override { int n = 0; SDL_GetKeyboardState(&n); return size_t(n); }
};

// ------------------------------------------------------------------ time
struct Clock : PyObj {
    Uint32 last = 0;
    std::deque<Uint32> frames;
    int raw = 0, time_ms = 0;
    const char* type_name() const override { return "Clock"; }
    bool call_method(Sym name, const Args& a, V& out) override {
        const std::string& n = name.str();
        if (n == "tick" || n == "tick_busy_loop") {
            double fps = a.pos.empty() ? 0 : a.pos[0].num();
            Uint32 now = SDL_GetTicks();
            if (!last) last = now;
            raw = int(now - last);
            if (fps > 0) {
                int target = int(1000.0 / fps);
                if (raw < target) { gil::Release g_; SDL_Delay(Uint32(target - raw)); now = SDL_GetTicks(); }
            }
            gil::yield_if_waiting();
            time_ms = int(now - last);
            last = now;
            frames.push_back(Uint32(time_ms));
            if (frames.size() > 10) frames.pop_front();
            out = V(double(time_ms));
            return true;
        }
        if (n == "get_fps") {
            double tot = 0; for (auto f : frames) tot += f;
            out = V(tot > 0 ? 1000.0 * frames.size() / tot : 0.0);
            return true;
        }
        if (n == "get_time") { out = V(double(time_ms)); return true; }
        if (n == "get_rawtime") { out = V(double(raw)); return true; }
        return false;
    }
    V method(Sym name) override {
        auto sp = std::static_pointer_cast<Clock>(shared_from_this());
        return V::func([sp, name](const Args& a) { V out; if (!sp->call_method(name, a, out)) throw PyError("AttributeError", "Clock." + name.str()); return out; });
    }
};

// ------------------------------------------------------------------ mixer
bool g_mixer = false;
int g_channels = 8;

bool open_mixer(int frequency,int channels,int buffer) {
    auto open=[&] {
        if(Mix_OpenAudio(frequency,MIX_DEFAULT_FORMAT,channels,buffer)!=0)return false;
        Mix_Init(MIX_INIT_OGG|MIX_INIT_MP3);g_mixer=true;Mix_AllocateChannels(g_channels);
        SDL_Log("pvz: audio ready (driver=%s)",SDL_GetCurrentAudioDriver()?SDL_GetCurrentAudioDriver():"unknown");
        return true;
    };
    if(open())return true;
    std::string reason=Mix_GetError();
#ifdef __ANDROID__
    // Try only compiled backends and respect an explicit driver override.
    // No device is open here; do not tear down a healthy music stream.
    if(!std::getenv("SDL_AUDIODRIVER")) {
        for(const char* driver:{"android","openslES"}) {
            const char* current=SDL_GetCurrentAudioDriver();
            if(current && std::string(current)==driver)continue;
            bool available=false;
            for(int i=0;i<SDL_GetNumAudioDrivers();++i)if(std::string(SDL_GetAudioDriver(i))==driver)available=true;
            if(!available)continue;
            SDL_AudioQuit();
            if(SDL_AudioInit(driver)==0 && open())return true;
            reason+=std::string("; ")+driver+": "+SDL_GetError();
        }
    }
#endif
    SDL_LogError(SDL_LOG_CATEGORY_AUDIO,"pvz: audio initialization failed: %s",reason.c_str());
    SDL_SetError("%s",reason.c_str());return false;
}

struct Sound : PyObj {
    Mix_Chunk* c = nullptr;
    std::string raw;   // Sound(buffer=...): raw samples in the mixer format (Mix_QuickLoad_RAW keeps a pointer)
    ~Sound() override { if (c && g_mixer) Mix_FreeChunk(c); }
    const char* type_name() const override { return "Sound"; }
    bool call_method(Sym name, const Args& a, V& out);
    V method(Sym name) override {
        auto sp = std::static_pointer_cast<Sound>(shared_from_this());
        return V::func([sp, name](const Args& a) { V out; if (!sp->call_method(name, a, out)) throw PyError("AttributeError", "Sound." + name.str()); return out; });
    }
};
std::map<int, V>& chan_sound() { static std::map<int, V> m; return m; }   // Channel.get_sound
struct Channel : PyObj {
    int id = 0;
    const char* type_name() const override { return "Channel"; }
    bool call_method(Sym name, const Args& a, V& out) override {
        const std::string& n = name.str();
        if (!g_mixer) { out = n == "get_busy" ? V(false) : V::none(); return true; }
        if (n == "play") {
            auto* s = as<Sound>(a.pos.at(0));
            static const V zero(0.0);
            int loops = int(a.get(1, Sym("loops"), &zero).num());
            if (s && s->c) { Mix_PlayChannel(id, s->c, loops); chan_sound()[id] = a.pos.at(0); }
            out = V::none();
            return true;
        }
        if (n == "stop") { Mix_HaltChannel(id); out = V::none(); return true; }
        if (n == "pause") { Mix_Pause(id); out = V::none(); return true; }
        if (n == "unpause") { Mix_Resume(id); out = V::none(); return true; }
        if (n == "fadeout") { Mix_FadeOutChannel(id, int(a.pos.at(0).num())); out = V::none(); return true; }
        if (n == "set_volume") {
            double l = a.pos.at(0).num();
            if (a.pos.size() > 1) { double r = a.pos[1].num(); Mix_SetPanning(id, Uint8(std::clamp(l, 0.0, 1.0) * 255), Uint8(std::clamp(r, 0.0, 1.0) * 255)); Mix_Volume(id, MIX_MAX_VOLUME); }
            else Mix_Volume(id, int(std::clamp(l, 0.0, 1.0) * MIX_MAX_VOLUME));
            out = V::none();
            return true;
        }
        if (n == "get_volume") { out = V(Mix_Volume(id, -1) / double(MIX_MAX_VOLUME)); return true; }
        if (n == "get_busy") { out = V(Mix_Playing(id) != 0); return true; }
        if (n == "get_sound") { auto it = chan_sound().find(id); out = (Mix_Playing(id) && it != chan_sound().end()) ? it->second : V::none(); return true; }
        if (n == "queue") { auto* s = as<Sound>(a.pos.at(0)); if (s && s->c && !Mix_Playing(id)) Mix_PlayChannel(id, s->c, 0); out = V::none(); return true; }
        return false;
    }
    V method(Sym name) override {
        auto sp = std::static_pointer_cast<Channel>(shared_from_this());
        return V::func([sp, name](const Args& a) { V out; if (!sp->call_method(name, a, out)) throw PyError("AttributeError", "Channel." + name.str()); return out; });
    }
};
V channel(int id) { auto c = std::make_shared<Channel>(); c->id = id; return V::inst(c); }

bool Sound::call_method(Sym name, const Args& a, V& out) {
    const std::string& n = name.str();
    if (n == "play") {
        static const V zero(0.0);
        int loops = int(a.get(0, Sym("loops"), &zero).num());
        int maxtime = int(a.get(1, Sym("maxtime"), &zero).num());
        int fade = int(a.get(2, Sym("fade_ms"), &zero).num());
        if (!g_mixer || !c) { out = V::none(); return true; }
        int ch = fade > 0 ? Mix_FadeInChannelTimed(-1, c, loops, fade, maxtime > 0 ? maxtime : -1)
                          : Mix_PlayChannelTimed(-1, c, loops, maxtime > 0 ? maxtime : -1);
        if (ch >= 0) chan_sound()[ch] = self();
        out = ch < 0 ? V::none() : channel(ch);
        return true;
    }
    if (n == "stop") { if (g_mixer && c) for (int i = 0; i < g_channels; ++i) if (Mix_GetChunk(i) == c && Mix_Playing(i)) Mix_HaltChannel(i); out = V::none(); return true; }
    if (n == "fadeout") { if (g_mixer && c) for (int i = 0; i < g_channels; ++i) if (Mix_GetChunk(i) == c && Mix_Playing(i)) Mix_FadeOutChannel(i, int(a.pos.at(0).num())); out = V::none(); return true; }
    if (n == "set_volume") { if (c) Mix_VolumeChunk(c, int(std::clamp(a.pos.at(0).num(), 0.0, 1.0) * MIX_MAX_VOLUME)); out = V::none(); return true; }
    if (n == "get_volume") { out = V(c ? Mix_VolumeChunk(c, -1) / double(MIX_MAX_VOLUME) : 0.0); return true; }
    if (n == "get_length") {
        int freq = 44100, ch = 2; Uint16 fmt = AUDIO_S16;
        if (g_mixer) Mix_QuerySpec(&freq, &fmt, &ch);
        double bytes_per = (SDL_AUDIO_BITSIZE(fmt) / 8.0) * ch;
        out = V(c ? c->alen / bytes_per / freq : 0.0);
        return true;
    }
    if (n == "get_num_channels") {
        int k = 0; if (g_mixer && c) for (int i = 0; i < g_channels; ++i) if (Mix_GetChunk(i) == c && Mix_Playing(i)) ++k;
        out = V(double(k));
        return true;
    }
    return false;
}

Mix_Music* g_music = nullptr;
double g_music_volume = 1.0;

std::string bytes_of(const V& v);   // BytesIO / bytes / str payload

V load_image(const V& src) {
    ensure_init();
    static bool img = false;
    if (!img) { IMG_Init(IMG_INIT_PNG | IMG_INIT_JPG); img = true; }
    SDL_Surface* raw;
    if (src.t == V::STR || (src.t == V::INST && src.box->inst->type_name() == std::string("Path"))) {
        std::string p = path_str(src);
        SDL_RWops* rw = SDL_RWFromFile(sdl_path(p).c_str(), "rb");
        if (!rw) throw PyError("FileNotFoundError", "No file '" + p + "' found in working directory");
        raw = IMG_Load_RW(rw, 1);
    } else {
        std::string data = bytes_of(src);
        raw = IMG_Load_RW(SDL_RWFromConstMem(data.data(), int(data.size())), 1);
    }
    if (!raw) throw PyError("error", std::string("image load failed: ") + IMG_GetError());
    bool alpha = SDL_ISPIXELFORMAT_ALPHA(raw->format->format) || raw->format->palette != nullptr && SDL_HasColorKey(raw);
    SDL_Surface* c = SDL_ConvertSurfaceFormat(raw, SDL_PIXELFORMAT_ARGB8888, 0);
    bool keyed = SDL_HasColorKey(raw);
    Uint32 key = 0;
    if (keyed) SDL_GetColorKey(raw, &key);
    SDL_FreeSurface(raw);
    if (!c) throw PyError("error", SDL_GetError());
    SDL_SetSurfaceBlendMode(c, SDL_BLENDMODE_NONE);
    V out = wrap_surface(c, alpha);
    return out;
}

}  // namespace

// payload of io.BytesIO / bytes objects: the runtime keeps bytes as STR values
namespace { std::string bytes_of(const V& v) {
    if (v.t == V::STR) return v.str();
    if (v.t == V::INST) {
        V g = pvz::getattr(v, Sym("getvalue"), V());
        if (g.has()) return g.call(Args{}).str();
        V r = pvz::getattr(v, Sym("read"), V());
        if (r.has()) return r.call(Args{}).str();
    }
    throw PyError("TypeError", "expected a file name or a bytes buffer");
} }

SDL_Window* window() { return g_disp.win; }
uint32_t display_flags(){return uint32_t(g_disp.flags);}
SDL_Renderer* renderer(){return g_disp.ren;}
void release_renderer(){if(g_disp.tex){SDL_DestroyTexture(g_disp.tex);g_disp.tex=nullptr;}if(g_disp.ren){SDL_DestroyRenderer(g_disp.ren);g_disp.ren=nullptr;}}


void present() {
    if (!g_disp.win || !g_disp.screen.has()) return;
    Surface* s = surf(g_disp.screen);
    SDL_UpdateTexture(g_disp.tex, nullptr, s->s->pixels, s->s->pitch);
    SDL_SetRenderDrawColor(g_disp.ren, 0, 0, 0, 255);
    SDL_RenderClear(g_disp.ren);
    SDL_RenderCopy(g_disp.ren, g_disp.tex, nullptr, nullptr);
    { gil::Release g_; SDL_RenderPresent(g_disp.ren); }   // no vsync (pygame flip does not wait either; Clock.tick paces)
}

V display_module() {
    static V m = [] {
        V mod = new_module("pygame.display");
        Module* md = module_of(mod);
        md->fn("init", [](const Args&) { ensure_init(); return V::none(); });
        md->fn("quit", [](const Args&) { joystick_quit(); return V::none(); });
        md->fn("get_init", [](const Args&) { return V(g_inited); });
        md->fn("set_mode", [](const Args& a) {
            static const V zero_size = V::tuple({V(0.0), V(0.0)}), zero(0.0);
            V size = a.get(0, Sym("size"), &zero_size);
            return set_mode(iv(size.idx(0)), iv(size.idx(1)), int(int64_t(a.get(1, Sym("flags"), &zero).num())));
        });
        md->fn("get_surface", [](const Args&) { return g_disp.screen.has() ? g_disp.screen : V::none(); });
        md->fn("flip", [](const Args&) { present(); return V::none(); });
        md->fn("update", [](const Args&) { present(); return V::none(); });
        md->fn("set_caption", [](const Args& a) {
            g_disp.caption = a.pos.at(0).str();
            if (a.pos.size() > 1) g_disp.icon_caption = a.pos[1].str();
            if (g_disp.win) SDL_SetWindowTitle(g_disp.win, g_disp.caption.c_str());
            return V::none();
        });
        md->fn("get_caption", [](const Args&) { return V::tuple({V(g_disp.caption), V(g_disp.icon_caption)}); });
        md->fn("get_window_size", [](const Args&) {
            int w = g_disp.lw, h = g_disp.lh;
            if (g_disp.win) SDL_GetWindowSize(g_disp.win, &w, &h);
            return tup2(w, h);
        });
        md->fn("get_desktop_sizes", [](const Args&) {
            ensure_init();
            std::vector<V> out;
            for (int i = 0; i < SDL_GetNumVideoDisplays(); ++i) { SDL_DisplayMode dm; if (SDL_GetDesktopDisplayMode(i, &dm) == 0) out.push_back(tup2(dm.w, dm.h)); }
            return V::list(out);
        });
        md->fn("toggle_fullscreen", [](const Args&) {
            if (!g_disp.win) return V(0.0);
            bool fs = (SDL_GetWindowFlags(g_disp.win) & SDL_WINDOW_FULLSCREEN_DESKTOP) != 0;
            SDL_SetWindowFullscreen(g_disp.win, fs ? 0 : SDL_WINDOW_FULLSCREEN_DESKTOP);
            return V(1.0);
        });
        md->fn("iconify", [](const Args&) { if (g_disp.win) SDL_MinimizeWindow(g_disp.win); return V(true); });
        md->fn("set_icon", [](const Args&) { return V::none(); });
        md->fn("get_active", [](const Args&) { return V(g_disp.win && (SDL_GetWindowFlags(g_disp.win) & SDL_WINDOW_INPUT_FOCUS)); });
        md->fn("get_driver", [](const Args&) { const char* d = SDL_GetCurrentVideoDriver(); return V(std::string(d ? d : "")); });
        md->fn("get_wm_info", [](const Args&) { return V::dict(); });
        md->fn("Info", [](const Args&) {
            ensure_init();
            V d = new_module("VideoInfo");
            SDL_DisplayMode dm{};
            SDL_GetDesktopDisplayMode(0, &dm);
            module_of(d)->add("current_w", V(double(g_disp.win ? g_disp.lw : dm.w)));
            module_of(d)->add("current_h", V(double(g_disp.win ? g_disp.lh : dm.h)));
            return d;
        });
        return mod;
    }();
    return m;
}

V event_module() {
    static V m = [] {
        V mod = new_module("pygame.event");
        Module* md = module_of(mod);
        md->fn("get", [](const Args& a) {
            static const V none_v = V::none();
            V filt = a.get(0, Sym("eventtype"), &none_v);
            std::vector<V> evs = pump_all(), out;
            for (auto& e : evs) {
                if (type_matches(as<Event>(e)->type, filt)) out.push_back(e);
                else g_posted.push_back(e);
            }
            return V::list(out);
        });
        md->fn("poll", [](const Args&) {
            std::vector<V> evs = pump_all();
            if (evs.empty()) return make_event(0);
            for (size_t i = 1; i < evs.size(); ++i) g_posted.push_back(evs[i]);
            return evs[0];
        });
        md->fn("wait", [](const Args& a) {
            for (;;) {
                std::vector<V> evs = pump_all();
                if (!evs.empty()) { for (size_t i = 1; i < evs.size(); ++i) g_posted.push_back(evs[i]); return evs[0]; }
                SDL_WaitEventTimeout(nullptr, a.pos.empty() ? 50 : int(a.pos[0].num()));
                if (!a.pos.empty()) return make_event(0);
            }
        });
        md->fn("peek", [](const Args& a) {
            std::vector<V> evs = pump_all();
            static const V none_v = V::none();
            V filt = a.get(0, Sym("eventtype"), &none_v);
            bool any = false;
            for (auto& e : evs) { if (type_matches(as<Event>(e)->type, filt)) any = true; g_posted.push_back(e); }
            return V(any);
        });
        md->fn("pump", [](const Args&) { SDL_PumpEvents(); return V::none(); });
        md->fn("clear", [](const Args&) { pump_all(); g_posted.clear(); return V::none(); });
        md->fn("post", [](const Args& a) { g_posted.push_back(a.pos.at(0)); return V(true); });
        md->fn("Event", [](const Args& a) {
            V d = V::dict();
            if (a.pos.size() > 1 && a.pos[1].is_dict()) for (auto& p : a.pos[1].kv()) d.at(p.first) = p.second;
            for (auto& p : a.kw) d.at(V(p.first)) = p.second;
            return make_event(int(a.pos.at(0).num()), d);
        });
        md->fn("event_name", [](const Args& a) { return V(event_name(int(a.pos.at(0).num()))); });
        md->fn("set_blocked", [](const Args& a) {
            if (a.pos.empty() || a.pos[0].is_none()) return V::none();
            if (a.pos[0].is_list()) for (auto& t : a.pos[0].items()) g_blocked[int(t.num())] = true; else g_blocked[int(a.pos[0].num())] = true;
            return V::none();
        });
        md->fn("set_allowed", [](const Args& a) {
            if (a.pos.empty() || a.pos[0].is_none()) { g_blocked.clear(); return V::none(); }
            if (a.pos[0].is_list()) for (auto& t : a.pos[0].items()) g_blocked[int(t.num())] = false; else g_blocked[int(a.pos[0].num())] = false;
            return V::none();
        });
        md->fn("get_blocked", [](const Args& a) { return V(g_blocked[int(a.pos.at(0).num())]); });
        md->fn("set_grab", [](const Args&) { return V::none(); });
        md->fn("get_grab", [](const Args&) { return V(false); });
        md->fn("custom_type", [](const Args&) { static int next = E_USEREVENT + 1; return V(double(next++)); });
        return mod;
    }();
    return m;
}

V key_module() {
    static V m = [] {
        V mod = new_module("pygame.key");
        Module* md = module_of(mod);
        md->fn("get_pressed", [](const Args&) { SDL_PumpEvents(); return V::inst(std::make_shared<Pressed>()); });
        md->fn("get_mods", [](const Args&) { return V(double(SDL_GetModState())); });
        md->fn("set_mods", [](const Args& a) { SDL_SetModState(SDL_Keymod(int(a.pos.at(0).num()))); return V::none(); });
        md->fn("name", [](const Args& a) {
            std::string n = SDL_GetKeyName(SDL_Keycode(int64_t(a.pos.at(0).num())));
            for (auto& c : n) c = char(std::tolower(static_cast<unsigned char>(c)));
            return V(n);
        });
        md->fn("key_code", [](const Args& a) {
            SDL_Keycode k = SDL_GetKeyFromName(a.pos.at(0).str().c_str());
            if (k == SDLK_UNKNOWN) throw PyError("ValueError", "unknown key name");
            return V(double(k));
        });
        md->fn("start_text_input", [](const Args&) { SDL_StartTextInput(); return V::none(); });
        md->fn("stop_text_input", [](const Args&) { SDL_StopTextInput(); return V::none(); });
        md->fn("set_text_input_rect", [](const Args& a) {
            if (a.pos.empty() || a.pos[0].is_none()) return V::none();
            IRect r = rect_of(a.pos[0]);
            SDL_Rect q{r.x, r.y, r.w, r.h};
            SDL_SetTextInputRect(&q);
            return V::none();
        });
        md->fn("set_repeat", [](const Args& a) {
            g_repeat_delay = a.pos.empty() ? 0 : int(a.pos[0].num());
            g_repeat_interval = a.pos.size() > 1 ? int(a.pos[1].num()) : g_repeat_delay;
            return V::none();
        });
        md->fn("get_repeat", [](const Args&) { return tup2(g_repeat_delay, g_repeat_interval); });
        md->fn("get_focused", [](const Args&) { return V(SDL_GetKeyboardFocus() != nullptr); });
        return mod;
    }();
    return m;
}

V mouse_module() {
    static V m = [] {
        V mod = new_module("pygame.mouse");
        Module* md = module_of(mod);
        md->fn("get_pos", [](const Args&) {
            int x, y; SDL_GetMouseState(&x, &y);
            int lx, ly; map_mouse(x, y, lx, ly);
            return tup2(lx, ly);
        });
        md->fn("get_pressed", [](const Args& a) {
            Uint32 b = SDL_GetMouseState(nullptr, nullptr);
            int n = a.pos.empty() ? 3 : int(a.pos[0].num());
            std::vector<V> out = {V((b & SDL_BUTTON_LMASK) != 0), V((b & SDL_BUTTON_MMASK) != 0), V((b & SDL_BUTTON_RMASK) != 0)};
            if (n == 5) { out.push_back(V((b & SDL_BUTTON_X1MASK) != 0)); out.push_back(V((b & SDL_BUTTON_X2MASK) != 0)); }
            return V::tuple(out);
        });
        md->fn("get_rel", [](const Args&) { int x, y; SDL_GetRelativeMouseState(&x, &y); return tup2(x, y); });
        md->fn("set_visible", [](const Args& a) { int prev = SDL_ShowCursor(SDL_QUERY); SDL_ShowCursor(a.pos.at(0).truthy() ? SDL_ENABLE : SDL_DISABLE); return V(prev == SDL_ENABLE); });
        md->fn("get_visible", [](const Args&) { return V(SDL_ShowCursor(SDL_QUERY) == SDL_ENABLE); });
        md->fn("set_pos", [](const Args& a) { if (g_disp.win) SDL_WarpMouseInWindow(g_disp.win, iv(a.pos.at(0).idx(0)), iv(a.pos.at(0).idx(1))); return V::none(); });
        md->fn("get_focused", [](const Args&) { return V(SDL_GetMouseFocus() != nullptr); });
        md->fn("set_cursor", [](const Args&) { return V::none(); });
        return mod;
    }();
    return m;
}

V time_module() {
    static V m = [] {
        V mod = new_module("pygame.time");
        Module* md = module_of(mod);
        md->fn("Clock", [](const Args&) { return V::inst(std::make_shared<Clock>()); });
        md->fn("get_ticks", [](const Args&) { return V(double(g_inited ? SDL_GetTicks() - g_start_ticks : 0)); });
        md->fn("wait", [](const Args& a) { gil::Release g_; SDL_Delay(Uint32(std::max(0.0, a.pos.at(0).num()))); return a.pos.at(0); });
        md->fn("delay", [](const Args& a) { gil::Release g_; SDL_Delay(Uint32(std::max(0.0, a.pos.at(0).num()))); return a.pos.at(0); });
        md->fn("set_timer", [](const Args&) { return V::none(); });
        return mod;
    }();
    return m;
}

V mixer_module() {
    static V m = [] {
        V mod = new_module("pygame.mixer");
        Module* md = module_of(mod);
        auto init = [](const Args& a) {
            ensure_init();
            if (g_mixer) return V::none();
            static const V f(44100.0), sz(-16.0), ch(2.0), buf(512.0);
            int freq = int(a.get(0, Sym("frequency"), &f).num());
            int chans = int(a.get(2, Sym("channels"), &ch).num());
            int buffer = int(a.get(3, Sym("buffer"), &buf).num());
            if (!open_mixer(freq > 0 ? freq : 44100,chans > 0 ? chans : 2,buffer > 0 ? buffer : 512)) {
                throw PyError("error", std::string("mixer not available: ") + Mix_GetError());
            }
            return V::none();
        };
        md->fn("init", init);
        md->fn("pre_init", [](const Args&) { return V::none(); });
        md->fn("quit", [](const Args&) { if (g_mixer) { Mix_HaltChannel(-1);Mix_ReserveChannels(0);Mix_CloseAudio();g_mixer=false; } g_channels=8;chan_sound().clear();return V::none(); });
        md->fn("get_init", [](const Args&) {
            if (!g_mixer) return V::none();
            int freq; Uint16 fmt; int ch;
            Mix_QuerySpec(&freq, &fmt, &ch);
            return V::tuple({V(double(freq)), V(-16.0), V(double(ch))});
        });
        md->fn("set_num_channels", [](const Args& a) { g_channels = int(a.pos.at(0).num()); if (g_mixer) Mix_AllocateChannels(g_channels); return V::none(); });
        md->fn("get_num_channels", [](const Args&) { if(!g_mixer)throw PyError("error","mixer not initialized");return V(double(Mix_AllocateChannels(-1))); });
        md->fn("set_reserved", [](const Args& a) { return V(double(g_mixer ? Mix_ReserveChannels(int(a.pos.at(0).num())) : 0)); });
        md->fn("stop", [](const Args&) { if (g_mixer) Mix_HaltChannel(-1); return V::none(); });
        md->fn("pause", [](const Args&) { if (g_mixer) Mix_Pause(-1); return V::none(); });
        md->fn("unpause", [](const Args&) { if (g_mixer) Mix_Resume(-1); return V::none(); });
        md->fn("fadeout", [](const Args& a) { if (g_mixer) Mix_FadeOutChannel(-1, int(a.pos.at(0).num())); return V::none(); });
        md->fn("get_busy", [](const Args&) { return V(g_mixer && Mix_Playing(-1) > 0); });
        md->fn("find_channel", [](const Args&) {
            if (!g_mixer) return V::none();
            for (int i = 0; i < g_channels; ++i) if (!Mix_Playing(i)) return channel(i);
            return V::none();
        });
        md->fn("Channel", [](const Args& a) { return channel(int(a.pos.at(0).num())); });
        md->fn("Sound", [](const Args& a) {
            auto s = std::make_shared<Sound>();
            static const V none_v = V::none();
            V file = a.get(0, Sym("file"), &none_v);
            if (file.is_none() && a.has_kw(Sym("buffer"))) {
                if (g_mixer) {
                    s->raw = bytes_of(a.get(1, Sym("buffer"), &none_v));
                    s->c = Mix_QuickLoad_RAW(reinterpret_cast<Uint8*>(s->raw.data()), Uint32(s->raw.size()));
                }
                return V::inst(s);
            }
            if (g_mixer && !file.is_none()) {
                if (file.t == V::STR && file.str().size() < 1024 && file.str().find('\0') == std::string::npos) {
                    s->c = Mix_LoadWAV(sdl_path(path_str(file)).c_str());
                } else if (file.t == V::INST && std::string(file.box->inst->type_name()) == "Path") {
                    s->c = Mix_LoadWAV(sdl_path(path_str(file)).c_str());
                } else {
                    std::string data = bytes_of(file);
                    s->c = Mix_LoadWAV_RW(SDL_RWFromConstMem(data.data(), int(data.size())), 1);
                }
                if (!s->c) { SDL_Log("pvz: sound load failed: %s", Mix_GetError()); throw PyError("FileNotFoundError", std::string("sound load failed: ") + Mix_GetError()); }
            }
            return V::inst(s);
        });
        V music = new_module("pygame.mixer.music");
        Module* mu = module_of(music);
        mu->fn("load", [](const Args& a) {
            if (!g_mixer) throw PyError("error", "mixer not initialized");
            if (g_music) { Mix_FreeMusic(g_music); g_music = nullptr; }
            g_music = Mix_LoadMUS(sdl_path(path_str(a.pos.at(0))).c_str());
            if (!g_music) { SDL_Log("pvz: music load failed: %s", Mix_GetError()); throw PyError("error", std::string("music load failed: ") + Mix_GetError()); }
            return V::none();
        });
        mu->fn("play", [](const Args& a) {
            static const V zero(0.0);
            int loops = int(a.get(0, Sym("loops"), &zero).num());
            double start = a.get(1, Sym("start"), &zero).num();
            int fade = int(a.get(2, Sym("fade_ms"), &zero).num());
            if (g_mixer && g_music) {
                if (fade > 0) Mix_FadeInMusicPos(g_music, loops, fade, start); else { Mix_PlayMusic(g_music, loops); if (start > 0) Mix_SetMusicPosition(start); }
                Mix_VolumeMusic(int(g_music_volume * MIX_MAX_VOLUME));
            }
            return V::none();
        });
        mu->fn("stop", [](const Args&) { if (g_mixer) Mix_HaltMusic(); return V::none(); });
        mu->fn("pause", [](const Args&) { if (g_mixer) Mix_PauseMusic(); return V::none(); });
        mu->fn("unpause", [](const Args&) { if (g_mixer) Mix_ResumeMusic(); return V::none(); });
        mu->fn("rewind", [](const Args&) { if (g_mixer) Mix_RewindMusic(); return V::none(); });
        mu->fn("fadeout", [](const Args& a) { if (g_mixer) Mix_FadeOutMusic(int(a.pos.at(0).num())); return V::none(); });
        mu->fn("set_volume", [](const Args& a) { g_music_volume = std::clamp(a.pos.at(0).num(), 0.0, 1.0); if (g_mixer) Mix_VolumeMusic(int(g_music_volume * MIX_MAX_VOLUME)); return V::none(); });
        mu->fn("get_volume", [](const Args&) { return V(g_music_volume); });
        mu->fn("get_busy", [](const Args&) { return V(g_mixer && Mix_PlayingMusic() && !Mix_PausedMusic()); });
        mu->fn("set_pos", [](const Args& a) { if (g_mixer) Mix_SetMusicPosition(a.pos.at(0).num()); return V::none(); });
        mu->fn("unload", [](const Args&) { if (g_music) { Mix_FreeMusic(g_music); g_music = nullptr; } return V::none(); });
        mu->fn("queue", [](const Args&) { return V::none(); });
        mu->fn("get_pos", [](const Args&) { return V(-1.0); });
        md->add("music", music);
        return mod;
    }();
    return m;
}

V scrap_module() {
    static V m = [] {
        V mod = new_module("pygame.scrap");
        Module* md = module_of(mod);
        md->fn("init", [](const Args&) { return V::none(); });
        md->fn("get_init", [](const Args&) { return V(true); });
        md->fn("put", [](const Args& a) { SDL_SetClipboardText(bytes_of(a.pos.at(1)).c_str()); return V::none(); });
        md->fn("put_text", [](const Args& a) { SDL_SetClipboardText(a.pos.at(0).str().c_str()); return V::none(); });
        md->fn("get", [](const Args&) {
            if (!SDL_HasClipboardText()) return V::none();
            char* t = SDL_GetClipboardText();
            std::string s = t ? t : "";
            SDL_free(t);
            return V(s);
        });
        md->fn("get_text", [](const Args&) { char* t = SDL_GetClipboardText(); std::string s = t ? t : ""; SDL_free(t); return V(s); });
        md->fn("get_types", [](const Args&) { return V::list({V("text/plain;charset=utf-8")}); });
        md->fn("contains", [](const Args&) { return V(SDL_HasClipboardText() == SDL_TRUE); });
        md->fn("lost", [](const Args&) { return V(false); });
        md->fn("set_mode", [](const Args&) { return V::none(); });
        return mod;
    }();
    return m;
}

V image_module() {
    static V m = [] {
        V mod = new_module("pygame.image");
        Module* md = module_of(mod);
        md->fn("load", [](const Args& a) { return load_image(a.pos.at(0)); });
        md->fn("save", [](const Args& a) {
            Surface* s = surf(a.pos.at(0));
            std::string p = path_str(a.pos.at(1));
            if (IMG_SavePNG(s->s, p.c_str()) != 0) throw PyError("error", IMG_GetError());
            return V::none();
        });
        // pygame.image.tobytes / tostring(surface, format, flipped=False): raw rows of the ARGB8888 pixels;
        // a surface without SRCALPHA reports opaque alpha exactly like pygame does
        auto tobytes = [](const Args& a) {
            Surface* s = surf(a.get(0, Sym("surface"), nullptr, "tobytes"));
            std::string fmt = a.get(1, Sym("format"), nullptr, "tobytes").str();
            static const V no = V(false);
            bool flipped = a.get(2, Sym("flipped"), &no, "tobytes").truthy();
            int w = s->w(), h = s->h();
            if (fmt != "RGBA" && fmt != "RGB" && fmt != "ARGB" && fmt != "RGBX" && fmt != "BGRA")
                throw PyError("ValueError", "Unrecognized type of format");
            std::string out;
            out.reserve(size_t(w) * size_t(h) * (fmt == "RGB" ? 3 : 4));
            for (int yy = 0; yy < h; ++yy) {
                int y = flipped ? h - 1 - yy : yy;
                const uint32_t* r = reinterpret_cast<const uint32_t*>(static_cast<const uint8_t*>(s->s->pixels) + size_t(y) * s->s->pitch);
                for (int x = 0; x < w; ++x) {
                    uint32_t c = r[x];
                    char R = char((c >> 16) & 255), G = char((c >> 8) & 255), B = char(c & 255), A = char(s->srcalpha ? (c >> 24) & 255 : 255);
                    if (fmt == "RGBA") { out += R; out += G; out += B; out += A; }
                    else if (fmt == "RGB") { out += R; out += G; out += B; }
                    else if (fmt == "RGBX") { out += R; out += G; out += B; out += char(255); }
                    else if (fmt == "ARGB") { out += A; out += R; out += G; out += B; }
                    else { out += B; out += G; out += R; out += A; }
                }
            }
            return V::bytes(std::move(out));
        };
        md->fn("tobytes", tobytes);
        md->fn("tostring", tobytes);
        auto frombytes = [](const Args& a) {
            const V buffer = a.get(0, Sym("bytes"), nullptr, "frombytes");
            if (!(buffer.t == V::STR && buffer.byt))
                throw PyError("TypeError", "a bytes-like object is required");
            const V data = py::builtin_call(V("bytes"), Args{buffer});
            const V size = a.get(1, Sym("size"), nullptr, "frombytes");
            const std::string format = a.get(2, Sym("format"), nullptr, "frombytes").str();
            static const V no(false);
            bool flipped = a.get(3, Sym("flipped"), &no, "frombytes").truthy();
            if (format != "RGBA" && format != "RGB" && format != "ARGB" && format != "RGBX" && format != "BGRA")
                throw PyError("ValueError", "Unrecognized type of format");
            int w = int(size.idx(0).num()), h = int(size.idx(1).num());
            size_t channels = format == "RGB" ? 3 : 4;
            if (w <= 0 || h <= 0 || size_t(w) > SIZE_MAX / size_t(h) / channels ||
                data.str().size() != size_t(w) * size_t(h) * channels)
                throw PyError("ValueError", "String length does not equal format and resolution size");
            V result = new_surface(w, h, format != "RGB" && format != "RGBX");
            Surface* surface = surf(result);
            const auto* input = reinterpret_cast<const unsigned char*>(data.str().data());
            for (int yy = 0; yy < h; ++yy) {
                int y = flipped ? h - 1 - yy : yy;
                auto* row = reinterpret_cast<uint32_t*>(static_cast<unsigned char*>(surface->s->pixels) + size_t(y) * surface->s->pitch);
                for (int x = 0; x < w; ++x) {
                    const auto* c = input + (size_t(yy) * w + x) * channels;
                    unsigned r, g, b, alpha = 255;
                    if (format == "ARGB") { alpha=c[0];r=c[1];g=c[2];b=c[3]; }
                    else if (format == "BGRA") { b=c[0];g=c[1];r=c[2];alpha=c[3]; }
                    else { r=c[0];g=c[1];b=c[2];if(format=="RGBA")alpha=c[3]; }
                    row[x]=(alpha<<24)|(r<<16)|(g<<8)|b;
                }
            }
            return result;
        };
        md->fn("frombytes", frombytes);
        md->fn("fromstring", frombytes);
        md->fn("get_extended", [](const Args&) { return V(true); });
        md->fn("get_sdl_image_version", [](const Args&) { return V::tuple({V(2.0), V(8.0), V(2.0)}); });
        return mod;
    }();
    return m;
}

void add_constants(V& module) {
    Module* md = module_of(module);
    auto k = [&](const char* n, double v) { md->add(n, V(v)); };
    // event types (pygame 2 numbering = SDL2 event numbers + pygame extras)
    k("NOEVENT", 0); k("QUIT", SDL_QUIT); k("KEYDOWN", SDL_KEYDOWN); k("KEYUP", SDL_KEYUP); k("TEXTEDITING", SDL_TEXTEDITING);
    k("TEXTINPUT", SDL_TEXTINPUT); k("MOUSEMOTION", SDL_MOUSEMOTION); k("MOUSEBUTTONDOWN", SDL_MOUSEBUTTONDOWN);
    k("MOUSEBUTTONUP", SDL_MOUSEBUTTONUP); k("MOUSEWHEEL", SDL_MOUSEWHEEL); k("FINGERDOWN", SDL_FINGERDOWN); k("FINGERUP", SDL_FINGERUP);
    k("FINGERMOTION", SDL_FINGERMOTION); k("ACTIVEEVENT", E_ACTIVEEVENT); k("VIDEORESIZE", E_VIDEORESIZE); k("VIDEOEXPOSE", E_VIDEOEXPOSE);
    k("USEREVENT", E_USEREVENT); k("WINDOWSHOWN", E_WINDOWSHOWN); k("WINDOWHIDDEN", E_WINDOWHIDDEN); k("WINDOWEXPOSED", E_WINDOWEXPOSED);
    k("WINDOWMOVED", E_WINDOWMOVED); k("WINDOWRESIZED", E_WINDOWRESIZED); k("WINDOWSIZECHANGED", E_WINDOWSIZECHANGED);
    k("WINDOWMINIMIZED", E_WINDOWMINIMIZED); k("WINDOWMAXIMIZED", E_WINDOWMAXIMIZED); k("WINDOWRESTORED", E_WINDOWRESTORED);
    k("WINDOWENTER", E_WINDOWENTER); k("WINDOWLEAVE", E_WINDOWLEAVE); k("WINDOWFOCUSGAINED", E_WINDOWFOCUSGAINED);
    k("WINDOWFOCUSLOST", E_WINDOWFOCUSLOST); k("WINDOWCLOSE", E_WINDOWCLOSE);
    k("APP_WILLENTERBACKGROUND", SDL_APP_WILLENTERBACKGROUND); k("APP_DIDENTERBACKGROUND", SDL_APP_DIDENTERBACKGROUND);
    k("APP_WILLENTERFOREGROUND", SDL_APP_WILLENTERFOREGROUND); k("APP_DIDENTERFOREGROUND", SDL_APP_DIDENTERFOREGROUND);
    k("JOYBALLMOTION", SDL_JOYBALLMOTION); k("JOYHATMOTION", SDL_JOYHATMOTION);
    k("JOYDEVICEADDED", SDL_JOYDEVICEADDED); k("JOYDEVICEREMOVED", SDL_JOYDEVICEREMOVED);
    k("JOYAXISMOTION", SDL_JOYAXISMOTION); k("JOYBUTTONDOWN", SDL_JOYBUTTONDOWN); k("JOYBUTTONUP", SDL_JOYBUTTONUP);
    // surface / display flags
    k("SWSURFACE", 0); k("HWSURFACE", 1); k("SRCALPHA", F_SRCALPHA); k("FULLSCREEN", double(uint32_t(F_FULLSCREEN)));
    k("RLEACCELOK", 0x2000); k("RLEACCEL", 0x4000);
    k("RESIZABLE", F_RESIZABLE); k("NOFRAME", F_NOFRAME); k("SCALED", F_SCALED); k("OPENGL", 2); k("DOUBLEBUF", double(0x40000000));
    k("SHOWN", 0); k("HIDDEN", 0x80);
    // blend flags
    k("BLEND_ADD", 1); k("BLEND_RGB_ADD", 1); k("BLEND_SUB", 2); k("BLEND_RGB_SUB", 2); k("BLEND_MULT", 3); k("BLEND_RGB_MULT", 3);
    k("BLEND_MIN", 4); k("BLEND_RGB_MIN", 4); k("BLEND_MAX", 5); k("BLEND_RGB_MAX", 5); k("BLEND_RGBA_ADD", 6); k("BLEND_RGBA_SUB", 7);
    k("BLEND_RGBA_MULT", 8); k("BLEND_RGBA_MIN", 9); k("BLEND_RGBA_MAX", 16); k("BLEND_PREMULTIPLIED", 17); k("BLEND_ALPHA_SDL2", 18);
    // mouse buttons
    k("BUTTON_LEFT", 1); k("BUTTON_MIDDLE", 2); k("BUTTON_RIGHT", 3); k("BUTTON_WHEELUP", 4); k("BUTTON_WHEELDOWN", 5);
    k("BUTTON_X1", 6); k("BUTTON_X2", 7);
    // modifiers
    k("KMOD_NONE", KMOD_NONE); k("KMOD_LSHIFT", KMOD_LSHIFT); k("KMOD_RSHIFT", KMOD_RSHIFT); k("KMOD_SHIFT", KMOD_SHIFT);
    k("KMOD_LCTRL", KMOD_LCTRL); k("KMOD_RCTRL", KMOD_RCTRL); k("KMOD_CTRL", KMOD_CTRL); k("KMOD_LALT", KMOD_LALT);
    k("KMOD_RALT", KMOD_RALT); k("KMOD_ALT", KMOD_ALT); k("KMOD_LMETA", KMOD_LGUI); k("KMOD_RMETA", KMOD_RGUI); k("KMOD_META", KMOD_GUI);
    k("KMOD_LGUI", KMOD_LGUI); k("KMOD_RGUI", KMOD_RGUI); k("KMOD_GUI", KMOD_GUI); k("KMOD_CAPS", KMOD_CAPS); k("KMOD_NUM", KMOD_NUM);
    k("KMOD_MODE", KMOD_MODE);
    // keys: letters, digits and the named SDL keycodes
    for (char c = 'a'; c <= 'z'; ++c) { char n[4] = {'K', '_', c, 0}; k(n, c); }
    for (char c = '0'; c <= '9'; ++c) { char n[4] = {'K', '_', c, 0}; k(n, c); }
    static const std::pair<const char*, SDL_Keycode> keys[] = {
        {"K_ESCAPE", SDLK_ESCAPE}, {"K_RETURN", SDLK_RETURN}, {"K_TAB", SDLK_TAB}, {"K_SPACE", SDLK_SPACE}, {"K_BACKSPACE", SDLK_BACKSPACE},
        {"K_DELETE", SDLK_DELETE}, {"K_INSERT", SDLK_INSERT}, {"K_HOME", SDLK_HOME}, {"K_END", SDLK_END}, {"K_PAGEUP", SDLK_PAGEUP},
        {"K_PAGEDOWN", SDLK_PAGEDOWN}, {"K_UP", SDLK_UP}, {"K_DOWN", SDLK_DOWN}, {"K_LEFT", SDLK_LEFT}, {"K_RIGHT", SDLK_RIGHT},
        {"K_KP_ENTER", SDLK_KP_ENTER}, {"K_KP0", SDLK_KP_0}, {"K_KP1", SDLK_KP_1}, {"K_KP2", SDLK_KP_2}, {"K_KP3", SDLK_KP_3},
        {"K_KP4", SDLK_KP_4}, {"K_KP5", SDLK_KP_5}, {"K_KP6", SDLK_KP_6}, {"K_KP7", SDLK_KP_7}, {"K_KP8", SDLK_KP_8}, {"K_KP9", SDLK_KP_9},
        {"K_KP_0", SDLK_KP_0}, {"K_KP_1", SDLK_KP_1}, {"K_KP_2", SDLK_KP_2}, {"K_KP_3", SDLK_KP_3}, {"K_KP_4", SDLK_KP_4},
        {"K_KP_5", SDLK_KP_5}, {"K_KP_6", SDLK_KP_6}, {"K_KP_7", SDLK_KP_7}, {"K_KP_8", SDLK_KP_8}, {"K_KP_9", SDLK_KP_9},
        {"K_KP_PLUS", SDLK_KP_PLUS}, {"K_KP_MINUS", SDLK_KP_MINUS}, {"K_KP_MULTIPLY", SDLK_KP_MULTIPLY}, {"K_KP_DIVIDE", SDLK_KP_DIVIDE},
        {"K_KP_PERIOD", SDLK_KP_PERIOD}, {"K_KP_EQUALS", SDLK_KP_EQUALS},
        {"K_LSHIFT", SDLK_LSHIFT}, {"K_RSHIFT", SDLK_RSHIFT}, {"K_LCTRL", SDLK_LCTRL}, {"K_RCTRL", SDLK_RCTRL}, {"K_LALT", SDLK_LALT},
        {"K_RALT", SDLK_RALT}, {"K_LMETA", SDLK_LGUI}, {"K_RMETA", SDLK_RGUI}, {"K_LGUI", SDLK_LGUI}, {"K_RGUI", SDLK_RGUI},
        {"K_CAPSLOCK", SDLK_CAPSLOCK}, {"K_NUMLOCK", SDLK_NUMLOCKCLEAR}, {"K_SCROLLOCK", SDLK_SCROLLLOCK}, {"K_PAUSE", SDLK_PAUSE},
        {"K_PRINT", SDLK_PRINTSCREEN}, {"K_MENU", SDLK_MENU}, {"K_AC_BACK", SDLK_AC_BACK},
        {"K_F1", SDLK_F1}, {"K_F2", SDLK_F2}, {"K_F3", SDLK_F3}, {"K_F4", SDLK_F4}, {"K_F5", SDLK_F5}, {"K_F6", SDLK_F6},
        {"K_F7", SDLK_F7}, {"K_F8", SDLK_F8}, {"K_F9", SDLK_F9}, {"K_F10", SDLK_F10}, {"K_F11", SDLK_F11}, {"K_F12", SDLK_F12},
        {"K_COMMA", SDLK_COMMA}, {"K_PERIOD", SDLK_PERIOD}, {"K_MINUS", SDLK_MINUS}, {"K_EQUALS", SDLK_EQUALS}, {"K_PLUS", SDLK_PLUS},
        {"K_SLASH", SDLK_SLASH}, {"K_BACKSLASH", SDLK_BACKSLASH}, {"K_SEMICOLON", SDLK_SEMICOLON}, {"K_QUOTE", SDLK_QUOTE},
        {"K_LEFTBRACKET", SDLK_LEFTBRACKET}, {"K_RIGHTBRACKET", SDLK_RIGHTBRACKET}, {"K_BACKQUOTE", SDLK_BACKQUOTE},
        {"K_EXCLAIM", SDLK_EXCLAIM}, {"K_QUESTION", SDLK_QUESTION}, {"K_COLON", SDLK_COLON}, {"K_UNDERSCORE", SDLK_UNDERSCORE},
        {"K_UNKNOWN", SDLK_UNKNOWN}};
    for (auto& [n, v] : keys) k(n, double(v));
    md->add("SCRAP_TEXT", V("text/plain;charset=utf-8"));
    md->add("SCRAP_BMP", V("image/bmp"));
}

V pygame_module() {
    static V m = [] {
        V mod = new_module("pygame");
        Module* md = module_of(mod);
        md->fn("init", [](const Args&) {
            ensure_init();
            // like pygame.init(): the mixer comes up too (44100 Hz, 16-bit, stereo, 512); no audio device -> one failure
            int failed = 0;
            try { joystick_init(); } catch(const PyError&) { ++failed; }
            if (!g_mixer) {
                if (!open_mixer(44100,2,512)) ++failed;
            }
            return V::tuple({V(6.0 - failed), V(double(failed))});
        });
        md->fn("quit", [](const Args&) { return V::none(); });
        md->fn("get_init", [](const Args&) { return V(g_inited); });
        md->fn("get_sdl_version", [](const Args&) { SDL_version v; SDL_GetVersion(&v); return V::tuple({V(double(v.major)), V(double(v.minor)), V(double(v.patch))}); });


        md->add("Surface", surface_type());
        md->add("Rect", rect_type());
        md->add("FRect", rect_type());
        md->fn("Color", [](const Args& a) {
            SDL_Color c = a.pos.size() >= 3 ? SDL_Color{Uint8(a.pos[0].num()), Uint8(a.pos[1].num()), Uint8(a.pos[2].num()), Uint8(a.pos.size() > 3 ? a.pos[3].num() : 255)}
                                            : color_of(a.pos.at(0));
            V out = V::tuple({V(double(c.r)), V(double(c.g)), V(double(c.b)), V(double(c.a))});
            out.box->color = true;   // tuple-equal like pygame.Color, plus .r .g .b .a
            return out;
        });
        md->add("error", py::class_value(V("error"),[](const Args& a){return py::make_exc(V("error"),a,"RuntimeError");}));
        md->add("draw", draw_module());
        md->add("transform", transform_module());
        md->add("font", font_module());
        md->add("image", image_module());
        md->add("display", display_module());
        md->add("event", event_module());
        md->add("key", key_module());
        md->add("mouse", mouse_module());
        md->add("time", time_module());
        md->add("mixer", mixer_module());
        md->add("scrap", scrap_module());
        md->add("joystick", joystick_module());
        V cursors = new_module("pygame.cursors");
        md->add("cursors", cursors);
        V version = new_module("pygame.version");
        module_of(version)->add("ver", V("2.4.0"));
        module_of(version)->add("vernum", V::tuple({V(2.0), V(4.0), V(0.0)}));
        module_of(version)->add("SDL", V::tuple({V(2.0), V(30.0), V(9.0)}));
        md->add("version", version);
        md->add("__file__", V("pygame/__init__.py"));
        add_constants(mod);
        return mod;
    }();
    return m;
}

void install_pygame() {
    py::register_module("pygame", pygame_module());
    install_stdlib();
}

}  // namespace pvz::pg
