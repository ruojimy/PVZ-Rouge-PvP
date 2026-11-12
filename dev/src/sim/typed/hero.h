// PvP hero state and allegiance. No dynamic world, value, or callback ABI.
#pragma once
#include "sim/typed/state.h"
#include "sim/typed/attack_identity.h"
#include "sim/typed/zombie_fields.h"
#include <memory>
#include <string_view>

namespace pvz::typed72 {

enum class CombatPhase { plants, zombies, entities, other, content, player, summon };
std::string_view hit_name(HeroHit);

// Schema lists are expanded into fixed, statically typed members. The names
// on the right are used only by cold boundary codecs and migration auditing.
#define PVZ72_HERO_NUMBERS(X) \
 X(jump,"玩家跳跃") X(double_jump,"二段跳") X(facing,"玩家方向") \
 X(down,"玩家倒地") X(hp,"玩家血量") X(balloon,"气球") X(water_ice,"冻水") \
 X(speed_max,"speedmax") X(angle,"dushu") X(speed,"speed") X(wjx,"wjx") X(wjy,"wjy") \
 X(recovery,"玩家恢复") X(hurt,"玩家受伤") X(xx,"xx") X(yy,"yy") \
 X(tail,"猫尾") X(tail_cd,"猫尾cd") X(tail_swing,"猫尾摇摆") \
 X(tail_tip_x,"citoux") X(head_angle,"toudushu") \
 X(chili_launch,"辣飞天") X(chili_lock_until,"__pvz_sb_chili_launch_lock_until")
#define PVZ72_HERO_BOOLEANS(X) X(in_water,"玩家入水") X(water,"入水") X(sbs,"sbs")
#define PVZ72_HERO_STRINGS(X) X(mode,"模式") X(skin,"玩家皮肤")
#define PVZ72_HERO_COMBAT(X) X(position) X(hp) X(recovery) X(hurt) X(down) X(chili_launch) X(chili_lock_until)

struct HeroFrame {
#define NUM(n,k) Field<double> n;
    PVZ72_HERO_NUMBERS(NUM)
#undef NUM
#define FLAG(n,k) Field<bool> n;
    PVZ72_HERO_BOOLEANS(FLAG)
#undef FLAG
#define STR(n,k) Field<std::string> n;
    PVZ72_HERO_STRINGS(STR)
#undef STR
    // Native position lists alias through target selection and proxy views.
    // A frame save must retain that identity, not copy the four coordinates.
    Field<std::shared_ptr<Motion>> position;
    Field<std::shared_ptr<std::vector<std::string>>> secrets;
    void overlay(const HeroFrame&,bool include_secrets);
};
struct HeroState {
    HeroFrame frame;
    Field<double> max_hp, ice, butter, stun, last_damage, regen_progress;
    Field<double> pea_angle;
    Field<int64_t> native_ticks;
    Field<int> landing_result;
    Field<int> balloon_hp;
    Field<double> cold_until,previous_hp;
    Field<double> water_damage_clock,masochist_ready;
    Field<bool> sturdy_down;
    Field<bool> floating_body,rally_before,rally_eligible,rally_checked;
    std::shared_ptr<AttackSource> avatar_source;
    std::optional<AttackIdentity> launch_attack;
    std::optional<Seat> actual_seat;
};
struct HeroPlayer {
    std::vector<std::string> secrets;
    double hp = 40, marked_until = 0, hero_damage = 0;
    // Public match coordinates at the last synchronization boundary. Native
    // movement can already have advanced when a targeting rule reads these.
    Point position;
    double height=0.;
    double max_hp=40.;
    int move=0;
    bool jump_held=false;
    uint64_t jump_presses=0;
    std::vector<std::pair<std::string,double>> cooldowns;
};

struct HeroSelection {
    Seat target, owner;
    CombatPhase phase;
    std::shared_ptr<AttackSource> source;
    std::optional<std::string> attack;
};
struct HeroBudgetKey {
    Seat seat;
    HeroHit hit;
    std::string attack;
    friend bool operator==(const HeroBudgetKey&, const HeroBudgetKey&) = default;
};
struct HeroBudgetHash { size_t operator()(const HeroBudgetKey&) const noexcept; };
struct HeroBudget { HeroBudgetKey key; int64_t tick; double used; };
struct ChiliAttackKey {
    std::optional<Seat> owner;
    std::string identity;
    friend bool operator==(const ChiliAttackKey&,const ChiliAttackKey&)=default;
};

class HeroCombat;
struct TypedBattleState;
struct ProjectileFlight;
class HeroContext {
public:
    HeroContext(HeroCombat&, HeroSelection);
    ~HeroContext() noexcept;
    HeroContext(const HeroContext&) = delete;
    HeroContext& operator=(const HeroContext&) = delete;
    void close();
private:
    HeroCombat* world_;
    HeroFrame saved_;
    std::optional<HeroSelection> previous_;
};

// Proxy fields mirror native hit reads but never own another hero's HP or
// position. sync() retains the original observable cache/write semantics.
struct HeroProxyState : ZombieRecordFields {
    RecordId identity;
    AttackSource source;
    ZombieNativeState native;
    Field<double> chili_row_hint;
    Field<double> observed_max_hp,plant_max_hp;
    std::shared_ptr<Motion> position;
    HeroProxyState(){source.bind_zombie_kind(kind);}
    HeroProxyState(const HeroProxyState&)=delete;
    HeroProxyState& operator=(const HeroProxyState&)=delete;
};
inline std::shared_ptr<AttackSource> source_ref(const std::shared_ptr<HeroProxyState>& proxy){return {proxy,&proxy->source};}
enum class HeroStatus { ice, butter, stun };
enum class HeroConversion { charm,death,expiry,emerge,kind,size,armor,armor_hp,hand,hand_hp };

class HeroCombat {
public:
    explicit HeroCombat(CombatRuntime& presentation) : events(presentation.events),presentation_(presentation) {}
    HeroCombat(const HeroCombat&) = delete;
    HeroCombat& operator=(const HeroCombat&) = delete;
    // Aliases select existing avatars, including the temporary second-seat
    // faction aliases used in team battles. They do not duplicate state.
    std::array<std::optional<HeroState>, 4> heroes;
    std::array<size_t, 4> aliases{0,1,2,3};
    std::array<std::optional<HeroPlayer>, 4> players;
    HeroFrame globals;
    std::optional<HeroSelection> active;
    std::array<std::shared_ptr<HeroProxyState>, 4> proxies;
    std::array<std::vector<std::shared_ptr<AttackSource>>, 3> phase_sources;
    const TypedBattleState* live_world=nullptr;
    std::optional<int64_t> source_index;
    int64_t tick = 0;
    double time = 0, mark_seconds = 0, water_ice = 0;
    HeroHit damage_kind = HeroHit::normal;
    uint64_t sequence = 0;
    std::array<std::optional<double>,4> last_stand;
    std::array<bool,4> last_stand_used{};
    std::vector<Seat> last_stand_order;
    bool damage_factors_enabled = true, last_stand_enabled = true, damage_events_enabled = true;
    std::vector<BattleEvent>& events;

