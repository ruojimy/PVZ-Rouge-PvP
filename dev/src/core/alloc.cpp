// Small-object allocator replacing global operator new/delete.
// The translated PvP code allocates millions of short-lived small blocks per battle second
// (list/tuple storage, closures, coroutine frames); the system heap was ~20% of run time.
// Per-thread free lists by 16-byte size class, 16-byte header holding the class; slabs are
// never returned to the OS. A block freed on another thread joins that thread's list.
#include <cstdlib>
#include <cstddef>
#include <cstdint>
#include <new>
#include <atomic>
#include "core/alloc.h"

namespace pvz {
namespace {
constexpr size_t kHeader = 16, kStep = 16, kMaxSmall = 512, kClasses = kMaxSmall / kStep;
constexpr uint32_t kBigTag = 0xFFFFFFFFu;
struct FreeNode { FreeNode* next; };
struct ThreadCache { FreeNode* lists[kClasses + 1] = {}; };
thread_local ThreadCache t_cache;
// Requested C++ new/delete payload bytes, excluding allocator slabs and foreign malloc/SDL.
// The existing 16-byte header stores size and generation, including cross-thread frees.
std::atomic<uint32_t> active_epoch{0};
std::atomic_flag trace_guard=ATOMIC_FLAG_INIT;
uint32_t last_epoch=0;
uint64_t trace_current=0,trace_peak=0;
struct TraceLock {
    TraceLock(){while(trace_guard.test_and_set(std::memory_order_acquire)) {}}
    ~TraceLock(){trace_guard.clear(std::memory_order_release);}
};
void* record_allocation(void* p,size_t bytes) {
    if(!p)return p;
    char* header=static_cast<char*>(p)-kHeader;
    auto& epoch=*reinterpret_cast<uint32_t*>(header+4);
    auto& size=*reinterpret_cast<uint64_t*>(header+8);
    epoch=0;size=bytes;
    if(active_epoch.load(std::memory_order_relaxed)) {
        TraceLock lock;epoch=active_epoch.load(std::memory_order_relaxed);
        if(epoch){trace_current+=bytes;if(trace_current>trace_peak)trace_peak=trace_current;}
    }
    return p;
}

inline void* refill(size_t cls) {
    const size_t block = kHeader + cls * kStep;
    size_t count = (64 * 1024) / block;
    if (count < 8) count = 8;
    char* slab = static_cast<char*>(std::malloc(block * count));
    if (!slab) return nullptr;
    FreeNode*& head = t_cache.lists[cls];
    for (size_t i = 1; i < count; ++i) {
        char* b = slab + i * block;
        *reinterpret_cast<uint32_t*>(b) = uint32_t(cls);
        auto* n = reinterpret_cast<FreeNode*>(b + kHeader);
        n->next = head; head = n;
    }
    *reinterpret_cast<uint32_t*>(slab) = uint32_t(cls);
    return slab + kHeader;
}
}  // namespace

// optional allocation statistics hook (run_battle PVZ_ALLOCSTAT)
void (*g_alloc_hook)(size_t) = nullptr;

void* small_alloc(size_t sz) {
    if (g_alloc_hook) g_alloc_hook(sz);
    if (sz == 0) sz = 1;
    if (sz <= kMaxSmall) {
        size_t cls = (sz + kStep - 1) / kStep;
        FreeNode*& head = t_cache.lists[cls];
        if (FreeNode* n = head) { head = n->next; return record_allocation(n,sz); }
        return record_allocation(refill(cls),sz);
    }
    char* p = static_cast<char*>(std::malloc(sz + kHeader));
    if (!p) return nullptr;
    *reinterpret_cast<uint32_t*>(p) = kBigTag;
    return record_allocation(p + kHeader,sz);
}
void small_free(void* p) {
    if (!p) return;
    char* h = static_cast<char*>(p) - kHeader;
    uint32_t cls = *reinterpret_cast<uint32_t*>(h);
    uint32_t epoch=*reinterpret_cast<uint32_t*>(h+4);
    if(epoch && active_epoch.load(std::memory_order_relaxed)) {
        TraceLock lock;
        if(epoch==active_epoch.load(std::memory_order_relaxed))trace_current-=*reinterpret_cast<uint64_t*>(h+8);
    }
    if (cls == kBigTag) { std::free(h); return; }
    auto* n = static_cast<FreeNode*>(p);
    n->next = t_cache.lists[cls];
    t_cache.lists[cls] = n;
}
void native_alloc_trace_start() {
    TraceLock lock;if(active_epoch.load(std::memory_order_relaxed))return;
    // Epoch zero denotes an untraced allocation. Refuse exhaustion instead of aliasing old blocks.
    if(last_epoch==UINT32_MAX)throw std::bad_alloc();
    trace_current=trace_peak=0;active_epoch.store(++last_epoch,std::memory_order_relaxed);
}
void native_alloc_trace_stop() {TraceLock lock;active_epoch.store(0,std::memory_order_relaxed);trace_current=trace_peak=0;}
bool native_alloc_trace_active(){return active_epoch.load(std::memory_order_relaxed)!=0;}
void native_alloc_trace_read(uint64_t& current,uint64_t& peak){TraceLock lock;current=trace_current;peak=trace_peak;}
void native_alloc_trace_reset_peak(){TraceLock lock;trace_peak=trace_current;}
int alloc_anchor() { return 0; }
}  // namespace pvz

void* operator new(size_t sz) { if (void* p = pvz::small_alloc(sz)) return p; throw std::bad_alloc(); }
void* operator new[](size_t sz) { if (void* p = pvz::small_alloc(sz)) return p; throw std::bad_alloc(); }
void* operator new(size_t sz, const std::nothrow_t&) noexcept { return pvz::small_alloc(sz); }
void* operator new[](size_t sz, const std::nothrow_t&) noexcept { return pvz::small_alloc(sz); }
void operator delete(void* p) noexcept { pvz::small_free(p); }
void operator delete[](void* p) noexcept { pvz::small_free(p); }
void operator delete(void* p, size_t) noexcept { pvz::small_free(p); }
void operator delete[](void* p, size_t) noexcept { pvz::small_free(p); }
void operator delete(void* p, const std::nothrow_t&) noexcept { pvz::small_free(p); }
void operator delete[](void* p, const std::nothrow_t&) noexcept { pvz::small_free(p); }
