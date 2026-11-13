#pragma once
#include "sim/pvp/pvprt.h"
#include <nlohmann/json.hpp>
#include <filesystem>
namespace pvz::texture74 {
struct DisplayScope {bool previous;DisplayScope();~DisplayScope();};
struct OriginalScope {bool previous;OriginalScope();~OriginalScope();};
// Cosmetic only: no simulation atlas, collision, RNG or replay hash is modified.
void initialize(const V& app);
bool action(const V& app,const V& command);
bool event(const V& app,const V& event);
bool draw(const V& app);
void overlay(const V& app);
void persist_editor(const V& app);
bool sync_text_input(const V& app);
void update(const V& app,double dt);
void close_connection(const V& app);
bool receive(const V& app,const V& peer,const V& payload);
V artwork(const std::string& name);
bool icon(const V& screen,const std::string& name,const V& rect,bool flip);
void sync_art(const V& art);
void sync_renderer(const V& renderer);
bool active();
uint64_t revision();
void register_hooks();
// Production operations also exposed to the integration verifier.
nlohmann::json inventory();
nlohmann::json validate_pack(const nlohmann::json& doc);
std::string pack_digest(const nlohmann::json& doc);
void import_pack(const std::filesystem::path& file);
void export_pack(const std::filesystem::path& file);
nlohmann::json diagnostics();
}
