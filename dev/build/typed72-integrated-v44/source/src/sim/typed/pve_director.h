#pragma once
// Typed port of next-pvp71/modkit/pvp/pve.py WaveDirector (sha256 4e029303...)
// and coop_cycle.py CoopCycle (sha256 8305723b...). V runs these as
// src/sim/pvp/gen/pm_pve.cpp / pm_coop_cycle.cpp.
//
// bind() runs while NativeBattle is constructed, so its products (spawn points,
// zombie pool, wave plan and both seeded RNGs) arrive as cold data. Everything
// that runs during the match is here: step, _compose, fronts, _spawn, bounties,
// ladder support, clear progress and the co-op day/night grave cycle.
#include "sim/typed/cold_catalog.h"
#include "sim/typed/pve_director_state.h"
#include "sim/typed/room_public_terrain.h"
#include "sim/typed/scripted_spawn_budget.h"
#include "sim/typed/zombie_motion.h"
#include "core/pyrandom.h"
#include <map>
#include <nlohmann/json.hpp>
#include <set>
#include <variant>
namespace pvz::typed72 {
using PveValue=std::variant<bool,int64_t,double,std::string,std::vector<std::string>>;
struct PveEvent {
    std::string name;
    std::vector<std::pair<std::string,PveValue>> fields;
};
class PveDirectorServices {
public:
    virtual ~PveDirectorServices()=default;
    // battle.spawn(key,"zombie",x,y,facing) inside _ban_free_spawn with
    // _scripted_spawn_wave=wave; nullopt when the spawn returns None.
    virtual std::optional<std::string> spawn_wave_zombie(const std::string& key,Point,double facing,int64_t wave)=0;
    virtual ZombieRef native_zombie(const std::string& id)=0;
    virtual PlantRef native_plant(const std::string& id)=0;
    // battle.drop_coin(amount,x,y,kind)
    virtual void drop_coin(double amount,Point,const std::string& kind)=0;
    // battle.spawn_remnant(x,y) with no source.
    virtual ZombieRef spawn_remnant(Point)=0;
    // battle._grave_soldier_exit(card,"zombie",battle.units[grave id],1); nullopt also when the unit is unpublished.
    virtual std::optional<Point> grave_soldier_exit(const std::string& card,const std::string& grave_id)=0;
    // map.environment.night, g['天']/g['tian'] and terrain_revision += 1.
    virtual void set_daylight(bool night)=0;
    virtual void event(PveEvent)=0;
};
struct PvePoolEntry {std::string key;int tier=0;double weight=0.;};
struct PveWavePlan {double time=0.;int64_t budget=0;bool flag=false;};
// The state WaveDirector.__init__ + bind leave behind.
struct PveDirectorCold {
    int64_t day=1,seed=1,max_zombies=40;
    bool coop=false;
    std::vector<Point> points;
    std::vector<PvePoolEntry> pool;
    std::vector<PveWavePlan> plan;
    PyRandom::State rng;
    bool cycle=false,initial_night=false;
    PyRandom::State cycle_rng;
};
struct PveQueued {double at=0.;std::string key;int64_t point=0,wave=0;friend bool operator==(const PveQueued&,const PveQueued&)=default;};
struct PveWaveProgress {int64_t total=0,remaining=0,cleared=0,clear_percent=100,queued=0,pending=0;};
class PveDirector {
public:
    PveDirector(TypedBattleState& world,const ColdCatalog& catalog,ScriptedSpawnBudget& budget,ZombieNavigation& ladders,
        const RoomPublicTerrain& terrain,PveDirectorServices& services)
        :world_(world),catalog_(catalog),budget_(budget),ladders_(ladders),terrain_(terrain),services_(services){}
    void bind(const PveDirectorCold&);
    bool bound()const{return bound_;}
    bool coop_cycle()const{return cycle_;}
    // NativeBattle.native_cost_ratio; the reference runs on a frozen clock (0).
    double pressure=0.;
    void step();
    void cycle_step();
    void request_ladder(const ZombieRef&);
    bool cleared()const;
    // pve.WaveDirector.snapshot() and, for co-op, CoopCycle.snapshot() (room snapshot "team").
    nlohmann::json waves_snapshot(double time);
    nlohmann::json daylight_snapshot(double time,bool night)const;
    int64_t next_wave=0,paced=0;
    double pressure_seconds=0.;
    bool last_flag=false;
    std::vector<PveQueued> queue;
    std::vector<int64_t> pending_ladders;
    std::vector<std::string> spawned;
    std::optional<double> last_spawn_time;
    std::map<int64_t,std::set<std::string>> wave_members;
    std::map<int64_t,double> wave_started;
private:
    TypedBattleState& world_;const ColdCatalog& catalog_;ScriptedSpawnBudget& budget_;ZombieNavigation& ladders_;
    const RoomPublicTerrain& terrain_;PveDirectorServices& services_;
    bool bound_=false;
    int64_t day_=1,seed_=1,max_zombies_=40;bool coop_=false;
    std::vector<Point> points_;std::vector<PvePoolEntry> pool_;std::vector<PveWavePlan> plan_;
    PyRandom rng_{1};
    // uid -> (card key, last position): insertion-ordered like the source dict.
    std::vector<std::pair<std::string,std::pair<std::string,std::optional<Point>>>> alive_;
    // CoopCycle
    bool cycle_=false,initial_night_=false;
    int64_t phase_=-1;double next_grave_=0.;PyRandom cycle_rng_{1};
    std::map<int64_t,double> credit_;std::map<int64_t,int64_t> turn_;
    std::set<std::string> sleepers_;
    std::map<int64_t,std::set<std::string>> emitted_;
    std::set<int64_t> finished_;std::optional<int64_t> last_finished_;

    double cost(const std::string& key)const;
    double now()const;
    std::vector<std::string> compose(double budget,bool flag);
    std::vector<int64_t> fronts(const PveWavePlan&);
    std::vector<int64_t> sample(int64_t n,int64_t k);
    bool spawn(const std::string& key,int64_t point,int64_t wave);
    void observe_wave_members();
    PveWaveProgress wave_progress(int64_t index);
    bool can_advance();
    void pay_bounties();
    std::pair<double,std::string> coin_drop(const std::string& key);
    double health_scale()const;
    std::vector<Seat> alive_plant_seats()const;
    // CoopCycle helpers
    std::vector<ZombieRef> graves()const;
    void rotate();void grow();void mushrooms(bool night,bool changed);
    double distance(double x,double y,double tx,double ty)const;
    std::map<int64_t,std::vector<ZombieRef>> groups()const;
    std::optional<std::pair<std::string,Point>> origin(int64_t point,const std::string& card,int64_t wave);
    std::optional<std::pair<std::string,Point>> origin_inner(int64_t point,const std::string& card);
};
} // namespace pvz::typed72
