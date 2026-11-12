"""Full native world with two compact original seed banks over the lawn."""
import math
from .catalog import CARDS,RULES,actual_card
from .hud import FeedbackTracker,stage_text,hero_status,battle_deck,battle_card,bank_page_size,latency_text
from .balance import cooldown_mask_scale, deathmatch_blocked
from .team_hud import draw_team_panel, draw_scripted_tray, overhead, seat_label, mate_key, draw_enemy_overview
from .teams import scripted, team_of
from .simulation import GIFT_AMOUNT


def bank_layout(view,side,players,xs):
    """(view key, x, role) of the two permanent banks.

    1v1 / PvE: the two factions, as before. 2v2 / co-op: this player's own
    operable bank and the teammate's read-only bank; the two enemy decks live
    in the on-demand overview (draw_enemy_overview), not in a permanent bar."""
    if (view.get("mode") or "duel") in ("duo","coop") and mate_key(side) in players:
        return [(side,xs[0],"own"),(mate_key(side),xs[1],"mate")]
    return [("plant",xs[0],None),("zombie",xs[1],None)]


def seed_bank_geometry(tray, count):
    """Fit one original growing bank, including its resource end and cap.

    The native 1.5-unit tile advances by only one unit. Card artwork occupies
    .975 by 1.3125 units of its transparent 1.5-unit canvas (raw 显示牌).
    """
    x,y,w,h=tray
    unit=min(w/(max(1,count)+2.5),h/1.5)
    return (x,y,(max(1,count)+2.5)*unit,1.5*unit),unit


def draw_seed_bank(r, tray, count, faction, resource):
    bank,unit=seed_bank_geometry(tray,count)
    r.native_seed_bank(bank,count)
    x,y=bank[:2]
    if faction=="zombie":
        # The shared original end contains a sun. Cover that illustration with
        # this faction's resource while retaining the same continuous wood.
        r.pg.draw.rect(r.screen,(105,53,22),(x+.22*unit,y+.2*unit,1.08*unit,.76*unit))
        r.icon("脑子",(x+.25*unit,y+.15*unit,unit,.8*unit))
    value=str(int(resource)) if resource is not None else "—"
    font_size=max(10,min(18,int(unit*.33)))
    while font_size>9 and r.text_size(r.font(font_size),value)[0]>1.2*unit:font_size-=1
    tw=r.text_size(r.font(font_size),value)[0]
    r.text(value,(x+.7*unit-tw/2,y+1.04*unit),(43,33,20),font_size)
    return bank,unit


def card_mask_scale(p, key, card, cd, game):
    """Mask height: the recorded span of the running cooldown (PvP64), else the old estimate."""
    span = (p.get("cooldown_spans") or {}).get(key)
    if span and span + 1e-6 >= cd:
        return max(.01, span)
    return cooldown_mask_scale(card["cooldown"], cd, game.get("time", 0.), game.get("deathmatch", False))


def pause_label(view,state):
    if view.get('paused'):return '继续'
    votes=view.get('pause_votes',[])
    if not votes:return '暂停'
    seat=(view.get('battle') or {}).get('local_seat') or state.get('active_side','plant')
    return '撤回暂停' if seat in votes else '同意暂停'


