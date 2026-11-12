# live PvP71 region physics_tracking_plants
if 植洪水cd > 0:
    植洪水cd -= 1
if 植洪水cd == 0:
    if 目标植物 == -1:
        植洪水cd = 20
    else:
        植洪水cd = 3
    if 植洪水圈 == []:
        wy = c(目标位置[0])
        wx = c(目标位置[1])
        if not 出界(wy, wx):
            植洪水圈.append([wy, wx])
            植洪水覆盖 = -植洪水覆盖
    植洪水圈x = c(植洪水圈)
    植洪水圈 = []
    for l in 植洪水圈x:
        yy = c(l[0])
        xx = c(l[1])
        for lzx in (1, 2, 3, 4):
            y = yy
            x = xx
            if lzx == 1:
                y -= 1
            if lzx == 2:
                y += 1
            if lzx == 3:
                x -= 1
            if lzx == 4:
                x += 1
            if not 出界(y, x) and ditu[y][x]['方块'] in kong and y <= 水平面 and (植洪水[y][x] == 0 or 植洪水覆盖 * 植洪水[y][x] < 0):
                if y > 0 and y < 23 and ditu[y - 1][x]['方块'] not in kong and ditu[y + 1][x]['方块'] not in kong:
                    pass
                else:
                    植洪水圈.append([y, x])
                    植洪水[y][x] = lzx * 植洪水覆盖
