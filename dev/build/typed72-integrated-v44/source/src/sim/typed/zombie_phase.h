#pragma once
#include "sim/typed/zombie_actions.h"
#include "sim/typed/sweet_taunts.h"

namespace pvz::typed72 {
class ZombiePhaseServices : public ZombieActionServices {
public:
    virtual void release_pending_destination()=0;
    virtual void finish_content_zombie()=0;
    virtual void finish_expansion_zombie()=0;
};

// Own the outer installed gate so every raw body goes through seat selection
// before the content/expansion gate supplied by the battle composition.
class ZombiePhase final : private ZombieActionServices {
public:
    ZombiePhase(TypedBattleState& world,ZombieMotion& motion,ZombieNavigation& navigation,
                ZombieActionState& state,ZombieMotionServices& movement,ZombiePhaseServices& services,
                PlantLifecycle& plants,EntityRenderer& renderer,SeatPathTracking& paths,SweetTaunts& taunts)
        :world_(world),services_(services),paths_(paths),taunts_(taunts),
         actions_(world,motion,navigation,state,movement,*this,plants,renderer){}
    std::vector<ZombieRef> run(std::span<const Seat> present,bool multi_plant);
private:
    TypedBattleState& world_;
    ZombiePhaseServices& services_;
    SeatPathTracking& paths_;
    SweetTaunts& taunts_;
    ZombieActions actions_;
    std::span<const Seat> present_;
    std::optional<Seat> entry_;
    void switch_plant(Seat);
    void mobile_actions(bool multi_plant);
    void zombie_gate(size_t)override;
    void summon_zombie(std::string name,Motion position,double facing)override {
        services_.summon_zombie(std::move(name),position,facing);
    }
    bool hold_dance()override{return services_.hold_dance();}
    bool defer_dancer(Point p,double facing,int64_t slot)override{return services_.defer_dancer(p,facing,slot);}
    bool hold_sled()override{return services_.hold_sled();}
    bool hold_giant()override{return services_.hold_giant();}
    void ash_zombie(size_t index)override{services_.ash_zombie(index);}
    void line(Point start,Point end)override{services_.line(start,end);}
    void crop(std::string sprite,Point point,bool mirrored,Point size)override {
        services_.crop(std::move(sprite),point,mirrored,size);
    }
    uint64_t flat_sprite(std::string sprite,Point size,bool mirrored)override {
        return services_.flat_sprite(std::move(sprite),size,mirrored);
    }
    bool has_sprite(const std::string& sprite)const override{return services_.has_sprite(sprite);}
};
} // namespace pvz::typed72
