// Small-object allocator replacing global operator new/delete.
// The translated PvP code allocates millions of short-lived small blocks per battle second
// (list/tuple storage, closures, coroutine frames); the system heap was ~20% of run time.
// Per-thread free lists by 16-byte size class. Cross-thread frees return to a
// shared pool: otherwise a snapshot producer keeps allocating slabs while the
// consumer accumulates every retired block in its own thread-local cache.
#include <cstdlib>
#include <cstddef>
#include <cstdint>
#include <new>
#include <atomic>
#include <cstring>
#include "core/alloc.h"

namespace pvz {
namespace {
constexpr size_t kHeader = 16, kStep = 16, kMaxSmall = 512, kClasses = kMaxSmall / kStep;
constexpr uint32_t kBigTag = 0xFFFFFFFFu;
constexpr uint32_t kClassBits=6,kClassMask=(1u<<kClassBits)-1,kMaxOwner=UINT32_MAX>>kClassBits;
constexpr size_t kCentralBatch=64;
struct FreeNode { FreeNode* next; };
struct ThreadCache { FreeNode* lists[kClasses+1]={};uint32_t owner=0;bool initialized=false,closed=false; };
// Trivially destructible storage remains usable by later TLS/global destructors.
thread_local ThreadCache t_cache;
struct CentralBucket {std::atomic_flag lock=ATOMIC_FLAG_INIT;FreeNode* head=nullptr;};
// No dynamic construction, allocation or destructor: safe during new/delete
// bootstrap and after normal static object destruction has begun.
constinit CentralBucket central[kClasses+1];
constinit std::atomic<uint32_t> next_owner{1};
constinit std::atomic<uint64_t> slab_bytes{0},slab_count{0},cross_thread_frees{0};
constinit std::atomic<uint64_t> central_blocks{0},central_reused_blocks{0},thread_cache_flushes{0};
constinit std::atomic<uint64_t> allocation_failures{0},last_failure_bytes{0};
bool legacy_allocator() {
    static const bool legacy=[] {const char* p=std::getenv("PVP742_ALLOCATOR");return p&&std::strcmp(p,"0")==0;}();
    return legacy;
}
struct PoolLock {
    CentralBucket& bucket;
    explicit PoolLock(CentralBucket& b):bucket(b){while(bucket.lock.test_and_set(std::memory_order_acquire)) {}}
    ~PoolLock(){bucket.lock.clear(std::memory_order_release);}
};
uint32_t reserve_owner() {
    auto token=next_owner.load(std::memory_order_relaxed);
    while(token<=kMaxOwner)if(next_owner.compare_exchange_weak(token,token+1,std::memory_order_relaxed))return token;
    // Zero is never a local owner. Saturation safely disables the fast return
    // for future threads instead of reusing a live or retired thread's token.
    return 0;
}
void central_return(size_t cls,FreeNode* node) {
    auto& bucket=central[cls];PoolLock lock(bucket);node->next=bucket.head;bucket.head=node;
    central_blocks.fetch_add(1,std::memory_order_relaxed);
}
void flush_thread_cache() {
    t_cache.closed=true;
    if(legacy_allocator())return; // Exact diagnostic control for the former path.
    bool flushed=false;
    for(size_t cls=1;cls<=kClasses;++cls) {
        auto* first=t_cache.lists[cls];if(!first)continue;flushed=true;
        size_t count=1;auto* tail=first;while(tail->next){tail=tail->next;++count;}
        auto& bucket=central[cls];PoolLock lock(bucket);tail->next=bucket.head;bucket.head=first;t_cache.lists[cls]=nullptr;
        central_blocks.fetch_add(count,std::memory_order_relaxed);
    }
    if(flushed)thread_cache_flushes.fetch_add(1,std::memory_order_relaxed);
}
struct ThreadCacheReaper {~ThreadCacheReaper(){flush_thread_cache();}bool armed=true;};
void initialize_thread_cache() {
    if(t_cache.initialized)return;
    t_cache.initialized=true;t_cache.owner=reserve_owner();
    // ODR-use registers the reaper after the trivial cache is ready. Recursive
    // allocations made by runtime TLS registration can use the prepared cache.
    static thread_local ThreadCacheReaper reaper;
    (void)reaper.armed;
}
void* central_take(size_t cls,bool cache_rest) {
    auto& bucket=central[cls];PoolLock lock(bucket);auto* first=bucket.head;if(!first)return nullptr;
    size_t count=1;auto* tail=first;
    while(cache_rest&&count<kCentralBatch&&tail->next){tail=tail->next;++count;}
    bucket.head=tail->next;tail->next=nullptr;
    if(cache_rest){t_cache.lists[cls]=first->next;first->next=nullptr;}
    central_blocks.fetch_sub(count,std::memory_order_relaxed);central_reused_blocks.fetch_add(count,std::memory_order_relaxed);
    return first;
}
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
    if(!p){last_failure_bytes.store(bytes,std::memory_order_relaxed);allocation_failures.fetch_add(1,std::memory_order_relaxed);return p;}
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

inline void* refill(size_t cls,bool cache_rest) {
    const size_t block = kHeader + cls * kStep;
    size_t count = (64 * 1024) / block;
    if (count < 8) count = 8;
    char* slab = static_cast<char*>(std::malloc(block * count));
    if (!slab) return nullptr;
    slab_bytes.fetch_add(block*count,std::memory_order_relaxed);slab_count.fetch_add(1,std::memory_order_relaxed);
    FreeNode* head=nullptr;
    for (size_t i = 1; i < count; ++i) {
        char* b = slab + i * block;
        *reinterpret_cast<uint32_t*>(b) = uint32_t(cls);
        auto* n = reinterpret_cast<FreeNode*>(b + kHeader);
        n->next = head; head = n;
    }
    *reinterpret_cast<uint32_t*>(slab) = uint32_t(cls);
    if(cache_rest)t_cache.lists[cls]=head;
    else if(head) {
        // Allocations after the TLS reaper cannot leave a private orphan cache.
        auto* tail=head;while(tail->next)tail=tail->next;
        auto& bucket=central[cls];PoolLock lock(bucket);tail->next=bucket.head;bucket.head=head;
        central_blocks.fetch_add(count-1,std::memory_order_relaxed);
    }
    return slab + kHeader;
}
}  // namespace

// optional allocation statistics hook (run_battle PVZ_ALLOCSTAT)
void (*g_alloc_hook)(size_t) = nullptr;

void* small_alloc(size_t sz) {
    if (g_alloc_hook) g_alloc_hook(sz);
    if (sz == 0) sz = 1;
    if(sz>SIZE_MAX-kHeader)return record_allocation(nullptr,sz);
    if (sz <= kMaxSmall) {
        size_t cls = (sz + kStep - 1) / kStep;
        const bool legacy=legacy_allocator();if(!legacy)initialize_thread_cache();
        FreeNode*& head = t_cache.lists[cls];
        void* result=nullptr;
        if((legacy||!t_cache.closed)&&head){auto* node=head;head=node->next;result=node;}
        else {
            if(!legacy)result=central_take(cls,!t_cache.closed);
            if(!result)result=refill(cls,legacy||!t_cache.closed);
        }
        if(result&&!legacy)*reinterpret_cast<uint32_t*>(static_cast<char*>(result)-kHeader)=uint32_t(cls)|(t_cache.owner<<kClassBits);
        return record_allocation(result,sz);
    }
    char* p = static_cast<char*>(std::malloc(sz + kHeader));
    if (!p) return record_allocation(nullptr,sz);
    *reinterpret_cast<uint32_t*>(p) = kBigTag;
    return record_allocation(p + kHeader,sz);
}
void small_free(void* p) {
    if (!p) return;
    char* h = static_cast<char*>(p) - kHeader;
    const uint32_t tag=*reinterpret_cast<uint32_t*>(h);
    uint32_t epoch=*reinterpret_cast<uint32_t*>(h+4);
    if(epoch && active_epoch.load(std::memory_order_relaxed)) {
        TraceLock lock;
        if(epoch==active_epoch.load(std::memory_order_relaxed))trace_current-=*reinterpret_cast<uint64_t*>(h+8);
    }
    if (tag == kBigTag) { std::free(h); return; }
    const bool legacy=legacy_allocator();const uint32_t cls=legacy?tag:(tag&kClassMask);
    auto* n = static_cast<FreeNode*>(p);
    if(!legacy&&(t_cache.closed||!t_cache.initialized||t_cache.owner==0||(tag>>kClassBits)!=t_cache.owner)) {
        cross_thread_frees.fetch_add(1,std::memory_order_relaxed);central_return(cls,n);return;
    }
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
SmallAllocatorStats native_small_allocator_stats(){
    return {slab_bytes.load(std::memory_order_relaxed),slab_count.load(std::memory_order_relaxed),cross_thread_frees.load(std::memory_order_relaxed),central_blocks.load(std::memory_order_relaxed),central_reused_blocks.load(std::memory_order_relaxed),thread_cache_flushes.load(std::memory_order_relaxed),legacy_allocator(),allocation_failures.load(std::memory_order_relaxed),last_failure_bytes.load(std::memory_order_relaxed)};
}
bool native_small_allocator_thread_cache_closed(){return t_cache.closed;}
int alloc_anchor() { return 0; }
}  // namespace pvz

void* operator new(size_t sz) { if (void* p = pvz::small_alloc(sz)) return p; throw std::bad_alloc(); }
void* operator new[](size_t sz) { if (void* p = pvz::small_alloc(sz)) return p; throw std::bad_alloc(); }
void* operator new(size_t sz, const std::nothrow_t&) noexcept { try{return pvz::small_alloc(sz);}catch(...){return nullptr;} }
void* operator new[](size_t sz, const std::nothrow_t&) noexcept { try{return pvz::small_alloc(sz);}catch(...){return nullptr;} }
void operator delete(void* p) noexcept { pvz::small_free(p); }
void operator delete[](void* p) noexcept { pvz::small_free(p); }
void operator delete(void* p, size_t) noexcept { pvz::small_free(p); }
void operator delete[](void* p, size_t) noexcept { pvz::small_free(p); }
void operator delete(void* p, const std::nothrow_t&) noexcept { pvz::small_free(p); }
void operator delete[](void* p, const std::nothrow_t&) noexcept { pvz::small_free(p); }
