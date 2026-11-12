// Fixed native fields shared by ordinary units and native hero colliders.
#pragma once
#include "sim/typed/state.h"
namespace pvz::typed72 {
#define PVZ72_ZOMBIE_NATIVE_NUMBERS(X) \
 X(divide,"坚持分兵") X(respawn,"再出场") X(entry,"出场") X(explosion_sound,"炸音") \
 X(midfield,"中场") X(dance_cd,"跳舞cd") X(light,"灯光") X(advance,"前进") \
 X(basketball_cd,"篮球cd") X(basketball_total,"篮球总量") X(shooting,"投篮") \
 X(crash,"撞车") X(wheel,"轮子") X(snow_capacity,"雪容量") X(throw_imp,"丢小鬼") \
 X(wake,"苏醒") X(red_eye,"红眼") X(half_hp,"半血") X(breath,"憋气") \
 X(jump_cd,"跳跃cd") X(biting,"啃咬") X(move_speed,"移速")
struct ZombieNativeState {
#define NUM(n,k) Field<double> n;
    PVZ72_ZOMBIE_NATIVE_NUMBERS(NUM)
#undef NUM
    Field<Point> entry_start,entry_end,rope_start;
    Field<std::array<double,6>> hand_animation;
    Field<bool> emerged;
    Field<double> split,garlic,leaving,linger,rotation;
};
} // namespace pvz::typed72
