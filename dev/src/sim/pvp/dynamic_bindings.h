#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz::py {
// Return a replacement bound as Python would bind a class attribute, or ABSENT for the
// generated declaration. Instance attributes are checked first by getattr/callm.
V class_method_override(const V& type, Sym name, const V& self);
}
