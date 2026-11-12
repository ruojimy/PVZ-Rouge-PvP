# live PvP71 region physics_tracking_targets
输出植物数 = 0
if 模式 == '我是僵尸':
    目标植物 = -1
else:
    目标植物 = -1
    for l in range(len(植物)):
        if 植物[l]['植物'] in 输出植物 and '睡觉' not in 植物[l]:
            x = c(植物[l]['坐标'][1])
            y = c(植物[l]['坐标'][0])
            if not 出界(y - 1, x) and ditu[y - 1][x]['方块'] not in kong:
                pass
            else:
                if 植物[l]['植物'] not in 产光植物:
                    输出植物数 += 1
                if 目标植物 == -1:
                    目标植物 = l
    if 目标植物 != -1:
        if 先别追植 > 0:
            先别追植 -= 1
        目标位置 = [c(植物[目标植物]['坐标'][0]), c(植物[目标植物]['坐标'][1])]
    else:
        先别追植 = 500
        if not 出界(wjy, wjx):
            目标位置 = [wjy, wjx]
paoku = (6 - 输出植物数) // 2
if paoku < 1:
    paoku = 1
