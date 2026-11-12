#pragma once
#include <cstdint>
namespace pvz {
// Actual outstanding and peak requested new/delete payload, since tracing started.
// This excludes allocator slab capacity, direct malloc, external libraries and OS RSS.
void native_alloc_trace_start();
void native_alloc_trace_stop();
bool native_alloc_trace_active();
void native_alloc_trace_read(uint64_t& current,uint64_t& peak);
void native_alloc_trace_reset_peak();
}
