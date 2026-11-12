#define PVZ72_NATIVE_STATUS_PROBE_EMBEDDED
#include "native_status_probe.cpp"
#include "sim/typed/bonus_scan.h"

namespace {
struct BonusProbe : NativeStatusProbe, BonusImpactServices, BonusPlantServices {
    BonusProjectiles bonus_projectiles{battle, *this, collision, rules};
    BonusPlants bonus_plants{battle, chart, squash, *this, *this};
    BonusScan bonus_scan{battle, {bonus_plants, bonus_projectiles, chain, shooting, lantern, peas, fume, squash}};
    bool observe_bonus = false, bonus_installed = false, blue_available = true;
    explicit BonusProbe(int64_t seed, double width, double splash) : NativeStatusProbe(seed, width, splash) {}
    void stored_add_entity(std::string name, double facing, Motion position) override {
        NativeStatusProbe::add_entity(std::move(name), facing, position);
    }
    void prepare_star_atlas() override {
        ;
        ;
        ;
    }
    bool prepare_blue_pea_atlas() override {
        ;
        ;
        ;
        return blue_available;
    }
    void bonus_damage(size_t index, double facing, double amount) override {
        NativeStatusProbe::ordinary_damage(index, facing, amount);
    }
    void head_damage(const EntityRef& entity, size_t index, double facing, double amount, bool surface) override {
        ;
        ;
        if (surface) NativeStatusProbe::surface_damage(index, facing, amount);
        else NativeStatusProbe::ordinary_damage(index, facing, amount);
        ;
    }
    void before_native_tick(double now) override {
        NativeStatusProbe::before_native_tick(now);
        if (bonus_installed) bonus_scan.before(now);
    }
    void after_native_tick(double now) override {
        NativeStatusProbe::after_native_tick(now);
        if (bonus_installed) bonus_scan.after(now, avatar_order());
    }
    void bonus_entity_fields(Entity& entity, const J& fields) {
        J previous = fields;
        if (fields.contains("消亡") && fields.at("消亡").is_boolean()) previous.erase("消亡");
        if (previous.contains("智能弹道") && previous["智能弹道"].is_object()) previous["智能弹道"].erase("target_id");
        for (const auto* key : {"智能增伤", "智能杨桃", "智能星命中", "植物僵尸头命中",
             "植物僵尸头命中表", "上次制导", "制导次数", "锁敌", "落点", "_pvp_content", "穿墙"}) previous.erase(key);
        pea_fields(entity, previous);
        auto& state = entity.bonus;
        read(fields, "智能增伤", state.damage_done);
        read(fields, "智能杨桃", state.star_patched);
        read(fields, "植物僵尸头命中", state.head_hit);
        read(fields, "上次制导", state.last_guide);
        read(fields, "制导次数", state.guide_count);
        read(fields, "锁敌", entity.cannon_lock);
        read(fields, "落点", entity.cannon_column);
        read(fields, "_pvp_content", entity.source.content);
        read(fields, "穿墙", entity.through_wall);
        if (fields.contains("消亡")) {
            const auto& expiry = fields.at("消亡");
            if (expiry.is_null()) entity.expires.set_null();
            else if (expiry.is_boolean()) entity.expires.set(expiry.get<bool>());
            else entity.expires.set(expiry.get<double>());
        }
        if (fields.contains("智能弹道") && fields.at("智能弹道").is_object() && fields.at("智能弹道").contains("target_id")) {
            const auto& id = fields.at("智能弹道").at("target_id");
            if (id.is_null()) entity.service.smart.get().target_id.set_null();
            else entity.service.smart.get().target_id.set(ChiliProbe::record(id));
        }
        for (auto [key, field] : {std::pair{"智能星命中", &state.star_hits}, std::pair{"植物僵尸头命中表", &state.head_hits}}) {
            if (!fields.contains(key)) continue;
            if (fields.at(key).is_null()) { field->set_null(); continue; }
            std::vector<RecordId> ids;
            for (const auto& value : fields.at(key)) ids.push_back(ChiliProbe::record(value));
            field->set(std::move(ids));
        }
    }
    void bonus_plant_fields(const PlantRef& plant, const J& fields) {
        read(fields, "射", plant->shooting);
        read(fields, "射cd", plant->shoot_cd);
        read(fields, "根动画", plant->root_animation);
        read(fields, "发射cd", plant->cannon_cd);
        read(fields, "发射动画", plant->cannon_animation);
        read(fields, "植物血", plant->hp);
        read_death(fields, "死", plant->dead);
        read_death(fields, "铲死", plant->shovel_dead);
        read_death(fields, "黑白", plant->monochrome);
        read(fields, "智能石块占位", plant->bonus.stone_placeholder);
        read(fields, "智能装填", plant->bonus.cannon_reloading);
        if (fields.contains("三向角")) {
            if (fields.at("三向角").is_null()) plant->bonus.tripea_angles.set_null();
            else {
                std::vector<Field<double>> values;
                for (const auto& value : fields.at("三向角")) {
                    Field<double> angle;
                    if (value.is_null()) angle.set_null(); else angle.set(value.get<double>());
                    values.push_back(angle);
                }
                plant->bonus.tripea_angles.set(std::move(values));
            }
        }
    }
    bool extra_operation(const J& op, J& result) override {
        const auto name = op.at("op").get<std::string>();
        if (name == "bonus_setup") {
            observe_bonus = true;
            bonus_installed = op.value("installed", false);
            blue_available = op.value("blue", true);
        } else if (name == "bonus_clock") bonus_scan.before(op.at("now"));
        else if (name == "bonus_entity") {
            add_entity(op.at("name"), op.value("facing", 1.), motion(op.at("position")));
            bonus_entity_fields(*births.back(), op.value("fields", J::object()));
        } else if (name == "bonus_entity_fields") bonus_entity_fields(*births.at(op.at("entity").get<size_t>()), op.at("fields"));
        else if (name == "bonus_plant_fields") bonus_plant_fields(plant_ref(op.at("plant").get<size_t>()), op.at("fields"));
        else if (name == "bonus_call") {
            const auto action = op.at("action").get<std::string>();
            const auto entity = op.contains("entity") ? births.at(op.at("entity").get<size_t>()) : EntityRef{};
            if (action == "patch") bonus_projectiles.patch(entity);
            else if (action == "guide") bonus_projectiles.guide();
            else if (action == "velocity") bonus_projectiles.velocity_damage(visual.entities.list(), battle.targets);
            else if (action == "heads") bonus_projectiles.head_hits();
            else if (action == "cannons") { bonus_projectiles.fix_cannons(); bonus_projectiles.patch_cannons(); }
            else if (action == "reload") bonus_projectiles.mark_reloading(entity);
            else if (action == "record_star") bonus_plants.record_star(entity, op.value("facing", entity->facing));
            else if (action == "finalize") bonus_plants.finalize_stars();
            else if (action == "stars") bonus_plants.starfruit();
            else if (action == "star_damage") bonus_plants.star_damage();
            else if (action == "tripea") bonus_plants.tripea();
            else if (action == "grave") bonus_plants.grave_damage();
            else if (action == "stones") bonus_plants.cleanup_stones();
            else if (action == "scan") bonus_scan.scan();
            else if (action == "after") bonus_scan.after(op.at("now"), avatar_order());
            else throw std::invalid_argument("unknown bonus operation");
        } else return NativeStatusProbe::extra_operation(op, result);
        return true;
    }
    void entity_bonus_json(J& row, const EntityRef& entity) {
        const auto& state = entity->bonus;
        write(row, "智能增伤", state.damage_done);
        write(row, "智能杨桃", state.star_patched);
        write(row, "植物僵尸头命中", state.head_hit);
        write(row, "上次制导", state.last_guide);
        write(row, "制导次数", state.guide_count);
        write(row, "_pvp_multi_red", entity->mortar.multi_red);
        if (entity->expires.boolean_encoding()) row["消亡"] = entity->expires.get() != 0.;
        for (auto [key, field] : {std::pair{"智能星命中", &state.star_hits}, std::pair{"植物僵尸头命中表", &state.head_hits}}) {
            if (!field->present()) continue;
            J values = nullptr;
            if (!field->is_null()) {
                values = J::array();
                for (const auto id : field->get()) values.push_back(key_json(ChiliKey::object(id)));
            }
            row[key] = values;
        }
        if (entity->service.smart.present() && !entity->service.smart.is_null()) {
            const auto& id = entity->service.smart.get().target_id;
            if (id.present()) row["智能弹道"]["target_id"] = id.is_null() ? J(nullptr) : key_json(ChiliKey::object(id.get()));
        }
    }
    void plant_bonus_json(J& row, const PlantRef& plant) {
        write(row, "智能石块占位", plant->bonus.stone_placeholder);
        write(row, "智能装填", plant->bonus.cannon_reloading);
        const auto& angles = plant->bonus.tripea_angles;
        if (angles.present()) {
            J values = nullptr;
            if (!angles.is_null()) { values = J::array(); for (const auto& angle : angles.get()) values.push_back(angle.is_null() ? J(nullptr) : J(angle.get())); }
            row["三向角"] = values;
        }
        const auto& targets = plant->bonus.tripea_targets;
        if (targets.present()) {
            J values = nullptr;
            if (!targets.is_null()) {
                values = J::array();
                for (const auto& id : targets.get()) values.push_back(id.is_null() ? J(nullptr) : key_json(ChiliKey::object(id.get())));
            }
            row["三向目标"] = values;
        }
    }
    void extra_snapshot(J& row) override {
        NativeStatusProbe::extra_snapshot(row);
        if (!observe_bonus) return;
        const auto entities = visual.entities.list();
        for (size_t index = 0; index < entities->size(); ++index) entity_bonus_json(row["entities"][index], entities->at(index));
        for (size_t index = 0; index < births.size(); ++index) entity_bonus_json(row["effect_births"][index], births[index]);
        for (size_t index = 0; index < battle.plant_roster->size(); ++index) plant_bonus_json(row["plants"][index], battle.plant_roster->at(index));
        for (size_t index = 0; index < all_plants.size(); ++index) plant_bonus_json(row["all_plants"][index], all_plants[index]);
        J pending = J::array(), bites = J::array();
        for (const auto& group : bonus_plants.pending_stars) {
            J stars = J::array();
            for (const auto& entity : group->stars) stars.push_back(entity_index(entity));
            pending.push_back({group->created, group->origin.x, group->origin.y, group->speed, group->direction, stars, group->done});
        }
        for (const auto& [id, hp] : bonus_plants.grave_bites) bites.push_back({key_json(ChiliKey::object(id)), hp});
        row["bonus"] = {{"time", bonus_scan.now}, {"scan", bonus_scan.last_scan}, {"maintenance", bonus_scan.last_maintenance},
            {"tick_calls", bonus_scan.tick_calls}, {"pending", pending}, {"bites", bites},
            {"counts", {bonus_projectiles.patches, bonus_projectiles.seen_throwers, bonus_projectiles.guide_logs,
                bonus_projectiles.bonus_hits, bonus_projectiles.cannon_patches, bonus_plants.star_patches,
                bonus_plants.star_shots, bonus_plants.tripea_shots, bonus_plants.grave_bite_hits}}};
    }
};

J run_bonus(const J& input) {
    J base = input;
    const auto cfg = base.at("world_rules");
    base.erase("world_rules");
    BonusProbe probe(input.value("seed", int64_t(1)), cfg.at("width"), cfg.value("splash", 20. / 3.));
    configure_shooting(probe, base);
    probe.battle.world_width.set(cfg.at("width"));
    probe.battle.dense_planting = cfg.at("dense");
    probe.battle.protection.deathmatch = cfg.at("deathmatch");
    if (cfg.at("rage").get<bool>()) {
        probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));
        probe.battle.protection.secrets.enabled = true;
    }
    probe.rules.damaging = cfg.at("damaging").get<std::vector<std::string>>();
    probe.rules.thrown = cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height = cfg.at("heights").get<decltype(probe.rules.homing_height)>();
    probe.collision.unit_scale = cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));
    return probe.states;
}
}
#ifndef PVZ72_BONUS_PROBE_EMBEDDED
int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::invalid_argument("usage: bonus72_probe inputs output");
        std::ifstream input(argv[1], std::ios::binary);
        std::ofstream output(argv[2], std::ios::binary);
        if (!input || !output) throw std::runtime_error("bonus fixture streams");
        std::string line;
        while (std::getline(input, line)) if (!line.empty()) output << run_bonus(J::parse(line)).dump() << '\n';
        return output ? 0 : 2;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 2; }
}
#endif
