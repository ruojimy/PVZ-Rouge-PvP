#include "sim/typed/protection.h"
#include <algorithm>

namespace pvz::typed72 {
namespace {
std::optional<std::string> optional_string(const Field<std::string>& f) {
    return f.present()&&!f.is_null()?std::optional<std::string>(f.get()):std::nullopt;
}
std::string_view value(const Field<std::string>& f){return f.present()&&!f.is_null()?f.get():std::string_view{};}
}
void DamageSecrets::configure(const std::array<std::optional<HeroPlayer>,4>& players) {
    enabled=false;team.reset();for(auto& s:seats)s.reset();
    constexpr std::array<std::string_view,size_t(DamageSecret::count)> names{
        "专注啃咬","狂暴","阿姆斯特朗","坤坤","解除封印","遗骸","二手","僵王出品"};
    for(auto side:{Seat::zombie,Seat::zombie2}) {
        const auto i=seat_index(side);if(!players[i])continue;
        for(const auto& card:players[i]->secrets) {
            if(!card.starts_with("zsecret:"))continue;
            enabled=true;const std::string_view name(card.data()+8,card.size()-8);
            for(size_t n=0;n<names.size();++n)if(name==names[n])seats[i].set(n);
        }
        team|=seats[i];
    }
}
std::optional<Seat> UnitProtection::owner(const AttackSource& source) const {
    if(source.charmed.present())return Seat::plant;
    const auto seat=known_seat(value(source.owner));
    if(seat&&heroes_.contains(*seat))return seat;
    return heroes_.active?std::optional<Seat>(heroes_.active->owner):std::nullopt;
}
bool UnitProtection::own(const DamageTarget& target) const {return owner(target.identity)==Seat::zombie;}
bool UnitProtection::berserk() const {
    return secrets.has(DamageSecret::rage)&&(deathmatch||!heroes_.last_stand_order.empty());
}
bool UnitProtection::focused(const DamageTarget& target) const {
    return secrets.has(DamageSecret::focus)&&double(heroes_.tick)-target.state.hurt_tick.or_missing(0.)>=1250.;
}
double UnitProtection::damage_factor(const DamageTarget& target) const {
    if(!secrets.enabled||target.identity.plant.present()||target.state.grave||target.state.hero||!own(target))return 1.;
    double factor=1.;
    if(berserk())factor*=.75;
    if(focused(target))factor*=.75;
    if(secrets.has(DamageSecret::armstrong)&&value(target.state.card)=="zombie:报纸僵尸"&&target.hand.empty())factor*=.5;
    if(target.state.crowd_factor.present()&&!target.state.crowd_factor.is_null()&&target.state.crowd_factor.get()!=0.)factor*=target.state.crowd_factor.get();
    return factor;
}
double UnitProtection::relic(DamageTarget target,double amount) {
    const auto& owner=target.identity.owner;
    if(!secrets.has(DamageSecret::relic)||owner.is_null()||value(owner).starts_with("plant"))return amount;
    auto& state=target.state;
    if(state.relic_until.present()&&!state.relic_until.is_null())return double(heroes_.tick)<state.relic_until.get()?0.:amount;
    if(amount<target.hp)return amount;
    const double seconds=deathmatch||!heroes_.last_stand_order.empty()?36.:3.;
    state.relic_until.set(double(heroes_.tick)+seconds*250.);
    events.push_back(RelicEvent{optional_string(target.identity.id),seconds});
    return std::max(0.,target.hp-.01);
}
double UnitProtection::adjust(DamageTarget target,double amount) {
    if(target.identity.plant.present()||target.state.hero)return amount;
    if(target.state.grave)return relic(target,amount);
    amount*=damage_factor(target);
    // Source intentionally resets this clock even for charmed units.
    if(secrets.has(DamageSecret::focus))target.state.hurt_tick.set(double(heroes_.tick));
    if(secrets.has(DamageSecret::basketball_lock)&&value(target.state.card)=="zombie:投篮车僵尸"&&own(target)&&!target.state.lock_done) {
        if(target.state.basketball.or_missing(0.)>0&&amount>=target.hp-1.) {
            target.state.locked.set(true);return std::max(0.,target.hp-1.);
        }
    }
    return amount;
}
bool UnitProtection::shield_first(const DamageTarget& target,double hand_hp) const {
    const auto& hand=target.hand;
    return hand_hp>0&&(hand=="报纸"||hand=="钢门"||hand=="梯子"||hand=="铁栅门"||hand=="传送带")&&own(target);
}
bool UnitProtection::selected(const DamageTarget& target) const {
    const auto uid=optional_string(target.identity.id);
    for(auto side:{Seat::zombie,Seat::zombie2})if(secrets.seat_has(side,DamageSecret::seal)&&selected_grave[seat_index(side)]==uid)return true;
    return false;
}
double UnitProtection::multiplier(const DamageTarget& target) const {
    if(double(heroes_.tick)<target.state.anchor_until.or_missing(0.))return 0.;
    if(secrets.enabled&&target.state.grave&&secrets.has(DamageSecret::seal)&&selected(target))return .25;
    if(!(0<=heroes_.tick&&heroes_.tick<until))return 1.;
    if(!target.state.card.present()||target.state.card.is_null())return 1.;
    const auto card=cards.find(target.state.card.get());
    return card!=cards.end()&&card->second.producer?producer_factor:1.;
}
double UnitProtection::amount(DamageTarget target,double amount) {
    if(amount<=0)return amount;
    if(secrets.enabled)amount=adjust(target,amount);
    amount*=multiplier(target);
    if(amount>0&&value(target.identity.content)=="死神僵尸")target.state.reaper_hurt.set(double(heroes_.tick));
    return amount;
}
} // namespace pvz::typed72
