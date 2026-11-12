if '追踪' not in 实体[l]:
    return  # region end
实体[l]['追踪'] += 1
z = 离玩家最近
if z == -1:
    return  # region end
if 僵尸[z]['位置'][0] - 实体[l]['位置'][0] == 0:
    return  # region end
y = c(僵尸[z]['位置'][1] - 比 - 实体[l]['位置'][1])
x = c(僵尸[z]['位置'][0] - 实体[l]['位置'][0])
实体[l]['旋转'] = math.degrees(math.atan2(y, x))
jd = math.pi * 2 * (-实体[l]['旋转'] / 360)
zz = 实体[l]['追踪'] // 2
实体[l]['位置'][3] = -math.sin(jd) * zz * plk
实体[l]['位置'][2] = math.cos(jd) * zz * plk
