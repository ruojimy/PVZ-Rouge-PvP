"""Guard the reviewed 74.4 feedback source/generated-method merge.

The 20261117 merge used pvp2cpp output before/after the owned Python changes,
then git merge-file to preserve native direct calls and seat_view adaptations.
Do not replace complete Application/Room modules with raw translator output.
--record is only for an explicitly reviewed generation/merge; builds use --check.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'tools/pvp744_feedback_sources.json'
SOURCES=['app','room','pve_ui','replay_ui','pve','battle_view','world_view','team_hud','coop_progress','result_outro']
METHODS={
 'src/ui/gen/pm_result_outro.cpp':['C_ResultOutro::m_start'],
 'src/ui/gen/pm_app.cpp':['C_Application::m_action','C_Application::m_pve_action','C_Application::m_pve_apply_guest_result','C_Application::m_draw_pve_result','C_Application::m_pve_push_deck','C_Application::m_draw_pve_shop'],
 'src/ui/gen/pm_room.cpp':['C_Room::m__command','C_Room::m_setup_changed','C_Room::m_set_pve'],
 'src/ui/gen/pm_pve_ui.cpp':['C_PveUI::m_pve_action','C_PveUI::m_pve_apply_guest_result','C_PveUI::m_draw_pve_result','C_PveUI::m_pve_push_deck','C_PveUI::m_draw_pve_shop'],
 'src/ui/gen/pm_replay_ui.cpp':['C_ReplayUI::m_replay_library','C_ReplayUI::m_replay_action','C_ReplayUI::m_render_replays'],
 'src/sim/pvp/gen/pm_pve.cpp':['f_map_for_day','f_describe_day','C_Campaign::m__credit_pickups','C_Campaign::m_win','C_Campaign::m_lose'],
 'src/sim/pvp/gen/pm_coop_progress.cpp':['C_CoopProgress::m_finish','C_CoopProgress::m_action'],
 'src/ui/gen/pm_battle_view.cpp':['f_draw_touch'],
 'src/ui/gen/pm_world_view.cpp':['C_WorldView::m_render'],
 'src/ui/gen/pm_team_hud.cpp':['f_draw_team_panel'],
}
def records():
 out={}
 for name in SOURCES:
  rel='tools/pvp72_sources/'+name+'.py';out[rel]=hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
 for rel,methods in METHODS.items():
  text=(ROOT/rel).read_text('utf8')
  for method in methods:
   found=re.search(r'^V '+re.escape(method)+r'\(const Args& A\) \{.*?^\}',text,re.S|re.M)
   if not found:raise RuntimeError('Missing reviewed method: '+method)
   if 'PVZ_TODO(' in found.group():raise RuntimeError('Untranslated code in reviewed method: '+method)
   out[rel+'::'+method]=hashlib.sha256(found.group().encode('utf8')).hexdigest()
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--record',action='store_true');p.add_argument('--check',action='store_true');a=p.parse_args()
 value=records()
 if a.record:MANIFEST.write_text(json.dumps(value,indent=2)+'\n','utf8')
 elif not MANIFEST.exists() or value!=json.loads(MANIFEST.read_text('utf8')):raise SystemExit('Stale PvP744 feedback source/method merge; review regeneration before --record')
 print('PvP744 feedback source/method merge: '+('recorded' if a.record else 'checked'))
