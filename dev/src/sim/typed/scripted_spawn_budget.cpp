#include "sim/typed/scripted_spawn_budget.h"
#include <algorithm>

namespace pvz::typed72 {
ScriptedSpawnOrigin scripted_spawn_origin(const ZombieRef& unit) {
    ScriptedSpawnOrigin result;
    result.source=std::make_shared<AttackSource>();
    auto& copy=*result.source;
    const auto& source=unit->source;
    copy.id=source.id;copy.owner=source.owner;copy.seat=source.seat;
    copy.wave_index=source.wave_index;copy.content=source.content;copy.charmed=source.charmed;
    result.public_id=source.id;
    if(!result.public_id.present())result.public_id.set_null();
    result.facing.set(unit->body.facing);
    result.position.set(unit->body.motion.get());
    if(unit->barrel_position.present())result.barrel_position.set(*unit->barrel_position.get());
    return result;
}
size_t ScriptedSpawnKeyHash::operator()(const ScriptedSpawnKey& key)const noexcept {
    size_t hash=std::hash<std::string>{}(key.source);
    const auto combine=[&](size_t part){hash^=part+size_t(0x9e3779b9)+(hash<<6)+(hash>>2);};
    combine(std::hash<std::string>{}(key.kind));combine(std::hash<double>{}(key.slot));
    return hash;
}
int ScriptedSpawnBudget::limit()const {
    const auto& raw=limits.director.present()?limits.director:limits.rule;
    if(!raw.present() || raw.is_null())return 40;
    return int(std::clamp<int64_t>(raw.get(),1,200));
}
bool ScriptedSpawnBudget::live_enemy(const CombatTarget& target) {
    return target.unit && target.unit->body.hp>0. && !target.unit->body.ash.present() &&
           !target.unit->source.charmed.present() && !target.unit->protection.grave && !target.unit->orphan_barrel;
}
size_t ScriptedSpawnBudget::count()const {
    return size_t(std::count_if(world_.targets->begin(),world_.targets->end(),live_enemy));
}
int64_t ScriptedSpawnBudget::available()const {
    return enabled?std::max<int64_t>(0,int64_t(limit())-int64_t(count())):200;
}
bool ScriptedSpawnBudget::can_spawn(int64_t count,const std::shared_ptr<AttackSource>& source)const {
    return !enabled || (source && source->charmed.present()) || available()>=count;
}
size_t ScriptedSpawnBudget::pending_count(std::optional<int64_t> wave)const {
    if(!wave)return ordered_.size();
    return size_t(std::count_if(ordered_.begin(),ordered_.end(),[&](const auto& item){
        return item.wave.present() && !item.wave.is_null() && item.wave.get()==*wave;
    }));
}
bool ScriptedSpawnBudget::pending_for_source(const AttackSource& source,std::optional<std::string_view> kind)const {
    const auto& id=source.id;
    if(!id.present() || id.is_null())return false;
    return std::any_of(ordered_.begin(),ordered_.end(),[&](const auto& item){
        return item.key.source==id.get() && (!kind || item.key.kind==*kind);
    });
}
bool ScriptedSpawnBudget::defer(const std::shared_ptr<AttackSource>& source,std::string kind,double slot,
        std::function<bool()> create) {
    if(!source || !create)throw std::invalid_argument("scripted spawn requires a source and constructor");
    const auto& field=source->id;
    const auto id=field.present() && !field.is_null() && !field.get().empty()?field.get():world_.heroes.source_id(source);
    ScriptedSpawnKey key{id,std::move(kind),slot};
    if(index_.contains(key))return false;
    if(ordered_.size()>=3200)throw std::length_error("scripted summon request capacity exceeded");
    auto wave=source->wave_index;
    if(!wave.present())wave.set_null();
    ordered_.push_back({key,wave,std::move(create)});
    const auto item=std::prev(ordered_.end());
    try{index_.emplace(key,item);}catch(...){ordered_.erase(item);throw;}
    ++deferred;peak_pending=std::max<uint64_t>(peak_pending,ordered_.size());
    services_.summon_deferred(key,wave);
    return true;
}
void ScriptedSpawnBudget::drain() {
    if(!enabled || draining)return;
    draining=true;
    struct Reset {bool& flag;~Reset(){flag=false;}} reset{draining};
    while(!ordered_.empty() && can_spawn()) {
        // A constructor can enqueue children, end the battle or recurse.
        // Retain its callable and key independently of the pending list.
        const auto request=ordered_.front();
        if(!request.create())break;
        const auto found=index_.find(request.key);
        if(found==index_.end())throw std::out_of_range("completed scripted request was removed during construction");
        ordered_.erase(found->second);index_.erase(found);++admitted;
    }
}
void ScriptedSpawnBudget::clear(){index_.clear();ordered_.clear();}
void ScriptedSpawnBudget::inherit(AttackSource& child,const AttackSource* parent) {
    if(!parent)return;
    if(parent->wave_index.present())child.wave_index=parent->wave_index;
    if(parent->seat)child.seat=parent->seat;
}
bool ScriptedSpawnBudget::hold_dance()const {
    const auto source=world_.heroes.source();
    return source && (!can_spawn(1,source) || pending_for_source(*source,"native_dancer"));
}
bool ScriptedSpawnBudget::hold_spawn()const {
    return !can_spawn(1,world_.heroes.source());
}
bool ScriptedSpawnBudget::defer_dancer(Point position,double facing,int64_t slot) {
    const auto source=world_.heroes.source();
    if(can_spawn(1,source))return false;
    if(!source)throw std::logic_error("native dancer has no producer");
    const bool charmed=source->charmed.present();
    ScriptedSpawnOrigin parent;
    parent.source=std::make_shared<AttackSource>();
    parent.source->id=source->id;parent.source->seat=source->seat;parent.source->wave_index=source->wave_index;
    parent.public_id=source->id;
    if(!parent.public_id.present())parent.public_id.set_null();
    defer(source,"native_dancer",double(slot),[this,position,facing,charmed,parent]() {
        ZombieRef child;
        {
            struct Exemption {
                int& count;
                explicit Exemption(int& count):count(count){++count;}
                ~Exemption(){--count;}
            } exemption(world_.spawn_ban_exempt);
            HeroContext context(world_.heroes,{Seat::zombie,charmed?Seat::plant:Seat::zombie,
                CombatPhase::summon,parent.source,{}});
            child=services_.spawn_dancer(position,facing,parent);
        }
        if(!child)return false;
        child->native.entry.set(300.);
        if(charmed)child->source.charmed.set(0.);
        inherit(child->source,parent.source.get());
        return true;
    });
    return true;
}
} // namespace pvz::typed72
