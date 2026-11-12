#include "sim/typed/native_status.h"
#include "core/pymath.h"
#include <algorithm>

namespace pvz::typed72 {
std::shared_ptr<PoisonLayers> NativeStatus::layers(PoisonState& state) {
    if(!state.layers.present() || state.layers.is_null()) {
        auto result=std::make_shared<PoisonLayers>();
        result->emplace_back(state.level.get(),std::make_shared<PoisonLayer>(
            PoisonLayer{state.until.get(),state.next.get(),state.owner.get()}));
        state.layers.set(result);
    }
    return state.layers.get();
}

void NativeStatus::summarize(PoisonSlot& slot,const std::shared_ptr<PoisonState>& state) {
    const auto values=layers(*state);
    if(values->empty()){slot.erase();return;}
    const auto strongest=std::max_element(values->begin(),values->end(),
        [](const auto& left,const auto& right){return left.first<right.first;});
    double until=values->front().second->until,next=values->front().second->next;
    for(const auto& [level,layer]:*values){until=std::max(until,layer->until);next=std::min(next,layer->next);}
    state->level.set(strongest->first);state->until.set(until);state->next.set(next);
    state->owner.set(strongest->second->owner);
}

void NativeStatus::apply(const ContentTarget& target,int level,double duration,Seat owner) {
    if((level!=1 && level!=2) || duration<=0.)return;
    // Native plants have 植物血 and fail the source's 血量 admission check.
    const auto* body=std::get_if<CombatTarget>(&target);
    if(!body)return;
    auto& heroes=world_.heroes;
    const double hp=body->is_hero()?heroes.cached_proxy(body->hero).hp:body->unit->body.hp;
    const auto source=body->is_hero()?heroes.proxy_source(body->hero):source_ref(body->unit);
    if(hp<=0. || heroes.owner(source)==owner)return;
    auto& slot=body->is_hero()?heroes.hero(body->hero).poison:body->unit->poison.poison;
    if(!slot.present()) {
        auto state=std::make_shared<PoisonState>();state->layers.set(std::make_shared<PoisonLayers>());
        slot.set(state);
    }
    const auto state=slot.get();const auto values=layers(*state);
    const auto old=std::find_if(values->begin(),values->end(),[&](const auto& item){return item.first==level;});
    const double now=double(heroes.tick);
    const double next=old!=values->end() && old->second->until>=now?old->second->next:now+250.;
    auto layer=std::make_shared<PoisonLayer>(PoisonLayer{now+py::round0(duration*250.),next,owner});
    if(old==values->end())values->emplace_back(level,std::move(layer));else old->second=std::move(layer);
    summarize(slot,state);
}

void NativeStatus::pulse(const Subject& subject,const PoisonLayer& layer,int level) {
    auto& heroes=world_.heroes;
    if(subject.avatar) {
        const auto identity=subject.source();
        const auto side=parse_seat(identity->owner.get());
        auto source=std::make_shared<AttackSource>();source->owner.set(std::string(seat_name(layer.owner)));
        source->id.set("poison:"+identity->id.get());
        // Preserve the frozen controller's explicit owner route, including
        // whichever hero is currently selected by that faction alias.
        HeroContext context(heroes,{side,layer.owner,CombatPhase::status,source,{}});
        heroes.damage(side,double(level),HeroHit::poison);
        return;
    }
    const auto unit=subject.unit;
    const double amount=world_.protection.amount(unit->damage_target(),double(level)*4.);
    unit->body.hp-=amount;unit->body.hurt=1.;
    services_.poison_damage(unit->source.id,amount,level);
    if(unit->body.hp>0.)return;
    if(unit->orphan_barrel)services_.break_poisoned_barrel(unit);
    else services_.detach_poisoned_barrel(unit);
    unit->poison.killed.set(true);unit->poison.armor_triggered.set(true);
    unit->body.armor.clear();unit->body.armor_hp=0.;unit->body.hand.clear();unit->body.hand_hp=0.;
    unit->poison.imp_armor.set("");unit->poison.imp_armor_hp.set(0.);
}

void NativeStatus::advance(const Subject& subject,double now) {
    auto& slot=subject.slot();
    if(!slot.present() || slot.is_null())return;
    const auto state=slot.get();
    if(state->empty())return;
    if(subject.hp()<=0.){slot.erase();return;}
    const auto values=layers(*state);
    const auto original=*values;
    for(const auto& [level,layer]:original) {
        if(world_.heroes.owner(subject.source())==layer->owner) {
            std::erase_if(*values,[&](const auto& item){return item.first==level;});
            continue;
        }
        while(layer->next<=std::min(now,layer->until)) {
            pulse(subject,*layer,level);
            layer->next+=250.;
            if(subject.hp()<=0.)break;
        }
        if(now>=layer->until)std::erase_if(*values,[&](const auto& item){return item.first==level;});
        if(subject.hp()<=0.){values->clear();break;}
    }
    summarize(slot,state);
}

void NativeStatus::tick(std::span<const Seat> avatar_order) {
    const double now=double(world_.heroes.tick);
    std::vector<Subject> subjects;
    subjects.reserve(world_.targets->size()+avatar_order.size());
    // Poison admitted through a hero collider belongs to its avatar. The
    // transient collider list never duplicates that authoritative status.
    for(const auto& target:*world_.targets)if(target.unit)subjects.push_back({target.unit,{}});
    for(const auto seat:avatar_order)subjects.push_back({{},&world_.heroes.hero(seat)});
    for(const auto& subject:subjects)advance(subject,now);
}
} // namespace pvz::typed72
