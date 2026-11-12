#include "sim/typed/zombie_spawn.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
void populate_original_zombie(CombatRuntime& w,CombatZombie& unit,std::string name,Motion& pos,double facing,const ZombieSpawnInput& input) {
    auto& z=unit.body;auto& n=unit.native;
    std::string armor,hand;double armor_hp=0.,hand_hp=0.,speed=40.,hp=100.;
    n.divide.set(0.);n.respawn.set(10000.);z.size.set(2.);n.entry.set(0.);n.entry_start.set({pos.x,w.tile*25.});
    const double fxx=input.player.x>pos.x?1.:-1.;
    const auto sound=[&](const char* sound_name,double tiles){w.sound(sound_name,{input.player.x-fxx*w.tile*tiles,pos.y});};
    if(name=="小丑僵尸"){speed=60.;hand="玩偶匣";hp=150.;sound("小丑音乐",16.);}
    if(name=="撑杆跳僵尸"){z.pole_vault.set(0.);speed=100.;hand="撑杆";hp=150.;}
    if(name=="梯子僵尸"){speed=60.;hand="梯子";hp=150.;hand_hp=250.;}
    if(name=="小鬼僵尸"){speed=60.;hp=60.;}
    if(name=="飞贼僵尸") {
        auto& e=w.construct_entity("飞贼目标",facing,{pos.x+w.tile*.5,-w.tile*15.,0.,500.*w.plk});e.expires.set(0.);e.gravity.set(0.);
        n.entry.set(-500.);z.stun.set(50.);n.entry_start.get().y=-w.tile*15.;n.rope_start=n.entry_start;
        // The temporary two-coordinate 位置 is overwritten by c(weizhi)
        // before return and is not read by any intervening native operation.
        speed=10.;hp=200.;
    }
    if(name=="旗帜僵尸")speed=80.;
    if(name=="潜水僵尸")speed=60.;
    if(name=="雪橇车小队僵尸")speed=80.;
    if(name=="海豚僵尸"){sound("海豚",30.);speed=80.;hp=150.;hand="海豚";}
    if(name=="气球僵尸") {
        pos.y-=w.tile*2.;sound("气球",12.);hp=150.;hand_hp=1.;hand="气球";z.balloon.set(0.);n.midfield.set(0.);
    }
    if(name=="矿工僵尸"){pos.y=input.map_rows*w.tile+w.tile*2.;n.emerged.set(false);hp=150.;hand="矿镐";}
    if(name=="蹦蹦僵尸"){hp=150.;hand="弹跳杆";}
    n.explosion_sound.set(0.);
    if(name=="伴舞僵尸"){hp=150.;z.dancing.set(1.);}
    if(name=="雪人僵尸"){hp=10000.;speed=90.;n.entry.set(-10000.);}
    if(name=="舞王僵尸"){hp=10000.;z.dancing.set(0.);n.dance_cd.set(1000.);n.light.set(1.);}
    if(name=="路障僵尸"){name="普通僵尸";armor="路障";armor_hp=200.;}
    if(name=="投篮车僵尸") {
        n.advance.set(0.);n.basketball_cd.set(500.);n.basketball_total.set(48.);unit.protection.basketball.set(3.);
        n.shooting.set(0.);n.crash.set(0.);z.size.set(3.);n.wheel.set(0.);hp=400.;
    }
    if(name=="雪橇车僵尸") {
        n.snow_capacity.set(std::floor(input.map_cols/2.)-6.);n.crash.set(0.);z.size.set(3.);n.wheel.set(0.);hp=600.;sound("雪橇车",1.);
    }
    if(name=="铁桶僵尸"){name="普通僵尸";armor="铁桶";armor_hp=500.;}
    if(name=="巨人僵尸") {
        n.hand_animation.set({});z.size.set(3.);hp=2000.;speed=30.;hand="锤子"+std::to_string(w.rng.randint(1,3));
    }
    if(name=="红眼巨人僵尸") {
        name="巨人僵尸";n.hand_animation.set({});z.size.set(3.);n.throw_imp.set(0.);n.wake.set(-1.);n.red_eye.set(0.);
        if(input.mode==NativeSpawnMode::test){n.entry.set(500.);pos.y-=input.screen_height*2.;pos.vy=500.*w.plk;}
        hp=20000.;speed=50.;hand="锤子"+std::to_string(w.rng.randint(1,3));
    }
    if(name=="橄榄球僵尸"){armor="橄榄球头盔";armor_hp=800.;speed=80.;}
    if(name=="黑橄榄球僵尸"){armor="黑橄榄球头盔";armor_hp=14000.;hp=1000.;speed=80.;}
    if(name=="鸭子普通僵尸")name="鸭子僵尸";
    if(name=="鸭子路障僵尸"){name="鸭子僵尸";armor="路障";armor_hp=200.;}
    if(name=="鸭子铁桶僵尸"){name="鸭子僵尸";armor="铁桶";armor_hp=500.;}
    if(name=="钢门普通僵尸"){name="普通僵尸";hand="钢门";hand_hp=500.;}
    if(name=="报纸僵尸"){hand="报纸";hand_hp=100.;hp=1000.;speed=30.;}
    if(name=="铁桶钢门僵尸"){name="普通僵尸";armor="铁桶";armor_hp=500.;hand="钢门";hand_hp=500.;}
    if(input.mode==NativeSpawnMode::doomsday){hp+=hp;armor_hp+=armor_hp;}
    if(input.mode!=NativeSpawnMode::extreme&&input.mode!=NativeSpawnMode::doomsday&&input.mode!=NativeSpawnMode::endless&&input.mode!=NativeSpawnMode::test) {
        hp=std::floor(hp/2.);armor_hp=std::floor(armor_hp/2.);
        if(input.mode==NativeSpawnMode::lottery&&(std::find(input.bosses.begin(),input.bosses.end(),name)!=input.bosses.end()||n.red_eye.present())) {
            hp=std::floor(hp/2.);armor_hp=std::floor(armor_hp/2.);
        }
    }
    if(name=="巨人僵尸")n.half_hp.set(std::floor(hp/2.));
    n.breath.set(0.);z.kind=std::move(name);z.armor=std::move(armor);z.hand=std::move(hand);z.hand_hp=hand_hp;z.armor_hp=armor_hp;
    z.facing=facing;z.hp=hp;z.hurt=0.;z.hand_hurt=0.;n.jump_cd.set(0.);z.motion=pos;n.biting.set(0.);
    n.move_speed.set((speed+w.rng.randint(-5,5))*w.plk);z.in_water.set(false);n.entry_end.set({pos.x,pos.y+w.tile*.2});
}
ZombieRef spawn_original_zombie(TypedBattleState& world,std::string name,Motion& pos,double facing,const ZombieSpawnInput& input) {
    auto unit=std::make_shared<CombatZombie>();world.add_zombie(unit);
    populate_original_zombie(world.runtime,*unit,std::move(name),pos,facing,input);return unit;
}
} // namespace pvz::typed72
