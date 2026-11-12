#pragma once
#include "cold_placement.h"
#include "cold_registration.h"
#include "sim/typed/scarecrow.h"
namespace pvz::typed72 {
struct ColdFirstSoldierEvent {std::string grave,entity;};
struct ColdCrowFlockEvent {Seat seat;std::string source;std::vector<std::string> entities;};
class ColdZombieSecretServices {
public:
    virtual ~ColdZombieSecretServices()=default;
    // The caller has entered the same explicit ban-free internal hand-out.
    virtual std::optional<std::string> spawn_flock(Point,double,const ColdParent&)=0;
    virtual void first_soldier_event(ColdFirstSoldierEvent)=0;
    virtual void crow_flock_event(ColdCrowFlockEvent)=0;
};
class ColdZombieSecrets final:public ColdPlacementSecrets {
public:
    ColdZombieSecrets(TypedBattleState& world,const ColdCatalog& catalog,const ColdDeploymentState& deployment,
        Scarecrows& scarecrows,ColdZombieSecretServices& services):world_(world),catalog_(catalog),deployment_(deployment),scarecrows_(scarecrows),services_(services){}
    void configure_locked();
    bool enabled()const;
    bool has(std::string_view)const;
    bool seat_has(Seat,std::string_view)const;
    bool last_stand()const override;
    bool unsealed(Seat seat)const override{return seat_has(seat,"解除封印");}
    double crow_surcharge(Seat)const override;
    void on_spawn(const ZombieRef&,const ColdCard&,const ColdParent*);
    void on_deployed(const std::string& entity,const std::optional<std::string>& grave);
    std::optional<std::string> flag_summon(const std::string& card)const;
    std::vector<std::string> crow_flock(const std::string& crow,Seat);
    static void scale_hp(const ZombieRef&,double);
    static bool scale_speed(const ZombieRef&,std::string,double);
private:
    TypedBattleState& world_;const ColdCatalog& catalog_;const ColdDeploymentState& deployment_;
    Scarecrows& scarecrows_;ColdZombieSecretServices& services_;
    std::array<bool,4> trinity_{};
    std::vector<ZombieRef> own_scarecrows()const;
};
} // namespace pvz::typed72
