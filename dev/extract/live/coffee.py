# live PvP71 region coffee
z = 哪个无南瓜植物(sby, sbx)
if z != -1:
    del 植物[z]['睡觉']
    if 植物[z]['植物'] == '海蘑菇' and '水兵' not in 秘籍:
        新增实体('咖啡豆', fx, [sbx * 比 + 比, sby * 比, 0, 0])
    else:
        新增实体('咖啡豆', fx, [sbx * 比 + 比, sby * 比 + 比 * 0.5, 0, 0])
    实体[-1]['消亡'] = 800
