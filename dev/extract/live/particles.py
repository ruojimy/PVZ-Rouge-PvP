# live PvP71 region particles
daxiaox = 比 * 0.15
for l in range(len(粒子) - 1, -1, -1):
    粒子[l][2] += 1
    if 粒子[l][2] == 300:
        del 粒子[l]
        continue
    daxiao = daxiaox
    可 = True
    if 粒子[l][1][3] > 0:
        y = int(粒子[l][1][1] // 比)
        x = int(粒子[l][1][0] // 比)
        if not 出界(y, x):
            if ditu[y][x]['方块'] not in kong:
                可 = False
            if ditu[y][x]['方块'] == '水':
                粒子[l][1][3] = 粒子[l][1][3] / 2
    if 可:
        无墙位移处理(粒子[l][1])
    if 补帧 == 0:
        if 粒子[l][2] >= 250:
            daxiao = daxiao * (300 - 粒子[l][2]) / 50
        pygame.draw.rect(screen, 粒子[l][0], [粒子[l][1][0] - daxiao / 2 - 摄像机[0] + 抖屏[1], 粒子[l][1][1] - daxiao / 2 - 摄像机[1] + 抖屏[2], daxiao, daxiao], 0)
