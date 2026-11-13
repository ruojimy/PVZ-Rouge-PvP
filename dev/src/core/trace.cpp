// PVZ_TRACE=1: print a symbolised native stack whenever a PyError is constructed.
#include <cstring>
#include "core/value.h"
#include "core/trace.h"
#include <atomic>
#include <cstdio>
#include <cstdlib>
#ifdef _WIN32
#include <windows.h>
#include <dbghelp.h>
#pragma comment(lib, "dbghelp.lib")
#endif

namespace pvz {
namespace {
std::atomic<void*> crash_reserve{nullptr};
void reserve_crash_memory(){void* expected=nullptr;void* memory=std::malloc(256*1024);if(memory&&!crash_reserve.compare_exchange_strong(expected,memory))std::free(memory);}
#ifdef _WIN32
struct ThrowStack {void* frames[48]{};USHORT count=0;};
thread_local ThrowStack last_cpp_throw;
LONG WINAPI capture_cpp_throw(EXCEPTION_POINTERS* ep){
    if(ep&&ep->ExceptionRecord&&ep->ExceptionRecord->ExceptionCode==0xE06D7363)
        last_cpp_throw.count=CaptureStackBackTrace(1,48,last_cpp_throw.frames,nullptr);
    return EXCEPTION_CONTINUE_SEARCH;
}
#endif
}
void release_crash_reserve() noexcept{std::free(crash_reserve.exchange(nullptr));}
void print_last_cpp_throw(FILE* output) noexcept{
    if(!output)return;
#ifdef _WIN32
    const auto saved=last_cpp_throw;
    if(!saved.count){std::fprintf(output,"C++ throw-site capture unavailable; enable PVP_CAPTURE_CPP_TRACE before startup.\n");return;}
    std::fprintf(output,"C++ original throw stack (before unwinding):\n");
    const auto process=GetCurrentProcess();SymSetOptions(SYMOPT_UNDNAME|SYMOPT_DEFERRED_LOADS|SYMOPT_LOAD_LINES);
    SymInitialize(process,nullptr,TRUE);
    char storage[sizeof(SYMBOL_INFO)+1024];
    const auto base=reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
    for(USHORT i=0;i<saved.count;++i){
        const auto address=reinterpret_cast<DWORD64>(saved.frames[i]);
        std::fprintf(output,"  %p exe-relative=%llx",saved.frames[i],static_cast<unsigned long long>(address-base));
        auto* symbol=reinterpret_cast<SYMBOL_INFO*>(storage);symbol->SizeOfStruct=sizeof(SYMBOL_INFO);symbol->MaxNameLen=1000;DWORD64 offset=0;
        if(SymFromAddr(process,address,&offset,symbol)){
            std::fprintf(output," %s+%llx",symbol->Name,static_cast<unsigned long long>(offset));
            IMAGEHLP_LINE64 line{};line.SizeOfStruct=sizeof(line);DWORD displacement=0;
            if(SymGetLineFromAddr64(process,address,&displacement,&line))std::fprintf(output," %s:%lu",line.FileName,line.LineNumber);
        }
        std::fputc('\n',output);
    }
#else
    std::fprintf(output,"C++ throw-site stack unavailable on this platform.\n");
#endif
    std::fflush(output);
}
static thread_local size_t test_unsupported_hits_ = 0;
static thread_local std::string test_last_unsupported_;
size_t test_unsupported_count() { return test_unsupported_hits_; }
std::string test_last_unsupported() { return test_last_unsupported_; }
void trace_pyerror(const std::string& what) {
    if (std::getenv("PVZ_TEST_STRICT") && (what.rfind("NotImplementedError:", 0) == 0 || what.find("unsupported function attribute:") != std::string::npos)) {
        ++test_unsupported_hits_;
        test_last_unsupported_ = what;
    }
    static int enabled = -1;
    if (enabled < 0) { const char* e = std::getenv("PVZ_TRACE"); enabled = e && *e == '1'; }
    if (!enabled) return;
#ifdef _WIN32
    static bool init = false;
    HANDLE proc = GetCurrentProcess();
    if (!init) { SymSetOptions(SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS | SYMOPT_LOAD_LINES); SymInitialize(proc, nullptr, TRUE); init = true; }
    void* frames[48];
    USHORT n = CaptureStackBackTrace(1, 48, frames, nullptr);
    fprintf(stderr, "---- PyError: %s\n", what.c_str());
    char buf[sizeof(SYMBOL_INFO) + 512];
    for (USHORT i = 0; i < n; ++i) {
        auto* sym = reinterpret_cast<SYMBOL_INFO*>(buf);
        sym->SizeOfStruct = sizeof(SYMBOL_INFO);
        sym->MaxNameLen = 500;
        DWORD64 disp = 0;
        IMAGEHLP_LINE64 line{};
        line.SizeOfStruct = sizeof(line);
        DWORD d2 = 0;
        if (SymFromAddr(proc, DWORD64(frames[i]), &disp, sym)) {
            if (SymGetLineFromAddr64(proc, DWORD64(frames[i]), &d2, &line))
                fprintf(stderr, "  %s  (%s:%lu)\n", sym->Name, line.FileName, line.LineNumber);
            else
                fprintf(stderr, "  %s\n", sym->Name);
        }
    }
#endif
}
}  // namespace pvz

