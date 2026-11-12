// Headless battle runner: builds a match like tests/multiworker_fixtures.new_battle and
// steps it, printing per-native-tick state in the oracle JSONL format.
//   run_battle <scenario.json> [out.jsonl]
#include "sim/pvp/pvprt.h"
#include "sim/pvp/battle_api.h"
#include "data/datastore.h"
#include "core/fsutil.h"
#include "core/gil.h"
#include "pg/pg.h"
#include <cstdio>
#include <fstream>
#include <chrono>
#include <cstdlib>
#include <new>
#include <algorithm>
#include <vector>

using namespace pvz;

// PVZ_ALLOCSTAT=1: histogram of operator new sizes during the bench loop
static bool g_count = false;
static size_t g_hist[1025];
static size_t g_big = 0;
static int g_trace_size = -1;     // PVZ_ALLOCSTAT=<n> (n > 1): capture stacks of n-byte allocations
static std::vector<std::vector<void*>>* g_stacks = nullptr;
static size_t g_trace_ctr = 0;
extern "C" __declspec(dllimport) unsigned short __stdcall RtlCaptureStackBackTrace(unsigned long, unsigned long, void**, unsigned long*);
namespace pvz { extern void (*g_alloc_hook)(size_t); }
static void alloc_hook(size_t sz) {
    if (!g_count) return;
    if (sz <= 1024) ++g_hist[sz]; else ++g_big;
    if (int(sz) == g_trace_size && (++g_trace_ctr % 211) == 0) {
        g_count = false;
        void* fr[24]; unsigned short n = RtlCaptureStackBackTrace(1, 24, fr, nullptr);
        g_stacks->emplace_back(fr, fr + n);
        g_count = true;
    }
}

namespace pvz { void report_stacks(const std::vector<std::vector<void*>>&, int); }
namespace pvz { void install_crash_handler(); void start_sampler(); void stop_sampler_report(int); }
int main(int argc, char** argv) {
    SDL_SetMainReady();
    if (!std::getenv("SDL_VIDEODRIVER")) SDL_setenv("SDL_VIDEODRIVER", "dummy", 0);
    if (!std::getenv("SDL_AUDIODRIVER")) SDL_setenv("SDL_AUDIODRIVER", "dummy", 0);
    gil::init();
    pvz::install_crash_handler();
    data::set_data_dir("extract/data");
    pg::install_pygame();
    callm(pg::pygame_module(), Sym("init"), Args{});
    std::string scen = argc > 1 ? argv[1] : "tools/scenarios/empty.json";
    std::string out = argc > 2 ? argv[2] : "extract/oracle_cpp/out.jsonl";
    std::ifstream f(u8p(scen), std::ios::binary);
    nlohmann::json sc = nlohmann::json::parse(f);
    try {
        auto t0 = std::chrono::steady_clock::now();
        BattleHandle b = battle_from_scenario(sc);
        auto t1 = std::chrono::steady_clock::now();
        if (out == "--bench") {
            int n = sc.value("room_ticks", 30);
            bool prof = std::getenv("PVZ_PROFILE") != nullptr;
            if (prof) start_sampler();
            bool stat = std::getenv("PVZ_ALLOCSTAT") != nullptr;
            if (stat) { g_trace_size = std::atoi(std::getenv("PVZ_ALLOCSTAT")); g_stacks = new std::vector<std::vector<void*>>(); g_stacks->reserve(100000); }
            if (stat) pvz::g_alloc_hook = alloc_hook;
            g_count = stat;
            for (int i = 0; i < n; ++i) callm(b.battle, Sym("step"), Args{});
            g_count = false;
            if (stat) {
                size_t tot = g_big; for (auto c : g_hist) tot += c;
                printf("allocations %zu (big %zu)\n", tot, g_big);
                std::vector<std::pair<size_t, int>> v; for (int i = 0; i <= 1024; ++i) if (g_hist[i]) v.push_back({g_hist[i], i});
                std::sort(v.rbegin(), v.rend());
                for (size_t i = 0; i < v.size() && i < 20; ++i) printf("  size %4d: %zu\n", v[i].second, v[i].first);
                fflush(stdout);
                if (g_trace_size > 1) report_stacks(*g_stacks, 30);
            }
            auto t2 = std::chrono::steady_clock::now();
            if (prof) stop_sampler_report(45);
            printf("init %.3fs, %d room ticks %.3fs\n", std::chrono::duration<double>(t1 - t0).count(), n,
                   std::chrono::duration<double>(t2 - t1).count());
            return 0;
        }
        std::ofstream o(u8p(out), std::ios::binary);
        battle_record_jsonl(b, sc, o);
        printf("ok\n");
    } catch (PyError& e) {
        fprintf(stderr, "PyError %s\n", e.what());
        return 2;
    } catch (std::exception& e) {
        fprintf(stderr, "error %s\n", e.what());
        return 3;
    }
    return 0;
}
