#pragma once
#include "sim/typed/content_queries.h"
#include "sim/typed/grave_binding.h"
#include "sim/typed/scripted_spawn_budget.h"
#include "sim/typed/sweet_taunts.h"
#include "sim/typed/grenadiers.h"
#include <map>
namespace pvz::typed72 {
struct Zombie70Event {
    enum class Kind {reaper_idle,reaper_resumed,airdrop,hook_fired,bone_thrown,grenade_reflected,
                     projectile_reflected,bone_grave,bone_gravebuster,hook_hit} kind;
    Field<std::string> source,entity,target;
    Field<Seat> owner;
    Cell cell;
    std::string projectile;
};
struct BoneSource {
    std::optional<NativeObject> object;
    std::shared_ptr<AttackSource> metadata;
    double direction=1.;
};
class ContentZombie70Services {
public:
    virtual ~ContentZombie70Services()=default;
    virtual void alias_art(const std::string&,const std::string&)=0;
    virtual void zombie70_event(const Zombie70Event&)=0;
    virtual ZombieRef spawn_airdrop(Point,double facing,const ScriptedSpawnOrigin&)=0;
    virtual ZombieRef spawn_bone_grave(Cell,const BoneSource&)=0;
    virtual PlantRef spawn_bone_gravebuster(Cell,double facing,const Field<std::string>& parent)=0;
    virtual void draw_zombie70_effects()=0;
};
class ContentZombies70 {
public:
    using Graves=std::map<std::pair<int,int64_t>,ZombieRef>;
    ContentZombies70(TypedBattleState& world,ContentQueries& queries,ContentTargets& targets,SweetTaunts& taunts,
                     ScriptedSpawnBudget& budget,GraveBinding& binding,const TargetSight& published,
                     const CollisionCatalog& collision,ContentZombie70Services& services)
        :world_(world),queries_(queries),targets_(targets),taunts_(taunts),budget_(budget),binding_(binding),
         published_(published),collision_(collision),services_(services){}
    bool configure(const ZombieRef&,std::string_view);
    void gate(const ZombieRef&);
    void airdrop(const ZombieRef&);
    bool airdrop_child(const ScriptedSpawnOrigin&);
    std::optional<ContentTarget> hook_target(const ZombieRef&);
    bool hook(const ZombieRef&);
    Graves graves()const;
    bool grave_cell(Cell,const Graves&)const;
    std::optional<Cell> bone_cell(const ZombieRef&);
    bool throw_bone(const ZombieRef&);
    bool reflect(const ContentProjectileRef&);
    void wind(const ContentProjectileRef&);
    bool reflect(const GrenadeRef&);
    void wind(const GrenadeRef&);
    void impact_bone(const ContentProjectileRef&,Cell);
    void projectiles();
private:
    TypedBattleState& world_;
    ContentQueries& queries_;
    ContentTargets& targets_;
    SweetTaunts& taunts_;
    ScriptedSpawnBudget& budget_;
    GraveBinding& binding_;
    const TargetSight& published_;
    const CollisionCatalog& collision_;
    ContentZombie70Services& services_;
    bool alive(const ContentTarget&)const;
    static bool head(const PlantRef&);
    static double factor(const CombatZombie&);
    bool seat_has(const ZombieRef&,std::string_view)const;
    bool solid(Point)const;
    std::shared_ptr<AttackSource> snapshot(const ZombieRef&)const;
    static std::optional<ContentTarget> target(const std::optional<NativeObject>&);
    template<class Shot> bool reflect_shot(const std::shared_ptr<Shot>&);
    template<class Shot> void wind_shot(const std::shared_ptr<Shot>&);
};
} // namespace pvz::typed72
