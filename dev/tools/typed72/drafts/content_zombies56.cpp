#include "sim/typed/content_zombies56.h"
#include "sim/typed/content_zombie56_state.h"
#include "sim/typed/cart_lifecycle.h"
#include "core/pymath.h"
#include <array>
#include <set>

namespace pvz::typed72 {
namespace {
constexpr std::array<double,4> slots{-4.,-2.,2.,4.};
bool yes(const Field<bool>& value){return value.present() && !value.is_null() && value.get();}
bool text(const Field<std::string>& value){return value.present() && !value.is_null() && !value.get().empty();}
bool leader(const ZombieRef& unit){return text(unit->source.content) && unit->source.content.get()=="舞王僵尸";}
struct Exemption {int& count;explicit Exemption(int& value):count(value){++count;}~Exemption(){--count;}};
ScriptedSpawnOrigin public_parent(const Field<std::string>& id) {
    ScriptedSpawnOrigin parent;parent.source=std::make_shared<AttackSource>();parent.public_id=id;return parent;
}
}
bool ContentZombies56::alive(const ZombieRef& unit){return unit && unit->body.hp>0. && !unit->body.ash.present();}
bool ContentZombies56::solid(Point point)const {
    const auto row=int64_t(std::floor(point.y/world_.runtime.tile));
    if(row<0)return false;if(uint64_t(row)>=published_.solid.size())return true;
    const auto& cells=published_.solid.at(size_t(row));
    return cells.at(size_t(std::floor(py::mod(point.x,world_.world_width.get())/world_.runtime.tile))%cells.size())!=0;
}
bool ContentZombies56::wild(const ZombieRef& unit)const{return wild_secret_ && world_.heroes.owner(source_ref(unit))==Seat::zombie;}
ZombieRef ContentZombies56::lookup(const Field<std::string>& id)const {
    if(!text(id))return {};
    const auto object=world_.native_objects.get(id.get());
    if(!object)return {};
    if(const auto* unit=std::get_if<ZombieRef>(&*object))return *unit;
    return {};
}
void ContentZombies56::started(const ZombieRef& unit,Seat owner) {
    services_.zombie56_event({Zombie56Event::Kind::dance_started,unit->source.id,{},owner,
        {unit->body.motion.get().x,unit->body.motion.get().y},{}});
}
void ContentZombies56::summoned(const Field<std::string>& source,const ZombieRef& child,Seat owner,std::optional<double> slot) {
    services_.zombie56_event({Zombie56Event::Kind::summon,source,child->source.id,owner,{},slot});
}
bool ContentZombies56::configure(const ZombieRef& unit,std::string_view name,double hp,bool observed) {
    if(name!="舞王僵尸" && name!="雪橇车小队" && name!="雪橇车小队僵尸")return false;
    unit->source.content.set(std::string(name));unit->body.hp=hp;unit->max_hp.set(hp);
    if(observed)unit->patch.observed_max_hp.set(hp);
    unit->base_speed=unit->native.move_speed;
    if(name=="舞王僵尸") {
        const auto owner=world_.heroes.owner(source_ref(unit)).value();auto& state=unit->content56;
        unit->body.dancing.set(1.);state.dance_clock.set(0.);state.dancing.set(true);state.dance_side.set(owner);started(unit,owner);
    }else if(name=="雪橇车小队")spawn_squad(unit);
    return true;
}
std::vector<ZombieRef> ContentZombies56::children(const ZombieRef& unit,bool free)const {
    const auto id=unit->source.id.get();const auto owner=world_.heroes.owner(source_ref(unit));std::vector<ZombieRef> result;
    for(const auto& target:*world_.targets)if(target.unit && alive(target.unit)) {
        const auto child=target.unit;const auto& parent=free?child->content56.wild_parent:child->content56.dance_owner;
        if(text(parent) && parent.get()==id && world_.heroes.owner(source_ref(child))==owner)result.push_back(child);
    }
    return result;
}
void ContentZombies56::release(const ZombieRef& unit) {
    auto& state=unit->content56;
    if(state.saved_speed.present()){unit->native.move_speed=state.saved_speed;state.saved_speed.erase();}
    state.dance_owner.erase();state.dance_slot.erase();state.impulse.erase();unit->body.dancing.set(0.);
}
ZombieRef ContentZombies56::leader_for(const ZombieRef& child) {
    const auto unit=lookup(child->content56.dance_owner);
    if(!alive(unit) || !leader(unit) || world_.heroes.owner(source_ref(unit))!=world_.heroes.owner(source_ref(child))) {
        release(child);return {};
    }
    return unit;
}
void ContentZombies56::anchor(const ZombieRef& child,const ZombieRef& unit,bool after_motion) {
    if(!alive(child))return;
    auto& state=child->content56;auto& point=child->body.motion.get();const double plk=world_.runtime.plk;
    if(!after_motion && std::abs(point.vx)+std::abs(point.vy)>1e-8)state.impulse.set(true);
    if(yes(state.impulse)) {
        const bool grounded=solid({point.x,point.y-world_.runtime.tile*.19});
        if(!(after_motion && grounded && std::abs(point.vx)<=plk*2. && point.vy>=-plk*2.)) {child->body.dancing.set(0.);return;}
        state.impulse.erase();
    }
    const auto& origin=unit->body.motion.get();
    point={py::mod(origin.x+state.dance_slot.get()*world_.runtime.tile,world_.world_width.get()),origin.y,0.,0.};
    child->body.facing=unit->body.facing;child->native.entry.set(500.);
    child->body.dancing.set(yes(unit->content56.dancing)?std::clamp(std::trunc(unit->content56.dance_clock.or_missing(0.))+1.,1.,999.):0.);
}
void ContentZombies56::before_tick() {
    for(const auto& target:*world_.targets)if(target.unit && text(target.unit->content56.dance_owner))
        if(const auto unit=leader_for(target.unit))anchor(target.unit,unit);
}
void ContentZombies56::gate(const ZombieRef& unit) {
    auto& state=unit->content56;
    if(leader(unit)) {
        for(const auto part:{"-身","-首"})for(const auto suffix:{"","-受伤","-冰冻","-灰烬","-魅惑"})
            services_.alias_art(unit->body.kind+part+suffix,std::string("舞王僵尸")+part+suffix);
        if(alive(unit)) {
            const auto owner=world_.heroes.owner(source_ref(unit)).value();
            if(!state.dance_side.present() || state.dance_side.is_null() || owner!=state.dance_side.get()) {
                state.dance_side.set(owner);state.dancing.set(false);state.dance_clock.set(0.);
            }
            if(!yes(state.dancing) && children(unit).size()+children(unit,true).size()<=2) {
                state.dancing.set(true);state.dance_clock.set(0.);started(unit,owner);
            }
            state.dance_rate.set(CartLifecycle::action_rate(*unit));
            unit->body.dancing.set(yes(state.dancing)?std::clamp(std::trunc(state.dance_clock.get())+1.,1.,999.):0.);
        }
    }
    if(text(state.dance_owner))if(const auto parent=leader_for(unit)) {
        anchor(unit,parent);
        if(yes(state.impulse)){state.saved_speed=unit->native.move_speed;unit->native.move_speed.set(.0001);}
    }
}
void ContentZombies56::finish(const ZombieRef& unit) {
    auto& state=unit->content56;
    if(state.saved_speed.present()){unit->native.move_speed=state.saved_speed;state.saved_speed.erase();}
    if(leader(unit) && alive(unit)) {
        if(yes(state.dancing)) {
            state.dance_clock.get()+=state.dance_rate.or_missing(0.);
            if(state.dance_clock.get()>=1000.) {
                if((budget_.enabled && state.dance_rate.or_missing(0.)==0.) || budget_.pending_for_source(unit->source,"dancer56") ||
                   !budget_.can_spawn(1,source_ref(unit)))state.dance_clock.set(1000.);
                else {fill_group(unit);state.dancing.set(false);state.dance_clock.set(0.);unit->body.dancing.set(0.);}
            }
        }
        for(const auto& child:children(unit))anchor(child,unit);
    }else if(text(state.dance_owner))if(const auto parent=leader_for(unit))anchor(unit,parent,true);
}
void ContentZombies56::fill_group(const ZombieRef& unit) {
    if(!alive(unit))return;
    std::set<double> occupied;for(const auto& child:children(unit))occupied.insert(child->content56.dance_slot.get());
    const auto owner=world_.heroes.owner(source_ref(unit)).value();const auto start=unit->body.motion.get();const bool free=wild(unit);
    if(free) {
        const auto available=int64_t(slots.size())-int64_t(children(unit,true).size());occupied.clear();
        for(size_t i=size_t(std::max<int64_t>(0,available));i<slots.size();++i)occupied.insert(slots[i]);
    }
    for(const auto slot:slots) {
        if(occupied.contains(slot))continue;
        if(!budget_.can_spawn(1,source_ref(unit))) {
            const auto saved=scripted_spawn_origin(unit);
            budget_.defer(source_ref(unit),"dancer56",slot,[this,saved,slot,free]{return deferred_dancer(saved,slot,free);});continue;
        }
        ZombieRef child;
        {HeroContext scope(world_.heroes,{Seat::zombie,owner,CombatPhase::summon,source_ref(unit),{}});
         Exemption exemption(world_.spawn_ban_exempt);
         child=services_.spawn_zombie56("zombie:伴舞僵尸",{py::mod(start.x+slot*world_.runtime.tile,world_.world_width.get()),start.y},
             unit->body.facing,public_parent(unit->source.id));}
        if(!child)continue;
        child->native.entry.set(500.);
        if(free) {child->content56.wild_parent=unit->source.id;child->body.facing=unit->body.facing;summoned(unit->source.id,child,owner,{});continue;}
        child->content56.dance_owner=unit->source.id;child->content56.dance_slot.set(slot);
        if(owner==Seat::plant)child->source.charmed.set(200.);
        anchor(child,unit);summoned(unit->source.id,child,owner,slot);
    }
}
bool ContentZombies56::deferred_dancer(const ScriptedSpawnOrigin& source,double slot,bool free) {
    const auto owner=world_.heroes.owner(source.source).value();auto start=source.position.get();
    const auto unit=lookup(source.source->id);const bool attached=alive(unit) && world_.heroes.owner(source_ref(unit))==owner;
    if(attached){start.x=unit->body.motion.get().x;start.y=unit->body.motion.get().y;}
    ZombieRef child;
    {HeroContext scope(world_.heroes,{Seat::zombie,owner,CombatPhase::summon,source.source,{}});Exemption exemption(world_.spawn_ban_exempt);
     child=services_.spawn_zombie56("zombie:伴舞僵尸",{py::mod(start.x+slot*world_.runtime.tile,world_.world_width.get()),start.y},source.facing.get(),source);}
    if(!child)return false;
    child->native.entry.set(500.);if(owner==Seat::plant)child->source.charmed.set(200.);
    if(free)child->content56.wild_parent=source.source->id;
    else if(attached){child->content56.dance_owner=source.source->id;child->content56.dance_slot.set(slot);anchor(child,unit);}
    summoned(source.source->id,child,owner,free?std::nullopt:std::optional<double>(slot));return true;
}
void ContentZombies56::spawn_squad(const ZombieRef& first) {
    const auto start=first->body.motion.get();const double tile=world_.runtime.tile,width=world_.world_width.get();
    first->body.motion.get().x=py::mod(start.x-.975*tile,width);first->content56.squad_owner=first->source.id;
    for(int slot=1;slot<4;++slot) {
        if(!budget_.can_spawn(1,source_ref(first))) {
            auto saved=scripted_spawn_origin(first);saved.position.get().x=start.x;saved.position.get().y=start.y;
            budget_.defer(source_ref(first),"sled_squad",slot,[this,saved,slot]{return deferred_sled(saved,slot);});continue;
        }
        ZombieRef child;
        {Exemption exemption(world_.spawn_ban_exempt);child=services_.spawn_zombie56("zombie:雪橇车小队僵尸",
            {py::mod(start.x+(slot-1.5)*.65*tile,width),start.y},first->body.facing,public_parent(first->source.id));}
        if(child)child->content56.squad_owner=first->source.id;
    }
}
bool ContentZombies56::deferred_sled(const ScriptedSpawnOrigin& source,double slot) {
    const auto start=source.position.get();ZombieRef child;
    {HeroContext scope(world_.heroes,{Seat::zombie,world_.heroes.owner(source.source).value(),CombatPhase::summon,source.source,{}});
     Exemption exemption(world_.spawn_ban_exempt);child=services_.spawn_zombie56("zombie:雪橇车小队僵尸",
         {py::mod(start.x+(slot-1.5)*.65*world_.runtime.tile,world_.world_width.get()),start.y},source.facing.get(),source);}
    if(!child)return false;child->content56.squad_owner=source.source->id;
    if(source.source->charmed.present())child->source.charmed.set(200.);return true;
}
} // namespace pvz::typed72
