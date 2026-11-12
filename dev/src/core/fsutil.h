// UTF-8 <-> filesystem path helpers (C++20 u8string is char8_t). On POSIX (Android) paths are UTF-8
// byte strings already, and NDK 25's libc++ has no char8_t path constructor.
#pragma once
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <string>

namespace pvz {
#ifdef _WIN32
inline std::filesystem::path u8p(const std::string& s) {
    return std::filesystem::path(reinterpret_cast<const char8_t*>(s.c_str()));
}
inline std::string p8(const std::filesystem::path& p) {
    auto u = p.u8string();
    return std::string(reinterpret_cast<const char*>(u.c_str()), u.size());
}
#else
inline std::filesystem::path u8p(const std::string& s) { return std::filesystem::path(s); }
inline std::string p8(const std::filesystem::path& p) { return p.string(); }
#endif

// Environment variables as UTF-8 (variable names are ASCII). On Windows std::getenv returns
// ANSI-code-page bytes (GBK on Chinese systems): not UTF-8, and lossy for characters outside
// the code page. A user folder such as "C:\Users\Admin（无密码）" therefore made u8p() fail
// with winerror 1113 at startup. Use the CRT wide environment instead.
inline bool env_u8(const char* name, std::string& out) {
#ifdef _WIN32
    std::wstring key(name, name + std::strlen(name));
    const wchar_t* value = _wgetenv(key.c_str());
    if (!value) return false;
    out = p8(std::filesystem::path(value));
    return true;
#else
    const char* value = std::getenv(name);
    if (!value) return false;
    out = value;
    return true;
#endif
}
// Sets both the CRT and the process environment (child processes, GetEnvironmentVariableW).
inline bool env_set_u8(const char* name, const std::string& value) {
#ifdef _WIN32
    std::wstring key(name, name + std::strlen(name));
    return _wputenv_s(key.c_str(), u8p(value).wstring().c_str()) == 0;
#else
    return setenv(name, value.c_str(), 1) == 0;
#endif
}
}  // namespace pvz
