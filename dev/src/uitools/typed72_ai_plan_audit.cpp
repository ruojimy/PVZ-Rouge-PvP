// typed72_ai_plan_audit <output-directory>
// Shipped AISeat (real ensure_agent + battle_tick, real r22 agent and V controller)
// on a typed battle with AI on every seat. Production plans with the typed r22
// planner (battle.ai_plan). Immediately BEFORE each battle_tick that will plan,
// the V r22 Agent.plan runs on the identical room snapshot as an oracle; the
// plan the seat then adopts must equal validate_plan(V plan) exactly (keys, key
// order, values). The oracle's V agent is the seat's own agent, so its memory
// evolves exactly as it would on the old V path.
// Scope: the r22 planner only. The controller that executes plans is still V.
#include "pg/pg.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_teams.h"
#include "sim/typed72_app/typed_battle.h"
#include "ui/gen/pm_lobby_room.h"
#include "ui/gen/pm_rv_realtime_controls.h"
#include "core/fsutil.h"
#include "core/gil.h"
#include "core/obj.h"
#include "data/datastore.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

using namespace pvz;
namespace {
using J = nlohmann::json;
V s(const char* text) { return V(text); }
V get(const V& value, const char* key, V fallback = V::none()) { return py::m_get(value, s(key), fallback); }
V attr(const V& value, const char* key) { return pvz::getattr(value, Sym(key)); }
void put(const V& value, const char* key, const V& field) { pvz::setattr(value, Sym(key), field); }
J json(const V& value) { return J::parse(dump(value)); }
void need(bool okay, const std::string& message) { if (!okay) throw std::runtime_error(message); }
std::string team(const std::string& seat) { return seat.rfind("plant", 0) == 0 ? "plant" : "zombie"; }
V object() { return V::inst(std::make_shared<PyObj>()); }
V json_v(const V& battle) { return get(callm(battle,Sym("snapshot"),Args({},{{Sym("include_map"),V(false)}})),"players"); }

struct Audit {
    std::filesystem::path out;
    std::vector<std::string> planned;
    std::set<std::string> completed;
    J report{{"complete",false},{"passed",false},{"checks",J::array()},{"scenarios",J::object()}};
    bool reached_end=false;
    void flush() {
        size_t passed=0; for (const auto& c:report["checks"]) if(c.at("passed").get<bool>()) ++passed;
        J unrun=J::array(); for(const auto& id:planned) if(!completed.count(id)) unrun.push_back(id);
        const bool strict=!planned.empty() && completed.size()==planned.size() && completed.size()==report["checks"].size();
        report["planned_checks"]=planned; report["planned_count"]=planned.size(); report["completed_checks"]=completed.size();
        report["pass_count"]=passed; report["fail_count"]=report["checks"].size()-passed;
        report["unrun_checks"]=unrun; report["unrun_count"]=unrun.size(); report["strict_check_accounting"]=strict;
        report["complete"]=reached_end && strict;
        report["passed"]=reached_end && strict && passed==planned.size() && !report.contains("fatal_error");
        report["outcome"]=report["passed"].get<bool>()?"PASS":"FAIL";
        std::ofstream stream(out/"report.json",std::ios::binary); need(bool(stream),"Cannot open report.json");
        stream << report.dump(2) << '\n'; stream.flush(); need(bool(stream),"Cannot write report.json");
    }
    void check(const std::string& id,bool okay,const J& evidence=J::object()) {
        need(std::find(planned.begin(),planned.end(),id)!=planned.end(),"Unplanned check: "+id);
        need(completed.insert(id).second,"Duplicate completed check: "+id);
        report["checks"].push_back({{"id",id},{"passed",okay},{"evidence",evidence}});
        std::fprintf(stderr,"%s %s\n",okay?"PASS":"FAIL",id.c_str()); std::fflush(stderr); flush();
    }
};

struct SeatRun {
    std::string seat;
    std::shared_ptr<pm_lobby_room::C_AISeat> impl;
    V v;
    size_t compared=0,mismatches=0;
    J first_mismatches=J::array();
    std::map<std::string,size_t> modes;
};

// A room exposing exactly what AISeat.ensure_agent / battle_tick read. The battle is
// the typed adapter; inputs go to battle.command_input like Room.command('input').
struct Match {
    std::string name,mode;
    BattleHandle cold;
    V battle,room,app,owner,terrain;
    J decks;
    std::vector<SeatRun> seats;
    std::map<std::string,std::string> peer_seat;
    J rejected=J::array();
    bool typed_control=false;
    Match(const std::string& n,const std::string& m,const J& scenario,const std::vector<std::string>& ai,bool control=false):name(n),mode(m),typed_control(control) {
        cold=battle_from_scenario(scenario);
        battle=typed72app::wrap_battle(cold.battle);
        typed72app::start_battle_session(battle);
        // This audit compares the typed planner with V Agent.plan on the reference path
        // (typed observation + typed plan + V controller); see aiseat_typed_control below.
        pvz::setattr(battle,Sym("typed_ai_control"),V(typed_control));
        decks=json(attr(battle,"players"));   // seat -> player dict; decks are read below
        J deck_map=J::object(); for(auto it=decks.begin();it!=decks.end();++it) deck_map[it.key()]=it.value().at("deck");
        decks=deck_map;
        room=object(); app=object(); owner=object(); terrain=object();
        put(app,"android",V(false)); put(app,"room",room); put(app,"bridge",cold.bridge); put(owner,"app",app);
        put(owner,"is_human_seat",V::func([](const Args&){return V(false);}));
        const V map=attr(battle,"map");
        put(terrain,"environment",get(map,"environment",V::dict())); put(terrain,"terrain_hash",s("typed72-plan-audit"));
        V battle_ref=battle;
        put(terrain,"to_dict",V::func([battle_ref](const Args&){return py::deepcopy(attr(battle_ref,"map"));}));
        put(room,"battle",battle); put(room,"paused",V(false)); put(room,"pause_votes",V::set({})); put(room,"pause_epoch",V(0.));
        put(room,"disconnect_deadline",V::none()); put(room,"match_number",V(1.)); put(room,"mode",V(mode)); put(room,"map",terrain);
        put(room,"map_id",s("audit")); put(room,"seed",V(scenario.value("seed",1.0))); put(room,"draft_schedule",V::list({}));
        put(room,"revision",V(0.)); put(room,"phase",s("battle")); put(room,"audit_error",V::none());
        V deck_v=V::dict(); for(auto it=decks.begin();it!=decks.end();++it){V l=V::list();for(const auto& k:it.value())l.append(V(k.get<std::string>()));deck_v.at(V(it.key()))=l;}
        put(room,"decks",deck_v);
        for(const auto& seat:ai) peer_seat["peer-"+seat]=seat;
        auto seats_of=peer_seat;
        put(room,"side_for",V::func([seats_of](const Args& a){auto f=seats_of.find(py_str(a.pos.at(0)));return f==seats_of.end()?V::none():V(f->second);}));
        put(room,"duo",V::func([m](const Args&){return V(m=="duo");}));
        put(room,"deck_of",V::func([deck_v](const Args& a){return deck_v.get(a.pos.at(0),V::list());}));
        V b=battle;
        put(room,"snapshot",V::func([b,seats_of](const Args& a){
            // Room.snapshot(for_peer, include_map, copy_state): peers' inputs masked as {}.
            const std::string seat=seats_of.at(py_str(a.pos.at(0)));
            V include=a.get(1,Sym("include_map"),nullptr), copy=a.get(2,Sym("copy_state"),nullptr);
            V snap=callm(b,Sym("snapshot"),Args({},{{Sym("include_map"),include.has()?include:V(true)},{Sym("copy_state"),copy.has()?copy:V(true)}}));
            for(auto kv:py::items_vec(get(snap,"players"))) if(py_str(kv.first)!=seat) kv.second.at(s("input"))=V::dict();
            return py_dict({{s("battle"),snap},{s("bans"),py::list(pvz::getattr(b,Sym("bans"),V::list()))},{s("rules"),py::deepcopy(attr(b,"rules"))}});
        }));
        J* rej=&rejected;
        put(room,"command",V::func([b,seats_of,rej](const Args& a){
            const std::string seat=seats_of.at(py_str(a.pos.at(0))); V payload=a.pos.at(1);
            need(get(payload,"type")==s("input"),"audit room only routes inputs");
            V error=callm(b,Sym("command_input"),Args{V(seat),get(payload,"input")});
            if(error.truthy()&&rej->size()<40) rej->push_back({{"seat",seat},{"input",json(get(payload,"input"))},{"error",py_str(error)}});
            return error;
        }));
        for(const auto& [peer,seat]:peer_seat) {
            SeatRun run; run.seat=seat; run.impl=std::make_shared<pm_lobby_room::C_AISeat>(); run.v=V::inst(run.impl);
            pm_lobby_room::initcv_AISeat(run.impl.get()); run.impl->m___init__(Args{owner,V(peer),V("audit-"+seat)});
            // The battle_tick key for this room/battle, so the agent built now is kept.
            put(run.v,"battle_key",V::tuple({py::id(room),py::id(battle)}));
            (void)callm(run.v,Sym("ensure_agent"),Args{});
            seats.push_back(std::move(run));
        }
    }
    ~Match() { try { callm(battle,Sym("close"),Args{}); } catch(...) {} }
    double time() const { return attr(battle,"time").num(); }
    bool finished() const { return !attr(battle,"result").is_none(); }
    V backend() const { return callm(battle,Sym("backend_audit"),Args{}); }
    // The V oracle: Agent.plan on the snapshot battle_tick is about to build.
    V oracle_plan(SeatRun& r) {
        const std::string side=team(r.seat);
        V snap=callm(room,Sym("snapshot"),Args({V("peer-"+r.seat)},{{Sym("include_map"),V(false)},{Sym("copy_state"),V(false)}}));
        if(r.seat!=side) snap.at(s("battle"))=pm_teams::f_local_perspective(Args{get(snap,"battle"),V(r.seat)});
        snap.at(s("map"))=attr(battle,"map");
        V agent=attr(r.v,"agent");
        // r2..r15 plan() never read ctx['obs'] (the observation feeds the controller only).
        V raw=callm(agent,Sym("plan"),Args{py_dict({{s("match"),r.v},{s("side"),V(side)},{s("snap"),snap},{s("obs"),V::none()},{s("plan"),attr(r.v,"plan")}})});
        return pm_rv_realtime_controls::f_validate_plan(Args{raw,callm(room,Sym("deck_of"),Args{V(r.seat)})});
    }
    bool will_plan(SeatRun& r) {
        if(attr(room,"paused").truthy()) return false;
        // Resuming: battle_tick calls reset_observation (plan=None, next_ctl=0) first.
        if(attr(r.v,"was_paused").truthy()) return true;
        const double t=time();
        if(t<attr(r.v,"next_ctl").num()) return false;
        V plan=attr(r.v,"plan");
        return plan.is_none() || t-attr(r.v,"plan_at").num()>=pvz::getattr(attr(r.v,"agent"),Sym("plan_every"),V(2.)).num();
    }
    void tick_all() {
        for(auto& r:seats) {
            V expected; const bool planning=will_plan(r);
            if(planning) expected=oracle_plan(r);
            const double before=attr(r.v,"plan_at").num();
            (void)callm(r.v,Sym("battle_tick"),Args{room,V(r.seat)});
            const bool planned=attr(r.v,"plan_at").num()!=before;
            need(planned==planning,"Plan boundary prediction failed for "+r.seat);
            if(!planned) continue;
            const std::string want=dump(expected),got=dump(attr(r.v,"plan"));
            ++r.compared; ++r.modes[py_str(get(attr(r.v,"plan"),"mode",s("-")))];
            if(want!=got) { ++r.mismatches; if(r.first_mismatches.size()<6) r.first_mismatches.push_back({{"time",time()},{"expected",J::parse(want)},{"actual",J::parse(got)}}); }
        }
    }
    void run(double until,int room_steps_per_tick=1) {
        while(time()<until && !finished()) { callm(battle,Sym("step"),Args{V(double(room_steps_per_tick))}); tick_all(); }
    }
    J summary() const {
        J seats_j=J::object(); const V audit=backend();
        for(const auto& r:seats) {
            J modes=J::object(); for(const auto& [k,n]:r.modes) modes[k]=n;
            seats_j[r.seat]={{"compared",r.compared},{"mismatches",r.mismatches},{"first_mismatches",r.first_mismatches},{"modes",modes},
                {"plan_rejections",json(pvz::getattr(r.v,Sym("plan_rejections"),V(0.)))}};
        }
        return {{"mode",mode},{"time",time()},{"finished",finished()},{"result",json(attr(battle,"result"))},{"seats",seats_j},
            {"backend",json(audit)},{"rejected_inputs_sample",rejected}};
    }
    bool all_equal(size_t minimum) const {
        for(const auto& r:seats) if(r.compared<minimum || r.mismatches || pvz::getattr(r.v,Sym("plan_rejections"),V(0.)).num()!=0.) return false;
        return true;
    }
    size_t compared() const { size_t n=0; for(const auto& r:seats) n+=r.compared; return n; }
};

bool typed_path(const Match& m) {
    const V a=m.backend();
    return get(a,"backend")==s("typed72") && get(a,"session").truthy() && get(a,"ai_plans").num()==double(m.compared()) &&
        get(a,"v_tick_now")==get(a,"v_tick_at_start") && get(a,"v_native_tick_now")==get(a,"v_native_tick_at_start");
}
J notes_of(const Match& m) { return json(get(m.backend(),"ai_planner_notes",V::dict())); }
J deck(std::initializer_list<const char*> keys) { J out=J::array(); for(const char* k:keys) out.push_back(k); return out; }

void duel(Audit& a,const std::string& id,const J& rules,double until,double hero_hp,double zombie_hp=0.) {
    J sc{{"seed",17},{"mode","duel"},{"decks",{{"plant",deck({"plant:向日葵","plant:豌豆射手","plant:坚果","plant:樱桃炸弹","plant:卷心菜投手","plant:花盆","plant:双发射手"})},
        {"zombie",deck({"zombie:脑光墓碑","zombie:普通僵尸","zombie:路障僵尸","zombie:铁桶僵尸","zombie:撑杆跳僵尸","zombie:坚固脑光墓碑","zombie:橄榄球僵尸"})}}},{"rules",rules}};
    if(hero_hp>0.) sc["rules"]["hero_hp"]=hero_hp;
    Match m(id,"duel",sc,{"plant","zombie"});
    // Fixture: a wounded zombie Dave. Hero HP lives in the native avatar state
    // (玩家血量); the official avatar fixture writes it into the typed hero and the
    // next room tick publishes it to players[zombie].hp before any plan is made.
    if(zombie_hp>0.) {
        callm(m.battle,Sym("fixture_set_avatar"),Args{s("zombie"),py_dict({{s("玩家血量"),V(zombie_hp)}})});
        callm(m.battle,Sym("step"),Args{V(1.)});
        need(get(get(json_v(m.battle),"zombie"),"hp").num()==zombie_hp,"zombie hp fixture did not reach the typed player");
    }
    m.run(until);
    J s=m.summary(); s["planner_notes"]=notes_of(m); a.report["scenarios"][id]=s;
    a.check(id+"_plans_equal",m.all_equal(20),s["seats"]);
    a.check(id+"_typed_path",typed_path(m),s["backend"]);
}

void duel_lifecycle(Audit& a) {
    const std::string id="duel_lifecycle";
    J sc{{"seed",29},{"mode","duel"},{"decks",{{"plant",deck({"plant:向日葵","plant:豌豆射手","plant:坚果","plant:花盆"})},{"zombie",deck({"zombie:脑光墓碑","zombie:普通僵尸","zombie:路障僵尸"})}}}};
    Match m(id,"duel",sc,{"plant","zombie"});
    m.run(40.);
    // Pause: the seat must not plan; on resume only the observation resets, the
    // strategy memory (V agent and typed planner alike) is kept.
    const double resets_before=get(m.backend(),"ai_planner_resets").num();
    put(m.room,"paused",V(true)); for(int i=0;i<30;++i) m.tick_all(); put(m.room,"paused",V(false));
    m.run(80.);
    const bool pause_kept=get(m.backend(),"ai_planner_resets").num()==resets_before && m.all_equal(10);
    a.check(id+"_pause_keeps_strategy",pause_kept,m.summary()["seats"]);
    // Rematch key: ensure_agent builds a fresh V agent and resets the typed planner.
    put(m.room,"match_number",V(2.));
    for(auto& r:m.seats) (void)callm(r.v,Sym("ensure_agent"),Args{});
    const double resets_after=get(m.backend(),"ai_planner_resets").num();
    m.run(140.);
    J s=m.summary(); s["planner_notes"]=notes_of(m); a.report["scenarios"][id]=s;
    a.check(id+"_rebuild_resets_planner",resets_after==resets_before+double(m.seats.size()) && m.all_equal(20),{{"resets_before",resets_before},{"resets_after",resets_after},{"seats",s["seats"]}});
}

// The shipped path: AISeat.battle_tick -> battle.ai_tick (typed observe, plan, control).
// No oracle here (the controller is shadow-audited by typed72_ai_control_audit); this
// checks the production wiring: inputs flow through AISeat.send/Room.command, nothing
// throws, and the AI builds no V room snapshot per control tick.
void aiseat_typed(Audit& a) {
    const std::string id="aiseat_typed_control";
    J sc{{"seed",61},{"mode","duo"},{"decks",{{"plant",deck({"plant:向日葵","plant:豌豆射手","plant:坚果","plant:花盆"})},{"plant2",deck({"plant:双子向日葵","plant:卷心菜投手","plant:高坚果","plant:花盆"})},
        {"zombie",deck({"zombie:脑光墓碑","zombie:普通僵尸","zombie:路障僵尸"})},{"zombie2",deck({"zombie:成长脑光墓碑","zombie:铁桶僵尸","zombie:坚固脑光墓碑"})}}}};
    Match m(id,"duo",sc,{"plant","plant2","zombie","zombie2"},true);
    const V before=m.backend();
    while(m.time()<120.&&!m.finished()){callm(m.battle,Sym("step"),Args{V(1.)});for(auto& r:m.seats)(void)callm(r.v,Sym("battle_tick"),Args{m.room,V(r.seat)});}
    const V after=m.backend();
    J seats=J::object();bool deployed=true;std::map<std::string,double> team_deploys{{"plant",0.},{"zombie",0.}};
    for(auto& r:m.seats){
        const J log=json(callm(m.battle,Sym("ai_control_log"),Args{V(r.seat)}));
        double deploys=0;for(auto it=log.begin();it!=log.end();++it)if(it.key().rfind("deploy:",0)==0)deploys+=it.value().get<double>();
        seats[r.seat]={{"deploys",deploys},{"plan",json(attr(r.v,"plan"))},{"rejections",json(pvz::getattr(r.v,Sym("plan_rejections"),V(0.)))}};
        team_deploys[team(r.seat)]+=deploys;
    }
    // Every team acts; a single seat may legitimately idle (r22 plant2 does in V too).
    for(const auto& [t,n]:team_deploys)deployed=deployed&&n>0;
    const bool no_snapshots=get(after,"snapshot_projections")==get(before,"snapshot_projections");
    const bool ran=get(after,"ai_controls").num()>get(before,"ai_controls").num()&&get(after,"ai_plans").num()>get(before,"ai_plans").num();
    J s={{"time",m.time()},{"seats",seats},{"before",json(before)},{"after",json(after)},{"rejected_inputs_sample",m.rejected}};
    a.report["scenarios"][id]=s;
    a.check(id+"_runs",ran&&deployed,s);
    a.check(id+"_no_v_snapshots",no_snapshots,{{"snapshot_projections_before",json(get(before,"snapshot_projections"))},{"after",json(get(after,"snapshot_projections"))}});
}

void duo(Audit& a) {
    const std::string id="duo";
    J sc{{"seed",41},{"mode","duo"},{"decks",{{"plant",deck({"plant:向日葵","plant:豌豆射手","plant:坚果","plant:花盆"})},{"plant2",deck({"plant:双子向日葵","plant:卷心菜投手","plant:高坚果","plant:花盆"})},
        {"zombie",deck({"zombie:脑光墓碑","zombie:普通僵尸","zombie:路障僵尸"})},{"zombie2",deck({"zombie:成长脑光墓碑","zombie:铁桶僵尸","zombie:坚固脑光墓碑"})}}}};
    Match m(id,"duo",sc,{"plant","plant2","zombie","zombie2"});
    m.run(240.);
    J s=m.summary(); s["planner_notes"]=notes_of(m); a.report["scenarios"][id]=s;
    a.check(id+"_plans_equal",m.all_equal(20),s["seats"]);
    a.check(id+"_typed_path",typed_path(m),s["backend"]);
}

void coop(Audit& a) {
    const std::string id="coop";
    J sc{{"seed",53},{"mode","coop"},{"campaign_deck",true},{"director",{{"day",1},{"seed",53}}}};
    Match m(id,"coop",sc,{"plant","plant2"});
    m.run(200.);
    J s=m.summary(); s["planner_notes"]=notes_of(m); a.report["scenarios"][id]=s;
    a.check(id+"_plans_equal",m.all_equal(20),s["seats"]);
    a.check(id+"_typed_path",typed_path(m),s["backend"]);
}
}

