# live PvP71 region dave_state
if 玩家血量 <= 0:
    玩家受伤 = 1
if 玩家血量 < 20:
    lzx = 玩家血量 * 13
    llzx = 0
    lllzx = 1
    if 玩家恢复 > 2000:
        lllzx = (玩家倒地 / 90) ** 0.5
    if 玩家受伤 > 0:
        玩家受伤 += 1
        llzx = int((1 - 玩家受伤 / 50) ** 0.5 * lzx)
    图集[玩家皮肤 + '-受伤'].set_alpha(int((llzx + 255 - lzx) * lllzx))
    if 玩家受伤 == 50:
        玩家受伤 = 0
