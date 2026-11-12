#include "sim/typed/owner_umbrella.h"
#include <algorithm>
#include <cmath>

namespace pvz::typed72 {
namespace {
void pass(TypedBattleState& world,bool after) {
    auto& heroes=world.heroes;const auto tile=world.runtime.tile,plk=world.runtime.plk;
    // enumerate retains the list identity and observes appends. Native hero
    // selection and the two utility slices do not mutate that list.
    const auto roster=world.plant_roster;
    for(size_t index=0;index<roster->size();++index) {
        const auto& plant=roster->at(index);
        if(plant->kind!="萝卜伞" || plant->hp.or_missing(0.)<=0. || plant->sleep.present())continue;
        if(after) {
            if(!plant->shooting.present() || plant->shooting.is_null() || plant->shooting.get()!=20.)continue;
        }else if(plant->shooting.is_null() || plant->shooting.or_missing(0.)!=0. || plant->shoot_cd.or_missing(0.)>0.)continue;
        const auto saved_index=heroes.source_index;
        const auto saved_x=heroes.globals.xx,saved_y=heroes.globals.yy;
        {
            HeroContext context(heroes,{Seat::plant,Seat::plant,CombatPhase::plants,source_ref(plant),{}});
            heroes.source_index=int64_t(index);const auto cell=plant->cell;
            heroes.globals.xx.set((cell.x+.5)*tile);heroes.globals.yy.set((cell.y+.5)*tile);
            auto& position=*heroes.globals.position.get();
            const auto dx=position.x-heroes.globals.xx.get(),dy=position.y-heroes.globals.yy.get();
            if(after) {
                if(std::abs(dx)+std::abs(dy)<=tile*2.) {
                    position.vx=(dx>0.?300.:-300.)*plk;position.vy=-600.*plk;
                }
            }else if(std::abs(dx)+std::abs(dy)<=tile*2. && position.vy>200.*plk) {
                auto& current=*world.plant_roster->at(index);current.shooting.set(1.);
                if(current.shoot_cd.get()==-1.)current.shoot_cd.set(0.);
            }else world.plant_roster->at(index)->shoot_cd.set(-1.);
        }
        // Source scratch restoration follows successful execution. Its hero
        // context separately restores the frame when execution throws.
        heroes.source_index=saved_index;heroes.globals.xx=saved_x;heroes.globals.yy=saved_y;
        if(!saved_x.present())heroes.globals.xx.set_null();
        if(!saved_y.present())heroes.globals.yy.set_null();
    }
}
}
void owner_umbrella_effects(TypedBattleState& world,bool after,std::span<const Seat> seats) {
    const auto count=std::count_if(seats.begin(),seats.end(),[](Seat seat){return team_of(seat)==Seat::plant;});
    if(count<=1){pass(world,after);return;}
    struct RestoreAlias {
        HeroCombat& heroes;
        ~RestoreAlias(){heroes.select_plant_seat(Seat::plant);}
    } restore{world.heroes};
    for(const auto seat:seats)if(team_of(seat)==Seat::plant && world.heroes.players.at(seat_index(seat))->hp>0.) {
        world.heroes.select_plant_seat(seat);pass(world,after);
    }
}
} // namespace pvz::typed72
