#pragma once
#include <map>
#include "cold_catalog.h"
#include "cold_deployment_state.h"
#include "cold_placement_rules.h"
#include "sim/typed/room_public.h"
namespace pvz::typed72 {
struct ColdPlacementPlan {
    ColdCard card;
    double charge=0.;Point position;
    std::string slot;
    std::optional<Cell> cell;
    std::optional<ColdCard> copied;
    std::optional<std::string> copy_id,grave_target,thief_target;
    bool temporary=false;
};
struct ColdPlacementResult {
    std::string error;
    std::optional<ColdPlacementPlan> plan;
    ColdPlacementResult(std::string error):error(std::move(error)){}
    ColdPlacementResult(const char* error):error(error){}
    ColdPlacementResult(ColdPlacementPlan plan):plan(std::move(plan)){}
};
class ColdPlacementSecrets {
public:
    virtual ~ColdPlacementSecrets()=default;
    virtual bool last_stand()const=0;
    virtual double crow_surcharge(Seat)const=0;
    virtual bool unsealed(Seat)const=0;
};
class ColdPlacement {
public:
    ColdPlacement(const TypedBattleState& world,const ColdCatalog& catalog,const ColdDeploymentState& state,
        const RoomState& room,const RoomPublicState& published,const Resources& resources,const EconomyState& economy,
        const ColdPlacementSecrets& secrets):world_(world),catalog_(catalog),state_(state),room_(room),published_(published),
        resources_(resources),economy_(economy),secrets_(secrets){}
    ColdCard player_card(Seat,const std::string&)const;
    ColdCard unit_card(Seat,const std::string&)const;
    ColdPlacementResult placement(Seat,const std::string&,Point,const ColdPlacementRules&,
        std::optional<std::string> grave={},std::optional<std::string> copied={})const;
    std::optional<Point> grave_soldier_exit(const ColdCard&,Seat,const RoomPublishedUnit&,double facing)const;
    std::optional<Point> aquatic_exit(const ColdCard&,Seat,const RoomPublishedUnit&,double facing)const;
    const RoomPublishedUnit* find(const std::string&)const;
    RoomPublicCell cell(Point)const;
    bool overlaps(Point,double w,double h,const RoomPublishedUnit&)const;
    double width()const{return world_.terrain.cols()*world_.runtime.tile;}
    double height()const{return world_.terrain.rows()*world_.runtime.tile;}
private:
    const TypedBattleState& world_;const ColdCatalog& catalog_;const ColdDeploymentState& state_;
    const RoomState& room_;const RoomPublicState& published_;const Resources& resources_;const EconomyState& economy_;const ColdPlacementSecrets& secrets_;
    ColdPlacementResult plant(Seat,const std::string&,Point,const ColdPlacementRules&,std::optional<std::string>)const;
    ColdPlacementResult zombie(Seat,const std::string&,Point,std::optional<std::string>,std::optional<std::string>)const;
    ColdPlacementResult thief(Seat,const std::string&,Point)const;
    struct Surface{Point position;bool water;};
    std::optional<Surface> surface(Point,bool grave=false)const;
    std::optional<Point> soldier_exit(const ColdCard&,Seat,Point)const;
    bool blocked(Point,double w,double h)const;
    double facing(Seat)const;
    double cooldown(Seat,const std::string&)const;
    bool present(Seat)const;
    bool deck_has(Seat,const std::string&)const;
    double balance(Seat s)const{return resources_.accounts[seat_index(s)].balance;}
    std::span<const std::string> secrets(Seat)const;
    std::string ring_error(const ColdCard&,Seat,Point)const;
};
} // namespace pvz::typed72
