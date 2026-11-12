"""Versioned input recordings replayed by the real NativeBattle, never pickle."""
import copy
import json
import os
import tempfile
import time
import uuid
from pathlib import Path

from . import BUILD
from .audit_log import AuditLog, write_json_array
from .catalog import RULES, catalog_hash, digest, rules_hash, ROOM_TICK_RATES
from .native_battle import NativeBattle

FORMAT = 'pvz-pvp-replay-1'
MAX_BYTES = 64 * 1024 * 1024
SPEEDS = (.25, .5, 1., 2., 4., 8.)
INPUT_FIELDS = ('type', 'seq', 'move', 'jump', 'edge', 'card', 'x', 'y',
                'facing', 'grave', 'copy', 'resource', 'right', 'target', 'clear', 'request')


def state_hash(battle):
    return digest(battle.snapshot(include_map=True))


def matches_state_hash(battle, expected, recording):
    snapshot = battle.snapshot(include_map=True)
    if digest(snapshot) == expected:return True
    # Native R8 omitted the rope width global. Only its presentation field may
    # be normalized; every combat field must still match the recorded digest.
    if (recording.get('format') != FORMAT or
            recording.get('build') != '1.6.0.72-native.20261104'):return False
    snapshot = copy.deepcopy(snapshot)
    frame = snapshot.get('native_frame') or {}
    width = int(frame.get('tile', 48) / 17)
    changed = False
    for command in frame.get('commands', []):
        args = command.get('args', [])
        if (command.get('op') == 'primitive' and command.get('primitive') == 'line'
                and len(args) == 4 and args[0] == [50, 50, 50] and args[3] == width
                and command.get('entity') and not command.get('kwargs')):
            args[3] = None
            changed = True
    return changed and digest(snapshot) == expected


class Recording:
    """Temporary bounded log. Permanent writes happen only on explicit save."""
    def __init__(self, battle, seed, decks, bans, terrain=None):
        self.battle = battle
        self.id = uuid.uuid4().hex
        self.created = time.strftime('%Y-%m-%d %H:%M:%S')
        # Native initialization itself can update terrain decorations; retain
        # the pre-initialization map, exactly as supplied to NativeBattle.
        self.initial = dict(map=copy.deepcopy(terrain if terrain is not None else battle.map), rules=copy.deepcopy(battle.rules),
                            seed=seed, decks=copy.deepcopy(decks), bans=list(bans))
        if getattr(battle, 'mode', 'duel') != 'duel':
            self.initial['mode'] = battle.mode
        self.initial['ai_subsidy_seats'] = list(getattr(battle, 'ai_subsidy_seats', ()))
        self.log = AuditLog()
        self.error = ''
        self.stepping = False
        self.last_saved = None
        command, clear, step, close = battle.command_input, battle.clear_input, battle.step, battle.close

        def input_command(side, payload):
            # Retain rejected attempts too: they can advance seq/last_input_tick.
            clean = {k: copy.deepcopy(v) for k, v in payload.items() if k in INPUT_FIELDS} if isinstance(payload, dict) else payload
            result = command(side, payload)
            self.append(dict(kind='input', side=side, payload=clean, error=result))
            return result

        def clear_command(side):
            clear(side)
            if not self.stepping:self.append(dict(kind='clear', side=side))

        def advance(steps=1):
            self.stepping = True
            try:
                for unused in range(steps):
                    battle._capture_intermediate=unused<steps-1
                    before = battle.tick
                    step(1)
                    if before == battle.tick:break
                    if battle.tick % (battle.rules['tick_rate'] * 5) == 0:
                        self.append(dict(kind='check', sha256=state_hash(battle)))
            finally:
                self.stepping = False
                battle._capture_intermediate=False
                graphics=getattr(battle,'graphics',None)
                if graphics is not None:graphics.defer_capture=False

        def finish():
            try:close()
            finally:self.log.close()

        battle.command_input, battle.clear_input, battle.step, battle.close = input_command, clear_command, advance, finish

    def append(self, event):
        if self.error:return
        try:self.log.append(dict(tick=self.battle.tick, **event))
        except (OSError, ValueError, RuntimeError) as exc:self.error = '回放记录失败：' + str(exc)

    def export(self, path, result=None):
        if self.error:raise ValueError(self.error)
        path = Path(path);path.parent.mkdir(parents=True, exist_ok=True)
        metadata = dict(format=FORMAT, build=BUILD, catalog_hash=catalog_hash(), rules_hash=rules_hash(),
                        id=self.id, created=self.created, initial=self.initial, ticks=self.battle.tick,
                        result=copy.deepcopy(result or self.battle.result), final_hash=state_hash(self.battle))
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf8', dir=str(path.parent),
                    prefix=path.name+'.', suffix='.pending', delete=False) as stream:
                temporary = stream.name
                stream.write(json.dumps(metadata, ensure_ascii=False, allow_nan=False)[:-1])
                stream.write(',"operations":');write_json_array(stream, self.log);stream.write('}')
                stream.flush();os.fsync(stream.fileno())
            os.replace(temporary, str(path))
        finally:
            if temporary and os.path.exists(temporary):os.unlink(temporary)
        return path


