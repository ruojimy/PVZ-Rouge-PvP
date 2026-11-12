#pragma once
#include "sim/typed/ballistics.h"
#include "sim/typed/content_queries.h"
#include "sim/typed/native_tracking.h"

namespace pvz::typed72 {
struct GrenadeBlast {int64_t tick;Point point;bool instant;};
struct GrenadeEvent {
    enum class Kind { cancelled,no_target,thrown,reflected,explode } kind;
    Field<std::string> source,other;
    Cell cell;
    std::vector<std::string> targets;
    bool instant=false;
};
class GrenadierServices {
public:
    virtual ~GrenadierServices()=default;
    virtual double card_cost(std::optional<Seat>,const std::string&)=0;
    virtual void grenade_event(const GrenadeEvent&)=0;
};
class Grenadiers {
public:
    Grenadiers(TypedBattleState& world,ContentQueries& queries,ContentTargets& targets,
               const TargetSight& published,GrenadierServices& services)
        :grenades(world.content_projectiles.grenades),world_(world),queries_(queries),targets_(targets),published_(published),services_(services),
         gravity_(4.*world.runtime.plk){}
    std::shared_ptr<GrenadeRoster>& grenades;
    std::vector<GrenadeBlast> blasts;
    void advance(const ZombieRef&,bool alive);
    std::optional<ContentTarget> target(const ZombieRef&);
    void throw_grenade(const ZombieRef&);
    void update();
    bool reflect(GrenadeRef);
    void explode(GrenadeRef,Cell);
    static bool zombie_vs_zombie(const ContentTarget&);
private:
    TypedBattleState& world_;
    ContentQueries& queries_;
    ContentTargets& targets_;
    const TargetSight& published_;
    GrenadierServices& services_;
    double gravity_;
    bool solid(Point)const;
};
} // namespace pvz::typed72
