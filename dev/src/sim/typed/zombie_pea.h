#pragma once
#include "sim/typed/plant_zombie_target.h"
namespace pvz::typed72 {
class TorchRules;
class ZombiePeaCallbacks {
public:
    virtual ~ZombiePeaCallbacks()=default;
    virtual void ensure_plant_zombie_assets()=0;
    virtual void add_entity(std::string,double,Motion)=0;
    virtual void clear_plant(Cell)=0;
    // nullopt denotes an absent surface callback, which takes a different
    // native branch from a present callback that throws or returns false.
    virtual std::optional<bool> surface_damage(size_t,double,double)=0;
    virtual void ordinary_damage(size_t,double,double)=0;
    virtual void knockback(size_t,double)=0;
    virtual void player_damage(double)=0;
};
class ZombiePeas {
public:
    ZombiePeas(TypedBattleState& w,ZombiePeaCallbacks& cb,const CollisionCatalog& c):world_(w),callbacks_(cb),catalog_(c),aim_(w,c){}
    ZombiePeas(TypedBattleState& w,ZombiePeaCallbacks& cb,const CollisionCatalog& c,TorchRules& torches)
        :ZombiePeas(w,cb,c){torches_=&torches;}
    uint64_t shots=0;
    static bool is_pea(const EntityRef&);
    static Point xy(const EntityRef&);
    static bool segment_hits(Point start,Point end,Point center,Point radii);
    static double fire_multiplier(const EntityRef&);
    bool damage_player(double direction=1.);
    bool damage_charmed(size_t,CombatTarget,const EntityRef&,double direction);
    void torch_check(const EntityRef&);
    void fire_splash(const EntityRef&,Point,const PlantRef& direct_plant={},std::optional<CombatTarget> direct_zombie={},bool direct_player=false);
    bool raw_hit(const EntityRef&);
    bool hit(const EntityRef&);
    bool raw_update_one(const EntityRef&,double scale,double width,double height);
    bool update_one(const EntityRef&,double scale,double width,double height);
    void update_all();
    std::optional<bool> shotgun_volley(const std::optional<CombatTarget>&);
    bool raw_spawn(Point,double angle,bool friendly=false,std::optional<CombatTarget> source={});
    bool sourced_spawn(Point,double angle,bool friendly=false,std::optional<CombatTarget> source={});
    bool spawn(Point,double angle,bool friendly=false,std::optional<CombatTarget> source={});
    bool hero_pea(Seat,std::span<const Seat> enemy_team,double width);
private:
    struct LegacyView {
        std::shared_ptr<TargetRoster> targets;
        std::shared_ptr<PlantRoster> plants;
    };
    TypedBattleState& world_;
    ZombiePeaCallbacks& callbacks_;
    const CollisionCatalog& catalog_;
    PlantZombieTargeting aim_;
    TorchRules* torches_=nullptr;
    bool i_zombie()const;
    void splat(Point);
    bool hit_charmed(const EntityRef&,Point start,Point end,double scale,const LegacyView*);
    void splash(const EntityRef&,Point,const PlantRef&,std::optional<CombatTarget>,bool,const LegacyView*);
    void plant_damage(const PlantRef&,double);
    std::shared_ptr<AttackSource> source_ref_for(const CombatTarget&)const;
    RecordId identity(const CombatTarget&)const;
};
} // namespace pvz::typed72
