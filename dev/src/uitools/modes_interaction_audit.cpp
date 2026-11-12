// Actual SDL mouse/key events across non-battle screens, isolated by PVP_USERDATA.
// The parent orchestrator builds this with the same pvzui/pvzcore as production.
#include "pg/pg.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/pvprt.h"
#include "ui/gen/pm_app.h"
#include "data/datastore.h"
#include "core/gil.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

using namespace pvz;
using json = nlohmann::json;

namespace {
V state(const V& app) { return pvz::getattr(app, Sym("state")); }
V action(std::initializer_list<V> values) { return V::tuple(std::vector<V>(values)); }
void act(const V& app, const V& value) { callm(app, Sym("action"), Args{value}); }
void require(bool ok, const char* why) { if (!ok) throw std::runtime_error(why); }
void home(const V& app) {
    if (!pvz::getattr(app, Sym("room"), V::none()).is_none()) callm(app, Sym("close_room"), Args{});
    V s = state(app);
    s.at(V("screen")) = V("home"); s.at(V("return_screen")) = V("home");
    s.at(V("focus")) = V::none(); s.at(V("confirm_leave")) = V(false);
    pvz::setattr(app, Sym("pointer_capture"), V::none());
}
void menu(const V& app, const char* name) { act(app, action({V("menu"), V(name)})); }
void render(const V& app) { callm(app, Sym("render"), Args{}); }
std::pair<int,int> point(const V& app, const V& wanted) {
    V controls = pvz::getattr(pvz::getattr(app, Sym("renderer")), Sym("controls"));
    for (auto& c : py::iter_list(controls).items()) {
        if (c.idx(1) != wanted) continue;
        V center = pvz::getattr(c.idx(0), Sym("center"));
        double sx = pvz::getattr(app, Sym("scale_x")).num();
        double sy = pvz::getattr(app, Sym("scale_y")).num();
        return {int(center.idx(0).num() / sx), int(center.idx(1).num() / sy)};
    }
    throw std::runtime_error("No active rendered control for " + dump(wanted));
}
void button(const V& app, int x, int y, bool down) {
    SDL_Event e{}; e.type = down ? SDL_MOUSEBUTTONDOWN : SDL_MOUSEBUTTONUP;
    e.button.button = SDL_BUTTON_LEFT; e.button.state = down ? SDL_PRESSED : SDL_RELEASED;
    e.button.x = x; e.button.y = y;
    require(SDL_PushEvent(&e) == 1, "SDL rejected mouse event");
    callm(app, Sym("handle_events"), Args{});
}
void click(const V& app, const V& wanted) {
    render(app); auto [x,y] = point(app, wanted); button(app,x,y,true); button(app,x,y,false);
}
void expect_screen(const V& app, const char* name) {
    require(py::m_get(state(app),V("screen")) == V(name), "Unexpected resulting screen");
}
struct Case { const char* name; std::function<void(V)> run; };
std::vector<Case> cases() {
    std::vector<Case> out;
    out.push_back({"home-settings-return", [](V a){ home(a); click(a,action({V("menu"),V("settings")})); expect_screen(a,"settings"); click(a,action({V("menu"),V("back")})); expect_screen(a,"home"); }});
    for (const char* key : {"sound", "music", "low_effects", "numeric_cd"}) {
        out.push_back({key, [key](V a){ home(a); menu(a,"settings"); V before=py::m_get(state(a),V(key)); click(a,action({V(key)})); require(py::m_get(state(a),V(key)) != before,"Setting click did not toggle"); }});
    }
    for (const char* name : {"touch_layout", "slot_keys", "performance", "action_keys"}) {
        out.push_back({name, [name](V a){ home(a); menu(a,"settings"); V touch=py::m_get(state(a),V("touch_mode"));if(std::string(name)=="touch_layout")state(a).at(V("touch_mode"))=V(true);click(a,action({V("menu"),V(name)})); expect_screen(a,name); click(a,action({V("menu"),V("back")})); expect_screen(a,"settings"); click(a,action({V("menu"),V("back")})); expect_screen(a,"home");state(a).at(V("touch_mode"))=touch; }});
    }
    for (const char* key : {"world_quality", "display_filter", "display_budget"}) {
        out.push_back({key, [key](V a){ home(a); menu(a,"settings"); menu(a,"performance"); V before=py::m_get(state(a),V(key)); click(a,action({V(key)})); require(py::m_get(state(a),V(key)) != before,"Display setting click did not change"); }});
    }
    out.push_back({"profile-name-save", [](V a){ home(a); menu(a,"profile"); state(a).at(V("player_name"))=V("交互审计"); click(a,action({V("profile_save")})); require(py::m_get(state(a),V("player_name_saved")).truthy(),"Name was not saved"); click(a,action({V("menu"),V("back")})); expect_screen(a,"home"); }});
    out.push_back({"profile-new", [](V a){ home(a); menu(a,"profile"); auto before=py::len(callm(pvz::getattr(a,Sym("profiles")),Sym("summaries"),Args{})).num(); click(a,action({V("profile_new")})); auto after=py::len(callm(pvz::getattr(a,Sym("profiles")),Sym("summaries"),Args{})).num(); require(after==before+1,"Profile was not created"); }});
    out.push_back({"profile-textinput", [](V a){ home(a); menu(a,"profile"); state(a).at(V("player_name"))=V(""); click(a,action({V("focus"),V("player_name")})); SDL_Event e{};e.type=SDL_TEXTINPUT;SDL_strlcpy(e.text.text,"雪碧test",sizeof(e.text.text)); require(SDL_PushEvent(&e)==1,"SDL rejected text input");callm(a,Sym("handle_events"),Args{}); require(py::m_get(state(a),V("player_name"))==V("雪碧test"),"Unicode text event was lost"); }});
    out.push_back({"replay-library-return", [](V a){ home(a); click(a,action({V("replay_library")})); expect_screen(a,"replays"); click(a,action({V("replay_home")})); expect_screen(a,"home"); }});
    out.push_back({"replay-autosave-setting", [](V a){ home(a); act(a,action({V("replay_library")})); V before=py::m_get(state(a),V("save_replays")); click(a,action({V("save_replays")})); require(py::m_get(state(a),V("save_replays"))!=before,"Replay auto-save did not toggle"); }});
    out.push_back({"maps-library-return", [](V a){ home(a); click(a,action({V("maps_open")})); expect_screen(a,"maps"); click(a,action({V("maps_back")})); expect_screen(a,"home"); }});
    out.push_back({"help-return", [](V a){ home(a); click(a,action({V("menu"),V("help")})); expect_screen(a,"help"); click(a,action({V("help_done")})); expect_screen(a,"home"); }});
    out.push_back({"settings-escape", [](V a){ home(a); menu(a,"settings"); SDL_Event e{};e.type=SDL_KEYDOWN;e.key.keysym.sym=SDLK_ESCAPE;require(SDL_PushEvent(&e)==1,"SDL rejected Escape");callm(a,Sym("handle_events"),Args{});expect_screen(a,"home"); }});
    out.push_back({"mouse-release-outside-cancels", [](V a){ home(a);render(a);auto [x,y]=point(a,action({V("menu"),V("settings")}));button(a,x,y,true);button(a,1,1,false);expect_screen(a,"home"); }});
    out.push_back({"empty-mouse-click", [](V a){ home(a);render(a);button(a,1,1,true);button(a,1,1,false);expect_screen(a,"home"); }});
    return out;
}
}

