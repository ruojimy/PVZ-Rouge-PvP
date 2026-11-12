#pragma once
#include <cmath>
#include <cstdio>
#include <string>

namespace pvz {
// Snapshot and attack IDs use the shipped native port's numeric spelling.
inline std::string native_number_text(double value){
    char buf[64];
    if(value==std::floor(value) && std::fabs(value)<9.007199254740992e15)
        std::snprintf(buf,sizeof buf,"%lld",static_cast<long long>(value));
    else std::snprintf(buf,sizeof buf,"%.17g",value);
    return buf;
}
}
