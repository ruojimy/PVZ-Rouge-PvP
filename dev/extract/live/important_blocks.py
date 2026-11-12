# live PvP71 region important_blocks
for l in range(len(重要方块) - 1, -1, -1):
    y = c(重要方块[l]['坐标'][0])
    x = c(重要方块[l]['坐标'][1])
    name = c(重要方块[l]['方块'])
    if name == '坟墓':
        ditu[y][x]['长出'] += 1
        if ditu[y][x]['长出'] % 50 == 0:
            xx = x * 比
            yy = y * 比
            yyyy = 按时归位([xx, yy + 比], [xx, yy], 200, ditu[y][x]['长出'])[1]
            增粒子(ditu[y + 1][x]['方块'], [x * 比 + 比 * 0.5, yyyy + 比], 4)
        if ditu[y][x]['长出'] == 200:
            del 重要方块[l]
    if name == '雪':
        if '雪消失' not in ditu[y][x]:
            del 重要方块[l]
        else:
            ditu[y][x]['雪消失'] += 1
            if ditu[y][x]['雪消失'] == 10000:
                摧毁方块(y, x)
                del ditu[y][x]['雪消失']
                沉浸播音('雪', [x * 比 + 比 * 0.5, y * 比 + 比 * 0.5])
                del 重要方块[l]
