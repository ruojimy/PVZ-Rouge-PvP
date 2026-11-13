#pragma once
#include <cstdlib>
namespace pvz::typed72 {
inline bool spatial741_enabled(){static const bool enabled=[]{const char* v=std::getenv("PVP741_SPATIAL");return !v||*v!='0';}();return enabled;}
}
