# live PvP71 region physics_hurt_recovery
if 玩家倒地 > 0:
    玩家恢复 += 1
    if 玩家恢复 > 2000 and 玩家血量 > 0:
        玩家倒地 -= 1
        if 玩家倒地 == 0 and 气球 > 0:
            气球 = -1
            增粒子('气球', [玩家位置[0], 玩家位置[1] - 比 * 2.5], 12)
            播音('气球爆炸')
    else:
        if 玩家倒地 < 90:
            玩家倒地 += 1
        if 气球 == 0 and 玩家血量 <= 10:
            气球 = 1
            播音('气球')
    dushu += 玩家倒地
    if dushu > 90:
        dushu = 90
    yy = jdz(dushu) * 比 * 0.008
xx = 0
if 冻水 > 0:
    xx += 抖(2)
    yy += 抖(2)
