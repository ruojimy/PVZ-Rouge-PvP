#pragma once
#include <span>
#include <string>
namespace pvz::typed72 {
double ai_human_residual(const std::string& card);
double ai_human_feature(std::span<const std::string> deck);
// Actual r22 retains the r19 tactical layer and draft67 plus this term.
constexpr double ai_r22_meta67_weight=10.;
}
