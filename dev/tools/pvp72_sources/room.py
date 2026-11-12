"""Authoritative room state machine. Transport identities are bound to factions here."""
import random
import time
import uuid
from copy import deepcopy
from . import cppcore as _cppcore
deepcopy = _cppcore.fast_deepcopy(deepcopy)
from .catalog import CARDS, RULES, PROTECTED, BASIC_GRAVES, allowed, validate_deck, map_card_error, digest, starter_grave, STARTER_GRAVE_ERROR, starting_resource, team_repeatable
from .maps import build_snapshot, MapSnapshot
from .native_battle import NativeBattle
from .audit_log import AuditLog,AuditLogError,write_json_array
from .pvp61_ranked import apply_options
from .teams import DUEL, MODES, MODE_LABELS, seats_for, scripted, team_of
from .adaptive_pacing import AdaptivePacing


def options_label(ranked,extra_slot):
    return ('计入胜率' if ranked else '不计胜率')+' · '+('8卡槽' if extra_slot else '7卡槽')

SECRET_PRODUCER_ERROR = "有前体的秘籍须同时保留前体植物和至少一种生产植物的卡槽"


class Room:
    def __init__(self,bridge,rules=None):
        self.bridge=bridge;self.rules=deepcopy(rules or RULES);self.members={"host":"plant"}
        self.connected={"host":True};self.revision=1;self.phase="config";self.clock=0.
        self.map_id="家院";self.seed=1;self.map=build_snapshot(bridge,self.map_id,self.seed)
        self.bans=[];self.decks={"plant":[],"zombie":[]};self.ready={"plant":False,"zombie":False}
        self.confirmed={"plant":False,"zombie":False};self.ban_schedule=[];self.ban_index=0
        self.draft_schedule=[];self.draft_index=0;self.draft_history=[];self.draft_stage=""
        self.deadline=0.;self.battle=None;self.result=None;self.accumulator=0.;self.status="等待对方加入并确认地图"
        self.pacing=AdaptivePacing();self._paced_battle=None
        self.copy_targets={}   # PvP73: seat -> 模仿者 target picked by that player (display hint)
        self.disconnect_deadline=None;self.rematch_votes={};self.pause_votes=set();self.paused=False;self.pause_epoch=0
        self.restart_votes=set()
        self.log=AuditLog();self.match_number=0;self.last_terrain_revision=-1
        self.loaded={"plant":False,"zombie":False}
        self.loading_id=None;self._audit_error=""
        self._draft_map_hash=None;self._draft_map_errors={}
        self.recording=None;self.replay_enabled=False;self.on_replay=None
        self.allow_spectators=True;self.spectators={};self.max_spectators=4
        # Explicit host-invited local controllers do not own a network pipe.
        # Fixed neutral-identity rooms leave this set empty.
        self.ai_peers=set()
        # Every AI peer, fixed rooms included (host-only; never published).
        # Co-op battles pay these seats the AI sun subsidy.
        self.subsidy_peers=set()
        self.player_profiles={};self.match_id=None;self.match_members={}
        self.config_requests={};self.request_serial=0;self.request_outcome=None
        self.same_deck_rematch=False
        self.match_ranked=False
        # PvP66 modes. PvE days come from the host's campaign (set_pve).
        self.mode=DUEL;self.pve=None;self.on_pve_result=None
        from .coop_progress import CoopProgress
        self.coop_progress=CoopProgress()
        from .team_chat import TeamChat
        self.team_chat=TeamChat()

    def set_player_profile(self,peer_id,value):
        if not self.peer_connected(peer_id):return False
        from .player_profile import public_profile
        self.player_profiles[peer_id]=public_profile(value)
        return True

    @property
    def audit_error(self):return self._audit_error or self.log.error or (self.battle.audit_error if self.battle else "")

    def _halt_for_audit(self,error):
        if self._audit_error==str(error) and self.paused:return self._audit_error
        self._audit_error=str(error);self.paused=True;self.accumulator=0.
        self.status=self._audit_error;self.revision+=1
        if self.battle:
            for side in self.seat_list():self.battle.clear_input(side)
        return self._audit_error

    def close(self):
        try:
            self._save_replay()
            if self.battle:self.battle.close()
        finally:self.log.close()

    def _save_replay(self):
        if self.recording is not None and self.on_replay:self.on_replay(self)

    def _record(self,event,**details):
        try:self.log.append(dict(event=event,clock=round(self.clock,3),revision=self.revision,**details))
        except AuditLogError as exc:return self._halt_for_audit(exc)
        return ""

    def side_for(self,peer_id):return self.members.get(peer_id)

    def peer_connected(self,peer_id):
        return bool(self.connected.get(peer_id) or self.spectators.get(peer_id))

    def snapshot_peers(self):
        return [peer for peer in self.members if peer!="host" and peer not in self.ai_peers and self.connected.get(peer)]+[p for p in self.spectators if p!='host']

    def role_change_error(self,peer_id,role,side=None):
        if role not in ('player','spectator'):return "身份设置无效"
        if not self.peer_connected(peer_id):return "玩家未连接"
        if self.phase not in ('config','result'):return "请在房间准备阶段或对局结束后切换身份"
        watching=peer_id in self.spectators
        if role=='spectator':
            if watching:return ""
            if peer_id!='host' and not self.allow_spectators:return "房主已关闭观战"
            if peer_id!='host' and sum(p!='host' for p in self.spectators)>=self.max_spectators:return "观战人数已满"
        else:
            if not watching:return "已经在玩家席位"
            free=[s for s in self.seat_list() if s not in self.members.values()]
            if not free:return "玩家席位已满"
            if side is not None and side not in self.seat_list():return "阵营设置无效"
            if side is not None and side not in free:return "该阵营已有玩家"
        return ""

    def change_role(self,peer_id,role,side=None):
        """Keep draft/loading/live seats fixed; change lobby/result seats only."""
        error=self.role_change_error(peer_id,role,side)
        if error:return error
        if role=='spectator' and peer_id in self.spectators:return ""
        if role=='player':side=side or next(s for s in self.seat_list() if s not in self.members.values())
        self._forget_prepared_seat(self.side_for(peer_id) if role=='spectator' else side)
        self._reset_selection()
        self.disconnect_deadline=None
        if role=='spectator':
            self.members.pop(peer_id,None);self.connected.pop(peer_id,None)
            self.spectators[peer_id]=True
        else:
            self.spectators.pop(peer_id,None)
            self.members[peer_id]=side;self.connected[peer_id]=True
        self.coop_progress.sync(self)
        self.status="席位已变更，请双方重新确认地图"
        return self._record('role_changed',peer=peer_id,role=role,side=side if role=='player' else None)

    def connect_spectator(self,peer_id):
        # Spectator admission must never touch player slots, pause state,
        # reconnect deadlines, draft revisions or the battle audit stream.
        if not self.allow_spectators:return "房主已关闭观战"
        if peer_id in self.members:return "身份已占用"
        if peer_id not in self.spectators and sum(p!='host' for p in self.spectators)>=self.max_spectators:return "观战人数已满"
        self.spectators[peer_id]=True
        return ""

    def connect(self,peer_id="guest",spectator=False,seat=None):
        if spectator:return self.connect_spectator(peer_id)
        if peer_id in self.spectators:return "观众不能占用玩家席位"
        if self.audit_error:return self._halt_for_audit(self.audit_error)
        if peer_id=="host":return "身份已占用"
        if peer_id in self.members:
            self.connected[peer_id]=True
            if all(self.connected.values()):self.disconnect_deadline=None
            self.status="对方已重连";return self._record("reconnected",peer=peer_id)
        if len(self.members)>=len(self.seat_list()):return "房间已满"
        if self.phase not in ('config','result'):return "对局中不能加入玩家席位"
        if seat is not None and seat not in self.seat_list():return "席位设置无效"
        if seat is not None and seat in self.members.values():return "该席位已有玩家"
        if self.phase=="result":
            # A settled/aborted match belongs to the previous opponent; a new
            # joiner gets a fresh setup instead of landing on a dead result.
            self._reset_selection()
        seat=seat or next(s for s in self.seat_list() if s not in self.members.values())
        self._forget_prepared_seat(seat)
        self.members[peer_id]=seat
        self.connected[peer_id]=True;self.revision+=1
        self.coop_progress.sync(self)
        error=self._record("joined",peer=peer_id)
        if error:return error
        self.status="双方确认地图后开始禁选";return ""

    def _forget_prepared_seat(self,seat):
        """A genuinely new occupant must select/confirm its own preparation.

        Temporary live disconnect/reconnect does not call this; its identity
        and locked day deck remain intact.
        """
        if seat is None:return
        self.confirmed={s:False for s in self.seat_list()}
        self.ready={s:False for s in self.seat_list()}
        if scripted(self.mode) and self.pve:
            self.pve.setdefault('decks',{}).pop(seat,None)

    def _release_peer(self,peer_id,status):
        """Drop a departed opponent from the roster so the room can refill.

        The settled result and battle object stay for the result screen and the
        audit log; only the membership slot is freed.
        """
        self._forget_prepared_seat(self.side_for(peer_id))
        self.members.pop(peer_id,None)
        self.coop_progress.drop(peer_id)
        self.coop_progress.sync(self)
        self.ai_peers.discard(peer_id)
        self.subsidy_peers.discard(peer_id)
        self.config_requests.pop(peer_id,None)
        self.connected.pop(peer_id,None)
        self.rematch_votes={};self.pause_votes=set();self.paused=False
        self.restart_votes=set()
        self.disconnect_deadline=self.disconnect_deadline if any(not self.connected.get(p) for p in self.members) else None
        self.status=status
        self.revision+=1

    def disconnect(self,peer_id):
        if peer_id in self.spectators:
            self.spectators.pop(peer_id,None);self.coop_progress.drop(peer_id);return
        if peer_id not in self.members:return
        self.connected[peer_id]=False
        if self.audit_error:return self._halt_for_audit(self.audit_error)
        if self.battle:self.battle.clear_input(self.side_for(peer_id))
        # An accepted surrender or resolved hero death is terminal even when
        # its peer closes before the next render/update promotes the result.
        self._capture_battle_result()
        if self.result is not None:
            self._record("disconnected_after_result",peer=peer_id)
            if peer_id!="host":
                self._release_peer(peer_id,"对方已离开，已确定的对局结果保留；可邀请新玩家加入")
            else:
                self.disconnect_deadline=None;self.status="对方已离开，已确定的对局结果保留"
                self.revision+=1
            return
        if self.phase=="config" and peer_id!="host":
            # Nothing is locked in the lobby: a quit and a network drop deserve
            # the same handling there, so free the slot at once.
            self._record("left",peer=peer_id)
            self._reset_selection()
            self._release_peer(peer_id,"对方已离开房间；可邀请新玩家加入")
            return
        self.disconnect_deadline=self.clock+20.
        self.status="对方断线，等待重连（20 秒）"
        self._record("disconnected",peer=peer_id)

    def leave(self,peer_id):
        """Explicit departure message: free the slot immediately, in any phase."""
        if peer_id in self.spectators:
            self.spectators.pop(peer_id,None);self.coop_progress.drop(peer_id);return
        if peer_id not in self.members or peer_id=="host":return
        if self.audit_error:return self._halt_for_audit(self.audit_error)
        self.connected[peer_id]=False
        self._capture_battle_result()
        if self.result is None and self.phase=="battle":
            # 对局中直接退出（关游戏 / 离开）= 退出方判负，另一方获胜。
            self._forfeit(peer_id,"leave")
        elif self.result is None and self.phase=="loading":
            self.result=dict(winner=None,reason="leave",tick=self.battle.tick if self.battle else 0)
            self.phase="result";self._record("interrupted",reason="leave")
        self._record("left",peer=peer_id)
        if self.phase in ('config','banning','picking'):
            self._reset_selection()
        forfeited=isinstance(self.result,dict) and self.result.get("forfeit")==self.side_for(peer_id)
        self._release_peer(peer_id,"对方退出对局，判对方负；可邀请新玩家加入" if forfeited
                           else "对方已离开房间；可邀请新玩家加入")

    def kick(self,peer_id):
        """Host-initiated removal; the caller notifies the peer over the wire."""
        if peer_id in self.spectators:
            self.spectators.pop(peer_id,None);self.coop_progress.drop(peer_id);return
        if peer_id not in self.members or peer_id=="host":return
        if self.audit_error:return self._halt_for_audit(self.audit_error)
        self.connected[peer_id]=False
        self._capture_battle_result()
        if self.result is None and self.phase in ("loading","battle"):
            self.result=dict(winner=None,reason="kick",tick=self.battle.tick if self.battle else 0)
            self.phase="result";self._record("interrupted",reason="kick")
        self._record("kicked",peer=peer_id)
        self._release_peer(peer_id,"已请出对方；可邀请新玩家加入")

    def reopen(self):
        """Host returns a finished room to the lobby once the opponent is gone."""
        if self.phase!="result":return "对局尚未结束"
        if len(self.members)>=len(self.seat_list()):return "对方仍在房间中"
        self._reset_selection()
        self.status="等待对方加入并确认地图"
        return ""

    def _forfeit(self,peer_id,reason):
        """The departing peer's side loses a live battle; the remaining side wins."""
        side=self.side_for(peer_id)
        if side not in self.seat_list():return
        side=team_of(side)
        winner="zombie" if side=="plant" else "plant"
        self.result=dict(winner=winner,reason=reason,tick=self.battle.tick if self.battle else 0,forfeit=side)
        self.phase="result";self.status="对方退出对局，判负";self.disconnect_deadline=None
        self.paused=False;self.pause_votes=set();self.revision+=1
        self._record("forfeit",reason=reason,peer=peer_id,side=side,result=self.result)
        self._save_replay()

    def host_quit(self):
        """The host closes the game mid-battle: the host's side forfeits."""
        if self.audit_error:return
        self._capture_battle_result()
        if self.result is None and self.phase=="battle":
            if self.side_for('host'):self._forfeit("host","leave")
            else:
                self.result=dict(winner=None,reason='host_closed',tick=self.battle.tick if self.battle else 0)
                self.phase='result';self.status='房主关闭房间，对局中止';self.revision+=1
                self._record('interrupted',reason='host_closed');self._save_replay()

    def _capture_battle_result(self):
        if self.audit_error:return
        if self.result is not None or not self.battle or not self.battle.result:return
        self.result=deepcopy(self.battle.result);self.phase="result";self.revision+=1
        if scripted(self.mode) and self.pve:
            self.result["pve_day"]=self.pve["day"]
            self.coop_progress.finish(self,self.result)
            if self.on_pve_result:self.on_pve_result(self.result)
        self.status="对局结束";self.disconnect_deadline=None
        self._record("result",result=self.result)
        self._save_replay()

    def _reset_selection(self):
        self._save_replay()
        if self.battle:self.battle.close()
        self.recording=None
        self.bans=[];self.decks={s:[] for s in self.deck_keys()};self.ready={s:False for s in self.seat_list()}
        self.confirmed={s:False for s in self.seat_list()};self.ban_schedule=[];self.ban_index=0
        self.draft_schedule=[];self.draft_index=0;self.draft_history=[];self.draft_stage=""
        self.phase="config";self.deadline=0.;self.battle=None;self.result=None;self.accumulator=0.
        self.rematch_votes={};self.pause_votes=set();self.paused=False;self.restart_votes=set();self.revision+=1
        self.loaded={s:False for s in self.seat_list()}
        self.loading_id=None
        self.config_requests={};self.same_deck_rematch=False
        self.match_id=None;self.match_members={}

    def _start_bans(self):
        self.config_requests={}
        # The source's optional seven-packet bank includes an auto economy card.
        # PvP uses seven manual picks and starts its second bans after four picks.
        self.draft_schedule=[];self.draft_index=0;self.draft_history=[]
        for stage,count in (("opening_ban",self.rules["opening_unit_bans"]),
                            ("opening_pick",self.rules["opening_picks"]),
                            ("second_ban",self.rules["second_unit_bans"]),
                            ("final_pick",max(self.rules["plant_slots"],self.rules["zombie_slots"])-self.rules["opening_picks"])):
            for index in range(count):
                if stage.endswith("ban"):
                    # PvP66 (user-confirmed order, 10-14): the plant side bans a
                    # zombie unit/grave then a zombie secret; the zombie side
                    # bans a plant unit/tool then a plant secret; twice per
                    # round. In 2v2 each seat takes one unit+secret pair per
                    # round, in turn: plant, zombie, plant2, zombie2.
                    suffix="2" if self.duo() and index%2 else ""
                    for side,foe in (("plant","zombie"),("zombie","plant")):
                        pair=[dict(stage=stage,side=side,kind="ban",category=foe),
                              dict(stage=stage,side=side,kind="ban",category="secret",target=foe)]
                        if self.duo():
                            for action in pair:action["seat"]=side+suffix
                        self.draft_schedule.extend(pair)
                else:
                    order=("zombie","plant","zombie2","plant2") if self.duo() else ("zombie","plant")
                    for seat in order:
                        side=team_of(seat)
                        pick_index=index+(self.rules["opening_picks"] if stage=="final_pick" else 0)
                        if pick_index<self.rules[side+"_slots"]:
                            action=dict(stage=stage,side=side,kind="pick",category=side)
                            if self.duo():action["seat"]=seat
                            self.draft_schedule.append(action)
        # Compatibility for callers inspecting the bans, never a second cursor.
        self.ban_schedule=[(a["side"],a["category"]) for a in self.draft_schedule if a["kind"]=="ban"]
        self.ban_index=0;self._set_draft_turn()

    def _draft_action(self):
        if self.draft_index<len(self.draft_schedule):return self.draft_schedule[self.draft_index]
        return None

    def _set_draft_turn(self):
        action=self._draft_action();self.revision+=1
        if action is None:
            self.phase="picking";self.draft_stage="complete"
            self.deadline=self.clock+self.rules["ready_seconds"]
            self.status="双方%d槽阵容已锁定，请准备进入战场"%self.rules["plant_slots"];return
        self.draft_stage=action["stage"]
        self.phase="banning" if action["kind"]=="ban" else "picking"
        self.deadline=self.clock+self.rules["ban_seconds" if action["kind"]=="ban" else "pick_seconds"]
        name="僵尸方" if action["side"]=="zombie" else "植物方"
        self.status=name+("禁用一个"+("僵尸" if action.get("target")=="zombie" else "植物")+"秘籍，也可跳过" if action["category"]=="secret" else
                         "禁用一个对方单位" if action["kind"]=="ban" else "选择并锁定一张卡")

    def _completion_error(self,side,deck,bans=None):
        """Check a partial draft can still reach a valid full deck, before commit."""
        bans=self.bans if bans is None else bans;limit=self.rules[side+"_slots"]
        if len(deck)>limit:return "卡槽已满，秘籍同样占一个槽"
        required=set(deck);pending=list(deck)
        while pending:
            key=pending.pop();card=CARDS.get(key)
            if not card or card["side"]!=side or not allowed(key,bans):return "已选卡或秘籍依赖不可用"
            error=self._deck_map_error(key,deck)
            if error:return error
            dependency=card.get("dependency")
            if dependency and dependency not in required:required.add(dependency);pending.append(dependency)
        if len(required)>limit:return "必须为已选秘籍保留前体"+("僵尸" if side=="zombie" else "植物")+"卡槽"
        available={k for k,c in CARDS.items() if c["side"]==side and allowed(k,bans) and not self._deck_map_error(k,deck)}
        # Reserve economy alongside the entire prerequisite closure. Checking
        # each independently lets the same last slot promise both cards.
        # A producing precursor already satisfies this and consumes one slot.
        needs_producer = side=="plant" and self.map.environment.get("night",False) and any(CARDS[k]["category"]=="secret"
                                               and CARDS[k].get("dependency") for k in required)
        if needs_producer and not any(CARDS[k].get("producer") for k in required):
            producers=[k for k in available if CARDS[k].get("producer")]
            if not producers:return "该秘籍需要生产植物，但禁选后已无可用生产植物"
            if len(required)>=limit:return SECRET_PRODUCER_ERROR
        zombie_start = starting_resource("zombie", self.rules, self.map)
        if side=="zombie" and not any(starter_grave(k,zombie_start) for k in required):
            graves=[k for k in available if starter_grave(k,zombie_start)]
            if not graves or len(required)>=limit:return STARTER_GRAVE_ERROR
        # A dependency must itself be available; count only cards reachable from
        # dependency-free roots, so banned dependencies cannot inflate capacity.
        reachable={k for k in available if not CARDS[k].get("dependency")}
        while True:
            added={k for k in available-reachable if CARDS[k].get("dependency") in reachable}
            if not added:break
            reachable.update(added)
        if not required.issubset(reachable) or len(reachable)<limit:return "剩余可用卡牌无法完成合法阵容"
        return ""

    def _map_error(self,key):
        carried=[k for seat,deck in self.decks.items() if team_of(seat)=='plant' for k in deck]
        return self._deck_map_error(key,carried)

    def _deck_map_error(self,key,deck):
        # Draft terrain is immutable. Do not serialize the native water map for
        # every candidate of every future-deck check; reset on actual map hash.
        # A deck only changes the answer through a carried 水盆 (PvP70).
        if self._draft_map_hash!=self.map.terrain_hash:
            self._draft_map_hash=self.map.terrain_hash;self._draft_map_errors={}
        basin='plant:水盆' in deck
        cache=(key,basin)
        if cache not in self._draft_map_errors:
            self._draft_map_errors[cache]=map_card_error(key,self.map,('plant:水盆',) if basin else ())
        return self._draft_map_errors[cache]

    def _ban_error(self,side,key,actor=None):
        action=self._draft_action()
        if self.phase!="banning" or not action or action["kind"]!="ban":return "当前不是禁选阶段"
        if team_of(side)!=action["side"]:return "请等待另一方禁选"
        if actor is not None and action.get("seat") and actor!=action["seat"]:
            return "请等待队友禁选（本轮由队友执行）"
        return self._ban_problem(action,key)

    def _ban_problem(self,action,key):
        side=action["side"]
        category=action["category"]
        if key is None:
            if category=="secret":return ""
            if any(not self._ban_problem(action,k) for k in CARDS):return "基础单位禁用不可主动跳过"
            return ""
        if not isinstance(key,str):return "卡牌 ID 无效"
        c=CARDS.get(key)
        if not c or not allowed(key,self.bans):return "此卡不可禁选"
        if c.get('requires_water') and self._map_error(key):return self._map_error(key)
        if key in PROTECTED:return "咖啡豆、花盆、睡莲和梯子僵尸不可禁选"
        if category=="secret":
            target=action.get("target","plant")
            if c["category"]!="secret" or c["side"]!=target:
                return "本轮仅禁"+("僵尸" if target=="zombie" else "植物")+"秘籍"
        elif c["side"]!=category or c["category"]=="secret":return "禁选类别错误"
        if category=="plant" and all(not allowed(k,self.bans+[key]) for k in ("plant:向日葵","plant:阳光菇")):
            return "向日葵和阳光菇最多禁用一个"
        if category=='zombie' and key in BASIC_GRAVES and not any(allowed(k,self.bans+[key]) for k in BASIC_GRAVES):
            return "脑光墓碑和成长脑光墓碑最多禁用一个（仅基础陆地型）"
        for target in self.deck_keys():
            error=self._seat_completion_error(target,self.decks[target],self.bans+[key])
            if error:return "不能使已选阵容失效："+error
        return ""

    def _finish_draft_action(self,side,key,automatic=False):
        action=self._draft_action()
        entry=dict(step=self.draft_index+1,stage=action["stage"],side=side,kind=action["kind"],
                   category=action["category"],card=key,skip=key is None,automatic=automatic)
        if action.get("seat"):entry["seat"]=action["seat"]
        self.draft_history.append(entry)
        error=self._record("draft_action",**entry)
        if error:return error
        if action["kind"]=="ban":self.ban_index+=1
        self.draft_index+=1;self._set_draft_turn();return ""

    def _ban(self,side,key,automatic=False,actor=None):
        error=self._ban_error(side,key,actor)
        if error:return error
        side=team_of(side)
        if key is not None:self.bans.append(key)
        return self._finish_draft_action(side,key,automatic)

    def _pick_error(self,side,key,actor=None):
        action=self._draft_action()
        if self.phase!="picking" or not action or action["kind"]!="pick":return "当前不是逐次选卡阶段"
        if team_of(side)!=action["side"]:return "请等待另一方选卡"
        seat=action.get("seat") or action["side"]
        if actor is not None and action.get("seat") and actor!=seat:
            return "请等待队友选卡（本轮由队友选择）"
        side=action["side"]
        if not isinstance(key,str):return "卡牌 ID 无效"
        card=CARDS.get(key)
        if not card or card["side"]!=side or not allowed(key,self.bans):return "卡牌不可选"
        deck=self.deck_of(seat)
        if key in deck:return "已选卡牌已锁定，不能撤回或重复选择"
        if key in self.mate_deck(seat) and not team_repeatable(key):
            return "队友已选此卡（队内只有经济植物、墓碑和花盆、咖啡豆、睡莲、梯子僵尸可重复）"
        return self._seat_completion_error(seat,deck+[key],self.bans)

    def _pick(self,side,key,automatic=False,actor=None):
        error=self._pick_error(side,key,actor)
        if error:return error
        action=self._draft_action()
        seat=action.get("seat") or action["side"]
        self.deck_of(seat).append(key)
        return self._finish_draft_action(action["side"],key,automatic)

    def _timeout_pick(self,side):
        action=self._draft_action()
        seat=(action or {}).get("seat") or side
        deck=self.deck_of(seat)
        required=[CARDS[k].get("dependency") for k in deck if CARDS[k].get("dependency") not in deck]
        candidates=required+self._default_deck(seat)+sorted(CARDS)
        return next((key for key in candidates if key and not self._pick_error(team_of(seat),key)),None)

    def advisor_view(self,seat):
        """Draft view for the advisor from one seat: its own deck under its
        faction, the enemy team's decks merged under theirs."""
        team=team_of(seat)
        foe="zombie" if team=="plant" else "plant"
        enemy=[]
        for s in self.deck_keys():
            if team_of(s)==foe:
                enemy.extend(k for k in self.decks[s] if k not in enemy)
        mate=[k for k in self.mate_deck(seat) if not team_repeatable(k)]
        return dict(map=self.map,bans=self.bans+mate,rules=self.rules,
                    decks={team:list(self.deck_of(seat)),foe:enemy})

    def _default_deck(self,side):
        from .draft_advisor import recommend
        return recommend(self.advisor_view(side),team_of(side))['deck']

    def _same_deck_error(self):
        if not self.battle or self.match_members!=self.members:return "玩家席位已变化，请重新禁选"
        if scripted(self.mode):return "闯关模式没有禁选卡组"
        for side in self.deck_keys():
            if len(self.decks[side])!=self.rules[team_of(side)+'_slots']:return "原卡组未选满，请重新禁选"
            error=self._seat_completion_error(side,self.decks[side],self.bans) or validate_deck(
                team_of(side),self.decks[side],self.bans,self.rules[team_of(side)+'_slots'],self.map,
                starting_resource('zombie',self.rules,self.map))
            if error:return "原卡组当前不可用，请重新禁选："+error
        return ""

    def _config_request(self,peer_id,payload):
        """Requests are proposals; only the authenticated host may apply one."""
        kind=payload['type']
        if self.phase!='config':return "请在房间准备阶段提出或处理设置请求"
        if kind=='resolve_config_request':
            if peer_id!='host':return "只有房主可处理设置请求"
            if type(payload.get('accept')) is not bool:return "处理方式无效"
            request=next((r for r in self.config_requests.values() if r['id']==payload.get('request_id')),None)
            if request is None:return "该请求已撤回或失效"
            requester=request['peer']
            if requester not in self.members or not self.connected.get(requester):
                self.config_requests.pop(requester,None);self.revision+=1
                return "请求玩家已离开"
            accepted=payload['accept']
            if accepted:
                error=self._command('host',dict(request['payload'],revision=self.revision))
                if error:return error
            self.config_requests.pop(requester,None)
            self.request_outcome=dict(id=request['id'],peer=requester,accepted=accepted,label=request['label'])
            self.revision+=1;self.status=('房主已同意：' if accepted else '房主已拒绝：')+request['label']
            return self._record('config_request_resolved',peer=requester,request_id=request['id'],accepted=accepted)
        if peer_id=='host' or peer_id not in self.members:return "只有客机玩家可提出设置请求"
        if kind=='cancel_config_request':
            self.config_requests.pop(peer_id,None);self.revision+=1
            self.status='已撤回房间设置请求';return ""
        proposal=payload.get('proposal')
        if not isinstance(proposal,dict):return "设置请求格式无效"
        setting=proposal.get('type')
        if setting not in ('map','swap','allow_spectators','room_options'):return "不支持的房间设置请求"
        if setting=='map':
            error,newmap,name,seed=self._map_proposal(proposal)
            if error:return error
            proposal={k:deepcopy(proposal[k]) for k in ('type','map_id','seed','custom_map','night','weather') if k in proposal}
            proposal.update(map_id=name,seed=seed,night=newmap.environment.get('night',False),weather=newmap.environment.get('weather','clear'))
            from .maps import weather_label
            label='地图 '+str(newmap.environment.get('custom_name') or name)+' · 种子 '+str(seed)+' · '+weather_label(newmap.environment)
        elif setting=='room_options':
            error=self._options_error(proposal)
            if error:return error
            proposal=dict(type=setting,ranked=proposal['ranked'],extra_slot=proposal['extra_slot'])
            label=options_label(proposal['ranked'],proposal['extra_slot'])
        elif setting=='allow_spectators':
            if type(proposal.get('enabled')) is not bool:return "观战设置无效"
            proposal=dict(type=setting,enabled=proposal['enabled']);label='允许观战：'+('开' if proposal['enabled'] else '关')
        else:proposal=dict(type='swap');label='交换双方阵营'
        self.request_serial+=1
        self.config_requests[peer_id]=dict(id=self.request_serial,peer=peer_id,payload=proposal,label=label)
        self.revision+=1;self.status='已请求'+label+'，等待房主同意'
        return self._record('config_request',peer=peer_id,request_id=self.request_serial,label=label)

    @staticmethod
    def _options_error(payload):
        if type(payload.get('ranked')) is not bool or type(payload.get('extra_slot')) is not bool:
            return "对局选项无效"
        return ""

    def _map_proposal(self,payload):
        name=payload.get('map_id');seed=payload.get('seed',1)
        def fail(message):return message,None,None,None
        if not isinstance(name,str) or type(seed) is not int or not 0<=seed<2**31:return fail('地图或种子无效')
        custom=payload.get('custom_map') or {}
        if not isinstance(custom,dict):return fail('地图格式无效')
        weather=payload.get('weather',custom.get('weather',self.map.environment.get('weather','clear')))
        night=payload.get('night',custom.get('night',self.map.environment.get('night',False)))
        if weather not in ('clear','rain'):return fail('天气设置无效')
        if type(night) is not bool:return fail('早晚设置无效')
        try:
            if 'custom_map' in payload:
                from .custom_maps import snapshot_from_document
                newmap=snapshot_from_document(payload['custom_map']);name=newmap.source;seed=newmap.seed
            elif name==self.map_id and self.map.source.startswith('custom:'):
                newmap=MapSnapshot.from_dict(self.map.to_dict());seed=newmap.seed
            else:newmap=build_snapshot(self.bridge,name,seed,weather=weather)
            data=newmap.to_dict();data.pop('terrain_hash',None)
            data['environment'].update(night=night,weather=weather)
            newmap=MapSnapshot.from_dict(data)
        except (ValueError,KeyError,RuntimeError,TypeError,AttributeError) as exc:return fail('地图不可用：'+str(exc))
        return '',newmap,name,seed

    def command(self,peer_id,payload):
        kind=payload.get('type') if isinstance(payload,dict) else None
        host_control=peer_id=='host' and kind in ('map','swap','allow_spectators','reopen','resolve_config_request','room_options','pve_population')
        if peer_id in self.spectators and kind!='role_change' and not host_control:return "观众不能操作对局"
        if self.audit_error:return self._halt_for_audit(self.audit_error)
        try:error=self._command(peer_id,payload)
        except AuditLogError as exc:return self._halt_for_audit(exc)
        return self._halt_for_audit(self.audit_error) if self.audit_error else error

    def _command(self,peer_id,payload):
        side=self.side_for(peer_id)
        if not self.peer_connected(peer_id):return "玩家未连接"
        if not isinstance(payload,dict):return "命令格式无效"
        kind=payload.get("type")
        if kind in ('request_config','cancel_config_request','resolve_config_request'):
            if payload.get('revision')!=self.revision:return "配置已变化，请使用最新房间状态"
            return self._config_request(peer_id,payload)
        if kind=='role_change':
            if payload.get('revision')!=self.revision:return "配置已变化，请使用最新房间状态"
            return self.change_role(peer_id,payload.get('role'),payload.get('side'))
        if kind=='reopen':
            if peer_id!='host':return "只有房主可返回房间"
            if payload.get('revision')!=self.revision:return "配置已变化，请使用最新房间状态"
            return self.reopen()
        if kind=="allow_spectators":
            if peer_id!="host":return "只有房主可设置观战"
            if payload.get("revision")!=self.revision:return "配置已变化，请使用最新房间状态"
            if type(payload.get("enabled")) is not bool:return "观战设置无效"
            self.allow_spectators=payload["enabled"]
            if not self.allow_spectators:self.spectators={p:True for p in self.spectators if p=='host'}
            self.revision+=1
            return ""
        if kind=='pve_population':
            if peer_id!='host':return '只有房主可设置在场僵尸上限'
            if not scripted(self.mode):return '当前不是闯关模式'
            if self.phase!='config':return '请在准备界面设置在场上限'
            if payload.get('revision')!=self.revision:return '配置已变化，请使用最新房间状态'
            from .pve import valid_zombie_limit
            limit=payload.get('max_zombies')
            if not valid_zombie_limit(limit):return '在场上限须为1到200的整数'
            if limit!=self.rules.get('pve_max_zombies',40):
                self.rules['pve_max_zombies']=limit
                if self.pve:self.pve['max_zombies']=limit
                self.confirmed={seat:False for seat in self.seat_list()}
                self.revision+=1
                self._record('pve_population',max_zombies=limit)
            return ''
        if not side and kind not in ('map','swap','room_options'):return "观众不能操作对局"
        if kind=="chat":
            # Team chat: no revision check, never part of the battle or its audit log.
            name=(self.player_profiles.get(peer_id) or {}).get("name")
            return self.team_chat.say(self.mode,peer_id,side,name,payload.get("text"))
        if kind=="copy_target":
            # PvP73: a plant player's chosen 模仿者 target is shown on every card bar
            # (肆意模仿 prices the imitater from it). Deployment still sends its own copy id.
            if self.phase!="battle":return "当前不在战斗"
            card=payload.get("card")
            if card is not None and (not isinstance(card,str) or card not in CARDS):return "模仿目标无效"
            self.copy_targets[side]=card
            return ""
        if kind=="room_mode":
            if peer_id!="host":return "只有房主可切换模式"
            if payload.get("revision")!=self.revision:return "配置已变化，请使用最新房间状态"
            return self.set_mode(payload.get("mode"))
        if kind=="loaded":
            if self.phase!="loading":return "当前不在载入阶段"
            if payload.get("loading_id")!=self.loading_id:return "载入确认属于旧对局，请重新同步"
            if payload.get("terrain_hash")!=self.map.terrain_hash:return "载入地形校验不一致"
            self.loaded[side]=True
            if all(self.loaded.values()):
                self.phase="battle";self.deadline=0.;self.accumulator=0.;self.revision+=1
                self.match_number+=1;self.status="双方载入完成，战斗开始";self.copy_targets={}
                self._record("battle",number=self.match_number,terrain_hash=self.map.terrain_hash,decks=deepcopy(self.decks))
            return ""
        if kind=="input":
            if self.phase!="battle" or not self.battle:return "当前不在战斗"
            intent=payload.get("input")
            terminal=isinstance(intent,dict) and intent.get("type") in ('surrender','surrender_accept','surrender_decline','surrender_cancel')
            if (self.paused or self.disconnect_deadline is not None) and not terminal:return "对局暂停"
            try:error=self.battle.command_input(side,payload.get("input"))
            except AuditLogError as exc:return self._halt_for_audit(exc)
            self._capture_battle_result()
            return error
        if kind=="pause":
            if self.phase!='battle':return '当前没有战斗'
            epoch=payload.get('pause_epoch',self.pause_epoch)
            if type(epoch) is not int or epoch!=self.pause_epoch:return '暂停状态已变化，请使用最新房间状态'
            desired=payload.get('paused',not self.paused)
            if type(desired) is not bool or type(payload.get('cancel',False)) is not bool:return '暂停请求无效'
            # Votes are battle controls, independent of map/config revisions.
            # Explicit desired state makes delayed confirmations idempotent.
            if payload.get('cancel'):
                if not self.paused:self.pause_votes.discard(side)
            elif desired:
                if self.paused:return ''
                self.pause_votes.add(side)
                if set(self.seat_list())<=self.pause_votes:
                    self.paused=True;self.accumulator=0.
                    for seat in self.seat_list():self.battle.clear_input(seat)
            else:
                if not self.paused:return ''
                self.paused=False;self.pause_votes=set();self.pause_epoch+=1;self.accumulator=0.
            self.status=('全体玩家已同意暂停' if self.paused else
                         '已请求暂停 %d/%d，等待其他玩家确认'%(len(self.pause_votes),len(self.seat_list())) if self.pause_votes else '对局继续')
            self.revision+=1;return ''
        if payload.get("revision")!=self.revision:return "配置已变化，请使用最新房间状态"
        if kind=="map":
            if peer_id!="host":return "只有房主可提出地图"
            if self.phase in ("loading","battle","result"):return "请在房间中修改地图"
            error,newmap,name,seed=self._map_proposal(payload)
            if error:return error
            if self.mode!=DUEL:
                from .team_maps import team_snapshot
                newmap=team_snapshot(newmap)
            self.map=newmap;self.map_id=name;self.seed=seed;self._reset_selection()
            self.status="地图已改变，需要双方重新确认";self._record("map",map=name,seed=seed);return ""
        if kind=="room_options":
            if peer_id!="host":return "只有房主可修改对局选项"
            if self.phase!="config":return "请在房间准备阶段修改对局选项"
            error=self._options_error(payload)
            if error:return error
            if (bool(self.rules.get('ranked'))==payload['ranked'] and
                    bool(self.rules.get('extra_slot'))==payload['extra_slot']):return ""
            apply_options(self.rules,payload['ranked'],payload['extra_slot'])
            self._reset_selection();self.status="对局选项已更新："+options_label(payload['ranked'],payload['extra_slot'])
            return self._record("room_options",ranked=payload['ranked'],extra_slot=payload['extra_slot'])
        if kind=="swap":
            if peer_id!="host":return "只有房主可交换阵营"
            if self.phase in ("loading","battle","result"):return "请在房间中交换阵营"
            if scripted(self.mode):return "闯关模式双方都是植物方"
            self.members={p:self._swapped(s) for p,s in self.members.items()}
            self._reset_selection();self.status="阵营已交换，请确认地图"
            return self._record("swap",members=deepcopy(self.members))
        if kind=="confirm_map":
            if self.phase!="config":return "地图已锁定"
            if len(self.members)!=len(self.seat_list()) or not all(self.connected.values()):return "等待另一位玩家"
            supplied=payload.get("terrain_hash")
            if supplied is not None and supplied!=self.map.terrain_hash:return "地图校验不一致，请重新同步"
            if scripted(self.mode) and not self.pve:return "房主尚未选择闯关天数与卡组"
            error=self.coop_progress.ready_error(self,peer_id)
            if error:return error
            self.confirmed[side]=True;self.revision+=1
            if all(self.confirmed.values()):
                if scripted(self.mode):self._start_pve()
                else:self._start_bans()
            return ""
        if kind=="pve_deck":return self._pve_seat_deck(side,payload)
        if kind in ('coop_buy','coop_reward','coop_reset_deck'):
            return self.coop_progress.action(self,peer_id,payload)
        if kind=='coop_skip':
            return self.coop_progress.skip(self,peer_id)
        if kind=="ban":return self._ban(side,payload.get("card"),actor=side)
        if kind=="pick":return self._pick(side,payload.get("card"),actor=side)
        if kind=="load_deck":return "预设仅供本地推荐，请在自己的回合逐张锁定，不能批量载入"
        if kind=="ready":
            if self.phase!="picking" or self.draft_stage!="complete":return "双方必须先完成%d槽逐次选卡"%self.rules["plant_slots"]
            value=payload.get("ready",True)
            if not isinstance(value,bool):return "准备状态无效"
            if value:
                if len(self.members)!=len(self.seat_list()) or not all(self.connected.values()):return "等待双方玩家连接"
                team=team_of(side)
                deck=self.deck_of(side)
                if len(deck)!=self.rules[team+"_slots"]:return "必须选满卡槽"
                error=self._seat_completion_error(side,deck,self.bans)
                if error:return error
                error=validate_deck(team,deck,self.bans,self.rules[team+"_slots"],self.map,
                                    starting_resource("zombie", self.rules, self.map))
                if error:return error
            self.ready[side]=value;self.revision+=1
            error=self._record("ready",side=side,ready=value)
            if error:return error
            if all(self.ready.values()):self._start_battle()
            return ""
        if kind=="restart":
            # Each occupied seat owns one vote. 2v2 needs three of four;
            # duel still needs both players. Pressing again withdraws a vote.
            if self.phase not in ("banning","picking"):return "当前不在禁选阶段"
            if side in self.restart_votes:
                self.restart_votes.discard(side);self.status="已取消重开请求"
            else:
                self.restart_votes.add(side)
                required=3 if self.duo() else len(self.seat_list())
                if len(self.restart_votes)>=required:
                    self._reset_selection();self.status="已达重开票数：请确认地图后重新禁选"
                else:self.status="重开禁选：%d / %d 人同意"%(len(self.restart_votes),required)
            self.revision+=1;return ""
        if kind=="rematch":
            if self.phase!="result":return "对局尚未结束"
            if len(self.members)!=len(self.seat_list()) or not all(self.connected.values()):return "等待双方玩家连接后复赛"
            same=payload.get('same_deck',False)
            if type(same) is not bool or type(payload.get('swap',False)) is not bool:return "复赛方式无效"
            if same and payload.get('swap',False):return "同卡组复赛保留当前阵营"
            if same:
                error=self._same_deck_error()
                if error:return error
            value='same_deck' if same else bool(payload.get("swap",False));self.rematch_votes[side]=value;self.revision+=1
            error=self._record("rematch_vote",side=side,swap=value)
            if error:return error
            if len(self.rematch_votes)==len(self.seat_list()):
                if len(set(self.rematch_votes.values()))!=1:
                    self.status="双方复赛方式不同，请重新选择";return ""
                if value=='same_deck':
                    decks=deepcopy(self.decks);bans=list(self.bans)
                    self._reset_selection();self.decks=decks;self.bans=bans
                    self.phase='picking';self.draft_stage='complete';self.same_deck_rematch=True
                    self.confirmed={s:True for s in self.seat_list()};self.deadline=0.
                    self.status="同卡组复赛：阵营、地图和卡组已保留，请双方点击准备"
                else:
                    if value and not scripted(self.mode):self.members={p:self._swapped(s) for p,s in self.members.items()}
                    self._reset_selection();self.status="复赛：请确认地图后重新禁选"
            return ""
        return "未知房间命令"

    @staticmethod
    def players_sides():return ("plant","zombie")

    def seat_list(self):
        """Player seats of the current mode (factions in the duel)."""
        return seats_for(self.mode)

    def duo(self):
        return self.mode == "duo"

    def deck_keys(self):
        """2v2 keeps one deck per seat; every other mode one per faction."""
        return seats_for(self.mode) if self.duo() else ("plant", "zombie")

    def deck_of(self, seat):
        # Co-op day decks are per seat too: each Dave selects their own cards
        # from the host's challenge pool, so the room carries one deck per seat.
        if scripted(self.mode) and self.pve and seat in (self.pve.get("decks") or {}):
            return self.pve["decks"][seat]
        return self.decks[seat] if self.duo() else self.decks[team_of(seat)]

    def seat_deck(self, seat):
        """The deck a plant seat will actually deploy this day (fallback: team)."""
        if scripted(self.mode) and self.pve:
            decks = self.pve.get("decks") or {}
            if decks.get(seat):
                return list(decks[seat])
            return list(self.pve.get("deck") or [])
        return list(self.deck_of(seat))

    def mate_deck(self, seat):
        if not self.duo():
            return []
        team = team_of(seat)
        mate = team + "2" if seat == team else team
        return self.decks.get(mate, [])

    def _team_feasible(self, team, decks, bans):
        """Can both teammates still fill every slot without sharing a card that
        only one of them may carry? Reserve each seat's own prerequisites too."""
        seats = [s for s in self.seat_list() if team_of(s) == team]
        limit = self.rules[team + "_slots"]
        required = {}
        for seat in seats:
            # Recheck BOTH seats against the prospective pick. A teammate may
            # not take the missing nonrepeatable precursor of a locked secret.
            mate = [k for other in seats if other != seat for k in decks[other]
                    if not team_repeatable(k) and k not in decks[seat]]
            error = self._completion_error(team, decks[seat], list(bans) + mate)
            if error:
                if any(CARDS[k].get('dependency') in mate for k in decks[seat]):
                    return "秘籍前体须由本人携带，队友不可占用：" + error
                return "不能使同队已选阵容无法补齐：" + error
            closure, pending = set(decks[seat]), list(decks[seat])
            while pending:
                dependency = CARDS[pending.pop()].get('dependency')
                if dependency and dependency not in closure:
                    closure.add(dependency);pending.append(dependency)
            required[seat] = closure
        reserved = set()
        for seat in seats:
            exclusive = {k for k in required[seat] if not team_repeatable(k)}
            if reserved & exclusive:
                return "两名队友不能同时保留同一张不可重复的秘籍前体或卡牌"
            reserved.update(exclusive)
        available = {k for k, c in CARDS.items() if c["side"] == team and allowed(k, bans) and not self._map_error(k)}
        taken = set().union(*(required[s] for s in seats))
        unique = {k for k in available if not team_repeatable(k) and k not in taken}
        short = 0
        for s in seats:
            need = max(0, limit - len(required[s]))
            repeat = len({k for k in available if team_repeatable(k) and k not in required[s]})
            if need > len(unique) + repeat:
                return "剩余可用卡牌无法让两名队友都选满"
            short += max(0, need - repeat)
        if short > len(unique):
            return "剩余可用卡牌无法让两名队友都选满（队内不可重复的卡不够分）"
        return ""

    def _seat_completion_error(self, seat, deck, bans):
        team = team_of(seat)
        if self.duo():
            # A card only the teammate may carry is out of reach for this seat:
            # a locked secret's precursor in the mate's deck does not count.
            mate = [k for k in self.mate_deck(seat) if not team_repeatable(k) and k not in deck]
            error = self._completion_error(team, deck, list(bans) + mate)
            if error and any(CARDS[k].get("dependency") in mate for k in deck):
                return "秘籍前体已在队友卡组中，本人无法携带：" + error
        else:
            error = self._completion_error(team, deck, bans)
        if error or not self.duo():
            return error
        decks = dict(self.decks)
        decks[seat] = deck
        return self._team_feasible(team, decks, bans)

    @staticmethod
    def _swapped(seat):
        team="zombie" if team_of(seat)=="plant" else "plant"
        return team+seat[len(team_of(seat)):]

    def set_mode(self,mode):
        """Host switches between 1v1, 2v2, PvE and co-op in the lobby."""
        if mode not in MODES:return "模式无效"
        if self.phase!="config":return "请在房间准备阶段切换模式"
        if mode==self.mode:return ""
        seats=seats_for(mode)
        if len(self.members)>len(seats):return "当前玩家人数超过该模式的席位"
        order=sorted(self.members,key=lambda p:(p!="host",p))
        self.mode=mode;self.pve=None
        self.members={peer:seats[i] for i,peer in enumerate(order)}
        if mode!=DUEL:
            from .team_maps import team_snapshot
            self.map=team_snapshot(self.map)
        self._reset_selection()
        self.status="已切换为"+MODE_LABELS[mode]
        return self._record("room_mode",mode=mode,members=deepcopy(self.members))

    def set_pve(self,day,deck,seed=None,start_sun=150,slots=None,decks=None,unlocked=None,max_zombies=None):
        """Host-side: the campaign day and the plant decks of the next match.

        ``deck`` is the host's own seat deck (kept for the single-player and AI
        harness callers); ``decks`` carries one deck per plant seat, because in
        co-op every Dave selects independently. ``slots``, unlocked cards and
        starting sun describe the host; CoopProgress publishes separate
        authoritative values for guests without importing their private saves.
        """
        if not scripted(self.mode):return "当前不是闯关模式"
        if self.phase!="config":return "请在房间准备阶段设置"
        from .pve import valid_zombie_limit
        limit=self.rules.get('pve_max_zombies',40) if max_zombies is None else max_zombies
        if not valid_zombie_limit(limit):return '在场上限须为1到200的整数'
        if not isinstance(day,int) or day<1:return "天数无效"
        seats=list(self.seat_list())
        plant_seats=[seat for seat in seats if team_of(seat)=="plant"] or ["plant"]
        per_seat={seat:list(deck) for seat in plant_seats}
        if decks:
            if not isinstance(decks,dict):return "卡组格式无效"
            for seat,value in decks.items():
                if seat in plant_seats and isinstance(value,list):
                    per_seat[seat]=list(value)
        for seat,value in per_seat.items():
            if not value or not all(isinstance(k,str) and k in CARDS and CARDS[k]["side"]=="plant" for k in value):
                return "卡组无效"
            from .pve import campaign_card_allowed, disabled_message
            if any(not campaign_card_allowed(k, self.mode=='coop') for k in value):
                return disabled_message(self.mode=='coop')
        if not isinstance(start_sun,int) or not 0<=start_sun<=2000:return "初始阳光无效"
        if slots is None:
            from .pve import slots_for_day
            slots=slots_for_day(day)
        from .pve import STARTER_PLANTS, FREE_TOOLS, MAX_EXTRA_SLOTS, slots_for_day
        minimum=slots_for_day(1) if self.mode=='coop' else slots_for_day(day)
        maximum=10+MAX_EXTRA_SLOTS if self.mode=='coop' else slots_for_day(day)+MAX_EXTRA_SLOTS
        if type(slots) is not int or not minimum<=slots<=maximum:
            return "卡槽数量无效"
        if unlocked is None:
            unlocked=list(dict.fromkeys(list(STARTER_PLANTS)+list(FREE_TOOLS)+list(deck)))
        if (not isinstance(unlocked,list) or not unlocked or
                not all(isinstance(k,str) and k in CARDS and CARDS[k]['side']=='plant' for k in unlocked)):
            return "挑战卡池无效"
        pool=list(dict.fromkeys(unlocked))
        if any(k not in pool for k in deck) or len(deck)>slots:
            return "卡组超出当前挑战卡池或卡槽"
        for seat,value in per_seat.items():
            if any(k not in pool for k in value) or len(value)>slots:
                per_seat[seat]=list(deck)
        host_deck=per_seat.get(self.side_for('host'),list(deck))
        self.pve=dict(day=day,deck=list(host_deck),seed=int(seed if seed is not None else self.seed),
                      start_sun=start_sun,slots=slots,decks=per_seat,unlocked=pool,max_zombies=limit)
        self.rules['pve_max_zombies']=limit
        if self.mode=='coop':self.coop_progress.day=day
        self.coop_progress.sync(self)
        self.confirmed={s:False for s in self.seat_list()}
        self.revision+=1
        self.status="第 %d 天：请确认地图后开始" % day
        return ""

    def setup_changed(self, seat):
        """A seat changed its own co-op setup: seats confirm again.

        An AI teammate's own deck/shop/reward change re-arms only its own
        confirmation; clearing a human's would undo the host's start click
        while the AI waits for that human (the room never left config).
        """
        peer=next((p for p,s in self.members.items() if s==seat),None)
        if peer in self.ai_peers:self.confirmed[seat]=False
        else:self.confirmed={s:False for s in self.seat_list()}

    def _pve_seat_deck(self, seat, payload):
        """A plant seat hands its own day deck to the host (co-op, config phase)."""
        if not scripted(self.mode):return "当前不是闯关模式"
        if self.phase!="config":return "请在房间准备阶段选卡"
        if not self.pve:return "房主尚未选择闯关天数"
        if team_of(seat)!="plant":return "只有植物方可以选卡"
        deck=payload.get("deck")
        if not isinstance(deck,list) or not deck:return "卡组无效"
        limit=(self.pve.get('seat_slots') or {}).get(seat,self.pve['slots'])
        if len(deck)>limit:return "卡槽已满（本局最多 %d 张）" % limit
        if not all(isinstance(k,str) and k in CARDS and CARDS[k]["side"]=="plant" for k in deck):return "卡组无效"
        from .pve import campaign_card_allowed, disabled_message
        if any(not campaign_card_allowed(k, self.mode=='coop') for k in deck):return disabled_message(self.mode=='coop')
        pool=(self.pve.get('seat_unlocked') or {}).get(seat,self.pve['unlocked'])
        if any(k not in pool for k in deck):return "卡牌未在本次合作进度中解锁"
        if len(set(deck))!=len(deck):return "卡组有重复卡牌"
        for key in deck:
            dependency=CARDS[key].get("dependency")
            if dependency and dependency not in deck:return "需要同时携带前体："+CARDS[dependency]["name"]
        decks=dict(self.pve.get("decks") or {})
        previous=decks.get(seat)
        decks[seat]=list(deck)
        self.pve["decks"]=decks
        campaign=self.coop_progress.campaign_for_seat(self,seat)
        if campaign:
            campaign.deck=list(deck)
            self.coop_progress.sync(self)
        if seat==self.side_for('host'):
            self.pve["deck"]=list(deck)
        # A changed deck is a changed day setup: the seats confirm again.
        if previous!=decks[seat]:
            self.setup_changed(seat)
        self.revision+=1
        self.status="第 %d 天：%s 已选好 %d 张卡" % (self.pve["day"], "植物1" if seat=="plant" else seat, len(deck))
        return ""

    def _start_pve(self):
        self.pause_epoch+=1
        from .pve import WaveDirector, pve_rules
        self._save_replay()
        if self.battle:self.battle.close()
        plant_seats=[seat for seat in self.seat_list() if team_of(seat)=="plant"] or ["plant"]
        per_seat=dict(self.pve.get("decks") or {})
        for seat in plant_seats:
            if not per_seat.get(seat):
                per_seat[seat]=list(self.pve["deck"])
        self.decks={seat:list(per_seat[seat]) for seat in plant_seats}
        self.decks["zombie"]=[]
        widest=max(len(per_seat[seat]) for seat in plant_seats)
        rules=pve_rules(self.rules,per_seat[plant_seats[0]],self.pve.get("start_sun",150),slots=widest)
        director=WaveDirector(self.pve["day"],self.pve["seed"],coop=len(self.seat_list())>1,
                              max_zombies=self.pve.get('max_zombies',self.rules.get('pve_max_zombies',40)))
        self.battle=NativeBattle(self.map,self.decks,rules,self.seed,[],bridge=self.bridge,mode=self.mode,director=director)
        if self.mode=='coop':
            self.battle.ai_subsidy_seats=tuple(sorted(seat for peer,seat in self.members.items()
                                                      if peer in self.subsidy_peers and seat in plant_seats))
        for seat,amount in (self.pve.get('seat_start_sun') or {}).items():
            if seat in self.battle.players:self.battle.players[seat]['resource']=float(amount)
        self.match_id=uuid.uuid4().hex;self.match_members=dict(self.members)
        self.match_ranked=False;self.recording=None
        self.phase="loading";self.deadline=self.clock+60.;self.accumulator=0.;self.revision+=1
        self.loading_id="load-%d"%self.revision
        self.loaded={s:False for s in self.seat_list()}
        self.status="正在载入第 %d 天" % self.pve["day"]
        self._record("loading",terrain_hash=self.map.terrain_hash,mode=self.mode,day=self.pve["day"])

    def _start_battle(self):
        self.pause_epoch+=1
        self._save_replay()
        if self.battle:self.battle.close()
        self.battle=NativeBattle(self.map,self.decks,self.rules,self.seed,self.bans,bridge=self.bridge,mode=self.mode)
        if self.mode=='duo':
            self.battle.ai_subsidy_seats=tuple(sorted(seat for peer,seat in self.members.items()
                if peer in self.subsidy_peers and team_of(seat)=='plant'))
        self.match_id=uuid.uuid4().hex;self.match_members=dict(self.members)
        self.match_ranked=bool(self.rules.get('ranked'))
        self.recording=None
        if self.replay_enabled and not scripted(self.mode):
            from .replay import Recording
            self.recording=Recording(self.battle,self.seed,self.decks,self.bans,self.map.to_dict())
        self.phase="loading";self.deadline=self.clock+60.;self.accumulator=0.;self.revision+=1
        self.loading_id="load-%d"%self.revision
        self.loaded={s:False for s in self.seat_list()}
        self.status="正在载入战场，等待双方画面就绪"
        self._record("loading",terrain_hash=self.map.terrain_hash)

    def update(self,dt):
        if self.audit_error:
            if not self._audit_error:self._halt_for_audit(self.audit_error)
            return
        if not isinstance(dt,(int,float)) or dt<0 or dt>2:return
        self.clock+=dt
        if self.disconnect_deadline is not None:
            if self.clock>=self.disconnect_deadline:
                gone=next((p for p in self.members if p!="host" and not self.connected.get(p)),None)
                self._capture_battle_result()
                if self.result is None and self.phase=="battle" and gone:
                    # 对局中断线且重连窗口内没回来（直接关游戏 / 杀进程）= 断线方判负。
                    self._forfeit(gone,"disconnect")
                elif self.result is None:
                    self.result=dict(winner=None,reason="disconnect",tick=self.battle.tick if self.battle else 0)
                    self.phase="result";self.disconnect_deadline=None;self.status="重连超时，对局中止"
                    self.revision+=1;self._record("interrupted",reason="disconnect")
                self.disconnect_deadline=None
                if gone:
                    forfeited=isinstance(self.result,dict) and self.result.get("forfeit")
                    self._release_peer(gone,"对方断线未重连，判对方负；可邀请新玩家加入" if forfeited
                                       else "重连超时，对局中止；可邀请新玩家加入")
            return
        if not all(self.connected.values()) or len(self.members)<len(self.seat_list()):return
        if self.phase=="banning" and self.clock>=self.deadline:
            action=self._draft_action();side=action["side"]
            choices=[] if action["category"]=="secret" else [k for k in sorted(CARDS) if not self._ban_error(side,k)]
            key=random.Random(self.seed+self.draft_index).choice(choices) if choices else None
            self._ban(side,key,automatic=True)
        elif self.phase=="picking" and self.clock>=self.deadline:
            action=self._draft_action()
            if action:
                side=action["side"];key=self._timeout_pick(side)
                if key is None:
                    self._halt_for_audit("选卡状态异常：没有可完成合法阵容的卡牌，对局已停止");return
                self._pick(side,key,automatic=True)
            else:
                # Ready confirmation is also one step per deadline, never a
                # hidden bulk roster mutation after the player has locked cards.
                side=next((s for s in sorted(self.seat_list(),key=lambda s:team_of(s)!="zombie") if not self.ready[s]),None)
                if side and not self.same_deck_rematch:
                    peer=next(p for p,s in self.members.items() if s==side)
                    self.command(peer,dict(type="ready",ready=True,revision=self.revision))
                    if self.phase=="picking":self.deadline=self.clock+self.rules["ready_seconds"]
        elif self.phase=="loading" and self.clock>=self.deadline:
            self.result=dict(winner=None,reason="load_timeout",tick=0)
            self.phase="result";self.revision+=1;self.status="载入超时，对局尚未开始"
            self._record("interrupted",reason="load_timeout")
        elif self.phase=="battle" and not self.paused:
            if self._paced_battle is not self.battle:
                self.pacing=AdaptivePacing();self._paced_battle=self.battle
            self.accumulator+=dt*self.pacing.scale
            # No dropped simulation time. Limit per render frame then drain next frame.
            count=min(12,int((self.accumulator+1e-9)/self.battle.dt))
            if count:
                started=time.perf_counter()
                try:self.battle.step(count)
                except AuditLogError as exc:self._halt_for_audit(exc);return
                self.accumulator-=count*self.battle.dt
                self.pacing.sample(time.perf_counter()-started,count*self.battle.dt)
            if self.battle.result:
                self._capture_battle_result()

    def snapshot(self,for_peer=None,include_map=True,copy_state=True):
        if self.pve and self.coop_progress.ensure(self):self.coop_progress.sync(self)
        side=self.side_for(for_peer) if for_peer else None
        turn=self._draft_action() if self.phase in ("banning","picking") else None
        actor=turn["side"] if turn else None
        action=(("zsecret" if turn.get("target")=="zombie" else turn["category"]) if turn["kind"]=="ban" else "pick") if turn else None
        stage_actions=[i for i,a in enumerate(self.draft_schedule) if a["stage"]==self.draft_stage]
        progress=dict(step=self.draft_index,total=len(self.draft_schedule),
                      stage_step=sum(i<self.draft_index for i in stage_actions),stage_total=len(stage_actions),
                      picked={s:len(self.decks[s]) for s in self.deck_keys()},
                      slot_limit={s:self.rules[s+"_slots"] for s in self.players_sides()})
        battle=self.battle.snapshot(include_map=include_map,copy_state=copy_state) if self.battle else None
        if battle and (side or for_peer in self.spectators):
            for s,p in battle["players"].items():
                if s!=side:p["input"]={}
        value=dict(phase=self.phase,revision=self.revision,map_id=self.map_id,seed=self.seed,
            members=deepcopy(self.members),connected=deepcopy(self.connected),confirmed=deepcopy(self.confirmed),
            bans=list(self.bans),decks=deepcopy(self.decks),ready=deepcopy(self.ready),
            current_side=actor,current_action=action,remaining=len(self.draft_schedule)-self.draft_index,
            draft_stage=self.draft_stage,draft_history=deepcopy(self.draft_history),draft_progress=progress,
            can_skip=bool(turn and turn["kind"]=="ban" and not self._ban_error(actor,None)),
            deadline=max(0.,self.deadline-self.clock),battle=battle,result=deepcopy(self.result),
            rules=deepcopy(self.battle.rules if self.battle and scripted(self.mode) else self.rules),
            status=self.status,terrain_hash=self.map.terrain_hash,paused=self.paused,pause_votes=sorted(self.pause_votes),pause_epoch=self.pause_epoch,audit_error=self.audit_error,
            pacing=self.pacing.snapshot(),
            restart_votes=sorted(self.restart_votes),
            restart_required=3 if self.duo() else len(self.seat_list()),
            rematch_votes=deepcopy(self.rematch_votes),disconnect_remaining=max(0.,self.disconnect_deadline-self.clock) if self.disconnect_deadline else None,
            match_number=self.match_number)
        value["loaded"]=deepcopy(self.loaded)
        value["copy_targets"]=dict(self.copy_targets)
        if turn and turn['kind']=='ban':
            same=[i for i,a in enumerate(self.draft_schedule) if a['stage']==turn['stage']
                  and a['side']==turn['side'] and a['category']==turn['category']]
            value['ban_progress']=dict(index=sum(i<=self.draft_index for i in same),total=len(same),
                                       target=turn.get('target',turn['category']),category=turn['category'])
        if turn and turn.get("seat"):value["current_seat"]=turn["seat"]
        value['same_deck_rematch']=self.same_deck_rematch
        value['config_requests']=[dict(id=r['id'],peer=p,label=r['label']) for p,r in self.config_requests.items()]
        value['request_outcome']=deepcopy(self.request_outcome)
        value['player_profiles']=deepcopy(self.player_profiles)
        value['ai_peers']=sorted(p for p in self.ai_peers if p in self.members)
        value['match_id']=self.match_id;value['match_members']=dict(self.match_members)
        value['match_ranked']=bool(self.match_ranked and self.match_id)
        value["allow_spectators"]=self.allow_spectators
        value["spectator_count"]=len(self.spectators)
        value["spectating"]=for_peer in self.spectators
        value["host_spectating"]='host' in self.spectators
        value["available_seats"]=[s for s in self.seat_list() if s not in self.members.values()]
        value["mode"]=self.mode;value["seats"]=list(self.seat_list())
        value["team_chat"]=self.team_chat.view(side,everyone=for_peer is None)
        if self.pve:value["pve"]=deepcopy(self.pve)
        value["can_change_role"]=self.phase in ('config','result') and self.peer_connected(for_peer)
        value["loading_id"]=self.loading_id
        if include_map:value["map"]=self.map.to_dict()
        return value

    def export_log(self,path):
        import json
        import os
        import tempfile
        from pathlib import Path
        destination=Path(path);destination.parent.mkdir(parents=True,exist_ok=True)
        metadata=dict(format="pvz-pvp-log-1",build=self.rules["build"],rules=self.rules,map=self.map.to_dict(),
                      result=self.result,audit_complete=not bool(self.audit_error),audit_error=self.audit_error,
                      battle_event_count=len(self.battle.log) if self.battle else 0)
        staging=None
        try:
            with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=str(destination.parent),
                                             prefix=destination.name+".",suffix=".pending",delete=False) as stream:
                staging=stream.name;stream.write("{");first=True
                for key,value in metadata.items():
                    if not first:stream.write(",")
                    json.dump(key,stream);stream.write(":")
                    json.dump(value,stream,ensure_ascii=False,separators=(",",":"),allow_nan=False)
                    first=False
                stream.write(',"room":');write_json_array(stream,self.log)
                stream.write(',"battle":');write_json_array(stream,self.battle.log if self.battle else ())
                stream.write("}");stream.flush();os.fsync(stream.fileno())
            os.replace(staging,str(destination))
        except Exception:
            if staging:
                try:os.unlink(staging)
                except OSError:pass
            raise
        return str(path)
