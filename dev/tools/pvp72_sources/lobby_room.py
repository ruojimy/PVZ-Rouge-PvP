# -*- coding: utf-8 -*-
"""The fixed 「你打不过我你信吗」 lobby room: an offline host room whose other seats are AI.

Nothing here touches the network. The room is a normal host-mode Room without a
transport, so the player keeps every host control (map, seed, weather, side swap,
ranked/extra-slot options, spectating) and every result option (same deck, same
side, swapped side, back to the room to pick another map). AI seats join as local
peers (one, plus a second while the host spectates; relay-style 'peer-…' ids) and act only through
Room.command, the same path a remote player uses. Draft, ready, confirm and
rematch actions wait a random, human-looking delay; drafting runs on a worker
thread so the window never freezes while the AI thinks.
"""
import json
import math
import random
import threading
import traceback

AI_ROOM_NAME = '你打不过我你信吗'
# PvP66: a 2v2 room in the same lobby; the three other seats behave like the 1v1 one.
AI_DUO_ROOM_NAME = '[2v2] 四人开黑缺你一个'
# PvP66: a co-op campaign room listed on the co-op page; the second plant seat
# is taken the same way (the host keeps the campaign, shop and day start).
AI_COOP_ROOM_NAME = '[合作] 一起闯关来个搭档'
SLOTS = ('main', 'spare')      # 'spare' only sits down while the host watches
RECORD_FILE = 'rival_record.json'
STAR_NAME = '张雪碧'
STAR_RATE = .25
NAMES = ('王可乐', '李芬达', '赵冰红茶', '陈酸梅汤', '周豆浆', '吴椰汁', '孙北冰洋', '钱橙汁', '郑绿茶', '冯美年达',
         '种豆得豆', '僵尸不吃辣', '夜猫子戴夫', '向日葵大王', '坚果墙墙', '豌豆射不准', '墓碑守夜人', '樱桃小炸',
         '阿呆的锅', '菜狗也想赢', '小鬼当家', '撑杆跳跳', '玉米加农炮手', '今天不上分', '路障张三', '铁桶李四',
         '晚安蘑菇', '阳光收集者', '大喷菇不喷', '冰瓜冰冰', '倭瓜压一压', '寒冰射手小王', '花盆里的猫',
         'ZzBrain', 'sunflower77', 'PeaShooter', 'Dave_Crazy', 'gargantuar', 'imp_rush', 'Lily_pad')
ANDROID_CONTROL_HZ = 10.
DESKTOP_CONTROL_HZ = 15.


DIAGNOSTIC_FILE = 'diagnostics/fixed-room.log'
DIAGNOSTIC_LIMIT = 256 * 1024


