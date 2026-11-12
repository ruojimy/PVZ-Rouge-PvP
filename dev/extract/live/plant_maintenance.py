# live PvP71 region plant_maintenance
for l in range(len(植物) - 1, -1, -1):
    if '死' in 植物[l]:
        y = c(植物[l]['坐标'][0])
        x = c(植物[l]['坐标'][1])
        增粒子(植物[l]['植物'], [x * 比 + 比 * 0.5, y * 比 + 比 * 0.5], 9)
        if 模式 == '我是僵尸' and '睡觉' in 植物[l]:
            del 植物[l]['睡觉']
        name = c(植物[l]['植物'])
        if '睡觉' not in 植物[l] and '铲死' not in 植物[l]:
            if name == '毁灭菇':
                核爆 = 80
                yy = 植物[l]['坐标'][0] * 比 + 比 * 0.5
                xx = 植物[l]['坐标'][1] * 比 + 比 * 0.5
                if jdz(玩家位置[0] - xx) <= 比 * 5 and jdz(玩家位置[1] - yy) <= 比 * 5:
                    if xx > 玩家位置[0]:
                        玩家位置[2] -= 900 * plk
                    else:
                        玩家位置[2] += 900 * plk
                    玩家位置[3] -= 800 * plk
                for z in range(len(僵尸)):
                    if jdz(僵尸[z]['位置'][0] - xx) <= 比 * 5 and jdz(僵尸[z]['位置'][1] - yy) <= 比 * 5:
                        灰烬僵尸(z)
                        if _pvp66_doom():
                            灰烬僵尸(z)
                for lzx in range(10):
                    if 随(0, 1) == 0:
                        fx = -1
                    else:
                        fx = 1
                    if lzx // 2 % 2 == 0:
                        ytm = 1
                    else:
                        ytm = -1
                    新增实体('毁灭3', fx, [植物[l]['坐标'][1] * 比 - 比 * 1.5 + lzx * 比 / 2, 植物[l]['坐标'][0] * 比 - 比 * 0.5 - 比 * 4 + ytm * 比 / 2, 0, -plk * 30])
                    实体[-1]['消亡'] = 700
                    实体[-1]['旋转'] = 随(0, 360)
                新增实体('毁灭2', c(植物[l]['方向']), [植物[l]['坐标'][1] * 比 - 比 * 1.5, 植物[l]['坐标'][0] * 比 - 比 * 0.5 - 比 * 3.5, 0, 0])
                实体[-1]['消亡'] = 700
                新增实体('毁灭1', c(植物[l]['方向']), [植物[l]['坐标'][1] * 比 - 比 * 1.5, 植物[l]['坐标'][0] * 比 - 比 * 0.5 - 比 * 3.5, 0, 0])
                实体[-1]['消亡'] = 700
                抖屏 = [200, 0, 0]
                沉浸播音('毁灭菇', [植物[l]['坐标'][1] * 比 + 比 * 0.5, 植物[l]['坐标'][0] * 比 + 比 * 0.5])
                zuoshang = [植物[l]['坐标'][0] - 2, 植物[l]['坐标'][1] - 2]
                for yy in range(5):
                    y = yy + zuoshang[0]
                    for xx in range(5):
                        x = xx + zuoshang[1]
                        if jdz(yy - 2) + jdz(xx - 2) <= 3:
                            摧毁方块(y, x)
            if name == '樱桃炸弹':
                yy = 植物[l]['坐标'][0] * 比 + 比 * 0.5
                xx = 植物[l]['坐标'][1] * 比 + 比 * 0.5
                if jdz(玩家位置[0] - xx) <= 比 * 2.5 and jdz(玩家位置[1] - yy) <= 比 * 2.5:
                    if xx > 玩家位置[0]:
                        玩家位置[2] -= 500 * plk
                    else:
                        玩家位置[2] += 500 * plk
                    玩家位置[3] -= 500 * plk
                zuoshang = [植物[l]['坐标'][0] - 2, 植物[l]['坐标'][1] - 2]
                for yyy in range(5):
                    y = yyy + zuoshang[0]
                    for xxx in range(5):
                        x = xxx + zuoshang[1]
                        if not (jdz(yyy - 2) + jdz(xxx - 2) > 3 or 出界(y, x)) and ditu[y][x]['方块'] == '梯子块':
                            摧毁方块(y, x)
                for z in range(len(僵尸)):
                    if jdz(僵尸[z]['位置'][0] - xx) <= 比 * 2.5 and jdz(僵尸[z]['位置'][1] - yy) <= 比 * 2.5:
                        灰烬僵尸(z)
                for lzx in range(随(4, 5)):
                    if lzx % 2 == 0:
                        fx = -1
                    else:
                        fx = 1
                    if lzx // 2 % 2 == 0:
                        ytm = 1
                    else:
                        ytm = -1
                    新增实体('爆炸', fx, [植物[l]['坐标'][1] * 比, 植物[l]['坐标'][0] * 比 - 比, fx * plk * 随(300, 400), plk * 随(200, 300) * ytm])
                    实体[-1]['消亡'] = 900
                    实体[-1]['旋转'] = 随(0, 360)
                if 随(0, 1) == 0:
                    fx = -1
                else:
                    fx = 1
                新增实体('爆炸', fx, [植物[l]['坐标'][1] * 比, 植物[l]['坐标'][0] * 比 - 比, 0, 0])
                实体[-1]['消亡'] = 900
                实体[-1]['旋转'] = 随(0, 360)
                抖屏 = [100, 0, 0]
                沉浸播音('樱桃炸弹', [植物[l]['坐标'][1] * 比 + 比 * 0.5, 植物[l]['坐标'][0] * 比 + 比 * 0.5])
            if name == '火爆辣椒':
                y = c(植物[l]['坐标'][0])
                x = c(植物[l]['坐标'][1])
                yy = y * 比 + 比 * 0.5
                for lzx in range(8):
                    zuox = x - lzx
                    if not 出界(y + 1, zuox) and ditu[y + 1][zuox]['方块'] in ('梯子块', '雪'):
                        摧毁方块(y + 1, zuox)
                    if not 出界(y - 1, zuox) and ditu[y - 1][zuox]['方块'] in ('梯子块', '雪'):
                        摧毁方块(y - 1, zuox)
                    if 出界(y, zuox) or ditu[y][zuox]['方块'] != '空':
                        if not 出界(y, zuox) and ditu[y][zuox]['方块'] in ('梯子块', '雪'):
                            摧毁方块(y, zuox)
                            新增实体('火', -1, [zuox * 比 + 比, y * 比, 0, 0])
                            实体[-1]['消亡'] = 900 - lzx * 5
                            continue
                        zuox += 1
                        break
                    else:
                        新增实体('火', -1, [zuox * 比 + 比, y * 比, 0, 0])
                        实体[-1]['消亡'] = 900 - lzx * 5
                for lzx in range(8):
                    youx = x + lzx
                    if not 出界(y + 1, youx) and ditu[y + 1][youx]['方块'] in ('梯子块', '雪'):
                        摧毁方块(y + 1, youx)
                    if not 出界(y - 1, youx) and ditu[y - 1][youx]['方块'] in ('梯子块', '雪'):
                        摧毁方块(y - 1, youx)
                    if 出界(y, youx) or ditu[y][youx]['方块'] != '空':
                        if not 出界(y, youx) and ditu[y][youx]['方块'] in ('梯子块', '雪'):
                            摧毁方块(y, youx)
                            新增实体('火', -1, [zuox * 比 + 比, y * 比, 0, 0])
                            实体[-1]['消亡'] = 900 - lzx * 5
                            continue
                        youx -= 1
                        break
                    else:
                        新增实体('火', -1, [youx * 比 + 比, y * 比, 0, 0])
                        实体[-1]['消亡'] = 900 - lzx * 5
                for z in range(len(僵尸)):
                    jr = 僵尸[z]['大小'] - 1
                    if jr == 0:
                        jr = 1
                    jr = 比 * (僵尸[z]['大小'] - 1)
                    if 僵尸[z]['位置'][0] > zuox * 比 - 比 * 0.5 and 僵尸[z]['位置'][0] < youx * 比 + 比 * 1.5 and jdz(僵尸[z]['位置'][1] - yy) <= jr:
                        灰烬僵尸(z)
                        if '冰冻' in 僵尸[z]:
                            del 僵尸[z]['冰冻']
                抖屏 = [50, 0, 0]
                沉浸播音('辣椒', [植物[l]['坐标'][1] * 比 + 比 * 0.5, 植物[l]['坐标'][0] * 比 + 比 * 0.5])
            if name == '缠绕海草':
                z = l
                新增实体('缠绕海草x', c(植物[z]['方向']), [植物[z]['坐标'][1] * 比 + 比 / 2, 植物[z]['坐标'][0] * 比, 0, 0])
                实体[-1]['消亡'] = 0
                if '黑白' in 植物[z]:
                    实体[-1]['黑白'] = 0
                实体[-1]['牛顿'] = 0
                沉浸播音('取走', [植物[z]['坐标'][1] * 比 + 比 * 0.5, 植物[z]['坐标'][0] * 比 + 比 * 0.5])
            if name == '土豆地雷' and 植物[l]['埋藏'] == 0:
                z = l
                yy = 植物[z]['坐标'][0] * 比 + 比 * 0.5
                xx = 植物[z]['坐标'][1] * 比 + 比 * 0.5
                if jdz(玩家位置[0] - xx) <= 比 and jdz(玩家位置[1] - yy) <= 比:
                    if xx > 玩家位置[0]:
                        玩家位置[2] -= 300 * plk
                    else:
                        玩家位置[2] += 300 * plk
                    玩家位置[3] -= 300 * plk
                for zz in range(len(僵尸)):
                    if _pvp64_mine_x() and _pvp64_mine_y():
                        灰烬僵尸(zz)
                if 随(0, 1) == 0:
                    fx = -1
                else:
                    fx = 1
                新增实体('炸雷', fx, [植物[z]['坐标'][1] * 比, 植物[z]['坐标'][0] * 比 - 比, 0, 0])
                实体[-1]['消亡'] = 800
                抖屏 = [50, 0, 0]
                沉浸播音('土豆地雷', [植物[z]['坐标'][1] * 比 + 比 * 0.5, 植物[z]['坐标'][0] * 比 + 比 * 0.5])
        if _pvp_supplement_death():
            阳光球.append([0, [植物[l]['坐标'][1] * 比 + 比 * 0.5, 植物[l]['坐标'][0] * 比 + 比 * 0.5, 随(-200, 200) * plk * 1.5, -随(200, 250) * plk], -200, 0])
        y = c(植物[l]['坐标'][0])
        x = c(植物[l]['坐标'][1])
        if name == '花盆':
            ditu[y][x]['方块'] = '空'
        if name == '睡莲':
            清除植物(y - 1, x)
            if '睡莲' in ditu[y][x]:
                del ditu[y][x]['睡莲']
        del 植物[l]
        if '植物' in ditu[y][x] and 哪个植物(y, x) == -1:
            del ditu[y][x]['植物']
        if not (模式 != '我是僵尸' or 胜利) and name in ('脑子', '黄金脑子'):
            if name == '黄金脑子':
                bb = '金币'
            else:
                bb = '银币'
            钱币.append([0, [x * 比 + 比 * 0.5, y * 比 + 比 * 0.5, 0, -随(350, 450) * plk], -300, bb])
            吃脑子数 += 1
            if 吃脑子数 == 3:
                if boss战:
                    胜利 = True
                    音乐淡出()
                    播音('大胜利')
                    for lzx in range(len(僵尸)):
                        伤害僵尸(lzx, c(僵尸[lzx]['方向']), 10000)
                    新卡 = ['金杯', [0, 0], [x * 比 - 摄像机[0], y * 比 - 比 * 0.5 - 摄像机[1]], 0, 0]
                else:
                    胜利 = True
                    音乐淡出()
                    if len(未拥有植物) > 0:
                        僵尸新卡()
                    else:
                        播音('小胜利')
                        关 = 1
            else:
                if boss战:
                    可种 = []
                    for y in range(len(ditu)):
                        for x in range(len(ditu[0])):
                            if not (not (ditu[y][x]['方块'] == '空' and y != 0 and ditu[y - 1][x]['方块'] == '空' and '植物' not in ditu[y][x]) or 出界(y + 1, x)) and (ditu[y + 1][x]['方块'] not in kong or ditu[y + 1][x]['方块'] == '水') and ditu[y + 1][x]['方块'] != '铁路':
                                if ditu[y + 1][x]['方块'] == '水':
                                    可种.append([y + 1, x, '水'])
                                else:
                                    if ditu[y + 1][x]['方块'] in ('草', '土'):
                                        可种.append([y, x, '草'])
                                    else:
                                        可种.append([y, x, '石'])
                    向日葵数 = 2
                    南瓜头数 = 0
                    香蒲数 = 1
                    磁力数 = 2
                    先来脑子 = True
                    脑子召唤cd = 0
                    脑子召唤 = 24
                    if 脑子召唤 > len(可种):
                        脑子召唤 = len(可种)
