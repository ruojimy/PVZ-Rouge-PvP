#pragma once
// PvP76 r2: co-op zombie secrets. Every cleared co-op day adds one zombie secret to the
// run; it is carried by the dormant zombie seat of each later co-op battle.
//   * eligible: secrets that act on zombie units (precursor-locked or naming the units
//     they change, plus 专注啃咬 / 二手 / 僵王出品); secrets about brains, Zombie Dave or
//     graves stay out, as do 一大波僵尸 and 鸦群 (no effect in co-op; user 11-22);
//   * a secret joins only when at least one of its precursors is in that day's co-op pool;
//   * the pick is deterministic: FNV-1a of "<run id>:<day>" over the eligible list.
// The schedule is a pure function of (run id, first counted day, current day), so the save
// only records where counting began: day 1 (runs saved before r2 count every cleared day).
#include "sim/pvp/pvprt.h"
#include <string>
#include <vector>
namespace pvz::pvp76r2 {
bool coop_secret_allowed(const std::string& key);
bool precursor_in_pool(const std::string& key,int64_t day);
// Secrets owned when playing `day`: one per cleared day in [from_day, day).
V coop_zombie_secrets(const V& run_id,const V& from_day,const V& day);
const std::vector<std::string>& coop_secret_keys();
// Room text: "僵尸秘籍（n）：A、B…" from pve["coop_zombie_secrets"] (absent: none yet).
V coop_secret_line(const V& pve);
// Room._start_pve: the dormant zombie seat's deck for a co-op day.
V coop_battle_secrets(const V& pve);
}
