# live PvP71 region cannon_select
开炮 = True
if not 出界(sby, sbx) and '植物' in ditu[sby][sbx] and 拿中玉米炮 == []:
    z = 哪个无南瓜植物(sby, sbx)
    if 植物[z]['植物'] == '玉米加农炮' and 植物[z]['发射cd'] == 0 and 植物[z]['发射动画'] == 0:
        拿中玉米炮 = [sby, sbx]
        开炮 = False
