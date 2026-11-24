"""PvP66 battle overlay for 2v2, co-op and PvE: waves, teammates, revive."""
from .teams import REVIVE_SECONDS, team_of

GOLD = (250, 210, 89)
TEXT = (245, 236, 210)
BAD = (255, 140, 120)
PANEL = (40, 31, 24)


def mate_key(key):
    """View key of the teammate (views always name the local seat by faction)."""
    if key in ("plant", "zombie"):
        return key + "2"
    return team_of(key)


def seat_label(key, game):
    """Real seat behind a view key, undoing the local perspective swap."""
    local = game.get("local_seat")
    if local and key == team_of(local):
        return local
    if local and key == local:
        return team_of(local)
    return key


def wave_line(team):
    waves = (team or {}).get("waves")
    if not waves:
        return ""
    line = "第 %d 天 · 第 %d / %d 波" % (waves["day"], waves["wave"], waves["waves"])
    if waves.get("next_in") is not None:
        line += " · %s %d 秒" % ("一大波僵尸" if waves.get("next_flag") else "下一波", int(waves["next_in"]))
    elif waves.get('waiting_for_clear'):
        line += ' · 本波清理 %d/%d%%'%(waves.get('clear_percent',0),waves.get('clear_required',80))
    line += " · 场上僵尸 %d" % waves.get("remaining", 0)
    if waves.get('max_zombies') is not None:line += '/%d'%waves['max_zombies']
    if waves.get('spawn_queued'):line += ' · 待入场 %d'%waves['spawn_queued']
    line += " · 本局金币 " + coin_text(team)
    return line


