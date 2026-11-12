#pragma once
#include "sim/typed/content_zombies64.h"
#include "sim/typed/native_summons.h"
#include "sim/typed/scarecrow.h"

namespace pvz::typed72 {
struct NativeContentZombieRules {
    std::vector<std::string> custom_zombies;
};
class ContentZombieControllers {
public:
    virtual ~ContentZombieControllers()=default;
    virtual void cart_before(const ZombieRef&)=0;
    virtual void cart_animate(const ZombieRef&,bool active,bool fired)=0;
    virtual void september_gate(const ZombieRef&)=0;
    virtual void september_wave_chase(const ZombieRef&)=0;
    virtual void september_finish(const ZombieRef&)=0;
    virtual void zombies56_gate(const ZombieRef&)=0;
    virtual void zombies56_finish(const ZombieRef&)=0;
    virtual void zombies70_gate(const ZombieRef&)=0;
    virtual bool solid(Point)const=0;
    virtual void barrel_correct_pair(const ZombieRef&)=0;
    virtual void barrel_detach(const ZombieRef&,double remaining)=0;
    virtual void barrel_break(const ZombieRef&)=0;
    virtual void barrel_move(const ZombieRef&,double factor)=0;
    virtual void barrel_contact(const ZombieRef&,double factor)=0;
    virtual double bite_damage(const ZombieRef&,const ContentTarget&)=0;
    virtual double movement_factor(const ZombieRef&)const=0;
    virtual void alias_art(const std::string&,const std::string&)=0;
    virtual void tint_poison(const ZombieRef&)=0;
    virtual double image_height(const std::string&)const=0;
    virtual double unit_scale(const ZombieRef&)const=0;
    virtual void stun_star(Point position,Point dimensions)=0;
    virtual void draw_content_zombie(const ZombieRef&)=0;
};

// NativeContent's installed per-body controller around the original mobile
// region. The roster entry is captured before any nested gate can replace it.
class ContentZombies {
public:
    ContentZombies(TypedBattleState& world,const NativeContentZombieRules& rules,
                   const std::vector<Seat>& present,const SeatCommands& commands,
                   const RallyPoints& rally,SeatPathTracking& paths,const uint64_t& terrain_revision,
                   ContentQueries& queries,ContentTargets& targets,SweetTaunts& taunts,
                   ContentZombies64& zombies64,Scarecrows& scarecrows,NativeSummons& summons,
                   ContentZombieControllers& controllers,const bool& drawing)
        :world_(world),rules_(rules),present_(present),commands_(commands),rally_(rally),paths_(paths),
         terrain_revision_(terrain_revision),queries_(queries),targets_(targets),taunts_(taunts),
         zombies64_(zombies64),scarecrows_(scarecrows),summons_(summons),controllers_(controllers),drawing_(drawing){}
    void gate(size_t index);
    void finish();
    void release_pending_destination();
    const ZombieRef& last()const{return last_;}
private:
    TypedBattleState& world_;
    const NativeContentZombieRules& rules_;
    const std::vector<Seat>& present_;
    const SeatCommands& commands_;
    const RallyPoints& rally_;
    SeatPathTracking& paths_;
    const uint64_t& terrain_revision_;
    ContentQueries& queries_;
    ContentTargets& targets_;
    SweetTaunts& taunts_;
    ContentZombies64& zombies64_;
    Scarecrows& scarecrows_;
    NativeSummons& summons_;
    ContentZombieControllers& controllers_;
    const bool& drawing_;
    ZombieRef last_;
    bool custom(std::string_view)const;
    bool follow(const CombatZombie&)const;
    bool rally(const CombatZombie&)const;
    Point destination(const CombatZombie&);
    Seat following_seat(const CombatZombie&)const;
    void restore_player(CombatZombie&);
    void cart_gate(const ZombieRef&,std::string_view name);
    void art_gate(const ZombieRef&,std::string_view name);
    void finish_summoner(const ZombieRef&,std::string_view name,double factor);
    void finish_flyer(const ZombieRef&,std::string_view name,double factor,std::optional<ContentTarget>);
    void flyer_bite_effect(const ZombieRef&,const ContentTarget&);
    void stun_stars(const ZombieRef&,std::string_view name);
};
} // namespace pvz::typed72
