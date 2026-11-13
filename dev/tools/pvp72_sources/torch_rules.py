"""Per-stump conversions: thaw and ignition cannot repeat at one torch."""
from .simulation import wrap_delta
from .native_gate import replace_predicate

class TorchRules:
    def __init__(self,b):
        self.b=b
        # Replace only the original one-global-guard torch scan. Collision,
        # damage and flight remain in the original entity region.
        b.g['_pvp_native_torch_scan']=lambda:False
        regions=dict(b.engine.regions)
        regions['entities']=replace_predicate(regions['entities'],101468,101482,'_pvp_native_torch_scan',[
            ('LOAD_CONST','火了'),('LOAD_NAME','实体'),('LOAD_NAME','l'),('BINARY_SUBSCR',None),('COMPARE_OP','not in')])
        b.engine.regions=regions
        b.patch.ns['__pvz_sb_zombie_pea_torch_check']=lambda g,e:self.convert(e,True)
        original=b.patch.ns['__pvz_sb_zombie_pea_fire_splash']
        def splash(g,e,*args,**kwargs):
            e['_pvp_melon_splash']=True
            try:return original(g,e,*args,**kwargs)
            finally:e.pop('_pvp_melon_splash',None)
        b.patch.ns['__pvz_sb_zombie_pea_fire_splash']=splash

    def points(self):
        b=self.b;points=[]
        for p in b.g['植物']:
            if p.get('植物')!='火炬树桩' or p.get('植物血',0)<=0 or '死' in p or '铲死' in p:continue
            row,col=p['坐标'];points.append(((col+.5)*b.tile,(row+.5)*b.tile,p,False))
        points.extend((x,y,p,True) for x,y,p in b._petrified_torches())
        return points

    def convert(self,e,zombie=False,points=None):
        b=self.b
        if not isinstance(e,dict):return
        if zombie:
            if e.get(b._petrified_fire_key):return
            point=b._petrified_pea_xy(e)
        else:
            if e.get('僵尸豌豆弹') or e.get('名') not in ('豌豆','冰豆'):return
            point=e.get('位置')
        if not point:return
        seen=e.setdefault('_pvp_torch_visits',[])
        x,y=point[:2];previous=e.get('_pvp_torch_previous',[e.get('prev_x',x),y])
        dx=wrap_delta(previous[0],x,b.width);dy=y-previous[1]
        candidates=[]
        for tx,ty,t,petrified in (self.points() if points is None else points):
            uid=b.targets.source_id(t)
            if uid in seen:continue
            reach=(2.5*b.zsecrets.torch_range_scale() if petrified else .75 if zombie else .5)*b.tile
            # Swept x/y box in the same periodic image as the projectile.
            rx=wrap_delta(previous[0],tx,b.width);ry=ty-previous[1]
            if min(0.,dx)-reach<=rx<=max(0.,dx)+reach and min(0.,dy)-reach<=ry<=max(0.,dy)+reach:
                along=(rx*dx+ry*dy)/max(1e-9,dx*dx+dy*dy)
                candidates.append((along,uid,t,petrified))
        for unused,uid,t,petrified in sorted(candidates,key=lambda row:(row[0],row[1])):
            # Rewarding an earlier projectile may have put this torch to sleep.
            if petrified and b.engine.native_tick<t.get('_pvp_torch_sleep_until',0):continue
            seen.append(uid)
            blue=('蓝火' in b.g['秘籍']) or (petrified and b.zsecrets.has('暴怒'))
            if zombie:e[b._petrified_fire_key]='blue' if blue else 'fire'
            elif e['名']=='冰豆':e['名']='豌豆';e['火了']=0
            else:
                e.update(名='蓝火豆' if blue else '火豆',火了=0,_pvp_fire_color='blue' if blue else 'fire')
            if petrified:b._petrified_torch_reward((x,y),t)
            if zombie or e['名'] in ('火豆','蓝火豆'):break
        e['_pvp_torch_previous']=[x,y]

    def tick(self):
        points=self.points()
        if not points:return
        for e in self.b.g['实体']:self.convert(e,points=points)
