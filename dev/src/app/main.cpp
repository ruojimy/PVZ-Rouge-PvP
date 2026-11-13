// PvZ PvP71 native game entry: the translated app.run() over the SDL2 pygame facade.
// Windows: the EXE (dist/PvZ-PvP-Native). Android: libmain.so under SDLActivity (android/), the game data
// ships as APK assets and is unpacked once into the app's internal storage, which becomes the cwd.
#include "pg/pg.h"
#include "sim/pvp/pvprt.h"
#include "sim/pvp/battle_api.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_userdata.h"
#include "data/datastore.h"
#include "core/fsutil.h"
#include "core/save_upgrade72.h"
#include "app/diagnostic72.h"
#include "app/developer_tools.h"
#include <SDL.h>
#include <cstdio>
#include <cstdlib>
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#ifdef __ANDROID__
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <memory>
#endif
#ifdef _WIN32
#include <windows.h>
#else
#include <csignal>
#include <unistd.h>
#endif

using namespace pvz;

namespace pvz { void install_crash_handler(); bool install_native_perf_boost(const std::string& userdata); }
#include "core/gil.h"

// v is UTF-8 (see env_u8 in core/fsutil.h for why the ANSI CRT/Win32 calls are not used).
static void set_env(const char* k, const std::string& v) {
    env_set_u8(k, v);
#ifdef _WIN32
    std::wstring key(k, k + std::strlen(k));
    SetEnvironmentVariableW(key.c_str(), u8p(v).wstring().c_str());
#endif
}

// Error text for the crash file / message box as UTF-8. MSVC's std::system_error and
// filesystem_error messages come from FormatMessageA in the ANSI code page (GBK on Chinese
// Windows); shown as UTF-8 every Chinese character turned into boxes.
static std::string utf8_message(const std::string& s) {
#ifdef _WIN32
    if (s.empty() || MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), int(s.size()), nullptr, 0) > 0)
        return s;
    int wide = MultiByteToWideChar(CP_ACP, 0, s.data(), int(s.size()), nullptr, 0);
    std::wstring w(size_t(wide), L'\0');
    MultiByteToWideChar(CP_ACP, 0, s.data(), int(s.size()), w.data(), wide);
    int bytes = WideCharToMultiByte(CP_UTF8, 0, w.data(), wide, nullptr, 0, nullptr, nullptr);
    std::string out(size_t(bytes), '\0');
    WideCharToMultiByte(CP_UTF8, 0, w.data(), wide, out.data(), bytes, nullptr, nullptr);
    return out;
#else
    return s;
#endif
}

static void report_fatal(const std::string& raw,bool interactive=true) {
    std::string msg = utf8_message(raw);
    std::ofstream("crash-native.txt", std::ios::binary) << msg << "\n";   // UTF-8
    fprintf(stderr,"PvZ native fatal: %s\n",msg.c_str());
    if(interactive)SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "PvZ PvP Native", msg.c_str(), nullptr);
}

