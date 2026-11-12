// Source: extract/original/functions.py:363-446. Original damage stage only.
// PvP damage packets, hero proxy and patch wrappers are separate
// migration obligations; never route a production PvP tick to this in isolation.
#include "state.h"

namespace pvz::typed72 {
namespace {
std::string sound_variant(CombatRuntime& w, const char* base) {
    return std::string(base) + std::to_string(w.rng.randint(1, 2));
}
void drop(CombatRuntime& w, Zombie& z, double facing) {
    // The source c(position) is a deep copy, including velocity.
    auto& e = w.construct_entity(z.armor, z.facing, z.motion.get());
    z.armor.clear();
    e.gravity.set(0);
    e.motion.get().x -= w.tile * .5;
    e.motion.get().y -= w.tile * 1.5;
    e.motion.get().vx = facing * w.plk * 400;
    e.motion.get().vy = -w.rng.randint(350, 450) * w.plk;
    e.expires.set(1);
}
}

void damage_zombie(CombatStages& w, Handle<Zombie> id, double facing, double amount) {
    damage_zombie(w,w.zombies.at(id),facing,amount);
}
void damage_zombie(CombatRuntime& w, Zombie& z, double facing, double amount) {
    ++w.damage_calls;
    if (w.branch(0, z.ash.present())) return;
    z.hurt = 1;
    if (w.branch(1, z.armor_hp > 0 && amount < z.armor_hp + z.hp)) {
        if (w.branch(2, z.armor == "路障" || z.armor == "橄榄球头盔" || z.armor == "黑橄榄球头盔"))
            w.sound(sound_variant(w, "路障"), z.motion.get());
        if (w.branch(3, z.armor == "铁桶")) w.sound(sound_variant(w, "铁桶"), z.motion.get());
        z.armor_hp -= amount;
        if (w.branch(4, z.armor_hp <= 0)) {
            z.armor_hp = 0;
            drop(w, z, facing);
        }
    } else if (w.branch(5, z.hp > 0)) {
        z.hp -= amount;
        if (w.branch(6, z.kind == "投篮车僵尸")) w.sound(sound_variant(w, "路障"), z.motion.get());
        if (w.branch(7, z.kind == "雪橇车僵尸")) w.sound(sound_variant(w, "铁桶"), z.motion.get());
        if (w.branch(8, z.hp <= 0)) {
            z.hp = 0;
            if (w.branch(9, z.kind == "巨人僵尸")) w.sound("巨人之死", z.motion.get());
            else {
                if (w.branch(10, z.armor_hp > 0)) { z.armor_hp = 0; drop(w, z, facing); }
                w.sound("掉头", z.motion.get());
                if (w.branch(11, z.hand == "玩偶匣")) {
                    w.sound(sound_variant(w, "小丑"), z.motion.get());
                    z.motion.get().vx = 350 * w.plk * z.facing;
                }
                auto& e = w.construct_entity(z.kind + "-首", z.facing, z.motion.get());
                z.motion.get().vx -= z.facing * w.plk * 100;
                e.gravity.set(0);
                e.motion.get().y -= w.tile * 1.5;
                e.motion.get().vx = facing * w.plk * 400;
                e.motion.get().vy = -w.rng.randint(350, 450) * w.plk;
                e.expires.set(1);
            }
        }
    }
}

bool surface_damage_zombie(CombatStages& w, Handle<Zombie> id, double facing, double amount) {
    auto& z=w.zombies.at(id);
    const auto result=surface_hand_damage(w,z,facing,amount);
    if(result==SurfaceDamageResult::armorless)damage_zombie(w,z,facing,amount);
    return result==SurfaceDamageResult::hand_hit;
}
SurfaceDamageResult surface_hand_damage(CombatRuntime& w,Zombie& z,double facing,double amount) {
    ++w.surface_calls;
    if (w.branch(12, !z.ash.present())) {
        if (w.branch(13, z.hand_hp > 0)) {
            z.hand_hurt = 1;
            if (w.branch(14, z.hand == "报纸")) w.sound("报纸", z.motion.get());
            if (w.branch(15, z.hand == "气球")) w.sound("气球爆炸", z.motion.get());
            if (w.branch(16, z.hand == "钢门" || z.hand == "梯子")) w.sound(sound_variant(w, "铁桶"), z.motion.get());
            z.hand_hp -= amount;
            if (w.branch(17, z.hand_hp <= 0)) {
                if (w.branch(18, z.hand == "气球")) {
                    z.hand.clear();
                    w.emit_particles("气球", {z.motion.get().x, z.motion.get().y - w.tile * 2.5}, 12);
                    z.balloon.set(1);
                } else {
                    auto& e = w.construct_entity(z.hand, z.facing, z.motion.get());
                    z.hand.clear();
                    e.gravity.set(0);
                    e.motion.get().x -= w.tile * .5;
                    e.motion.get().y -= w.tile * 1.5;
                    e.motion.get().vx = facing * w.plk * 400;
                    e.motion.get().vy = -w.rng.randint(350, 450) * w.plk;
                    e.expires.set(1);
                }
            }
            return SurfaceDamageResult::hand_hit;
        }
        return SurfaceDamageResult::armorless;
    }
    return SurfaceDamageResult::ashed;
}
} // namespace pvz::typed72
