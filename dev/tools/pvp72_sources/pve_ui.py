"""PvP66 PvE / co-op screens, entered from the original game's mode list.

Styled after the original: the sky backdrop, seed envelopes on the original
card board, Crazy Dave and his car boot for the shop, coins with the original
coin art. The PvP menus are not touched; these screens only run when the
original mode list opened 闯关模式 or 双人合作.

The campaign lives with the player profile (pve_campaign.json). Single PvE
uses an offline host room; co-op is a network room created in PvE co-op mode,
and the host decides the day. Each seated guest grows independently within
the room; a watching host controls the calendar without earning progress.
"""
import time

from .catalog import CARDS
from .pve import (Campaign, describe_day, map_for_day, slots_for_day, waves_for_day, SUN_STEP, TIERS,
                  TIER_NAMES, TIER_UNLOCK_DAY, COOP_TIER_UNLOCK_DAY, zombie_limit, MAX_ZOMBIE_LIMIT)
from .rendering import card_art_name
from .teams import DUEL, DUO, PVE, COOP, MODES, MODE_LABELS, scripted, team_of

PAGE = 16
GOLD = (255, 226, 120)
INK = (49, 39, 26)
PAPER = (244, 236, 215)
BAD = (255, 150, 130)


class PveUI:
    def init_pve(self):
        self._campaign = None
        self._coop_campaign = None
        self._coop_campaign_scope = None
        self._coop_campaign_remote = None
        self._coop_observer_campaign = None
        self._coop_observer_scope = None
        self.native_entry = None

    # ------------------------------------------------------------ storage
    def campaign_path(self):
        profiles = getattr(self, "profiles", None)
        folder = profiles.folder() if profiles else self.settings_path.parent
        return folder / "pve_campaign.json"

    def bind_coop_progress(self):
        if self.mode=='host' and self.room and self.room.mode==COOP and self.room.coop_progress.path is None:
            self.room.coop_progress.bind(self.campaign_path().with_name('coop_run.json'),self.personal_campaign)

    @property
    def personal_campaign(self):
        if self._campaign is None:
            self._campaign = Campaign.load(self.campaign_path())
        return self._campaign

    @property
    def campaign(self):
        """Read this room's authoritative guest growth, never a private save."""
        personal = self.personal_campaign
        view = self.view or {}
        pve = view.get('pve') or {}
        room=self.room
        if self.mode=='host' and room and room.mode==COOP:
            self.bind_coop_progress()
            seat=room.side_for('host')
            if seat:
                return room.coop_progress.campaign_for_seat(room,seat)
            scope=(id(room),room.coop_progress.run_id)
            if self._coop_observer_scope!=scope:
                self._coop_observer_campaign=Campaign.from_dict(room.coop_progress.campaigns['plant'].to_dict())
                self._coop_observer_campaign.rewards=[]
                self._coop_observer_scope=scope
            self._coop_observer_campaign.day=room.coop_progress.day
            return self._coop_observer_campaign
        self._coop_observer_campaign = None
        self._coop_observer_scope = None
        if self.mode != 'guest' or view.get('mode') != COOP:
            return personal
        seat = (view.get('members') or {}).get(self.peer_id)
        remote = (pve.get('guest_campaigns') or {}).get(seat)
        scope = (self.peer_id, seat, pve.get('coop_run_id'), id(personal))
        if self._coop_campaign_scope != scope or remote != self._coop_campaign_remote:
            campaign = Campaign.from_dict(remote) if remote else Campaign(seed=pve.get('seed', 1))
            if remote:
                campaign.deck = list(remote['deck'])
            pending = self.state.get('pve_pending_deck')
            if (self._coop_campaign_scope == scope and pending and remote
                    and pending['deck'] != remote['deck'] and self._coop_campaign):
                selected = list(self._coop_campaign.deck)
                campaign.deck = [k for k in selected if k in campaign.available_unlocked()][:campaign.slots()]
            self._coop_campaign, self._coop_campaign_scope = campaign, scope
            self._coop_campaign_remote = remote
        return self._coop_campaign

    def save_campaign(self, personal=False):
        campaign = self.personal_campaign if personal else self.campaign
        if campaign is not self.personal_campaign:
            if self.mode=='host' and self.room and self.room.mode==COOP:
                # Publish via pve_push_deck so its old/new comparison can
                # invalidate preparation before mirroring the saved deck.
                self.room.coop_progress.save()
            return
        try:
            campaign.save(self.campaign_path())
        except OSError as exc:
            self.message("闯关进度保存失败：" + str(exc))

    def pve_result(self, result):
        """Apply a finished day to this player's own campaign.

        The host gets this from the room callback; a co-op guest runs it from
        the broadcast result, so both Daves keep their own coins, unlocks and
        reward picks while sharing the same match.
        """
        if (self.room and self.room.mode==COOP) or (self.view or {}).get('mode')==COOP:
            seat=self.room.side_for('host') if self.mode=='host' else (self.view.get('members') or {}).get(self.peer_id)
            income=self.room.coop_progress.income.get(seat) if self.mode=='host' else ((self.view.get('pve') or {}).get('guest_income') or {}).get(seat)
            if income:
                self.state['pve_income'] = dict(income)
                tail = '另余 0.5 金币已结转，下次累计入账。' if income['coin_half'] else ''
                self.message('第 %d 天金币 +%d（拾取 %d，通关奖励 %d）。%s' %
                             (income['day'], income['total'], income['coins'], income['bonus'], tail))
            elif self.mode=='host':
                self.message('观战结算已完成，入座玩家各自领取奖励；房主可准备下一天')
            return
        campaign = self.personal_campaign
        day = result.get("pve_day")
        if day is None:
            return
        if self.mode != "guest" and day != campaign.day:
            return
        coins = int(result.get("coins", 0) or 0)
        coop = bool(self.room and self.room.mode == COOP) or (self.view or {}).get("mode") == COOP
        before = campaign.coins
        bonus = 0
        if result.get("winner") == "plant":
            bonus = campaign.win(coins, coop, int(result.get("fallen", 0) or 0), played_day=day)
        else:
            campaign.lose(coins)
        total = campaign.coins - before
        earned = total - bonus
        self.state["pve_income"] = dict(day=day, winner=result.get("winner"), coins=earned,
                                       bonus=bonus, total=total, coin_half=campaign.coin_half)
        tail = "另余 0.5 金币已结转，下次累计入账。" if campaign.coin_half else ""
        if result.get("winner") == "plant":
            self.message("第 %d 天通过！金币 +%d（拾取 %d，通关奖励 %d）。%s" % (day, total, earned, bonus, tail))
        else:
            self.message("第 %d 天失败，保留拾取的 %d 金币；可去商店或调整卡组后重试。%s" % (day, earned, tail))
        self.save_campaign(personal=True)

    def pve_apply_guest_result(self, view):
        """A co-op guest advances its own campaign once per finished day.

        A network guest has no local room object, so the mode comes from the
        broadcast view (or from the mirror room when one exists).
        """
        self._pve_sync_guest_deck(view)
        if self.mode != "guest":
            return
        if (view.get("mode") or "") not in (PVE, COOP) and not (self.room and scripted(self.room.mode)):
            return
        result = view.get("result") or {}
        if result.get("pve_day") is None:
            return
        key = self.pve_result_key(view)
        if self.state.get("pve_applied_result") == key:
            return
        self.state["pve_applied_result"] = key
        self.pve_result(result)

    def _pve_deck_scope(self, view):
        pve = view.get("pve") or {}
        seat = (view.get("members") or {}).get(self.peer_id)
        return (self.peer_id, seat, pve.get("day"), pve.get("seed"), view.get("terrain_hash"))

    def pve_guest_command_error(self, payload):
        """A rejected request must never leave a delayed ready click armed."""
        if self.mode == "guest":
            self.state.pop("pve_pending_deck", None)
            self.state.pop("pve_pending_ready", None)

    def _pve_sync_guest_deck(self, view):
        """Finish an explicit ready click only after this seat's deck is acknowledged."""
        state = self.state
        if (self.mode != "guest" or view.get("mode") != COOP or view.get("phase") != "config"
                or not (view.get("pve") or {}).get("day")
                or team_of((view.get("members") or {}).get(self.peer_id)) != "plant"):
            state.pop("pve_pending_deck", None)
            state.pop("pve_pending_ready", None)
            return
        scope = self._pve_deck_scope(view)
        seat = scope[1]
        deck = list(self.campaign.deck)
        published = ((view.get("pve") or {}).get("decks") or {}).get(seat)
        pending = state.get("pve_pending_deck")
        if (pending and pending["scope"] == scope and pending["deck"] == deck
                and published != deck and view.get("revision", 0) > pending["revision"]):
            # A newer configuration without our deck is not its acknowledgement.
            # Do not turn a delayed error/snapshot into an automatic retry/ready.
            state.pop("pve_pending_deck", None)
            state.pop("pve_pending_ready", None)
            return
        if pending and (pending["scope"] != scope or pending["deck"] != deck
                        or published == pending["deck"]
                        or view.get("revision", 0) > pending["revision"]):
            state.pop("pve_pending_deck", None)
        ready = state.get("pve_pending_ready")
        if not ready:
            return
        if ready["scope"] != scope or ready["deck"] != deck or state.get("screen") != "room":
            state.pop("pve_pending_ready", None)
            return
        if published != deck:
            return
        state.pop("pve_pending_ready", None)
        if not (view.get("confirmed") or {}).get(seat):
            self.command(dict(type="confirm_map", terrain_hash=view.get("terrain_hash")), seat)

    def pve_result_key(self, view):
        result = view.get("result") or {}
        return (view.get("match_id") or getattr(self.room, "match_id", "") or "", result.get("pve_day"),
                result.get("winner"), result.get("tick"))

    def pve_room_seat(self):
        """The plant seat this client owns in the current room."""
        members = (self.view or {}).get("members") or {}
        seat = members.get(self.peer_id)
        if seat and team_of(seat) == "plant":
            return seat
        room = self.room
        if room:
            for peer, value in (room.members or {}).items():
                if peer == self.peer_id and team_of(value) == "plant":
                    return value
        return None

    def pve_room_day(self):
        """The day the host set for this room (None outside a scripted room)."""
        view = self.view or {}
        if view.get("mode") in (PVE, COOP):
            pve = view.get("pve") or {}
            if pve.get("day"):
                return pve["day"]
        room = self.room
        if room is not None and scripted(getattr(room, "mode", None)) and getattr(room, "pve", None):
            return room.pve.get("day")
        return None

    def pve_deck_capacity(self):
        """Slots this player may fill for the day being played."""
        if (self.room and self.room.mode==COOP) or (self.view or {}).get('mode')==COOP:
            return self.campaign.slots()
        campaign = self.campaign
        day = self.pve_room_day()
        return (slots_for_day(day) + campaign.extra_slots) if day else campaign.slots()

    def pve_push_deck(self):
        """Publish either Dave's selected deck before anyone can confirm it."""
        if self.mode not in ("host", "guest") or not self.pve_room_day():
            return ""
        seat = self.pve_room_seat()
        if not seat:
            return ""
        if self.room and self.mode == 'host':
            wanted = self._pve_wanted()
            pve = self.room.pve or {}
            if (pve.get('day') == wanted['day'] and pve.get('seed') == wanted['seed']
                    and any(pve.get(key) != wanted[key] for key in ('unlocked', 'slots', 'start_sun'))):
                # Publish a host purchase before validating its newly unlocked
                # card. Guests receive the pool/slot change in the same revision.
                decks = dict(pve.get('decks') or {})
                decks.pop(seat, None)
                error = self.room.set_pve(decks=decks, **wanted)
                if not error:
                    self.room._pve_setup = (wanted, self.room.map_id, self.room.seed)
                    self.refresh()
                return error or ''
        view = self.view or {}
        deck = list(self.campaign.deck)
        scope = self._pve_deck_scope(view)
        revision = view.get("revision", 0)
        pending = self.state.get("pve_pending_deck")
        if self.mode == "guest":
            if ((view.get("pve") or {}).get("decks") or {}).get(seat) == deck:
                self.state.pop("pve_pending_deck", None)
                return ""
            if pending == dict(scope=scope, deck=deck, revision=revision):
                return ""
        error = self.command(dict(type="pve_deck", deck=deck)) or ""
        if not error and self.mode == "guest":
            self.state["pve_pending_deck"] = dict(scope=scope, deck=deck, revision=revision)
        if not error and self.room and self.mode == "host":
            wanted = self._pve_wanted()
            current = {key: self.room.pve.get(key) for key in wanted}
            if current == wanted:
                self.room._pve_setup = (wanted, self.room.map_id, self.room.seed)
        return error

    # -------------------------------------------------------------- entry
    def enter_native(self, entry):
        """Opened from the original mode list: go straight to the new mode."""
        self.native_entry = entry
        if entry == "pve":
            self.state.update(screen="pve", pve_page=0, pve_reset=False, pve_coop=False, pve_return="exit")
        elif entry == "coop":
            self.state.update(screen="coop_entry", focus=None, network_mode="relay", room_public=True)

    def leave_to_native(self):
        """Back from a PvP66 screen opened by the original mode list."""
        if self.native_entry:
            self.running = False
            return True
        return False

    # ------------------------------------------------------------ actions
    def pve_action(self, action):
        kind = action[0]
        if kind in ("leave", "coop_back", "coop_join", "coop_spectate", "coop_create", "pve_reset"):
            self.state.pop("pve_pending_deck", None)
            self.state.pop("pve_pending_ready", None)
        if (kind == "confirm_map" and self.mode == "guest" and (self.view or {}).get("mode") == COOP
                and (self.view or {}).get("phase") == "config" and self.pve_room_day()
                and self.pve_room_seat()):
            seat = self.pve_room_seat()
            deck = list(self.campaign.deck)
            if (((self.view or {}).get("pve") or {}).get("decks") or {}).get(seat) != deck:
                self.state["pve_pending_ready"] = dict(scope=self._pve_deck_scope(self.view), deck=deck)
                error = self.pve_push_deck()
                if error:
                    self.state.pop("pve_pending_ready", None)
                    self.message(error)
                return True
        if kind == "room_mode":
            if not self.room or self.mode not in ("host", "local"):
                self.message("只有房主可切换模式")
                return True
            current = self.room.mode
            target = action[1] if len(action) > 1 else MODES[(MODES.index(current) + 1) % len(MODES)]
            error = self.command(dict(type="room_mode", mode=target), self.room.side_for("host"))
            if not error and self.transport and hasattr(self.transport, "set_max_peers"):
                self.transport.set_max_peers(max(2, len(self.room.seat_list()) - 1))
            if not error and target == DUO and current != DUO:
                from .team_maps import DEFAULT_DUO_MAP, bundled_id, map_command
                if not bundled_id(self.room.map_id):
                    self.command(map_command(DEFAULT_DUO_MAP, self.room.revision), self.room.side_for("host"))
            return True
        if kind == "chat_open":
            from .team_chat import open_chat
            open_chat(self.state)
            self.release_inputs()
            return True
        if kind == "chat_send":
            text = self.state.get("chat", "").strip()
            self.state.update(focus=None, ime_text="")
            if text:
                sides = self.local_sides()
                error = self.command({"type": "chat", "text": text}, sides[0] if sides else None)
                if error:
                    self.message(error)
                else:
                    self.state["chat"] = ""
            return True
        if kind == "coop_create":
            limit=zombie_limit(self.state.get('pve_max_zombies'))
            self.state.update(room_size="duel", room_kind="coop")
            self.create(False)
            self.state.pop('room_kind',None)  # direct creation also consumes the mode hint
            if self.room:
                self.room.set_mode(COOP)
                self.room.rules['pve_max_zombies']=limit
                self.room.replay_enabled = False
                self.room.on_pve_result = self.pve_result
                self.refresh()
            else:self.state['screen']='coop_entry'
            return True
        if kind=='coop_network':
            self.state.update(network_mode='direct' if self.state.get('network_mode')=='relay' else 'relay',
                              token='',focus=None,message='')
            return True
        if kind == "coop_join":
            self.join()
            if self.transport is None:self.state['screen']='coop_entry'
            return True
        if kind == "coop_spectate":
            self.join(spectator=True)
            return True
        if kind == "coop_back":
            if not self.leave_to_native():
                self.state.update(screen="home")
            return True
        if not kind.startswith("pve_"):
            return False
        if kind in ("pve_open", "pve_toggle", "pve_reward", "pve_item", "pve_buy", "pve_reset", "pve_start", "pve_limit", "pve_skip"):
            phase = self.room.phase if self.room else (self.view or {}).get("phase")
            if phase and phase not in ("config", "result"):
                self.message("请先结束当前挑战，再调整选卡、购买或重开")
                return True
        campaign = self.campaign
        if kind=='pve_limit':
            if self.mode=='guest':
                self.message('在场僵尸上限由房主设置');return True
            delta=action[1] if len(action)>1 else 0
            if type(delta) is not int:return True
            limit=max(1,min(MAX_ZOMBIE_LIMIT,self.pve_population_limit()+delta))
            if self.room and self.room.mode==COOP:
                error=self.command(dict(type='pve_population',max_zombies=limit))
                if error:self.message(error)
                else:self.room._pve_setup=None
            elif self.state.get('screen')=='coop_entry':
                self.state['pve_max_zombies']=limit
            else:
                campaign.max_zombies=limit;self.save_campaign()
                if self.room and self.room.mode==PVE and self.room.phase=='config':
                    self.command(dict(type='pve_population',max_zombies=limit))
                    self.room._pve_setup=None
            return True
        if kind == "pve_open":
            if self.mode == 'guest' and (self.view or {}).get('mode') == COOP and not self.pve_room_day():
                self.message('等待房主设置本次挑战后再选卡')
                return True
            self.state.pop("pve_pending_ready", None)
            # A co-op guest has no local room object, but lives in one: the room
            # is where the day screen goes back to.
            in_room = bool(self.room) or self.mode == "guest"
            coop = bool(self.room and self.room.mode == COOP) or (self.view or {}).get("mode") == COOP
            self.state.update(screen="pve", pve_page=0, pve_reset=False, focus=None,
                              pve_return="room" if in_room else ("exit" if self.native_entry else "home"), pve_coop=coop)
        elif kind == "pve_back":
            target = self.state.get("pve_return", "home")
            if target == "room" and (self.view or {}).get("phase") == "config":
                error = self.pve_push_deck()
                if error:
                    self.message(error)
                    return True
            if target == "exit":
                self.close_room()
                if not self.leave_to_native():
                    self.state.update(screen="home")
            else:
                self.state.update(screen=target, focus=None)
        elif kind == "pve_skip":
            # PvP73: pay $10000 to count the current day as cleared (reward pick, no coins).
            from .pve import SKIP_PRICE
            if self.mode == "guest":
                self.message("只有房主可以花金币跳关")
                return True
            now = time.monotonic()
            if now - self.state.get("pve_skip_armed", -10.) > 4.:
                self.state["pve_skip_armed"] = now
                self.message("再点一次确认：花费 $%d 跳过第 %d 天（视为通关，可领取奖励卡，不发通关金币）" % (SKIP_PRICE, campaign.day))
                return True
            self.state.pop("pve_skip_armed", None)
            if self.room and self.room.mode == COOP:
                if self.mode == "host":
                    self.refresh()
                error = self.command(dict(type="coop_skip"))
                if not error and self.mode == "host":
                    error = self.pve_push_deck()
                self.message(error or "已跳过本关，请领取奖励卡")
            else:
                day = campaign.day
                error = campaign.skip_day()
                if error:
                    self.message(error)
                    return True
                self.save_campaign()
                self.message("已花费 $%d 跳过第 %d 天，请选择奖励卡" % (SKIP_PRICE, day))
        elif kind == "pve_shop":
            self.state.update(screen="pve_shop", focus=None, pve_pick=None, pve_detail=None, pve_detail_scroll=0, message="")
        elif kind == "pve_shop_back":
            self.state.update(screen="pve", focus=None, pve_pick=None, message="")
        elif kind == "pve_item":
            # Desktop buys on click as the original; touch has no hover, so the
            # first tap shows the description and a second tap buys.
            if self._touch_ui() and self.state.get("pve_pick") != action[1]:
                self.state["pve_pick"] = action[1]
            else:
                self.pve_buy(action[1])
        elif kind == "pve_buy":
            self.pve_buy(action[1])
        elif kind == "pve_scroll":
            self.state[action[1]] = max(0, int(self.state.get(action[1], 0) or 0) + action[2])
        elif kind == "pve_page":
            self.state["pve_page"] = max(0, self.state.get("pve_page", 0) + action[1])
        elif kind == "pve_toggle":
            self.state.pop("pve_pending_ready", None)
            # Each seat selects independently within the host's challenge pool.
            if self.pve_room_day() and campaign.deck == [action[1]]:
                self.message("本局至少需要携带一张卡，请先选入替换卡")
                return True
            error = campaign.toggle(action[1], limit=self.pve_deck_capacity(), day=self.pve_room_day())
            if error:
                self.message(error)
            else:
                self.save_campaign()
                pushed = self.pve_push_deck()
                if pushed:
                    self.message(pushed)
                elif self.pve_room_seat():
                    self.message("已选好 %d 张卡，请双方重新确认" % len(campaign.deck))
        elif kind == "pve_reward":
            if self._touch_ui() and action[1] is not None and self.state.get("pve_pick_reward") != action[1]:
                self.state["pve_pick_reward"] = action[1]      # touch: first tap reads the card
                return True
            self.state["pve_pick_reward"] = None
            if campaign is not self.personal_campaign:
                error = self.command(dict(type='coop_reward', card=action[1]))
                self.message(error or '正在领取本次合作奖励')
                return True
            error = campaign.choose_reward(action[1])
            if error:
                self.message(error)
            else:
                self.save_campaign()
                self.message("已解锁：" + (CARDS[action[1]]["name"] if action[1] else "（跳过）") + "；商店已进新货")
        elif kind == "pve_reset":
            if self.mode=='host' and self.room and self.room.mode==COOP:
                if not self.state.get('pve_reset'):
                    self.state['pve_reset']=True
                    self.message('再点一次将重开合作挑战，清空两个合作席位；单人存档保留')
                else:
                    self.room.coop_progress.reset();self.room.coop_progress.save()
                    self.room._reset_selection();self.room.pve=None;self.room._pve_setup=None
                    self.state.update(pve_reset=False,pve_page=0,pve_pick=None,pve_pick_reward=None,pve_income=None,focus=None)
                    self.refresh();self.message('已重开合作挑战，两个席位从第一天开始')
                return True
            if campaign is not self.personal_campaign:
                if not self.state.get('pve_reset'):
                    self.state['pve_reset'] = True
                    self.message('再点一次将重置本次合作选卡，个人闯关存档保留')
                else:
                    self.state.update(pve_reset=False, pve_page=0, pve_pick=None, focus=None)
                    error = self.command(dict(type='coop_reset_deck'))
                    self.message(error or '正在重置本次合作选卡')
                return True
            if not self.state.get("pve_reset"):
                self.state["pve_reset"] = True
                self.message("再点一次“确认重开”将清空闯关进度")
            else:
                phase = self.room.phase if self.room else (self.view or {}).get("phase")
                if phase and phase not in ("config", "result"):
                    self.message("请先结束当前挑战，再确认重开闯关")
                    return True
                self._campaign = Campaign()
                self.save_campaign()
                # A new local save must also invalidate the host's prepared
                # day. Otherwise set_pve's per-seat overrides can restore the
                # old host deck even though the selection board was reset.
                if self.room and scripted(self.room.mode):
                    self.room.coop_progress.reset()
                    self.room._reset_selection()
                    self.room.pve = None
                    self.room._pve_setup = None
                    self.refresh()
                if self.mode == "guest" and phase == "result":
                    # The host may remain on this result screen after our
                    # personal restart. Its next snapshot must not pay the
                    # same old victory into the new campaign again.
                    self.state["pve_applied_result"] = self.pve_result_key(self.view or {})
                error = self.pve_push_deck() if self.mode == "guest" and phase == "config" else ""
                self.state.update(pve_reset=False, pve_page=0, pve_pick=None,
                                  pve_pick_reward=None, pve_detail=None,
                                  pve_detail_scroll=0, pve_income=None, focus=None)
                self.message("已开始新的闯关存档" + ("；房间卡组同步失败：" + error if error else ""))
        elif kind == "pve_start":
            self.start_pve_day()
        return True

    def pve_buy(self, index):
        campaign = self.campaign
        if campaign is not self.personal_campaign:
            if self.mode=='host':self.refresh()
            error = self.command(dict(type='coop_buy', index=index))
            if not error and self.mode=='host':
                error=self.pve_push_deck()
            self.state['pve_pick'] = None
            self.message(error or ('购买成功' if self.mode=='host' else '正在购买本次合作商品'))
            return
        error = campaign.buy(index)
        audio = getattr(self, "game_audio", None)
        if error:
            if error.startswith("金币不足"):
                # The original plays 阳光不够 and flashes the wallet red.
                self.state["pve_broke_until"] = time.monotonic() + 3.3
                if audio:
                    audio.play("阳光不够", self.state.get("volume", .35))
            self.message(error)
            return
        if audio:
            audio.play("花费", self.state.get("volume", .35))
        self.state["pve_pick"] = None
        self.save_campaign()
        error = self.pve_push_deck()
        if self.room and self.mode == "host" and self.room.phase == "config" and self.room.pve and not self.pve_setup_current():
            # Starting sun or capacity can change without changing the deck.
            # These purchases still invalidate the old ready-to-start setup.
            self.room.confirmed = {seat: False for seat in self.room.seat_list()}
            self.room._pve_setup = None
            self.room.revision += 1
            self.refresh()
        self.message("购买成功：" + shop_label(campaign.shop[index]) + ("；卡组同步失败：" + error if error else ""))

    def start_pve_day(self):
        campaign = self.campaign
        if campaign.rewards:
            self.message("请先选择上一天的奖励卡")
            return
        coop = bool(self.room and self.room.mode == COOP)
        if not coop:
            if not self.room or self.room.mode != PVE:
                self.create_offline_host()
                error = self.room.set_mode(PVE)
                if error:
                    self.message(error)
                    return
        room = self.room
        if room.phase == "result":
            room._reset_selection()
        # Re-sending the map and day clears every seat's confirmation, so a
        # host pressing 开始干 after the teammate confirmed used to knock that
        # confirmation out. Only re-send when the day's setup really changed.
        if not self.pve_setup_current():
            wanted=self._pve_wanted()
            source, name, night = map_for_day(wanted['day'], coop)
            if source == "team":
                from .team_maps import bundled_document
                doc = bundled_document(name)
                payload = dict(type="map", map_id="custom:" + doc["id"], seed=doc["seed"], custom_map=doc, night=night)
            else:
                payload = dict(type="map", map_id=name, seed=campaign.seed % 100000 + campaign.day, night=night)
            error = room.command("host", dict(payload, revision=room.revision))
            if error:
                self.message(error)
                return
            # Only teammates' decks survive a host day update. The host deck
            # comes from the current campaign, never the previous room setup.
            decks = dict((room.pve or {}).get("decks") or {})
            decks.pop(room.side_for("host"), None)
            error = room.set_pve(decks=decks,**wanted)
            if error:
                self.message(error)
                return
            room._pve_setup = (self._pve_wanted(), room.map_id, room.seed)
        if coop and self.ai_room:
            # Prepare built-in seats before the human confirms this setup.
            # Their purchases/deck commands legitimately clear confirmations;
            # doing those on the next AI tick would cancel a just-pressed start.
            from .coop_ai import preparation_action
            for controller in self.ai_room.seats.values():
                for _ in range(32):  # finite shop, one reward and one deck
                    if not preparation_action(controller):break
        room.on_pve_result = self.pve_result
        room.replay_enabled = False
        self.state.update(screen="room", focus=None)
        self.refresh()
        host_seat = room.side_for("host")
        if host_seat is None:
            self.message('房主观战：已准备第 %d 天，等待两位玩家确认' % campaign.day)
        elif not room.confirmed.get(host_seat):
            self.command({"type": "confirm_map", "terrain_hash": room.map.terrain_hash}, host_seat)

    def _pve_wanted(self):
        campaign = self.campaign
        day=self.room.coop_progress.day if self.room and self.room.mode==COOP else campaign.day
        return dict(day=day, deck=list(campaign.battle_deck()), seed=int(campaign.seed + day),
                    start_sun=campaign.start_sun(), slots=campaign.slots(), unlocked=campaign.available_unlocked(),
                    max_zombies=self.pve_population_limit())

    def pve_population_limit(self):
        if self.room and self.room.mode==COOP:
            return zombie_limit(self.room.rules.get('pve_max_zombies'))
        view=self.view or {}
        if self.mode=='guest' and view.get('mode')==COOP:
            return zombie_limit((view.get('pve') or {}).get('max_zombies',(view.get('rules') or {}).get('pve_max_zombies')))
        if self.state.get('screen')=='coop_entry':return zombie_limit(self.state.get('pve_max_zombies'))
        return zombie_limit(self.campaign.max_zombies)

    def _draw_population_limit(self,r,st,x,y,width,fs):
        limit=self.pve_population_limit()
        label(r,'在场上限 %d'%limit,st.pos(x,y+.13),WHITE,fs,BLACK)
        if self.mode=='guest':return
        button_w=.75
        start=x+width-4*(button_w+.08)
        for index,(text,delta) in enumerate((('-10',-10),('-1',-1),('+1',1),('+10',10))):
            r.button(text,st.rect(start+index*(button_w+.08),y,button_w,.65),('pve_limit',delta),size=max(11,fs-2))

    def pve_setup_current(self):
        """The room already holds today's map and deck, as last sent by the host."""
        room = self.room
        if not room or room.phase != "config" or not room.pve:
            return False
        wanted = self._pve_wanted()
        # Co-op carries one deck per seat, so only the host's own keys decide
        # whether the day needs to be re-sent (a teammate's deck must survive it).
        current = {key: room.pve.get(key) for key in wanted}
        return current == wanted and getattr(room, "_pve_setup", None) == (wanted, room.map_id, room.seed)

    # -------------------------------------------------------------- views
    def _pointer(self):
        """Where the mouse rests; None on touch, where nothing hovers."""
        touch = getattr(self, "touch", None)
        if touch is not None and touch.active:
            return None
        try:
            return self.logical_pos(self.mouse_pos())
        except Exception:
            return None

    def _touch_ui(self):
        touch = getattr(self, "touch", None)
        return bool(self.state.get("touch_mode") or (touch is not None and touch.active))

    def _guest(self):
        return bool(self.room and self.mode == "guest")

    def _panel(self, r, name, rect, edge):
        if not r.native_frame(name, rect, edge):
            r.box(rect)

    def draw_pve(self, r):
        """The original seed selection: seed bank on top, 选卡板 on the left,
        开始干 / 返回菜单 plaques at the bottom right (main loop offset 48810)."""
        state = self.state
        campaign = self.campaign
        coop = state.get("pve_coop")
        # Co-op guests see the host pool and capacity with their own selection.
        room_day = self.pve_room_day()
        shown_day = room_day or campaign.day
        capacity = self.pve_deck_capacity()
        st = Stage(r)
        r.start("", "")
        r.native_hover = ("pve_toggle", "pve_reward", "pve_start", "pve_back")
        pointer = self._pointer()
        guest = self._guest()
        fs = st.font()
        # Seed bank (总板): 阳光板 then one 卡槽 per slot, the deck on it. The
        # bar grows with the slots bought in Dave's shop (up to 13) instead of
        # letting the last cards run off the stage.
        slots = max(capacity, len(campaign.deck))
        bank = seed_bank_layout(st, slots)
        r.native_seed_bank(bank["rect"], slots)
        sun = str(campaign.start_sun())
        sx = round(bank["rect"][0] + .75 * bank["unit_x"])
        sy = round(bank["rect"][1] + 1.05 * bank["unit_y"])
        r.text(sun, (sx - r.text_size(r.font(fs), sun)[0] // 2, sy), BLACK, fs)
        for i, key in enumerate(campaign.deck):
            rect = bank["cards"][i]
            r.seed_packet(key, rect)
            r.controls.append((r.pg.Rect(bank["slots"][i]), ("pve_toggle", key)))
        # 选卡板 with every owned card, 8 to a row.
        native_image(r, "选卡板", st.rect(0, 1.5, 8.6, 8.55))
        hovered = None
        if campaign.rewards:
            label(r, "第 %d 天通过！选一张新植物收下：" % campaign.day, st.pos(.45, 2.0), WHITE, fs, BLACK, int(7.9 * st.u))
            for i, key in enumerate(campaign.rewards):
                rect = st.rect(.55 + i * 2.75, 3.0, CARD_W * 1.5, CARD_H * 1.5)
                r.seed_packet(key, rect)
                hit = r.pg.Rect(rect)
                if pointer is not None and hit.collidepoint(pointer):
                    card_glow(r, rect)
                    hovered = key
                r.controls.append((hit, ("pve_reward", key)))
                label(r, CARDS[key]["name"], st.pos(.55 + i * 2.75, 5.1), WHITE, fs, BLACK, int(2.6 * st.u))
            r.button("跳过奖励", st.rect(.55, 8.7, 3, .9), ("pve_reward", None), size=fs)
            focus = hovered or state.get("pve_pick_reward")
            if focus in CARDS and state.get("pve_reward_detail") != focus:
                state.update(pve_reward_detail=focus, pve_reward_scroll=0)
            focus = state.get("pve_reward_detail")
            if focus in campaign.rewards:
                detail_panel(r, st, card_lines(focus), st.rect(.35, 5.55, 7.9, 3.05), "pve_reward_scroll", state, fs)
        else:
            cards = campaign.available_unlocked()
            rows = 6 if len(cards) <= 48 else 5
            per_page = rows * 8
            page = max(0, min(state.get("pve_page", 0), max(0, (len(cards) - 1) // per_page)))
            state["pve_page"] = page
            for l, key in enumerate(cards[page * per_page:(page + 1) * per_page]):
                x, y = (l % 8) + .32, 2.05 + (l // 8) * 1.3
                rect = st.rect(x, y, CARD_W, CARD_H)
                r.seed_packet(key, rect)
                if key in campaign.deck:
                    native_image(r, "植物卡黑", st.rect(x, y, 1.5, 1.5), alpha=100)
                    native_image(r, "植物卡黑", st.rect(x, y, 1.5, 1.5), alpha=100)
                hit = r.pg.Rect(st.rect(x, y, 1, 1.3))
                if pointer is not None and hit.collidepoint(pointer) and key not in campaign.deck:
                    card_glow(r, st.rect(x, y, 1.5, 1.5))
                    hovered = key
                r.controls.append((hit, ("pve_toggle", key)))
            if per_page < len(cards):
                r.button("上一页", st.rect(.4, 8.7, 2.6, .9), ("pve_page", -1), active=page > 0, size=fs)
                r.button("下一页", st.rect(3.2, 8.7, 2.6, .9), ("pve_page", 1),
                         active=(page + 1) * per_page < len(cards), size=fs)
                label(r, "%d / %d" % (page + 1, (len(cards) - 1) // per_page + 1), st.pos(6.2, 8.85), WHITE, fs, BLACK)
        if hovered and pointer is not None:
            name = CARDS[hovered]["name"]
            width = r.text_size(r.font(fs), name)[0]
            px = max(2, min(st.width - width - 2, int(pointer[0] - width / 2)))
            label(r, name, (px, int(pointer[1] + .3 * st.u)), WHITE, fs, BLACK)
        self._draw_day_board(r, st, campaign, coop, fs, shown_day)
        # Plaques: 开始干 (16.5, 9.75 on a 720-high screen), 返回菜单 beside it.
        bottom = st.rows - 1.5
        # The day is started by the host; a co-op guest fills its own slots and
        # confirms, so the board, the shop and the reward pick stay usable.
        start_here = not guest and not self.pve_room_day()
        ready = bool(campaign.deck) and not campaign.rewards and start_here
        if ready:
            plaque(r, st, "开始干", "第 %d 天-作战" % shown_day, 16.5, bottom, ("pve_start",), pointer, fs)
        back_caption = "返回准备界面" if coop and state.get("pve_return") == "room" else "返回菜单"
        plaque(r, st, "返回菜单", back_caption, 13.25, bottom, ("pve_back",), pointer, fs)
        room_guest = self.mode=='guest' and coop
        r.button("戴夫的商店", st.rect(9.6, bottom, 3.2, 1), ("pve_shop",), size=fs)
        reset_label = ('确认重置' if state.get('pve_reset') else '重置选卡') if room_guest else ('确认重开' if state.get('pve_reset') else '重开闯关')
        if coop and self.mode=='host':reset_label='确认重开' if state.get('pve_reset') else '重开合作挑战'
        r.button(reset_label, st.rect(17.0, 1.75, 2.6, .8), ("pve_reset",),
                 selected=bool(state.get("pve_reset")), size=max(11, fs - 2))
        if not guest and not campaign.rewards:
            from .pve import SKIP_PRICE
            armed = time.monotonic() - state.get("pve_skip_armed", -10.) <= 4.
            r.button(("确认跳关" if armed else "$%d 跳关" % SKIP_PRICE), st.rect(14.2, 1.75, 2.6, .8), ("pve_skip",),
                     selected=armed, size=max(11, fs - 2))
        message = state.get("message", "")
        if message:
            label(r, message, st.pos(9.2, bottom - 1.15), WHITE, fs, BLACK, int(10.6 * st.u))

    def _draw_day_board(self, r, st, campaign, coop, fs, day=None):
        """Today's facts and the zombies that may come, beside the board."""
        day = campaign.day if day is None else day
        source, name, night = map_for_day(day, coop)
        if source == "team":
            from .team_maps import bundled_index
            name = next((e["name"] for e in bundled_index() if e["id"] == name), name)
        unlocks=COOP_TIER_UNLOCK_DAY if coop else TIER_UNLOCK_DAY
        tiers = [TIER_NAMES[t] for t, unlock in sorted(unlocks.items()) if day >= unlock]
        lines = ["%d 波僵尸 · 出没：%s" % (waves_for_day(day), "、".join(tiers)),
                 "初始阳光 %d · 卡槽 %d（商店已加 %d）" % (campaign.start_sun(), self.pve_deck_capacity(), campaign.extra_slots),
                 "金币 $%d · 最佳第 %d 天" % (campaign.coins, campaign.best_day),
                 "花盆、睡莲、咖啡豆也在选卡板上，选中后各占一个卡槽"]
        upcoming = [TIER_NAMES[t] + "（第 %d 天）" % unlock for t, unlock in sorted(unlocks.items())
                    if day < unlock]
        if upcoming:
            lines.append("即将出现：" + upcoming[0])
        if coop:
            lines.append("合作：各自产阳光；天降阳光与金币共用；全员无人阵亡通关额外 $50")
        x, y = st.pos(9.2, 2.75)
        width = int(10.5 * st.u)
        big = int(fs * 1.25)
        label(r, ("双人合作 · " if coop else "") + "第 %d 天" % day,
              st.pos(9.2, 1.65), WHITE, big, BLACK, int(7.5 * st.u))
        label(r, name + ("（夜）" if night else ""), st.pos(9.2, 2.2), WHITE, fs, BLACK, int(7.5 * st.u))
        self._draw_population_limit(r,st,9.2,2.7,10.5,fs)
        y=st.pos(0,3.5)[1]
        for line in wrap_px(r, lines, width, fs):
            label(r, line, (x, y), WHITE, fs, BLACK, width)
            y += int(fs * 1.35)
        # The day's zombie pool, one of each tier that has arrived.
        shown = []
        for tier, unlock in sorted(TIER_UNLOCK_DAY.items()):
            if day >= unlock:
                shown += ["zombie:" + n for n in TIERS[tier][:3] if "zombie:" + n in CARDS]
        shown = shown[-8:]
        ground = st.rows - 2.9
        for i, key in enumerate(shown):
            r.icon(card_art_name(CARDS[key]), st.rect(9.4 + i * 1.3, ground - 1.6, 1.2, 1.6))

    def draw_pve_shop(self, r):
        """Crazy Dave's car boot as in the original (main loop 161052-168824):
        the 商店 backdrop drawn whole, upgrades on the lid at y 1.8, plants on
        the shelf at (9.5 + 2i, 4.6), prices above, the description under the
        pointer, 走啦 top left and the 钱袋 bottom left."""
        state = self.state
        campaign = self.campaign
        st = Stage(r, bottom=True)
        r.start("", "")
        r.native_hover = ("pve_item", "pve_buy", "pve_shop_back")
        # Crazy Dave stands by his car; the boot art itself is drawn whole.
        r.icon("疯狂戴夫", st.rect(3.6, 4.3, 3.6, 6.9))
        native_image(r, "商店", st.rect(0, 0, STAGE_W, STAGE_H))
        pointer = self._pointer()
        touch = self._touch_ui()
        guest = self._guest()
        fs = st.font()
        shop = campaign.shop
        positions = shop_positions(shop)
        focus = state.get("pve_pick") if touch else None
        if not touch and pointer is not None:
            for i, (item, (x, y)) in enumerate(zip(shop, positions)):
                if not item["sold"] and r.pg.Rect(st.rect(x, y, 1, 1.3)).collidepoint(pointer):
                    focus = i
        if not isinstance(focus, int) or not 0 <= focus < len(shop) or shop[focus]["sold"]:
            focus = None
        for i, (item, (x, y)) in enumerate(zip(shop, positions)):
            lift = -.2 if i == focus else 0.
            draw_item(r, st, item, x, y + lift)
            if item["sold"]:
                if item["kind"] != "secret":
                    native_image(r, "植物卡黑", st.rect(x, y, 1.5, 1.5), alpha=100)
                label(r, "已售", st.pos(x + .15, y + .5), RED, fs, BLACK)
                continue
            color = WHITE if i == focus else BLACK
            if campaign.coins < item["price"]:
                color = RED
            dx = .1 if len(str(item["price"])) >= 4 else .2
            label(r, "$%d" % item["price"], st.pos(x + dx, y - .5 + lift), color, fs,
                  WHITE if color == BLACK else BLACK)
            if not guest:
                r.controls.append((r.pg.Rect(st.rect(x, y, 1, 1.3)), ("pve_item", i)))
        if focus is not None and state.get("pve_detail") != focus:
            state.update(pve_detail=focus, pve_detail_scroll=0)
        detail = state.get("pve_detail")
        if isinstance(detail, int) and 0 <= detail < len(shop):
            lines = item_lines(shop[detail], campaign)
            if shop[detail]["sold"]:
                lines = lines + ["已售"]
            elif campaign.coins < shop[detail]["price"]:
                lines = lines + ["价格 $%d · 还差 $%d" % (shop[detail]["price"], shop[detail]["price"] - campaign.coins)]
            else:
                lines = lines + ["价格 $%d" % shop[detail]["price"]]
            top = int(1.8 * st.u)
            panel = (int(st.ox + .3 * st.u), top, int(6.5 * st.u), int(st.height - .9 * st.u) - top)
            detail_panel(r, st, lines, panel, "pve_detail_scroll", state, fs)
        if focus is not None:
            x, y = positions[focus]
            anchor = pointer if pointer is not None and not touch else st.pos(x + .5, y + 1.15)
            description(r, item_lines(shop[focus], campaign), anchor, st, fs)
        elif touch and not guest:
            label(r, "点一下商品看说明，再点一下买下", st.pos(8.0, .65), WHITE, fs, BLACK)
        # 走啦 (0.5, 0.5) and the 钱袋 (0.1, 总高 - 0.6) hang on the window corners.
        back = r.pg.Rect(int(st.ox + .5 * st.u), int(.5 * st.u), int(3 * st.u), int(st.u))
        over = pointer is not None and back.collidepoint(pointer)
        native_image(r, "走啦-选中" if over else "走啦", tuple(back))
        r.controls.append((back, ("pve_shop_back",)))
        bag = (int(st.ox + .1 * st.u), int(st.height - .6 * st.u), int(2 * st.u), int(.5 * st.u))
        native_image(r, "钱袋", bag)
        broke = state.get("pve_broke_until", 0) - time.monotonic()
        color = RED if broke > 0 and int(broke * 3) % 2 == 0 else WHITE
        money = "$%d" % campaign.coins
        width = r.text_size(r.font(fs), money)[0]
        r.text(money, (int(st.ox + 1.92 * st.u) - width, int(st.height - .52 * st.u)), color, fs)
        if guest:
            label(r, "房主的商店：只有房主可以购买", st.pos(8.0, .65), WHITE, fs, BLACK)

    def draw_pve_result(self, r, view):
        """The day's tally on the original 选卡板, plaques underneath."""
        st = Stage(r)
        r.start("", "")
        result = view.get("result") or {}
        won = result.get("winner") == "plant"
        day = result.get("pve_day", "?")
        fs = st.font()
        pointer = self._pointer()
        native_image(r, "选卡板", st.rect(1.0, 1.0, 8.6, 8.55))
        label(r, "第 %s 天 · %s" % (day, "通关！" if won else "失败"), st.pos(1.6, 1.7), WHITE, int(fs * 1.4), BLACK)
        label(r, "全部僵尸已消灭" if won else "所有戴夫阵亡；拾取的金币仍然保留", st.pos(1.6, 2.5), WHITE, fs, BLACK,
              int(7.6 * st.u))
        native_image(r, "钱袋", st.rect(1.6, 3.3, 2, .5))
        income = self.state.get("pve_income") or {}
        if income.get("day") == day and income.get("winner") == result.get("winner"):
            summary = "入账 $%d" % income["total"]
            detail = "拾取 %d + 通关奖励 %d（获取已折半）" % (income["coins"], income["bonus"])
            half = income.get("coin_half", 0)
        else:
            # Before the local callback has settled, show only the exact half
            # pickup amount. Never present the original full-value counter.
            summary = "本局拾取 $" + half_coin_text(result.get("coins", 0))
            detail = "金币获取已折半，尾数随结算累计"
            half = int(result.get("coins", 0) or 0) % 2
        label(r, summary, st.pos(3.75, 3.33), WHITE, max(11, fs - 2), BLACK, int(5.2 * st.u))
        label(r, detail, st.pos(1.6, 3.95), WHITE, max(11, fs - 3), BLACK, int(7.6 * st.u))
        if half:
            label(r, "余 0.5 金币随结算保留，下次累计入账", st.pos(1.6, 4.4), GOLD, max(11, fs - 3), BLACK, int(7.6 * st.u))
        battle = view.get("battle") or {}
        y = 5.0
        for seat in view.get("seats") or ("plant",):
            # local_perspective exchanges secondary / primary player keys for
            # the HUD, but members and profile names still use authority seats.
            key = seat
            local = battle.get("local_seat")
            players = battle.get("players", {})
            team = team_of(local) if local else None
            if local and local != team and local in players and team in players:
                if seat == team:
                    key = local
                elif seat == local:
                    key = team
            p = players.get(key, {})
            stats = p.get("stats", {})
            member = next((peer for peer, s in view.get("members", {}).items() if s == seat), None)
            name = view.get("player_profiles", {}).get(member, {}).get("name", "戴夫")
            label(r, name, st.pos(1.6, y), WHITE, fs, BLACK, int(7.6 * st.u))
            label(r, "阳光收入 %d · 消费 %d" % (stats.get("earned", 0), stats.get("spent", 0)),
                st.pos(1.6, y + .45), WHITE, fs, BLACK, int(7.6 * st.u))
            label(r, "拾币 %s · 剩余生命 %d" % (half_coin_text(stats.get("coins", 0)), max(0, p.get("hp", 0))),
                st.pos(1.6, y + .9), WHITE, fs, BLACK, int(7.6 * st.u))
            y += 1.6
        host = self.mode in ("host", "local")
        bottom = st.rows - 1.5
        if host:
            if self.campaign.rewards:
                plaque(r, st, "开始干", "领奖励", 16.5, bottom, ("pve_open",), pointer, fs)
            else:
                plaque(r, st, "开始干", "第 %d 天-作战" % self.campaign.day, 16.5, bottom, ("pve_start",), pointer, fs)
            r.button("选卡 · 商店", st.rect(9.6, bottom, 3.2, 1), ("pve_open",), size=fs)
        else:
            label(r, "等待房主开始下一天……", st.pos(9.6, bottom + .2), WHITE, fs, BLACK)
        plaque(r, st, "返回菜单", "离开", 13.25, bottom, ("leave",), pointer, fs)
        message = self.state.get("message", "")
        if message:
            label(r, message, st.pos(10.0, 8.0), WHITE, fs, BLACK, int(9.6 * st.u))

    def draw_coop_entry(self, r):
        """Create or join a co-op room, in the PvE pages' original look:
        走啦 top left, two 选卡板 boards (create / join), arrow plaques to go."""
        state = self.state
        st = Stage(r)
        r.start("", "")
        r.native_hover = ("coop_back", "coop_create", "coop_join")
        pointer = self._pointer()
        fs = st.font()
        back = r.pg.Rect(int(st.ox + .5 * st.u), int(.5 * st.u), int(3 * st.u), int(st.u))
        native_image(r, "走啦-选中" if pointer is not None and back.collidepoint(pointer) else "走啦", tuple(back))
        r.controls.append((back, ("coop_back",)))
        label(r, "双人合作", st.pos(4.0, .45), WHITE, int(fs * 1.5), BLACK)
        label(r, "两名植物戴夫并肩闯关 · 房主决定天数，双方各自成长", st.pos(4.0, 1.2), WHITE, fs,BLACK,
              int(10.0 * st.u))
        cloud=state.get('network_mode')=='relay'
        r.button('云端房间 / 切换直连' if cloud else '局域网 / IPv6 / 切换云端',
                 st.rect(14.0,1.1,5.1,.7),('coop_network',),size=max(11,fs-2))
        width = int(9.1 * st.u)
        for i, title in enumerate(("创建合作房间", "加入队友的房间")):
            x = .35 + i * 9.8
            frame = st.rect(x, 2.0, 9.1, 6.4)
            if not r.native_frame("选卡板", frame, 8):
                r.box(frame)
            label(r, title, st.pos(x + .4, 2.35), WHITE, int(fs * 1.2), BLACK)
        # create
        r.icon("疯狂戴夫", st.rect(.8, 3.0, 1.5, 1.5))
        r.icon("疯狂戴夫", st.rect(2.3, 3.0, 1.5, 1.5), flip=True)
        y = st.pos(0, 3.2)[1]
        instructions=(["把邀请码发给队友，", "也可设为公开，在大厅等待队友。"] if cloud else
                      ["把主机地址和邀请码", "发给同一局域网或IPv6网络的队友。"])
        for line in wrap_px(r, instructions, int(5.0 * st.u), fs):
            label(r, line, (st.pos(4.0, 0)[0], y), WHITE, fs, BLACK)
            y += int(fs * 1.3)
        label(r, "房间名称：" if cloud else "监听端口：", st.pos(.8, 4.55), WHITE, fs, BLACK)
        name_box = r.pg.Rect(st.rect(.8, 4.95, 8.2, .75))
        host_field='room_name' if cloud else 'port'
        focused = state.get("focus") == host_field
        r.box(tuple(name_box), (25, 18, 12), border=(250, 210, 89) if focused else (150, 110, 60))
        room_name = str(state.get(host_field) or "")
        r.text(room_name or "例如：一起守住戴夫", (name_box.x + 10, name_box.y + (name_box.h - fs) // 2),
               (255, 239, 199) if room_name else (170, 150, 120), fs, name_box.w - 20)
        r.controls.append((name_box, ("focus", host_field)))
        public = state.get("room_public", True)
        if cloud:
            r.button("公开房间 · 大厅可见" if public else "私有房间 · 仅凭邀请码加入", st.rect(.8, 5.75, 8.2, .65),
                     ("relay_visibility",), size=fs)
        else:
            label(r,'私有直连房间 · 凭主机地址和邀请码加入',st.pos(.8,5.85),WHITE,fs,BLACK,int(8.2*st.u))
        self._draw_population_limit(r,st,.8,6.45,8.2,fs)
        r.button("创建房间",st.rect(6.0,7.2,3,1),("coop_create",),size=fs)
        # join
        label(r, "输入 10 位邀请码：" if cloud else "主机地址（IPv4 或 [IPv6]:端口）：", st.pos(10.6, 3.15), WHITE, fs, BLACK)
        box = r.pg.Rect(st.rect(10.6, 3.75, 8.3, .9))
        join_field='token' if cloud else 'address'
        focused = state.get("focus") == join_field
        r.box(tuple(box), (25, 18, 12), border=(250, 210, 89) if focused else (150, 110, 60))
        token = state.get(join_field) or ""
        default_port=state.get('port') or '24561'
        r.text(token or ("例如：0123ABCDXY" if cloud else "192.168.1.2:%s / [::1]:%s"%(default_port,default_port)), (box.x + 10, box.y + (box.h - fs) // 2),
               (255, 239, 199) if token else (170, 150, 120), fs + 2, box.w - 20)
        r.controls.append((box, ("focus", join_field)))
        if cloud:
            r.button("浏览公开大厅", st.rect(10.6, 5.6, 8.2, .85), ("relay_lobby",), size=fs)
        else:
            label(r,'主机生成的6位邀请码：',st.pos(10.6,4.85),WHITE,fs,BLACK)
            code_box=r.pg.Rect(st.rect(10.6,5.35,8.2,.85))
            r.box(tuple(code_box),(25,18,12),border=(250,210,89) if state.get('focus')=='token' else (150,110,60))
            r.text(state.get('token') or '填写主机的邀请码',(code_box.x+10,code_box.y+8),WHITE,fs,code_box.w-20)
            r.controls.append((code_box,('focus','token')))
        r.button("凭码观战", st.rect(10.6, 6.55, 3.4, .65), ("coop_spectate",), size=fs)
        plaque(r, st, "开始干", "凭码加入", 15.85, 7.2, ("coop_join",), pointer, fs)
        # The co-op fixed room heads the public list, drawn like any public room.
        from .lobby_room import AI_COOP_ROOM_NAME
        from .catalog import RULES
        row = st.rect(.35, 8.65, 18.6, 1.15)
        if not r.native_frame("选卡板", row, 8):
            r.box(row)
        label(r, AI_COOP_ROOM_NAME, st.pos(.75, 8.75), WHITE, fs, BLACK, int(12 * st.u))
        label(r, RULES["build"] + " · 公开房间 · 等待加入", st.pos(.75, 9.25), (230, 220, 190), max(11, fs - 3), BLACK)
        r.button("加入", st.rect(16.2, 8.8, 2.4, .85), ("ai_room", "coop"), size=fs)
        relay = state.get("relay_endpoint") or "未设置（在联机对战的设置中填写）"
        label(r, "中继地址：" + relay if cloud else '局域网填写主机内网地址；IPv6直连填写 [IPv6]:端口。',
              st.pos(.4, 9.95), WHITE, max(11, fs - 3), BLACK, width * 2)
        message = state.get("message", "")
        if message:
            label(r, message, st.pos(.4, 10.45), WHITE, fs, BLACK, int(19 * st.u))

    def draw_coop_room(self, r, view):
        """The co-op room before a day: the day's deck on the original seed
        bar, both Daves on 选卡板 frames with their state, plaques to start or
        leave. Host and guest see their own actions; chat stays bottom left."""
        state = self.state
        st = Stage(r)
        r.start("", "")
        r.native_hover = ("pve_start", "confirm_map", "leave")
        pointer = self._pointer()
        fs = st.font()
        mode = view.get("mode") or COOP
        pve = view.get("pve")
        host = bool(view.get("can_kick"))
        watching=bool(view.get('spectating'))
        # Each Dave sees the cards they selected, including while the host is
        # acknowledging the latest deck. Observers see the host's prepared deck.
        local_seat = (view.get("members") or {}).get(self.peer_id)
        own_deck = self.mode in ("host", "guest") and team_of(local_seat) == "plant" and (self.mode != 'guest' or bool(pve))
        deck = [] if watching else list(self.campaign.deck if own_deck else (pve or {}).get("deck") or [])
        slots = max(self.pve_deck_capacity() if own_deck else int((pve or {}).get("slots") or 0), len(deck), 4)
        bank = seed_bank_layout(st, slots)
        r.native_seed_bank(bank["rect"], slots)
        sun = str(((pve or {}).get('seat_start_sun') or {}).get(local_seat, (pve or {}).get("start_sun", 150)))
        sx = round(bank["rect"][0] + .75 * bank["unit_x"])
        sy = round(bank["rect"][1] + 1.05 * bank["unit_y"])
        r.text(sun, (sx - r.text_size(r.font(fs), sun)[0] // 2, sy), BLACK, fs)
        for i, key in enumerate(deck[:slots]):
            r.seed_packet(key, bank["cards"][i])
        wide_bank = bank["rect"][0] + bank["rect"][2] > st.pos(12., 0)[0]
        if wide_bank:
            # An expanded bank fills the top row. Keep headings below it so
            # they cannot paint over the later cards.
            label(r, MODE_LABELS.get(mode, "双人合作"), st.pos(10.0, 1.65), WHITE, int(fs * 1.3), BLACK)
        else:
            left = (bank["rect"][0] + bank["rect"][2] - st.ox) / st.u + .6
            label(r, MODE_LABELS.get(mode, "双人合作"), st.pos(max(left, 12.0), .3), WHITE, int(fs * 1.3), BLACK)
            label(r, ("第 %d 天已选定" % pve["day"]) if pve else "等待房主选择天数与卡组",
                  st.pos(max(left, 12.0), 1.0), WHITE, fs, BLACK)
        # The two Daves.
        seats = view.get("seats") or ("plant", "plant2")
        members = view.get("members", {})
        connected = view.get("connected", {})
        confirmed = view.get("confirmed", {})
        for i, seat in enumerate(seats):
            x = .35 + i * 4.4                       # two Daves never share a column
            frame = st.rect(x, 1.9, 4.2, 3.5)
            if not r.native_frame("选卡板", frame, 8):
                r.box(frame)
            member = next((p for p, s in members.items() if s == seat), None)
            name = view.get("player_profiles", {}).get(member, {}).get("name") or ("戴夫" if member else "等待队友加入")
            if member in view.get('ai_peers', ()):name = 'AI · ' + name
            r.icon("疯狂戴夫", st.rect(x + .3, 2.35, 1.3, 2.0), flip=i == 1)
            seat_deck = (pve or {}).get("decks", {}).get(seat) or []
            label(r, "植物%d%s · %d张" % (i + 1, "·房主" if member == "host" else "", len(seat_deck)),
                  st.pos(x + 1.8, 2.25), WHITE, fs, BLACK, int(2.3 * st.u))
            label(r, name, st.pos(x + 1.8, 2.8), (255, 226, 120), fs, BLACK, int(2.3 * st.u))
            if not member:
                status, color = "空位", (200, 190, 170)
            elif not connected.get(member, True):
                status, color = "已断开 · 等待重连", RED
            elif confirmed.get(seat):
                status, color = "已确认", (150, 230, 120)
            else:
                status, color = "待确认", WHITE
            label(r, status, st.pos(x + 1.8, 3.35), color, fs, BLACK, int(2.3 * st.u))
            if host and member and member != "host":
                r.button("请出", st.rect(x + 2.8, 4.55, 1.3, .65), ("kick", member), size=max(11, fs - 2))
            elif host and not member and view.get('can_fill_ai'):
                r.button("AI", st.rect(x + 2.8, 4.55, 1.3, .65), ("fill_ai", seat), size=max(11, fs - 2))
        if view.get('can_change_role'):
            if watching:
                for i,seat in enumerate(view.get('available_seats',())):
                    r.button('入座植物'+('1' if seat=='plant' else '2'),st.rect(.35+i*4.4,5.6,4.2,.7),
                             ('spectator_role','player',seat),size=fs)
            else:
                r.button('转为观战',st.rect(.35,5.6,4.2,.7),('spectator_role','spectator'),size=fs)
        # Day facts and room code on the right.
        x0 = 10.0
        y = 2.3 if wide_bank else 2.0
        if pve:
            source, name, night = map_for_day(pve["day"], True)
            if source == "team":
                from .team_maps import bundled_index
                name = next((e["name"] for e in bundled_index() if e["id"] == name), name)
            tiers = [TIER_NAMES[t] for t, unlock in sorted(COOP_TIER_UNLOCK_DAY.items()) if pve["day"] >= unlock]
            for line in ("第 %d 天 · %s%s" % (pve["day"], name, "（夜）" if night else ""),
                         "%d 波僵尸 · 出没：%s" % (waves_for_day(pve["day"]), "、".join(tiers)),
                         "携带 %d 张卡 · 初始阳光 %d" % (len(deck), pve.get("start_sun", 150)),
                         "各自产阳光；天降阳光与金币共用"):
                label(r, line, st.pos(x0, y), WHITE, fs, BLACK, int(9.6 * st.u))
                y += .5
        if view.get("disconnect_remaining"):
            label(r, "有玩家断线，%d 秒内可重连" % int(view["disconnect_remaining"]), st.pos(x0, y + .1), RED, fs, BLACK)
            y += .55
        if state.get("token"):
            label(r, "邀请码：" + state["token"], st.pos(x0, y + .2), (255, 226, 120), int(fs * 1.15), BLACK)
            r.button("复制邀请码", st.rect(x0 + 5.2, y + .1, 2.6, .7), ("copy_relay_code",), size=max(11, fs - 2))
            y += .9
        if state.get('network_mode')=='direct' and state.get('endpoints'):
            endpoint=state['endpoints'][state.get('endpoint_index',0)%len(state['endpoints'])]
            label(r,'主机地址：'+endpoint,st.pos(x0,y+.1),WHITE,max(11,fs-2),BLACK,int(9.6*st.u))
            r.button('切换地址',st.rect(x0,y+.6,3.,.65),('endpoint',1),size=max(11,fs-2))
            r.button('复制地址',st.rect(x0+3.3,y+.6,3.,.65),('copy_address',),size=max(11,fs-2))
            y+=1.4
        message = state.get("message", "")
        if message:
            label(r, message, st.pos(x0, y + .2), WHITE, fs, BLACK, int(9.6 * st.u))
        # Plaques (bottom right), as on the day-select page.
        bottom = st.rows - 1.5
        if host:
            mine = (view.get("local_seats") or [None])[0]
            if watching:
                plaque(r,st,'开始干','设置第 %d 天' % self.campaign.day,16.5,bottom,('pve_start',),pointer,fs)
            elif pve and confirmed.get(mine) and self.pve_setup_current():
                label(r, "已确认，等待队友确认", st.pos(16.0, bottom + .25), WHITE, fs, BLACK)
            elif pve:
                plaque(r, st, "开始干", "第 %d 天-作战" % pve["day"], 16.5, bottom, ("pve_start",), pointer, fs)
            if not watching:r.button("选卡 · 商店", st.rect(9.6, bottom, 3.2, 1), ("pve_open",), size=fs)
        elif watching:
            label(r,'观战中，可在空位入座',st.pos(9.6,bottom+.25),WHITE,fs,BLACK)
        else:
            local = (view.get("local_seats") or [None])[0]
            if pve and not confirmed.get(local):
                plaque(r, st, "开始干", "确认 · 第 %d 天" % pve["day"], 16.5, bottom, ("confirm_map",), pointer, fs)
            else:
                label(r, "已确认，等待房主开战" if pve else "等待房主选择天数", st.pos(16.0, bottom + .25), WHITE, fs, BLACK)
            # The guest builds its own day deck from its own campaign and buys
            # in its own shop, so the board must be reachable from the room too.
            if pve:
                r.button("选卡 · 商店", st.rect(9.6, bottom, 3.2, 1), ("pve_open",), size=fs)
        plaque(r, st, "返回菜单", "离开", 13.25, bottom, ("leave",), pointer, fs)



def shop_label(item):
    if item["kind"] == "slot":
        return "卡槽 +1"
    if item["kind"] == "sun":
        return "初始阳光 +25"
    return CARDS[item["key"]]["name"] if item.get("key") in CARDS else "?"


def mode_label(view):
    return MODE_LABELS.get(view.get("mode") or DUEL, MODE_LABELS[DUEL])


def seat_name(seat):
    return {"plant": "植物 1", "plant2": "植物 2", "zombie": "僵尸 1", "zombie2": "僵尸 2"}.get(seat, seat)


def is_scripted(view):
    return scripted(view.get("mode") or DUEL)


# ------------------------------------------------------------ original grid
STAGE_W, STAGE_H = 20., 11.25        # the original screen in tiles: 比 = 总宽 // 20
CARD_W, CARD_H = .975, 1.3125        # visible seed envelope (26x35 of the 40px card at 1.5 比)
WHITE, BLACK, RED = (255, 255, 255), (0, 0, 0), (235, 35, 30)
LID, SHELF = 1.8, 4.6                # the boot's lid row and shelf row


def seed_bar_pitch(slots, left=1.5, right=STAGE_W - .6):
    """Original 1u pitch, uniformly fit including the sun panel and tail."""
    slots = max(1, int(slots))
    return min(1., max(.01, (right - left + 1.5) / (slots + 2.5)))


def seed_bank_layout(stage, slots):
    """Cards and disjoint hits mapped from the complete original bank canvas."""
    slots = max(1, int(slots))
    unit = seed_bar_pitch(slots)
    rect = stage.rect(0, 0, (slots + 2.5) * unit, 1.5 * unit)
    x, y, width, height = rect
    ux, uy = width / (slots + 2.5), height / 1.5
    cards, hits = [], []
    for index in range(slots):
        left, right = round(x + (1.5 + index) * ux), round(x + (2.5 + index) * ux)
        cards.append((left, round(y + .1 * uy), max(1, round(CARD_W * ux)), max(1, round(CARD_H * uy))))
        hits.append((left, y, max(1, right - left), height))
    return dict(rect=rect, unit_x=ux, unit_y=uy, cards=cards, slots=hits)


def half_coin_text(raw_coins):
    raw = max(0, int(raw_coins or 0))
    return str(raw // 2) + (".5" if raw % 2 else "")


class Stage:
    """The original's tile grid. One tile (比) is width/20 as in the original,
    capped so the 16:9 stage fits; the stage is centred horizontally and
    anchored to the top (or, for the shop boot, to the bottom) - one uniform
    scale, never a crop of the art's transparent edges."""

    def __init__(self, r, bottom=False):
        width, height = r.screen.get_size()
        self.u = min(width / STAGE_W, height / STAGE_H)
        self.ox = (width - STAGE_W * self.u) / 2.
        self.oy = height - STAGE_H * self.u if bottom else 0.
        self.width, self.height = width, height
        self.rows = (height - self.oy) / self.u        # tiles from the stage top to the window bottom

    def pos(self, x, y):
        return int(round(self.ox + x * self.u)), int(round(self.oy + y * self.u))

    def rect(self, x, y, w, h):
        left, top = self.pos(x, y)
        return left, top, max(1, int(round(w * self.u))), max(1, int(round(h * self.u)))

    def font(self):
        return max(12, int(self.u / 3. * 1.05))      # 小font is 行距 / 2 = 比 / 3


def native_image(r, name, rect, alpha=None):
    """An original ui image stretched whole to its load size (加载游戏 sizes)."""
    image = r.artwork(name)
    if image is None:
        return False
    key = ("native", name, int(rect[2]), int(rect[3]), alpha)
    scaled=r.scaled.get(key)
    if scaled is None:
        scaled = r.pg.transform.scale(image, (int(rect[2]), int(rect[3])))
        if alpha is not None:
            scaled = scaled.copy()
            scaled.set_alpha(alpha)
        r.scaled[key] = scaled
    r.screen.blit(scaled, (int(rect[0]), int(rect[1])))
    return True


def card_glow(r, rect):
    """卡亮: the 植物卡黑 silhouette turned white at alpha 150."""
    key = ("卡亮", int(rect[2]), int(rect[3]))
    glow=r.scaled.get(key)
    if glow is None:
        base = r.artwork("植物卡黑")
        if base is None:
            return
        glow = r.pg.transform.scale(base, (int(rect[2]), int(rect[3]))).copy()
        glow.fill((255, 255, 255, 0), special_flags=r.pg.BLEND_RGBA_MAX)
        glow.set_alpha(150)
        r.scaled[key] = glow
    r.screen.blit(glow, (int(rect[0]), int(rect[1])))


def label(r, text, pos, color, size, outline=None, max_width=None):
    if outline is not None:
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            r.text(text, (pos[0] + dx, pos[1] + dy), outline, size, max_width)
    r.text(text, pos, color, size, max_width)


def plaque(r, st, image, caption, x, y, action, pointer, fs):
    """开始干 / 返回菜单: a 3x1 plaque with its caption just above (offsets 51036-51338)."""
    rect = r.pg.Rect(st.rect(x, y, 3, 1))
    over = pointer is not None and rect.collidepoint(pointer)
    native_image(r, image + ("-选中" if over else ""), tuple(rect))
    # Caption centred above the plaque (the original's sits at x + 0.5), kept on screen.
    width = r.text_size(r.font(fs), caption)[0]
    cx = max(2, min(st.width - width - 2, rect.centerx - width // 2))
    label(r, caption, (cx, st.pos(x, y - .55)[1]), WHITE if over else BLACK, fs, BLACK if over else WHITE)
    r.controls.append((rect, action))


def shop_positions(items):
    """Tile position of each item. The original puts 阳光卡 at (10.5, 1.8),
    卡槽卡 at (12.5, 1.8) and the plants at (9.5 + 2i, 4.6); its secrets take
    the place of a random item. Ours keep two secrets on the lid at 14.5 and
    16.5 so all seven goods have a fixed place."""
    out, plants, secrets = [], 0, 0
    for item in items:
        kind = item["kind"]
        if kind == "sun":
            out.append((10.5, LID))
        elif kind == "slot":
            out.append((12.5, LID))
        elif kind == "plant":
            out.append((9.5 + 2 * min(plants, 3), SHELF))
            plants += 1
        else:
            out.append((14.5 + 2 * min(secrets, 1), LID))
            secrets += 1
    return out


def draw_item(r, st, item, x, y):
    kind = item["kind"]
    if kind == "plant":
        r.seed_packet(item["key"], st.rect(x, y, CARD_W, CARD_H))
    elif kind == "secret":
        r.seed_packet(item["key"], st.rect(x, y, 31 / 40. * 1.5, 32 / 40. * 1.5))
    else:
        native_image(r, "卡槽卡" if kind == "slot" else "阳光卡", st.rect(x, y, 1.5, 1.5))


def wrap(text, width=15):
    lines = []
    for part in str(text).replace("。", "。\n").split("\n"):
        part = part.strip()
        while part:
            lines.append(part[:width])
            part = part[width:]
    return lines


def card_lines(key):
    card = CARDS[key]
    head = card["name"] + ("（秘籍）" if card.get("category") == "secret" else "（阳光 %d）" % card["cost"])
    lines = [head] + wrap(card.get("description") or card.get("native_description") or "")
    dependency = card.get("dependency")
    if dependency in CARDS:
        lines.append("需同时携带前体：" + CARDS[dependency]["name"])
    return lines


def item_lines(item, campaign):
    """The 说明 of a good, as the original reads 卡[l]['说明'] on hover."""
    if item["kind"] == "slot":
        return ["卡槽数+1", "现有 %d 槽" % campaign.slots()]
    if item["kind"] == "sun":
        return ["初始阳光+%d" % SUN_STEP, "现在 %d" % campaign.start_sun()]
    lines = card_lines(item["key"])
    if item["key"] in campaign.unlocked:
        lines.append("已拥有")
    return lines


HOVER_LINES = 5
CLOSING = "，。、；：！？）)」』%,.;:!?"


def wrap_px(r, lines, width, fs):
    """Wrap by rendered width so no line is cut by the renderer's ellipsis."""
    font = r.font(fs)
    out = []
    for line in lines:
        current = ""
        for char in line:
            # Closing punctuation stays on its line instead of starting a new one.
            if current and char not in CLOSING and r.text_size(font, current + char)[0] > width:
                out.append(current)
                current = char
            else:
                current += char
        out.append(current)
    return out


def detail_panel(r, st, lines, rect, scroll_key, state, fs):
    """The full 说明 in a bounded panel; scrolls (wheel / 上翻 下翻) when long.
    Returns (wrapped rows, first shown, count shown)."""
    x, y, w, h = [int(v) for v in rect]
    if not r.native_frame("选卡板", (x, y, w, h), 8):
        r.box((x, y, w, h))
    pad = max(8, int(.28 * st.u))
    step = int(fs * 1.3)
    rows = wrap_px(r, lines, w - 2 * pad, fs)
    visible = max(1, (h - 2 * pad) // step)
    overflow = len(rows) > visible
    if overflow:
        visible = max(1, (h - 2 * pad - int(.75 * st.u)) // step)
    top = max(0, min(int(state.get(scroll_key, 0) or 0), len(rows) - visible))
    state[scroll_key] = top
    for i, row in enumerate(rows[top:top + visible]):
        label(r, row, (x + pad, y + pad + i * step), WHITE, fs, BLACK)
    if overflow:
        bh = int(.6 * st.u)
        by = y + h - pad - bh
        bw = int(1.5 * st.u)
        r.button("上翻", (x + w - pad - 2 * bw - 6, by, bw, bh), ("pve_scroll", scroll_key, -max(1, visible - 1)),
                 active=top > 0, size=max(11, fs - 3))
        r.button("下翻", (x + w - pad - bw, by, bw, bh), ("pve_scroll", scroll_key, max(1, visible - 1)),
                 active=top + visible < len(rows), size=max(11, fs - 3))
        label(r, "%d-%d / %d 行" % (top + 1, min(len(rows), top + visible), len(rows)), (x + pad, by + 4),
              WHITE, max(11, fs - 3), BLACK)
    return rows, top, min(visible, len(rows))


def description(r, lines, anchor, st, fs):
    """White lines under the pointer (offset 167416), kept inside the window.
    Long texts show their head here; the detail panel holds all of it."""
    if len(lines) > HOVER_LINES:
        lines = lines[:HOVER_LINES - 1] + ["……完整说明见左侧面板"]
    font = r.font(fs)
    width = max(r.text_size(font, line)[0] for line in lines)
    step = int(fs * 1.25)
    x = max(4, min(st.width - width - 4, int(anchor[0] - width / 2)))
    y = int(anchor[1] + .3 * st.u)
    y = max(4, min(st.height - step * len(lines) - 4, y))
    for line in lines:
        label(r, line, (x, y), WHITE, fs, BLACK)
        y += step
