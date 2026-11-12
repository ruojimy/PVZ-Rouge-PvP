# live PvP71 region water_animation
if 冻水 == 0:
    水波 += 1
    if 水波 >= 500:
        水波 = 0
dushu = math.pi * (水波 / 500)
shui = math.sin(dushu) * 比 * 0.1
