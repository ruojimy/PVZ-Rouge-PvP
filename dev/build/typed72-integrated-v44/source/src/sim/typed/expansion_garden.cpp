#include "sim/typed/expansion_garden.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <cmath>

namespace pvz::typed72 {
namespace {
constexpr std::array<double, 14> checkpoints{0.,20.,25.,50.,75.,100.,120.,125.,150.,200.,250.,500.,1000.,1200.};
constexpr std::array<Field<double> CombatPlant::*, 10> timer_fields{
    &CombatPlant::shoot_cd, &CombatPlant::shooting, &CombatPlant::eating,
    &CombatPlant::cannon_cd, &CombatPlant::cannon_animation, &CombatPlant::buried,
    &CombatPlant::grave_eating, &CombatPlant::magnet, &CombatPlant::burst, &CombatPlant::lamp
};
bool held(const HeroPlayer& player, std::string_view secret) {
    return std::find(player.secrets.begin(), player.secrets.end(), secret) != player.secrets.end();
}
ExpansionClockValues& ensure_values(Field<ExpansionClockValues>& slot) {
    if (!slot.present()) slot.set({});
    return slot.get();
}
double previous_value(const Field<ExpansionClockValues>& slot, size_t index) {
    return slot.present() ? slot.get().at(index).or_missing(0.) : 0.;
}
}

Field<double>& ExpansionGarden::timer(CombatPlant& plant, ExpansionTimer key) {
    return plant.*timer_fields.at(size_t(key));
}
void ExpansionGarden::configure_locked_secrets() {
    cactus_spikes = false;
    pressure_holders.clear();
    pressure_tick.reset();
    pressure_positions.clear();
    for (const auto seat : seats_for(world_.mode)) {
        const auto& player = world_.heroes.players.at(seat_index(seat)).value();
        if (team_of(seat) == Seat::plant) cactus_spikes = cactus_spikes || held(player, "secret:尖刺");
        else if (held(player, "zsecret:威压")) pressure_holders.push_back(seat);
    }
}
double ExpansionGarden::pressure(const PlantRef& plant) {
    if (pressure_holders.empty() || world_.heroes.owner(source_ref(plant)) != Seat::plant) return 1.;
    const auto now = world_.heroes.tick;
    if (pressure_tick != now) {
        pressure_tick = now;
        pressure_positions.clear();
        for (const auto seat : pressure_holders) {
            const auto& avatar = world_.heroes.heroes.at(seat_index(seat)).value();
            if (avatar.frame.hp.get() <= 0.) continue;
            const auto& position = *avatar.frame.position.get();
            pressure_positions.push_back({position.x, position.y});
        }
    }
    const double tile = world_.runtime.tile;
    const Point point{(plant->cell.x + .5) * tile, (plant->cell.y + .5) * tile};
    for (const auto& position : pressure_positions) {
        if (std::hypot(wrap_delta(position.x, point.x, world_.world_width.get()),
                       point.y - (position.y - tile)) <= 6. * tile) return 1. / 1.3;
    }
    return 1.;
}
double ExpansionGarden::aura(const PlantRef& plant) {
    const auto found = aura_cells.find({plant->cell.y, plant->cell.x});
    const int stacks = found == aura_cells.end() ? 0 : found->second;
    double factor = std::pow(.8, std::min(4, stacks)) * Scarecrows::slow_factor(plant, slow_cells) * pressure(plant);
    if (plant->kind == "仙人掌" && cactus_spikes) factor *= .5;
    return factor;
}
void ExpansionGarden::absorb_clock_cap() {
    for (const auto& plant : *world_.plant_roster) {
        if (!plant->magnet.present() || plant->magnet.is_null()) continue;
        if (plant->kind == "磁力菇" && plant->magnet.get() == 13000.) plant->magnet.set(9000.);
        if (plant->kind == "吸金磁" && plant->magnet.get() == 9000.) plant->magnet.set(6000.);
    }
}
void ExpansionGarden::before_plants(std::span<const std::string> producers) {
    absorb_clock_cap();
    timer_before.clear();
    aura_centers.clear();
    for (const auto& plant : *world_.plant_roster) {
        if (plant->kind == "金盏花" && plant->hp.or_missing(0.) > 0. &&
            !plant->dead.present() && !plant->sleep.present()) aura_centers.push_back(plant->cell);
    }
    aura_cells.clear();
    slow_cells = scarecrows_.aura_cells();
    const auto columns = int64_t(world_.world_width.get() / world_.runtime.tile);
    for (const auto& center : aura_centers) {
        if (columns == 0) throw std::domain_error("marigold map has no columns");
        for (int dy = -3; dy <= 3; ++dy) for (int dx = -3; dx <= 3; ++dx) {
            auto& count = aura_cells[{center.y + dy, int64_t(py::mod(double(center.x + dx), double(columns)))}];
            count = std::min(4, count + 1);
        }
    }
    for (const auto& plant : *world_.plant_roster) {
        if (plant->kind == "金盏花") { plant->money_cd.set(1000000.); plant->burst.set(0.); }
        if (plant->hp.or_missing(0.) <= 0. || plant->sleep.present()) continue;
        const double factor = aura(plant);
        plant->aura_factor.set(factor);
        ExpansionClockValues seen;
        for (size_t index = 0; index < timer_fields.size(); ++index) {
            if (index == size_t(ExpansionTimer::burst) &&
                std::find(producers.begin(), producers.end(), plant->kind) != producers.end()) continue;
            auto& field = timer(*plant, ExpansionTimer(index));
            if (!field.present() || field.is_null()) continue;
            const double value = field.get();
            const double delta = previous_value(plant->expansion_clock.delta, index);
            if (factor < 1. && 0. < std::abs(delta) && std::abs(delta) <= 2. && value > 0.) {
                if (factor == 0.) throw std::domain_error("zero expansion interval");
                auto& credits = ensure_values(plant->expansion_clock.credit);
                const double credit = credits[index].or_missing(0.) + std::abs(delta) * (1. / factor - 1.);
                double limit;
                if (delta < 0.) limit = std::max(0., std::trunc(value) - 1.);
                else {
                    const auto next = std::find_if(checkpoints.begin(), checkpoints.end(), [value](double checkpoint) { return checkpoint > value; });
                    const double terminal = next == checkpoints.end() ? std::trunc(value) + 100000. : *next;
                    limit = std::max(0., terminal - std::trunc(value) - 1.);
                }
                const double extra = std::min(std::trunc(credit), limit);
                field.set(value + extra * (delta < 0. ? -1. : 1.));
                credits[index].set(credit - extra);
            } else if (factor > 1. && 0. < std::abs(delta) && std::abs(delta) <= 2. && value > 0. &&
                       std::find(checkpoints.begin(), checkpoints.end(), std::trunc(value)) == checkpoints.end()) {
                auto& debts = ensure_values(plant->expansion_clock.debt);
                const double debt = debts[index].or_missing(0.) + std::abs(delta) * (1. - 1. / factor);
                double back = debt >= 1. ? 1. : 0.;
                if (back && delta > 0. && value - back < 1.) back = 0.;
                if (back) field.set(value + (delta < 0. ? back : -back));
                debts[index].set(debt - back);
            }
            seen[index] = field;
        }
        timer_before[plant->identity.value] = std::move(seen);
    }
}
void ExpansionGarden::after_plants() {
    for (const auto& plant : *world_.plant_roster) {
        const auto found = timer_before.find(plant->identity.value);
        if (found == timer_before.end()) continue;
        const auto& seen = found->second;
        if (std::none_of(seen.begin(), seen.end(), [](const auto& value) { return value.present(); })) continue;
        auto& slot = plant->expansion_clock.delta;
        if (!slot.present() || slot.is_null()) slot.set({});
        for (size_t index = 0; index < seen.size(); ++index) {
            if (seen[index].present()) slot.get()[index].set(timer(*plant, ExpansionTimer(index)).or_missing(seen[index].get()) - seen[index].get());
        }
    }
}
} // namespace pvz::typed72
