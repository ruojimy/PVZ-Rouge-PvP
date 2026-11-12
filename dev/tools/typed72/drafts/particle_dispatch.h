#pragma once
#include "sim/typed/geometry.h"
#include <optional>
#include <string>
namespace pvz::typed72 {
struct CombatRuntime;
class NativeParticleDispatch {
public:
    virtual ~NativeParticleDispatch()=default;
    virtual void emit(CombatRuntime&,const std::string&,Point,int,std::optional<int>)=0;
};
} // namespace pvz::typed72
