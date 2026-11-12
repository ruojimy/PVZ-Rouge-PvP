#pragma once
#include "sim/typed/allegiance.h"
#include "sim/typed/geometry.h"
#include <optional>
#include <string>
#include <variant>
#include <vector>
namespace pvz::typed72 {
enum class HeroHit { normal, ash, swallow, content, lightning, spring, grenade, poison, hook, anchor, chili, tentacle, black_armor };
struct HeroDamageEvent {
    enum class Type { damage, last_stand_start, last_stand_end } type;
    Seat seat;
    double amount=0.;
    HeroHit hit=HeroHit::normal;
    std::optional<std::string> source_id;
};
struct RelicEvent {std::optional<std::string> entity;double seconds;};
struct BasketballHitEvent {std::optional<std::string> source;std::string target;};
struct MelonSplashEvent {Point position;std::optional<Seat> owner;std::optional<std::string> source;};
struct SquashSplashEvent {std::optional<std::string> entity;};
struct ZombieHeroPeaEvent {Seat seat;};
struct RallyRiseEvent {Seat seat;bool early;};
struct ResourceIncomeEvent {Seat seat;double amount;std::string source,id;bool shared_auto=false;};
struct CoinIncomeEvent {Seat seat;double amount;std::string id;};
struct EnvironmentalDamageEvent {Seat seat;double amount;};
struct HeroHealEvent {Seat seat;double amount;};
struct SturdyEvent {Seat seat;std::vector<std::string> cards;};
struct GraveWokenEvent {std::optional<std::string> entity;std::string cause;};
// One typed journal preserves cross-system emission order. A wire/replay
// serializer must consume this order, never concatenate per-system buffers.
using BattleEvent=std::variant<HeroDamageEvent,RelicEvent,BasketballHitEvent,MelonSplashEvent,SquashSplashEvent,ZombieHeroPeaEvent,RallyRiseEvent,ResourceIncomeEvent,CoinIncomeEvent,EnvironmentalDamageEvent,HeroHealEvent,SturdyEvent,GraveWokenEvent>;
} // namespace pvz::typed72
