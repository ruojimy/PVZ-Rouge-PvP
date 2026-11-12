#pragma once
#include "core/pyobj.h"
namespace pvz {
// Actual compiled capture cells and a native body blueprint, not CodeType or wordcode.
using NativeClosureBody=std::function<V(const V&,const Args&)>;
V native_cell(const Args&);
V native_cell_value(const V&);
V make_native_closure(const V&,const V&,const V&,const V&,NativeClosureBody);
V clone_native_closure(const Args&); // ABSENT for a non-native blueprint
}