int main(int argc,char** argv) {
    if(argc!=2) { std::fprintf(stderr,"Usage: typed72_ai_plan_audit <output-directory>\n"); return 2; }
    Audit audit;
    audit.planned={"duel_plans_equal","duel_typed_path","duel_long_plans_equal","duel_long_typed_path",
        "duel_rich_plans_equal","duel_rich_typed_path","duel_low_zombie_plans_equal","duel_low_zombie_typed_path",
        "duel_lifecycle_pause_keeps_strategy","duel_lifecycle_rebuild_resets_planner",
        "duo_plans_equal","duo_typed_path","coop_plans_equal","coop_typed_path","aiseat_typed_control_runs","aiseat_typed_control_no_v_snapshots"};
    try {
        audit.out=std::filesystem::absolute(u8p(argv[1])); std::filesystem::create_directories(audit.out/"userdata");
        audit.report["scope"]="Typed r22 planner vs V r22 Agent.plan, same session, same snapshot, inside the shipped AISeat; exact dump equality after validate_plan.";
        audit.report["limitations"]={"The controller that executes plans is still V (r22 tactics chain)","Variant parameters are the production empty variant only","Branch coverage is reported in planner_notes (and branch_hits), not asserted"};
        audit.flush();
#ifdef _WIN32
        _putenv_s("PVP_USERDATA",p8(audit.out/"userdata").c_str());
        _putenv_s("SDL_VIDEODRIVER","dummy"); _putenv_s("SDL_AUDIODRIVER","dummy");
#else
        setenv("PVP_USERDATA",p8(audit.out/"userdata").c_str(),1);
        setenv("SDL_VIDEODRIVER","dummy",1); setenv("SDL_AUDIODRIVER","dummy",1);
#endif
        SDL_SetMainReady(); gil::init(); data::set_data_dir("extract/data"); py::g_real_clock=true;
        pg::install_pygame(); init_pvp_modules();
        pm_rv_realtime_controls::init(); pm_teams::init(); pm_lobby_room::init();
        duel(audit,"duel",J::object(),300.,0.);
        duel(audit,"duel_long",J::object(),460.,4000.);
        // Rich banks: r7's zombie quota bump (>=700), r10/r15 rich plant branches.
        duel(audit,"duel_rich",J{{"plant_start",1000},{"zombie_start",1000}},300.,0.);
        // Zombie at 11 hp with 坚固脑光墓碑 in deck: balloon_hp is 12 -> r9 zombie mode branch.
        duel(audit,"duel_low_zombie",J::object(),60.,0.,11.);
        duel_lifecycle(audit);
        duo(audit);
        coop(audit);
        aiseat_typed(audit);
        // Branch evidence across all scenarios (typed planner counters).
        J hits=J::object();
        for(const auto& [name,scenario]:audit.report["scenarios"].items())
            for(const auto& [seat,notes]:scenario["planner_notes"].items())
                for(const auto& [key,n]:notes.items()) if(key!="mode"&&key!="grave_target") hits[key]=hits.value(key,0.)+n.get<double>();
        J expected_branches={"pushes","retreats","recovering_or_low","r8_siege","balloon_defend","econ_emergency","econ_expand","siege_wait_econ",
            "grave_expand","grave_late","zombie_pressure","zombie_rich_quotas","zombie_balloon_defend"};
        J unhit=J::array(); for(const auto& b:expected_branches) if(!hits.contains(b.get<std::string>())) unhit.push_back(b);
        audit.report["branch_hits"]=hits; audit.report["branches_not_exercised"]=unhit;
        audit.reached_end=true; audit.flush();
    } catch(const std::exception& e) {
        audit.report["fatal_error"]=e.what(); try { audit.flush(); } catch(...) {}
        std::fprintf(stderr,"TYPED72_AI_PLAN_AUDIT FAIL: %s\n",e.what()); return 1;
    }
    const bool ok=audit.report["passed"].get<bool>();
    std::fprintf(stderr,"TYPED72_AI_PLAN_AUDIT %s %zu/%zu\n",ok?"PASS":"FAIL",size_t(audit.report["pass_count"]),audit.planned.size());
    return ok?0:1;
}
