#pragma once
#include "cold_admission.h"
#include "sim/typed/plant_zombie_shooting.h"
#include "sim/typed/chili_effects.h"
#include "sim/typed/zombie_spawn.h"
namespace pvz::typed72 {
struct ColdFactorySettings {
    bool plant_zombie_test=false,ladder_support_call=false,sunflower_context=false;
    std::optional<size_t> dancer_index;
    std::optional<int> dancer_slot;
    double screen_height=768.;
    std::vector<std::string> bosses,current_zombies,spawn_zombies,battle_zombies;
    std::vector<std::pair<std::string,std::vector<std::string>>> test_source_mapping;
    // __pvz_sb_pumpkin_armor_chance. PvP replaces it with lambda game: 0 (native_patch.py:119);
    // unset keeps the original 4+plant-zombie-kinds formula.
    std::optional<int> pumpkin_chance;
};
struct ColdFactoryState {
    bool sunflower_active=false,sunflower_spawned=false,sunflower_restore_tail=false;
    bool i_zombie_placed=false;
    std::weak_ptr<TargetRoster> board_zombies;
    std::weak_ptr<PlantRoster> board_plants;
    Field<std::vector<std::string>> dancer_pending;
};
class ColdNativeFactory final:public ColdPatchedFactory {
public:
    ColdNativeFactory(TypedBattleState& world,ColdFactorySettings& settings,ColdFactoryState& state,
        PlantZombieShooting& shooting,ChiliDispatch& chili):world_(world),settings_(settings),state_(state),shooting_(shooting),chili_(chili){}
    PlantRef plant(Cell,const std::string&,double facing)override;
    ZombieRef zombie(const std::string&,Motion&,double facing)override;
    void init_plant_zombie(const ZombieRef&,const std::string&,bool duck,bool random_armor);
private:
    TypedBattleState& world_;ColdFactorySettings& settings_;ColdFactoryState& state_;PlantZombieShooting& shooting_;ChiliDispatch& chili_;
    ZombieRef raw(const std::string&,Motion&,double,bool hard_bridge=false);
    ZombieRef plant_zombie(const std::string&,Motion&,double,bool random_armor,bool ladder=false);
    ZombieRef sunflower(Motion&,double);
    std::optional<ZombieRef> backup(const std::string&,Motion&,double);
    bool duck(Point)const;
    double hp_multiplier()const;
    void random_armor(const ZombieRef&,double);
    void note(size_t before);
    std::string test_name(const std::string&);
    std::string mode()const;
};
} // namespace pvz::typed72
