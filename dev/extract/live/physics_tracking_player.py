# live PvP71 region physics_tracking_player
if 人洪水cd > 0:
    人洪水cd -= 1
if 人洪水cd == 0:
    人洪水cd = 3
    if 人洪水圈 == []:
        wx = int(玩家位置[0] // 比)
        wy = int((玩家位置[1] - 0.5 * 比) // 比)
        if not 出界(wy, wx):
            人洪水圈.append([wy, wx])
            人洪水覆盖 = -人洪水覆盖
    人洪水圈x = c(人洪水圈)
    人洪水圈 = []
    for l in 人洪水圈x:
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
            if not 出界(y, x) and ditu[y][x]['方块'] in kong and y <= 水平面 and (人洪水[y][x] == 0 or 人洪水覆盖 * 人洪水[y][x] < 0):
                if y > 0 and y < 23 and ditu[y - 1][x]['方块'] not in kong and ditu[y + 1][x]['方块'] not in kong:
                    pass
                else:
                    人洪水圈.append([y, x])
                    人洪水[y][x] = lzx * 人洪水覆盖
