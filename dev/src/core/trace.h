#pragma once
#include <cstdio>
namespace pvz {
void install_crash_handler();
// Opt-in first-chance C++ throw capture. No stack-walk cost in normal play.
// Set PVP_CAPTURE_CPP_TRACE=1 before process startup, then print on a failure.
void print_last_cpp_throw(FILE*) noexcept;
void release_crash_reserve() noexcept;
}
