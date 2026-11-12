#pragma once
#include "cold_hero_scope.h"
#include "cold_registration.h"
#include "cold_zombie_secrets.h"
#include "sim/typed/content_admission.h"
#include "sim/typed/expansion_combat.h"
namespace pvz::typed72 {
// This is the complete installed patch factory, before the PvP ban gate.
// A raw plant_original/spawn_original_zombie function cannot satisfy it.
class ColdPatchedFactory {
public:
    virtual ~ColdPatchedFactory()=default;
    virtual PlantRef plant(Cell,const std::string&,double facing)=0;
    virtual ZombieRef zombie(const std::string&,Motion&,double facing)=0;
};
enum class ColdNativeCall {external,zombie_region};
struct ColdNativeCallSite {ColdNativeCall kind=ColdNativeCall::external;std::optional<size_t> index;};
class ColdAdmissionServices {
public:
    virtual ~ColdAdmissionServices()=default;
    virtual void sync_public()=0;
    virtual void sync_terrain()=0;
    virtual void spawn_blocked(const std::string& card)=0;
};
class ColdAdmission {
public:
    ColdAdmission(TypedBattleState& world,const ColdCatalog& catalog,ColdDeploymentState& state,const RoomState& room,
        const EconomyState& economy,const ColdPlacement& placement,ColdRegistration& registration,ScriptedSpawnBudget& budget,
        ColdPatchedFactory& factory,ContentAdmission& content,ExpansionCombat& expansion,ColdZombieSecrets& secrets,
        const std::shared_ptr<std::vector<std::string>>& native_secrets,ColdAdmissionServices& services)
        :world_(world),catalog_(catalog),state_(state),room_(room),economy_(economy),placement_(placement),registration_(registration),
        budget_(budget),factory_(factory),content_(content),expansion_(expansion),secrets_(secrets),native_secrets_(native_secrets),services_(services){}
    PlantRef native_plant(Cell,const std::string&,double facing);
    // PvP73: NativeImitater.plant - the copy keeps its PvP card (甜椒投手 stays 甜椒投手, not its 西瓜投手 template).
    bool imitate(const PlantRef& imitater,Cell,double facing);
    ZombieRef native_zombie(const std::string&,Motion&,double facing,const ColdNativeCallSite& site={});
    std::optional<std::string> spawn(const std::string&,Seat team,Point,double facing=1.,bool temporary=false,
        const ColdParent* parent=nullptr,std::optional<AttackIdentity> parent_attack={});
    bool auto_register(const NativeObject&,Seat,const std::string&,bool temporary);
    std::shared_ptr<const RoomPublicCard> public_card(Seat,const std::string&)const;
    RoomRegistrationView registration_view(const NativeObject&)const;
    void harden(const PlantRef&);
    static bool inherit_carried_imp_armor(const ZombieRef&,const ZombieRef&);
    ColdRegistrationContext context()const;
private:
    TypedBattleState& world_;const ColdCatalog& catalog_;ColdDeploymentState& state_;const RoomState& room_;
    const EconomyState& economy_;const ColdPlacement& placement_;ColdRegistration& registration_;ScriptedSpawnBudget& budget_;
    ColdPatchedFactory& factory_;ContentAdmission& content_;ExpansionCombat& expansion_;ColdZombieSecrets& secrets_;
    const std::shared_ptr<std::vector<std::string>>& native_secrets_;ColdAdmissionServices& services_;
    std::vector<std::string> team_secrets(Seat)const;
    std::optional<ExpansionVariantSetup> expansion_setup(const ColdCard&)const;
};
} // namespace pvz::typed72
