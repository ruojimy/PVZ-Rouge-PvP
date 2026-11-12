#pragma once
#include <cstdint>
#include <stdexcept>
#include <utility>
namespace pvz::typed72 {
// Missing, None, zero and false have different source semantics.
template<class T> class Field {
public:
    enum class Presence : uint8_t { missing, null, value };
    Field() = default;
    explicit Field(T value) : presence_(Presence::value), value_(std::move(value)) {}
    bool present() const noexcept { return presence_ != Presence::missing; }
    bool is_null() const noexcept { return presence_ == Presence::null; }
    void erase() { presence_ = Presence::missing; value_ = T{}; }
    void set_null() { presence_ = Presence::null; value_ = T{}; }
    void set(T value) { value_ = std::move(value); presence_ = Presence::value; }
    const T& get() const { require(); return value_; }
    T& get() { require(); return value_; }
    T or_missing(T fallback) const { return present() ? get() : std::move(fallback); }
private:
    void require() const {
        if (presence_ != Presence::value)
            throw std::logic_error(presence_ == Presence::missing ? "missing typed field" : "None typed field");
    }
    Presence presence_ = Presence::missing;
    T value_{};
};
} // namespace pvz::typed72
