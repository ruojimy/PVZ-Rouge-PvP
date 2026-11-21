#include <position_head.h>
#include <iostream>
#include <stdexcept>

using namespace position_ai;
struct TestCards : ai::Services {
    pvz::typed72::ColdCard item{};
    std::string preview(const std::string&,double,double,const std::optional<std::string>&,bool) override { return {}; }
    const pvz::typed72::ColdCard& card(const std::string&) override { return item; }
    bool air_plant(const std::string&) const override { return false; }
};
int main() {
    ai::View v;
    ai::Player p;
    p.key="zombie";p.deck={"zombie:test"};p.resource=9.;p.cooldowns={{"zombie:test",2.}};
    v.players.push_back(p);
    TestCards cards;cards.item.cost=10.;
    EventChoices chooser;
    auto check=[&](int expected) {
        if(chooser.changes(v,cards)!=expected)throw std::runtime_error("event mask mismatch");
    };
    check(16);check(0);
    v.players[0].resource=10.;check(8);check(0);
    v.time=2.;check(4);check(0);
    ai::Unit grave;
    grave.id="g1";grave.hp=1.;grave.side=pvz::typed72::Seat::zombie;grave.behavior="grave";
    v.units={grave};check(1);
    v.units.front().id="g2";check(1|2);
    v.players[0].resource=3.;v.players[0].cooldowns[0].second=4.;check(0);
    v.time=4.;v.players[0].resource=10.;v.units.front().hp=0.;check(2|4|8);check(0);
    std::cout<<"11/11 event masks, including equal-count replacement and simultaneous changes\n";
}
