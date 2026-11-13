// Typed migration state. This library deliberately has no V/Args/Match dependency.
#pragma once
#include <functional>
#include <optional>
#include "sim/typed/bonus_state.h"
#include "sim/typed/content_entity_state.h"
#include "sim/typed/flying_state.h"
#include "sim/typed/mortar_state.h"
#include "core/pyrandom.h"
#include "sim/typed/field.h"
#include "sim/typed/geometry.h"
#include "sim/typed/attack_source.h"
#include "sim/typed/particle_dispatch.h"
#include "sim/typed/content_target_state.h"
#include "sim/typed/projectile_state.h"
#include "sim/typed/combat_events.h"
#include "sim/typed/death_marker.h"
#include "sim/typed/chili_state.h"
#include "sim/typed/service_state.h"
#include "sim/typed/squash_state.h"
#include "sim/typed/zombie_pea_state.h"
#include <array>
#include <cstdint>
#include <deque>
#include <limits>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <span>
#include <algorithm>

namespace pvz::typed72 {

template<class Tag> struct Handle {
    uint32_t index = std::numeric_limits<uint32_t>::max();
    uint64_t generation = 0;
    friend bool operator==(const Handle&, const Handle&) = default;
};

// Stable addresses and generation IDs; erase preserves the order of every
// surviving unit. Slots can be reused, but old IDs can never name a new unit.
template<class T> class Store {
    struct Slot { uint64_t generation = 1; std::optional<T> value; };
public:
    using Id = Handle<T>;
    template<class... Args> Id emplace(Args&&... args) {
        if (free_.empty()) {
            if (slots_.size() >= std::numeric_limits<uint32_t>::max()) throw std::length_error("typed store full");
            slots_.emplace_back();
            free_.push_back(static_cast<uint32_t>(slots_.size() - 1));
        }
        const auto index = free_.back();
        auto& slot = slots_[index];
        slot.value.emplace(std::forward<Args>(args)...);
        Id id{index, slot.generation};
        try { order_.push_back(id); }
        catch (...) { slot.value.reset(); throw; }
        free_.pop_back();
        return id;
    }
    T* find(Id id) noexcept {
        if (id.index >= slots_.size()) return nullptr;
        auto& slot = slots_[id.index];
        return slot.generation == id.generation && slot.value ? &*slot.value : nullptr;
    }
    const T* find(Id id) const noexcept { return const_cast<Store*>(this)->find(id); }
    T& at(Id id) { auto* p = find(id); if (!p) throw std::out_of_range("stale typed handle"); return *p; }
    const T& at(Id id) const { auto* p = find(id); if (!p) throw std::out_of_range("stale typed handle"); return *p; }
    bool erase(Id id) {
        if (!find(id)) return false;
        auto& slot = slots_[id.index];
        // Reserve before modifying state so an allocation failure is atomic.
        if (slot.generation != std::numeric_limits<uint64_t>::max()) free_.push_back(id.index);
        slot.value.reset();
        if (slot.generation != std::numeric_limits<uint64_t>::max()) ++slot.generation;
        for (auto i = order_.begin(); i != order_.end(); ++i)
            if (*i == id) { order_.erase(i); break; }
        return true;
    }
    // Batch reclamation compacts iteration order once, avoiding quadratic
    // cleanup when an entire projectile volley expires on the same tick.
    void erase_many(std::span<const Id> ids) {
        free_.reserve(free_.size()+ids.size());
        for(const auto id:ids)if(find(id)) {
            auto& slot=slots_[id.index];slot.value.reset();
            if(slot.generation!=std::numeric_limits<uint64_t>::max()){++slot.generation;free_.push_back(id.index);}
        }
        std::erase_if(order_,[&](Id id){return find(id)==nullptr;});
    }
    const std::vector<Id>& order() const noexcept { return order_; }
    size_t size() const noexcept { return order_.size(); }
private:
    std::deque<Slot> slots_;
    std::vector<uint32_t> free_;
    std::vector<Id> order_;
};

// Kept as typed strings while source-to-catalog identity is reconciled. These
// are never dynamic value containers or callable objects.
struct ZombieRecordFields {
    ContentTargetState content_target;
    std::string kind, armor, hand;
    double hp = 0, armor_hp = 0, hand_hp = 0, facing = 1;
    double hurt = 0, hand_hurt = 0;
    Field<double> ash, balloon;
    Field<double> size, berserk, pole_vault, dancing;
    Field<bool> in_water;
    Field<double> ice,butter,stun,gravity;
    Field<bool> blown;
    Field<DeathMarker> dead;
};
struct Zombie : ZombieRecordFields {
    MotionRecord motion;
};
struct Entity {
    BonusEntityState bonus;
    ContentEntityState content_state;
    RecordId identity;
    FlyingShotState flying;
    MortarShotState mortar;
    ChiliState chili;
    EntityServiceState service;
    SquashState squash;
    ZombiePeaState pea;
    Field<RecordId> native_source_zombie;
    Field<double> tracking;
    AttackSource source;
    ProjectileFlight flight;
    // The name is one string, also visible to all retained attack sources.
    std::string& kind;
    MotionRecord motion;
    double facing = 1;
    Field<double> gravity, through_wall, rotation;
    EntityExpiry expires;
    Field<double> cannon_lock,cannon_column;
    Field<DeathMarker> monochrome;
    Field<bool> in_water;
    Field<uint64_t> flat_sprite;
    Field<bool> flying_plant;
    Field<std::string> art_name;
    Entity(std::string name,double direction,Motion position):kind(initialize_name(source,std::move(name))),motion(position),facing(direction){}
    Entity(const Entity&)=delete;
    Entity& operator=(const Entity&)=delete;
private:
    static std::string& initialize_name(AttackSource& source,std::string name){source.projectile.set(std::move(name));return source.projectile.get();}
};
using EntityRef=std::shared_ptr<Entity>;
inline std::shared_ptr<AttackSource> source_ref(const EntityRef& entity){entity->source.entity.bind(entity);return {entity,&entity->source};}
using EntityRoster=std::vector<EntityRef>;
// A list identity and object identities are different things in the native
// loop: replacing the active list does not retarget an in-progress iterator.
// Only references are stored in lists/handles; each entity has one body.
class EntityCollection {
public:
    explicit EntityCollection(RecordIdentities& identities):identities_(identities){}
    using Id=Store<EntityRef>::Id;
    Id emplace(EntityRef entity) {
        if(!entity)throw std::invalid_argument("null entity");
        const auto id=register_entity(entity);current_->push_back(std::move(entity));return id;
    }
    EntityRef* find(Id id)noexcept{return storage_.find(id);}
    const EntityRef* find(Id id)const noexcept{return storage_.find(id);}
    EntityRef& at(Id id){return storage_.at(id);}
    const EntityRef& at(Id id)const{return storage_.at(id);}
    Id id(const EntityRef& entity)const{return ids_.at(entity.get());}
    // Handle order is for pool diagnostics. Combat always iterates list().
    const std::vector<Id>& order()const noexcept{return storage_.order();}
    std::shared_ptr<EntityRoster> list()const noexcept{return current_;}
    // Temporary native callback views do not re-register/reclaim objects.
    // Replacing the authoritative roster still uses replace() below.
    std::shared_ptr<EntityRoster> exchange_view(std::shared_ptr<EntityRoster> view) {
        if(!view)throw std::invalid_argument("null entity view");return std::exchange(current_,std::move(view));
    }
    bool erase(Id id) {
        const auto* found=find(id);if(!found)return false;const auto entity=*found;
        std::erase(*current_,entity);ids_.erase(entity.get());return storage_.erase(id);
    }
    // Original DELETE_SUBSCR removes one occurrence. During an owner-specific
    // phase the full match roster still holds its handles until reconciliation.
    void erase_at(size_t index) {
        const auto e=current_->at(index);
        current_->erase(current_->begin()+index);
        if(current_!=authoritative_ || std::find(current_->begin(),current_->end(),e)!=current_->end())return;
        const auto i=ids_.find(e.get());
        if(i!=ids_.end()){storage_.erase(i->second);ids_.erase(i);}
    }
    void replace(std::shared_ptr<EntityRoster> next) {
        if(!next)throw std::invalid_argument("null entity roster");
        std::unordered_set<const Entity*> keep;keep.reserve(next->size());
        for(const auto& entity:*next){if(!entity)throw std::invalid_argument("null entity in roster");keep.insert(entity.get());register_entity(entity);}
        std::vector<Id> retired;retired.reserve(ids_.size());
        for(auto i=ids_.begin();i!=ids_.end();)if(!keep.contains(i->first)){retired.push_back(i->second);i=ids_.erase(i);}else ++i;
        storage_.erase_many(retired);current_=std::move(next);authoritative_=current_;
    }
private:
    RecordIdentities& identities_;
    Store<EntityRef> storage_;
    std::unordered_map<const Entity*,Id> ids_;
    std::shared_ptr<EntityRoster> current_=std::make_shared<EntityRoster>();
    std::shared_ptr<EntityRoster> authoritative_=current_;
    Id register_entity(const EntityRef& entity) {
        if(const auto i=ids_.find(entity.get());i!=ids_.end())return i->second;
        if(!entity->identity.value)entity->identity=identities_.assign();
        const auto id=storage_.emplace(entity);
        try{ids_.emplace(entity.get(),id);}catch(...){storage_.erase(id);throw;}return id;
    }
};
class EntityBirthObserver {
public:
    virtual ~EntityBirthObserver()=default;
    virtual void entity_born(const EntityRef&)=0;
};
class NativeEntityConstructor {
public:
    virtual ~NativeEntityConstructor()=default;
    virtual void add_entity(std::string,double,Motion)=0;
};
enum class ShooterKind { pea, ice_pea, repeater, star, cactus, gatling };
struct Shooter {
    ShooterKind kind = ShooterKind::pea;
    double row = 0, col = 0, facing = 1;
    double cooldown = -1, animation = 0, double_shot = 0, gatling_shot = 0;
};
// journal_mark: events.size() when played. V NativeAudio records event sounds the moment
// _emit fires, so native sounds and journal events interleave by this mark.
struct Sound { std::string name; Point position; bool spatial=true; size_t journal_mark=0; int64_t tick=-1; };
struct ParticleRequest { std::string name; Point position; int count = 0; };
using Color = std::array<uint8_t, 4>;
struct SpritePixels {
    int width = 0, height = 0;
    std::vector<Color> pixels;
    const Color& at(int x, int y) const {
        if (x < 0 || y < 0 || x >= width || y >= height) throw std::out_of_range("typed sprite pixel");
        return pixels.at(size_t(y)*width+x);
    }
};
struct Particle { Color color{}; Motion motion; double age = 0; };
struct ParticleRect { Color color{}; double x=0,y=0,width=0,height=0; };
struct ParticlePresentation {
    bool enabled = false;
    Point camera;
    double screen_width = 1152;
    // g['总高'] (screen height). patch1501 fume bubbles cull against 总宽/总高, the screen.
    double screen_height = 0.;
    std::unordered_map<std::string, SpritePixels> atlas;
    std::unordered_map<std::string,std::string> source_art;
    const std::string& sprite_name(const std::string& name)const {
        const auto it=source_art.find(name);
        return it==source_art.end()?name:it->second;
    }
};

// Shared typed RNG, entity births and presentation state. A complete battle
// owns its unit roster separately; isolated raw-stage tests add their roster
// through CombatStages below. There is no duplicated authoritative HP array.
struct CombatRuntime : NativeEntityConstructor {
    explicit CombatRuntime(int64_t seed = 1) : rng(seed),entities(identities) {}
    CombatRuntime(const CombatRuntime&)=delete;
    CombatRuntime& operator=(const CombatRuntime&)=delete;
    PyRandom rng;
    double tile = 48, plk = .0048;
    RecordIdentities identities;
    EntityCollection entities;
    std::vector<BattleEvent> events;
    std::vector<std::string> other_images;
    Field<double> nuclear_flash;
    Field<std::array<double,3>> screen_shake;
    Field<double> freeze_flash;
    Field<ChiliHits> chili_player_hits;
    EntityBirthObserver* birth_observer=nullptr;
    // The original constructor is the base layer. A battle phase installs its
    // typed global constructor so nested head/armor drops enter the same chain.
    NativeEntityConstructor* native_constructor=this;
    std::vector<Sound> sounds; int64_t sound_tick=0;
    std::vector<ParticleRequest> particles;
    std::vector<Particle> particle_state;
    std::vector<ParticleRect> particle_rects;
    ParticlePresentation presentation;
    uint64_t damage_calls = 0, surface_calls = 0, shot_calls = 0;
    std::vector<uint64_t> branches;
    bool instrument = false;
    bool branch(size_t id, bool result) {
        if (instrument) {
            if (branches.size() <= id*2+1) branches.resize(id*2+2);
            ++branches[id*2 + (result ? 1 : 0)];
        }
        return result;
    }
    void sound(std::string name, const Motion& m) { sounds.push_back({std::move(name), {m.x, m.y}, true, events.size(), sound_tick}); }
    // native_audio.emit(name) without a position: V places it at the current source's 位置
    // (units and entities; an avatar source has none). The composition installs the lookup.
    std::function<std::optional<Point>()> sound_source;
    void play_sound(std::string name){
        if(sound_source)if(const auto at=sound_source()){sounds.push_back({std::move(name),*at,true,events.size(),sound_tick});return;}
        sounds.push_back({std::move(name),{},false,events.size(),sound_tick});
    }
    Entity& spawn(std::string name, double facing, Motion motion) {
        auto e=std::make_shared<Entity>(std::move(name),facing,motion);entities.emplace(e);
        if(birth_observer)birth_observer->entity_born(e);
        return *e;
    }
    void add_entity(std::string name,double facing,Motion pos)override{spawn(std::move(name),facing,pos);}
    Entity& construct_entity(std::string name,double facing,Motion pos){
        native_constructor->add_entity(std::move(name),facing,pos);
        return *entities.list()->back();
    }
    NativeParticleDispatch* particle_dispatch=nullptr;
    bool particle_dispatch_required=false;
    void bind_particles(NativeParticleDispatch& dispatch){if(particle_dispatch&&particle_dispatch!=&dispatch)throw std::logic_error("particle dispatch already bound");particle_dispatch=&dispatch;}
    void require_particles(bool required=true){particle_dispatch_required=required;}
    void emit_particles_native(const std::string& name, Point position, int count,std::optional<int> direction={});
    void emit_particles(const std::string& name, Point position, int count,std::optional<int> direction={});
};
class NativeBirthScope {
public:
    NativeBirthScope(CombatRuntime& w,NativeEntityConstructor& constructor):world_(w),previous_(std::exchange(w.native_constructor,&constructor)){}
    ~NativeBirthScope(){world_.native_constructor=previous_;}
    NativeBirthScope(const NativeBirthScope&)=delete;
private:
    CombatRuntime& world_;
    NativeEntityConstructor* previous_;
};
struct CombatStages : CombatRuntime {
    explicit CombatStages(int64_t seed=1):CombatRuntime(seed){}
    Store<Zombie> zombies;
};

void damage_zombie(CombatStages&, Handle<Zombie>, double facing, double amount);
bool surface_damage_zombie(CombatStages&, Handle<Zombie>, double facing, double amount);
void damage_zombie(CombatRuntime&, Zombie&, double facing, double amount);
enum class SurfaceDamageResult { ashed, armorless, hand_hit };
SurfaceDamageResult surface_hand_damage(CombatRuntime&, Zombie&, double facing, double amount);
void shooter_attack(CombatStages&, Shooter&, const std::vector<double>* row_targets, size_t zombie_count, bool emperor);

} // namespace pvz::typed72
