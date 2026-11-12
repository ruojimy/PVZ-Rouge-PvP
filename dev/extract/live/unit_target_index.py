# live PvP71 region unit_target_index
分梯 = []
离玩家最近 = -1
for l in range(len(僵尸) - 1, -1, -1):
    if 僵尸[l]['手持'] == '梯子' and '分兵' in 僵尸[l]:
        x = int(僵尸[l]['位置'][0] // 比)
        y = int((僵尸[l]['位置'][1] - 比 * 0.5) // 比)
        分梯.append(x)
    juli = jdz(僵尸[l]['位置'][0] - 玩家位置[0])
    if 僵尸[l]['血量'] > 0 and '魅惑' not in 僵尸[l] and '灰烬' not in 僵尸[l] and '出土' not in 僵尸[l] and 僵尸[l]['出场'] == 500 and (离玩家最近 == -1 or juli < 最近距离):
        离玩家最近 = l
        最近距离 = juli
