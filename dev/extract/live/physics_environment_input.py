# live PvP71 region physics_environment_input
speed = speedmax
if 冻水 > 0:
    speed = speed / 2
wjx = int(玩家位置[0] // 比)
wjy = int(玩家位置[1] // 比)
x = wjx
y = wjy
if not 出界(y - 1, x) and ditu[y - 1][x]['方块'] == '雪':
    摧毁方块(y - 1, x)
if 模式 == '我是僵尸':
    if x not in 同竖尸:
        同竖尸[x] = [y, y - 1]
    else:
        同竖尸[x].append(y - 1)
        同竖尸[x].append(y)
    if y not in 同横尸:
        同横尸[y] = [x]
    else:
        同横尸[y].append(x)
    if y - 1 not in 同横尸:
        同横尸[y - 1] = [x]
    else:
        同横尸[y - 1].append(x)
按 = pygame.key.get_pressed()
入水 = False
sbs = False
if not 出界(y, x):
    if ditu[y][x]['方块'] == '水':
        入水 = True
    if ditu[y][x]['方块'] == '梯子块' and 玩家倒地 == 0:
        玩家跳跃 = 0
        if 按[跳跃]:
            玩家位置[3] = -plk * 150
            玩家位置[2] = 玩家位置[2] * 9 / 10
if not 出界(y - 1, x) and ditu[y - 1][x]['方块'] == '水':
    入水 = True
    sbs = True
if 入水:
    speed = speed / 2
    if not 玩家入水:
        玩家跳跃 = 2
        玩家入水 = True
        播音('入水')
        增粒子(水, [玩家位置[0], 玩家位置[1]], 16)
    if 玩家位置[3] > 0:
        玩家位置[3] -= plk * 3.9
    if 玩家位置[3] > 50 * plk:
        玩家位置[3] = 50 * plk
    if sbs and 玩家血量 > 0:
        玩家位置[3] = -plk * 200
        玩家跳跃 = 0
else:
    玩家入水 = False
if 玩家倒地 == 0 or 气球 > 0:
    if 按[左走]:
        if 玩家位置[2] < 0:
            玩家方向 = -1
        if 玩家位置[2] > -speed:
            玩家位置[2] -= plk * 7
    if 按[右走]:
        if 玩家位置[2] > 0:
            玩家方向 = 1
        if 玩家位置[2] < speed:
            玩家位置[2] += plk * 7
