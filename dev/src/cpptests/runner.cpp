// Runner for the translated old-suite tests: the same engine as the released game (pvzcore + pvzui,
// translated pvp modules, SDL pygame facade). One instance per test method, as unittest does:
//   setUpClass once per class -> for each test: setUp, test, tearDown, doCleanups -> tearDownClass.
//   cpp_tests [-m module]... [-k substring] [--json out.json]
// Outcome: AssertionError -> FAIL, SkipTest -> SKIP, any other exception -> ERROR, else PASS.
#include "cpptests/registry.h"
#include "pg/pg.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/hand/hero_monitor.h"
#include "data/datastore.h"
#include "core/gil.h"
#include <SDL.h>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <map>
#include <string>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#endif

namespace pvz::cpptests { bool native_platform_contract(); bool native_behavior_companion(const std::string&); bool native_atlas_probe();bool application_lifecycle_contract();bool projectile_diagnostic();bool contact_animation_diagnostic(); }
using namespace pvz;
namespace pvz { void install_crash_handler(); size_t test_unsupported_count(); std::string test_last_unsupported(); }

namespace {
std::string utf8_prefix(const std::string& text, size_t limit) {
    size_t end = std::min(limit, text.size());
    if (end < text.size()) while (end && (static_cast<unsigned char>(text[end]) & 0xc0) == 0x80) --end;
    return text.substr(0, end);
}
std::string json_str(const std::string& s) {
    std::string o = "\"";
    for (size_t i = 0; i < s.size(); ++i) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        if (c >= 0x80) {
            size_t count = c >= 0xc2 && c <= 0xdf ? 2 : c >= 0xe0 && c <= 0xef ? 3 : c >= 0xf0 && c <= 0xf4 ? 4 : 0;
            bool valid = count && i + count <= s.size();
            for (size_t n = 1; valid && n < count; ++n) valid = (static_cast<unsigned char>(s[i + n]) & 0xc0) == 0x80;
            if (valid && count >= 3) {
                unsigned char second = static_cast<unsigned char>(s[i + 1]);
                valid = !(c == 0xe0 && second < 0xa0) && !(c == 0xed && second >= 0xa0) &&
                        !(c == 0xf0 && second < 0x90) && !(c == 0xf4 && second >= 0x90);
            }
            if (valid) { o.append(s, i, count); i += count - 1; }
            else o += "\\ufffd";   // an earlier diagnostic may itself have truncated a multibyte character
            continue;
        }
        if (c == '"' || c == '\\') { o += '\\'; o += char(c); }
        else if (c == '\n') o += "\\n";
        else if (c == '\r') o += "\\r";
        else if (c == '\t') o += "\\t";
        else if (c < 0x20) { char b[8]; snprintf(b, sizeof b, "\\u%04x", c); o += b; }
        else o += char(c);
    }
    return o + "\"";
}
struct Result { std::string module, cls, test, outcome, detail; double seconds = 0; };

std::string classify(const PyError& e, std::string& detail) {
    detail = e.what();
    if (e.kind == "SkipTest") return "SKIP";
    if (e.matches("AssertionError")) return "FAIL";
    return "ERROR";
}
}  // namespace

int main(int argc, char** argv) {
    SDL_SetMainReady();
    install_crash_handler();
    gil::init();
    data::set_data_dir("extract/data");
    py::g_real_clock = true;
    std::vector<std::string> only_mods;
    std::string only_test, json_out;
    bool framework_only = false;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--framework-selftest") framework_only = true;
        else if (a == "-m" && i + 1 < argc) only_mods.push_back(argv[++i]);
        else if (a == "-k" && i + 1 < argc) only_test = argv[++i];
        else if (a == "--json" && i + 1 < argc) json_out = argv[++i];
        else if (a == "--list") {
            for (auto& c : cpptests::registry()) for (auto* t : c.tests) printf("%s.%s.%s\n", c.module, c.binding, t);
            return 0;
        }
    }
    // isolated userdata (never the player's real save folder)
    if (!std::getenv("PVP_USERDATA")) {
        std::string tmp = (std::filesystem::temp_directory_path() / ("pvz-cpptests-" + std::to_string(SDL_GetTicks()) + "-" + std::to_string(rand()))).string();
#ifdef _WIN32
        _putenv_s("PVP_USERDATA", tmp.c_str());
#else
        setenv("PVP_USERDATA", tmp.c_str(), 1);
#endif
    }
    pg::install_pygame();
    cpptests::install_test_adapters();
    std::vector<Result> results;
    std::map<std::string, int> counts;
    try {
        init_pvp_modules();
    } catch (PyError& e) {
        fprintf(stderr, "init failed: %s\n", e.what());
        return 3;
    }
    // Production initialization includes retired-core introspection probes. Enable
    // strict testing only after that common startup, before any test is imported.