    bool contains(Seat) const;
    HeroState& hero(Seat);
    const HeroState& hero(Seat) const;
    std::shared_ptr<AttackSource> source() const;
    void select_plant_seat(Seat);
    void switch_plant_globals(Seat);
    std::optional<Seat> owner(const std::shared_ptr<AttackSource>& explicit_source = {}) const;
    std::string source_id(const std::shared_ptr<AttackSource>&);
    void tag_entity(const std::shared_ptr<AttackSource>& entity,const Motion* position,ProjectileFlight&,
                    std::optional<Seat> explicit_owner={},const std::shared_ptr<AttackSource>& explicit_source={});
    HeroBudgetKey attack_key(Seat, HeroHit);
    ChiliAttackKey chili_attack_key();
    const std::vector<HeroBudget>& budgets() const { return budgets_; }
    double damage(Seat, double, HeroHit = HeroHit::normal);
    std::optional<double> player_damage(double);
    std::optional<double> source_amount(Seat) const;
    HeroProxyState& proxy(Seat);
    HeroProxyState& cached_proxy(Seat side)const {
        const auto& p=proxies.at(seat_index(side));if(!p)throw std::out_of_range("hero proxy not constructed");return *p;
    }
    std::shared_ptr<AttackSource> proxy_source(Seat side)const {cached_proxy(side);return source_ref(proxies.at(seat_index(side)));}
    void sync_proxies();
    void context_effects(Seat target,Seat owner,CombatPhase);
    void write_proxy_hp(Seat, double);
    void write_proxy_ash(Seat);
    void write_proxy_status(Seat, HeroStatus, double);
    void write_proxy_conversion(Seat,HeroConversion);
    void step_last_stand();
private:
    friend class HeroContext;
    CombatRuntime& presentation_;
    std::vector<HeroBudget> budgets_;
    std::unordered_map<HeroBudgetKey,size_t,HeroBudgetHash> budget_index_;
    void sync_proxy(Seat);
    static void sync_proxy_state(HeroProxyState&,const HeroState&);
    double cap_damage(HeroBudgetKey, double, double);
    double damage_factor(Seat) const;
    double last_stand_amount(Seat, double);
    void hurt(double, bool pvp);
    void on_damage(Seat, double, HeroHit, const std::shared_ptr<AttackSource>&);
};

std::optional<double> balanced_hero_amount(const AttackSource*, Seat, const HeroFrame&);
std::string_view projectile_fire_color(const AttackSource&,const HeroFrame&);

} // namespace pvz::typed72
