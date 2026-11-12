// Real SDL events -> Application.handle_events -> pointer capture -> draft actions.
// Run from the checkout root with an isolated PVP_USERDATA:
// draft_interaction_audit <report.json> [mouse|touch] [--minimal] [--frame-dt=0.6]
#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/pvprt.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "ui/gen/pm_app.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <filesystem>
#include <set>
#include <string>

using namespace pvz;
using json = nlohmann::json;
namespace pvz { void install_crash_handler(); }
namespace {
void require(bool value, const std::string& message) { if (!value) throw std::runtime_error(message); }
V tuple(std::initializer_list<V> values) { return V::tuple(values); }
std::string text(const V& value) { return value.str(); }
struct Audit {
    json rows=json::array();
    V app;
    bool touch=false;
    bool minimal=false;
    bool waiting_for_battle=false;
    double frame_dt=0.016;
    int serial=0;
    std::set<std::string> seen;
    V state() { return getattr(app,SY("state")); }
    V view() { return getattr(app,SY("view")); }
    V room() { return getattr(app,SY("room")); }
    void render() { callm(app,SY("render"),Args{}); }
    V controls() { return getattr(getattr(app,SY("renderer")),SY("controls")); }
    V find(V action) {
        for (const auto& control:py::iter_list(controls()).items())
            if(control.idx(1)==action)return control.idx(0);
        return V::none();
    }
    void row(std::string name, bool pass, std::string detail="") {
        rows.push_back({{"name",name},{"passed",pass},{"detail",detail},
            {"phase",text(py::m_get(view(),SV("phase"),V::none()))},
            {"screen",text(py::m_get(state(),SV("screen"),V::none()))},
            {"message",text(py::m_get(state(),SV("message"),V::none()))}});
        fprintf(stderr,"%s %s %s\n",pass?"PASS":"FAIL",name.c_str(),detail.c_str());
        fflush(stderr);
    }
    void events(V logical, int button=1, bool cancel=false) {
        double px=logical.idx(0).num()/getattr(app,SY("scale_x")).num();
        double py=logical.idx(1).num()/getattr(app,SY("scale_y")).num();
        SDL_Event event{};
        if(touch) {
            V size=callm(getattr(app,SY("surface")),SY("get_size"),Args{});
            event.type=SDL_FINGERDOWN;event.tfinger.touchId=77;event.tfinger.fingerId=++serial;
            event.tfinger.x=float(px/size.idx(0).num());event.tfinger.y=float(py/size.idx(1).num());
            event.tfinger.pressure=1;
        } else {
            event.type=SDL_MOUSEBUTTONDOWN;event.button.which=17;event.button.button=Uint8(button);
            event.button.state=SDL_PRESSED;event.button.x=int(std::round(px));event.button.y=int(std::round(py));
        }
        require(SDL_PushEvent(&event)==1,"SDL rejected down event");
        callm(app,SY("handle_events"),Args{});
        if(minimal) {
            fprintf(stderr,"DOWN_HANDLED revision=%s capture=%s\n",dump(py::m_get(view(),SV("revision"))).c_str(),
                dump(getattr(app,SY("pointer_capture"),V::none())).c_str());fflush(stderr);
            SDL_Delay(30);
            callm(app,SY("step"),Args({V(frame_dt)},{{SY("present"),V(false)}}));
            fprintf(stderr,"BETWEEN_INPUT_FRAMES revision=%s capture=%s\n",dump(py::m_get(view(),SV("revision"))).c_str(),
                dump(getattr(app,SY("pointer_capture"),V::none())).c_str());fflush(stderr);
        }
        if(touch) { event.type=SDL_FINGERUP;event.tfinger.pressure=0; if(cancel)event.tfinger.x=0.999f; }
        else { event.type=SDL_MOUSEBUTTONUP;event.button.state=SDL_RELEASED; if(cancel)event.button.x+=2000; }
        require(SDL_PushEvent(&event)==1,"SDL rejected up event");
        callm(app,SY("handle_events"),Args{});
    }
    void click(V action, const std::string& label, int button=1, bool cancel=false) {
        render();V rect=find(action);require(!rect.is_none(),"Control missing for "+label+": "+dump(action));
        fprintf(stderr,"BEGIN %s %s\n",label.c_str(),dump(action).c_str());fflush(stderr);
        try { events(getattr(rect,SY("center")),button,cancel); row(label,true,dump(action)); }
        catch(const std::exception& e) { row(label,false,e.what()); throw; }
    }
    void all_cards() {
        render();V tabs=V::list();
        for(const auto& control:py::iter_list(controls()).items()) {
            V action=control.idx(1);
            if((action.t==V::TUPLE || action.t==V::LIST) && action.len()>0 && action.idx(0)==SV("tab"))tabs.append(action);
        }
        require(tabs.len()>0,"Draft has no card tabs");
        V revision=getattr(room(),SY("revision"));
        for(const auto& tab:tabs.items()) {
            click(tab,"tab:"+dump(tab));
            for(int page=0;page<40;++page) {
                render();V actions=V::list();
                for(const auto& control:py::iter_list(controls()).items()) {
                    V action=control.idx(1);
                    if((action.t==V::TUPLE || action.t==V::LIST) && action.len()>1 && action.idx(0)==SV("card"))actions.append(action);
                }
                require(actions.len()>0,"Empty card page");
                for(const auto& action:actions.items()) {
                    V key=action.idx(-1);click(action,"preview:"+text(key));
                    require(py::m_get(state(),SV("detail"))==key,"Click did not select card detail");
                    require(getattr(room(),SY("revision"))==revision,"Preview unexpectedly submitted card");
                    seen.insert(text(key));
                }
                render();V next=tuple({SV("page"),tab.idx(1),V(1)});
                if(find(next).is_none())break;
                V old=py::m_get(py::m_get(state(),SV("pages")),tab.idx(1),V(0));
                click(next,"page:"+dump(tab)+":"+std::to_string(page));
                if(py::m_get(py::m_get(state(),SV("pages")),tab.idx(1),V(0))==old)break;
                require(page<39,"Card pagination did not terminate");
            }
        }
        row("preview_matrix",true,"unique_cards="+std::to_string(seen.size())+" catalogue="+std::to_string(pm_catalog::CARDS.len()));
    }
    void reveal(V key) {
        V card=pm_catalog::CARDS.at(key),side=py::m_get(card,SV("side")),category=py::m_get(card,SV("category"));
        click(tuple({SV("tab"),side,category}),"reveal_tab:"+text(key));
        for(int i=0;i<40;++i) {
            render();if(!find(tuple({SV("card"),key})).is_none())return;
            V next=tuple({SV("page"),side,V(1)});require(!find(next).is_none(),"Legal card is absent from paginated UI: "+text(key));
            click(next,"reveal_page:"+text(key));
        }
        throw std::runtime_error("Too many card pages");
    }
    void match() {
        bool recommendation_checked=false;
        for(int turn=0;turn<100;++turn) {
            V action=callm(room(),SY("_draft_action"),Args{});
            if(!action.truthy())break;
            V actor=py::m_get(action,SV("side"));
            bool ban=py::m_get(action,SV("kind"))==SV("ban");
            V before=getattr(room(),SY("revision"));
            if(!ban && !recommendation_checked) {
                click(tuple({SV("recommended")}),"recommend_current_pick");
                V recommended=py::m_get(state(),SV("pending_card"));
                require(recommended.truthy(),"Recommendation did not preview a card");
                require(!callm(room(),SY("_pick_error"),Args{actor,recommended}).truthy(),"Recommended card is illegal");
                require(getattr(room(),SY("revision"))==before,"Recommendation committed a pick without confirmation");
                recommendation_checked=true;
            }
            if(ban && py::m_get(action,SV("category"))==SV("secret"))click(tuple({SV("skip_ban")}),"skip_secret_ban");
            else {
                V key=V::none();V cands=ban?py::list_it(pm_catalog::CARDS):callm(room(),SY("_default_deck"),Args{actor})+py::list_it(pm_catalog::CARDS);
                for(const auto& candidate:py::iter_list(cands).items()) {
                    if(ban && py::m_get(pm_catalog::CARDS.at(candidate),SV("producer"),V(false)).truthy())continue;
                    if(!callm(room(),ban?SY("_ban_error"):SY("_pick_error"),Args{actor,candidate}).truthy()){key=candidate;break;}
                }
                require(!key.is_none(),"No legal draft card");
                reveal(key);click(tuple({SV("card"),key}),ban?"ban_preview":"pick_preview");
                require(getattr(room(),SY("revision"))==before,"Preview committed authority");
                click(tuple({SV("advance")}),ban?"confirm_ban":"confirm_pick");
            }
            require(getattr(room(),SY("revision"))!=before,"Confirmed draft action did not advance");
        }
        require(py::m_get(view(),SV("draft_stage"))==SV("complete"),"Draft did not complete");
        click(tuple({SV("save_deck")}),"save_completed_deck");
        require(std::filesystem::exists(u8p(std::getenv("PVP_USERDATA"))/"decks.json"),"Saved deck file is absent");
        click(tuple({SV("draft_reference")}),"open_completed_reference");
        click(tuple({SV("load_deck")}),"reload_completed_deck");
        V plan=py::m_get(state(),SV("draft_plan"),V::dict());
        require(py::m_get(plan,SV("plant"),V::list()).len()>0 && py::m_get(plan,SV("zombie"),V::list()).len()>0,
            "Reloaded deck plan is empty");
        click(tuple({SV("menu"),SV("back")}),"completed_reference_back");
        click(tuple({SV("advance")}),"ready_and_start");
        require(py::in(py::m_get(view(),SV("phase")),tuple({SV("loading"),SV("battle")})),"Ready did not enter loading or battle");
        waiting_for_battle=true;
    }
    void minimal_ban() {
        V key=SV("zombie:稻草人");
        require(pm_catalog::CARDS.contains(key),"Minimal scene card absent");
        V before=getattr(room(),SY("revision"));
        reveal(key);
        click(tuple({SV("card"),key}),"minimal_strawman_preview");
        require(getattr(room(),SY("revision"))==before,"Preview committed before confirmation");
        require(py::m_get(state(),SV("pending_ban"))==key,"Preview was not captured");
        click(tuple({SV("advance")}),"minimal_confirm_ban");
        require(getattr(room(),SY("revision"))!=before,"Confirmed strawman ban did not advance revision");
        require(py::in(key,getattr(room(),SY("bans"))),"Confirmed strawman is absent from authoritative bans");
        require(py::m_get(state(),SV("pending_ban")).is_none(),"Confirmed preview was not cleared");
        row("minimal_confirm_ban_roundtrip",true);
        // Cold-cache regression: command success is insufficient if the newly
        // selected secret tab blocks its first icon render on the next frame.
        for(int frame=0;frame<12;++frame) {
            fprintf(stderr,"BEGIN POST_CONFIRM_FRAME %d tabs=%s\n",frame,dump(py::m_get(state(),SV("tabs"))).c_str());fflush(stderr);
            callm(app,SY("step"),Args{V(0.016)});
            fprintf(stderr,"END POST_CONFIRM_FRAME %d phase=%s\n",frame,text(py::m_get(view(),SV("phase"))).c_str());fflush(stderr);
        }
        row("minimal_next_twelve_render_frames",true);
    }
};
}
int main(int argc,char**argv) {
    if(argc<2)return 2;
    SDL_SetMainReady();install_crash_handler();gil::init();data::set_data_dir("extract/data");
    py::g_real_clock=true;
    require(std::getenv("PVP_USERDATA")!=nullptr,"An isolated PVP_USERDATA is mandatory");
    pg::install_pygame();init_pvp_modules();pm_app::init();
    Audit audit;audit.touch=argc>2 && std::string(argv[2])=="touch";
    for(int i=2;i<argc;++i) {
        std::string option=argv[i];
        if(option=="--minimal" || option=="fast")audit.minimal=true;
        if(option.rfind("--frame-dt=",0)==0)audit.frame_dt=std::stod(option.substr(11));
    }
    require(audit.frame_dt>=0 && audit.frame_dt<=1,"frame-dt must be between0and1second");
    std::string fatal;
    try {
        V callback=V::func([&](const Args& args)->V {
            int frame=int(args.pos.at(1).num());
            if(audit.waiting_for_battle) {
                if(py::m_get(audit.view(),SV("phase"))==SV("battle")) {
                    audit.row("complete_draft_to_battle",true,"normal loading acknowledgement completed");
                    setattr(audit.app,SY("running"),V(false));
                } else require(frame<180,"Loading acknowledgements did not complete within180frames");
                return V::none();
            }
            if(frame!=2)return V::none();
            audit.app=args.pos.at(0);setitem(audit.state(),SV("touch_mode"),V(audit.touch));
            setitem(audit.state(),SV("android"),V(audit.touch));
            if(audit.touch)setattr(audit.app,SY("android"),V(true));
            V surface=callm(getattr(getattr(audit.app,SY("pg")),SY("display")),SY("set_mode"),Args{tuple({V(1280),V(720)})});
            setattr(audit.app,SY("surface"),surface);
            setitem(audit.state(),SV("ui_scale"),V(1.0));
            callm(audit.app,SY("apply_scale"),Args{});
            audit.click(tuple({SV("menu"),SV("local")}),"create_local_room");
            audit.click(tuple({SV("confirm_map")}),"confirm_map");
            require(py::m_get(audit.view(),SV("phase"))==SV("banning"),"Map confirmation did not enter draft");
            if(audit.minimal) {
                audit.minimal_ban();setattr(audit.app,SY("running"),V(false));return V::none();
            }
            audit.all_cards();
            // Reference, persisted deck and recommendation use the same pointer path.
            audit.click(tuple({SV("draft_reference")}),"open_reference");
            audit.click(tuple({SV("save_deck")}),"save_empty_deck");
            audit.click(tuple({SV("load_deck")}),"load_saved_deck");
            audit.click(tuple({SV("menu"),SV("back")}),"reference_back");
            audit.match();
            return V::none();
        });
        pm_app::f_run(Args({},{{SY("auto_test"),callback}}));
    } catch(const std::exception&e) { fatal=e.what();fprintf(stderr,"FATAL %s\n",fatal.c_str()); }
    bool passed=fatal.empty();for(const auto& row:audit.rows)if(!row.at("passed").get<bool>())passed=false;
    json report={{"passed",passed},{"input",audit.touch?"SDL_FINGERDOWN/UP":"SDL_MOUSEBUTTONDOWN/UP"},
        {"minimal",audit.minimal},{"physical_size",{1280,720}},{"ui_scale",1.0},
        {"events_cross_update_frame",audit.minimal},{"between_input_frame_dt",audit.frame_dt},
        {"fatal",fatal},{"unique_card_previews",audit.seen.size()},{"checks",audit.rows}};
    std::ofstream out(u8p(argv[1]),std::ios::binary);out<<report.dump(2);out.close();
    fflush(nullptr);return passed && !out.fail()?0:1;
}
