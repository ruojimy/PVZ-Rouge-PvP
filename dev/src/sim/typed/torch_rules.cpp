#include "sim/typed/torch_rules.h"
#include "sim/typed/projectile_rules.h"
#include <algorithm>

namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& value) {return value.present() && !value.is_null() && value.get();}
bool truth(const Field<std::string>& value) {return value.present() && !value.is_null() && !value.get().empty();}
}
std::vector<TorchRules::Torch> TorchRules::points() const {
    std::vector<Torch> torches;
    const double tile=world_.runtime.tile;
    for(const auto& p:*world_.plant_roster) {
        if(p->kind!="火炬树桩" || p->hp.or_missing(0.)<=0. || p->dead.present() || p->shovel_dead.present())continue;
        torches.push_back({{(p->cell.x+.5)*tile,(p->cell.y+.5)*tile},source_ref(p),{}});
    }
    for(const auto& t:*world_.targets) {
        if(t.is_hero())continue;
        const auto& u=t.unit;
        if(!u->protection.grave || u->body.hp<=0. ||
           !truth(u->protection.card) || u->protection.card.get()!="zombie:石化火炬" ||
           world_.heroes.tick<u->patch.torch_sleep_until.or_missing(0.))continue;
        const auto& p=u->body.motion.get();
        torches.push_back({{p.x,p.y},source_ref(u),u});
    }
    return torches;
}
void TorchRules::reward(const ZombieRef& torch,Point point) {
    rewards_.petrified_resource(15.,point);
    double paid=torch->patch.torch_brain.or_missing(0.)+15.;
    if(paid>=150.) {
        double seconds=world_.protection.deathmatch?24.:36.;
        if(world_.protection.secrets.has(DamageSecret::rage))seconds*=.5;
        torch->patch.torch_sleep_until.set(world_.heroes.tick+seconds*250.);
        paid=0.;
    }
    torch->patch.torch_brain.set(paid);
}
void TorchRules::convert(const EntityRef& e,bool zombie,const std::vector<Torch>* cached) {
    if(zombie) {
        if(truth(e->source.zombie_fire))return;
    } else if(yes(e->pea.zombie_pea) || (e->kind!="豌豆" && e->kind!="冰豆"))return;
    const auto& motion=e->motion.get();
    const Point now{motion.x,motion.y};
    auto& field=e->flight.torch_visits;
    if(!field.present())field.set(std::make_shared<std::vector<std::string>>());
    const auto visits=field.get();
    // A stored previous point takes precedence, including an explicit None.
    const auto& previous=e->flight.torch_previous;
    const Point start=previous.present()?previous.get():Point{e->pea.previous_x.or_missing(now.x),now.y};
    const double width=world_.world_width.get(),tile=world_.runtime.tile;
    const double dx=wrap_delta(start.x,now.x,width),dy=now.y-start.y;
    std::vector<Torch> local;
    if(!cached){local=points();cached=&local;}
    struct Candidate {double along;std::string id;ZombieRef grave;};
    std::vector<Candidate> candidates;
    for(const auto& t:*cached) {
        auto id=world_.heroes.source_id(t.source);
        if(std::find(visits->begin(),visits->end(),id)!=visits->end())continue;
        const double reach=(t.grave?(world_.protection.secrets.has(DamageSecret::rage)?5.:2.5):
                            zombie?.75:.5)*tile;
        const double rx=wrap_delta(start.x,t.point.x,width),ry=t.point.y-start.y;
        if(rx<std::min(0.,dx)-reach || rx>std::max(0.,dx)+reach ||
           ry<std::min(0.,dy)-reach || ry>std::max(0.,dy)+reach)continue;
        const double along=(rx*dx+ry*dy)/std::max(1.e-9,dx*dx+dy*dy);
        candidates.push_back({along,std::move(id),t.grave});
    }
    std::stable_sort(candidates.begin(),candidates.end(),[](const Candidate& a,const Candidate& b){
        return a.along!=b.along?a.along<b.along:a.id<b.id;
    });
    for(const auto& c:candidates) {
        if(c.grave && world_.heroes.tick<c.grave->patch.torch_sleep_until.or_missing(0.))continue;
        visits->push_back(c.id);
        const auto& secrets=*world_.heroes.globals.secrets.get();
        const bool blue=std::find(secrets.begin(),secrets.end(),"蓝火")!=secrets.end() ||
                        (c.grave && world_.protection.secrets.has(DamageSecret::rage));
        if(zombie)e->source.zombie_fire.set(blue?"blue":"fire");
        else if(e->kind=="冰豆"){e->kind="豌豆";e->source.fire_lit.set(0.);}
        else {
            e->kind=blue?"蓝火豆":"火豆";
            e->source.fire_lit.set(0.);
            e->source.fire_color.set(blue?"blue":"fire");
        }
        if(c.grave)reward(c.grave,now);
        if(zombie || e->kind=="火豆" || e->kind=="蓝火豆")break;
    }
    e->flight.torch_previous.set(now);
}
void TorchRules::tick() {
    const auto captured=points();
    if(captured.empty())return;
    const auto entities=world_.runtime.entities.list();
    for(size_t i=0;i<entities->size();++i) {
        const auto e=entities->at(i);
        convert(e,false,&captured);
    }
}
void TorchRules::zombie_pea(const EntityRef& e) {convert(e,true,nullptr);}
void TorchRules::ignite_charmed_peas() {
    const auto entities=world_.runtime.entities.list();
    for(size_t i=0;i<entities->size();++i) {
        const auto e=entities->at(i);
        if(!yes(e->pea.charmed_pea) || e->kind!="豌豆")continue;
        zombie_pea(e);
        e->pea.previous_x.set(e->motion.get().x);
        e->pea.previous_y.set(e->motion.get().y);
        if(truth(e->source.zombie_fire)){e->kind="火豆";e->source.fire_lit.set(0.);}
    }
}
} // namespace pvz::typed72
