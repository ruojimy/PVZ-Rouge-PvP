#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz::solo77 {
bool action(const V& app,const V& action);
bool draw(const V& app);
bool result(const V& app,const V& result);
V seat_rally(const V& app,const V& view);
V shop_rect(const V& stage,const V& item,const V& x,const V& y);
bool draw_coop(const V& app,const V& renderer,const V& view);
void init_coop(const V& app);
V coop_command(const V& room,const V& peer,const V& payload);
void result_receipt(const V& room,const V& result);
void start_coop_attempt(const V& room);
void settle_coop(const V& room,const V& result);
V coop_ready(const V& room,const V& peer);
V classic_seed(const V& room,const V& campaign,const V& day);
V classic_map(const V& app,const V& day,const V& coop);
bool adventure_rain(const V& campaign);
V adventure_map(const V& campaign);
void configure_adventure(const V& room,const V& campaign);
void difficulty_buttons(const V& app,const V& renderer,const V& stage,const V& x,const V& y,const V& width,const V& font);
void observe_result(const V& app,const V& view);
void profile_button(const V& app);
void pool_button(const V& renderer);
}
