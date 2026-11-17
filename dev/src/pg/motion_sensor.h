#pragma once
#include "pg/pg.h"
#include <array>
namespace pvz::pg {
// UI-only orientation. Its output goes through the same recorded movement input as touch/keys.
struct MotionTilt {
 std::array<double,3> gravity{0.,9.80665,0.};
 double neutral=0.; bool ready=false; SDL_DisplayOrientation orientation=SDL_ORIENTATION_UNKNOWN;
 double sample(const std::array<double,3>& acceleration,const std::array<double,3>& angular,double dt,SDL_DisplayOrientation direction,bool calibrate);
 void reset(){ready=false;neutral=0.;orientation=SDL_ORIENTATION_UNKNOWN;}
};
V motion_sensor(const Args&);
void close_motion_sensor();
}
