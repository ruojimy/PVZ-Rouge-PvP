// Read-only game data exported from PvP71 (tools/export_data.py -> data/*.json).
#pragma once
#include <nlohmann/json.hpp>
#include <string>

namespace pvz::data {

using json = nlohmann::json;

// Directory containing the exported *.json (default "data", override before first use).
void set_data_dir(const std::string& dir);
const std::string& data_dir();

// data/<module>.json, loaded once and cached; throws if missing.
const json& module(const std::string& name);

// Convenience: module(name)[key]
const json& get(const std::string& module_name, const std::string& key);

}  // namespace pvz::data
