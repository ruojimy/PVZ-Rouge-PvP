// A CPython-style global interpreter lock for the dynamic V runtime.
//
// V values (refcounts, the small-object allocator, interned symbols) are not thread-safe. The translated
// network code (network.py / relay.py) runs its transports on background threads exactly like python;
// those threads may only touch V while holding this lock. A thread releases it inside blocking calls
// (frame delay, select, sleep, lock / event / queue waits, blocking socket I/O) via gil::Release, and -
// like CPython's 5 ms switch interval - hands it over at a call boundary (poll(), in V::call / callm)
// once another thread has waited 5 ms, so a long computation cannot starve the network heartbeat.
//
// Tools that never start threads (run_battle, the oracle) never call init(): everything is a no-op.
#pragma once
#include <atomic>

namespace pvz::gil {

void init();          // the calling (main) thread takes the lock; enables the mechanism
bool active();
void acquire();       // background thread entry
void release();       // background thread exit
void yield_if_waiting();   // main loop: hand the lock over briefly when a background thread waits

extern std::atomic<int> g_waiters;
void switch_slow();
inline void poll() { if (g_waiters.load(std::memory_order_relaxed)) switch_slow(); }

struct Release {      // scope without the lock (blocking call)
    bool on;
    Release();
    ~Release();
    Release(const Release&) = delete;
    Release& operator=(const Release&) = delete;
};

}  // namespace pvz::gil
