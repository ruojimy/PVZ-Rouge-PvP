#pragma once
#include "cold_admission.h"
#include "sim/typed/grave_binding.h"
#include "sim/typed/content_vines.h"
namespace pvz::typed72 {
struct ColdDeployEvent {Seat seat;std::string card;double charge;std::optional<std::string> entity;Point position;std::optional<std::string> grave;double facing;};
struct ColdFlagEvent {std::string grave,source;std::optional<std::string> entity;bool blocked=false;};
class ColdDeploymentServices {
public:
    virtual ~ColdDeploymentServices()=default;
    virtual void sync_public()=0;
    virtual void sync_terrain()=0;
    virtual void terrain_grass(Cell)=0;
    virtual void deploy_event(ColdDeployEvent)=0;
    virtual void flag_event(ColdFlagEvent)=0;
    virtual void select_grave(Seat,const std::string&)=0;
};
class ColdDeployment {
public:
    ColdDeployment(TypedBattleState& world,const ColdCatalog& catalog,ColdDeploymentState& state,RoomState& room,
        const RoomPublicState& published,Resources& resources,const ColdPlacement& placement,ColdAdmission& admission,
        ContentVines& vines,GraveBinding& graves,Scarecrows& scarecrows,ColdZombieSecrets& secrets,
        const std::shared_ptr<std::vector<std::string>>& native_secrets,ColdDeploymentServices& services)
        :world_(world),catalog_(catalog),state_(state),room_(room),published_(published),resources_(resources),placement_(placement),
        admission_(admission),vines_(vines),graves_(graves),scarecrows_(scarecrows),secrets_(secrets),native_secrets_(native_secrets),services_(services){}
    ColdPlacementResult placement(Seat,const std::string&,Point,std::optional<std::string> grave={},std::optional<std::string> copy={})const;
    std::string deploy(Seat,const std::string&,Point,std::optional<std::string> grave={},std::optional<std::string> copy={},std::optional<double> facing={});
    std::vector<ColdPlacementPlant> placement_roster()const;
    bool campaign_allowed(const std::string&)const;
private:
    TypedBattleState& world_;const ColdCatalog& catalog_;ColdDeploymentState& state_;RoomState& room_;const RoomPublicState& published_;
    Resources& resources_;const ColdPlacement& placement_;ColdAdmission& admission_;ContentVines& vines_;GraveBinding& graves_;
    Scarecrows& scarecrows_;ColdZombieSecrets& secrets_;const std::shared_ptr<std::vector<std::string>>& native_secrets_;ColdDeploymentServices& services_;
    std::string perform(Seat,const std::string&,Point,std::optional<std::string>,std::optional<std::string>,std::optional<double>);
    void coffee(Cell,double);
    void flag_reinforcements(const std::string&);
};
} // namespace pvz::typed72
