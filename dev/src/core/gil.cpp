#include "core/gil.h"
#include <chrono>
#include <mutex>
#include <thread>

namespace pvz::gil {
std::atomic<int> g_waiters{0};
namespace {
std::mutex g_lock;
std::atomic<bool> g_active{false};
std::atomic<long long> g_wait_since{0};   // steady-clock microseconds when the oldest current waiter started
thread_local int t_held = 0;              // this thread owns the lock
long long now_us() {
    return std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
void lock_waiting() {
    if (g_waiters.fetch_add(1) == 0) g_wait_since = now_us();
    g_lock.lock();
    if (g_waiters.fetch_sub(1) > 1) g_wait_since = now_us();   // the next waiter's clock starts now
    t_held = 1;
}
void hand_over() {
    t_held = 0;
    g_lock.unlock();
    // give a waiter the chance to take it (std::mutex is not fair)
    long long until = now_us() + 2000;
    int before = g_waiters.load();
    while (g_waiters.load() >= before && before > 0 && now_us() < until) std::this_thread::yield();
    lock_waiting();
}
}  // namespace

void init() {
    if (g_active.exchange(true)) return;
    g_lock.lock();
    t_held = 1;
}
bool active() { return g_active.load(std::memory_order_relaxed); }

void acquire() {
    if (!active()) return;
    lock_waiting();
}
void release() {
    if (!active() || !t_held) return;
    t_held = 0;
    g_lock.unlock();
}

void yield_if_waiting() {
    if (!active() || !t_held || g_waiters.load() == 0) return;
    hand_over();
}

void switch_slow() {
    // CPython's switch interval: a thread that waited 5 ms gets the lock at the holder's next call
    if (!t_held || now_us() - g_wait_since.load() < 5000) return;
    hand_over();
}

Release::Release() : on(active() && t_held) {
    if (on) { t_held = 0; g_lock.unlock(); }
}
Release::~Release() {
    if (on) lock_waiting();
}

}  // namespace pvz::gil
