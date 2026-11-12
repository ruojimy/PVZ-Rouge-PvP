# live PvP71 region physics_hero_effects
if 猫尾 > 0 and 猫尾 < 100:
    猫尾 += 1
    if 猫尾 == 50:
        新增实体('尖刺', 1, [玩家位置[0] - 玩家方向 * 比 * 0.5, 玩家位置[1] - 比 * 1.2 + yy, 玩家方向 * 200 * plk, 0])
        实体[-1]['追踪'] = 0
        实体[-1]['穿墙'] = 0
        实体[-1]['消亡'] = -1000
        实体[-1]['旋转'] = 0
if 气球 > 0:
    if 玩家位置[3] > -60 * plk and 玩家位置[1] > 比:
        玩家位置[3] -= 5 * plk
    气球 += 1
    if 气球 < 100:
        fangda = 气球 / 100 * 比 * 2
        摄像显示(变图(图集['气球'], fangda, fangda), [玩家位置[0] - fangda / 2, 玩家位置[1] - 比 - fangda + yy])
    else:
        摄像显示(图集['气球'], [玩家位置[0] - 比, 玩家位置[1] - 比 * 3 + yy])
if 猫尾cd > 0:
    猫尾摇摆 += 1
    if 猫尾摇摆 == 250:
        猫尾摇摆 = 0
    猫尾cd += 1
    if 猫尾cd <= 450 and 猫尾cd % 150 == 0 and 离玩家最近 != -1:
        猫尾 = 1
    if 猫尾cd == 1000:
        猫尾cd = 1
    if 玩家方向 == 1:
        gen = 图集['香蒲尾']
    else:
        gen = 反(图集['香蒲尾'])
    dushux = math.pi * 2 * (猫尾摇摆 / 250)
    sinzhi = math.sin(dushux) * 10
    tousin = 0
    if 猫尾 > 0 and 猫尾 < 100:
        shedu = math.pi * 2 * (猫尾 / 100)
        shesin = math.sin(shedu)
        citoux = -shesin * 比 * 0.15 * 玩家方向
        toudushu = -shesin * 20 * 玩家方向
        toudu = math.pi * 2 * (猫尾 / 100)
        tousin = -math.sin(toudu) * 60 * 玩家方向
    旋转摄像显示(gen, (玩家位置[0] - 比 * 0.5 - 玩家方向 * 比 * 0.25, 玩家位置[1] - 比 * 1.5 + jdz(sinzhi) * 比 * 0.005 + yy), tousin + sinzhi)