def draw(r,view,state):
    if state.get("touch_mode"):
        draw_touch(r,view,state)
    else:
        _draw_desktop(r,view,state)
    from .deathmatch_presentation import draw_notice
    draw_notice(r,view)
    pacing=view.get('pacing') or {}
    if pacing.get('slow'):
        r.text('主机负载慢放 ×%.2f'%pacing['scale'],(r.screen.get_width()//2-90,105),(255,213,114),16)
        # PvP71: Android hosts add core/frequency/thermal for screenshot reports.
        from .perf_hooks import status_line
        line=status_line()
        if line:r.text(line,(r.screen.get_width()//2-90,126),(255,213,114),13)
    if (view.get("mode") or "duel")=="duo" and state.get("enemy_overview") and (view.get("battle") or {}).get("players"):
        width,height=r.screen.get_size();touch=bool(state.get("touch_mode"))
        rect=(8,258,width-150,min(260,height-340)) if touch else (width//2+8,190,width//2-120,min(250,height-250))
        draw_enemy_overview(r,view,state,view["battle"],view["battle"]["players"],state.get("active_side","plant"),rect)


def draw_placement_ring(r,view,state,game,terrain,players,side):
    """Ranked matches: green reach ellipse around the deploying Dave.

    The golden bloom shows its forbidden inner disc in red. Pure overlay; the
    authority validates the same ring in NativeBattle.placement.
    """
    from .pvp61_ranked import ranked,placement_ring,hero_center,ELLIPSE_X
    rules=view.get("rules") or {}
    key=state.get("selected_card")
    if not ranked(rules) or not key or not terrain or side not in players or not getattr(r,"camera",None):return
    if side not in view.get("local_sides",[side]):return
    card=battle_card(key,players[side],game,terrain.get("environment",{}).get("night",False),state.get('copy'))
    if card.get("category")=="secret":return
    if side=="zombie" and card.get("behavior")!="grave" and "zsecret:解除封印" in players[side].get("secrets",()):return
    inner,outer=placement_ring(card)
    tile=terrain.get("tile_size",48);scale=r.camera[2]
    x,y=hero_center(players[side]["x"],players[side]["y"],tile)
    cx,cy=r.world.point(x,y)
    ry=max(4,round(outer*tile*scale));rx=max(4,round(outer*tile*scale*ELLIPSE_X))
    w,h=rx*2+8,ry*2+8
    left,top=round(cx)-w//2,round(cy)-h//2
    # Only the on-screen part is allocated and the surface is reused while its
    # size holds: a full zoomed ring was a fresh 10-30 MB alpha surface every
    # frame and crashed the match with "Out of memory" when RAM ran short.
    clip=r.pg.Rect(left,top,w,h).clip(r.screen.get_rect())
    if clip.w<=0 or clip.h<=0:return
    try:
        overlay=getattr(r,"_ring_overlay",None)
        if overlay is None or overlay.get_size()!=clip.size:
            r._ring_overlay=overlay=None
            overlay=r._ring_overlay=r.pg.Surface(clip.size,r.pg.SRCALPHA)
    except r.pg.error:
        return
    overlay.fill((0,0,0,0))
    ox,oy=left-clip.x,top-clip.y
    def ellipse(a,b):return r.pg.Rect(ox+w//2-a,oy+h//2-b,a*2,b*2)
    line=max(2,round(tile*scale*.06))
    r.pg.draw.ellipse(overlay,(60,220,90,42),ellipse(rx,ry))
    r.pg.draw.ellipse(overlay,(80,240,110,220),ellipse(rx,ry),line)
    if inner>0:
        hy=max(2,round(inner*tile*scale));hx=max(2,round(inner*tile*scale*ELLIPSE_X))
        r.pg.draw.ellipse(overlay,(230,60,50,70),ellipse(hx,hy))
        r.pg.draw.ellipse(overlay,(240,70,60,230),ellipse(hx,hy),line)
    r.screen.blit(overlay,clip.topleft)


def mark_grave(r,fitted,terrain,game,state):
    """解除封印: show the chosen grave on the minimap."""
    units=game.get("units") or {}
    units=units.values() if isinstance(units,dict) else units
    grave=next((u for u in units if u.get("id")==state.get("grave")),None)
    if not grave or not terrain or not fitted:return
    px=fitted.x+grave["x"]/terrain["width"]*fitted.w
    py=fitted.y+grave["y"]/terrain["height"]*fitted.h
    r.pg.draw.rect(r.screen,(255,214,92),(int(px)-4,int(py)-7,8,8),2)


def draw_touch(r,view,state):
    """Thumb-first battle layout: taller banks, corner virtual pads, wide targets."""
    from .rendering import COLORS
    from .world_view import WorldView
    from .touch import thumb_clusters
    width,height=r.screen.get_size();r.controls=[]
    game=view.get("battle") or {};terrain=game.get("map") or view.get("map")
    players=game.get("players",{});side=state.get("active_side","plant")
    if not hasattr(r,"world"):r.world=WorldView(r.pg,r.bridge,r.asset_dir)
    r.world.local_pixels=getattr(r,"local_pixels",None)
    r.camera=r.world.render(r.screen,game,(0,0,width,height),side,state,terrain=terrain)
    draw_placement_ring(r,view,state,game,terrain,players,side)
    if not terrain or not players:
        r.text("正在载入战场…",(32,42),COLORS["text"],23);return
    local=view.get("local_sides",[side]);rules=view.get("rules",RULES)
    bank_w=(width-160)//2;bank_h=100
    for key,x,role in bank_layout(view,side,players,(8,16+bank_w)):
        faction=team_of(key);p=players[key];active=key==side;owned=faction in local and role!="mate"
        tray=(x,8,bank_w,bank_h)
        if p.get("absent"):
            draw_scripted_tray(r,tray,game);continue
        if role=="mate" and state.get("mate_collapsed"):
            # Touch: the teammate bank folds into a small tab, freeing the lawn.
            r.button("展开队友卡栏",(x,8,140,40),("hud_toggle","mate_collapsed"),size=15)
            continue
        deck=battle_deck(p);page=state.get("battle_page",0) if active else 0
        page_size=bank_page_size(rules,faction,len(deck),scripted(view.get("mode")));page%=max(1,math.ceil(len(deck)/page_size));visible=deck[page*page_size:(page+1)*page_size]
        bank,unit=draw_seed_bank(r,tray,page_size,faction,p.get("resource"))
        r.controls.append((r.pg.Rect(tray),("hud_block",)))
        if active:r.pg.draw.rect(r.screen,COLORS["gold"],bank,2)
        pitch=unit;cw=.975*unit;ch=1.3125*unit
        for index in range(page_size):
            rect=(bank[0]+(1.5+index)*pitch,bank[1]+.1*unit,cw,ch)
            if index>=len(visible):continue
            key=visible[index];card=battle_card(key,p,game,terrain.get("environment",{}).get("night",False),state.get("copy") if active else (view.get("copy_targets") or {}).get(key));secret=card["category"]=="secret"
            cd=max(0,p.get("cooldowns",{}).get(key,0)-game.get("time",0))
            blocked=bool(game.get("deathmatch") and deathmatch_blocked(card))
            r.seed_packet(key,rect,selected=active and key==state.get("selected_card"),label=False,cost=card["cost"],display_card=card,disabled=blocked)
            if cd:
                shade=r.pg.Surface((int(cw),int(ch)),r.pg.SRCALPHA);shade.fill((0,0,0,160))
                fill=min(int(ch),int(ch*cd/card_mask_scale(p,key,card,cd,game)))
                r.screen.blit(shade,rect[:2],r.pg.Rect(0,0,int(cw),fill))
            if blocked:r.text("禁放",(rect[0]+4,rect[1]+ch//2-7),COLORS["bad"],15,cw-8)
            elif secret:r.text("秘",(rect[0]+4,rect[1]+4),(69,38,16),13)
            elif cd and state.get("numeric_cd",True):r.text("%.1f"%cd,(rect[0]+4,rect[1]+ch//2-7),COLORS["text"],15,cw-8)
            elif owned and active:r.text(str(index+1),(rect[0]+4,rect[1]+3),(38,59,31),12)
            if owned and active and not secret:r.controls.append((r.pg.Rect(rect),("select_card",key)))
        if role=="mate":
            # Read-only: dimmed, labelled, no select_card targets.
            veil=r.pg.Surface((int(bank[2]),int(bank[3])),r.pg.SRCALPHA);veil.fill((20,20,26,70));r.screen.blit(veil,bank[:2])
        hp=max(0,p.get("hp",0));maximum=p.get("max_hp",1000)
        r.pg.draw.rect(r.screen,(36,28,34),(x,bank_h+14,bank_w,24))
        r.pg.draw.rect(r.screen,(90,38,28),(x+3,bank_h+30,bank_w-6,5))
        r.pg.draw.rect(r.screen,COLORS[faction],(x+3,bank_h+30,int((bank_w-6)*min(1.,hp/max(1,maximum))),5))
        r.text(("队友 · 只读 · " if role=="mate" else "")+("普通戴夫" if faction=="plant" else "僵尸戴夫")+"  %d / %d"%(hp,maximum),(x+9,bank_h+16),COLORS["text"],13,bank_w-126)
        if owned:
            r.button("操作此方" if not active else "当前操作",(x+bank_w-108,bank_h+13,108,26),("active_side",faction),selected=active,accent=COLORS[faction],size=13)
        if role=="mate":
            r.button("收起",(x+bank_w-70,bank_h+13,70,26),("hud_toggle","mate_collapsed"),size=13)
    mx=width-130
    r.button("菜单",(mx,8,122,40),("menu","settings"),size=18)
    r.button("帮助",(mx,54,122,36),("menu","help"),size=15)
    r.button(pause_label(view,state),(mx,96,122,36),("pause",),size=15)
    if (view.get("mode") or "duel") in ("duo","coop"):
        r.button("资助队友 %d" % GIFT_AMOUNT,(mx,138,122,36),("gift",),size=14)
    seconds=int(game.get("time",0));timer="%02d:%02d"%(seconds//60,seconds%60)
    plaque=(width//2-72,bank_h+14,144,30)
    r.box(plaque,(40,31,24));r.text(timer+(" 死斗" if game.get("deathmatch") else ""),(plaque[0]+14,bank_h+18),COLORS["gold"],20,116)
    r.controls.append((r.pg.Rect(plaque),("hud_block",)))
    fitted=r.world.preview(r.screen,terrain,(width//2-84,bank_h+50,168,62),players)
    r.world.minimap_flags(r.screen,game,terrain,fitted)
    r.controls.append((r.pg.Rect(width//2-84,bank_h+50,168,62),("hud_block",)))
    move,column=thumb_clusters(width,height,state)
    x0=move[0]+move[2]+10;x1=column[0]-10
    r.box((x0,height-30,max(120,x1-x0),26),(34,30,24))
    r.controls.append((r.pg.Rect(x0,height-30,max(120,x1-x0),26),("hud_block",)))
    selected=CARDS.get(state.get("selected_card"))
    preview=state.get("placement_preview")
    if not hasattr(r,"_battle_feedback"):r._battle_feedback=FeedbackTracker()
    feedback=r._battle_feedback.update(view,side)
    message=preview.get("error") if preview and preview.get("error") else state.get("message")
    if selected:
        hint=(" · 跟随戴夫朝向种植 · 自动/左/右可切换" if state.get('touch_quick_plant',True)
              else " · 固定朝向种植 · 点自动恢复跟随") if side=="plant" else " · 点按墓碑出兵 · 虚拟键取消"
        message=message or selected["name"]+hint
    message=message or feedback or stage_text(game,rules)
    r.text(message,(x0+10,height-25),COLORS["gold"],14,max(100,x1-x0-190))
    r.text(latency_text(state),(max(x0+120,x1-176),height-25),COLORS["muted"],13,168)
    # The floating stage line is skipped here: the bottom bar already carries
    # the same stage_text when nothing more urgent is showing.
    if (view.get("mode") or "duel")=="duo":
        r.button("收起敌方卡组" if state.get("enemy_overview") else "敌方卡组",(width//2-84,bank_h+120,168,34),("hud_toggle","enemy_overview"),size=15)
    draw_team_panel(r,view,state,game,players,side)
    for faction,p in players.items():
        if p.get("absent"):continue
        status=overhead(game,faction,p) or hero_status(p,game.get("time",0))
        if status:
            x,y=r.world.point(p["x"],p["y"])
            r.text(status,(x-48,y-2*terrain.get("tile_size",48)*r.camera[2]-21),(83,41,14),14)
    recent=any(e.get("event")=="damage" and e.get("target")==side and e.get("kind") in ("ash","chomp","crush") and game.get("time",0)-e.get("time",0)<2 for e in game.get("events",[]))
    if recent:r.text("灰烬 / 吞噬：单轮伤害保护",(12,bank_h+52),(122,35,21),14)
    notice_w=width//2-108
    if state.get("cooperation_hint"):
        r.box((8,bank_h+84,notice_w,29),(40,31,24))
        r.text(state["cooperation_hint"],(15,bank_h+90),COLORS["gold"],14,notice_w-18)
    if state.get("link_notice"):
        r.box((8,bank_h+117,notice_w,29),(52,28,24))
        r.text(state["link_notice"],(15,bank_h+123),COLORS["bad"],14,notice_w-18)


def _draw_desktop(r,view,state):
    from .rendering import COLORS
    from .world_view import WorldView
    width,height=r.screen.get_size();r.controls=[]
    game=view.get("battle") or {};terrain=game.get("map") or view.get("map")
    players=game.get("players",{});side=state.get("active_side","plant")
    if not hasattr(r,"world"):r.world=WorldView(r.pg,r.bridge,r.asset_dir)
    r.world.local_pixels=getattr(r,"local_pixels",None)
    r.camera=r.world.render(r.screen,game,(0,0,width,height),side,state,terrain=terrain)
    draw_placement_ring(r,view,state,game,terrain,players,side)
    if not terrain or not players:
        r.text("正在载入战场…",(32,42),COLORS["text"],23);return
    local=view.get("local_sides",[side]);rules=view.get("rules",RULES)
    bank_w=(width-126)//2;bank_h=82;gap=8
    for key,x,role in bank_layout(view,side,players,(8,16+bank_w)):
        faction=team_of(key);p=players[key];active=key==side;owned=faction in local and role!="mate"
        tray=(x,8,bank_w,bank_h)
        if p.get("absent"):
            draw_scripted_tray(r,tray,game);continue
        deck=battle_deck(p);page=state.get("battle_page",0) if active else 0
        page_size=bank_page_size(rules,faction,len(deck),scripted(view.get("mode")));page%=max(1,math.ceil(len(deck)/page_size));visible=deck[page*page_size:(page+1)*page_size]
        bank,unit=draw_seed_bank(r,tray,page_size,faction,p.get("resource"))
        r.controls.append((r.pg.Rect(tray),("hud_block",)))
        if active:r.pg.draw.rect(r.screen,COLORS["gold"],bank,2)
        pitch=unit;cw=.975*unit;ch=1.3125*unit
        for index in range(page_size):
            rect=(bank[0]+(1.5+index)*pitch,bank[1]+.1*unit,cw,ch)
            if index>=len(visible):continue
            key=visible[index];card=battle_card(key,p,game,terrain.get("environment",{}).get("night",False),state.get("copy") if active else (view.get("copy_targets") or {}).get(key));secret=card["category"]=="secret"
            cd=max(0,p.get("cooldowns",{}).get(key,0)-game.get("time",0))
            blocked=bool(game.get("deathmatch") and deathmatch_blocked(card))
            r.seed_packet(key,rect,selected=active and key==state.get("selected_card"),label=False,cost=card["cost"],display_card=card,disabled=blocked)
            if cd:
                shade=r.pg.Surface((int(cw),int(ch)),r.pg.SRCALPHA);shade.fill((0,0,0,160))
                fill=min(int(ch),int(ch*cd/card_mask_scale(p,key,card,cd,game)))
                r.screen.blit(shade,rect[:2],r.pg.Rect(0,0,int(cw),fill))
            if blocked:r.text("禁放",(rect[0]+3,rect[1]+25),COLORS["bad"],13,cw-6)
            elif secret:r.text("秘",(rect[0]+3,rect[1]+3),(69,38,16),12)
            elif cd and state.get("numeric_cd",True):r.text("%.1f"%cd,(rect[0]+3,rect[1]+25),COLORS["text"],14,cw-6)
            if owned and active and not state.get('touch_mode') and index<8:
                label=r.pg.key.name(state.get('bindings',{}).get('slot_%d'%(index+1),r.pg.K_1+index)).upper()
                bw=min(cw-4,max(18,r.text_size(r.font(13),label)[0]+6))
                r.pg.draw.rect(r.screen,(30,34,29),(rect[0]+2,rect[1]+2,bw,18))
                r.text(label,(rect[0]+5,rect[1]+3),(255,245,200),13,bw-4)
            if owned and active and not secret:r.controls.append((r.pg.Rect(rect),("select_card",key)))
        if role=="mate":
            # Read-only: dimmed, labelled, no select_card targets.
            veil=r.pg.Surface((int(bank[2]),int(bank[3])),r.pg.SRCALPHA);veil.fill((20,20,26,70));r.screen.blit(veil,bank[:2])
        hp=max(0,p.get("hp",0));maximum=p.get("max_hp",1000)
        r.pg.draw.rect(r.screen,(36,28,34),(x,94,bank_w,21))
        r.pg.draw.rect(r.screen,(90,38,28),(x+3,109,bank_w-6,4))
        r.pg.draw.rect(r.screen,COLORS[faction],(x+3,109,int((bank_w-6)*min(1.,hp/max(1,maximum))),4))
        member=next((peer for peer,team in view.get('members',{}).items() if team==seat_label(key,game)),None)
        name=view.get('player_profiles',{}).get(member,{}).get('name') or ('普通戴夫' if faction=='plant' else '僵尸戴夫')
        r.text(("队友 · 只读 · " if role=="mate" else "")+name+"  %d / %d"%(hp,maximum),(x+8,95),COLORS["text"],12,bank_w-115)
        if owned:
            r.button("操作此方" if not active else "当前操作",(x+bank_w-94,94,94,21),("active_side",faction),selected=active,accent=COLORS[faction],size=12)
    mx=width-99
    r.button("菜单",(mx,8,91,32),("menu","settings"),size=16)
    r.button("帮助",(mx,47,91,28),("menu","help"),size=14)
    def shortcut(label,key):
        return label+(' '+r.pg.key.name(state.get('bindings',{}).get(key,0)).upper() if not state.get('touch_mode') and key in state.get('bindings',{}) else '')
    r.button(shortcut(pause_label(view,state),'pause'),(mx,83,91,28),("pause",),size=14)
    if (view.get("mode") or "duel") in ("duo","coop"):
        r.button(shortcut("资助队友 %d" % GIFT_AMOUNT,'gift'),(mx,120,91,28),("gift",),size=13)
    cancel_key=r.pg.key.name(state.get('bindings',{}).get('cancel',r.pg.K_c)).upper()
    r.button('取消 '+cancel_key,(mx,191,91,30),('cancel_action',),size=14)
    seconds=int(game.get("time",0));timer="%02d:%02d"%(seconds//60,seconds%60)
    plaque=(width//2-64,121,128,27)
    r.box(plaque,(40,31,24));r.text(timer+(" 死斗" if game.get("deathmatch") else ""),(plaque[0]+13,125),COLORS["gold"],18,108)
    stands=(game.get("zsecrets") or {}).get("last_stand") or {}
    if stands:
        left=min(stands.values())
        r.box((plaque[0]-20,plaque[1]+30,168,24),(70,22,18))
        r.text("最后攻势 %d 秒"%int(left+.99),(plaque[0]-12,plaque[1]+33),COLORS["bad"],16,152)
    r.controls.append((r.pg.Rect(plaque),("hud_block",)))
    minimap=(mx-178,121,168,62)
    fitted=r.world.preview(r.screen,terrain,minimap,players)
    r.world.minimap_flags(r.screen,game,terrain,fitted)
    mark_grave(r,fitted,terrain,game,state)
    r.controls.append((r.pg.Rect(minimap),("hud_block",)))
    if "zombie" in local:
        key=r.pg.key.name(state.get("bindings",{}).get("command",r.pg.K_f)).upper()
        r.button(key+" · "+("跟随戴夫" if game.get("command")=="follow" else "追击敌方"),(10,121,162,27),("command",),size=14)
    if 'plant' in local and side=='plant':
        left=180 if 'zombie' in local else 10
        r.button(shortcut('铲子','shovel'),(left,121,80,27),('shovel',),selected=state.get('shovel',False),size=14)
        icon=r.artwork('铲子')
        if icon is not None:r.screen.blit(r.pg.transform.scale(icon,(24,24)),(left+2,122))
    if 'zombie' in local and side=='zombie':
        r.button(shortcut('清除召集' if game.get('rally_point') else '召集','rally'),(180,121,88,27),('rally',),selected=state.get('rally',False),size=14)
        from .teams import own_rally_seat
        r.world.flag(r.screen,190,144,17,own_rally_seat(game))
    # Context lives at the edge. The lawn and heroes retain the original scale.
    if side in local:
        remaining=max(0,players[side].get('teleport_ready_at',0)-game.get('time',0))
        left=278 if 'zombie' in local else 100
        r.button('传送 %.1fs'%remaining if remaining else shortcut('传送','teleport'),(left,121,105,27),('teleport',),selected=state.get('teleport',False),size=14)
    r.box((0,height-28,width,28),(34,30,24))
    r.controls.append((r.pg.Rect(0,height-28,width,28),("hud_block",)))
    selected=CARDS.get(state.get("selected_card"))
    preview=state.get("placement_preview")
    if not hasattr(r,"_battle_feedback"):r._battle_feedback=FeedbackTracker()
    feedback=r._battle_feedback.update(view,side)
    message=preview.get("error") if preview and preview.get("error") else state.get("message")
    if selected:
        hint=(" · 左键向左 / 右键向右 / %s取消" if side=="plant" else " · 点击墓碑出兵 / %s取消") % cancel_key
        message=message or selected["name"]+hint
    message=message or feedback or stage_text(game,rules)
    r.text(message,(12,height-23),COLORS["gold"],14,width-205)
    r.text(latency_text(state),(width-192,height-23),COLORS["muted"],13,184)
    if len(players[side].get("deck",[]))>bank_page_size(rules,side,len(players[side].get("deck",[])),scripted(view.get("mode"))):
        r.button("翻面",(width-85,height-26,78,24),("battle_page",),size=13)
    stage_label=stage_text(game,rules)
    # Native outlined lettering stays readable over sky, roof and foliage.
    for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)):
        r.text(stage_label,(12+dx,157+dy),(27,23,17),14,width-260)
    r.text(stage_label,(12,157),COLORS["gold"],14,width-260)
    if (view.get("mode") or "duel")=="duo":
        r.button("收起敌方卡组" if state.get("enemy_overview") else "敌方卡组",(mx,154,91,28),("hud_toggle","enemy_overview"),size=13)
    draw_team_panel(r,view,state,game,players,side)
    for faction,p in players.items():
        if p.get("absent"):continue
        status=overhead(game,faction,p) or hero_status(p,game.get("time",0))
        if status:
            x,y=r.world.point(p["x"],p["y"])
            r.text(status,(x-48,y-2*terrain.get("tile_size",48)*r.camera[2]-21),(83,41,14),14)
    recent=any(e.get("event")=="damage" and e.get("target")==side and e.get("kind") in ("ash","chomp","crush") and game.get("time",0)-e.get("time",0)<2 for e in game.get("events",[]))
    if recent:r.text("灰烬 / 吞噬：单轮伤害保护",(12,179),(122,35,21),14)
    if state.get("cooperation_hint"):
        r.box((8,199,width-210,29),(40,31,24))
        r.text(state["cooperation_hint"],(15,205),COLORS["gold"],14,width-228)
    # Neither text below is a network problem: the local client stopped sending,
    # or the other player did. Saying which one keeps "对面卡了" from being the
    # only available diagnosis.
    if state.get("link_notice"):
        r.box((8,232,width-210,29),(52,28,24))
        r.text(state["link_notice"],(15,238),COLORS["bad"],14,width-228)
    if side=='plant' and 'plant' in local and state.get('shovel'):
        cursor=r.artwork('铲子')
        if cursor is not None:
            mx,my=r.pg.mouse.get_pos()
            r.screen.blit(r.pg.transform.scale(cursor,(36,36)),(mx-8,my-8))
    # 瞄准态：鼠标位置的原生红色准星。引擎主循环（偏移 151522 段）就是拿同一张
    # `轰炸` 居中画在鼠标上；这里沿用同一个资源、同一个"一格"尺寸，别自创圆圈。
    if side=='plant' and 'plant' in local and (game.get("players",{}).get("plant") or {}).get("cannon_aim"):
        mark=r.artwork('轰炸')
        if mark is not None:
            mx,my=r.pg.mouse.get_pos()
            size=max(16,round(terrain.get("tile_size",48)*r.camera[2]))
            r.screen.blit(r.pg.transform.scale(mark,(size,size)),(mx-size//2,my-size//2))