int main(int argc,char**argv) {
    if(argc!=2 || !std::getenv("PVP_USERDATA")) {fprintf(stderr,"Usage: PVP_USERDATA=<isolated-folder> modes_interaction_audit out.json\n");return 2;}
    SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");py::g_real_clock=true;pg::install_pygame();
    auto tests=cases();auto rows=std::make_shared<json>(json::array());auto index=std::make_shared<size_t>(0);std::string output=argv[1];
    auto save=[=](){int passed=0;for(auto&r:*rows)if(r.value("passed",false))++passed;std::ofstream f(output,std::ios::binary);f<<json{{"scope","SDL mouse/key/text input on desktop dummy driver; not Android device proof"},{"planned",tests.size()},{"executed",rows->size()},{"passed",passed},{"rows",*rows}}.dump(2);};
    try {
        init_pvp_modules();pm_app::init();
        V cb=V::func([=](const Args&A){V a=A.pos.at(0);int frame=int(A.pos.at(1).num());if(frame<3 || frame%3) return V::none();
            if(*index>=tests.size()){pvz::setattr(a,Sym("running"),V(false));return V::none();}
            auto&t=tests[*index];json row{{"name",t.name},{"frame",frame}};
            try{t.run(a);row["passed"]=true;}catch(const PyError&e){row["passed"]=false;row["error"]=e.what();}catch(const std::exception&e){row["passed"]=false;row["error"]=e.what();}
            row["screen"]=py::m_get(state(a),V("screen")).str();row["message"]=py::m_get(state(a),V("message"),V("")).str();
            fprintf(stderr,"MODE_AUDIT %s\n",row.dump().c_str());rows->push_back(row);++*index;home(a);save();return V::none();});
        pm_app::f_run(Args({},{{Sym("auto_test"),cb}}));
    }catch(const PyError&e){rows->push_back(json{{"name","outer-application"},{"passed",false},{"error",e.what()}});}
    catch(const std::exception&e){rows->push_back(json{{"name","outer-application"},{"passed",false},{"error",e.what()}});}
    save();if(*index!=tests.size())return 1;for(auto&r:*rows)if(!r.value("passed",false))return 1;return 0;
}