#ifdef __ANDROID__
// assets/manifest.txt: first line = build stamp, then one relative path per line (written by
// android/prepare_assets.py). Unpacked again whenever the stamp changes (an updated APK).
// SDL_RWFromFile prefers files already unpacked in internal storage. During
// an upgrade that silently reads the old resource and writes it back. Read
// this APK's AssetManager directly; keep its Java owner alive for the copy.
class ApkAssets {
    JNIEnv* env_ = nullptr;
    jobject activity_ = nullptr, assets_ = nullptr;
    AAssetManager* manager_ = nullptr;
public:
    ApkAssets() {
        env_ = static_cast<JNIEnv*>(SDL_AndroidGetJNIEnv());
        activity_ = static_cast<jobject>(SDL_AndroidGetActivity());
        if (!env_ || !activity_) throw std::runtime_error("Android activity unavailable");
        jclass type = env_->GetObjectClass(activity_);
        jmethodID get = env_->GetMethodID(type, "getAssets", "()Landroid/content/res/AssetManager;");
        env_->DeleteLocalRef(type);
        assets_ = get ? env_->CallObjectMethod(activity_, get) : nullptr;
        manager_ = assets_ ? AAssetManager_fromJava(env_, assets_) : nullptr;
        if (!manager_) throw std::runtime_error("APK asset manager unavailable");
    }
    ~ApkAssets() {
        if (assets_) env_->DeleteLocalRef(assets_);
        if (activity_) env_->DeleteLocalRef(activity_);
    }
    bool read(const std::string& rel, std::string& out) {
        std::unique_ptr<AAsset, decltype(&AAsset_close)> asset(
            AAssetManager_open(manager_, rel.c_str(), AASSET_MODE_STREAMING), AAsset_close);
        if (!asset) return false;
        auto length = AAsset_getLength64(asset.get());
        if (length < 0) return false;
        out.resize(static_cast<size_t>(length));
        size_t got = 0;
        while (got < out.size()) {
            size_t chunk = std::min<size_t>(out.size() - got, 1024 * 1024);
            int n = AAsset_read(asset.get(), out.data() + got, chunk);
            if (n <= 0) return false;
            got += static_cast<size_t>(n);
        }
        return true;
    }
};
static void unpack_assets(const std::string& root) {
    namespace fs = std::filesystem;
    ApkAssets apk;
    std::string manifest;
    if (!apk.read("manifest.txt", manifest)) throw std::runtime_error("APK asset manifest missing");
    size_t nl = manifest.find('\n');
    // Invalidate stamps written by the old filesystem-first installer.
    std::string stamp = "apk-only-v1:" + manifest.substr(0, nl);
    std::string have;
    { std::ifstream f(root + "/.assets_stamp", std::ios::binary); std::getline(f, have); }
    if (have == stamp) { SDL_Log("pvz: assets up to date (%s)", stamp.c_str()); return; }
    SDL_Log("pvz: unpacking assets %s -> %s (%zu bytes manifest)", stamp.c_str(), root.c_str(), manifest.size());
    int written = 0, failed = 0, missing = 0;
    size_t pos = nl == std::string::npos ? manifest.size() : nl + 1;
    std::string buf;
    while (pos < manifest.size()) {
        size_t e = manifest.find('\n', pos);
        std::string rel = manifest.substr(pos, e == std::string::npos ? std::string::npos : e - pos);
        pos = e == std::string::npos ? manifest.size() : e + 1;
        if (!rel.empty() && rel.back() == '\r') rel.pop_back();
        if (rel.empty()) continue;
        if (!apk.read(rel, buf)) { if (++missing < 5) SDL_Log("pvz: APK asset missing: %s", rel.c_str()); continue; }
        fs::path dst = fs::path(root) / u8p(rel);
        std::error_code ec;
        fs::create_directories(dst.parent_path(), ec);
        std::ofstream o(dst, std::ios::binary);
        o.write(buf.data(), std::streamsize(buf.size()));
        if (o) ++written; else if (++failed < 5) SDL_Log("pvz: write failed %s (%s)", dst.c_str(), ec.message().c_str());
    }
    SDL_Log("pvz: unpacked %d files, %d missing, %d failed", written, missing, failed);
    if (failed || missing) throw std::runtime_error("APK asset upgrade incomplete; refusing stale resources");
    std::ofstream marker(root + "/.assets_stamp", std::ios::binary);
    marker << stamp << "\n";marker.close();
    if (marker.fail()) throw std::runtime_error("Cannot record APK asset upgrade");
}
#endif