def read_recording(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:raise ValueError('回放超过 64 MB，无法加载')
    data = json.loads(path.read_text(encoding='utf8'), parse_constant=lambda x: (_ for _ in ()).throw(ValueError('非有限数值')))
    if not isinstance(data, dict) or data.get('format') != FORMAT:
        raise ValueError('这是旧审计日志或不支持的格式；缺少完整输入，不能可靠回放')
    if (data.get('build'), data.get('catalog_hash'), data.get('rules_hash')) != (BUILD, catalog_hash(), rules_hash()):
        raise ValueError('回放与当前游戏版本/规则不同，请使用记录时的版本：'+str(data.get('build')))
    initial = data.get('initial', {})
    rules = initial.get('rules', {})
    if set(rules) != set(RULES) or any(type(v) is not type(RULES[k]) for k,v in rules.items()):
        raise ValueError('回放规则无效')
    if rules['tick_rate'] not in ROOM_TICK_RATES:raise ValueError('回放时间刻频率无效')
    ticks = data.get('ticks')
    if type(ticks) is not int or not 0 <= ticks <= 6*3600*rules['tick_rate']:raise ValueError('回放时长无效')
    from .maps import MapSnapshot
    MapSnapshot.from_dict(initial['map'])
    if type(initial.get('seed')) is not int or not 0 <= initial['seed'] < 2**31:raise ValueError('回放随机种子无效')
    from .teams import MODES, scripted, seats_for
    mode = initial.get('mode', 'duel')
    if mode not in MODES or scripted(mode):raise ValueError('回放模式无效')
    seats = seats_for(mode)
    operations = data.get('operations')
    if not isinstance(operations, list) or len(operations)>1000000:raise ValueError('回放输入数量无效')
    previous = 0
    for op in operations:
        if not isinstance(op,dict) or type(op.get('tick')) is not int or not previous <= op['tick'] <= ticks:
            raise ValueError('回放输入时间顺序无效')
        previous = op['tick']
        if op.get('kind') not in ('input','clear','check'):raise ValueError('未知回放操作')
        if op['kind'] in ('input','clear') and op.get('side') not in seats:raise ValueError('回放阵营无效')
        if op['kind']=='input' and (not isinstance(op.get('payload'),dict) or set(op['payload'])-set(INPUT_FIELDS)):
            raise ValueError('回放输入字段无效')
    return data


class Playback:
    def __init__(self, data, bridge, pygame=None):
        self.data, self.bridge, self.pg = data, bridge, pygame
        self.battle = None
        self.playing = False
        self.speed = 1.
        self.credit = 0.
        self.target = None
        self.error = ''
        self.verified = False
        try:self.restart()
        except Exception:
            self.close()
            raise

    @property
    def duration(self):return self.data['ticks'] / self.data['initial']['rules']['tick_rate']

    def restart(self):
        if self.battle:self.battle.close()
        initial = copy.deepcopy(self.data['initial'])
        self.battle = NativeBattle(initial['map'], initial['decks'], initial['rules'], initial['seed'],
                                   initial['bans'], bridge=self.bridge, pygame=self.pg, mode=initial.get('mode', 'duel'))
        self.battle.ai_subsidy_seats = tuple(initial.get('ai_subsidy_seats', ()))
        self.cursor = 0;self.verified = False;self.error = '';self.credit = 0.
        self._inputs()

    def _inputs(self):
        ops = self.data['operations']
        while self.cursor < len(ops) and ops[self.cursor]['tick'] == self.battle.tick:
            op = ops[self.cursor];self.cursor += 1
            if op['kind'] == 'input':
                error = self.battle.command_input(op['side'], op['payload'])
                if error != op['error']:raise ValueError('输入结果不一致，回放已停止（刻 %d）' % self.battle.tick)
            elif op['kind'] == 'clear':self.battle.clear_input(op['side'])
            elif not matches_state_hash(self.battle, op['sha256'], self.data):
                raise ValueError('战斗状态校验不一致，回放已停止（刻 %d）' % self.battle.tick)
        if self.battle.tick == self.data['ticks']:
            if not matches_state_hash(self.battle, self.data['final_hash'], self.data):raise ValueError('回放终点状态校验不一致')
            self.verified = True;self.playing = False

    def seek(self, tick):
        self.target = max(0, min(self.data['ticks'], int(tick)))
        self.credit = 0.
        if self.target < self.battle.tick or self.error:self.restart()

    def update(self, dt, max_steps=None, budget=None):
        if self.error:return
        if self.target is None and not self.playing:return
        # Each recorded tick runs several original-engine ticks. A fixed small
        # budget can leave a slow device behind; the old credit clamp then
        # silently discarded requested time. Preserve it, bounded by the log.
        if self.target is None:self.credit = min(self.data['ticks']-self.battle.tick,
                                                self.credit + max(0.,dt)*self.speed/self.battle.dt)
        if max_steps is None:max_steps=2000 if self.target is not None else max(60,min(2000,int(self.credit)+1))
        if budget is None:budget=.035 if self.target is not None or self.speed>1 else .014
        target = self.target if self.target is not None else min(self.data['ticks'],self.battle.tick+int(self.credit))
        deadline = time.perf_counter()+budget
        try:
            for unused in range(max_steps):
                if self.battle.tick >= target:break
                before = self.battle.tick;self.battle.step()
                if self.battle.tick == before:raise ValueError('回放在日志终点前意外结束')
                self._inputs()
                if self.target is None:self.credit=max(0.,self.credit-1)
                if time.perf_counter()>=deadline:break
            if self.target is not None and self.battle.tick >= self.target:self.target=None
        except (ValueError, RuntimeError, KeyError, TypeError) as exc:
            self.error=str(exc);self.playing=False;self.target=None

    def close(self):
        if self.battle:self.battle.close();self.battle=None
