// typed72_ai_observation_audit <output-directory>
// Same-session integration oracle, NOT an r22 planner/controller migration claim.
// Only the shipped typed session advances. Legacy V observation code is read-only.
// No networking, Application loop, second controller, or large image rendering.
#include "pg/pg.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_teams.h"
#include "sim/typed72_app/typed_battle.h"
#include "ui/gen/pm_lobby_room.h"
#include "ui/gen/pm_rv_observation.h"
#include "ui/gen/pm_rv_native_observation.h"
#include "ui/gen/pm_rv_realtime_controls.h"
#include "core/fsutil.h"
#include "core/gil.h"
#include "core/obj.h"
#include "data/datastore.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <limits>
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
J json(const V& value) { return J::parse(dump(value)); } // Never hide an invalid projection behind a string.
void need(bool okay, const std::string& message) { if (!okay) throw std::runtime_error(message); }
bool near(double a, double b) { return std::isfinite(a) && std::isfinite(b) && std::abs(a-b) <= 1e-8; }
std::string team(const std::string& seat) { return seat.rfind("plant", 0) == 0 ? "plant" : "zombie"; }
double wrap(double from, double to, double width) { double d = std::fmod(to-from+width/2., width); if (d<0.) d+=width; return d-width/2.; }
V object() { return V::inst(std::make_shared<PyObj>()); }

// Strict structural comparison: no sorting, dropped fields, broad rounding windows,
// or number/string/bool coercion. Both implementations retain native roundn semantics.
void differences(const J& actual, const J& expected, const std::string& path, J& out) {
    if (out.size() >= 24) return;
    if (actual.is_number() && expected.is_number()) {
        if (!near(actual.get<double>(), expected.get<double>())) out.push_back({{"path",path},{"actual",actual},{"expected",expected}});
    } else if (actual.is_object() && expected.is_object()) {
        for (auto i=expected.begin(); i!=expected.end(); ++i) {
            if (!actual.contains(i.key())) out.push_back({{"path",path+"."+i.key()},{"error","missing field"}});
            else differences(actual.at(i.key()), i.value(), path+"."+i.key(), out);
            if (out.size() >= 24) return;
        }
        for (auto i=actual.begin(); i!=actual.end(); ++i)
            if (!expected.contains(i.key())) out.push_back({{"path",path+"."+i.key()},{"error","unexpected field"}});
    } else if (actual.is_array() && expected.is_array()) {
        if (actual.size()!=expected.size()) out.push_back({{"path",path},{"actual_size",actual.size()},{"expected_size",expected.size()}});
        for (size_t i=0; i<std::min(actual.size(),expected.size()); ++i) differences(actual[i],expected[i],path+"["+std::to_string(i)+"]",out);
    } else if (actual != expected) out.push_back({{"path",path},{"actual",actual},{"expected",expected}});
}