#ifdef _WIN32
// PvP73 PC upgrade: the release zip has one fixed top folder (PvZ-PvP-Native), so a new version is
// installed by extracting it over the old folder. Files the old version shipped and the new one no
// longer does would linger and could shadow renamed assets; SHA256SUMS lists every shipped file.
// Only the shipped asset trees are swept; saves live in %APPDATA% and are never touched here.
// Returns the number of removed files (or -1 when there is no usable manifest).
static int sweep_stale_release_files(const std::filesystem::path& dir, std::vector<std::string>& removed) {
    namespace fs = std::filesystem;
    std::ifstream sums(dir / "SHA256SUMS", std::ios::binary);
    if (!sums) return -1;
    std::vector<std::string> listed; std::string line;
    while (std::getline(sums, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        const auto star = line.find(" *./");
        if (star == 64) listed.push_back(line.substr(star + 4));
    }
    if (listed.size() < 1000) return -1;            // not a release manifest: do nothing
    std::sort(listed.begin(), listed.end());
    int count = 0;
    for (const char* tree : {"extract", "图片", "音乐", "音效", "fonts"}) {
        const fs::path root = dir / u8p(tree); std::error_code ec;
        if (!fs::is_directory(root, ec)) continue;
        std::vector<fs::path> stale;
        for (auto it = fs::recursive_directory_iterator(root, ec); !ec && it != fs::recursive_directory_iterator(); it.increment(ec)) {
            if (!it->is_regular_file(ec)) continue;
            std::string rel = p8(fs::relative(it->path(), dir, ec)); if (ec) break;
            for (auto& c : rel) if (c == '\\') c = '/';
            if (!std::binary_search(listed.begin(), listed.end(), rel)) stale.push_back(it->path());
        }
        for (const auto& path : stale) if (fs::remove(path, ec)) { ++count; removed.push_back(p8(fs::relative(path, dir, ec))); }
    }
    return count;
}
// Once per installed build: sweep, then tell the player the upgrade finished (saves untouched).
static void release_upgrade_check(const std::filesystem::path& exe_dir, const std::string& userdata) {
    namespace fs = std::filesystem;
    if (!fs::is_regular_file(exe_dir / "SHA256SUMS")) return;
    std::string build = "unknown";
    {   std::ifstream in(exe_dir / "extract" / "data" / "__init__.json", std::ios::binary);
        const std::string text((std::istreambuf_iterator<char>(in)), {});
        const auto k = text.find("\"BUILD\""); const auto a = k == std::string::npos ? k : text.find('"', text.find(':', k) + 1);
        const auto b = a == std::string::npos ? a : text.find('"', a + 1);
        if (b != std::string::npos) build = text.substr(a + 1, b - a - 1); }
    const fs::path marker = u8p(userdata) / "installed-build.txt";
    std::string previous;
    { std::ifstream in(marker, std::ios::binary); std::getline(in, previous); }
    while (!previous.empty() && (previous.back() == '\r' || previous.back() == ' ')) previous.pop_back();
    // PvP72 and older never wrote the marker: existing saves mean this is an upgrade, not a fresh install.
    const bool had_saves = previous.empty() && fs::is_regular_file(u8p(userdata) / "player.json");
    if (previous == build) return;
    std::vector<std::string> removed;
    const int count = sweep_stale_release_files(exe_dir, removed);
    std::error_code ec; fs::create_directories(marker.parent_path(), ec);
    { std::ofstream out(marker, std::ios::binary); out << build << "\n"; }
    if (count > 0) {
        std::ofstream log(u8p(userdata) / "upgrade-cleanup.txt", std::ios::binary | std::ios::app);
        log << "build " << build << " (from " << (previous.empty() ? "unknown" : previous) << "): removed " << count << " stale files\n";
        for (const auto& r : removed) log << "  " << r << "\n";
    }
    if (!previous.empty() || had_saves) {
        const std::string text = "已升级到 " + build + "（原版本 " + (previous.empty() ? std::string("PvP72 或更早") : previous) + "）。\n存档、设置与回放保持不变" +
            (count > 0 ? "；已清理旧版本残留文件 " + std::to_string(count) + " 个。" : "。");
        { std::ofstream log(u8p(userdata) / "upgrade-cleanup.txt", std::ios::binary | std::ios::app); log << "notice: " << text << "\n"; }
        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_INFORMATION, "PvZ PvP Native", text.c_str(), nullptr);
    }
}
#endif

int main(int argc, char** argv) {
    const bool diagnostic_mode=argc>1&&(std::string(argv[1])=="--diagnostic"||std::string(argv[1])=="--diagnostic-json");
    int exit_status=0;
    bool default_pc_userdata=false;
    install_crash_handler();
    gil::init();   // main thread holds the GIL; network transports run on GIL threads
#ifdef _WIN32
    {   // release layout (dist/PvZ-PvP-Native): data beside the exe -> run from there, whatever the launch cwd
        wchar_t buf[MAX_PATH];
        DWORD n = GetModuleFileNameW(nullptr, buf, MAX_PATH);
        std::wstring exe(buf, n);
        std::wstring dir = exe.substr(0, exe.find_last_of(L"\\/"));
        if (GetFileAttributesW((dir + L"\\extract\\data").c_str()) != INVALID_FILE_ATTRIBUTES) SetCurrentDirectoryW(dir.c_str());
    }
    // Stable native save location across releases. Legacy sources are merged
    // read-only below; explicit PVP_USERDATA continues to isolate tests/users.
    if (std::string existing; !env_u8("PVP_USERDATA", existing)) {
        default_pc_userdata=true;
        std::string appdata;
        if (!env_u8("APPDATA", appdata)) appdata = ".";
        set_env("PVP_USERDATA", appdata + "/PVZ-PvP-Native/pvp_userdata");
    }
#else
    signal(SIGPIPE, SIG_IGN);   // a peer closing a socket must not kill the process
#ifdef __ANDROID__
    {
        SDL_SetHint(SDL_HINT_ORIENTATIONS, "LandscapeLeft LandscapeRight");
        const char* internal = SDL_AndroidGetInternalStoragePath();
        std::string root = internal ? internal : ".";
        try { unpack_assets(root); }
        catch (const std::exception& error) {
            SDL_Log("APK upgrade failed: %s", error.what());
            SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "PvZ PvP Native", error.what(), nullptr);
            return 3;
        }
        if (chdir(root.c_str()) != 0) SDL_Log("chdir %s failed", root.c_str());
        set_env("PVP_USERDATA", root + "/pvp_userdata");
        set_env("ANDROID_PRIVATE", root);   // app._is_android(): touch layout, android display path
    }
