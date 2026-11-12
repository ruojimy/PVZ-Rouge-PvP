#include <bit>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include "nlohmann/json.hpp"
int main(int argc, char** argv) {
    if (argc != 3) return 2;
    std::ifstream input(argv[1]);
    std::ofstream output(argv[2]);
    if (!input || !output) return 3;
    for (std::string line; std::getline(input, line);) {
        const auto value = nlohmann::json::parse(line);
        const auto x = std::bit_cast<double>(std::stoull(value.at(0).get<std::string>()));
        const auto y = std::bit_cast<double>(std::stoull(value.at(1).get<std::string>()));
        output << std::bit_cast<uint64_t>(std::hypot(x,y)) << '\n';
    }
    return input.bad() || !output ? 4 : 0;
}