struct Audit {
    std::filesystem::path out;
    const std::vector<std::string> planned{
        "cold_capability", "cold_reset", "typed_started", "projection_free_observe", "caches_really_invalidated",
        "duel_sample_1", "duel_sample_2", "duel_sample_3", "duel_income_positive", "duel_same_time", "match_id_default",
        "duel_reset", "shot_fixture", "shot_sample_1", "shot_sample_2", "shot_sample_3", "shot_velocity_history",
        "shot_same_time", "shot_gap_over_half_second", "duel_backend",
        "duo_four_seats_1", "duo_four_seats_2", "duo_four_seats_3", "duo_owner_counts", "duo_decks_resources",
        "duo_resource_perspective", "reset_one_seat", "reset_other_seat_history", "duo_backend",
        "coop_private_resources", "coop_shared_sky_visible", "coop_sky_without_secret_not_auto",
        "coop_shared_sky_auto_income", "coop_shared_counts", "coop_backend",
        "aiseat_paused_gate", "aiseat_production_observe", "aiseat_same_time_gate", "aiseat_resume_reset", "aiseat_backend"
    };
    std::set<std::string> completed;
    J report{{"complete",false},{"passed",false},{"checks",J::array()},{"samples",J::array()}};
    bool reached_end=false;
    void flush() {
        const std::set<std::string> expected(planned.begin(),planned.end());
        size_t passed=0; for (const auto& c:report["checks"]) if(c.at("passed").get<bool>()) ++passed;
        J unrun=J::array(); for(const auto& id:planned) if(!completed.count(id)) unrun.push_back(id);
        const bool strict=!planned.empty() && expected.size()==planned.size() && completed==expected && completed.size()==report["checks"].size();
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

struct Fixture {
    BattleHandle cold;
    V battle;
    std::string mode;
    std::map<std::string,int> seq;
    explicit Fixture(const std::string& m="duel",bool sunlight=false):mode(m) {
        // secret:蓝火 is only legal with its dependency plant:火炬树桩 (catalog.validate_deck).
        J decks{{"plant",{"plant:豌豆射手","plant:向日葵","plant:花盆","plant:火炬树桩","secret:蓝火"}},
                {"zombie",{"zombie:普通僵尸","zombie:脑光墓碑"}}};
        if(m!="duel") { decks["plant2"]={"plant:坚果","plant:双子向日葵","plant:花盆"}; }
        if(m=="duo") decks["zombie2"]={"zombie:路障僵尸","zombie:脑光墓碑"};
        if(sunlight) decks["plant2"].push_back("secret:阳光");
        cold=battle_from_scenario({{"seed",301},{"mode",m},{"decks",decks},{"clear_cooldowns",true},
            {"rules",{{"sky_interval",m=="coop"?.8:100000.},{"day_brain_interval",100000.},{"hero_hp",10000.}}}});
        // battle_from_scenario returns an unwrapped RecBattle, not the room's adapter.
        battle=typed72app::wrap_battle(cold.battle);
    }
    ~Fixture() { try { callm(battle,Sym("close"),Args{}); } catch(...) {} }
    void start() { typed72app::start_battle_session(battle); }
    V backend() const { return callm(battle,Sym("backend_audit"),Args{}); }
    V snapshot() const { return callm(battle,Sym("snapshot"),Args({},{{Sym("include_map"),V(true)}})); }
    void step(int count=3) { callm(battle,Sym("step"),Args{V(double(count))}); }
    V observe(const std::string& seat,int match=731) { return callm(battle,Sym("ai_observe"),Args{V(seat),V(double(match))}); }
    void reset(const std::string& seat) { callm(battle,Sym("reset_ai_observation"),Args{V(seat)}); }
    V command(const std::string& seat,V payload) {
        payload.at(s("seq"))=V(double(++seq[seat]));
        V error=callm(battle,Sym("command_input"),Args{V(seat),payload});
        need(!error.truthy(),"Command rejected for "+seat+": "+py_str(error)); return error;
    }
    V hero(const std::string& seat) const { return get(snapshot(),"players").get(V(seat),V::none()); }
    V resource(const std::string& seat,double amount,double dx=0.) {
        const V p=hero(seat);
        return callm(battle,Sym("resource"),Args{V(seat),V(amount),V(get(p,"x").num()+dx),V(get(p,"y").num()-30.),s("audit")});
    }
    void credit(const std::string& seat,double amount) {
        const V id=resource(seat,amount);
        if(team(seat)=="plant") command(seat,py_dict({{s("type"),s("collect")},{s("resource"),id}}));
    }
    // NativeBattle.spawn takes a TEAM (it registers _pvp_owner=side). Seat-owned
    // units must come from deploy(), the path a player's command takes.
    V spawn(const std::string& side,const char* card,double x,double y,double facing=1.) {
        need(side==team(side),std::string("spawn() needs a team, not a seat: ")+side);
        V unit=callm(battle,Sym("spawn"),Args{V(card),V(side),V(x),V(y),V(facing)});
        need(unit.truthy(),std::string("Spawn failed: ")+card+" / "+side); return unit;
    }
    // A real seat deploy command: fund it through the ordinary resource path,
    // let the room tick admit the income, then search for a cell the production
    // placement rules accept near the seat's hero. No placement rule is bypassed.
    J deploy(const std::string& seat,const char* card,double funds=200.) {
        credit(seat,funds); step(1);
        V terrain=get(snapshot(),"map"),h=hero(seat),rows=get(terrain,"tiles");
        const double tile=get(terrain,"tile_size").num(),width=get(terrain,"width").num();
        const double hx=get(h,"x").num(),hy=get(h,"y").num();
        // Ground surfaces: a solid cell whose upper neighbour is open, probed just
        // above the surface (as the shot fixture does), nearest to the hero first.
        std::vector<std::pair<double,std::pair<double,double>>> cells;
        for(int r=1;r<int(rows.len());++r) for(int c=0;c<int(rows.idx(r).len());++c) {
            if(!get(rows.idx(r).idx(c),"solid",V(false)).truthy() || get(rows.idx(r-1).idx(c),"solid",V(false)).truthy()) continue;
            const double x=(c+.5)*tile,y=r*tile-2.;
            const double d=std::hypot(wrap(hx,x,width),y-hy); if(d<tile*.75) continue; // not under the hero itself
            cells.push_back({d,{x,y}});
        }
        std::sort(cells.begin(),cells.end());
        J rejected=J::array();
        for(size_t i=0;i<cells.size()&&i<160;++i) {
            const double x=cells[i].second.first,y=cells[i].second.second;
            V r=callm(battle,Sym("placement"),Args{V(seat),V(card),V(x),V(y)});
            if(r.idx(0).truthy()||r.idx(1).is_none()) { if(rejected.size()<4) rejected.push_back(py_str(r.idx(0))); continue; }
            command(seat,py_dict({{s("type"),s("deploy")},{s("card"),V(card)},{s("x"),V(x)},{s("y"),V(y)}}));
            return {{"seat",seat},{"card",card},{"x",x},{"y",y}};
        }
        throw std::runtime_error(std::string("No legal deploy cell for ")+card+" / "+seat+": "+rejected.dump());
    }
};

V masked_snapshot(Fixture& f,const std::string& seat) {
    V snap=f.snapshot(), players=get(snap,"players");
    // Room.snapshot masks peer inputs before ObservationBuilder sees the enemy.
    for(auto kv:py::items_vec(players)) if(py_str(kv.first)!=seat) kv.second.erase(s("input"));
    if(seat!=team(seat)) snap=pm_teams::f_local_perspective(Args{snap,V(seat)});
    return snap;
}

// Test-only stable identities for copied fallback entities. Nothing is written to
// battle.g or authoritative entities. Matching uses positions/name/owner ONLY;
// actual physics vx/damage and typed observation IDs are never inputs to tracking.
struct StableEntities {
    struct Track { std::string id,name,owner; double x=0.,y=0.,vx=0.,vy=0.,time=0.; };
    std::vector<Track> previous;
    V cached=V::list(); double last=-1.; size_t serial=0;
    V sample(Fixture& f) {
        const double now=attr(f.battle,"time").num(),width=attr(f.battle,"width").num();
        if(now==last) return cached;
        V out=V::list(), raw=py::iter_list(get(attr(f.battle,"g"),"实体",V::list()));
        std::set<size_t> used; std::vector<Track> next;
        for(const auto& entity:raw.items()) {
            V name=get(entity,"名"),owner=get(entity,"_pvp_owner"),pos=get(entity,"位置");
            if(!py::in(name,pm_rv_native_observation::SHOT_NAMES) || (owner!=s("plant") && owner!=s("zombie"))) continue;
            need(pos.len()>=2,"Malformed native shot position");
            const double x=pos.idx(0).num(),y=pos.idx(1).num();
            need(std::isfinite(x)&&std::isfinite(y),"Non-finite native shot position");
            V copy=py::dict_of(entity); const V explicit_id=get(entity,"_pvp_id");
            if(!explicit_id.truthy()) {
                size_t best=previous.size(); double score=std::numeric_limits<double>::infinity(),runner=score;
                for(size_t i=0;i<previous.size();++i) {
                    const auto& p=previous[i]; if(used.count(i)||p.name!=py_str(name)||p.owner!=py_str(owner)) continue;
                    const double dt=now-p.time;
                    const double d=std::hypot(wrap(p.x+p.vx*dt,x,width),y-p.y-p.vy*dt);
                    if(d<score) { runner=score; score=d; best=i; } else runner=std::min(runner,d);
                }
                const double dt=now-last;
                if(best<previous.size() && score<=std::max(32.,2500.*dt)) {
                    need(runner-score>1e-6,"Ambiguous test-side shot identity; do not silently normalize it");
                    const auto& p=previous[best]; used.insert(best);
                    next.push_back({p.id,py_str(name),py_str(owner),x,y,wrap(p.x,x,width)/(now-p.time),(y-p.y)/(now-p.time),now});
                } else next.push_back({"audit-fallback:"+std::to_string(++serial),py_str(name),py_str(owner),x,y,0.,0.,now});
                copy.at(s("_pvp_id"))=V(next.back().id);
            }
            out.append(copy);
        }
        previous=std::move(next); cached=out; last=now; return out;
    }
};

struct Oracle {
    V builder,shots;
    void reset() { builder=V::none(); shots=V::none(); }
    V observe(Fixture& f,const std::string& seat,const V& entities,int match) {
        V snap=masked_snapshot(f,seat),terrain=get(snap,"map"),side=V(team(seat));
        if(builder.is_none()||!builder.has()) {
            builder=pm_rv_observation::new_ObservationBuilder(Args{side,get(terrain,"width"),get(terrain,"height"),get(terrain,"tile_size"),get(get(terrain,"environment"),"night",V(false))});
            shots=pm_rv_native_observation::new_NativeShotView(Args{});
        }
        V all=callm(shots,Sym("sample"),Args{entities,get(snap,"time"),get(terrain,"width")});
        V visible=callm(shots,Sym("visible"),Args{all,get(snap,"players").get(side,V::none()),get(terrain,"width")});
        snap.at(s("projectiles"))=get(snap,"projectiles",V::list())+visible;
        V obs=callm(builder,Sym("build"),Args({},{{Sym("view"),py_dict({{s("battle"),snap},{s("map"),terrain}})},{Sym("match_id"),V(double(match))}}));
        V units=get(snap,"units",V::list());
        obs.at(s("own_card_counts"))=py::dict_of(pm_rv_realtime_controls::f_own_counts(Args{units,side,f.mode=="duo"?V(seat):V::none()}));
        obs.at(s("team_card_counts"))=py::dict_of(pm_rv_realtime_controls::f_own_counts(Args{units,side}));
        return py_dict({{s("observation"),obs},{s("projectiles"),visible},{s("shots_seen"),attr(shots,"seen")}});
    }
};

struct Pairing {
    StableEntities entities;
    std::map<std::string,Oracle> seats;
    std::map<std::string,std::string> ids,reverse_ids;
    J last_actual,last_expected;
    void reset(Fixture& f,const std::string& seat) { f.reset(seat); seats[seat].reset(); }
    void normalize(J& value) const {
        if(value.is_string()) { auto p=ids.find(value.get<std::string>()); if(p!=ids.end()) value=p->second; }
        else if(value.is_array()||value.is_object()) for(auto& child:value) normalize(child);
    }
    bool sample(Audit& audit,Fixture& f,const std::string& seat,const std::string& label,int match=731) {
        const V native_entities=entities.sample(f);
        last_actual=json(f.observe(seat,match)); last_expected=json(seats[seat].observe(f,seat,native_entities,match));
        need(last_actual.is_object()&&last_actual.contains("observation")&&last_actual.contains("projectiles")&&last_actual.contains("shots_seen"),"ai_observe result contract");
        const auto& actual=last_actual.at("projectiles"); const auto& expected=last_expected.at("projectiles");
        need(actual.is_array()&&expected.is_array(),"projectiles must be lists");
        for(size_t i=0;i<std::min(actual.size(),expected.size());++i) {
            const std::string a=actual[i].at("id").get<std::string>(),e=expected[i].at("id").get<std::string>();
            if(e.rfind("visible-shot:audit-fallback:",0)!=0) continue;
            // Only numeric native fallback IDs may differ. Enforce a persistent bijection.
            const std::string prefix="visible-shot:";
            need(a.rfind(prefix,0)==0 && a.size()>prefix.size() && std::all_of(a.begin()+prefix.size(),a.end(),[](char c){return c>='0'&&c<='9';}),"Unexpected non-fallback shot id: "+a);
            need(actual[i].at("asset")==expected[i].at("asset") && actual[i].at("side")==expected[i].at("side") &&
                near(actual[i].at("x").get<double>(),expected[i].at("x").get<double>()) && near(actual[i].at("y").get<double>(),expected[i].at("y").get<double>()),"Cannot pair shots out of order/by mismatched geometry");
            need((!ids.count(a)||ids.at(a)==e)&&(!reverse_ids.count(e)||reverse_ids.at(e)==a),"Fallback shot ID mapping is not one-to-one over time");
            ids[a]=e; reverse_ids[e]=a;
        }
        J normalized=last_actual; normalize(normalized); J diff=J::array(); differences(normalized,last_expected,"$",diff);
        audit.report["samples"].push_back({{"label",label},{"seat",seat},{"mode",f.mode},{"actual",last_actual},{"expected",last_expected},{"differences",diff}});
        return diff.empty();
    }
};

bool backend_ok(Fixture& f) {
    const V a=f.backend();
    return get(a,"backend")==s("typed72") && get(a,"session").truthy() && get(a,"typed_steps").num()>0. && get(a,"typed_commands").num()>0. &&
        get(a,"typed_tick").num()>0. && get(a,"ai_observations").num()>0. &&
        get(a,"v_tick_now")==get(a,"v_tick_at_start") && get(a,"v_native_tick_now")==get(a,"v_native_tick_at_start");
}

void duel(Audit& a) {
    Fixture f; Pairing p;
    V before=f.backend(); const bool capable=attr(f.battle,"typed_ai_observation").truthy(); V after=f.backend();
    a.check("cold_capability",capable && !get(before,"session").truthy() && !get(after,"session").truthy(),json(after));
    f.reset("plant"); after=f.backend();
    a.check("cold_reset",!get(after,"session").truthy() && get(after,"typed_steps").num()==0. && get(after,"typed_commands").num()==0. &&
        get(after,"snapshot_projections")==get(before,"snapshot_projections") && get(after,"native_projections")==get(before,"native_projections") &&
        get(after,"v_tick_now")==get(before,"v_tick_now") && get(after,"v_native_tick_now")==get(before,"v_native_tick_now"),json(after));
    f.start(); a.check("typed_started",get(f.backend(),"session").truthy(),json(f.backend()));
    // Warm BOTH caches, invalidate by an actual typed step, and do no projection
    // reads between the invalidation and the observation counter assertion.
    (void)f.snapshot(); (void)attr(f.battle,"g"); f.step(); before=f.backend();
    (void)f.observe("plant"); (void)f.observe("plant",732); after=f.backend();
    a.check("projection_free_observe",get(after,"snapshot_projections")==get(before,"snapshot_projections") &&
        get(after,"native_projections")==get(before,"native_projections") && get(after,"ai_observations").num()==get(before,"ai_observations").num()+2.,
        {{"before",json(before)},{"after",json(after)}});
    (void)f.snapshot(); (void)attr(f.battle,"g"); V refilled=f.backend();
    a.check("caches_really_invalidated",get(refilled,"snapshot_projections").num()==get(after,"snapshot_projections").num()+1. &&
        get(refilled,"native_projections").num()==get(after,"native_projections").num()+1.,json(refilled));
    p.reset(f,"plant"); p.reset(f,"zombie");
    for(int frame=1;frame<=3;++frame) {
        if(frame>1) { f.step(); f.credit("plant",13.); f.credit("zombie",21.); }
        bool okay=true;
        for(const auto& seat:{"plant","zombie"}) okay=p.sample(a,f,seat,"duel_frame_"+std::to_string(frame))&&okay;
        a.check("duel_sample_"+std::to_string(frame),okay);
    }
    a.check("duel_income_positive",p.last_actual.at("observation").at("income_per_second").get<double>()>0.,p.last_actual.at("observation"));
    const double seen=p.last_actual.at("shots_seen").get<double>();
    bool same=p.sample(a,f,"zombie","duel_same_time",812);
    a.check("duel_same_time",same && p.last_actual.at("shots_seen").get<double>()==seen && p.last_actual.at("observation").at("match_id")==812 &&
        p.last_actual.at("observation").at("strategy_plan_id")==0 && p.last_actual.at("observation").at("observation_id")==0);
    V default_result=callm(f.battle,Sym("ai_observe"),Args{s("zombie")});
    a.check("match_id_default",get(get(default_result,"observation"),"match_id").num()==0.);
    p.reset(f,"plant"); p.reset(f,"zombie");
    bool reset=p.sample(a,f,"plant","duel_after_reset");
    a.check("duel_reset",reset && p.last_actual.at("observation").at("income_per_second").get<double>()==0. && get(f.backend(),"ai_resets").num()>0.);

    // Real pea/zombie spawn admissions. Find a flat eight-tile lane, not a write
    // to g[实体] or any native entity authority. Official avatar fixture only sets
    // the observation camera's hero near the lane; it cannot create projectiles.
    V terrain=get(f.snapshot(),"map"),rows=get(terrain,"tiles"); const double tile=get(terrain,"tile_size").num();
    int rr=-1,cc=-1;
    for(int r=2;r<int(rows.len()) && rr<0;++r) for(int c=2;c+9<int(rows.idx(r).len());++c) {
        bool flat=true; for(int k=0;k<9;++k) flat=flat && get(rows.idx(r).idx(c+k),"solid",V(false)).truthy() && !get(rows.idx(r-1).idx(c+k),"solid",V(false)).truthy();
        if(flat) { rr=r; cc=c; break; }
    }
    need(rr>=0,"No flat real-shot fixture lane"); const double x=(cc+.5)*tile,y=rr*tile-2.;
    callm(f.battle,Sym("fixture_set_avatar"),Args{s("plant"),py_dict({{s("玩家位置"),V::list({V(x+3.*tile),V(y),V(0.),V(0.)})}})});
    (void)f.spawn("plant","plant:豌豆射手",x,y);
    (void)f.spawn("zombie","zombie:普通僵尸",x+8.*tile,y,-1.);
    bool found=false;
    for(int i=0;i<450 && !found;++i) {
        f.step(1); V raw=py::iter_list(get(attr(f.battle,"g"),"实体",V::list()));
        for(const auto& e:raw.items()) if(py::in(get(e,"名"),pm_rv_native_observation::SHOT_NAMES) && get(e,"_pvp_owner")==s("plant")) found=true;
    }
    a.check("shot_fixture",found,{{"maximum_room_steps",450},{"lane",{x,y}},{"backend",json(f.backend())}});
    need(found,"Real pea fixture produced no native projectile within the bound");
    p.reset(f,"plant"); double moving=0.;
    for(int frame=1;frame<=3;++frame) {
        if(frame>1) f.step(2);
        const bool okay=p.sample(a,f,"plant","shot_frame_"+std::to_string(frame));
        for(const auto& shot:p.last_actual.at("projectiles")) moving=std::max(moving,std::abs(shot.at("vx").get<double>())+std::abs(shot.at("vy").get<double>()));
        a.check("shot_sample_"+std::to_string(frame),okay && !p.last_actual.at("projectiles").empty(),{{"shots",p.last_actual.at("projectiles")}});
    }
    a.check("shot_velocity_history",moving>0. && p.last_actual.at("shots_seen").get<double>()>0.,{{"maximum_observed_speed_l1",moving},{"fallback_bijection",p.ids}});
    J shots=p.last_actual.at("projectiles"); const J seen_before=p.last_actual.at("shots_seen");
    const bool cached=p.sample(a,f,"plant","shot_same_time");
    a.check("shot_same_time",cached && shots==p.last_actual.at("projectiles") && seen_before==p.last_actual.at("shots_seen"));
    const double t=attr(f.battle,"time").num(); f.step(18);
    const bool gap=p.sample(a,f,"plant","shot_long_gap"); bool zero=true;
    for(const auto& shot:p.last_actual.at("projectiles")) zero=zero && shot.at("vx").get<double>()==0. && shot.at("vy").get<double>()==0. && shot.at("gravity").get<double>()==0.;
    a.check("shot_gap_over_half_second",gap && attr(f.battle,"time").num()-t>.5 && zero,{{"remaining_visible_shots",p.last_actual.at("projectiles").size()},{"note","Empty-after-impact is reported, not proof of nonempty long-gap velocity reset."}});
    a.check("duel_backend",backend_ok(f),json(f.backend()));
}

void duo(Audit& a) {
    Fixture f("duo"); f.start(); Pairing p;
    const std::vector<std::string> seats{"plant","plant2","zombie","zombie2"};
    for(size_t i=0;i<seats.size();++i) {
        const auto& seat=seats[i];
        (void)f.deploy(seat,i==0?"plant:向日葵":i==1?"plant:花盆":"zombie:脑光墓碑");
        f.credit(seat,double(11*(i+1))); p.reset(f,seat);
    }
    std::map<std::string,J> observations;
    for(int frame=1;frame<=3;++frame) {
        if(frame>1) { f.step(); for(size_t i=0;i<seats.size();++i) f.credit(seats[i],double(7*(i+1))); }
        bool okay=true;
        for(const auto& seat:seats) { okay=p.sample(a,f,seat,"duo_frame_"+std::to_string(frame))&&okay; observations[seat]=p.last_actual.at("observation"); }
        a.check("duo_four_seats_"+std::to_string(frame),okay);
    }
    bool owner=true; for(const auto& seat:seats) owner=owner && !observations.at(seat).at("own_card_counts").empty() &&
        observations.at(seat).at("own_card_counts")!=observations.at(seat).at("team_card_counts");
    a.check("duo_owner_counts",owner,{{"observations",observations}});
    // Each seat reads ITS OWN authoritative account (int truncation, as the
    // builder does), never the team's. Equal amounts across the two teams are a
    // legitimate coincidence, so only teammates are required to differ here.
    bool distinct=true; J money=J::object();
    for(const auto& seat:seats) {
        const double account=get(f.hero(seat),"resource").num(); const auto seen=observations.at(seat).at("resource").get<int64_t>();
        money[seat]={{"observed",seen},{"account",account}};
        distinct=distinct && std::isfinite(account) && seen==int64_t(account);
    }
    distinct=distinct && observations.at("plant").at("resource")!=observations.at("plant2").at("resource") &&
        observations.at("zombie").at("resource")!=observations.at("zombie2").at("resource") &&
        observations.at("plant").at("cards")!=observations.at("plant2").at("cards") && observations.at("zombie").at("cards")!=observations.at("zombie2").at("cards");
    a.check("duo_decks_resources",distinct,{{"resources",money}});
    // Private resource ownership swaps for secondary perspective; unit side never does.
    V r1=f.resource("plant",19.,190.),r2=f.resource("plant2",23.,190.);
    bool perspective=p.sample(a,f,"plant","duo_primary_resource") && p.sample(a,f,"plant2","duo_secondary_resource");
    V primary=masked_snapshot(f,"plant"),secondary=masked_snapshot(f,"plant2");
    auto side_of=[](const V& snap,const V& id){ V resources=py::iter_list(get(snap,"resources",V::list())); for(const auto& r:resources.items()) if(get(r,"id")==id) return get(r,"side"); return V::none(); };
    a.check("duo_resource_perspective",perspective && side_of(primary,r1)==s("plant") && side_of(secondary,r1)==s("plant2") && side_of(secondary,r2)==s("plant"),
        {{"plant_resource",json(r1)},{"plant2_resource",json(r2)}});
    // Both seats have established history. Reset ONLY plant; after positive gains
    // plant must report zero, while plant2 must retain its strictly positive rate.
    p.reset(f,"plant"); f.step(); f.credit("plant",31.); f.credit("plant2",47.);
    bool one=p.sample(a,f,"plant","reset_plant_only");
    a.check("reset_one_seat",one && p.last_actual.at("observation").at("income_per_second").get<double>()==0.);
    bool other=p.sample(a,f,"plant2","other_seat_keeps_history");
    a.check("reset_other_seat_history",other && p.last_actual.at("observation").at("income_per_second").get<double>()>0.,p.last_actual.at("observation"));
    a.check("duo_backend",backend_ok(f),json(f.backend()));
}

void coop(Audit& a,bool sunlight) {
    Fixture f("coop",sunlight); f.start(); Pairing p;
    p.reset(f,"plant"); p.reset(f,"plant2");
    if(!sunlight) {
        // Ordinary create_resource(source=audit) remains private, even in co-op.
        V id=f.resource("plant2",23.,180.); V snap=f.snapshot(); bool private_resource=false;
        for(const auto& r:py::iter_list(get(snap,"resources")).items()) if(get(r,"id")==id) private_resource=!get(r,"shared",V(false)).truthy() && get(r,"side")==s("plant2");
        bool okay=p.sample(a,f,"plant","coop_private_primary"); okay=p.sample(a,f,"plant2","coop_private_secondary")&&okay;
        a.check("coop_private_resources",private_resource && okay);
        // Real Economy::sky is what marks a resource shared. Merely calling
        // resource(..., source="sky") would NOT exercise that production path.
        bool shared=false; V shared_id;
        for(int i=0;i<60&&!shared;++i) {
            f.step(1); V frame=f.snapshot();
            for(const auto& r:py::iter_list(get(frame,"resources")).items()) if(get(r,"source")==s("sky") && get(r,"shared",V(false)).truthy()) { shared=true; shared_id=get(r,"id"); break; }
        }
        bool visible=p.sample(a,f,"plant","coop_shared_sky_primary"); visible=p.sample(a,f,"plant2","coop_shared_sky_secondary")&&visible;
        a.check("coop_shared_sky_visible",shared && visible,{{"shared_id",shared?json(shared_id):J(nullptr)}});
        std::map<std::string,std::set<std::string>> credited;
        const V log=py::iter_list(attr(f.battle,"log"));
        for(const auto& e:log.items()) if(get(e,"event")==s("income") && get(e,"source")==s("sky")) credited[py_str(get(e,"resource_id"))].insert(py_str(get(e,"side")));
        bool auto_income=false; for(const auto& item:credited) if(item.second.size()>1) auto_income=true;
        a.check("coop_sky_without_secret_not_auto",shared && !auto_income,{{"condition","two plant seats, no secret:阳光; shared sky need not auto-credit both"},{"payees_by_resource",credited}});
    } else {
        // One (secondary) sunlight holder is sufficient, but BOTH must receive
        // +15 from the same shared sky event; ordinary producer income is not shared.
        V hp=f.hero("plant"),hm=f.hero("plant2"); const double bp=get(hp,"resource").num(),bm=get(hm,"resource").num();
        bool okay=p.sample(a,f,"plant","coop_auto_baseline"); okay=p.sample(a,f,"plant2","coop_auto_baseline")&&okay;
        bool paid=false;
        for(int i=0;i<60&&!paid;++i) { f.step(1); paid=get(f.hero("plant"),"resource").num()>=bp+15. && get(f.hero("plant2"),"resource").num()>=bm+15.; }
        okay=p.sample(a,f,"plant","coop_auto_primary")&&okay; okay=p.sample(a,f,"plant2","coop_auto_secondary")&&okay;
        J credits=J::array(); std::set<std::string> payees; std::set<std::string> resources;
        const V log=py::iter_list(attr(f.battle,"log"));
        for(const auto& e:log.items()) if(get(e,"event")==s("income") && get(e,"source")==s("sky")) {
            credits.push_back(json(e)); if(near(get(e,"amount",V(0.)).num(),15.)) payees.insert(py_str(get(e,"side"))); resources.insert(py_str(get(e,"resource_id")));
        }
        a.check("coop_shared_sky_auto_income",paid && okay && payees==std::set<std::string>{"plant","plant2"} && resources.size()==1,
            {{"condition","coop, day, exactly two plant seats, plant2 has secret:阳光"},{"credits",credits}});
        (void)f.deploy("plant2","plant:花盆");
        bool counts=p.sample(a,f,"plant","coop_counts_primary");
        bool same=p.last_actual.at("observation").at("own_card_counts")==p.last_actual.at("observation").at("team_card_counts");
        counts=p.sample(a,f,"plant2","coop_counts_secondary")&&counts;
        a.check("coop_shared_counts",counts && same && !p.last_actual.at("observation").at("team_card_counts").empty() &&
            p.last_actual.at("observation").at("own_card_counts")==p.last_actual.at("observation").at("team_card_counts"));
        f.command("plant",py_dict({{s("type"),s("move")},{s("move"),V(0.)},{s("jump"),V(false)}}));
        a.check("coop_backend",backend_ok(f),json(f.backend()));
    }
}

// Keep the production battle_tick/reset_observation implementation, replace only
// agent creation with a plan recorder returning None. No controller is executed.
struct RecordingSeat final:pm_lobby_room::C_AISeat {
    V recorder;
    V m_ensure_agent(const Args&) override { return recorder; }
};
void production_seat(Audit& a) {
    Fixture f; f.start(); f.step();
    // These checks follow the observation into a recording controller, i.e. the
    // reference path. The shipped typed-control path is checked by the plan audit.
    pvz::setattr(f.battle,Sym("typed_ai_control"),V(false));
    V room=object(),app=object(),owner=object(),terrain=object(),agent=object();
    put(app,"android",V(false)); put(app,"room",room); put(owner,"app",app);
    put(room,"battle",f.battle); put(room,"paused",V(true)); put(room,"pause_votes",V::set({}));
    put(room,"disconnect_deadline",V::none()); put(room,"match_number",V(997.)); put(room,"mode",s("duel")); put(room,"map",terrain);
    put(room,"side_for",V::func([](const Args&){return s("plant");}));
    put(room,"duo",V::func([](const Args&){return V(false);}));
    put(terrain,"to_dict",V::func([&](const Args&){return get(f.snapshot(),"map");}));
    put(room,"snapshot",V::func([&](const Args&){return py_dict({{s("battle"),masked_snapshot(f,"plant")}});}));
    // battle_tick validates the (typed) plan against the seat's own deck.
    put(room,"deck_of",V::func([&](const Args& args){return get(get(get(f.snapshot(),"players"),py_str(args.pos.at(0)).c_str()),"deck");}));
    // With the typed r22 planner, the production AISeat no longer calls agent.plan;
    // the observation is consumed by the controller, so it is recorded there.
    J received=J::array(); int v_plan_calls=0; V controller=object();
    put(controller,"recovering",V(false));
    put(controller,"step",V::func([&](const Args& args){received.push_back(json(args.pos.at(2)));return V::none();}));
    put(agent,"controller",controller);
    put(agent,"plan_every",V(1.5)); put(agent,"plan",V::func([&](const Args&){++v_plan_calls;return V::none();}));
    auto seat=std::make_shared<RecordingSeat>(); V seat_v=V::inst(seat);
    pm_lobby_room::initcv_AISeat(seat.get()); seat->m___init__(Args{owner,s("audit-peer"),s("audit-seat")}); seat->recorder=agent;
    V before=f.backend(); callm(seat_v,Sym("battle_tick"),Args{room,s("plant")}); V after=f.backend();
    a.check("aiseat_paused_gate",get(after,"ai_observations")==get(before,"ai_observations"));
    put(room,"paused",V(false)); callm(seat_v,Sym("battle_tick"),Args{room,s("plant")}); after=f.backend();
    a.check("aiseat_production_observe",get(after,"ai_observations").num()>get(before,"ai_observations").num() && !received.empty() && received.back().at("match_id")==997 &&
        get(after,"ai_plans").num()>get(before,"ai_plans").num() && v_plan_calls==0,
        {{"before",json(before)},{"after",json(after)},{"v_plan_calls",v_plan_calls},{"scope","Real AISeat battle_tick branch; typed r22 plan; observation recorded at the controller (recording stub); no controller equivalence claim."}});
    before=after; callm(seat_v,Sym("battle_tick"),Args{room,s("plant")}); after=f.backend();
    a.check("aiseat_same_time_gate",get(after,"ai_observations")==get(before,"ai_observations"));
    put(room,"paused",V(true)); callm(seat_v,Sym("battle_tick"),Args{room,s("plant")});
    f.step(); f.credit("plant",17.); before=f.backend(); put(room,"paused",V(false));
    callm(seat_v,Sym("battle_tick"),Args{room,s("plant")}); after=f.backend();
    a.check("aiseat_resume_reset",get(after,"ai_resets").num()>get(before,"ai_resets").num() && get(after,"ai_observations").num()>get(before,"ai_observations").num() &&
        received.size()>=2 && received.back().at("income_per_second").get<double>()==0. && v_plan_calls==0,{{"observations_at_controller",received},{"v_plan_calls",v_plan_calls}});
    a.check("aiseat_backend",backend_ok(f),json(f.backend()));
}
}

int main(int argc,char** argv) {
    if(argc!=2) { std::fprintf(stderr,"Usage: typed72_ai_observation_audit <output-directory>\n"); return 2; }
    Audit audit;
    try {
        audit.out=std::filesystem::absolute(u8p(argv[1])); std::filesystem::create_directories(audit.out/"userdata");
        audit.report["scope"]="Typed Session observation integration against V ObservationBuilder/NativeShotView on the SAME session. Native roundn retained; absolute numeric tolerance 1e-8; only fallback shot IDs normalized bijectively.";
        audit.report["limitations"]={"No full r22 planner/controller migration claim", "No Android, network, rendering or gameplay acceptance", "Birth/impact may empty long-gap samples; report discloses this", "Production AISeat observer branch is tested with a recording planner, not a second controller"};
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
        pm_rv_observation::init(); pm_rv_native_observation::init(); pm_rv_realtime_controls::init(); pm_lobby_room::init();
        duel(audit); duo(audit); coop(audit,false); coop(audit,true); production_seat(audit);
        audit.reached_end=true; audit.flush();
    } catch(const std::exception& e) {
        audit.report["fatal_error"]=e.what(); audit.reached_end=false;
        try { if(!audit.out.empty()) audit.flush(); } catch(const std::exception& report_error) { std::fprintf(stderr,"REPORT_WRITE_FAIL %s\n",report_error.what()); }
        std::fprintf(stderr,"TYPED72_AI_OBSERVATION_AUDIT FAIL: %s\n",e.what()); return 1;
    } catch(...) {
        audit.report["fatal_error"]="Unknown exception"; audit.reached_end=false;
        try { if(!audit.out.empty()) audit.flush(); } catch(...) {}
        std::fprintf(stderr,"TYPED72_AI_OBSERVATION_AUDIT FAIL: unknown exception\n"); return 1;
    }
    const bool passed=audit.report.at("passed").get<bool>();
    std::fprintf(stderr,"TYPED72_AI_OBSERVATION_AUDIT %s %zu/%zu\n",passed?"PASS":"FAIL",audit.report.at("pass_count").get<size_t>(),audit.planned.size());
    return passed?0:1;
}
