#include "core/resource_paths.h"
#include "core/fsutil.h"
#include "core/pyops.h"
#include <cstdlib>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#endif

namespace pvz {
std::filesystem::path native_executable_directory() {
#ifdef _WIN32
    std::vector<wchar_t> path(32768);
    DWORD length = GetModuleFileNameW(nullptr, path.data(), DWORD(path.size()));
    if (length && length < path.size()) return std::filesystem::path(std::wstring(path.data(), length)).parent_path();
#else
    std::error_code error;
    auto path = std::filesystem::read_symlink("/proc/self/exe", error);
    if (!error) return path.parent_path();
#endif
    return std::filesystem::current_path();
}
std::filesystem::path native_workspace() {
    if (const char* fixture = std::getenv("PVZ_TEST_ROOT")) {
        auto path = u8p(fixture);
        if (!std::filesystem::is_directory(path)) throw PyError("FileNotFoundError", "Native test fixture root is unavailable");
        return path;
    }
    auto current = std::filesystem::current_path(), executable = native_executable_directory();
    for (auto& path : std::vector<std::filesystem::path>{current, executable, executable.parent_path(), executable.parent_path().parent_path()})
        if (std::filesystem::is_directory(path / "extract" / "data")) return path;
    throw PyError("FileNotFoundError", "Native game data directory is unavailable");
}
std::filesystem::path native_image_directory() {
    auto root = native_workspace(), executable = native_executable_directory();
    auto images = u8p("图片");
    for (auto& path : std::vector<std::filesystem::path>{root / images, root / "PVZ-Rouge-v1.4.8" / images,
             executable / images, root / "build" / "Release" / images})
        if (std::filesystem::is_directory(path)) return path;
    throw PyError("FileNotFoundError", "Native image directory is unavailable");
}
}
