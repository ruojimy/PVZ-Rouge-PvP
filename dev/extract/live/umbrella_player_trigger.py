# live PvP71 region umbrella_player_trigger
if jdz(玩家位置[0] - xx) + jdz(玩家位置[1] - yy) <= 比 * 2 and 玩家位置[3] > 200 * plk:
    射 = True
if 射:
    植物[l]['射'] = 1
    if 植物[l]['射cd'] == -1:
        植物[l]['射cd'] = 0
else:
    植物[l]['射cd'] = -1