namespace pvz {
#ifdef _WIN32
static LONG WINAPI crash_filter(EXCEPTION_POINTERS* ep) {
    fprintf(stderr, "==== native crash 0x%08lx at %p\n", ep->ExceptionRecord->ExceptionCode, ep->ExceptionRecord->ExceptionAddress);
    HANDLE proc = GetCurrentProcess();
    SymSetOptions(SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS | SYMOPT_LOAD_LINES);
    SymInitialize(proc, nullptr, TRUE);
    CONTEXT ctx = *ep->ContextRecord;
    STACKFRAME64 sf{};
    sf.AddrPC.Offset = ctx.Rip; sf.AddrPC.Mode = AddrModeFlat;
    sf.AddrFrame.Offset = ctx.Rbp; sf.AddrFrame.Mode = AddrModeFlat;
    sf.AddrStack.Offset = ctx.Rsp; sf.AddrStack.Mode = AddrModeFlat;
    char buf[sizeof(SYMBOL_INFO) + 512];
    for (int i = 0; i < 40; ++i) {
        if (!StackWalk64(IMAGE_FILE_MACHINE_AMD64, proc, GetCurrentThread(), &sf, &ctx, nullptr,
                         SymFunctionTableAccess64, SymGetModuleBase64, nullptr)) break;
        auto* sym = reinterpret_cast<SYMBOL_INFO*>(buf);
        sym->SizeOfStruct = sizeof(SYMBOL_INFO); sym->MaxNameLen = 500;
        DWORD64 disp = 0; IMAGEHLP_LINE64 line{}; line.SizeOfStruct = sizeof(line); DWORD d2 = 0;
        if (SymFromAddr(proc, sf.AddrPC.Offset, &disp, sym)) {
            if (SymGetLineFromAddr64(proc, sf.AddrPC.Offset, &d2, &line))
                fprintf(stderr, "  %s  (%s:%lu)\n", sym->Name, line.FileName, line.LineNumber);
            else fprintf(stderr, "  %s\n", sym->Name);
        }
    }
    return EXCEPTION_EXECUTE_HANDLER;
}
void install_crash_handler() { reserve_crash_memory();const char* trace=std::getenv("PVP_CAPTURE_CPP_TRACE");if(trace&&*trace=='1')AddVectoredExceptionHandler(0,capture_cpp_throw);ULONG guarantee = 256 * 1024; SetThreadStackGuarantee(&guarantee); SetUnhandledExceptionFilter(crash_filter); AddVectoredExceptionHandler(0, [](EXCEPTION_POINTERS* ep) -> LONG {
    DWORD c = ep->ExceptionRecord->ExceptionCode;
    if (c == EXCEPTION_ACCESS_VIOLATION || c == EXCEPTION_STACK_OVERFLOW) crash_filter(ep);
    return EXCEPTION_CONTINUE_SEARCH; }); }
#else
void install_crash_handler() {reserve_crash_memory();}
#endif
}  // namespace pvz

