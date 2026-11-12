z = -1
for zz in range(len(僵尸) - 1, -1, -1):
    if '魅惑' in 僵尸[zz] or '灰烬' in 僵尸[zz]:
        continue
    lzx = 0
    if 僵尸[zz]['血量'] < 0:
        dushu = -jdz(僵尸[zz]['血量']) * 僵尸[zz]['方向']
        if dushu > 90:
            dushu = 90
        if dushu < -90:
            dushu = -90
        lzx = jdz(dushu) * 比 * 0.008
    dx = c(僵尸[zz]['大小'])
    if 实体[l]['位置'][0] > 僵尸[zz]['位置'][0] - 比 * 0.15 * dx and 实体[l]['位置'][0] < 僵尸[zz]['位置'][0] + 比 * 0.15 * dx and 实体[l]['位置'][1] > 僵尸[zz]['位置'][1] - 比 * 0.85 * dx + lzx and 实体[l]['位置'][1] < 僵尸[zz]['位置'][1]:
        z = zz
        break
if z != -1:
    shanchu = True
    biaomian = True
    if name in 投掷物 and 实体[l]['位置'][1] < 僵尸[z]['位置'][1] - 比:
        biaomian = False
    if name == '泡泡' or name == '海泡泡':
        sh = 5
    else:
        if name == '玉米粒':
            sh = 5
        else:
            if name == '卷心菜':
                sh = 30
            else:
                if name == '黄油':
                    sh = 10
                else:
                    if name == '火豆':
                        if '蓝火' in 秘籍:
                            sh = 30
                        else:
                            sh = 20
                        if 僵尸[z]['手持'] in ('报纸', '气球'):
                            biaomian = True
                        else:
                            biaomian = False
                    else:
                        if name == '西瓜' or name == '冰瓜':
                            sh = 150
                            僵尸[z]['位置'][2] += 实体[l]['方向'] * plk * 200
                        else:
                            sh = 10
    if 实体[l]['方向'] == 僵尸[z]['方向'] and '追踪' not in 实体[l]:
        biaomian = False
    if biaomian:
        biaomian = 表面伤害僵尸(z, c(实体[l]['方向']), sh)
        if not biaomian and sh > 5 and '追踪' not in 实体[l]:
            击退僵尸(z, 实体[l]['方向'] * plk * 200)
            if name == '冰豆':
                if '冰冻' not in 僵尸[z] or 僵尸[z]['冰冻'] == 0:
                    沉浸播音('冰冻', [僵尸[z]['位置'][0], 僵尸[z]['位置'][1]])
                僵尸[z]['冰冻'] = 1150
    else:
        if sh > 5:
            击退僵尸(z, 实体[l]['方向'] * plk * 200)
        伤害僵尸(z, c(实体[l]['方向']), sh)
        if name == '冰豆':
            if '冰冻' not in 僵尸[z] or 僵尸[z]['冰冻'] == 0:
                沉浸播音('冰冻', [僵尸[z]['位置'][0], 僵尸[z]['位置'][1]])
            僵尸[z]['冰冻'] = 1200
    if name == '黄油':
        沉浸播音('黄油', [僵尸[z]['位置'][0], 僵尸[z]['位置'][1]])
        僵尸[z]['黄油'] = 3000
    if name == '火豆':
        if '冰冻' in 僵尸[z]:
            del 僵尸[z]['冰冻']
        沉浸播音('火豆' + str(随(1, 2)), [实体[l]['位置'][0], 实体[l]['位置'][1]])
    else:
        if name == '西瓜' or name == '冰瓜':
            pass
        else:
            if not biaomian:
                沉浸播音('splat' + str(随(1, 3)), [僵尸[z]['位置'][0], 僵尸[z]['位置'][1]])
if name != '篮球x':
    return  # region end
name = '篮球'
xx += 比 * 0.5
