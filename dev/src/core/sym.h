// Interned strings. The original game identifies everything (units, blocks,
// secrets) by Chinese strings; a Sym compares as an integer.
#pragma once
#include <cstdint>
#include <string>
#include <string_view>
#include <functional>

namespace pvz {

struct Sym {
    uint32_t id = 0;          // 0 == "" (empty string)
    Sym() = default;
    explicit Sym(uint32_t i) : id(i) {}
    Sym(std::string_view s);  // interns
    Sym(const char* s) : Sym(std::string_view(s)) {}
    Sym(const std::string& s) : Sym(std::string_view(s)) {}
    const std::string& str() const;
    const char* c_str() const { return str().c_str(); }
    bool empty() const { return id == 0; }
    bool operator==(Sym o) const { return id == o.id; }
    bool operator!=(Sym o) const { return id != o.id; }
    bool operator<(Sym o) const { return id < o.id; }
};

size_t sym_count();

}  // namespace pvz

template <> struct std::hash<pvz::Sym> {
    size_t operator()(pvz::Sym s) const noexcept { return s.id; }
};

// Cached literal symbol: SY("飞贼僵尸") interns once per call site.
#define SY(lit) ([]() -> ::pvz::Sym { static const ::pvz::Sym s_(lit); return s_; }())
