# live PvP71 region physics_jump_keydown
if event.type == pygame.KEYDOWN and event.key == 跳跃 and 玩家倒地 == 0 and 玩家跳跃 < 2 and 二段跳 == 0:
    玩家跳跃 += 1
    if 玩家跳跃 == 2:
        二段跳 = 1
        玩家位置[2] += 玩家方向 * plk * 200
        if 模式 == '我是僵尸':
            玩家跳跃 = 2
    玩家位置[3] = -plk * 380
