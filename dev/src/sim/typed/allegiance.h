#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string_view>
namespace pvz::typed72 {
enum class Seat : uint8_t { plant, zombie, plant2, zombie2 };
constexpr size_t seat_index(Seat s) { return static_cast<size_t>(s); }
constexpr Seat team_of(Seat s) { return s == Seat::plant || s == Seat::plant2 ? Seat::plant : Seat::zombie; }
std::string_view seat_name(Seat);
Seat parse_seat(std::string_view);
std::optional<Seat> known_seat(std::string_view);
} // namespace pvz::typed72
