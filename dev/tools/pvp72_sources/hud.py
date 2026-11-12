"""Read-only HUD summaries. These helpers never advance or mutate a battle."""
import math
from .catalog import CARDS, actual_card
from .balance import deathmatch_blocked


def bank_page_size(rules, side, slots=None, scripted_waves=False):
    """Packets per bank page.

    PvP keeps the fixed seven (eight with the room's extra slot): its number
    keys and 翻面 page flip depend on it.  PvE and co-op buy slots in Dave's
    shop (up to thirteen) and the original seed bank grows with them, so every
    card the player owns is on the bar at once -- the packets shrink instead of
    hiding cards behind a second page.
    """
    base = 8 if (rules or {}).get("extra_slot") else 7
    if not scripted_waves:
        return base
    try:
        owned = int(slots or 0)
    except (TypeError, ValueError):
        owned = 0
    return max(1, owned)


def battle_deck(player):
    """Stable slot order shared by rendered banks and numeric shortcuts."""
    deck = player.get("deck", [])
    return ([key for key in deck if CARDS[key]["category"] != "secret"] +
            [key for key in deck if CARDS[key]["category"] == "secret"])


def battle_card(key, player, battle, night=False, copy_id=None):
    """Resolve the displayed card from the same state used by placement."""
    card = actual_card(key, player.get("secrets", ()), night)
    if key=='plant:模仿者' and 'secret:肆意模仿' in player.get('secrets',()):
        target=copy_id or player.get('last_copy_card')
        if target in player.get('deck',()) and target in CARDS and target!=key:
            card['cost']=actual_card(target,player.get('secrets',()),night)['cost']-100
    if key == "zombie:乌鸦" and "zsecret:鸦群" in player.get("secrets", ()):
        from .zombie_secrets import CROW_SURCHARGE
        units = battle.get("units") or ()
        if isinstance(units, dict):
            units = units.values()
        count = sum(1 for u in units if u.get("card_id", (u.get("card") or {}).get("id")) == "zombie:稻草人"
                    and u.get("side") == "zombie" and u.get("hp", 0) > 0)
        card["cost"] += CROW_SURCHARGE * count
    if card.get("native_input_name") == "地刺":
        price = battle.get("native_placement_state", {}).get("spike_cost")
        if isinstance(price, (int, float)) and not isinstance(price, bool) and math.isfinite(price) and price >= 0:
            card["cost"] = int(price) if price == int(price) else price
    return card


def latency_text(state):
    """Measured application RTT; a local/unmeasured link is never fake 0 ms."""
    status = state.get("network_latency_status", "offline")
    value = state.get("network_latency_ms")
    if status == "offline":
        return "本地"
    if status == "ok" and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0:
        prefix = "最慢延迟" if state.get("network_latency_scope") == "host_max" else "延迟"
        return "%s %d ms" % (prefix, round(value))
    return "延迟 --" + {"waiting": " · 待测", "stale": " · 过期", "disconnected": " · 断开"}.get(status, "")


def cooperation_hint(view):
    names={"plant":"植物方","zombie":"僵尸方"}
    if (view.get("mode") or "duel")=="duo":
        names={"plant":"植物1","zombie":"僵尸1","plant2":"植物2","zombie2":"僵尸2"}
    elif view.get('mode')=='coop':names={'plant':'植物1','plant2':'植物2'}
    elif view.get('mode')=='pve':names={'plant':'植物方'}
    phase=view.get("phase");field=None;verb=""
    if phase in ("banning","picking"):
        votes=view.get("restart_votes") or []
        if votes:
            if view.get('mode')=='duo':
                return '重开禁选 %d/%d 人同意 · 当前禁选继续'%(len(votes),view.get('restart_required',3))
            waiting="、".join(names[s] for s in names if s not in votes)
            return "已请求重开禁选 · 等待"+waiting+"同意（当前禁选继续）"
    if phase=="config":field="confirmed";verb="确认地图"
    elif phase=="loading":field="loaded";verb="载入完成"
    elif phase=="picking" and view.get("draft_stage")=="complete":field="ready";verb="点击准备"
    elif phase=="battle":
        if view.get("paused"):
            return ('全体玩家已同意暂停 · 任一玩家点击继续可恢复' if view.get('mode') in ('duo','coop')
                    else '双方已同意暂停 · 任一方点击继续可恢复')
        votes=view.get("pause_votes",[])
        if votes:
            waiting="、".join(names[s] for s in names if s not in votes)
            return "已请求暂停 · 等待"+waiting+"点击暂停同意（当前仍在战斗）"
        return ""
    elif phase=="result" and view.get("rematch_votes"):
        votes=view["rematch_votes"]
        if len(votes)==len(names) and len(set(votes.values()))>1:return "双方复赛选择不同 · 请统一同卡组、原阵营或交换阵营"
        return "已请求再战 · 等待"+"、".join(names[s] for s in names if s not in votes)+"选择相同复赛方式"
    if field:
        flags=view.get(field,{})
        return " · ".join(names[s]+("已就绪" if flags.get(s) else "待"+verb) for s in names)
    return ""


# A host-authoritative link has two failure modes that look identical to the
# player on the other end ("对面卡了") but have nothing to do with the network:
# the local client stops sending because its own UI took the input over, or the
# opponent has simply stopped sending. Both used to be invisible; these two
# helpers turn them into text.
INPUT_BLOCK_TEXT={"unfocused":"窗口不在前台 · 按键没有发送",
                  "viewing":"正在查看菜单 / 图鉴 · 你的操作已暂停",
                  "textbox":"搜索框占用键盘 · 你的操作已暂停",
                  "leaving":"离开确认框打开中 · 你的操作已暂停",
                  "audit":"日志写入失败 · 对局已暂停"}
