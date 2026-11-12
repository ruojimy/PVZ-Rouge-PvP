if 植物[l]['吃'] > 0:
    植物[l]['吃'] -= 1
if 植物[l]['射'] == 0:
    if 植物[l]['吃'] > 0:
        pass
    else:
        射 = False
        if y - 1 in 同横尸:
            if x + 植物[l]['方向'] in 同横尸[y - 1]:
                射 = True
            if x in 同横尸[y - 1]:
                射 = True
        if 射:
            植物[l]['射'] = 1
            植物[l]['射cd'] = 500
            if name == '龙蒺藜':
                植物[l]['射cd'] = 300
    return  # region end
if 植物[l]['射'] < 150:
    植物[l]['射'] += 1
    if 植物[l]['射'] == 75:
        xx = x * 比 + 比 / 2
        yy = y * 比 + 比 / 2
        沉浸播音('大嘴', [植物[l]['坐标'][1] * 比 + 比 * 0.5, 植物[l]['坐标'][0] * 比 + 比 * 0.5])
        zz = -1
        if 植物[l]['方向'] == 1:
            for z in range(len(僵尸)):
                if 僵尸[z]['位置'][0] >= xx and '魅惑' not in 僵尸[z] and (僵尸[z]['血量'] > 0 or 僵尸[z]['手持'] == '玩偶匣') and jdz(僵尸[z]['位置'][0] - xx) <= 比 * 2 and jdz(僵尸[z]['位置'][1] - 比 - yy) <= 比:
                    zz = z
                    break
        else:
            for z in range(len(僵尸)):
                if 僵尸[z]['位置'][0] <= xx and '魅惑' not in 僵尸[z] and (僵尸[z]['血量'] > 0 or 僵尸[z]['手持'] == '玩偶匣') and jdz(僵尸[z]['位置'][0] - xx) <= 比 * 2 and jdz(僵尸[z]['位置'][1] - 比 - yy) <= 比:
                    zz = z
                    break
        if zz != -1:
            if 僵尸[z]['大小'] == 2 and 僵尸[z]['僵尸'] not in boss:
                僵尸[z]['血量'] = -1024
                植物[l]['吃'] = 7000
                if name == '龙蒺藜':
                    植物[l]['吃'] = 1400
            else:
                伤害僵尸(z, c(植物[l]['方向']), 50)
植物[l]['射cd'] -= 1
if 植物[l]['射cd'] > 0:
    return  # region end
植物[l]['射cd'] = 0
植物[l]['射'] = 0
