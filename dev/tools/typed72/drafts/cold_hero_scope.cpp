#include "cold_hero_scope.h"
#include <exception>
namespace pvz::typed72 {
namespace {void capture(HeroFrame& to,const HeroFrame& from){
#define COPY(n) if(from.n.present())to.n=from.n;
PVZ72_HERO_COMBAT(COPY)
#undef COPY
}}
void cold_select_hero(HeroCombat& heroes,Seat side,const std::shared_ptr<std::vector<std::string>>& secrets){
    heroes.globals.overlay(heroes.hero(side).frame,true);heroes.globals.mode.set(team_of(side)==Seat::zombie?"我是僵尸":"正常模式");heroes.globals.secrets.set(secrets);
}
ColdHeroScope::ColdHeroScope(HeroCombat& heroes,Seat side,const std::shared_ptr<std::vector<std::string>>& secrets):heroes_(&heroes),side_(side),active_(heroes.active){
    if(active_)capture(heroes.hero(active_->target).frame,heroes.globals);
    saved_=heroes.globals;mask_=heroes.hero(side).frame;cold_select_hero(heroes,side,secrets);if(heroes.active)heroes.active->target=side;
}
void ColdHeroScope::close(){if(!heroes_)return;auto& heroes=*heroes_;capture(heroes.hero(side_).frame,heroes.globals);
#define RESTORE(n,k) if(mask_.n.present())heroes.globals.n=saved_.n;
PVZ72_HERO_NUMBERS(RESTORE) PVZ72_HERO_BOOLEANS(RESTORE) PVZ72_HERO_STRINGS(RESTORE)
#undef RESTORE
    if(mask_.position.present())heroes.globals.position=saved_.position;
    heroes.globals.mode=saved_.mode;heroes.globals.secrets=saved_.secrets;
    heroes.active=active_;if(active_)capture(heroes.globals,heroes.hero(active_->target).frame);heroes_=nullptr;
}
ColdHeroScope::~ColdHeroScope()noexcept{try{close();}catch(...){std::terminate();}}
} // namespace pvz::typed72
