# live PvP71 region physics_double_jump_clock
if 二段跳 > 0:
    sj = 100 - 二段跳
    二段跳 += 1
    if 二段跳 == 100:
        二段跳 = 0
    a = 0.072
    dushu -= a * sj * sj / 2