#endif
#endif
    data::set_data_dir("extract/data");
    py::g_real_clock = true;
    pg::install_pygame();
    try {
        init_pvp_modules();
        pm_app::init();
#ifdef __ANDROID__
        // PvP73: native perf_boost provider (ADPF hint, big-core binding, 30 fps while slowed, diagnostics).
        if (std::string ud; env_u8("PVP_USERDATA", ud)) install_native_perf_boost(ud);
#endif
        if(argc>1 && std::string(argv[1])=="--developer-tools") {
            if(argc!=4) {
                fprintf(stderr,"Usage: --developer-tools request.json response.json\n");
                exit_status=2;
            } else exit_status=run_developer_tools(argv[2],argv[3]);
        } else if(argc==3 && (std::string(argv[1])=="--diagnostic" || std::string(argv[1])=="--diagnostic-json")) {
            std::string config=argv[2];
            if(std::string(argv[1])=="--diagnostic") {
                std::ifstream input(u8p(config),std::ios::binary);
                if(!input)throw std::runtime_error("Diagnostic config file missing");
                config=std::string(std::istreambuf_iterator<char>(input),{});
            }
            exit_status=run_diagnostic72(config);
        } else if(argc==3 && std::string(argv[1])=="--smoke-report") {
            // Explicit package acceptance only. The normal game entry retains
            // its existing call and cannot enable this from saved settings.
            V report=pm_app::f_run(Args({},{{Sym("auto_test"),V("smoke")}}));
            std::ofstream output(u8p(argv[2]),std::ios::binary);output<<dump(report)<<"\n";output.close();
            V smoke=py::m_get(report,V("smoke"),V::dict());
            bool passed=report.is_dict() && py::m_get(report,V("passed"),V(false)).truthy() && py::m_get(smoke,V("native_checks_passed"),V(false)).truthy() && py::m_get(smoke,V("native_tick"))==V(1250) && py::m_get(smoke,V("rematched"),V(false)).truthy();
            exit_status=output.fail() || !passed ? 4 : 0;
        } else {
            if(std::string path; env_u8("PVP_USERDATA", path)) {
                backup_native_save72(u8p(path));
#ifdef _WIN32
                {   // release folder only (the EXE beside its SHA256SUMS); dev trees have no manifest
                    wchar_t buf[MAX_PATH]; DWORD n = GetModuleFileNameW(nullptr, buf, MAX_PATH);
                    release_upgrade_check(std::filesystem::path(std::wstring(buf, n)).parent_path(), path);
                }
                if(default_pc_userdata) {
                    std::filesystem::create_directories(u8p(path));
                    V sources=V::list();
                    if(std::string appdata; env_u8("APPDATA", appdata))for(const char* folder:{"PVZ-Rouge-PvP67","PVZ-Rouge-PvP66","PVZ-Rouge-PvP"})
                        sources.append(V(p8(u8p(appdata)/folder/"pvp_userdata")));
                    sources.append(V(p8(std::filesystem::current_path()/"pvp_userdata")));
                    pm_userdata::f_migrate(Args{V(path),sources});
                    backup_native_save72(u8p(path));
                }
#endif
            }
            pm_app::f_run(Args{});
        }
    } catch (PyError& e) {
        report_fatal(std::string("PyError ") + e.what(),!diagnostic_mode);
        return 2;
    } catch (std::exception& e) {
        report_fatal(std::string("error ") + e.what(),!diagnostic_mode);
        return 3;
    }
    // network / AI threads may still be parked on the GIL: skip static destruction
    fflush(nullptr);
    _exit(exit_status);
}