def coin_text(team):
    """Raw drops remain integral; campaign income is half, with carried halves."""
    coins = max(0, int((team or {}).get("coins", 0)))
    return "%d%s" % (coins // 2, ".5" if coins % 2 else "")


def overhead(game, key, player):
    """Text over a Dave: fallen / revive progress in team modes."""
    team = game.get("team")
    if not team or player.get("absent"):
        return ""
    seat = seat_label(key, game)
    if player.get("hp", 1) <= 0:
        progress = (team.get("revive") or {}).get(seat, 0)
        return "阵亡 · 复活 %d%%" % int(progress * 100) if progress else "阵亡 · 队友接触可复活"
    return ""


def draw_team_panel(r, view, state, game, players, side):
    team = game.get("team")
    if not team:
        return
    width, height = r.screen.get_size()
    request=(game.get('surrender_requests') or {}).get(team_of(side))
    if request:
        seat=seat_label(side,game)
        x=(width-460)//2
        r.box((x,height//2-78,460,82),PANEL)
        mine=request['seat']==seat
        r.text('投降请求 · 等待队友确认' if mine else '队友请求投降，本局是否认输？',
               (x+12,height//2-68),GOLD,18,436)
        if mine:r.button('撤回请求',(x+12,height//2-37,140,32),('surrender_vote','cancel',request['id']),size=15)
        else:
            r.button('同意投降',(x+12,height//2-37,140,32),('surrender_vote','accept',request['id']),size=15)
            r.button('继续战斗',(x+168,height//2-37,140,32),('surrender_vote','decline',request['id']),size=15)
    lines = []        # the wave line is the stage line (hud.stage_text)
    mate = players.get(mate_key(side))
    if mate and not mate.get("absent"):
        if mate.get("hp", 0) <= 0:
            progress = (team.get("revive") or {}).get(seat_label(mate_key(side), game), 0)
            lines.append(("队友阵亡：站到其身体上 %d 秒可复活（%d%%）" % (int(REVIVE_SECONDS), int(progress * 100)), BAD))
        elif (view.get("mode") or "duel") != "duo":
            # 2v2 shows the teammate's life in its own top bar; only co-op
            # needs this line (and every mode needs the revive line above).
            lines.append(("队友生命 %d / %d · 碰触倒地队友可立刻扶起" % (max(0, mate.get("hp", 0)), mate.get("max_hp", 40)), TEXT))
    me = players.get(side) or {}
    if not lines and not (me.get("hp", 1) <= 0 and not me.get("absent")):
        return
    box_w = min(560, width - 220)
    x = (width - box_w) // 2
    y = 152
    line_h=22
    font_size=15
    if state.get("touch_mode"):
        from .touch import placed_slots
        x,y,box_w,box_h=placed_slots(width,height,state)["team_info"]
        line_h=max(12,int(22*box_h/30))
        font_size=max(10,int(15*box_h/30))
    if lines:
        r.box((x, y, box_w, 8 + line_h * len(lines)), PANEL)
    for index, (line, color) in enumerate(lines):
        r.text(line, (x + 10, y + 5 + line_h * index), color, font_size, box_w - 20)
    if (mate and not mate.get("absent") and mate.get("deck") and (view.get("mode") or "duel") not in ("duo","coop")):
        # Co-op: the teammate strip (2v2 shows the teammate in the top bar).
        if state.get("mate_collapsed"):
            r.button("展开队友卡组", (x, y + 10 + 22 * len(lines), 110, 26), ("hud_toggle", "mate_collapsed"), size=13)
        else:
            draw_mate_deck(r, mate, (x, y + 10 + 22 * len(lines), box_w))
            r.button("收起", (x + box_w - 52, y + 14 + 22 * len(lines), 48, 26), ("hud_toggle", "mate_collapsed"), size=12)
    if me.get("hp", 1) <= 0 and not me.get("absent"):
        message = "你已阵亡 · 观战中：队友接触你的身体 %d 秒即可复活" % int(REVIVE_SECONDS)
        w = min(640, width - 40)
        r.box(((width - w) // 2, height // 2 - 30, w, 44), (60, 20, 18))
        r.text(message, ((width - w) // 2 + 14, height // 2 - 20), BAD, 18, w - 28)


def draw_mate_deck(r, mate, area):
    """The teammate's deck: small, read-only seed packets (no controls)."""
    from .hud import battle_deck
    x, y, w = area
    deck = battle_deck(mate)
    pw, ph = 26, 36
    r.box((x, y, min(w, 64 + len(deck) * (pw + 3)), ph + 8), PANEL)
    r.text("队友卡组", (x + 6, y + 13), TEXT, 12, 56)
    for index, key in enumerate(deck):
        r.seed_packet(key, (x + 62 + index * (pw + 3), y + 4, pw, ph), label=False)


def draw_enemy_overview(r, view, state, game, players, side, rect):
    """2v2: both enemy seats on demand - name, life, resource, read-only deck."""
    from .hud import battle_deck
    x, y, w, h = rect
    r.box(rect, PANEL)
    r.controls.append((r.pg.Rect(rect), ("hud_block",)))
    foe = "zombie" if team_of(side) == "plant" else "plant"
    keys = [k for k in (foe, foe + "2") if k in players and not players[k].get("absent")]
    row_h = max(60, (h - 30) // max(1, len(keys)))
    r.text("敌方卡组（公开信息，只读）", (x + 10, y + 6), GOLD, 15, w - 20)
    for index, key in enumerate(keys):
        p = players[key]
        top = y + 28 + index * row_h
        seat = seat_label(key, game)
        member = next((peer for peer, s in view.get("members", {}).items() if s == seat), None)
        label = ("植物" if seat.startswith("plant") else "僵尸") + ("2" if seat.endswith("2") else "1")
        name = view.get("player_profiles", {}).get(member, {}).get("name")
        name = label + (" · " + name if name else "")
        r.text("%s · 生命 %d/%d · %s %d" % (name, max(0, p.get("hp", 0)), p.get("max_hp", 40),
                                           "阳光" if foe == "plant" else "脑光", int(p.get("resource") or 0)),
               (x + 10, top), TEXT, 13, w - 20)
        deck = battle_deck(p)
        pw = min(34, (w - 20) / max(1, len(deck)) - 3)
        for i, card in enumerate(deck):
            r.seed_packet(card, (x + 10 + i * (pw + 3), top + 18, pw, pw * 1.35), label=False)


def draw_scripted_tray(r, tray, game):
    """The zombie tray of a PvE match shows the waves instead of a deck."""
    x, y, w, h = tray
    r.native_frame("作战卡", tray, 3)
    team = game.get("team") or {}
    waves = team.get("waves") or {}
    r.icon("脑子", (x + 9, y + 9, 31, 31))
    heading = "我是僵尸 · 第 %d 场"%game.get("solo_stage",1) if game.get("solo_mode")=="izombie" else "僵尸来袭"
    r.text(heading, (x + 50, y + 8), TEXT, 17, w - 60)
    if waves:
        r.text("第 %d / %d 波 · 场上 %d" % (waves.get("wave", 0), waves.get("waves", 0), waves.get("remaining", 0)),
               (x + 50, y + 34), GOLD, 15, w - 160)
    r.icon("金币", (x + w - 110, y + 10, 30, 30))
    r.text(coin_text(team), (x + w - 74, y + 14), GOLD, 18, 70)
