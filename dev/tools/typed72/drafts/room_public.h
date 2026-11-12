#pragma once
#include "sim/typed/room_state.h"
#include "sim/typed/room_public_terrain.h"
#include "sim/typed/ai_observation_builder.h"
#include "sim/typed/grave_clock.h"
#include "sim/typed/room_native_pose.h"
namespace pvz::typed72 {
// Immutable resolved catalog entry. The admission/catalog owner keeps one
// instance per actual-card resolution; public rows retain it by shared handle.
struct RoomPublicCard {
    std::string id,name,behavior,asset;
    double cost=0.,damage=0.;std::optional<double> range;
    bool producer=false,mushroom=false,flying=false;
};
// Only fields absent from the current body schemas cross this typed adapter.
// The admission owner must return its authoritative registration values; it
// must not reconstruct these from current HP or invent a second unit store.
struct RoomRegistrationView {
    double registered_plant_max_hp=0.,plant_armor_max=0.;
    bool zombie_temporary=false,floating=false,coop_dormant=false,first_soldier_used=false;
    std::span<const std::pair<std::string,double>> secret_speed;
};
struct RoomPublishedUnit {
    std::string id;std::shared_ptr<const RoomPublicCard> card;
    Seat side=Seat::plant,original_owner=Seat::plant;std::optional<Seat> seat;
    Point position,velocity;double w=0.,h=0.,hp=0.,max_hp=0.,facing=1.,armor_hp=0.,armor_max=0.;
    bool mobile=false,burrowed=false,temporary=false,awake=true,floating=false,frozen=false,slowed=false,buttered=false,stunned=false;
    double production_rate=1.,drowsy_level=0.;bool mature=false,torch_blue=false,drowsy=false,orphan_barrel=false;
    int poison_level=0;std::optional<std::string> copy_card;
    std::optional<bool> first_soldier_ready;
    std::vector<std::pair<std::string,double>> secret_speed;
};
struct RoomPublishedHero {AiPublicHero visible;RoomNativePose native_pose;};
struct RoomPublicHeroFacts {double resource=0.,teleport_ready=0.;bool cannon_aimed=false,absent=false;};
struct RoomPublicDeath {std::string entity,card;Seat side;};
class RoomPublicServices {
public:
    virtual ~RoomPublicServices()=default;
    virtual void harden(const PlantRef&)=0;
    // Returns false only for absent/banned/unresolvable cards, just as the
    // source catches ValueError. On true, native_objects owns registration.
    virtual bool auto_register(const NativeObject&,Seat,const std::string& card,bool temporary)=0;
    virtual std::shared_ptr<const RoomPublicCard> unit_card(Seat original_owner,const std::string& key)=0;
    virtual bool base_producer(const std::string& key)const=0;
    virtual RoomRegistrationView registration(const NativeObject&)const=0;
    virtual int jump_cap(Seat)const=0;
    // Read the existing economy account and room action state. These are
    // publication facts, not a second balance/cooldown authority.
    virtual RoomPublicHeroFacts hero_facts(Seat)const=0;
    virtual bool rage()const=0;
    virtual bool first_soldier()const=0;
    virtual void unit_gone(const NativeObject&)=0;
    virtual void death(const RoomPublicDeath&)=0;
    virtual std::span<const Cell> head_only_cells()const=0;
    virtual void set_belts(const std::set<int64_t>&)=0;
};
struct RoomPublicState {
    std::array<std::optional<RoomPublishedHero>,4> heroes;
    std::vector<RoomPublishedUnit> units;
    RoomPublicTerrain terrain;
};
class RoomPublicSync {
public:
    RoomPublicSync(TypedBattleState& world,RoomState& room,RoomPublicState& published,GraveClock& graves,TargetSight& sight,RoomPublicServices& services,const std::shared_ptr<std::vector<std::string>>& native_secrets)
        :world_(world),room_(room),published_(published),graves_(graves),sight_(sight),services_(services),native_secrets_(native_secrets){}
    void sync(std::span<const Seat> avatar_order,bool terrain=true);
    const RoomPublishedUnit* find(const std::string&)const;
private:
    TypedBattleState& world_;RoomState& room_;RoomPublicState& published_;GraveClock& graves_;TargetSight& sight_;RoomPublicServices& services_;const std::shared_ptr<std::vector<std::string>>& native_secrets_;
    std::vector<const void*> live_;
    std::vector<NativeObject> births_;
    std::vector<NativeObjectRegistry::Entry> registered_;
    std::unordered_map<std::string,size_t> lookup_;
};
} // namespace pvz::typed72