namespace pvz {
// PVZ_TRACE_KEY=<key>: print value + stack for every dict write of that key (debug aid)
void trace_key_write(const V& c, const V& k, const V& v) {
    static std::string key = [] { const char* e = std::getenv("PVZ_TRACE_KEY"); std::string k(e ? e : ""); if (k == "hurt") k = "玩家受伤"; return k; }();
    if (key.empty() || k.t != V::STR || k.str() != key) return;
    static int enabled = -1;
    const V* id = (c.t == V::DICT || c.t == V::OBJ) ? c.find(V("_pvp_id")) : nullptr;
    trace_pyerror(std::string("write ") + ((id && id->t == V::STR) ? id->str() : std::string(c.type_name())) + " " + key + " = " + (v.is_num() ? std::to_string(v.num()) : std::string("?")));
}
}

// ---------------------------------------------------------------- sampling profiler (bench aid)
#ifdef _WIN32
#include <thread>
#include <atomic>
#include <map>
#include <vector>
#include <algorithm>
namespace pvz {
static std::atomic<bool> g_sampling{false};
static std::thread g_sampler;
static std::vector<std::vector<DWORD64>> g_samples;
#pragma comment(lib, "winmm.lib")
extern "C" __declspec(dllimport) unsigned int __stdcall timeBeginPeriod(unsigned int);
void start_sampler() {
    timeBeginPeriod(1);
    SymSetOptions(SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS | SYMOPT_LOAD_LINES);
    SymInitialize(GetCurrentProcess(), nullptr, TRUE);
    HANDLE target;
    DuplicateHandle(GetCurrentProcess(), GetCurrentThread(), GetCurrentProcess(), &target, 0, FALSE, DUPLICATE_SAME_ACCESS);
    g_sampling = true;
    g_sampler = std::thread([target]() {
        HANDLE proc = GetCurrentProcess();
        while (g_sampling) {
            Sleep(1);
            if (SuspendThread(target) == (DWORD)-1) continue;
            CONTEXT ctx{}; ctx.ContextFlags = CONTEXT_FULL;
            if (GetThreadContext(target, &ctx)) {
                std::vector<DWORD64> st;
                STACKFRAME64 sf{};
                sf.AddrPC.Offset = ctx.Rip; sf.AddrPC.Mode = AddrModeFlat;
                sf.AddrFrame.Offset = ctx.Rbp; sf.AddrFrame.Mode = AddrModeFlat;
                sf.AddrStack.Offset = ctx.Rsp; sf.AddrStack.Mode = AddrModeFlat;
                for (int i = 0; i < 40; ++i) {
                    if (!StackWalk64(IMAGE_FILE_MACHINE_AMD64, proc, target, &sf, &ctx, nullptr, SymFunctionTableAccess64, SymGetModuleBase64, nullptr)) break;
                    st.push_back(sf.AddrPC.Offset);
                }
                g_samples.push_back(std::move(st));
            }
            ResumeThread(target);
        }
    });
}
void stop_sampler_report(int top) {
    g_sampling = false;
    g_sampler.join();
    HANDLE proc = GetCurrentProcess();
    std::map<std::string, int> self_, incl;
    char buf[sizeof(SYMBOL_INFO) + 512];
    auto name = [&](DWORD64 a) {
        auto* sym = reinterpret_cast<SYMBOL_INFO*>(buf);
        sym->SizeOfStruct = sizeof(SYMBOL_INFO); sym->MaxNameLen = 500;
        DWORD64 d = 0;
        if (SymFromAddr(proc, a, &d, sym)) { std::string s(sym->Name); if (s.size() > 90) s = s.substr(0, 90); return s; }
        return std::string("?");
    };
    for (auto& st : g_samples) {
        if (st.empty()) continue;
        self_[name(st[0])]++;
        std::map<std::string, int> seen;
        for (auto a : st) { auto n = name(a); if (!seen[n]++) incl[n]++; }
    }
    auto dumpv = [&](const char* title, std::map<std::string, int>& m) {
        std::vector<std::pair<int, std::string>> v;
        for (auto& p : m) v.push_back({p.second, p.first});
        std::sort(v.rbegin(), v.rend());
        fprintf(stderr, "== %s (%zu samples)\n", title, g_samples.size());
        for (int i = 0; i < top && i < (int)v.size(); ++i) fprintf(stderr, "%6d %5.1f%%  %s\n", v[i].first, 100.0 * v[i].first / g_samples.size(), v[i].second.c_str());
    };
    std::map<std::string, int> alloc;
    for (auto& st : g_samples) {
        if (st.empty()) continue;
        std::string top = name(st[0]);
        if (top.find("Heap") == std::string::npos && top.find("malloc") == std::string::npos && top.find("free") == std::string::npos) continue;
        for (auto a : st) {
            auto n = name(a);
            if (n.find("Heap") != std::string::npos || n.find("malloc") != std::string::npos || n.find("free") != std::string::npos ||
                n.find("operator new") != std::string::npos || n.find("operator delete") != std::string::npos || n.find("std::") == 0 ||
                n.find("allocator") != std::string::npos || n.find("_Tidy") != std::string::npos || n.find("~") != std::string::npos ||
                n.find("make_shared") != std::string::npos || n.find("Box::") != std::string::npos) continue;
            alloc[n]++; break;
        }
    }
    dumpv("alloc callers", alloc);
    // PVZ_PROFILE_FOCUS=substr: for samples whose stack mentions substr, the first generated-code frame
    // (pm_*/fn_*/region_*) at or above the match -> which translated code pays for that helper.
    if (const char* fe = std::getenv("PVZ_PROFILE_FOCUS")) {
        std::string focus(fe);
        for (size_t a0 = 0, a1; a0 <= focus.size(); a0 = a1 + 1) {
            a1 = focus.find(',', a0); if (a1 == std::string::npos) a1 = focus.size();
            std::string f = focus.substr(a0, a1 - a0);
            if (f.empty()) continue;
            std::map<std::string, int> by;
            for (auto& st : g_samples) {
                size_t i = 0;
                for (; i < st.size(); ++i) if (name(st[i]).find(f) != std::string::npos) break;
                if (i == st.size()) continue;
                std::string who = "?";
                for (size_t j = i + 1; j < st.size(); ++j) {
                    auto n = name(st[j]);
                    if (n.find("pm_") != std::string::npos || n.find("fn_") != std::string::npos || n.find("region_") != std::string::npos ||
                        n.find("hand") != std::string::npos) { who = n; break; }
                }
                by[who]++;
            }
            std::string t = "focus " + f;
            dumpv(t.c_str(), by);
        }
    }
    // PVZ_PROFILE_UNDER=substr: children breakdown (direct callees, skipping std::function glue)
    std::vector<std::string> skips;
    if (const char* se = std::getenv("PVZ_PROFILE_SKIP")) {
        std::string sk(se);
        for (size_t a0 = 0, a1; a0 <= sk.size(); a0 = a1 + 1) { a1 = sk.find(',', a0); if (a1 == std::string::npos) a1 = sk.size(); if (a1 > a0) skips.push_back(sk.substr(a0, a1 - a0)); }
    }
    auto skip_frame = [&](const std::string& n) { for (auto& k : skips) if (n.find(k) != std::string::npos) return true; return false; };
    if (const char* ue = std::getenv("PVZ_PROFILE_UNDER")) {
        std::string f(ue);
        std::map<std::string, int> by;
        for (auto& st : g_samples) {
            size_t i = st.size();
            for (size_t j = st.size(); j-- > 0;) if (name(st[j]).find(f) != std::string::npos) { i = j; break; }  // outermost
            if (i == st.size()) continue;
            std::string who = "<self>";
            for (size_t j = i; j-- > 0;) {
                auto n = name(st[j]);
                if (n.find(f) != std::string::npos || n.find("_Func_impl") != std::string::npos || n.find("std::invoke") != std::string::npos ||
                    n.find("_ResumeCoro") != std::string::npos || skip_frame(n)) continue;
                who = n; break;
            }
            by[who]++;
        }
        std::string t = "under " + f;
        dumpv(t.c_str(), by);
    }
    // PVZ_PROFILE_TREE=depth: call tree over generated-code frames (regions, module functions,
    // methods, closures), rooted at the frame matching PVZ_PROFILE_ROOT (default _step_original)
    if (const char* te = std::getenv("PVZ_PROFILE_TREE")) {
        int depth = std::max(1, std::atoi(te));
        const char* re = std::getenv("PVZ_PROFILE_ROOT");
        std::string root = re ? re : "C_NativeBattle::m__step_original";
        auto gen_frame = [](const std::string& n) {
            return (n.find("pm_") != std::string::npos || n.find("region_") != std::string::npos || n.find("fn_") != std::string::npos ||
                    n.find("hand") != std::string::npos) && n.find("_Func_impl") == std::string::npos &&
                   n.find("call_method") == std::string::npos && n.find("::method") == std::string::npos;
        };
        auto shortname = [](std::string n) {
            for (const char* p : {"pvz::", "`", "'"}) { size_t i; while ((i = n.find(p)) != std::string::npos) n.erase(i, std::strlen(p)); }
            size_t i = n.find("::operator()");
            if (i != std::string::npos) n = n.substr(0, i);
            if (n.size() > 110) n = n.substr(0, 110);
            return n;
        };
        std::map<std::string, int> paths;
        size_t rooted = 0;
        for (auto& st : g_samples) {
            size_t r = st.size();
            for (size_t j = st.size(); j-- > 0;) if (name(st[j]).find(root) != std::string::npos) { r = j; break; }
            if (r == st.size()) continue;
            ++rooted;
            std::vector<std::string> chain;
            std::string last;
            for (size_t j = r; j-- > 0 && int(chain.size()) < depth;) {
                auto n = name(st[j]);
                if (!gen_frame(n)) continue;
                n = shortname(n);
                if (n == last) continue;
                chain.push_back(n); last = n;
            }
            std::string key;
            for (size_t k = 0; k <= chain.size(); ++k) {
                paths[key]++;
                if (k < chain.size()) key += (key.empty() ? "" : " > ") + chain[k];
            }
        }
        std::vector<std::pair<std::string, int>> v(paths.begin(), paths.end());
        fprintf(stderr, "== tree under %s (%zu samples)\n", root.c_str(), rooted);
        for (auto& [k, c] : v) {
            if (k.empty() || c * 200 < int(rooted)) continue;   // >= 0.5%
            int lvl = 0; for (size_t i = 0; (i = k.find(" > ", i)) != std::string::npos; i += 3) ++lvl;
            std::string leaf = k.substr(k.rfind(" > ") == std::string::npos ? 0 : k.rfind(" > ") + 3);
            fprintf(stderr, "%5.1f%% %*s%s\n", 100.0 * c / rooted, lvl * 2, "", leaf.c_str());
        }
    }
    // PVZ_PROFILE_MODULES=1: each sample charged to the module of its innermost generated-code frame
    if (std::getenv("PVZ_PROFILE_MODULES")) {
        std::map<std::string, int> by;
        for (auto& st : g_samples) {
            std::string who = "<runtime/other>";
            for (auto a : st) {
                auto n = name(a);
                size_t p = n.find("pm_");
                if (p != std::string::npos && n.find("_Func_impl") == std::string::npos) {
                    size_t e = n.find("::", p);
                    who = n.substr(p, e == std::string::npos ? std::string::npos : e - p); break;
                }
                if (n.find("pvz::region_") == 0 || n.find("pvz::region_") != std::string::npos) { who = n.substr(n.find("region_")); size_t e = who.find('('); if (e != std::string::npos) who = who.substr(0, e); break; }
                if (n.find("pvz::fn_") != std::string::npos) { who = "original_funcs (fn_*)"; break; }
                if (n.find("hand") != std::string::npos || n.find("HeroProxyHook") != std::string::npos) { who = "hand"; break; }
            }
            by[who]++;
        }
        dumpv("by module (innermost generated frame)", by);
    }
    // PVZ_PROFILE_FUNCS=<substring>: charge samples to the innermost frame whose name contains it
    if (const char* fe = std::getenv("PVZ_PROFILE_FUNCS")) {
        std::string f(fe);
        std::map<std::string, int> by;
        for (auto& st : g_samples) {
            for (auto a : st) {
                auto n = name(a);
                if (n.find(f) != std::string::npos && n.find("_Func_impl") == std::string::npos) { by[n]++; break; }
            }
        }
        dumpv(("functions matching " + f).c_str(), by);
    }
    // PVZ_PROFILE_LINES=<function substring>: samples inside that function by source line (inclusive of callees)
    if (const char* le = std::getenv("PVZ_PROFILE_LINES")) {
        std::string f(le);
        std::map<std::string, int> by;
        for (auto& st : g_samples) {
            for (size_t i = 0; i < st.size(); ++i) {
                auto n = name(st[i]);
                if (n.find(f) == std::string::npos || n.find("_Func_impl") != std::string::npos) continue;
                IMAGEHLP_LINE64 ln{}; ln.SizeOfStruct = sizeof(ln);
                DWORD disp = 0;
                // return addresses point after the call: step back one byte to land on the call's line
                DWORD64 addr = i == 0 ? st[i] : st[i] - 1;
                if (SymGetLineFromAddr64(proc, addr, &disp, &ln)) by["line " + std::to_string(ln.LineNumber)]++;
                else by["?"]++;
                break;
            }
        }
        dumpv(("lines in " + f).c_str(), by);
    }
    dumpv("self", self_);
    dumpv("inclusive", incl);
}
}  // namespace pvz
namespace pvz {
// Symbolize captured stacks (run_battle PVZ_ALLOCSTAT=<size>): first non-allocator frame, and first generated frame.
void report_stacks(const std::vector<std::vector<void*>>& stacks, int top) {
    HANDLE proc = GetCurrentProcess();
    SymSetOptions(SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS | SYMOPT_LOAD_LINES);
    SymInitialize(proc, nullptr, TRUE);
    char buf[sizeof(SYMBOL_INFO) + 512];
    auto name = [&](void* a) {
        auto* sym = reinterpret_cast<SYMBOL_INFO*>(buf);
        sym->SizeOfStruct = sizeof(SYMBOL_INFO); sym->MaxNameLen = 500;
        DWORD64 d = 0;
        if (SymFromAddr(proc, (DWORD64)a, &d, sym)) { std::string s(sym->Name); if (s.size() > 100) s = s.substr(0, 100); return s; }
        return std::string("?");
    };
    std::map<std::string, int> helper, gen, pair;
    for (auto& st : stacks) {
        std::string h = "?", g = "?";
        for (auto a : st) {
            auto n = name(a);
            bool alloc = n.find("operator new") != std::string::npos || n.find("std::") == 0 || n.find("allocator") != std::string::npos ||
                         n.find("malloc") != std::string::npos || n.find("_Allocate") != std::string::npos || n == "?" ||
                         n.find("report_") != std::string::npos;
            if (alloc) continue;
            if (h == "?") h = n;
            if (n.find("pm_") != std::string::npos || n.find("fn_") != std::string::npos || n.find("region_") != std::string::npos ||
                n.find("hand") != std::string::npos) { g = n; break; }
        }
        helper[h]++; gen[g]++; pair[h + "  <-  " + g]++;
    }
    auto dumpv = [&](const char* title, std::map<std::string, int>& m) {
        std::vector<std::pair<int, std::string>> v;
        for (auto& p : m) v.push_back({p.second, p.first});
        std::sort(v.rbegin(), v.rend());
        fprintf(stderr, "== %s (%zu stacks)\n", title, stacks.size());
        for (int i = 0; i < top && i < (int)v.size(); ++i) fprintf(stderr, "%6d %5.1f%%  %s\n", v[i].first, 100.0 * v[i].first / stacks.size(), v[i].second.c_str());
    };
    dumpv("allocating helper", helper);
    dumpv("generated caller", gen);
    dumpv("helper <- caller", pair);
}
}  // namespace pvz
#endif
