"""Host-owned co-op growth belongs to plant/plant2, never a connection."""
import hashlib
import json
import shutil
import time
import uuid
from pathlib import Path

from .pve import Campaign, STARTER_PLANTS
from .teams import COOP, team_of


class CoopProgress:
    def __init__(self):
        self.path=None
        self._saved=None
        self.reset()

    def reset(self):
        self.run_id = uuid.uuid4().hex
        self.day=1
        self.campaigns = {}
        self.income = {}
        self.applied = set()
        self.ensure(None)
        self._saved=None

    def ensure(self, room):
        changed = False
        if room is not None and room.mode != COOP:
            return changed
        for seat in ('plant','plant2'):
            if seat in self.campaigns:
                self.campaigns[seat].restrict_coop()
                continue
            seed = int(hashlib.sha256((self.run_id + seat).encode('utf8')).hexdigest()[:8], 16) % (2**31)
            self.campaigns[seat] = Campaign(seed=seed, coop=True)
            changed = True
        return changed

    def bind(self,path,initial=None):
        """Migrate host progress once; later rooms load both seats from disk."""
        path=Path(path)
        if self.path==path:return
        self.path=path
        if path.exists():
            try:
                value=json.loads(path.read_text('utf8'))
                if value.get('format')!='pvp67-coop-seats-1':raise ValueError('未知合作存档格式')
                self.run_id=str(value['run_id']);self.day=max(1,int(value['day']))
                self.campaigns={s:Campaign.from_dict(value['seats'][s]) for s in ('plant','plant2')}
                for seat,c in self.campaigns.items():
                    c.deck=[k for k in value['seats'][seat].get('deck',[]) if k in c.unlocked][:c.slots()]
                self.income={s:dict(v) for s,v in value.get('income',{}).items() if s in self.campaigns}
                self.applied={tuple(k) for k in value.get('applied',[])}
            except (OSError,ValueError,TypeError,KeyError,AttributeError):
                shutil.copy2(path,path.with_name(path.name+'.invalid-'+str(time.time_ns())))
                self.reset()
        elif initial is not None:
            self.campaigns['plant']=Campaign.from_dict(initial.to_dict())
            self.campaigns['plant'].deck=list(initial.deck)
            self.day=initial.day
        self.ensure(None)
        self.save()

    def save(self):
        if self.path is None:return
        value=dict(format='pvp67-coop-seats-1',run_id=self.run_id,day=self.day,
            seats={s:c.to_dict() for s,c in self.campaigns.items()},income=self.income,
            applied=[list(k) for k in sorted(self.applied,key=repr)][-200:])
        text=json.dumps(value,ensure_ascii=False,indent=1)
        if text==self._saved:return
        self.path.parent.mkdir(parents=True,exist_ok=True)
        pending=self.path.with_name(self.path.name+'.pending')
        pending.write_text(text,'utf8');pending.replace(self.path);self._saved=text

    def sync(self, room):
        if room.mode != COOP or not room.pve:
            return
        self.ensure(room)
        pve = room.pve
        pve['coop_run_id'] = self.run_id
        pve['run_day']=self.day
        pve['guest_campaigns'] = {}
        pve['guest_income'] = {}
        pve['seat_slots'] = {}
        pve['seat_start_sun'] = {}
        pve['seat_unlocked'] = {}
        for seat,campaign in self.campaigns.items():
            pve['seat_slots'][seat]=campaign.slots()
            pve['seat_start_sun'][seat]=campaign.start_sun()
            pve['seat_unlocked'][seat]=campaign.available_unlocked()
            pve['decks'][seat]=list(campaign.deck)
            pve['guest_campaigns'][seat]=campaign.to_dict()
            if seat in self.income:pve['guest_income'][seat]=dict(self.income[seat])
        self.save()

    def drop(self, peer):
        # Membership and preparation are cleared by Room; saved seat growth remains.
        return

    def campaign_for_seat(self, room, seat):
        self.ensure(room)
        return self.campaigns.get(seat) if room.mode==COOP else None

    def ready_error(self, room, peer):
        self.ensure(room)
        campaign = self.campaign_for_seat(room,room.side_for(peer))
        return '请先领取本次合作的奖励卡' if campaign and campaign.rewards else ''

    def action(self, room, peer, payload):
        # PvP73: shopping and reward picks also work before the host sets the day up
        # (a coin skip offers its reward there); room.pve is optional for these.
        if room.mode != COOP:
            return '当前不是合作模式'
        if room.phase not in ('config', 'result'):
            return '请先结束当前挑战'
        self.ensure(room)
        campaign = self.campaign_for_seat(room,room.side_for(peer))
        if campaign is None:
            return '只有合作玩家可以操作'
        kind = payload['type']
        if kind == 'coop_buy':
            index = payload.get('index')
            if type(index) is not int:
                return '商品编号无效'
            error = campaign.buy(index)
        elif kind == 'coop_reward':
            error = campaign.choose_reward(payload.get('card'))
        elif kind == 'coop_reset_deck':
            if room.phase != 'config':
                return '请先返回合作准备界面'
            campaign.deck = [key for key in (*STARTER_PLANTS, 'plant:花盆') if key in campaign.unlocked]
            campaign.fit_deck()
            error = ''
        else:
            return '合作操作无效'
        if error:
            return error
        self.sync(room)
        self.save()
        if room.phase == 'config':
            room.setup_changed(room.side_for(peer))
        room.revision += 1
        room.status = '合作个人进度已更新，请重新确认选卡'
        return ''

    def skip(self, room, peer):
        """PvP73: the host pays SKIP_PRICE from its own seat; every seated player
        counts the day as cleared (reward pick, no coins), the run advances."""
        from .pve import SKIP_PRICE
        # Unlike a purchase, a skip is offered before the host has set the day up
        # (room.pve is only filled by that setup), so only the mode is required.
        if room.mode != COOP:
            return '当前不是合作模式'
        if peer != 'host':
            return '只有房主可以花金币跳关'
        if room.phase != 'config':
            return '请在合作准备界面跳关'
        self.ensure(room)
        payer = self.campaign_for_seat(room, room.side_for(peer))
        if payer is None:
            return '房主需入座后才能跳关'
        seated = [s for s in ('plant', 'plant2') if s in room.members.values()]
        if any(self.campaigns[s].rewards for s in seated):
            return '请先领取本次合作的奖励卡'
        day = self.day
        before = {s: self.campaigns[s].coins for s in seated}
        error = payer.skip_day(pay=True)
        if error:
            return error
        for seat in seated:
            campaign = self.campaigns[seat]
            if campaign is not payer:
                campaign.skip_day(pay=False)
            self.income[seat] = dict(day=day, winner='plant', coins=0, bonus=0,
                                     total=campaign.coins - before[seat], coin_half=campaign.coin_half, skipped=True)
        self.applied.add(('skip', self.run_id, day))
        self.day = max(self.day, day + 1)
        self.sync(room)
        self.save()
        room.setup_changed(room.side_for(peer))
        room.revision += 1
        room.status = '房主花费 $%d 跳过第 %d 天，请各自领取奖励卡' % (SKIP_PRICE, day)
        return ''

    def finish(self, room, result):
        if room.mode != COOP:
            return
        self.ensure(room)
        for seat, campaign in self.campaigns.items():
            if seat not in room.members.values():
                continue
            key = (seat, room.match_id, result.get('tick'), result.get('pve_day'))
            if key in self.applied:
                continue
            self.applied.add(key)
            before = campaign.coins
            coins = int(result.get('coins', 0) or 0)
            bonus = campaign.win(coins, coop=True, fallen=int(result.get('fallen', 0) or 0),
                                 played_day=result['pve_day']) if result.get('winner') == 'plant' else 0
            if result.get('winner') != 'plant':
                campaign.lose(coins)
            total = campaign.coins - before
            self.income[seat] = dict(day=result['pve_day'], winner=result.get('winner'),
                                    coins=total-bonus, bonus=bonus, total=total, coin_half=campaign.coin_half)
        calendar=('calendar',room.match_id,result.get('tick'),result.get('pve_day'))
        if calendar not in self.applied:
            self.applied.add(calendar)
            self.day=max(self.day,result['pve_day']+(result.get('winner')=='plant'))
        self.sync(room)
