#pragma once
#include <filesystem>
namespace pvz {
std::filesystem::path native_executable_directory();
std::filesystem::path native_workspace();
std::filesystem::path native_image_directory();
}
