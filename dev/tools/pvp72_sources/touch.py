# -*- coding: utf-8 -*-
"""Touch controls: multi-finger virtual buttons, long-press right click, drag scroll.

The desktop client drives everything from a keyboard plus a press/release
mouse pair.  This module adds a parallel path for fingers without changing any
of that: hold buttons latch the *current* binding keycodes into
``app.held_keys`` (jump also calls ``app.jump_press`` so the edge report keeps
its timing), tap buttons dispatch existing actions, and screen touches reuse
``app.pointer_down/up`` — the same code the mouse uses.  Nothing here talks to
the network or the room; it only produces the same inputs a keyboard/mouse
would.

Every button has its own layout slot. ``default_slots`` defines thumb zones;
the dedicated layout editor (screen ``touch_layout``) stores per-slot
``[x_frac, y_frac, scale]`` overrides in ``state["touch_layout"]`` which
``placed_slots`` applies with on-screen clamping.
"""
import math

from .catalog import CARDS

# Logical-pixel sizes of the big hold buttons per setting档位 (S/M/L).
BUTTON_SIZES = (76, 92, 108)
MARGIN = 18
GAP = 14
LONG_PRESS_SECONDS = .5
LONG_PRESS_SLACK = 12
SCROLL_STEP = 56
# Thumb-zone column width and row height for the stacked tap actions.
ACTION_W_EXTRA = 34
ACTION_H = 40
ACTION_GAP = 10
ACTION_ROWS = 6
# Each action can be moved and scaled separately, including facing buttons.
ACTION_SLOTS = ("cancel", "facing_auto", "facing_left", "facing_right",
                "shovel", "copy_target", "rally", "command", "teleport", "battle_page")
HUD_SLOTS = ("own_bank", "mate_bank", "minimap", "timer", "stage_info", "team_info", "battle_menu")
SLOTS = ("left", "right", "jump", "joystick", "facing_slider") + ACTION_SLOTS + HUD_SLOTS
SLOT_NAMES = dict(left="左移", right="右移", jump="跳跃", cancel="取消",
                  facing_auto="自动朝向", facing_left="朝向左", facing_right="朝向右",
                  shovel="铲子", copy_target="模仿", rally="召集", command="调令",
                  teleport="传送", battle_page="翻面", joystick="移动摇杆", facing_slider="朝向滑条")
SLOT_NAMES.update(own_bank="自己的卡槽", mate_bank="队友／另一方卡槽", minimap="小地图", timer="计时器", stage_info="波次与僵尸数量", team_info="队友与复活信息", battle_menu="菜单与资助按钮")
SCALE_MIN, SCALE_MAX = .4, 2.


def control_options(value):
    value = value if isinstance(value, dict) else {}
    shapes = value.get('shapes', {})
    shapes = shapes if isinstance(shapes, dict) else {}
    out = dict(movement='buttons', facing_slider=bool(value.get('facing_slider', False)),
               gyro=bool(value.get('gyro', False)), jump_angle=60., gyro_threshold=12., shapes={})
    if value.get('movement') in ('buttons', 'joystick', 'off'):
        out['movement'] = value['movement']
    for key, low, high in (('jump_angle', 20., 160.), ('gyro_threshold', 2., 35.)):
        try:
            number = float(value.get(key, out[key]))
            if math.isfinite(number):out[key] = min(high, max(low, number))
        except (ValueError, TypeError):pass
    for slot in SLOTS:
        if slot not in HUD_SLOTS and shapes.get(slot) == 'circle':out['shapes'][slot] = 'circle'
    return out


def visible_slots(state, editor=False):
    options = control_options(state.get('touch_options'))
    out = []
    for slot in SLOTS:
        if slot in HUD_SLOTS and not editor:continue
        if slot in ('left', 'right') and options['movement'] != 'buttons':continue
        if slot == 'joystick' and (options['movement'] == 'buttons' or (options['movement'] == 'off' and not editor)):continue
        if slot in ('facing_auto', 'facing_left', 'facing_right') and options['facing_slider']:continue
        if slot == 'facing_slider' and not options['facing_slider']:continue
        out.append(slot)
    return out


def button_size(state):
    index = state.get("touch_size", 1)
    if not isinstance(index, int) or isinstance(index, bool):
        index = 1
    return BUTTON_SIZES[min(2, max(0, index))]


def thumb_clusters(width, height, state):
    """Reserved bottom-corner zones for a touch battle: (move, actions).

    ``battle_view`` keeps its message bar between them and this module places
    its buttons inside them.  Mirror swaps the two sides for left-handed play.
    """
    size = button_size(state)
    move_w = size * 2 + GAP
    column_w = size + ACTION_W_EXTRA
    rows = ACTION_ROWS
    column_h = rows * ACTION_H + (rows - 1) * ACTION_GAP
    bottom = height - MARGIN
    move = (MARGIN, bottom - size, move_w, size)
    column = (width - MARGIN - column_w, bottom - size - 12 - column_h, column_w, column_h)
    if state.get("touch_mirror"):
        move = (width - MARGIN - move_w, move[1], move_w, move[3])
        column = (MARGIN, column[1], column_w, column[3])
    return move, column


