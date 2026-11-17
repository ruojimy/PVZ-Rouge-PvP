#pragma once
#include "sim/typed/field.h"
#include <algorithm>
namespace pvz::typed72 {
// Optional, shared by all zombie bodies. Absent preserves the original combat
// contract; an explicitly configured defense uses Classic Terraria's flat DR.
inline double defended_damage(double amount,const Field<double>& defense){
    if(!defense.present()||defense.is_null()||amount<=0.)return amount;
    return std::max(1.,amount-std::max(0.,defense.get())*.5);
}
}
