from pathlib import Path
root=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
p=root/'tools/typed72/drafts/verify_native_tick.py';t=p.read_bytes().decode('utf8')
a="env['draw_dave']=lambda game,root,avatar,materialize:self.record('hero_'+avatar['_pvp_seat']+('_pixels' if materialize else '_hidden'))"
assert t.count(a)==1
b="""env['draw_dave']=lambda game,root,avatar,materialize:(self.record('hero_'+avatar['_pvp_seat']+('_pixels' if materialize else '_hidden')),dave_state_region(avatar))"""
t=t.replace(a,b)
nl='\r\n' if '\r\n' in t else '\n'
a='class NativeTickExtension(';assert t.count(a)==1
helper='''# Observed bound of the real _draw_dave: the recovered dave_state region runs on the
# avatar's fields, HP on the source's 20-point scale. Alpha is presentation and is discarded.
DAVE_STATE=compile((Path(__file__).resolve().parents[3]/'extract/live/dave_state.py').read_text(encoding='utf8'),'dave_state','exec')
class _DaveImage:
    def set_alpha(self,value):pass
def dave_state_region(avatar):
    maximum=avatar.get('_pvp_max_hp',20.);skin=avatar.get('玩家皮肤','')
    env=dict(玩家血量=avatar['玩家血量']*20./maximum if maximum!=20. else avatar['玩家血量'],玩家受伤=avatar.get('玩家受伤',0),
             玩家恢复=avatar.get('玩家恢复',0),玩家倒地=avatar.get('玩家倒地',0),玩家皮肤=skin,图集={skin+'-受伤':_DaveImage()},int=int)
    exec(DAVE_STATE,env);avatar['玩家受伤']=env['玩家受伤']
'''.replace('\n',nl)
t=t.replace(a,helper+a)
p.write_bytes(t.encode('utf8'))
