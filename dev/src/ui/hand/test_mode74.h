#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz::test74 {
bool action(const V& app,const V& command);
bool event(const V& app,const V& event);
bool draw(const V& app);
void overlay(const V& app);
bool sync_text_input(const V& app);
V original_asset(const std::string& key);
bool icon(const V& screen,const std::string& name,const V& rect,bool flip);
void catalog();
V replay_rules(const V& rules);
void register_sounds(const V& files);
V boss_camera(const V& camera,const V& battle,const V& settings,bool replay,const V& hero);
}
