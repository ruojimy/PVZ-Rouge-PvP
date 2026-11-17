#include "pg/motion_sensor.h"
#include <algorithm>
#include <cmath>
namespace pvz::pg {
double MotionTilt::sample(const std::array<double,3>& a,const std::array<double,3>& omega,double dt,SDL_DisplayOrientation direction,bool calibrate){
 const double length=std::hypot(a[0],a[1],a[2]);
 const bool valid=std::isfinite(length)&&length>4.9&&length<14.8;
 // Opening the sensor while tapping a button must not turn that arbitrary
 // tilted pose into the neutral point. Flat is neutral unless explicitly calibrated.
 if(!ready){if(!valid)return 0.;gravity=a;ready=true;neutral=0.;}
 if(direction!=orientation){orientation=direction;neutral=0.;}
 dt=std::clamp(std::isfinite(dt)?dt:0.,0.,.1);
 const auto g=gravity;
 // A world-fixed vector expressed in rotating device axes: dg/dt = g cross omega.
 gravity[0]+=dt*(g[1]*omega[2]-g[2]*omega[1]);
 gravity[1]+=dt*(g[2]*omega[0]-g[0]*omega[2]);
 gravity[2]+=dt*(g[0]*omega[1]-g[1]*omega[0]);
 const double blend=valid?(calibrate?1.:1.-std::exp(-2.*dt)):0.;
 for(int i=0;i<3;++i)gravity[i]=gravity[i]*(1.-blend)+a[i]*blend;
 const double magnitude=std::hypot(gravity[0],gravity[1],gravity[2]);
 double lateral=gravity[0];
 if(direction==SDL_ORIENTATION_LANDSCAPE)lateral=-gravity[1];
 else if(direction==SDL_ORIENTATION_LANDSCAPE_FLIPPED)lateral=gravity[1];
 else if(direction==SDL_ORIENTATION_PORTRAIT_FLIPPED)lateral=-gravity[0];
 const double angle=-std::asin(std::clamp(lateral/std::max(.001,magnitude),-1.,1.))*180./3.14159265358979323846;
 if(calibrate)neutral=angle;
 return std::clamp(angle-neutral,-90.,90.);
}
namespace {
struct Device {
 SDL_Sensor* accel=nullptr;SDL_Sensor* gyro=nullptr;bool attempted=false,initialized=false;Uint64 last=0;MotionTilt tilt;
 void close(){if(SDL_WasInit(SDL_INIT_SENSOR)){if(accel)SDL_SensorClose(accel);if(gyro)SDL_SensorClose(gyro);if(initialized)SDL_QuitSubSystem(SDL_INIT_SENSOR);}accel=gyro=nullptr;attempted=initialized=false;last=0;tilt.reset();}
 ~Device(){close();}
 void open(){if(attempted)return;attempted=true;if(SDL_InitSubSystem(SDL_INIT_SENSOR)<0)return;initialized=true;
  for(int i=0;i<SDL_NumSensors();++i){auto type=SDL_SensorGetDeviceType(i);if(type==SDL_SENSOR_ACCEL&&!accel)accel=SDL_SensorOpen(i);else if(type==SDL_SENSOR_GYRO&&!gyro)gyro=SDL_SensorOpen(i);}
 }
};
Device& device(){static Device value;return value;}
}
void close_motion_sensor(){device().close();}
V motion_sensor(const Args& args){
 const bool enabled=!args.pos.empty()&&args.pos[0].truthy();auto& d=device();
 if(!enabled){d.close();return V::none();}d.open();if(!d.accel||!d.gyro)return V::none();
 SDL_SensorUpdate();float a[3]{},w[3]{};
 if(SDL_SensorGetData(d.accel,a,3)<0||SDL_SensorGetData(d.gyro,w,3)<0)return V::none();
 for(int i=0;i<3;++i)if(!std::isfinite(a[i])||!std::isfinite(w[i]))return V::none();
 const auto now=SDL_GetPerformanceCounter();double dt=d.last?double(now-d.last)/double(SDL_GetPerformanceFrequency()):0.;d.last=now;
 const bool calibrate=args.pos.size()>1&&args.pos[1].truthy();
 return V(d.tilt.sample({a[0],a[1],a[2]},{w[0],w[1],w[2]},dt,SDL_GetDisplayOrientation(0),calibrate));
}
}
