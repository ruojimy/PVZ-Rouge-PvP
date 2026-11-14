#pragma once
// One typed PvP72 simulation: room steps, native ticks, native draw commands and
// snapshots run in the persistent C++ composition, admitted once from owned cold data.
// This interface has no V dependency. Outer UI/AI orchestration is a separate boundary;
// a typed simulation session alone does not prove that the outer AI is V-free.
#include "sim/typed72_app/cold_data.h"
#include "sim/typed/ai_observation_builder.h"
#include "sim/typed72_app/ai_planner_r22.h"
#include "sim/typed72_app/ai/view.h"
#include <functional>
#include <memory>
#include <optional>
namespace pvz::typed72 {struct NativeFrame;}
namespace pvz::typed72app {
// Owned values from the authoritative typed match. No spans or native handles
// escape a sample; the legacy planner/controller may project these at its exit.
struct AiObservationPacket {
    typed72::AiObservation observation;
    std::vector<typed72::AiVisibleShot> visible_shots;
    typed72::AiCardCounts own_counts,team_counts;
    uint64_t shots_seen=0;
};
// Cheap value observation of authoritative clocks. Reading a clock must not
// serialize all units, draw commands, terrain or events through JSON/V.
struct SessionClock {
    int64_t room_tick=0,native_tick=0,terrain_revision=0;
    double time=0.;
    bool deathmatch=false;
};
class Session {
public:
    virtual ~Session()=default;
    // NativeBattle.command_input: "" on success, otherwise the rejection text.
    virtual std::string command(const std::string& side,const nlohmann::json& payload)=0;
    virtual void clear_input(const std::string& side)=0;
    virtual void step()=0;                       // one room tick, including its final display frame
    virtual nlohmann::json snapshot(bool include_frame=true)=0;
    virtual const typed72::NativeFrame& native_frame()const=0;
    virtual nlohmann::json reference_native_frame()const=0; // explicit differential verification
    // Battle event log, read incrementally. The composition keeps it in its own json type
    // (ordered_json), so entries are converted by value; never hand out a reference.
    virtual size_t log_size()const=0;
    virtual nlohmann::json log_entry(size_t index)const=0;
    virtual int64_t tick()const=0;
    virtual SessionClock clock()const=0;
    // Read only typed published facts, with independent shot/income history per
    // owner seat. plan_id and observation_id remain zero; reset affects one seat.
    virtual AiObservationPacket ai_observe(typed72::Seat owner,int64_t match_id=0)=0;
    virtual void reset_ai_observation(typed72::Seat owner)=0;
    // The shipped r22 strategy planner, run on typed published facts of the owner
    // seat's local perspective. Its memory (mode, pressure clocks, peaks) is per
    // owner seat and survives pauses; reset only when the seat's agent is rebuilt.
    // recovering is the still-V controller's Recovery flag (boundary input).
    virtual AiPlanR22 ai_plan(typed72::Seat owner,bool recovering)=0;
    virtual void reset_ai_planner(typed72::Seat owner)=0;
    virtual const AiPlannerR22* ai_planner(typed72::Seat owner)const=0;   // audit evidence
    // The r22 controller port, one layer at a time ("v7"/"z7"; later layers follow).
    // Runs on a view frozen at call time, with the owner's last observation (ai_observe)
    // and last plan (ai_plan); every input goes out through send (AISeat.send ->
    // Room.command), so the room still validates and records it. Returns the
    // controller's log (Python Counter) for evidence.
    using AiSend=std::function<std::string(const std::string& kind,const ai::Args& data)>;
    virtual const std::map<std::string,double>& ai_control(typed72::Seat owner,const std::string& layer,AiSend send)=0;
    virtual void reset_ai_controller(typed72::Seat owner)=0;
    virtual bool ai_controller_recovering(typed72::Seat owner)const=0;
    virtual ai::View ai_control_view(typed72::Seat owner)=0;
    virtual bool finished()const=0;               // a result is settled; step() is a no-op
    // snapshot()["result"] / snapshot().get("surrender_requests", {}) alone: per-tick
    // readers (AISeat) must not pay a whole-world projection for these two facts.
    virtual nlohmann::json result_json()const=0;
    virtual nlohmann::json surrender_requests_json()const=0;
    virtual void set_ai_subsidy_seats(const std::vector<std::string>&)=0;
    // NativeBattle.placement: [error or null, plan or null] for deploying key at (x, y).
    virtual nlohmann::json placement(const std::string& side,const std::string& key,double x,double y,
                                     const nlohmann::json& grave,const nlohmann::json& copy)=0;
    // Tutorial lesson hooks (pm_tutorial put_grave_to_sleep / grave_awake), on the typed grave:
    // set a producing grave's idle clock; and "awake" = missing, dead or no longer drowsy.
    virtual bool tutorial_sleep_grave(const std::string& id,double idle_seconds)=0;
    virtual bool grave_awake(const std::string& id)=0;
    // Read-only typed projection in NativeBattle's record format: {"g":{植物,僵尸,实体},"avatars":{...}}.
    virtual nlohmann::json native_view()=0;
    // NativeBattle.native_cost_ratio: smoothed real seconds per game second of native ticks.
    virtual std::optional<double> native_cost_ratio()const=0;
    // Acceptance fixtures (pm_smoke --smoke-report): place a zombie, merge an avatar state dict
    // (physics.make_state) into a typed hero, and republish (NativeBattle._sync_public).
    virtual bool fixture_place_zombie(const std::string& id,double x,double y,double facing)=0;
    virtual void fixture_set_avatar(const std::string& side,const nlohmann::json& state)=0;
    virtual void sync_public()=0;
    // White-box record writes (battle._native_objects[id][k]=v, avatars[side].update(...)) applied
    // to the typed object; throws for a key the record view cannot write.
    virtual void native_set(bool avatar,const std::string& id,const nlohmann::json& fields)=0;
    // Acceptance fixture only: retain an actually generated projectile, optionally
    // isolate it and change its motion; kind, source, damage and RNG stay intact.
    virtual void fixture_entity(size_t index,const nlohmann::json& fields,bool keep_only)=0;
    // NativeBattle.spawn(card, side, x, y, facing, temporary): unit id or nullopt.
    virtual std::optional<std::string> spawn(const std::string& key,const std::string& side,double x,double y,double facing,bool temporary)=0;
    // engine.rng state: {"mt":[624 words],"mti":index}.
    virtual nlohmann::json rng_state()const=0;
    // NativeBattle.resource(side, amount, x, y, source): the typed resource admission; returns its id.
    virtual std::string create_resource(const std::string& side,double amount,double x,double y,const std::string& source)=0;
    // snapshot()["players"] alone (the live player dicts are refreshed from it after each change).
    virtual nlohmann::json players()=0;
    // Writes through battle.players[side] (resource, cooldowns) and battle.time / battle.deathmatch.
    virtual void fixture_player(const std::string& side,const nlohmann::json& fields)=0;
    virtual void fixture_clock(const nlohmann::json& fields)=0;
    virtual void fixture_tile(int64_t row,int64_t col,const nlohmann::json& cell)=0;
    // battle.map["tiles"] (the published cells) and a g["ditu"] native record write.
    virtual nlohmann::json map_tiles()=0;
    virtual void fixture_ditu(int64_t row,int64_t col,const nlohmann::json& cell)=0;
    virtual int64_t terrain_revision()const=0;
    virtual std::optional<bool> coop_map_night()const=0;
    virtual nlohmann::json performance_counters()const=0;
    // Read-only live container lengths, for memory diagnostics only. These are
    // not serialized into combat snapshots, replay state or hash inputs.
    virtual nlohmann::json fixture_retention()const=0;
    virtual nlohmann::json events(size_t n)const=0;   // Simulation.events[-n:]
    static std::unique_ptr<Session> create(ColdExport cold,const std::string& map_name);
};
} // namespace pvz::typed72app
