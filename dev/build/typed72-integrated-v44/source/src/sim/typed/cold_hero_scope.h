#pragma once
#include "sim/typed/hero.h"
namespace pvz::typed72 {
// NativeBattle::_summon_hero: this borrows one existing avatar, including its
// position-list identity, without changing the enclosing attack ownership.
class ColdHeroScope {
public:
    ColdHeroScope(HeroCombat& heroes,Seat side,const std::shared_ptr<std::vector<std::string>>& secrets);
    ~ColdHeroScope()noexcept;
    ColdHeroScope(const ColdHeroScope&)=delete;
    void close();
private:
    HeroCombat* heroes_;Seat side_;HeroFrame saved_,mask_;
    std::optional<HeroSelection> active_;
};
void cold_select_hero(HeroCombat&,Seat,const std::shared_ptr<std::vector<std::string>>&);
} // namespace pvz::typed72