def layout_overrides(value):
    """Validated custom slot placements: {slot: (x_frac, y_frac, scale)}.

    Fractions anchor the slot's top-left corner to the logical screen size and
    scale multiplies the stock geometry.  Anything malformed is dropped so a
    corrupt settings file can never break battle input.
    """
    out = {}
    if not isinstance(value, dict):
        return out
    # Keep the old actions placement to migrate saved layouts on first use.
    for slot in SLOTS + ("actions",):
        entry = value.get(slot)
        if not isinstance(entry, (list, tuple)) or len(entry) != 3:
            continue
        try:
            fx, fy, scale = float(entry[0]), float(entry[1]), float(entry[2])
        except (TypeError, ValueError):
            continue
        if not all(map(math.isfinite, (fx, fy, scale))):
            continue
        out[slot] = (min(1., max(0., fx)), min(1., max(0., fy)),
                     min(SCALE_MAX, max(SCALE_MIN, scale)))
    return out


def default_slots(width, height, state):
    """Stock anchor rect per layout slot: {slot: (x, y, w, h)}."""
    size = button_size(state)
    move, column = thumb_clusters(width, height, state)
    slots = {"left": (move[0], move[1], size, size),
            "right": (move[0] + size + GAP, move[1], size, size),
            "jump": ((MARGIN, height - MARGIN - size, size, size) if state.get("touch_mirror")
                     else (width - MARGIN - size, height - MARGIN - size, size, size)),
            }
    cw = size + ACTION_W_EXTRA
    top = height - MARGIN - size - 12 - (4 * ACTION_H + 3 * ACTION_GAP)
    outer = MARGIN if state.get("touch_mirror") else width - MARGIN - cw
    inner = outer + cw + ACTION_GAP if state.get("touch_mirror") else outer - cw - ACTION_GAP
    for index, slot in enumerate(("cancel", "shovel", "copy_target", "teleport")):
        slots[slot] = (outer, top + index * (ACTION_H + ACTION_GAP), cw, ACTION_H)
    for index, slot in enumerate(("rally", "command", "battle_page"), 1):
        slots[slot] = (inner, top + index * (ACTION_H + ACTION_GAP), cw, ACTION_H)
    third = (cw - 8) / 3.
    for index, slot in enumerate(("facing_auto", "facing_left", "facing_right")):
        slots[slot] = (inner + index * (third + 4), top, third, ACTION_H)
    diameter = size * 1.8
    slots['joystick'] = (move[0], height-MARGIN-diameter, diameter, diameter)
    slots['facing_slider'] = (inner, top, cw, ACTION_H)
    bank_w = (width-160)//2
    slots.update(own_bank=(8,8,bank_w,100), mate_bank=(16+bank_w,8,bank_w,100),
                 minimap=(width-188,190,168,62), timer=(width//2-72,114,144,30),
                 stage_info=(8,150,width-160,30), team_info=(8,186,min(560,width-220),30),
                 battle_menu=(width-130,8,122,166))
    shapes = control_options(state.get('touch_options'))['shapes']
    for slot in shapes:
        if slot in ('joystick', 'facing_slider'):continue
        x,y,w,h = slots[slot]
        diameter = min(w,h)
        slots[slot] = (x+(w-diameter)//2, y+(h-diameter)//2, diameter, diameter)
    return slots


def placed_slots(width, height, state):
    """Default slots with the player's custom layout applied, clamped on-screen."""
    slots = default_slots(width, height, state)
    overrides = layout_overrides(state.get("touch_layout"))
    legacy = overrides.get("actions")
    if legacy:
        # The former column anchors the outside column; explicit per-button
        # overrides win. Existing users keep their chosen corner and scale.
        old = thumb_clusters(width, height, state)[1]
        anchor_x, anchor_y, scale = legacy
        for slot in ACTION_SLOTS:
            x, y, w, h = slots[slot]
            slots[slot] = (anchor_x * width + (x-old[0]) * scale,
                           anchor_y * height + (y-old[1]) * scale, w*scale, h*scale)
    for slot, (fx, fy, scale) in overrides.items():
        if slot == "actions":continue
        base = default_slots(width, height, state)[slot]
        scale = min(scale, width/max(1,base[2]), height/max(1,base[3]))
        w, h = int(base[2] * scale), int(base[3] * scale)
        slots[slot] = (int(min(width - w, max(0., fx * width))),
                       int(min(height - h, max(0., fy * height))), w, h)
    for slot, (x,y,w,h) in slots.items():
        slots[slot] = (int(min(width-w,max(0,x))),int(min(height-h,max(0,y))),int(w),int(h))
    return slots


class TouchControls:
    def __init__(self, app):
        self.app = app
        self.fingers = {}
        self.pressed = set()
        self._hover = None
        self._scroll = 0.
        self.editor_selected = None
        self.editor_panel = False
        self.virtual_keys = set()
        self.virtual_bindings = set()
        self.gyro_bindings = []
        self.gyro_status = ''
        self.gyro_calibrate = False

    @property
    def active(self):
        return bool(self.app.state.get("touch_mode"))

    # ------------------------------------------------------------------ layout
    def _hold_binding(self, name):
        """The keycode a hold button latches, resolved against current bindings."""
        state = self.app.state
        side = state.get("active_side", "plant")
        if side == "plant" or self.app.mode in ("host", "guest"):
            return side, "plant_" + name
        return side, "zombie_" + name

    def _copy_name(self, battle):
        """Current mimic target for the button label ('—' until one exists)."""
        player = battle.get("players", {}).get("plant", {})
        key = self.app.state.get("copy") or player.get("last_copy_card")
        return CARDS[key]["name"] if key in CARDS else "—"

    def _action_buttons(self, slots, actions):
        """Resolve every action to its independent saved placement."""
        buttons = []
        for payload, label in actions:
            if payload == ("facing",):
                if control_options(self.app.state.get('touch_options'))['facing_slider']:
                    buttons.append((slots['facing_slider'], 'slider', ('facing_slider',), '左  自动  右'))
                    continue
                for slot,value,title in (("facing_auto",0,"自动"),("facing_left",-1,"左"),("facing_right",1,"右")):
                    buttons.append((slots[slot],"tap",("facing",value),title))
            else:
                slot = "cancel" if payload == "escape" else payload[0]
                buttons.append((slots[slot], "tap", payload, label))
        return buttons

    def layout(self):
        """Virtual buttons for the current screen: (rect, role, payload, label)."""
        app = self.app
        state = app.state
        renderer = app.renderer
        width, height = renderer.screen.get_size()
        buttons = []
        if state.get("screen") == "room" and app.view.get("phase") == "battle" \
                and not state.get("confirm_leave") and not state.get("leave_pending") and not app.view.get('spectating'):
            slots = placed_slots(width, height, state)
            movement = control_options(state.get('touch_options'))['movement']
            if movement == 'buttons':
                buttons.append((slots["left"], "hold", "left", "左"))
                buttons.append((slots["right"], "hold", "right", "右"))
            elif movement == 'joystick':
                buttons.append((slots['joystick'], 'stick', 'joystick', '移动'))
            battle = app.view.get("battle") or {}
            players = battle.get("players", {})
            side = state.get("active_side", "plant")
            local = app.view.get("local_sides", [side])
            actions = [("escape", "取消")]
            if side in local:
                actions.append((("facing",), ""))
                if side == "plant" and "plant" in local:
                    actions.append((("shovel",), "铲子"))
                    deck = players.get(side, {}).get("deck", [])
                    if any(key in CARDS and CARDS[key]["behavior"] == "copy" for key in deck):
                        # The label carries the current target: a bare "模仿"
                        # button told players nothing about what it did.
                        actions.append((("copy_target",), "模仿·" + self._copy_name(battle)))
                if "zombie" in local:
                    if side=='zombie':
                        label = "清除旗" if battle.get('rally_point') else "召集·选位置" if state.get('rally') else "召集"
                        actions.append((("rally",), label))
                    label = "跟随" if battle.get("command") == "follow" else "追击"
                    actions.append((("command",), label))
                remaining = max(0, players.get(side, {}).get("teleport_ready_at", 0)
                                - battle.get("time", 0))
                label = "传送·选目标" if state.get('teleport') else "传送 %.0fs" % remaining if remaining else "传送"
                actions.append((("teleport",), label))
                if len(players.get(side, {}).get("deck", [])) > 7:
                    actions.append((("battle_page",), "翻面"))
            buttons.extend(self._action_buttons(slots, actions))
            # Jump sits at the far bottom corner opposite the move pair.
            buttons.append((slots["jump"], "hold", "jump", "跳"))
            return buttons
        # Non-battle screens need no virtual buttons: every menu already has
        # its own 返回/离开 control, and the Android back gesture arrives as
        # K_AC_BACK -> Escape for the rest. A floating button would collide
        # with the BP grids.
        return []

    def _hit(self, pos):
        for rect, role, payload, label in self.layout():
            box = self.app.pg.Rect(rect)
            slot = self._slot(payload, role)
            if self._contains(box, pos, slot):
                return box, role, payload, label
        return None

    def _slot(self, payload, role):
        if role in ('hold', 'stick'):return payload
        if role == 'slider':return 'facing_slider'
        if payload == 'escape':return 'cancel'
        if payload[0] == 'facing':return 'facing_auto' if payload[1] == 0 else 'facing_left' if payload[1] < 0 else 'facing_right'
        return payload[0]

    def _contains(self, box, pos, slot):
        if not box.collidepoint(pos):return False
        if slot == 'joystick' or control_options(self.app.state.get('touch_options'))['shapes'].get(slot) == 'circle':
            return ((pos[0]-box.centerx)/(box.w*.5))**2 + ((pos[1]-box.centery)/(box.h*.5))**2 <= 1.
        return True

    def _sync_virtual(self):
        manual = any(role[0] == 'stick' or (role[0] == 'hold' and role[1].endswith(('_left', '_right'))) for role in self.fingers.values())
        bindings = set() if manual else set(self.gyro_bindings)
        for role in self.fingers.values():
            if role[0] == 'stick':bindings.update(role[3])
        keys = set()
        for binding in bindings:
            code = self.app.state['bindings'].get(binding)
            if code is not None:keys.add(code)
        for code in self.virtual_keys - keys:
            if not any(role[0] == 'hold' and role[2] == code for role in self.fingers.values()):
                if not self.app.pg.key.get_pressed()[code]:self.app.held_keys.discard(code)
        for binding in self.virtual_bindings - bindings:
            if not any(role[0] == 'hold' and role[1] == binding for role in self.fingers.values()):self.pressed.discard(binding)
        for code in keys:self.app.held_keys.add(code)
        for binding in bindings:self.pressed.add(binding)
        changed = keys != self.virtual_keys
        self.virtual_keys = keys
        self.virtual_bindings = bindings
        if changed:self.app.move_inputs(0.)

    def _stick_motion(self, role, pos):
        rect = role[1]
        dx = (pos[0]-rect[0]-rect[2]*.5)/(rect[2]*.5)
        dy = (pos[1]-rect[1]-rect[3]*.5)/(rect[3]*.5)
        names = []
        if abs(dx) > .22:names.append('left' if dx < 0 else 'right')
        options = control_options(self.app.state.get('touch_options'))
        if dy < -.3 and math.atan2(abs(dx), -dy)*180./math.pi <= options['jump_angle']*.5:names.append('jump')
        bindings = [self._hold_binding(name)[1] for name in names]
        jump = self._hold_binding('jump')[1]
        jump_edge = jump in bindings and jump not in role[3]
        role[2] = pos
        role[3] = bindings
        self._sync_virtual()
        if jump_edge:
            code = self.app.state['bindings'].get(jump)
            if code is not None:self.app.jump_press(code)

    def _slider_motion(self, role, pos):
        rect = role[1]
        index = min(2, max(0, int((pos[0]-rect[0])*3./rect[2])))
        value = (-1, 0, 1)[index]
        if role[2] != value:
            role[2] = value
            self._dispatch(('facing', value))

    # ------------------------------------------------------------------ events
    def finger(self, event, kind):
        surface = self.app.surface
        width, height = surface.get_size()
        pos = (event.x * width, event.y * height)
        fid = getattr(event, "finger_id", 0)
        if kind == "down":
            self._down(fid, self.app.logical_pos(pos))
        elif kind == "motion":
            self._motion(fid, self.app.logical_pos(pos))
        else:
            self._up(fid, self.app.logical_pos(pos))

    def mouse_down(self, pos, button):
        if button != 1:
            self.app.pointer_down(pos, button)
            return
        self._down("mouse", pos)

    def mouse_motion(self, pos):
        self._hover = pos
        if "mouse" in self.fingers:
            self._motion("mouse", pos)
        elif self.app.pointer_capture:
            self.app.pointer_motion(pos)

    def mouse_up(self, pos, button):
        if button != 1 or "mouse" not in self.fingers:
            self.app.pointer_up(pos, button)
            return
        self._up("mouse", pos)

    def _down(self, fid, pos):
        if fid in self.fingers:
            return
        if self.app.chat_guard(pos):
            return
        hit = self._hit(pos)
        if hit is not None:
            rect, role, payload, label = hit
            if role == 'stick':
                if any(value[0] == 'stick' for value in self.fingers.values()):return
                value = ['stick', tuple(rect), pos, []]
                self.fingers[fid] = value
                self._stick_motion(value, pos)
                return
            if role == 'slider':
                if any(value[0] == 'slider' for value in self.fingers.values()):return
                value = ['slider', tuple(rect), None]
                self.fingers[fid] = value
                self._slider_motion(value, pos)
                return
            if payload == ('rally',):
                if self.app.begin_rally(None):self.fingers[fid]=('rally',pos)
                return
            if role == "hold":
                side, binding = self._hold_binding(payload)
                keycode = self.app.state["bindings"].get(binding)
                if keycode is None:
                    return
                self.fingers[fid] = ("hold", binding, keycode)
                self.pressed.add(binding)
                self.app.held_keys.add(keycode)
                if payload == "jump":
                    self.app.jump_press(keycode)
                else:
                    self.app.move_inputs(0.)
            else:
                self.fingers[fid] = ("tap", payload)
                self.pressed.add(payload)
                self._dispatch(payload)
            return
        # The application has one pointer capture. A second world finger must
        # not replace it or release it, while move/jump fingers remain independent.
        if any(value[0] == "screen" for value in self.fingers.values()):
            return
        editor = self.app.state.get("screen") == "touch_layout"
        if self.app.renderer.hit(pos) is None and self.app.world_touch_can_jump(pos):
            side,binding=self._hold_binding('jump')
            keycode=self.app.state['bindings'][binding]
            # 'world' marks a finger that began on the field: sliding it sweeps
            # sun up without another tap (see _motion and app.hover_collect).
            self.fingers[fid]=('hold',binding,keycode,'world')
            self._hover=pos
            self.pressed.add(binding);self.app.held_keys.add(keycode)
            self.app.jump_press(keycode)
            # The empty-world gesture also keeps the original plant mark.
            # world_touch_can_jump already excludes resources, cannon and tools;
            # the authority still checks hero range and line of sight.
            if side == 'plant':self.app.input(side,'mark')
            return
        if editor and self.app.renderer.hit(pos) is None:
            # Layout editor: a press on a slot starts a drag owned entirely by
            # this module; toolbar buttons keep the normal press path below.
            grab = self._editor_grab(pos)
            if grab is not None:
                slot, dx, dy = grab
                self.editor_selected = slot
                self.fingers[fid] = ["editor", slot, dx, dy, pos, False]
                return
        facing=self.app.state.get('touch_facing',-1)
        if self.app.state.get('shovel') and self.app.state.get('touch_quick_plant',True):
            side=self.app.state.get('active_side','plant')
            facing=(self.app.view.get('battle') or {}).get('players',{}).get(side,{}).get('facing',-1)
        button = 3 if (not editor
                       and self.app.view.get("phase") == "battle"
                       and self.app.renderer.hit(pos) is None
                       and (not self.app.state.get('touch_quick_plant',True) or self.app.state.get('shovel'))
                       and facing > 0) else 1
        self.fingers[fid] = ["screen", pos, pos, 0., False, button]
        self._hover = pos
        self._scroll = 0.
        self.app.pointer_down(pos, button)

    def _motion(self, fid, pos):
        role = self.fingers.get(fid)
        if role is None:
            return
        if role[0] == 'stick':
            self._stick_motion(role, pos)
            return
        if role[0] == 'slider':
            self._slider_motion(role, pos)
            return
        if role[0]=='rally':
            if (abs(pos[0]-role[1][0])+abs(pos[1]-role[1][1]) >= LONG_PRESS_SLACK
                    and self._hit(pos) is None):
                self.app.state['rally_drag']=pos
            return
        if role[0] == "editor":
            if abs(pos[0]-role[4][0])+abs(pos[1]-role[4][1]) >= LONG_PRESS_SLACK:role[5] = True
            if role[5]:
                self.editor_panel = False
                self._editor_drag(role[1], pos, role[2], role[3])
            return
        if role[0] == "hold":
            if role[3:] == ('world',):
                self._hover = pos
            return
        if role[0] == "screen":
            role[2] = pos
            self._hover = pos
            if getattr(self.app,'replay_drag',None) or getattr(self.app,'spectator_drag',None):
                self.app.pointer_motion(pos)
                return
            if getattr(self.app, "map_paint", None) is not None:
                self.app.pointer_motion(pos)
                return
            if self.app.pointer_capture:
                self.app.pointer_motion(pos)
            if not self.app.pointer_capture:
                self._scroll += pos[1] - role[1][1]
                role[1] = pos
                while self._scroll >= SCROLL_STEP:
                    self._scroll -= SCROLL_STEP
                    self.app.wheel(1, pos=pos)
                while self._scroll <= -SCROLL_STEP:
                    self._scroll += SCROLL_STEP
                    self.app.wheel(-1, pos=pos)

    def _up(self, fid, pos):
        role = self.fingers.pop(fid, None)
        if role is None:
            return
        if role[0] in ('stick', 'slider'):
            self._sync_virtual()
            return
        if role[0]=='rally':
            dragging=self.app.state.pop('rally_drag',None) is not None
            if dragging and self._hit(pos) is None:self.app.place_rally(pos)
            return
        if role[0] == "editor":
            if not role[5]:self.editor_panel = True
            self.app.save_settings()
        elif role[0] == "hold":
            if role[3:] == ('world',) and fid != "mouse":
                self._hover = None
            if role[1] not in self.virtual_bindings and not any(other[0] == "hold" and other[1] == role[1] for other in self.fingers.values()):
                self.pressed.discard(role[1])
            if role[2] not in self.virtual_keys and not any(other[0] == "hold" and other[2] == role[2] for other in self.fingers.values()):
                self.app.held_keys.discard(role[2])
                self.app.move_inputs(0.)
        elif role[0] == "tap":
            self.pressed.discard(role[1])
        else:
            self._hover = None if fid != "mouse" else pos
            if role[4]:
                # The long press already delivered a right click; do not also
                # release the cancelled left capture.
                return
            self.app.pointer_up(pos, role[5])

    def _dispatch(self, payload):
        app = self.app
        if payload == "escape":
            app.action(('cancel_action',))
        elif payload == ("copy_target",):
            app.keyboard(app.pg.event.Event(app.pg.KEYDOWN, key=app.state['bindings']['copy'], mod=0))
        else:
            app.action(payload)

    # ------------------------------------------------------------------ timers
    def update(self, dt):
        self._update_gyro()
        if (self.app.state.get('rally') or self.app.state.get('teleport')
                or self.app.state.get("screen") in ("map_editor", "replay", "touch_layout")
                or self.app.view.get('spectating')):
            return
        for role in self.fingers.values():
            if isinstance(role, list) and role[0] == "screen" and not role[4]:
                role[3] += dt
                start, pos = role[1], role[2]
                if (role[3] >= LONG_PRESS_SECONDS
                        and abs(pos[0] - start[0]) + abs(pos[1] - start[1]) < LONG_PRESS_SLACK
                        and role[5] == 1 and not self.app.state.get("selected_card")):
                    role[4] = True
                    self.app.pointer_capture = None
                    self.app.pointer_down(start, 3)
                    self.app.pointer_up(start, 3)

    def clear(self):
        sensor = getattr(self.app.pg, 'motion_sensor', None)
        if callable(sensor):sensor(False, False)
        # An explicit editor request must survive menu/focus input cleanup.
        self.gyro_bindings = []
        for role in self.fingers.values():
            if role[0] == "hold":
                self.app.held_keys.discard(role[2])
        self.fingers.clear()
        self._sync_virtual()
        self.pressed.clear()
        self._hover = None
        self._scroll = 0.

    def hover_pos(self):
        return self._hover

    def _update_gyro(self):
        state = self.app.state
        options = control_options(state.get('touch_options'))
        enabled = (options['gyro'] and self.active and state.get('focused', True)
                   and state.get('screen') == 'room' and self.app.view.get('phase') == 'battle'
                   and not self.app.view.get('spectating') and not state.get('focus')
                   and not state.get('confirm_leave') and not state.get('leave_pending'))
        sensor = getattr(self.app.pg, 'motion_sensor', None)
        reading = sensor(enabled, self.gyro_calibrate) if callable(sensor) else None
        self.gyro_bindings = []
        if enabled:
            if reading is None:
                self.gyro_status = '设备无可用陀螺仪'
            else:
                self.gyro_status = '已校准'
                self.gyro_calibrate = False
                # A touch gesture wins over tilt until its finger is released.
                manual = any(role[0] == 'stick' or (role[0] == 'hold' and role[1].endswith(('_left', '_right'))) for role in self.fingers.values())
                if not manual and abs(reading) >= options['gyro_threshold']:
                    self.gyro_bindings = [self._hold_binding('left' if reading < 0 else 'right')[1]]
        self._sync_virtual()

    def editor_option(self, key, value):
        state = self.app.state
        options = control_options(state.get('touch_options'))
        if key == 'close':
            self.editor_panel = False
            return
        if key == 'movement_settings':
            self.editor_selected = 'left' if options['movement'] == 'buttons' else 'joystick'
            self.editor_panel = True
            return
        if key == 'calibrate':
            self.gyro_calibrate = True
            self.app.message('回到对局后，以当前握持角度校准')
            return
        if key == 'shape' and self.editor_selected and self.editor_selected not in HUD_SLOTS:
            slot = self.editor_selected
            if options['shapes'].get(slot) == 'circle':options['shapes'].pop(slot)
            else:options['shapes'][slot] = 'circle'
        elif key in ('movement', 'facing_slider', 'gyro', 'jump_angle', 'gyro_threshold'):
            options[key] = value
        if key == 'movement':self.editor_selected = 'left' if value == 'buttons' else 'joystick'
        if key == 'facing_slider':self.editor_selected = 'facing_slider' if value else 'facing_auto'
        state['touch_options'] = control_options(options)
        if key == 'gyro' and not value:self.gyro_calibrate = False
        self.app.save_settings()

    def _panel_rect(self):
        width, height = self.app.renderer.screen.get_size()
        return ((width-440)//2, max(12, (height-360)//2), 440, 360)

    def _draw_options(self):
        if not self.editor_panel or not self.editor_selected:return
        r = self.app.renderer
        pg = self.app.pg
        screen = r.screen
        x,y,w,h = self._panel_rect()
        pg.draw.rect(screen, (37, 32, 26), (x,y,w,h), border_radius=12)
        pg.draw.rect(screen, (218, 188, 116), (x,y,w,h), 2, border_radius=12)
        options = control_options(self.app.state.get('touch_options'))
        slot = self.editor_selected
        r.text(SLOT_NAMES.get(slot, slot), (x+16,y+12), size=20)
        r.button('关闭', (x+w-88,y+8,72,32), ('touch_option','close',0))
        if slot in HUD_SLOTS:
            r.text('拖动更改位置，用缩小／放大调整尺寸', (x+16,y+62), size=17)
            r.button('- 缩小', (x+16,y+106,192,38), ('layout_scale',-1))
            r.button('+ 放大', (x+224,y+106,200,38), ('layout_scale',1))
        elif slot not in ('joystick', 'facing_slider'):
            shape = '圆形' if options['shapes'].get(slot) == 'circle' else '方形'
            r.button('形状：'+shape+'（点击切换）', (x+16,y+52,w-32,36), ('touch_option','shape',0))
        row = y+100
        if slot in ('left','right','joystick'):
            for index, mode in enumerate(('buttons','joystick','off')):
                r.button(('双按键','圆盘摇杆','关闭移动键')[index], (x+16+index*136,row,128,36), ('touch_option','movement',mode), selected=options['movement']==mode)
            row += 48
            r.text('上拉跳跃角度：%d°（以正上方为中心）' % options['jump_angle'], (x+16,row), size=16)
            r.button('缩小角度', (x+16,row+32,192,34), ('touch_option','jump_angle',options['jump_angle']-10))
            r.button('扩大角度', (x+224,row+32,200,34), ('touch_option','jump_angle',options['jump_angle']+10))
        if slot.startswith('facing_'):
            r.button('朝向：'+('左 / 自动 / 右 滑动条' if options['facing_slider'] else '三个独立按键'), (x+16,row,w-32,40), ('touch_option','facing_slider',not options['facing_slider']))
        r.button('陀螺仪：'+('开' if options['gyro'] else '关'), (x+16,y+h-84,192,34), ('touch_option','gyro',not options['gyro']))
        r.button('重新校准', (x+224,y+h-84,200,34), ('touch_option','calibrate',0))
        r.button('灵敏度 -', (x+16,y+h-42,124,30), ('touch_option','gyro_threshold',options['gyro_threshold']+1))
        r.text('%d%% · %d°' % (round((35-options['gyro_threshold'])*100/33), options['gyro_threshold']), (x+152,y+h-38), size=16)
        r.button('灵敏度 +', (x+300,y+h-42,124,30), ('touch_option','gyro_threshold',options['gyro_threshold']-1))

    # ------------------------------------------------------------- layout editor
    def _editor_grab(self, pos):
        width, height = self.app.renderer.screen.get_size()
        if self.editor_panel and self.app.pg.Rect(self._panel_rect()).collidepoint(pos):return None
        for slot, rect in placed_slots(width, height, self.app.state).items():
            if slot in visible_slots(self.app.state, True) and self._contains(self.app.pg.Rect(rect), pos, slot):
                return slot, pos[0] - rect[0], pos[1] - rect[1]
        return None

    def _editor_drag(self, slot, pos, dx, dy):
        state = self.app.state
        width, height = self.app.renderer.screen.get_size()
        rect = placed_slots(width, height, state)[slot]
        overrides = layout_overrides(state.get("touch_layout"))
        fallback = overrides.get("actions", (0., 0., 1.)) if slot in ACTION_SLOTS else (0., 0., 1.)
        scale = overrides.get(slot, fallback)[2]
        x = min(width - rect[2], max(0., pos[0] - dx))
        y = min(height - rect[3], max(0., pos[1] - dy))
        state.setdefault("touch_layout", {})[slot] = [x / width, y / height, scale]

    def editor_scale_selected(self, delta):
        """Grow/shrink the tapped slot in the layout editor (step e.g. ±0.1)."""
        slot = self.editor_selected
        if slot is None:
            self.app.message("先点选一个按键，再调整大小")
            return
        state = self.app.state
        width, height = self.app.renderer.screen.get_size()
        current = layout_overrides(state.get("touch_layout")).get(slot)
        if current is None:
            rect = placed_slots(width, height, state)[slot]
            scale = layout_overrides(state.get("touch_layout")).get("actions", (0., 0., 1.))[2] if slot in ACTION_SLOTS else 1.
            current = (rect[0] / width, rect[1] / height, scale)
        scale = min(SCALE_MAX, max(SCALE_MIN, round(current[2] + delta, 2)))
        state.setdefault("touch_layout", {})[slot] = [current[0], current[1], scale]
        self.app.save_settings()

    def draw_editor(self):
        """The dedicated layout editor: drag slots, scale the selected one."""
        app = self.app
        pg = app.pg
        renderer = app.renderer
        screen = renderer.screen
        width, height = screen.get_size()
        shade = pg.Surface((width, height), pg.SRCALPHA)
        shade.fill((10, 8, 6, 150))
        screen.blit(shade, (0, 0))
        slots = placed_slots(width, height, app.state)
        for slot in visible_slots(app.state, True):
            if slot == self.editor_selected:
                pg.draw.rect(screen, (255, 218, 106), pg.Rect(slots[slot]).inflate(10, 10), 3,
                             border_radius=12)
        preview = [("escape", "取消"), (("facing",), ""), (("shovel",), "铲子"),
                   (("copy_target",), "模仿·目标"), (("rally",), "召集"),
                   (("command",), "调令"), (("teleport",), "传送"),
                   (("battle_page",), "翻面")]
        options = control_options(app.state.get('touch_options'))
        if options['movement'] == 'buttons':
            self._paint_button(slots["left"], "左", self.editor_selected == "left", 'left')
            self._paint_button(slots["right"], "右", self.editor_selected == "right", 'right')
        else:self._paint_stick(slots['joystick'], options['movement']=='off')
        self._paint_button(slots["jump"], "跳", self.editor_selected == "jump", 'jump')
        for rect, role, payload, label in self._action_buttons(slots, preview):
            if role == 'slider':self._paint_slider(rect)
            else:self._paint_button(rect, label, self.editor_selected in slots and rect == slots[self.editor_selected], self._slot(payload, role))
        for slot in HUD_SLOTS:
            self._paint_button(slots[slot], SLOT_NAMES[slot], self.editor_selected == slot, slot)
        selected = SLOT_NAMES.get(self.editor_selected)
        toolbar_y = max(220, int(height*.38))
        renderer.text("已选：" + (selected or "无（点选一个按键）"), (24, toolbar_y-28), size=17)
        renderer.button("- 缩小", (24, toolbar_y, 120, 38), ("layout_scale", -1), active=bool(selected))
        renderer.button("+ 放大", (156, toolbar_y, 120, 38), ("layout_scale", 1), active=bool(selected))
        renderer.button("移动设置", (288, toolbar_y, 132, 38), ('touch_option','movement_settings',0))
        renderer.button("重置布局", (width - 304, toolbar_y, 132, 38), ("layout_reset",))
        renderer.button("完成", (width - 160, toolbar_y, 136, 38), ("menu", "back"))
        renderer.text('点击控件设置，拖动改位置；卡槽、小地图、信息栏均可调整；移动键从“移动设置”恢复', (24,toolbar_y+52), size=15)
        self._draw_options()

    # ------------------------------------------------------------------ drawing
    def _fit_font(self, label, max_width):
        """Largest font (19 down to 12) that keeps the label inside the button."""
        size = 19
        while size > 12 and self.app.renderer.font(size).size(label)[0] > max_width:
            size -= 1
        return self.app.renderer.font(size)

    def _paint_button(self, rect, label, held=False, slot=''):
        pg = self.app.pg
        screen = self.app.renderer.screen
        box = pg.Rect(rect)
        overlay = pg.Surface(box.size, pg.SRCALPHA)
        circle = bool(slot) and control_options(self.app.state.get('touch_options'))['shapes'].get(slot) == 'circle'
        if circle:pg.draw.ellipse(overlay, (20, 16, 12, 165 if held else 96), (0,0,box.w,box.h))
        else:overlay.fill((20, 16, 12, 165 if held else 96))
        screen.blit(overlay, box.topleft)
        if circle:pg.draw.ellipse(screen, (255,224,125) if held else (198,181,145), box, 2)
        else:pg.draw.rect(screen, (255, 224, 125) if held else (198, 181, 145), box, 2, border_radius=9)
        if circle and len(label) > 3:label = label[:2]
        image = self._fit_font(label, box.w - 10).render(label, True, (255, 239, 199))
        screen.blit(image, (box.x + (box.w - image.get_width()) // 2,
                            box.y + (box.h - image.get_height()) // 2))

    def _paint_stick(self, rect, disabled=False):
        pg = self.app.pg
        screen = self.app.renderer.screen
        x,y,w,h = rect
        cx,cy = x+w*.5,y+h*.5
        overlay = pg.Surface((int(w),int(h)), pg.SRCALPHA)
        pg.draw.ellipse(overlay, (20,16,12,70 if disabled else 110), (0,0,w,h))
        screen.blit(overlay, (x,y))
        pg.draw.ellipse(screen, (198,181,145), rect, 2)
        angle = control_options(self.app.state.get('touch_options'))['jump_angle']*.5*math.pi/180.
        for side in (-1,1):pg.draw.line(screen, (158,159,133), (cx,cy), (cx+side*math.sin(angle)*w*.45,cy-math.cos(angle)*h*.45), 1)
        dx,dy = 0.,0.
        for role in self.fingers.values():
            if role[0] == 'stick':
                dx,dy = role[2][0]-cx,role[2][1]-cy
                length = math.sqrt(dx*dx+dy*dy)
                if length > w*.35:dx,dy = dx*w*.35/length,dy*w*.35/length
        pg.draw.circle(screen, (216,191,131), (int(cx+dx),int(cy+dy)), int(w*.16), 2)
        self.app.renderer.text('移动已关' if disabled else '上拉跳跃', (x+w*.5-30,y+h*.73), size=15)

    def _paint_slider(self, rect):
        x,y,w,h = rect
        selected = 0 if self.app.state.get('touch_quick_plant',True) else self.app.state.get('touch_facing',-1)
        for index, value in enumerate((-1,0,1)):
            self._paint_button((x+index*w/3.,y,w/3.,h), ('左','自动','右')[index], value==selected)

    def draw(self):
        for rect, role, payload, label in self.layout():
            if role == 'stick':
                self._paint_stick(rect)
                continue
            if role == 'slider':
                self._paint_slider(rect)
                continue
            key = payload if role == "tap" else self._hold_binding(payload)[1]
            held = (role == "tap" and payload in self.pressed) or \
                   (role == "hold" and key in self.pressed)
            if payload in (("teleport",),("rally",),("shovel",)):
                held = held or bool(self.app.state.get(payload[0]))
            if isinstance(payload, tuple) and len(payload) == 2 and payload[0] == "facing":
                held = (payload[1]==0 if self.app.state.get('touch_quick_plant',True)
                        else self.app.state.get("touch_facing", -1) == payload[1])
            self._paint_button(rect, label, held, self._slot(payload,role))
        if control_options(self.app.state.get('touch_options'))['gyro'] and self.gyro_status == '设备无可用陀螺仪':
            self.app.renderer.text(self.gyro_status, (18,198), size=14)
