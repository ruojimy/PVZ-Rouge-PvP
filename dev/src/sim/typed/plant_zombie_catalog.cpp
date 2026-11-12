// Generated constants after NativeCombatPatch's current PvP overrides.
#include "sim/typed/plant_zombie_catalog.h"
#include <array>
namespace pvz::typed72 {
std::span<const PlantZombieConfig> native_plant_zombie_catalog() {
    static const auto entries=[] {
        std::array<PlantZombieConfig,13> values;
        {auto& c=values[0];c.kind="豌豆僵尸";c.head="豌豆射手";
            c.hp.set(0x1.9000000000000p+6);
            c.shoot.set(true);
            c.burst.set(0x1.0000000000000p+0);
            c.cooldown.set(0x1.9000000000000p+6);
            c.initial_cooldown_max.set(0x1.9000000000000p+4);
            c.fire_anim.set(0x1.8000000000000p+4);
            c.head_scale.set(0x1.8f5c28f5c28f6p-1);
            c.head_x.set(0x1.999999999999ap-4);
            c.head_y.set(0x1.6666666666666p+0);
            c.duck_head_x.set(0x1.70a3d70a3d70ap-4);
            c.duck_head_y.set(0x1.3851eb851eb85p+0);
            c.armor_x.set(-0x1.8000000000000p+1);
            c.armor_y.set(-0x1.0000000000000p+1);
        }
        {auto& c=values[1];c.kind="机枪僵尸";c.head="机枪射手";
            c.hp.set(0x1.9000000000000p+6);
            c.shoot.set(true);
            c.burst.set(0x1.0000000000000p+2);
            c.cooldown.set(0x1.9000000000000p+6);
            c.initial_cooldown_max.set(0x1.9000000000000p+4);
            c.burst_gap.set(0x1.8000000000000p+2);
            c.fire_anim.set(0x1.8000000000000p+4);
            c.head_scale.set(0x1.ae147ae147ae1p-1);
            c.head_x.set(0x1.28f5c28f5c28fp-3);
            c.head_y.set(0x1.6666666666666p+0);
            c.duck_head_x.set(0x1.c28f5c28f5c29p-4);
            c.duck_head_y.set(0x1.3851eb851eb85p+0);
            c.armor_x.set(-0x1.4000000000000p+2);
            c.armor_y.set(-0x1.8000000000000p+1);
        }
        {auto& c=values[2];c.kind="坚果僵尸";c.head="坚果";
            c.hp.set(0x1.2c00000000000p+9);
            c.shoot.set(false);
            c.burst.set(0x0.0p+0);
            c.head_scale.set(0x1.ccccccccccccdp-1);
            c.head_x.set(0x1.1eb851eb851ecp-3);
            c.head_y.set(0x1.70a3d70a3d70ap+0);
            c.duck_head_x.set(0x1.eb851eb851eb8p-4);
            c.duck_head_y.set(0x1.3d70a3d70a3d7p+0);
            c.armor_x.set(0x0.0p+0);
            c.armor_y.set(-0x1.4000000000000p+2);
            c.knockback.set(0x1.6666666666666p-2);
        }
        {auto& c=values[3];c.kind="高坚果僵尸";c.head="高坚果";
            c.hp.set(0x1.f400000000000p+10);
            c.shoot.set(false);
            c.burst.set(0x0.0p+0);
            c.head_scale.set(0x1.b851eb851eb85p-1);
            c.head_x.set(0x1.1eb851eb851ecp-3);
            c.head_y.set(0x1.a3d70a3d70a3dp+0);
            c.duck_head_x.set(0x1.eb851eb851eb8p-4);
            c.duck_head_y.set(0x1.6666666666666p+0);
            c.armor_x.set(0x0.0p+0);
            c.armor_y.set(-0x1.0000000000000p+3);
            c.knockback.set(0x1.0000000000000p-2);
        }
        {auto& c=values[4];c.kind="辣椒僵尸";c.head="火爆辣椒";
            c.hp.set(0x1.9000000000000p+6);
            c.shoot.set(false);
            c.burst.set(0x0.0p+0);
            c.head_scale.set(0x1.ccccccccccccdp-1);
            c.head_x.set(0x1.0a3d70a3d70a4p-3);
            c.head_y.set(0x1.6666666666666p+0);
            c.duck_head_x.set(0x1.999999999999ap-4);
            c.duck_head_y.set(0x1.3851eb851eb85p+0);
            c.armor_x.set(-0x1.0000000000000p+0);
            c.armor_y.set(-0x1.0000000000000p+2);
        }
        {auto& c=values[5];c.kind="毁灭菇僵尸";c.head="毁灭菇";
            c.hp.set(0x1.2c00000000000p+7);
            c.shoot.set(false);
            c.burst.set(0x0.0p+0);
            c.doom.set(true);
            c.head_scale.set(0x1.ccccccccccccdp-1);
            c.head_x.set(0x1.0a3d70a3d70a4p-3);
            c.head_y.set(0x1.6666666666666p+0);
            c.duck_head_x.set(0x1.999999999999ap-4);
            c.duck_head_y.set(0x1.3851eb851eb85p+0);
            c.armor_x.set(-0x1.0000000000000p+0);
            c.armor_y.set(-0x1.0000000000000p+2);
            c.move_speed.set(0x1.e000000000000p+6);
            c.jump_speed.set(0x1.6800000000000p+8);
        }
        {auto& c=values[6];c.kind="三叶草僵尸";c.head="三叶草";
            c.hp.set(0x1.9000000000000p+7);
            c.shoot.set(false);
            c.burst.set(0x0.0p+0);
            c.blover.set(true);
            c.cooldown.set(0x1.f400000000000p+8);
            c.fire_anim.set(0x1.0e00000000000p+8);
            c.head_scale.set(0x1.b851eb851eb85p-1);
            c.head_x.set(0x1.0a3d70a3d70a4p-3);
            c.head_y.set(0x1.6666666666666p+0);
            c.duck_head_x.set(0x1.999999999999ap-4);
            c.duck_head_y.set(0x1.3851eb851eb85p+0);
            c.armor_x.set(-0x1.0000000000000p+0);
            c.armor_y.set(-0x1.0000000000000p+2);
            c.move_speed.set(0x1.e000000000000p+6);
            c.jump_speed.set(0x1.6800000000000p+8);
        }
        {auto& c=values[7];c.kind="路灯花僵尸";c.head="路灯花";
            c.hp.set(0x1.2c00000000000p+8);
            c.shoot.set(false);
            c.burst.set(0x0.0p+0);
            c.lantern.set(true);
            c.cooldown.set(0x1.2c00000000000p+8);
            c.fire_anim.set(0x1.f400000000000p+6);
            c.head_scale.set(0x1.b851eb851eb85p-1);
            c.head_x.set(0x1.0a3d70a3d70a4p-3);
            c.head_y.set(0x1.6666666666666p+0);
            c.duck_head_x.set(0x1.999999999999ap-4);
            c.duck_head_y.set(0x1.3851eb851eb85p+0);
            c.armor_x.set(-0x1.0000000000000p+0);
            c.armor_y.set(-0x1.0000000000000p+2);
        }
        {auto& c=values[8];c.kind="倭瓜僵尸";c.head="窝瓜";
            c.hp.set(0x1.2c00000000000p+7);
            c.shoot.set(false);
            c.burst.set(0x0.0p+0);
            c.squash.set(true);
            c.head_scale.set(0x1.851eb851eb852p-1);
            c.head_x.set(0x1.0a3d70a3d70a4p-3);
            c.head_y.set(0x1.6147ae147ae14p+0);
            c.duck_head_x.set(0x1.999999999999ap-4);
            c.duck_head_y.set(0x1.3333333333333p+0);
            c.armor_x.set(-0x1.0000000000000p+0);
            c.armor_y.set(-0x1.0000000000000p+2);
            c.move_speed.set(0x1.e000000000000p+6);
            c.jump_speed.set(0x1.4a00000000000p+8);
        }
        {auto& c=values[9];c.kind="墓碑吞噬者僵尸";c.head="墓碑吞噬者";
            c.hp.set(0x1.2c00000000000p+9);
            c.shoot.set(false);
            c.burst.set(0x0.0p+0);
            c.gravebuster.set(true);
            c.plant_damage.set(0x1.8000000000000p+2);
            c.head_scale.set(0x1.b851eb851eb85p-1);
            c.head_x.set(0x1.0a3d70a3d70a4p-3);
            c.head_y.set(0x1.6666666666666p+0);
            c.duck_head_x.set(0x1.999999999999ap-4);
            c.duck_head_y.set(0x1.3851eb851eb85p+0);
            c.armor_x.set(-0x1.0000000000000p+0);
            c.armor_y.set(-0x1.0000000000000p+2);
            c.knockback.set(0x1.6666666666666p-2);
            c.move_speed.set(0x1.4000000000000p+5);
        }
        {auto& c=values[10];c.kind="萝卜伞僵尸";c.head="萝卜伞";
            c.hp.set(0x1.2c00000000000p+8);
            c.shoot.set(false);
            c.burst.set(0x0.0p+0);
            c.umbrella.set(true);
            c.cooldown.set(0x1.9000000000000p+6);
            c.fire_anim.set(0x1.9000000000000p+5);
            c.head_scale.set(0x1.eb851eb851eb8p-1);
            c.head_x.set(0x1.eb851eb851eb8p-4);
            c.head_y.set(0x1.9333333333333p+0);
            c.duck_head_x.set(0x1.999999999999ap-4);
            c.duck_head_y.set(0x1.63d70a3d70a3dp+0);
            c.armor_x.set(-0x1.0000000000000p+0);
            c.armor_y.set(-0x1.c000000000000p+2);
            c.knockback.set(0x1.0000000000000p-2);
        }
        {auto& c=values[11];c.kind="吸金磁僵尸";c.head="吸金磁";
            c.hp.set(0x1.9000000000000p+7);
            c.shoot.set(false);
            c.burst.set(0x0.0p+0);
            c.gold_magnet.set(true);
            c.cooldown.set(0x1.f400000000000p+8);
            c.fire_anim.set(0x1.6800000000000p+6);
            c.head_scale.set(0x1.b851eb851eb85p-1);
            c.head_x.set(0x1.0a3d70a3d70a4p-3);
            c.head_y.set(0x1.6666666666666p+0);
            c.duck_head_x.set(0x1.999999999999ap-4);
            c.duck_head_y.set(0x1.3851eb851eb85p+0);
            c.armor_x.set(-0x1.0000000000000p+0);
            c.armor_y.set(-0x1.0000000000000p+2);
        }
        {auto& c=values[12];c.kind="大喷菇僵尸";c.head="大喷菇";
            c.hp.set(0x1.9000000000000p+7);
            c.shoot.set(false);
            c.burst.set(0x0.0p+0);
            c.fumeshroom.set(true);
            c.cooldown.set(0x1.9000000000000p+6);
            c.fire_anim.set(0x1.9000000000000p+6);
            c.visual_tick.set(0x1.0000000000000p+3);
            c.damage_tick.set(0x1.2c00000000000p+6);
            c.damage_pulses.set(0x1.8000000000000p+1);
            c.range_tiles.set(0x1.2000000000000p+3);
            c.attack_length.set(0x1.8000000000000p+2);
            c.visual_bubbles.set(0x1.2000000000000p+5);
            c.head_scale.set(0x1.b851eb851eb85p-1);
            c.head_x.set(0x1.0a3d70a3d70a4p-3);
            c.head_y.set(0x1.6666666666666p+0);
            c.duck_head_x.set(0x1.999999999999ap-4);
            c.duck_head_y.set(0x1.3851eb851eb85p+0);
            c.armor_x.set(-0x1.0000000000000p+0);
            c.armor_y.set(-0x1.0000000000000p+2);
        }
        return values;
    }();return entries;
}
const PlantZombieConfig* native_plant_zombie_config(std::string_view kind) {
    for(const auto& c:native_plant_zombie_catalog())if(c.kind==kind)return &c;return nullptr;
}
void load_native_plant_zombie_heads(CollisionCatalog& catalog) {
    for(const auto& c:native_plant_zombie_catalog())
        catalog.plant_heads[std::string(c.kind)]={c.head_x.or_missing(.08),c.head_y.or_missing(1.35),
            c.duck_head_x.or_missing(.08),c.duck_head_y.or_missing(1.35),c.head_scale.or_missing(.68),
            c.fire_anim.or_missing(catalog.default_fire_frames),c.fumeshroom.or_missing(false)};
}
} // namespace pvz::typed72
