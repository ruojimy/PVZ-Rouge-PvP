#pragma once
#include "sim/pyrt.h"
namespace pvz {
void mark_compiled_original_namespace(const V&);
bool is_compiled_original_namespace(const V&);
V bind_compiled_original_function(const V&,const V&);
V invoke_compiled_original_namespace(const V&,const std::function<V(Match&)>&);
void flush_compiled_original_namespace(const V&);
void flush_active_compiled_original_namespace(const V&);
}