def diagnose(app, text):
    """Engineering details of a seat controller error go to a diagnostic file
    in the player folder (never on screen; the seat simply retries)."""
    try:
        path = app.profiles.folder() / DIAGNOSTIC_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and path.stat().st_size > DIAGNOSTIC_LIMIT:
            path.replace(path.with_suffix('.old.log'))
        import time
        with path.open('a', encoding='utf-8') as fh:
            fh.write('--- %s\n%s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), text))
    except Exception:
        traceback.print_exc()


def ai_name(rng, avoid=()):
    if rng.random() < STAR_RATE and STAR_NAME not in avoid:
        return STAR_NAME
    pool = [n for n in NAMES if n not in avoid]
    return rng.choice(pool or NAMES)


def human_delay(rng, kind):
    """Seconds a person would plausibly take; log-normal around a per-action median."""
    median, low, high = {'ban': (4.5, 1.6, 13.), 'pick': (6., 2., 16.), 'secret': (3., 1.2, 9.),
                         'confirm': (1.8, .7, 5.), 'ready': (2.4, .9, 7.), 'rematch': (2.5, 1., 6.),
                         'restart': (2., .8, 5.), 'spectate_rematch': (7., 5., 11.),
                         'arrive': (3.5, 1.5, 9.)}[kind]
    return max(low, min(high, rng.lognormvariate(math.log(median), .45)))


class SeatDraftView(object):
    """2v2: the room as one seat's drafter sees it - its own deck under its
    faction, both enemy decks merged, cards only the teammate may hold treated
    as banned. Legality questions go to the real room."""

    def __init__(self, room, seat):
        self.team_draft = True
        self.refresh(room, seat)

    def refresh(self, room, seat):
        from .catalog import team_repeatable
        from .teams import team_of
        self._room = room
        view = room.advisor_view(seat)
        self.seat = seat
        # 2v2: the teammate's own deck, for complementing its roles (AI team66).
        self.team_mate_deck = list(room.mate_deck(seat)) if room.mode != 'duel' else []
        self.decks = view['decks']
        self.bans = view['bans']
        self.map, self.rules = room.map, room.rules
        self.draft_index, self.draft_schedule = room.draft_index, room.draft_schedule
        self.revision = room.revision

    def __getattr__(self, name):
        return getattr(self._room, name)


class AISeat(object):
    """One AI-controlled peer of the room (its side follows swaps and rematches)."""

    def __init__(self, owner, peer, name):
        self.owner = owner
        self.peer = peer
        self.name = name
        self.rng = random.Random()
        self.agent = None
        self.agent_key = None
        self.clock = 0.
        self.wait = {}               # trigger key -> time the action may happen
        self.thinking = None         # (key, thread, box)
        self.seq = {}
        self.next_ctl = 0.
        self.plan = None
        self.plan_at = -1e9
        self.field = None
        self.builder = None
        self.shots = None
        self.battle_key = None
        self.was_paused = False
        self.failures = 0
        self.retry_at = 0.

    @property
    def app(self):
        return self.owner.app

    @property
    def room(self):
        return self.app.room

    def side(self):
        """The seat (plant2 / zombie2 in 2v2)."""
        return self.room.side_for(self.peer) if self.room else None

    def team(self):
        from .teams import team_of
        return team_of(self.side())

    def cmd(self, payload):
        room = self.room
        payload = dict(payload)
        payload.setdefault('revision', room.revision)
        return room.command(self.peer, payload)

    def send(self, side, kind, **data):
        # The brain speaks for its faction; the room knows this peer's seat.
        seat = self.side() or side
        self.seq[seat] = self.seq.get(seat, 0) + 1
        return self.cmd({'type': 'input', 'input': dict(type=kind, seq=self.seq[seat], **data)})

    def due(self, key, kind):
        """True once the human-looking delay for this trigger has elapsed."""
        if key not in self.wait:
            self.wait = {k: v for k, v in self.wait.items() if k[0] == key[0]}
            self.wait[key] = self.clock + human_delay(self.rng, kind)
        return self.clock >= self.wait[key]

    def ensure_agent(self):
        room = self.room
        side = self.team()
        key = (id(room), room.map_id, room.seed, room.map.terrain_hash, self.side(), room.match_number, id(room.draft_schedule))
        if self.agent is None or self.agent_key != key:
            brain = room_brain()
            info = dict(map=room.map_id, night=bool(room.map.environment.get('night')), seed=room.seed,
                        opponent='human', variant='')
            self.agent = brain.make(side, info)
            ctl = getattr(self.agent, 'controller', None)
            if ctl is not None and hasattr(ctl, 'bind'):
                ctl.bind(self.app.bridge, self.send)
            self.agent_key = key
            self.reset_observation()
            battle = getattr(room, 'battle', None)
            seat = self.side()
            if battle is not None and seat is not None and getattr(battle, 'typed_ai_plan', False):
                # A rebuilt agent starts with fresh typed strategy memory (r22 Agent.__init__).
                # Like the observation reset this must not start a cold battle.
                battle.reset_ai_planner(seat)
            if battle is not None and seat is not None and getattr(battle, 'typed_ai_control', False):
                # The typed controller's memory belongs to this agent, like agent.controller.
                battle.reset_ai_controller(seat)
        return self.agent

    def reset_observation(self):
        self.next_ctl = 0.
        self.plan = None
        self.plan_at = -1e9
        self.field = None
        self.builder = None
        self.shots = None
        room = self.room
        battle = getattr(room, 'battle', None) if room is not None else None
        seat = self.side() if room is not None else None
        if battle is not None and seat is not None and getattr(battle, 'typed_ai_observation', False):
            # Reset just this seat's typed histories. This must not start a cold battle.
            battle.reset_ai_observation(seat)

    def safe_tick(self, dt):
        self.clock += dt
        if self.clock < self.retry_at:
            return
        try:
            self.tick()
            self.failures = 0
        except Exception:
            diagnose(self.app, traceback.format_exc())
            self.failures += 1
            self.retry_at = self.clock + min(5., .5 * 2 ** min(self.failures - 1, 4))
            self.reset_observation()
            if self.failures >= 3:
                self.agent = None
            room = self.room
            side = self.side()
            if room and room.phase == 'battle' and side and not room.paused:
                try:
                    self.send(side, 'move', move=0, jump=False)
                except Exception:
                    pass

    # ---------------------------------------------------------------- phases
    def tick(self):
        room = self.room
        side = self.side()
        if room is None or side is None or room.audit_error or not room.connected.get(self.peer):
            return
        phase = room.phase
        if room.mode == 'coop' and phase in ('config', 'result') and room.pve:
            from .coop_ai import preparation_action
            if preparation_action(self):
                return
        if phase != 'battle':
            self.battle_key = None
        if phase == 'config':
            self.thinking = None
            human = self.owner.human_side()
            other_ready = room.confirmed.get(human) if human else True
            if other_ready and not room.confirmed.get(side) and len(room.members) == len(room.seat_list()):
                # A watching host gets time to pick the map before the AIs start.
                if self.due(('confirm', room.revision), 'confirm' if human else 'spectate_rematch'):
                    self.cmd({'type': 'confirm_map', 'terrain_hash': room.map.terrain_hash})
            return
        if phase in ('banning', 'picking'):
            if room.restart_votes and side not in room.restart_votes:
                if self.due(('restart', tuple(sorted(room.restart_votes)), room.draft_index), 'restart'):
                    self.cmd({'type': 'restart'})
                return
            act = room._draft_action()
            mine = act and (act.get('seat') == side if act.get('seat') else
                            act['side'] == self.team() and self.owner.drafter(self.team()) is self)
            if mine:
                self.draft_turn(room, act, self.team())
            elif not act and room.draft_stage == 'complete' and not room.ready.get(side):
                if self.due(('ready', id(room.draft_schedule), room.match_number), 'ready'):
                    self.cmd({'type': 'ready', 'ready': True})
            return
        if phase == 'loading':
            if not room.loaded.get(side):
                self.cmd({'type': 'loaded', 'loading_id': room.loading_id, 'terrain_hash': room.map.terrain_hash})
            return
        if phase == 'battle' and room.battle:
            self.battle_tick(room, side)

    def draft_turn(self, room, act, side):
        key = ('draft', id(room.draft_schedule), room.draft_index)
        kind = 'secret' if act['category'] == 'secret' else act['kind']
        if self.thinking is not None and self.thinking[0]!=key:
            if self.thinking[1].is_alive():return
            self.thinking=None
        if self.thinking is None or self.thinking[0] != key:
            agent = self.ensure_agent()
            box = {}

            view=room
            if room.duo():
                view=getattr(self,'draft_view',None)
                if view is None or view._room is not room or view.seat!=self.side():
                    view=SeatDraftView(room,self.side());self.draft_view=view
                else:view.refresh(room,self.side())

            def think():
                try:
                    box['card'] = agent.draft(view, act)
                except Exception:
                    diagnose(self.app, traceback.format_exc())
                    box['card'] = None
            thread = threading.Thread(target=think, name='PvP-room-draft', daemon=True)
            self.thinking = (key, thread, box)
            thread.start()
        key_, thread, box = self.thinking
        urgent = room.deadline - room.clock < 1.5
        if (not self.due(key, kind) or thread.is_alive()) and not urgent:
            return
        if thread.is_alive():
            box = {}
        card = box.get('card')
        check = room._ban_error if act['kind'] == 'ban' else room._pick_error
        if card is None or check(side, card):
            if act['category'] == 'secret':
                card = None
            elif act['kind'] == 'pick':
                card = room._timeout_pick(act.get('seat') or side)
            else:
                card = next((k for k in sorted(self.owner.cards()) if not room._ban_error(side, k)), None)
        # Retain an overdue worker until it finishes. Replacing its handle
        # every turn formerly left abandoned searches competing for the GIL.
        if not thread.is_alive():self.thinking = None
        self.cmd({'type': act['kind'], 'card': card})

    def battle_tick(self, room, side):
        from .rv_observation import ObservationBuilder
        from .rv_field import Field
        from .rv_realtime_controls import validate_plan, own_counts
        from .rv_native_observation import NativeShotView
        b = room.battle
        seat, side = side, self.team()
        request=b.surrender_requests.get(side)
        if request and request['seat']!=seat and b.time<request['expires']:
            mine=b.players[seat];mate=b.players[request['seat']]
            hopeless=(mine['hp']<mine['max_hp']*.35 and mate['hp']<mate['max_hp']*.35
                      and mine['resource']<75)
            # A human teammate's surrender is theirs to call: the AI seat follows
            # it instead of second-guessing (user report 10-14).  Between AI seats
            # the old hopeless-position test still decides.
            try:
                from .teams import team_of
                requested_seat=request.get('seat')
                follows=(team_of(requested_seat)==side and
                         self.owner.is_human_seat(requested_seat))
            except AttributeError:
                follows=False
            self.send(seat,'surrender_accept' if (hopeless or follows) else 'surrender_decline',request=request['id'])
            if b.result:return
        if not room.paused and room.pause_votes and seat not in room.pause_votes:
            self.cmd({'type':'pause','paused':True,'pause_epoch':room.pause_epoch})
        if room.paused or room.disconnect_deadline is not None:
            self.was_paused = True
            return
        key = (id(room), id(b))
        if self.battle_key != key:
            self.battle_key = key
            self.agent = None
        if self.was_paused:
            self.was_paused = False
            self.reset_observation()
        agent = self.ensure_agent()
        if b.time < self.next_ctl:
            return
        self.next_ctl = b.time + 1. / (ANDROID_CONTROL_HZ if self.app.android else DESKTOP_CONTROL_HZ)
        typed_observer = bool(getattr(b, 'typed_ai_observation', False))
        from .rv_source import BRAIN
        if typed_observer and BRAIN == 'r22' and getattr(b, 'typed_ai_control', False):
            # The whole r22 seat AI runs typed inside the battle: observation, the 1.5 s
            # strategy plan and the controller, on the battle's own facts. No room snapshot,
            # Field or V agent code is built or run here. Every input still leaves through
            # self.send -> Room.command, so the room validates and records it as before.
            every = getattr(agent, 'plan_every', 2.)
            replan = self.plan is None or b.time - self.plan_at >= every
            raw = b.ai_tick(seat, room.match_number, replan, self.send)
            if replan:
                # The fresh typed plan (a dict, as agent.plan returned) keeps AISeat.plan's
                # contract for readers; the controller already ran on the typed plan itself.
                try:
                    self.plan = validate_plan(raw, room.deck_of(seat))
                except ValueError as exc:
                    self.plan_rejections = getattr(self, 'plan_rejections', 0) + 1
                    self.last_plan_error = str(exc)[:200]
                self.plan_at = b.time
            return
        if self.field is None:
            terrain = room.map.to_dict()
            self.field = Field(terrain)
            if not typed_observer:
                # Reference/legacy battle only; the shipped typed battle never runs these algorithms.
                self.builder = ObservationBuilder(side, terrain['width'], terrain['height'], terrain['tile_size'],
                                                  terrain['environment'].get('night', False))
                self.shots = NativeShotView()
        snap = room.snapshot(self.peer, include_map=False, copy_state=False)
        if seat != side:
            from .teams import local_perspective
            snap['battle'] = local_perspective(snap['battle'], seat)
        snap['map'] = b.map
        if typed_observer:
            # Input is a seat and match ID, never the V snapshot. The Session reads typed
            # authoritative objects directly. Only the result crosses back for the still-V
            # r22 planner/controller; moving the whole strategy is a separate step.
            packet = b.ai_observe(seat, room.match_number)
            snap['battle']['projectiles'] = snap['battle'].get('projectiles', []) + packet['projectiles']
            obs = packet['observation']
        else:
            width = snap['map']['width']
            shots = self.shots.sample(b.g.get('实体', []), b.time, width)
            snap['battle']['projectiles'] = (snap['battle'].get('projectiles', [])
                                             + self.shots.visible(shots, snap['battle']['players'][side], width))
            obs = self.builder.build(snap, match_id=room.match_number)
            # 2v2: retain separate per-seat and team counts on the legacy reference path.
            obs['own_card_counts'] = dict(own_counts(snap['battle']['units'], side, seat if room.duo() else None))
            obs['team_card_counts'] = dict(own_counts(snap['battle']['units'], side))
        every = getattr(agent, 'plan_every', 2.)
        if self.plan is None or b.time - self.plan_at >= every:
            if typed_observer and BRAIN == 'r22' and getattr(b, 'typed_ai_plan', False):
                # The r22 strategy runs typed on the battle's own facts for this seat; only the
                # still-V controller's Recovery flag crosses in. The V agent.plan is not run.
                raw = b.ai_plan(seat, bool(getattr(agent.controller, 'recovering', False)))
            else:
                raw = agent.plan(dict(match=self, side=side, snap=snap, obs=obs, plan=self.plan))
            if raw is not None:
                try:
                    # The seat's own deck (plant2/zombie2 differ from seat 1).
                    self.plan = validate_plan(raw, room.deck_of(seat))
                except ValueError as exc:
                    # Keep the previous (validated) plan, but never silently.
                    self.plan_rejections = getattr(self, 'plan_rejections', 0) + 1
                    self.last_plan_error = str(exc)[:200]
            self.plan_at = b.time
        if self.plan is not None:
            agent.controller.step(side, snap, obs, self.plan, self.field)


class AIRoom(object):
    """Owns the AI seats of one offline room and keeps them attached across matches."""

    def __init__(self, app, rng=None, autofill=True):
        self.app = app
        self.autofill = autofill
        self.rng = rng or random.Random()
        from .player_profile import PlayerProfile
        self.profile = PlayerProfile(app.profiles.folder() / RECORD_FILE)
        self.seats = {}
        self.recorded = set()
        self.background_token = None
        self.rematch_wait = {}
        self.arrivals = {}          # slot -> time it sits down, like a player finding the room
        self.slots = {}             # slot -> peer id (fresh 'peer-…' id per arrival, as the relay assigns)
        self.clock = 0.

    @staticmethod
    def cards():
        from .catalog import CARDS
        return CARDS

    # ------------------------------------------------------------ roster
    def add_seat(self, peer, side=None):
        room = self.app.room
        if peer in room.members:
            return ''
        error = room.connect(peer, seat=side)
        if error:
            return error
        names = [s.name for s in self.seats.values()] + [self.app.player_profile.name]
        seat = AISeat(self, peer, ai_name(self.rng, names))
        self.seats[peer] = seat
        if not self.autofill:room.ai_peers.add(peer)
        room.subsidy_peers.add(peer)
        self.publish_profile(peer)
        return ''

    def invite(self, side):
        """An explicit lobby action; it never replaces a human or refills later."""
        room = self.app.room
        if self.autofill:return '固定房间自动安排席位'
        if room is None or room.phase not in ('config', 'result'):
            return '请在准备界面邀请 AI'
        if side not in room.seat_list():return '席位设置无效'
        if side in room.members.values():return '该席位已有玩家'
        return self.add_seat('peer-%012x' % self.rng.getrandbits(48), side)

    def publish_profile(self, peer):
        seat = self.seats.get(peer)
        if seat is None or not self.app.room:
            return
        profile = self.profile.public()
        profile['name'] = seat.name
        self.app.room.set_player_profile(peer, profile)

    def remove_seat(self, peer):
        room = self.app.room
        if room and peer in room.members:
            room.leave(peer)
        self.seats.pop(peer, None)

    def human_side(self):
        room = self.app.room
        if not room:return None
        host=room.side_for('host')
        if host or self.autofill:return host
        return next((side for peer,side in sorted(room.members.items()) if peer not in self.seats),None)

    def is_human_seat(self, side):
        """A request belongs to its actual peer, even when the host watches.

        The authoritative request uses real seats, before any second-seat
        perspective swap. An occupied seat outside this owner's AI roster is
        human; looking only at the host omitted guests and swapped seats.
        """
        room = self.app.room
        return bool(room and any(seat == side and peer not in self.seats
                                 for peer, seat in room.members.items()))

    def drafter(self, team):
        """The one AI seat that drafts for a team; none when the host plays in it."""
        from .teams import team_of
        room = self.app.room
        human = self.human_side()
        if human is not None and team_of(human) == team:
            return None
        seats = sorted((s for s in self.seats.values() if s.side() and team_of(s.side()) == team),
                       key=lambda s: s.side())
        return seats[0] if seats else None

    def peers(self):
        return [p for p in self.seats if self.app.room and p in self.app.room.members]

    def before_role_change(self, payload):
        """The host takes a seat back: the spare AI gives it up first."""
        room = self.app.room
        if self.autofill and payload.get('role') == 'player' and 'host' in room.spectators and room.phase in ('config', 'result'):
            spare = self.slots.get('spare')
            if spare in room.members:
                if payload.get('side') is None or room.side_for(spare) == payload.get('side'):
                    self.remove_seat(spare)
                    self.app.refresh()

    # ------------------------------------------------------------ per frame
    def tick(self, dt):
        room = self.app.room
        if room is None:
            return
        self.clock += dt
        for peer in list(self.seats):
            if peer not in room.members:
                self.seats.pop(peer, None)          # kicked or left: someone else may come
        if len(room.seat_list()) > 2:
            # 2v2: every free seat is taken by someone who turns up shortly.
            wanted = tuple('seat%d' % i for i in range(len(room.seat_list())))
        else:
            wanted = SLOTS if 'host' in room.spectators else SLOTS[:1]
        if self.autofill and room.phase in ('config', 'result'):
            for slot in wanted:
                if self.slots.get(slot) in room.members or len(room.members) >= len(room.seat_list()):
                    self.arrivals.pop(slot, None)
                    continue
                if slot not in self.arrivals:
                    self.arrivals[slot] = self.clock + human_delay(self.rng, 'arrive')
                elif self.clock >= self.arrivals[slot]:
                    del self.arrivals[slot]
                    peer = 'peer-%012x' % self.rng.getrandbits(48)
                    if not self.add_seat(peer):
                        self.slots[slot] = peer
                        self.app.refresh()
        for seat in list(self.seats.values()):
            seat.safe_tick(dt)
        self.rematch(room, dt)
        if room.phase == 'result':
            self.app.result_seen_peers.update(self.peers())
            self.record(room)

    def rematch(self, room, dt):
        from .teams import scripted
        if scripted(room.mode):
            # Co-op days: the host starts the next day (or retries) from the
            # campaign page; the teammate never votes a rematch of its own.
            self.rematch_wait = {}
            return
        if room.phase != 'result' or len(room.members) != len(room.seat_list()):
            self.rematch_wait = {}
            return
        votes = room.rematch_votes
        human = self.human_side()
        for seat in self.seats.values():
            side = seat.side()
            if side is None or side in votes:
                continue
            if human is not None:
                if human not in votes:
                    continue
                value = votes[human]
                kind = 'rematch'
            else:
                # Host watching AI vs AI: keep the show going, alternating sides.
                value = bool(room.match_number % 2)
                kind = 'spectate_rematch'
            key = (room.match_id, side, json.dumps(value))
            if key not in self.rematch_wait:
                self.rematch_wait[key] = seat.clock + human_delay(seat.rng, kind)
            if seat.clock >= self.rematch_wait[key]:
                error = seat.cmd({'type': 'rematch', 'swap': value is True, 'same_deck': value == 'same_deck'})
                if error and value == 'same_deck':
                    seat.cmd({'type': 'rematch', 'swap': False, 'same_deck': False})

    def record(self, room):
        """Ranked AI matches count for the AI's own save, like any player's."""
        from .teams import scripted
        if scripted(room.mode) or not room.match_id or room.match_id in self.recorded or 'host' not in room.match_members:
            return
        self.recorded.add(room.match_id)
        for peer in self.peers():
            if peer in room.match_members:
                try:
                    self.profile.record(room.snapshot(peer, include_map=False), peer, 'guest')
                except OSError:
                    pass
                break
        for peer in self.peers():
            self.publish_profile(peer)

    # ------------------------------------------------------------ lifecycle
    def background(self):
        room = self.app.room
        if room and room.phase == 'battle' and not room.paused:
            self.background_token = (id(room), id(room.battle))

    def foreground(self):
        room = self.app.room
        token, self.background_token = self.background_token, None
        if room and token == (id(room), id(room.battle)) and room.phase == 'battle' and not room.audit_error:
            for seat in self.seats.values():
                side = seat.side()
                if side and room.pause_votes and side not in room.pause_votes and not room.paused:
                    seat.cmd({'type': 'pause'})
            if room.paused:
                self.app.command({'type': 'pause'})
            for seat in self.seats.values():
                seat.reset_observation()

    def close(self):
        """Leaving or closing mid-battle concedes it, exactly as in an online room."""
        room = self.app.room
        if room is None:
            return
        try:
            room._capture_battle_result()
            if room.phase == 'battle' and room.result is None and room.side_for('host'):
                room.host_quit()
                self.app.player_profile.record(room.snapshot('host', include_map=False), 'host', 'host')
                self.app.state['player_stats'] = self.app.player_profile.public()
            if room.phase == 'result':
                self.record(room)
        except Exception:
            traceback.print_exc()


def room_code(rng):
    from .relay import ALPHABET
    return ''.join(rng.choice(ALPHABET) for _ in range(10))


def room_brain():
    """The embedded brain every fixed room uses: the one sync_ai copied in
    (rv_source.BRAIN), so an AI upgrade reaches 1v1, 2v2 and co-op alike."""
    import importlib
    from .rv_source import BRAIN
    return importlib.import_module(__package__ + '.rv_' + BRAIN)


def create(app, watch=False, duo=False, coop=False):
    """Open the fixed room as its host. It presents exactly like a public cloud
    room; the other player sits down after a short, human-looking wait."""
    app.create_offline_host()
    owner = AIRoom(app)
    app.ai_room = owner
    if duo:
        app.room.set_mode('duo')
        # Same default as any player's 2v2 room: the extended maps.
        from .team_maps import DEFAULT_DUO_MAP, map_command
        app.room.command('host', map_command(DEFAULT_DUO_MAP, app.room.revision))
    if coop:
        app.room.set_mode('coop')
        app.room.on_pve_result = app.pve_result
        app.room.replay_enabled = False
    name = AI_COOP_ROOM_NAME if coop else AI_DUO_ROOM_NAME if duo else AI_ROOM_NAME
    app.state.update(network_mode='relay', token=room_code(owner.rng), room_public=True, room_name=name)
    app.message('云端房间已开启 · 房间码 %s · 发给朋友即可加入' % app.state['token'])
    if watch:
        app.room.change_role('host', 'spectator')
    app.refresh()
    return owner
