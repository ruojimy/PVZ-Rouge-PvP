#pragma once
// Typed port of the shipped r22 strategy planner (Agent.plan, every 1.5 s): the
// effective chain r15 -> r12 -> r10 -> r9 -> r8 -> r7 -> r2 (plant) / r3 (zombie),
// from modkit/pvp/rv_r*.py. Production parameters only: variant "" (no params)
// plus r13's siege_guard=0 default, which makes r12's siege veto a no-op.
// Draft/BP (cold) stays out of this file. No V, JSON or snapshot input: the
// Session fills AiPlannerInput from its typed authoritative state.
#include "sim/typed/ai_observation.h"
#include <cstdint>
#include <map>
#include <optional>
#include <span>
#include <string>
#include <utility>
#include <vector>

namespace pvz::typed72app {

// The facts plan() reads from players[side] / players[foe] of the seat's local
// perspective snapshot (the own seat is "me"; the foe is the enemy main seat).
struct AiPlannerHero {
    double x=0.,y=0.,hp=0.,max_hp=0.,resource=0.;
};

struct AiPlannerInput {
    typed72::Seat side=typed72::Seat::plant;       // team
    double time=0.,width=0.;
    AiPlannerHero me,foe;
    std::span<const std::string> deck;             // own seat's deck, secrets included
    std::span<const typed72::AiUnitView> units;    // published units, both teams
    bool recovering=false;                         // controller.recovering (front7.Recovery)
};

// The plan dict r22 returns, before AISeat.validate_plan. Keys are emitted in the
// order Python builds them (plant: r2 dict then r7 update; zombie: r3 dict then
// r7 update, then optional save / mode).
struct AiPlanR22 {
    typed72::Seat side=typed72::Seat::plant;
    std::vector<std::string> priority;
    std::vector<std::pair<std::string,double>> quotas;   // insertion order
    std::optional<std::string> mode;                      // plant always; zombie on balloon hp
    // plant
    double econ_goal=0.,wall_goal=0.,reserve=0.,siege_gap=0.,teleport_hp=0.,panic_value=0.,bomb_value=0.;
    double siege_step=0.,siege_dwell=0.,siege_lobs=0.,rich=0.,vine_reserve=0.;
    bool global_collect=false;
    // zombie
    double grave_start=0.,grave_max=0.,grave_every=0.,save_horizon=0.,wave_base=0.,wave_growth=0.;
    double wave_cap=0.,wave_hold_max=0.,tend_every=0.,detonate_value=0.;
    std::optional<bool> save;
};

// The strategy memory a planner carries from one plan to the next (r22: Agent.mode,
// last_pressure_at, last_enemy_hp, last_attack_at, push_until, peak_econ, peak_graves).
// A plain value so a recorded plan can be recomputed offline from (input, memory).
struct AiPlannerMemory {
    std::string mode="defend";
    double last_pressure_at=0.,last_enemy_hp=40.,last_attack_at=0.,push_until=0.;
    int64_t peak_econ=0,peak_graves=0;
};

// A seat's strategy planner as the Session drives it: published facts in, plan dict out.
// AiPlannerR22 is the shipped implementation and the Session's default; another planner
// (a network) is injected with Session::set_ai_planner_factory.
class IPlanner {
public:
    virtual ~IPlanner()=default;
    virtual AiPlanR22 plan(const AiPlannerInput&)=0;
    virtual typed72::Seat side()const=0;
    virtual const char* name()const=0;
    virtual AiPlannerMemory memory()const=0;
    virtual void set_memory(const AiPlannerMemory&)=0;
};

class AiPlannerR22 final:public IPlanner {
public:
    explicit AiPlannerR22(typed72::Seat side);
    AiPlanR22 plan(const AiPlannerInput&)override;
    typed72::Seat side()const override{return side_;}
    const char* name()const override{return "r22";}
    AiPlannerMemory memory()const override{return {mode_,last_pressure_at_,last_enemy_hp_,last_attack_at_,push_until_,peak_econ_,peak_graves_};}
    void set_memory(const AiPlannerMemory& m)override{
        mode_=m.mode;last_pressure_at_=m.last_pressure_at;last_enemy_hp_=m.last_enemy_hp;last_attack_at_=m.last_attack_at;
        push_until_=m.push_until;peak_econ_=m.peak_econ;peak_graves_=m.peak_graves;
    }
    const std::string& mode()const{return mode_;}
    // Agent.notes counters and branch hits; audit evidence only, never projected.
    const std::map<std::string,int64_t>& notes()const{return notes_;}
private:
    typed72::Seat side_;
    std::string mode_="defend";
    double last_pressure_at_=0.,last_enemy_hp_=40.,last_attack_at_=0.,push_until_=0.;
    int64_t peak_econ_=0,peak_graves_=0;
    std::map<std::string,int64_t> notes_;
    bool ahead(const AiPlannerInput&)const;
    int64_t econ_goal(const AiPlannerInput&);
    void grave_plan(const AiPlannerInput&,AiPlanR22&);
    void hit(const char* key){++notes_[key];}
};

} // namespace pvz::typed72app
