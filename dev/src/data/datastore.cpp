#include "data/datastore.h"
#include <fstream>
#include <map>
#include <mutex>
#include <stdexcept>
#include <filesystem>
#include "core/fsutil.h"

namespace pvz::data {
namespace {
std::string g_dir = "data";
std::map<std::string, json> g_cache;
std::mutex g_mu;
}

void set_data_dir(const std::string& dir) { g_dir = dir; }
const std::string& data_dir() { return g_dir; }

const json& module(const std::string& name) {
    std::lock_guard<std::mutex> lock(g_mu);
    auto it = g_cache.find(name);
    if (it != g_cache.end()) return it->second;
    std::filesystem::path p = u8p(g_dir) / u8p(name + ".json");
    std::ifstream f(p, std::ios::binary);
    if (!f) throw std::runtime_error("data file missing: " + p8(p));
    json j = json::parse(f);
    return g_cache.emplace(name, std::move(j)).first->second;
}

const json& get(const std::string& module_name, const std::string& key) {
    const json& m = module(module_name);
    auto it = m.find(key);
    if (it == m.end()) throw std::runtime_error("data key missing: " + module_name + "." + key);
    return *it;
}

}  // namespace pvz::data
