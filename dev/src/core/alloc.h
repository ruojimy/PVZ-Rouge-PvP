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
struct SmallAllocatorStats {
    uint64_t slab_bytes=0,slab_count=0,cross_thread_frees=0,central_blocks=0;
    uint64_t central_reused_blocks=0,thread_cache_flushes=0;
    bool legacy=false;
    uint64_t allocation_failures=0,last_failure_bytes=0;
};
// Slab capacity is separate from requested live bytes. Counters are cumulative
// process diagnostics and never enter battle state or replay hashes.
SmallAllocatorStats native_small_allocator_stats();
bool native_small_allocator_thread_cache_closed();
}
