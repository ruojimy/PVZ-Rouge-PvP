# live PvP71 region umbrella_player_bounce
if jdz(玩家位置[0] - xx) + jdz(玩家位置[1] - yy) <= 比 * 2:
    if 玩家位置[0] > xx:
        玩家位置[2] = 300 * plk
    else:
        玩家位置[2] = -300 * plk
    玩家位置[3] = -600 * plk
