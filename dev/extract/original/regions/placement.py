# original pvzrouge.pyc bytes 109352..110754
if 拿中 == '':
    return  # region end
y = sby
x = sbx
if 出界(y, x):
    return  # region end
种植 = '不适宜种植'
if 拿中 == '铲子':
    if '植物' in ditu[y][x]:
        种植 = '适宜铲除'
    return  # region end
if 拿中 == '咖啡豆':
    z = 哪个无南瓜植物(y, x)
    if '植物' in ditu[y][x] and z != -1 and '睡觉' in 植物[z]:
        种植 = '适宜种植'
    return  # region end
if 拿中 == '墓碑吞噬者':
    if ditu[y][x]['方块'] == '坟墓' and '植物' not in ditu[y][x]:
        种植 = '适宜种植'
    return  # region end
if 拿中 in ('睡莲', '海蘑菇', '缠绕海草', '香蒲'):
    if ditu[y][x]['方块'] == '水' and ditu[y - 1][x]['方块'] != '水' and ditu[y - 1][x]['方块'] in kong and '植物' not in ditu[y][x]:
        种植 = '适宜种植'
    return  # region end
if 模式 == '我是僵尸':
    if ditu[y][x]['方块'] == '坟墓':
        种植 = '适宜种植'
    return  # region end
可 = False
if not 出界(y + 1, x):
    if 拿中 == '花盆':
        if ditu[y + 1][x]['方块'] not in kong:
            可 = True
    else:
        if 拿中 == '南瓜头' and ditu[y + 1][x]['方块'] == '水' and '植物' in ditu[y + 1][x] and 植物[哪个植物(y + 1, x)]['植物'] == '香蒲':
            可 = True
        if ditu[y + 1][x]['方块'] in ('草', '土'):
            可 = True
        else:
            if 拿中 != '地刺' and 拿中 != '地刺王' and ditu[y + 1][x]['方块'] in ('花盆块',):
                可 = True
            else:
                if ('无土栽培' in 秘籍 or 拿中 == '高坚果' and '石果' in 秘籍) and ditu[y + 1][x]['方块'] not in kong:
                    可 = True
                else:
                    if 拿中 != '地刺' and 拿中 != '地刺王' and 拿中 != '土豆地雷' and ditu[y + 1][x]['方块'] == '水':
                        z = 哪个植物(y + 1, x)
                        if z != -1 and 植物[z]['植物'] == '睡莲':
                            可 = True
        if ditu[y + 1][x]['方块'] == '铁路':
            可 = False
二可 = True
if '植物' in ditu[y][x]:
    z = 哪个植物(y, x)
    if 植物[z]['植物'] == '南瓜头' and 拿中 != '南瓜头':
        for zz in range(len(植物)):
            if 植物[zz]['坐标'][0] == y and 植物[zz]['坐标'][1] == x and zz != z:
                二可 = False
                break
    else:
        if 拿中 == '南瓜头' and 植物[z]['植物'] == '南瓜头':
            二可 = False
        else:
            if 拿中 != '南瓜头':
                二可 = False
if not (可 and 二可 and ditu[y][x]['方块'] == '空'):
    return  # region end
种植 = '适宜种植'