SIDE_NAMES={"plant":"植物方","zombie":"僵尸方"}


def input_block_text(reason):
    """Player-facing text for a local input block, or '' when it is not one."""
    return INPUT_BLOCK_TEXT.get(reason,"")


def opponent_idle_text(view,local,threshold=1.5,grace=3.):
    """How long the other side has sent no input, in battle seconds.

    Reads only the authoritative ``last_input_tick`` already in the snapshot.
    Silence during the first ``grace`` seconds is ignored: a guest needs a
    moment to send its first frame.
    """
    battle=view.get("battle") or {}
    tick=battle.get("tick");rate=(view.get("rules") or {}).get("tick_rate",30) or 30
    if not isinstance(tick,int) or battle.get("time",0.)<grace:return ""
    # A pause rejects every input in the room, and a finished battle accepts
    # none; neither is the opponent going quiet on purpose.
    if view.get("paused") or battle.get("result") or view.get("result"):return ""
    parts=[]
    from .teams import scripted,team_of
    dormant=scripted(view.get("mode") or battle.get("mode") or "duel")
    for side,player in (battle.get("players") or {}).items():
        if side in local:continue
        # PvE / co-op: the zombie seat is dormant (the waves play it), never "idle".
        if dormant and team_of(side)=="zombie":continue
        if player.get("absent"):continue
        last=player.get("last_input_tick")
        if not isinstance(last,int):continue
        idle=(tick-last)/float(rate)
        if idle>=threshold:parts.append("%s已 %.0f 秒无操作"%(SIDE_NAMES.get(side,side),idle))
    return " · ".join(parts)


def page_summary(player, battle_time, deathmatch, page, capacity=8):
    keys=[key for key in player.get("deck",[]) if CARDS[key]["category"]!="secret"]
    pages=max(1,math.ceil(len(keys)/capacity));page%=pages
    hidden=keys[:page*capacity]+keys[(page+1)*capacity:]
    ready=0;next_cd=[];blocked=0
    for key in hidden:
        c=actual_card(key,player.get("secrets",()))
        if deathmatch and deathmatch_blocked(c):
            blocked+=1;continue
        cd=max(0.,player.get("cooldowns",{}).get(key,0)-battle_time)
        if cd:next_cd.append(cd)
        elif player.get("resource",0)>=c["cost"]:ready+=1
    text="其他页：%d 张可用"%ready if hidden else "本页已显示全部部署卡"
    if next_cd:text+=" · 最近 %.1fs"%min(next_cd)
    if blocked:text+=" · %d 张禁新生产"%blocked
    return dict(text=text,hidden=hidden,ready=ready,next_cd=min(next_cd) if next_cd else None,blocked=blocked)


def stage_text(battle,rules):
    now=battle.get("time",0);threshold=rules.get("deathmatch_seconds",420)
    waves=(battle.get("team") or {}).get("waves")
    if waves:
        # PvP66 PvE: no deathmatch; the wave line says what comes next.
        from .team_hud import wave_line
        return wave_line(battle.get("team"))
    if threshold>=1e8:return "生产者持续有效"
    if battle.get("deathmatch"):
        return "死斗：禁止新增生产者 · 已有生产 ×%g · 水中英雄每秒-1生命"%rules.get("production_multiplier",1.5)
    if now>=threshold-30:
        return "%d 秒后禁止新生产者 · 已有生产将提速"%max(0,math.ceil(threshold-now))
    return "距死斗 %02d:%02d · 届时禁止新增生产者"%(int(threshold-now)//60,int(threshold-now)%60)


def hero_status(hero,now):
    labels=[]
    if hero.get("control_until",0)>now:labels.append("受控 %.1fs"%(hero["control_until"]-now))
    elif hero.get("immune_until",0)>now:labels.append("控制保护 %.1fs"%(hero["immune_until"]-now))
    if hero.get("marked_until",0)>now:labels.append("已标记 %.1fs"%(hero["marked_until"]-now))
    # 计入胜率对局：黄金蓓蕾放下后只能由戴夫肉身拾取阳光。
    if hero.get("collect_locked_until",0)>now:labels.append("鼠标拾阳光 %.1fs"%(hero["collect_locked_until"]-now))
    return " · ".join(labels)


class FeedbackTracker:
    def __init__(self):
        self.key=None;self.tick=-1;self.losses={};self.notice="";self.until=0.

    def update(self,view,side):
        battle=view.get("battle") or {};now=battle.get("time",0.)
        key=(view.get("match_number"),view.get("terrain_hash"),side)
        lost=battle.get("players",{}).get(side,{}).get("stats",{}).get("producer_lost",0)
        if key!=self.key or battle.get("tick",0)<self.tick:
            self.key=key;self.losses={side:lost};self.notice="";self.until=0.
        delta=lost-self.losses.get(side,lost)
        if delta>0:
            self.notice=("本批损失 %d 座经济墓碑" if side=="zombie" else "本批损失 %d 个生产者")%delta
            self.until=now+4.
        self.losses[side]=lost;self.tick=battle.get("tick",0)
        units=battle.get("units",[])
        units=units.values() if isinstance(units,dict) else units
        graves=[u for u in units if u.get("behavior")=="grave" and u.get("side")=="zombie" and u.get("hp",0)>0]
        damaged=sum(u["hp"]<u.get("max_hp",u["hp"]) for u in graves)
        text=self.notice if now<self.until else ""
        if side=="zombie":
            status="出兵点 %d"%len(graves)
            if damaged:status+=" · %d 座墓碑受损"%damaged
            if not graves:status+=" · 无可用墓碑"
            text=status+(" / "+text if text else "")
        return text