#ifdef _WIN32
    _putenv_s("PVZ_TEST_STRICT", "1");
#else
    setenv("PVZ_TEST_STRICT", "1", 1);
#endif
    for(int i=1;i<argc;++i)if(std::string(argv[i])=="--native-platform-contract")return cpptests::native_platform_contract()?0:1;
    if (!cpptests::framework_contract()) return 4;
    if (framework_only) return 0;
    for(int i=1;i+1<argc;++i)if(std::string(argv[i])=="--native-behavior-companion")return cpptests::native_behavior_companion(argv[i+1])?0:1;
    for(int i=1;i<argc;++i)if(std::string(argv[i])=="--native-atlas-probe")return cpptests::native_atlas_probe()?0:1;
    for(int i=1;i<argc;++i)if(std::string(argv[i])=="--application-lifecycle")return cpptests::application_lifecycle_contract()?0:1;
    for(int i=1;i<argc;++i)if(std::string(argv[i])=="--projectile-diagnostic")return cpptests::projectile_diagnostic()?0:1;
    for(int i=1;i<argc;++i)if(std::string(argv[i])=="--contact-animation-diagnostic")return cpptests::contact_animation_diagnostic()?0:1;
    for (int i = 1; i + 1 < argc; ++i) if (std::string(argv[i]) == "--units-probe") {
        try { py::native_hook(V("test.units.probe"), Args{V(argv[i + 1])}); return 0; }
        catch (const PyError& e) { fprintf(stderr, "%s\n", e.what()); return 1; }
    }
    for (int i = 1; i + 2 < argc; ++i) if (std::string(argv[i]) == "--runtime-report") {
        try { py::native_hook(V("test.runtime.report"), Args{V(argv[i + 1]), V(argv[i + 2])}); return 0; }
        catch (const PyError& e) { fprintf(stderr, "%s\n", e.what()); return 1; }
    }
    for (int i = 1; i + 2 < argc; ++i) if (std::string(argv[i]) == "--font-report") {
        try { py::native_hook(V("test.graphics.font"), Args{V(argv[i + 1]), V(argv[i + 2])}); return 0; }
        catch (const PyError& e) { fprintf(stderr, "%s\n", e.what()); return 1; }
    }
    // Test-tool diagnostic for an independent CPython 3.8 decoder comparison.
    for (int i = 1; i + 2 < argc; ++i) if (std::string(argv[i]) == "--dis-report") {
        try { py::native_hook(V("test.dis38.report"), Args{V(argv[i + 1]), V(argv[i + 2])}); return 0; }
        catch (const PyError& e) { fprintf(stderr, "%s\n", e.what()); return 1; }
    }
    for (int i = 1; i + 2 < argc; ++i) if (std::string(argv[i]) == "--graphics-report") {
        try { py::native_hook(V("test.graphics.report"), Args{V(argv[i + 1]), V(argv[i + 2])}); return 0; }
        catch (const PyError& e) { fprintf(stderr, "%s\n", e.what()); return 1; }
    }
    for (int i = 1; i + 2 < argc; ++i) if (std::string(argv[i]) == "--image-bytes-report") {
        try { py::native_hook(V("test.graphics.frombytes"), Args{V(argv[i + 1]), V(argv[i + 2])}); return 0; }
        catch (const PyError& e) { fprintf(stderr, "%s\n", e.what()); return 1; }
    }
    for (int i = 1; i + 2 < argc; ++i) if (std::string(argv[i]) == "--recipes-report") {
        try { py::native_hook(V("test.graphics.recipes"), Args{V(argv[i + 1]), V(argv[i + 2])}); return 0; }
        catch (const PyError& e) { fprintf(stderr, "%s\n", e.what()); return 1; }
    }
    for (int i = 1; i + 1 < argc; ++i) if (std::string(argv[i]) == "--seedbank-report") {
        try { py::native_hook(V("test.seedbank.report"), Args{V(argv[i + 1])}); return 0; }
        catch (const PyError& e) { fprintf(stderr, "%s\n", e.what()); return 1; }
    }
    // diagnostic: cpp_tests --dump-module-value pvp.catalog CARDS out.json -> the exact json.dumps used by digest()
    for (int i = 1; i + 3 < argc; ++i) if (std::string(argv[i]) == "--dump-module-value") {
        V m = py::import_pvp_module(argv[i + 1]);
        V v = pvz::getattr(m, Sym(argv[i + 2]));
        V text = py::stdlib_call(V("json.dumps"), Args({v}, {{Sym("sort_keys"), V(true)}, {Sym("ensure_ascii"), V(false)}, {Sym("separators"), V::tuple({V(","), V(":")})}, {Sym("allow_nan"), V(false)}}));
        std::ofstream(argv[i + 3], std::ios::binary) << text.str();
        return 0;
    }
    // diagnostic: cpp_tests --hash-report out.json -> native catalog/rules identity hashes, plus the same
    // digests after one rule / one card value changes (they must differ); compare across runs and platforms
    for (int i = 1; i + 1 < argc; ++i) if (std::string(argv[i]) == "--hash-report") {
        V cat = py::import_pvp_module("catalog");
        V rules = py::deepcopy(pvz::getattr(cat, Sym("RULES")));
        rules.at(V("plant_start")) = rules.at(V("plant_start")) + V(1.0);
        V cards = py::deepcopy(pvz::getattr(cat, Sym("CARDS")));
        V first = cards.kv().front().first;
        cards.at(first).at(V("cost")) = cards.at(first).at(V("cost")) + V(1.0);
        V report = py_dict({
            {V("catalog_hash"), callm(cat, Sym("catalog_hash"), Args{})},
            {V("rules_hash"), callm(cat, Sym("rules_hash"), Args{})},
            {V("rules_hash_plant_start_plus_1"), callm(cat, Sym("rules_hash"), Args{rules})},
            {V("catalog_digest_first_card_cost_plus_1"), callm(cat, Sym("digest"), Args{cards})},
            {V("changed_card"), first}});
        std::ofstream(argv[i + 1], std::ios::binary) << py::stdlib_call(V("json.dumps"), Args({report}, {{Sym("ensure_ascii"), V(false)}, {Sym("sort_keys"), V(true)}})).str();
        return 0;
    }
    auto wanted = [&](const cpptests::Case& c) {
        if (only_mods.empty()) return true;
        for (auto& m : only_mods) if (m == c.module) return true;
        return false;
    };
    for (auto& c : cpptests::registry()) {
        if (!wanted(c)) continue;
        std::vector<std::string> tests;
        for (auto* t : c.tests) if (only_test.empty() || std::string(t).find(only_test) != std::string::npos) tests.push_back(t);
        if (tests.empty()) continue;
        V cls;
        std::string class_error;
        const auto class_unsupported_before = test_unsupported_count();
        try {
            cls = c.cls_value();
            cpptests::set_current_test("");   // class-level reference invocations are not captured
            callm(cls, Sym("setUpClass"), Args{});
        } catch (PyError& e) {
            class_error = std::string("setUpClass: ") + e.what();
        }
        if (class_error.empty() && test_unsupported_count() != class_unsupported_before)
            class_error = "setUpClass used unsupported capability: " + test_last_unsupported();
        for (auto& t : tests) {
            const auto guard_before = pm_hero_guard::reported_violation_count();
            const auto unsupported_before = test_unsupported_count();
            Result r{c.module, c.binding, t, "PASS", "", 0};
            cpptests::set_current_test(std::string(c.module) + "." + c.binding + "." + t);
            auto t0 = std::chrono::steady_clock::now();
            if (!class_error.empty()) {
                std::string d; r.outcome = "ERROR"; r.detail = class_error;
            } else {
                V inst;
                try {
                    inst = cls.call(Args{V(t)});
                    callm(inst, Sym("setUp"), Args{});
                    try {
                        callm(inst, Sym(t), Args{});
                    } catch (PyError& e) {
                        r.outcome = classify(e, r.detail);
                    }
                    try { callm(inst, Sym("tearDown"), Args{}); }
                    catch (PyError& e) { if (true) { r.outcome = "ERROR"; r.detail = std::string("tearDown: ") + e.what(); } }
                } catch (PyError& e) {
                    r.outcome = classify(e, r.detail);
                    if (r.outcome == "FAIL") r.outcome = "ERROR";
                    r.detail = std::string("setUp: ") + r.detail;
                } catch (std::exception& e) {
                    r.outcome = "ERROR"; r.detail = std::string("C++ exception: ") + e.what();
                }
                if (inst.has()) {
                    try { callm(inst, Sym("doCleanups"), Args{}); }
                    catch (PyError& e) { if (true) { r.outcome = "ERROR"; r.detail = std::string("cleanup: ") + e.what(); } }
                }
            }
            if (test_unsupported_count() != unsupported_before && r.outcome == "PASS") {
                r.outcome = "ERROR";
                r.detail = "unsupported capability was caught by test: " + test_last_unsupported();
            }
            if (pm_hero_guard::reported_violation_count()!=guard_before && r.outcome=="PASS") {
                r.outcome="FAIL";r.detail="hero guard violation caught by test: "+pm_hero_guard::last_violation();
            }
            if (r.outcome == "PASS") {   // every CPython reference invocation of this test must have been replayed
                std::string unconsumed = cpptests::reference_consumption_error(std::string(c.module) + "." + c.binding + "." + t);
                if (!unconsumed.empty()) { r.outcome = "ERROR"; r.detail = unconsumed; }
            }
            r.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
            printf("%-5s %s.%s.%s (%.2fs)%s%s\n", r.outcome.c_str(), c.module, c.binding, t.c_str(), r.seconds,
                   r.detail.empty() ? "" : "  -- ", utf8_prefix(r.detail, 400).c_str());
            fflush(stdout);
            counts[r.outcome]++;
            results.push_back(std::move(r));
        }
        if (class_error.empty()) {
            try { callm(cls, Sym("tearDownClass"), Args{}); }
            catch (PyError& e) {
                results.push_back(Result{c.module, c.binding, "tearDownClass", "ERROR", e.what(), 0});
                counts["ERROR"]++;
                fprintf(stderr, "tearDownClass %s: %s\n", c.binding, e.what());
            }
        }
    }
    printf("\nRan %zu tests: PASS %d FAIL %d ERROR %d SKIP %d\n", results.size(), counts["PASS"], counts["FAIL"], counts["ERROR"], counts["SKIP"]);
    if (!json_out.empty()) {
        std::ofstream o(json_out, std::ios::binary);
        o << "[\n";
        for (size_t i = 0; i < results.size(); ++i) {
            auto& r = results[i];
            o << "{\"module\":" << json_str(r.module) << ",\"class\":" << json_str(r.cls) << ",\"test\":" << json_str(r.test)
              << ",\"outcome\":" << json_str(r.outcome) << ",\"seconds\":" << r.seconds << ",\"detail\":" << json_str(utf8_prefix(r.detail, 2000)) << "}"
              << (i + 1 < results.size() ? ",\n" : "\n");
        }
        o << "]\n";
    }
    fflush(nullptr);
    _exit(results.empty() ? 2 : (counts["FAIL"] || counts["ERROR"] ? 1 : 0));
}
