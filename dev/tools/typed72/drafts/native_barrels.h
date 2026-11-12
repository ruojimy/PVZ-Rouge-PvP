#pragma once
#include "sim/typed/native_summons.h"
#include "sim/typed/content_target.h"
#include "sim/typed/native_tracking.h"
namespace pvz::typed72 {
struct BarrelEvent {
    enum class Kind {detached,corrected} kind;
    Field<std::string> entity,source;
    double hp=0.;Point position;
};
class NativeBarrelServices {
public:
    virtual ~NativeBarrelServices()=default;
    // Registers an already appended native body using the real card constructor
    // metadata; constructor order is observable by synchronous spawn callbacks.
    virtual void register_barrel(const ZombieRef&,const Field<std::string>& parent)=0;
    virtual void barrel_event(const BarrelEvent&)=0;
    virtual void crush_barrel_plant(const ZombieRef&,const PlantRef&)=0;
    virtual void draw_barrel_sprite(Point feet,double rotation)=0;
};
class NativeBarrels {
public:
    NativeBarrels(TypedBattleState& world,const TargetSight& published,ContentTargets& targets,
                  NativeSummons& summons,NativeBarrelServices& services)
        :world_(world),published_(published),targets_(targets),summons_(summons),services_(services){}
    void track(const ZombieRef&);
    ZombieRef detach(const ZombieRef&,std::optional<double> hp={});
    void reconcile();
    void contact(const ZombieRef&,double factor);
    void correct_pair(const ZombieRef&);
    void float_on_water(Motion&);
    void tick();
    void break_barrel(const ZombieRef&);
    void move(const ZombieRef&,double factor);
    int displace(Motion&);
    void draw(const ZombieRef&,bool drawing);
    static bool active(const CombatZombie&);
    bool overlap(const ZombieRef&,Point)const;
    const auto& carriers()const{return carriers_;}
private:
    TypedBattleState& world_;
    const TargetSight& published_;
    ContentTargets& targets_;
    NativeSummons& summons_;
    NativeBarrelServices& services_;
    std::vector<ZombieRef> carriers_;
    bool solid(Point)const;
    static ZombieRef orphan_copy(const ZombieRef&,double hp);
};
} // namespace pvz::typed72
