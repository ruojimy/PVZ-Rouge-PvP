def 刷选块():
    if 选块名 != []:
        for l in range(len(选块)):
            选块[l]['淘汰'] = True
        for l in 选块名:
            wei = False
            if l[0] == '未':
                wei = True
                l = l.split('-')[1]
            新选块(l)
            if 开始方式 == '继续游戏' and l in 数据['继续']:
                shuju = c(数据['继续'][l])
                yq = c(shuju[-1])
                第几天 = 数解密(shuju[1] - yq)
                天 = c(shuju[2])
                选块[-1]['继续'] = '继续:第' + str(第几天) + '天-' + 天
            if 开始方式 == '新游戏' and l in 数据['继续']:
                选块[-1]['警告'] = '警告：存档将会被覆盖'
            if wei:
                if l == '极难模式':
                    zi = '过[正常]解锁'
                if l == '抽奖模式':
                    zi = '马上解锁'
                if l == '末日模式':
                    zi = '过[极难]解锁'
                if l == '我是僵尸':
                    zi = '过[抽奖]解锁'
                选块[-1]['提示'] = zi
                continue
            if not (l == '无尽模式' and 数据['新无尽记录'] != []):
                continue
            选块[-1]['记录'] = '第' + str(数解密(数据['新无尽记录'][0])) + '天-' + 数据['新无尽记录'][1]
        选块归位()

def 僵尸新卡():
    播音('新卡')
    llzx = len(未拥有植物)
    if llzx > 2:
        llzx = 2
    for lzx in range(llzx):
        if 模式 == '我是僵尸' and '梯子僵尸' in 未拥有植物 and lzx == 0:
            for yq in range(len(未拥有植物)):
                if 未拥有植物[yq] != '梯子僵尸':
                    continue
                break
        else:
            yq = 随(0, len(未拥有植物) - 1)
        if llzx == 1:
            x = 比 * 10
        else:
            x = 比 * 7 + lzx * 比 * 6
        新卡动画[c(未拥有植物[yq])] = [[0, 0], 0, [比 * 10, 比 * 12], [x - 比 / 2, 比 * 3], lzx * 250]

def 植物新卡():
    播音('新卡')
    llzx = len(未拥有植物)
    if llzx > 3:
        llzx = 3
    for lzx in range(llzx):
        while True:
            yq = 随(0, len(未拥有植物) - 1)
            if 未拥有植物[yq] not in 新卡动画:
                break
        if lzx == 0:
            if 模式 == '抽奖模式' and '咖啡豆' in 未拥有植物:
                for yq in range(len(未拥有植物)):
                    if 未拥有植物[yq] != '咖啡豆':
                        continue
                    break
            if 模式 in ('极难模式', '末日模式') and '阳光菇' in 未拥有植物:
                for yq in range(len(未拥有植物)):
                    if 未拥有植物[yq] != '阳光菇':
                        continue
                    break
            if 模式 == '正常模式' and '坚果' in 未拥有植物:
                for yq in range(len(未拥有植物)):
                    if 未拥有植物[yq] != '坚果':
                        continue
                    break
        if llzx == 1:
            x = 比 * 10
        else:
            if llzx == 2:
                x = 比 * 7 + lzx * 比 * 6
            else:
                x = 比 * 6 + lzx * 比 * 4
        新卡动画[c(未拥有植物[yq])] = [[0, 0], 0, [比 * 10, 比 * 12], [x - 比 / 2, 比 * 3], lzx * 150]

def 读取(weizhi):
    cd = open(weizhi, 'r')
    lzx = cd.read()
    cd.close()
    # ?? SETUP_FINALLY 40
    # ?? POP_BLOCK None
    return json.loads(lzx)

def 音乐淡出():
    # ?? SETUP_FINALLY 20
    pygame.mixer.music.fadeout(2000)
    # ?? POP_BLOCK None

def 掉血(sh):
    global 玩家恢复, 玩家血量, 玩家倒地, 玩家受伤
    if 模式 != '我是僵尸':
        if 玩家倒地 == 0 and 玩家皮肤 == '疯狂戴夫':
            播音('戴夫疯狂')
        玩家恢复 = 0
        玩家血量 -= sh
        if 玩家倒地 == 0:
            玩家倒地 = 1
        玩家受伤 = 1
        增粒子('血', [玩家位置[0], 玩家位置[1]], 4 + sh * 2)

def 增加重要方块(y, x, name):
    重要方块.append({})
    重要方块[-1]['坐标'] = [y, x]
    重要方块[-1]['方块'] = name

def 飞贼来了():
    feizei = 0
    fz = int(8 * 新手保护)
    if fz == 0:
        fz = 1
    for lzx in 参战僵尸:
        if lzx != '飞贼僵尸':
            continue
        feizei += fz
    可飞 = []
    次可飞 = []
    for x in range(len(ditu[0])):
        for y in range(len(ditu)):
            if ditu[y][x]['方块'] not in kong:
                break
            if '植物' not in ditu[y][x]:
                continue
            z = 哪个植物(y, x)
            if 植物[z]['植物'] in ('地刺', '地刺王'):
                break
            else:
                if 植物[z]['植物'] in 输出植物:
                    可飞.append([y, x])
                else:
                    次可飞.append([y, x])
            break
    for lzx in range(feizei):
        if len(可飞) == 0 and len(次可飞) == 0:
            break
        if len(可飞) > 0:
            yq = 随(0, len(可飞) - 1)
            y, x = c(可飞[yq])
            del 可飞[yq]
        else:
            yq = 随(0, len(次可飞) - 1)
            y, x = c(次可飞[yq])
            del 次可飞[yq]
        fx = 随(0, 1)
        if fx == 0:
            fx = -1
        新增僵尸('飞贼僵尸', [x * 比 + 比 * 0.5, y * 比 + 比, 0, 0], fx)

def 种植植物(sby, sbx, 拿中, fx):
    global 模仿
    if 拿中 == '高坚果' and '石果' in 秘籍:
        拿中 = '石果子'
    if 拿中 == '大嘴花' and '龙蒺藜' in 秘籍:
        拿中 = '龙蒺藜'
    if 拿中 == '大喷菇' and '雷霆' in 秘籍:
        拿中 = '雷蘑菇'
    if 拿中 == '睡莲':
        ditu[sby][sbx]['睡莲'] = fx
    if 拿中 == '花盆':
        ditu[sby][sbx]['方块'] = '花盆块'
        ditu[sby][sbx]['根动画'] = 0
        增粒子('花盆', [sbx * 比 + 比 * 0.5, sby * 比 + 比], 6)
    植物.append({})
    植物[-1]['坐标'] = [sby, sbx]
    植物[-1]['植物'] = 拿中
    植物[-1]['根动画'] = 0
    植物[-1]['头动画'] = 0
    植物[-1]['方向'] = fx
    if 拿中 == '向日葵' or 拿中 == '阳光菇' or 拿中 == '双子向日葵':
        if 模式 == '我是僵尸':
            植物[-1]['阳光'] = 0
        else:
            植物[-1]['阳光'] = 1
        植物[-1]['爆了'] = 0
        if 拿中 == '阳光菇':
            植物[-1]['长大'] = 0
            植物[-1]['成长'] = 20000
    if 拿中 == '大嘴花' or 拿中 == '龙蒺藜':
        植物[-1]['吃'] = 0
        植物[-1]['射'] = 0
        植物[-1]['射cd'] = 0
    if 拿中 == '地刺王':
        植物[-1]['虚血'] = 3
    if 拿中 == '模仿者':
        植物[-1]['模仿'] = 模仿
        if 模式 == '抽奖模式':
            if 随(1, 3 + len(僵尸) // 10) != 1 or boss战:
                while True:
                    name = c(所有植物[随(0, len(所有植物) - 1)])
                    if name not in ('睡莲', '咖啡豆'):
                        break
                植物[-1]['模仿'] = name
            else:
                while True:
                    name = c(参战僵尸图[随(0, len(参战僵尸图) - 1)])
                    if name not in ():
                        break
                植物[-1]['模仿'] = name
        植物[-1]['模仿cd'] = 300
    if 拿中 == '萝卜伞':
        植物[-1]['射cd'] = 0
        植物[-1]['射'] = 0
    if 拿中 == '路灯花':
        植物[-1]['路灯'] = 600
        植物[-1]['爆了'] = 0
    if 拿中 == '土豆地雷':
        植物[-1]['埋藏'] = 6000
        if '地雷' in 秘籍:
            植物[-1]['埋藏'] = 3000
        植物[-1]['出来'] = 0
        植物[-1]['闪'] = 0
    if 拿中 == '金盏花':
        if 模式 == '我是僵尸':
            植物[-1]['钱钱'] = 0
        else:
            植物[-1]['钱钱'] = 1
        植物[-1]['爆了'] = 0
        植物[-1]['金钱'] = 0
    if 拿中 == '裂荚射手':
        植物[-1]['射'] = 0
        植物[-1]['射cd'] = 0
        植物[-1]['副射'] = 0
        植物[-1]['副射cd'] = 0
        植物[-1]['副双发'] = 0
    if 拿中 == '小喷菇' and '小喷' in 秘籍:
        植物[-1]['小喷'] = 15
    if 拿中 == '豌豆射手' or 拿中 == '海蘑菇' or 拿中 == '香蒲' or 拿中 == '机枪射手' or 拿中 == '寒冰射手' or 拿中 == '双发射手' or 拿中 == '小喷菇' or 拿中 == '大喷菇' or 拿中 == '雷蘑菇' or 拿中 == '忧郁蘑菇' or 拿中 == '胆小菇' or 拿中 == '杨桃' or 拿中 == '地刺' or 拿中 == '地刺王' or 拿中 in 投手植物:
        植物[-1]['射'] = 0
        植物[-1]['射cd'] = 0
        if 拿中 == '胆小菇':
            植物[-1]['胆小'] = 0
        if 拿中 == '双发射手':
            植物[-1]['双发'] = 0
        if 拿中 == '机枪射手':
            植物[-1]['机枪'] = 0
    if 天 == '白天' and 拿中 in 夜间植物 and tian != '红天' or '早八' in 秘籍:
        植物[-1]['睡觉'] = 0
    ditu[sby][sbx]['植物'] = True
    植物[-1]['植物血'] = 6
    if 拿中 == '樱桃炸弹' or 拿中 == '毁灭菇' or 拿中 == '寒冰菇' or 拿中 == '火爆辣椒' or 拿中 == '三叶草':
        植物[-1]['消亡'] = 0
    if 拿中 == '墓碑吞噬者':
        植物[-1]['滚蛋'] = 0
    if 拿中 == '玉米加农炮':
        植物[-1]['发射cd'] = 0
        植物[-1]['发射动画'] = 0
        植物[-1]['发射闪闪'] = 0
    if 拿中 == '磁力菇' or 拿中 == '吸金磁':
        植物[-1]['吸'] = 0
    if 拿中 == '仙人掌':
        植物[-1]['射'] = 0
        植物[-1]['射cd'] = 0
        植物[-1]['植物血'] = 36
    if 拿中 == '大蒜':
        植物[-1]['植物血'] = 18
    if 拿中 == '坚果' or 拿中 == '南瓜头':
        植物[-1]['植物血'] = 72
    if 拿中 == '高坚果':
        植物[-1]['植物血'] = 144
    if 拿中 == '石果子':
        植物[-1]['虚血'] = 3
        植物[-1]['消亡'] = 0
        植物[-1]['植物血'] = 144
    if '硬化' in 秘籍:
        植物[-1]['植物血'] += 3
    植物[-1]['受伤'] = 0
    植物[-1]['植物血上限'] = c(植物[-1]['植物血'])
    if 拿中 not in ('花盆', '睡莲', '墓碑吞噬者'):
        模仿 = 拿中

def 击退僵尸(z, jf):
    if 僵尸[z]['防具'] in ('橄榄球头盔', '黑橄榄球头盔') or 僵尸[z]['大小'] > 2 or '狂暴' in 僵尸[z] or '撑杆' in 僵尸[z] or 僵尸[z]['手持'] == '海豚' and 僵尸[z]['入水'] or '跳舞' in 僵尸[z] and 僵尸[z]['跳舞'] > 0 and 僵尸[z]['血量'] > 0 or 僵尸[z]['手持'] == '玩偶匣' and 僵尸[z]['血量'] <= 0:
        jf = 0
    僵尸[z]['位置'][2] += jf

def 保存数据():
    user_dir = os.path.expanduser('~')
    file_name = 'pvzrouge.json'
    file_path = os.path.join(user_dir, file_name)
    保存(file_path, 数据)

def 保存备份数据():
    user_dir = os.path.expanduser('~')
    file_name = 'pvzrougeb.json'
    file_path = os.path.join(user_dir, file_name)
    保存(file_path, 数据)

def 保存进度():
    yq = 随(-1000, 1000)
    if 模式 == '无尽模式':
        数据['地图'] = c(ditu)
        数据['植物'] = c(植物)
    数据['继续'][模式] = [拥有植物, 数加密(第几天) + yq, 天, 数加密(初始阳光) + yq, 数加密(卡槽数) + yq, 数加密(钱) + yq, 商店植物, 商店存货, 数加密(防守) + yq, 数加密(作战数) + yq, 雨天位, 作战, 参战僵尸, 未参战僵尸, 模式, 秘籍, yq]
    保存数据()

def 坟墓出僵尸():
    lzx = 0
    for y in range(len(ditu)):
        for x in range(len(ditu[0])):
            if ditu[y][x]['方块'] != '坟墓':
                continue
            lzx += 1
            if lzx == 1:
                name = '普通僵尸'
            if lzx == 2:
                name = '路障僵尸'
            if lzx == 3:
                name = '铁桶僵尸'
                lzx = 0
            if 随(0, 1) == 0:
                fx = -1
            else:
                fx = 1
            新增僵尸(name, [x * 比 + 比 * 0.5, y * 比, 0, 0], fx)
            僵尸[-1]['出场初位置'][1] = y * 比 + 比 * 3
            僵尸[-1]['出场末位置'][1] = y * 比 + 比 * 1.2
            沉浸播音('出坟墓', [x * 比 + 比 * 0.5, y * 比 + 比 * 0.5])

def 摧毁实方块(y, x):
    if not 出界(y, x) and y != len(ditu) - 1 and ditu[y][x]['方块'] not in kong:
        摧毁方块(y, x)

def 摧毁方块(y, x):
    if not 出界(y, x) and y != len(ditu) - 1:
        name = c(ditu[y][x]['方块'])
        if name != '空':
            增粒子(name, [x * 比 + 比 * 0.5, y * 比 + 比 * 0.5], 9)
        if name == '花盆块':
            ditu[y][x]['方块'] = '空'
            if not 出界(y - 1, x) and '植物' in ditu[y - 1][x]:
                清除植物(y - 1, x)
        if y < 水平面 and name != '车底':
            if name not in kong + ['雪']:
                ditu[y][x]['里方块'] = name
                沉浸播音('方块' + str(随(1, 4)), [x * 比 + 比 * 0.5, y * 比 + 比 * 0.5])
            ditu[y][x]['方块'] = '空'
            if name not in kong + ['雪']:
                ditu[y][x]['摧'] = 0
        if '植物' in ditu[y][x]:
            清除植物(y, x)

def 灰烬僵尸(z):
    if 僵尸[z]['血量'] + 僵尸[z]['防具血量'] > 500:
        if 僵尸[z]['僵尸'] in boss:
            伤害僵尸(z, 1, 300)
        else:
            伤害僵尸(z, 1, 500)
    else:
        僵尸[z]['灰烬'] = 0

def 表面伤害僵尸(z, fx, shanghai):
    if '灰烬' not in 僵尸[z]:
        if 僵尸[z]['手持血量'] > 0:
            僵尸[z]['手持受伤'] = 1
            if 僵尸[z]['手持'] == '报纸':
                沉浸播音('报纸', [僵尸[z]['位置'][0], 僵尸[z]['位置'][1]])
            if 僵尸[z]['手持'] == '气球':
                沉浸播音('气球爆炸', [僵尸[z]['位置'][0], 僵尸[z]['位置'][1]])
            if 僵尸[z]['手持'] == '钢门' or 僵尸[z]['手持'] == '梯子':
                沉浸播音('铁桶' + str(随(1, 2)), [僵尸[z]['位置'][0], 僵尸[z]['位置'][1]])
            僵尸[z]['手持血量'] -= shanghai
            if 僵尸[z]['手持血量'] <= 0:
                if 僵尸[z]['手持'] == '气球':
                    僵尸[z]['手持'] = ''
                    增粒子('气球', [僵尸[z]['位置'][0], 僵尸[z]['位置'][1] - 比 * 2.5], 12)
                    僵尸[z]['气球'] = 1
                else:
                    新增实体(c(僵尸[z]['手持']), c(僵尸[z]['方向']), c(僵尸[z]['位置']))
                    僵尸[z]['手持'] = ''
                    实体[-1]['牛顿'] = 0
                    实体[-1]['位置'][0] -= 比 * 0.5
                    实体[-1]['位置'][1] -= 比 * 1.5
                    实体[-1]['位置'][2] = fx * plk * 400
                    实体[-1]['位置'][3] = -随(350, 450) * plk
                    实体[-1]['消亡'] = 1
            return True
        伤害僵尸(z, fx, shanghai)
    return False

def 伤害僵尸(z, fx, shanghai):
    if '灰烬' not in 僵尸[z]:
        僵尸[z]['受伤'] = 1
        if 僵尸[z]['防具血量'] > 0 and shanghai < 僵尸[z]['防具血量'] + 僵尸[z]['血量']:
            if 僵尸[z]['防具'] in ('路障', '橄榄球头盔', '黑橄榄球头盔'):
                沉浸播音('路障' + str(随(1, 2)), [僵尸[z]['位置'][0], 僵尸[z]['位置'][1]])
            if 僵尸[z]['防具'] == '铁桶':
                沉浸播音('铁桶' + str(随(1, 2)), [僵尸[z]['位置'][0], 僵尸[z]['位置'][1]])
            僵尸[z]['防具血量'] -= shanghai
            if 僵尸[z]['防具血量'] <= 0:
                僵尸[z]['防具血量'] = 0
                新增实体(c(僵尸[z]['防具']), c(僵尸[z]['方向']), c(僵尸[z]['位置']))
                僵尸[z]['防具'] = ''
                实体[-1]['牛顿'] = 0
                实体[-1]['位置'][0] -= 比 * 0.5
                实体[-1]['位置'][1] -= 比 * 1.5
                实体[-1]['位置'][2] = fx * plk * 400
                实体[-1]['位置'][3] = -随(350, 450) * plk
                实体[-1]['消亡'] = 1
        else:
            if 僵尸[z]['血量'] > 0:
                僵尸[z]['血量'] -= shanghai
                if 僵尸[z]['僵尸'] == '投篮车僵尸':
                    沉浸播音('路障' + str(随(1, 2)), [僵尸[z]['位置'][0], 僵尸[z]['位置'][1]])
                if 僵尸[z]['僵尸'] == '雪橇车僵尸':
                    沉浸播音('铁桶' + str(随(1, 2)), [僵尸[z]['位置'][0], 僵尸[z]['位置'][1]])
                if 僵尸[z]['血量'] <= 0:
                    僵尸[z]['血量'] = 0
                    if 僵尸[z]['僵尸'] == '巨人僵尸':
                        沉浸播音('巨人之死', [僵尸[z]['位置'][0], 僵尸[z]['位置'][1]])
                    else:
                        if 僵尸[z]['防具血量'] > 0:
                            僵尸[z]['防具血量'] = 0
                            新增实体(c(僵尸[z]['防具']), c(僵尸[z]['方向']), c(僵尸[z]['位置']))
                            僵尸[z]['防具'] = ''
                            实体[-1]['牛顿'] = 0
                            实体[-1]['位置'][0] -= 比 * 0.5
                            实体[-1]['位置'][1] -= 比 * 1.5
                            实体[-1]['位置'][2] = fx * plk * 400
                            实体[-1]['位置'][3] = -随(350, 450) * plk
                            实体[-1]['消亡'] = 1
                        沉浸播音('掉头', [僵尸[z]['位置'][0], 僵尸[z]['位置'][1]])
                        if 僵尸[z]['手持'] == '玩偶匣':
                            沉浸播音('小丑' + str(随(1, 2)), [僵尸[z]['位置'][0], 僵尸[z]['位置'][1]])
                            僵尸[z]['位置'][2] = 350 * plk * 僵尸[z]['方向']
                        新增实体(僵尸[z]['僵尸'] + '-首', c(僵尸[z]['方向']), c(僵尸[z]['位置']))
                        僵尸[z]['位置'][2] -= 僵尸[z]['方向'] * plk * 100
                        实体[-1]['牛顿'] = 0
                        实体[-1]['位置'][1] -= 比 * 1.5
                        实体[-1]['位置'][2] = fx * plk * 400
                        实体[-1]['位置'][3] = -随(350, 450) * plk
                        实体[-1]['消亡'] = 1

def 扁死(y, x):
    z = 哪个植物(y, x)
    if z != -1:
        沉浸播音('吃' + str(随(1, 2)), [x * 比 + 比 * 0.5, y * 比 + 比 * 0.5])
        if '虚血' in 植物[z]:
            植物[z]['受伤'] = 1
            植物[z]['虚血'] -= 1
            if 植物[z]['虚血'] == 1:
                del 植物[z]['虚血']
            return True
        清除植物(y, x)
        if 植物[z]['植物'] == '缠绕海草':
            植物[z]['铲死'] = 0
        name = c(植物[z]['植物'])
        lzx = 比 * 1.2
        if name == '海蘑菇' and '水兵' not in 秘籍:
            lzx -= 比 * 0.6
        if name == '缠绕海草' or name == '睡莲':
            lzx += -比 * 0.8
        if name == '香蒲':
            lzx += -比 * 0.9
        新增实体(name, c(植物[z]['方向']), [x * 比 + 比 * 0.8, y * 比 + 比 * 0.1 + lzx, 0, 0])
        hb = ''
        if '黑白' in 植物[z]:
            hb = '-黑白'
        实体[-1]['扁'] = 变图(图集[name + hb], 比 * 1.4, 比 * 0.3)
        if 植物[z]['方向'] == -1:
            实体[-1]['扁'] = 反(实体[-1]['扁'])
        实体[-1]['消亡'] = 800
        return True
    return False

def 清除植物(y, x):
    z = 哪个植物(y, x)
    if z != -1:
        植物[z]['死'] = 0
        return True
    return False

def 显示近景(tu, zuobiao):
    裁剪显示(tu, [0, 0], [-zuobiao[0], 0, 总宽, 总高])

def 生成近景(name, tianse):
    近景 = 加载图('图片/透明.png', 1152, 384)
    for y in range(24):
        r, g, b = 天色[tianse]
        se = (12 - y) * -1
        r += se
        g += se
        b += se
        if r < 0:
            r = 0
        if r > 255:
            r = 255
        if g < 0:
            g = 0
        if g > 255:
            g = 255
        if b < 0:
            b = 0
        if b > 255:
            b = 255
        pygame.draw.rect(近景, (r, g, b), [0, y * 16, 1152, 16], 0)
    if name != '木船':
        sha = False
        if name in ('沙城', '绿洲'):
            sha = True
        近景ditu = 生成地图('山地')
        if 天 == '白天':
            for y in range(len(近景ditu)):
                for x in range(len(近景ditu[0])):
                    for yy in range(16):
                        for xx in range(16):
                            if 近景ditu[y][x]['方块'] == '空':
                                continue
                            if sha:
                                if 近景ditu[y][x]['方块'] == '草':
                                    a = 近景图集['沙板'].get_at((xx, yy))
                                else:
                                    a = 近景图集['沙石'].get_at((xx, yy))
                            else:
                                a = 近景图集[近景ditu[y][x]['方块']].get_at((xx, yy))
                            近景.set_at((x * 16 + xx, y * 16 + yy), a)
        else:
            for y in range(len(近景ditu)):
                for x in range(len(近景ditu[0])):
                    for yy in range(16):
                        for xx in range(16):
                            if 近景ditu[y][x]['方块'] == '空':
                                continue
                            if sha:
                                if 近景ditu[y][x]['方块'] == '草':
                                    a = 近景图集['沙板'].get_at((xx, yy))
                                else:
                                    a = 近景图集['沙石'].get_at((xx, yy))
                            else:
                                a = 近景图集[近景ditu[y][x]['方块']].get_at((xx, yy))
                            近景.set_at((x * 16 + xx, y * 16 + yy), (a[0] // 2, a[1] // 2, a[2] // 2, a[3]))
        chang = len(近景ditu[0])
        for x in range(len(近景ditu[0])):
            for y in range(len(近景ditu) - 1, -1, -1):
                if 近景ditu[y][x]['方块'] == '空':
                    for xx in range(16):
                        近景.set_at((x * 16 + xx, y * 16 + 15), (0, 0, 0, 255))
                    break
                if x > 0 and 近景ditu[y][x - 1]['方块'] == '空':
                    for yy in range(16):
                        近景.set_at((x * 16, y * 16 + yy), (0, 0, 0, 255))
                if not (x < chang - 1 and 近景ditu[y][x + 1]['方块'] == '空'):
                    continue
                for yy in range(16):
                    近景.set_at((x * 16 + 16, y * 16 + yy), (0, 0, 0, 255))
    return 变图(近景, 总高 * 3, 总高)

def 哪个植物(y, x):
    lzx = -1
    for ll in range(len(植物)):
        if not (植物[ll]['坐标'][0] == y and 植物[ll]['坐标'][1] == x):
            continue
        if 植物[ll]['植物'] == '南瓜头':
            lzx = ll
            break
        lzx = ll
    return lzx

def 哪个无南瓜植物(y, x):
    lzx = -1
    for ll in range(len(植物)):
        if not (植物[ll]['坐标'][0] == y and 植物[ll]['坐标'][1] == x):
            continue
        if 植物[ll]['植物'] == '南瓜头':
            continue
        lzx = ll
    return lzx

def 新增僵尸(name, weizhi, fx):
    僵尸.append({})
    fj = ''
    sc = ''
    fjxl = 0
    scxl = 0
    yisu = 40
    xl = 100
    xcxl = 0
    僵尸[-1]['坚持分兵'] = 0
    僵尸[-1]['再出场'] = 10000
    僵尸[-1]['大小'] = 2
    僵尸[-1]['出场'] = 0
    僵尸[-1]['出场初位置'] = [c(weizhi[0]), 比 * 25]
    if 玩家位置[0] > weizhi[0]:
        fxx = 1
    else:
        fxx = -1
    if name == '小丑僵尸':
        yisu = 60
        sc = '玩偶匣'
        xl = 150
        沉浸播音('小丑音乐', [玩家位置[0] - fxx * 比 * 16, weizhi[1]])
    if name == '撑杆跳僵尸':
        僵尸[-1]['撑杆'] = 0
        yisu = 100
        sc = '撑杆'
        xl = 150
    if name == '梯子僵尸':
        yisu = 60
        sc = '梯子'
        xl = 150
        scxl = 250
    if name == '小鬼僵尸':
        yisu = 60
        xl = 60
    if name == '飞贼僵尸':
        新增实体('飞贼目标', fx, [weizhi[0] + 比 * 0.5, -比 * 15, 0, 500 * plk])
        实体[-1]['消亡'] = 0
        实体[-1]['牛顿'] = 0
        僵尸[-1]['出场'] = -500
        僵尸[-1]['眩晕'] = 50
        僵尸[-1]['出场初位置'][1] = -比 * 15
        僵尸[-1]['绳初位置'] = c(僵尸[-1]['出场初位置'])
        僵尸[-1]['位置'] = c(僵尸[-1]['出场初位置'])
        yisu = 10
        xl = 200
    if name == '旗帜僵尸':
        yisu = 80
    if name == '潜水僵尸':
        yisu = 60
    if name == '雪橇车小队僵尸':
        yisu = 80
    if name == '海豚僵尸':
        沉浸播音('海豚', [玩家位置[0] - fxx * 比 * 30, weizhi[1]])
        yisu = 80
        xl = 150
        sc = '海豚'
    if name == '气球僵尸':
        weizhi[1] -= 比 * 2
        沉浸播音('气球', [玩家位置[0] - fxx * 比 * 12, weizhi[1]])
        xl = 150
        scxl = 1
        sc = '气球'
        僵尸[-1]['气球'] = 0
        僵尸[-1]['中场'] = 0
    if name == '矿工僵尸':
        weizhi[1] = len(ditu) * 比 + 比 * 2
        僵尸[-1]['出土'] = False
        xl = 150
        sc = '矿镐'
    if name == '蹦蹦僵尸':
        xl = 150
        sc = '弹跳杆'
    僵尸[-1]['炸音'] = 0
    if name == '伴舞僵尸':
        xl = 150
        僵尸[-1]['跳舞'] = 1
    if name == '雪人僵尸':
        xl = 10000
        yisu = 90
        僵尸[-1]['出场'] = -10000
    if name == '舞王僵尸':
        xl = 10000
        僵尸[-1]['跳舞'] = 0
        僵尸[-1]['跳舞cd'] = 1000
        僵尸[-1]['灯光'] = 1
    if name == '路障僵尸':
        name = '普通僵尸'
        fj = '路障'
        fjxl = 200
    if name == '投篮车僵尸':
        僵尸[-1]['前进'] = 0
        僵尸[-1]['篮球cd'] = 500
        僵尸[-1]['篮球总量'] = 48
        僵尸[-1]['篮球'] = 3
        僵尸[-1]['投篮'] = 0
        僵尸[-1]['撞车'] = 0
        僵尸[-1]['大小'] = 3
        僵尸[-1]['轮子'] = 0
        xl = 400
    if name == '雪橇车僵尸':
        僵尸[-1]['雪容量'] = len(ditu[0]) // 2 - 6
        僵尸[-1]['撞车'] = 0
        僵尸[-1]['大小'] = 3
        僵尸[-1]['轮子'] = 0
        xl = 600
        沉浸播音('雪橇车', [玩家位置[0] - fxx * 比, weizhi[1]])
    if name == '铁桶僵尸':
        name = '普通僵尸'
        fj = '铁桶'
        fjxl = 500
    if name == '巨人僵尸':
        僵尸[-1]['手持动画'] = [0, 0, 0, 0, 0, 0]
        僵尸[-1]['大小'] = 3
        xl = 2000
        yisu = 30
        sc = '锤子' + str(随(1, 3))
    if name == '红眼巨人僵尸':
        name = '巨人僵尸'
        僵尸[-1]['手持动画'] = [0, 0, 0, 0, 0, 0]
        僵尸[-1]['大小'] = 3
        僵尸[-1]['丢小鬼'] = 0
        僵尸[-1]['苏醒'] = -1
        僵尸[-1]['红眼'] = 0
        if 模式 == '测试模式':
            僵尸[-1]['出场'] = 500
            weizhi[1] -= 总高 * 2
            weizhi[3] = 500 * plk
        xl = 20000
        yisu = 50
        sc = '锤子' + str(随(1, 3))
    if name == '橄榄球僵尸':
        name = '橄榄球僵尸'
        fj = '橄榄球头盔'
        fjxl = 800
        yisu = 80
    if name == '黑橄榄球僵尸':
        name = '黑橄榄球僵尸'
        fj = '黑橄榄球头盔'
        fjxl = 14000
        xl = 1000
        yisu = 80
    if name == '鸭子普通僵尸':
        name = '鸭子僵尸'
    if name == '鸭子路障僵尸':
        name = '鸭子僵尸'
        fj = '路障'
        fjxl = 200
    if name == '鸭子铁桶僵尸':
        name = '鸭子僵尸'
        fj = '铁桶'
        fjxl = 500
    if name == '钢门普通僵尸':
        name = '普通僵尸'
        sc = '钢门'
        scxl = 500
    if name == '报纸僵尸':
        name = '报纸僵尸'
        sc = '报纸'
        scxl = 100
        xl = 1000
        yisu = 30
    if name == '铁桶钢门僵尸':
        name = '普通僵尸'
        fj = '铁桶'
        fjxl = 500
        sc = '钢门'
        scxl = 500
    if 模式 == '末日模式':
        xl += xl
        fjxl += fjxl
        xcxl += xcxl
    if 模式 not in ('极难模式', '末日模式', '无尽模式', '测试模式'):
        xl = xl // 2
        fjxl = fjxl // 2
        xcxl = xcxl // 2
        if 模式 == '抽奖模式' and (name in boss or '红眼' in 僵尸[-1]):
            xl = xl // 2
            fjxl = fjxl // 2
            xcxl = xcxl // 2
    if name == '巨人僵尸':
        僵尸[-1]['半血'] = xl // 2
    僵尸[-1]['憋气'] = 0
    僵尸[-1]['僵尸'] = name
    僵尸[-1]['防具'] = fj
    僵尸[-1]['手持'] = sc
    僵尸[-1]['手持血量'] = scxl
    僵尸[-1]['防具血量'] = fjxl
    僵尸[-1]['方向'] = fx
    僵尸[-1]['血量'] = xl
    僵尸[-1]['受伤'] = 0
    僵尸[-1]['手持受伤'] = 0
    僵尸[-1]['跳跃cd'] = 0
    僵尸[-1]['位置'] = c(weizhi)
    僵尸[-1]['啃咬'] = 0
    僵尸[-1]['移速'] = (yisu + 随(-5, 5)) * plk
    僵尸[-1]['入水'] = False
    僵尸[-1]['出场末位置'] = [c(weizhi[0]), c(weizhi[1]) + 比 * 0.2]

def 新增实体(name, fx, weizhi):
    实体.append({})
    实体[-1]['名'] = name
    实体[-1]['方向'] = fx
    实体[-1]['位置'] = weizhi

def 多少cd(name):
    if 模式 == '测试模式':
        return 0
    if name == '墓碑吞噬者' or name == '土豆地雷':
        cd = 500
    if name == '花盆':
        cd = 400
    if name == '向日葵' or name == '阳光菇' or name == '大嘴花':
        cd = 3000
    if name == '胆小菇' or name == '卷心菜投手' or name == '玉米投手' or name == '豌豆射手' or name == '路灯花':
        cd = 1000
    if name == '睡莲' or name == '地刺':
        cd = 750
    if name == '咖啡豆':
        cd = 3000
        if '咖啡' in 秘籍:
            cd = 750
    if name == '缠绕海草' or name == '小喷菇' or name == '海蘑菇' or name == '大喷菇':
        cd = 1500
    if name == '双发射手':
        cd = 2000
    if name == '寒冰射手' or name == '萝卜伞' or name == '仙人掌' or name == '裂荚射手':
        cd = 3000
    if name == '杨桃':
        cd = 4000
    if name == '磁力菇' or name == '火炬树桩' or name == '机枪射手' or name == '吸金磁':
        cd = 8000
    if name == '西瓜投手' or name == '双子向日葵' or name == '地刺王' or name == '忧郁蘑菇' or name == '坚果':
        cd = 5000
    if name == '高坚果':
        cd = 9000
    if name == '金盏花' or name == '南瓜头':
        cd = 6000
    if name == '大蒜' or name == '三叶草' or name == '寒冰菇':
        cd = 12000
    if name == '香蒲' or name == '魅惑菇' or name == '窝瓜':
        cd = 10000
    if name == '冰瓜投手':
        cd = 7000
    if name == '模仿者':
        cd = 20000
        if 模式 == '抽奖模式':
            cd = 300
            if boss战:
                cd = 1000
    if name == '樱桃炸弹' or name == '火爆辣椒' or name == '玉米加农炮':
        cd = 30000
    if name == '毁灭菇':
        cd = 40000
    if not (版本 != 'v233.0.0' or boss战) and 测试秘籍 != '速植':
        cd = cd // 10
    if '速植' in 秘籍:
        cd -= cd // 10
    return cd

def 方向性增粒子(name, zuobiao, duoshao, fx):
    if 设置['粒子效果']:
        if zuobiao[0] < 摄像机[0] - 比 or zuobiao[0] > 摄像机[0] + 总宽 + 比:
            pass
        else:
            if name in 图集:
                w, h = 图集[name].get_size()
                if fx == 2:
                    yfx = 1
                else:
                    yfx = -1
                xfx = 0
                if fx == 3:
                    xfx = -1
                if fx == 4:
                    xfx = 1
                for lzx in range(duoshao):
                    if xfx == 0:
                        fx = 1
                        if lzx % 2 == 0:
                            fx = -1
                    else:
                        fx = xfx
                    top = 0
                    while top < 10:
                        top += 1
                        x = 随(int(w / 4), int(w / 4) * 3)
                        y = 随(int(h / 4), int(h / 4) * 3)
                        a = 图集[c(name)].get_at((x, y))
                        if a[3] <= 0:
                            continue
                        if not (a[0] == 0 and a[1] == 0 and a[2] == 0):
                            break
                    if top >= 10:
                        continue
                    粒子.append([c(a), [c(zuobiao[0]), c(zuobiao[1]), fx * 随(100, 200) * plk, yfx * 随(50, 250) * plk], 0])

def 增粒子(name, zuobiao, duoshao):
    if 设置['粒子效果']:
        if zuobiao[0] < 摄像机[0] - 比 or zuobiao[0] > 摄像机[0] + 总宽 + 比:
            pass
        else:
            if name in 图集:
                w, h = 图集[name].get_size()
                for lzx in range(duoshao):
                    fx = 1
                    if lzx % 2 == 0:
                        fx = -1
                    top = 0
                    while top < 10:
                        top += 1
                        x = 随(int(w / 4), int(w / 4) * 3)
                        y = 随(int(h / 4), int(h / 4) * 3)
                        a = 图集[c(name)].get_at((x, y))
                        if a[3] <= 0:
                            continue
                        if not (a[0] == 0 and a[1] == 0 and a[2] == 0):
                            break
                    if top >= 10:
                        continue
                    if duoshao == 30:
                        粒子.append([c(a), [c(zuobiao[0]), c(zuobiao[1]), fx * 随(150, 250) * plk, -随(350, 450) * plk], 0])
                        continue
                    粒子.append([c(a), [c(zuobiao[0]), c(zuobiao[1]), fx * 随(100, 200) * plk, -随(150, 250) * plk], 0])

def 旋转摄像显示(图片, zuobiao, dushu):
    if not (补帧 != 0 or 不显(图片, zuobiao)):
        dushu = -dushu
        center = 图片.get_rect().center
        temp = pygame.transform.rotate(图片, dushu)
        new = temp.get_rect(center=center)
        摄像显示(temp, [zuobiao[0] + new[0] + 抖屏[1], zuobiao[1] + new[1] + 抖屏[2]])

def 旋转显示(图片, zuobiao, dushu):
    if 补帧 == 0:
        dushu = -dushu
        center = 图片.get_rect().center
        temp = pygame.transform.rotate(图片, dushu)
        new = temp.get_rect(center=center)
        显示(temp, [zuobiao[0] + new[0], zuobiao[1] + new[1]])

def 旋转(图片, zuobiao, dushu):
    if 补帧 == 0:
        dushu = -dushu
        center = 图片.get_rect().center
        temp = pygame.transform.rotate(图片, dushu)
        new = temp.get_rect(center=center)
        return [temp, [zuobiao[0] + new[0], zuobiao[1] + new[1]]]
    return [图片, zuobiao]

def 无墙位移处理(weizhi):
    if weizhi[2] < 0:
        weizhi[2] += plk * 1
        if weizhi[2] > 0:
            weizhi[2] = 0
    else:
        if weizhi[2] > 0:
            weizhi[2] -= plk * 1
            if weizhi[2] < 0:
                weizhi[2] = 0
    weizhi[3] += plk * 3
    weizhi[0] += weizhi[2]
    weizhi[1] += weizhi[3]

def 位移处理(weizhi, daxiao):
    if daxiao == 0:
        dian = [[c(weizhi[0]), c(weizhi[1])]]
    else:
        dian = [[weizhi[0] - 比 * 0.3 * daxiao, weizhi[1] - 比 * 1.5 * daxiao], [weizhi[0] - 比 * 0.3 * daxiao, weizhi[1] - 比 * 0.2], [weizhi[0] + 比 * 0.3 * daxiao, weizhi[1] - 比 * 1.5 * daxiao], [weizhi[0] + 比 * 0.3 * daxiao, weizhi[1] - 比 * 0.2]]
        dian.append([weizhi[0] - 比 * 0.3 * daxiao, weizhi[1] - 比 * 0.75])
        dian.append([weizhi[0] + 比 * 0.3 * daxiao, weizhi[1] - 比 * 0.75])
    if weizhi[2] < 0:
        weizhi[2] += plk * 2
        if weizhi[2] > 0:
            weizhi[2] = 0
    else:
        if weizhi[2] > 0:
            weizhi[2] -= plk * 2
            if weizhi[2] < 0:
                weizhi[2] = 0
    weizhi[3] += plk * 4
    横可 = True
    竖可 = True
    hengdian = []
    shudian = []
    for lzx in range(len(dian)):
        y = int(dian[lzx][1] // 比)
        x = int(dian[lzx][0] // 比)
        yy = int((dian[lzx][1] + weizhi[3]) // 比)
        if 不封顶出界(yy, x):
            竖可 = False
            shudian.append(lzx)
        else:
            if yy >= 0 and ditu[yy][x]['方块'] not in kong:
                竖可 = False
                shudian.append(lzx)
        xx = int((dian[lzx][0] + weizhi[2]) // 比)
        if 不封顶出界(y, xx):
            横可 = False
            hengdian.append(lzx)
        else:
            if not (y >= 0 and ditu[y][xx]['方块'] not in kong):
                continue
            横可 = False
            hengdian.append(lzx)
    if not (横可 or 竖可):
        weizhi[1] -= plk * 20
        weizhi[0] -= weizhi[2]
    tiao = 0
    if 竖可:
        weizhi[1] += weizhi[3]
    else:
        tiao = 2
        if weizhi[3] > 0:
            tiao = 1
            weizhi[3] = -jdz(weizhi[2])
            if weizhi[3] < -plk * 200:
                weizhi[3] = -plk * 200
        else:
            weizhi[3] = 0
    if 横可:
        weizhi[0] += weizhi[2]
    else:
        if not (竖可 or 横可):
            weizhi[0] -= weizhi[2]
        weizhi[2] = 0
    if 出界(int(weizhi[1] // 比), int((weizhi[0] - daxiao * 比 * 0.3) // 比)):
        weizhi[0] += plk * 10
    if 出界(int(weizhi[1] // 比), int((weizhi[0] + daxiao * 比 * 0.3) // 比)):
        weizhi[0] -= plk * 10
    return tiao

def 生成地图(name):
    ditu = []
    dituh = []
    for x in range(72):
        dituh.append({})
        dituh[-1]['方块'] = '空'
    for y in range(24):
        ditu.append(c(dituh))
    if name == '山地':
        起伏y = 22
        x = -1
        终x = len(ditu[0])
        参数 = 随(10, 20)
        连续 = 参数 + 随(-参数 // 5, 参数 // 5)
        上下 = 0
        真连续 = 0
        while True:
            x += 1
            if x == 终x:
                break
            连续 -= 1
            if 连续 <= 0 and 真连续 > 1:
                连续 = 参数 + 随(-参数 // 5, 参数 // 5)
                if 上下 == 0:
                    上下 = 1
                else:
                    上下 = 0
            if 随(1, 2) == 1:
                if 上下 == 0:
                    起伏y -= 1
                    if 起伏y < 8:
                        起伏y = 8
                    else:
                        真连续 = 0
                else:
                    起伏y += 1
                    if 起伏y > 22:
                        起伏y = 22
                    else:
                        真连续 = 0
            else:
                真连续 += 1
            if 22 - 起伏y > 终x - x:
                起伏y = 22 - 终x + x
            cao = 1
            tu = 1
            for yy in range(24 - 起伏y):
                y = 起伏y + yy
                zi = '石'
                if cao > 0:
                    cao -= 1
                    zi = '草'
                else:
                    if tu > 0:
                        tu -= 1
                        zi = '土'
                ditu[y][x]['方块'] = zi
    else:
        if name == '大楼':
            lou = 2
            chux = (len(ditu[0]) - lou * 16) // 2
            gao = 6
            chang = 12
            for x in range(len(ditu[0])):
                yy = 20
                for lzx in range(len(ditu) - yy):
                    if lzx == 0:
                        fk = '草'
                    else:
                        if lzx == 1:
                            fk = '土'
                            if x >= 20 and x <= 49:
                                fk = '石'
                        else:
                            fk = '石'
                    y = yy + lzx
                    ditu[y][x]['方块'] = fk
            tongdao = 随(0, 1)
            for xx in range(6):
                x = xx + chux + 12
                ditu[20][x]['方块'] = '墙砖'
            if tongdao == 0:
                for xx in range(6):
                    x = xx + chux + 12
                    for yy in range(gao + 1):
                        y = 20 - gao * 2 + yy
                        if yy == 0 or yy == gao:
                            ditu[y][x]['方块'] = '墙砖'
                        else:
                            if yy == gao // 2 or yy == gao // 2 + 1:
                                ditu[y][x]['里方块'] = '窗户'
                            else:
                                ditu[y][x]['里方块'] = '墙砖'
            if 随(1, 2) == 1:
                yqq = 6
                if tongdao == 1:
                    yy = 20 - 3 * gao
                    for lzx in range(gao * 3 - gao):
                        y = yy + lzx + gao
                        ditu[y][chux + chang]['方块'] = '梯子块'
            else:
                yqq = 9
                if tongdao == 1:
                    yy = 20 - 3 * gao
                    for lzx in range(gao * 3 - gao):
                        y = yy + lzx + gao
                        ditu[y][chux + chang + 5]['方块'] = '梯子块'
            if tongdao == 1:
                if yqq == 6:
                    yq = 8
                else:
                    yq = 5
            else:
                if 随(1, 2) == 1:
                    yq = 4
                else:
                    yq = 7
            破门位 = [随(2, 3), yq, 随(11, 12), yqq]
            if tongdao == 0:
                破门位 += [5, 8]
            for l in range(lou):
                for ceng in range(3):
                    if 随(0, 1) == 0:
                        yqx = 2
                    else:
                        yqx = 8
                    for yy in range(gao):
                        y = 20 - gao + yy - ceng * gao
                        for xx in range(chang):
                            x = chux + xx
                            if yy == 0:
                                ditu[y][x]['方块'] = '墙砖'
                            else:
                                if xx == 0 and (1 + ceng + l * 6 not in 破门位 or yy == 1):
                                    ditu[y][x]['方块'] = '墙砖'
                                else:
                                    if xx == chang - 1 and (4 + ceng + l * 6 not in 破门位 or yy == 1):
                                        ditu[y][x]['方块'] = '墙砖'
                                    else:
                                        if yy == 3 and xx > 1 and xx < chang - 2 and gao > 3:
                                            ditu[y][x]['里方块'] = '窗户'
                                        else:
                                            ditu[y][x]['里方块'] = '墙砖'
                            if ceng != 0:
                                continue
                            ditu[20][x]['方块'] = '墙砖'
                        if ceng == 2:
                            continue
                        if ditu[y][chux + yqx]['方块'] != '空':
                            ditu[y][chux + yqx]['里方块'] = c(ditu[y][chux + yqx]['方块'])
                        ditu[y][chux + yqx]['方块'] = '梯子块'
                chux += chang + 6
        else:
            if name == '铁道':
                for yy in range(8):
                    if yy == 0:
                        fk = '铁路'
                    else:
                        if yy == 1:
                            fk = '石'
                        else:
                            fk = '石'
                    y = yy + 16
                    for x in range(len(ditu[0])):
                        ditu[y][x]['方块'] = fk
                for lzx in range(6):
                    if lzx == 5:
                        yq = 随(1, 3)
                    else:
                        yq = 随(1, 4)
                    for yy in range(6):
                        y = 9 + yy
                        for xx in range(11):
                            x = xx + lzx * 12 + 1
                            if yy == 0 or yy <= 2 and (xx == 0 or xx == 10):
                                ditu[y][x]['方块'] = '车体'
                            else:
                                if yy == 5:
                                    ditu[y][x]['方块'] = '车底'
                                else:
                                    if yy == 3 and xx > 1 and xx < 9:
                                        ditu[y][x]['里方块'] = '窗户'
                                    else:
                                        ditu[y][x]['里方块'] = '车体'
                    if 随(1, 4) == 1 or lzx == 2:
                        for yy in range(5):
                            y = 9 + yy
                            if yy == 0 or ditu[y][lzx * 12 + 6]['方块'] == '空':
                                ditu[y][lzx * 12 + 6]['方块'] = '梯子块'
                            if yy != 0:
                                continue
                            ditu[y][lzx * 12 + 6]['里方块'] = '车体'
                    if yq == 2:
                        for yy in range(2):
                            y = 12 + yy
                            for xx in range(5):
                                x = xx + lzx * 12 + 4
                                if yy == 0:
                                    if xx != 0:
                                        if xx == 4:
                                            pass
                                        else:
                                            ditu[y][x]['方块'] = '木箱'
                                else:
                                    # !! GOTO @2260 (already emitted above)
                                    pass
                    if yq == 4:
                        for yy in range(2):
                            y = 12 + yy
                            for xx in range(6):
                                if xx == 5 and yy == 0:
                                    pass
                                else:
                                    x = xx + lzx * 12 + 1
                                    ditu[y][x]['方块'] = '木箱'
                    if yq == 3:
                        for yy in range(2):
                            y = 12 + yy
                            for xx in range(6):
                                if xx == 5 and yy == 0:
                                    pass
                                else:
                                    x = 11 - xx + lzx * 12
                                    ditu[y][x]['方块'] = '木箱'
                    for xx in range(11):
                        x = xx + lzx * 12 + 1
                        if xx % 2 != 0:
                            continue
                        ditu[15][x]['里方块'] = '车轮'
                    ditu[14][lzx * 12]['方块'] = '车底'
                    ditu[13][lzx * 12]['里方块'] = '铁栅栏'
            else:
                if name == '沙城':
                    for yy in range(4):
                        if yy == 0:
                            fk = '沙板'
                        else:
                            fk = '沙石'
                        y = yy + 20
                        for x in range(len(ditu[0])):
                            ditu[y][x]['方块'] = fk
                    for yy in range(7):
                        x = 1 + yy
                        y = 19 - yy
                        if y < 16:
                            y = 16
                        if yy == 6:
                            y = 19
                        ditu[y][x]['方块'] = '沙板'
                        for yyy in range(20 - y):
                            ditu[y + yyy + 1][x]['方块'] = '沙石'
                    for yy in range(7):
                        x = len(ditu[0]) - 2 - yy
                        y = 19 - yy
                        if y < 16:
                            y = 16
                        if yy == 6:
                            y = 19
                        ditu[y][x]['方块'] = '沙板'
                        for yyy in range(20 - y):
                            ditu[y + yyy + 1][x]['方块'] = '沙石'
                    chux = 10
                    中楼 = False
                    while True:
                        chang = 随(5, 7)
                        if chang != 6:
                            break
                    if chux + chang >= len(ditu[0]) - 8:
                        chang = 5
                        if chux + chang < len(ditu[0]) - 8:
                            # goto @3050
                            pass
                        # goto @4260
                    zuo = 随(0, 1)
                    if zuo == 0:
                        you = 随(0, 1)
                    else:
                        you = 0
                    tizi = 0
                    if zuo == 1 or you == 1:
                        tizi = 1
                    if not 中楼 and chux > 27:
                        中楼 = True
                        tizi = 1
                    gao = 随(3, 5)
                    for ceng in range(随(1, 2)):
                        for yy in range(gao):
                            y = 20 - gao + yy - ceng * gao
                            for xx in range(chang):
                                x = chux + xx
                                if yy == 0:
                                    if xx == chang // 2 and ceng == 1:
                                        ditu[y][x]['方块'] = '沙刻'
                                    else:
                                        ditu[y][x]['方块'] = '沙砖'
                                else:
                                    if yy == 2 and xx > 0 and xx < chang - 1 and gao > 3:
                                        if tizi != 0:
                                            if ceng > 0:
                                                pass
                                            else:
                                                ditu[y][x]['里方块'] = '沙墙'
                                    else:
                                        # !! GOTO @3360 (already emitted above)
                                        pass
                                if ceng != 0:
                                    continue
                                if zuo == 1 and xx == 0:
                                    ditu[y][x]['方块'] = '沙砖'
                                if you == 1 and xx == chang - 1:
                                    ditu[y][x]['方块'] = '沙砖'
                                if not (tizi == 1 and xx == chang // 2):
                                    continue
                                ditu[y][x]['方块'] = '梯子块'
                                ditu[y][x]['里方块'] = '沙墙'
                    chux += chang + 随(1, 3)
                    while True:
                        chang = 随(5, 7)
                        if chang != 6:
                            break
                        # !! GOTO @2978 (already emitted above)
                    # !! GOTO @2988 (already emitted above)
                else:
                    if name not in 地图数据:
                        xditu = 读取('地图/新地图.json')
                    else:
                        xditu = c(地图数据[name])
                    if name == '家院':
                        fk = ['空', '石', '里-栅栏', '土', '草', '池砖', '墙砖', '屋瓦', '里-窗户', '里-屋瓦', '里-墙砖', '马路', '梯子块']
                    if name == '古堡':
                        fk = ['空', '石', '土', '草', '石砖', '里-石砖', '里-土', '里-石', '里-堡砖', '隔-石砖1', '', '']
                    if name == '大桥':
                        fk = ['空', '石', '土', '草', '桥砖', '里-石', '里-桥砖', '梯子块', '桥面', '', '', '']
                    if name == '要塞':
                        fk = ['空', '石', '土', '草', '砖1', '里-砖3', '里-窗户', '隔-砖3', '梯子块', '', '', '']
                    if name == '木船':
                        fk = ['空', '沙', '木板', '木头', '里-帆', '里-木板', '里-木头', '梯子块', '空', '', '', '']
                    if name == '小镇':
                        fk = ['空', '水泥', '泥砖', '泥砖', '里-泥砖', '木箱', '里-窗户', '', '', '', '']
                    if name == '遗迹':
                        fk = ['空', '石', '石砖', '石砖', '里-石砖', '堡砖', '里-堡砖', '草', '土', '', '']
                    if name == '绿洲':
                        fk = ['空', '沙石', '石', '桥砖', '里-桥砖', '草', '土', '隔-桥砖', '', '', '']
                    for y in range(len(xditu)):
                        for x in range(len(xditu[0])):
                            lzx = c(xditu[y][x])
                            tizi = False
                            if lzx < 0:
                                tizi = True
                                lzx = jdz(lzx)
                            name = c(fk[lzx])
                            if name[0] == '里':
                                namex = name.split('-')[1]
                                if namex == '石砖':
                                    if 随(1, 6) == 1:
                                        yq = 随(2, 3)
                                    else:
                                        yq = 1
                                    namex += str(yq)
                                ditu[y][x]['里方块'] = namex
                                if tizi:
                                    ditu[y][x]['方块'] = '梯子块'
                            else:
                                if name == '石砖':
                                    if 随(1, 6) == 1:
                                        yq = 随(2, 3)
                                    else:
                                        yq = 1
                                    name += str(yq)
                                if name[0] == '隔':
                                    ditu[y][x]['里方块'] = name.split('-')[1]
                                    if ditu[y][x]['里方块'] == '空':
                                        del ditu[y][x]['里方块']
                                else:
                                    ditu[y][x]['方块'] = name
    return ditu

def 多少阳光(name):
    if name == '火炬树桩' and '蓝火' in 秘籍:
        return 300
    if name == '高坚果' and '石果' in 秘籍:
        return 250
    if name == '大嘴花' and '龙蒺藜' in 秘籍:
        return 350
    if name == '大喷菇' and '雷霆' in 秘籍:
        return 150
    if name == '咖啡豆' and '咖啡' in 秘籍:
        return 50
    if name == '地刺':
        return 地刺阳光
    for lzx in 花费阳光:
        if name not in 花费阳光[lzx]:
            continue
        return lzx

def 显示植物(l):
    hb = ''
    if '黑白' in 植物[l]:
        hb = '-黑白'
    y = c(植物[l]['坐标'][0])
    x = c(植物[l]['坐标'][1])
    yy = y * 比
    xx = x * 比
    citoux = 0
    citouy = 0
    sinzhi = math.sin(math.pi * 2 * (植物[l]['根动画'] / 250)) * 10
    name = c(植物[l]['植物'])
    if name == '模仿者' and 植物[l]['模仿cd'] > 0:
        sinzhi = sinzhi * 5
    if name in 根茎叶植物:
        zi = '根茎叶'
        if name == '三叶草':
            zi = '三叶草-根'
        if name == '双子向日葵':
            zi = '双子根'
            citouy -= 比 * 0.3
            citoux -= 比 * 0.25
        if name in ('大嘴花', '龙蒺藜'):
            sinzhi = sinzhi / 2
            zi = '大嘴根'
            if name == '龙蒺藜':
                zi = '龙蒺藜根'
            citouy -= 比 * 0.6
            citoux -= 比 * 0.25
    else:
        if name in 投手植物:
            if 植物[l]['射'] > 100 and 植物[l]['射'] < 200:
                zi = name + '-投空'
            else:
                zi = name + '-投'
        else:
            if name == '香蒲':
                zi = '香蒲尾'
            else:
                if name == '火炬树桩':
                    name = '火炬树桩-秃'
                if name == '磁力菇' or name == '吸金磁':
                    if '睡觉' in 植物[l] and name == '磁力菇':
                        name = '磁力菇-睡觉'
                    if 植物[l]['吸'] > 0:
                        name += '-吸'
                if name == '玉米加农炮':
                    citouy -= 比 * 0.6
                    citoux -= 比 * 0.5
                if name in 大头:
                    citouy -= 比 * 0.5
                    citoux -= 比 * 0.25
                if name == '高坚果':
                    if 植物[l]['植物血'] <= 96:
                        name = '高坚果-小残'
                    if 植物[l]['植物血'] <= 48:
                        name = '高坚果-大残'
                if name == '南瓜头':
                    sinzhi = sinzhi / 2
                    if 植物[l]['植物血'] <= 48:
                        name = '南瓜头-小残'
                    if 植物[l]['植物血'] <= 24:
                        name = '南瓜头-大残'
                if name == '坚果':
                    if 植物[l]['植物血'] <= 48:
                        name = '坚果-小残'
                    if 植物[l]['植物血'] <= 24:
                        name = '坚果-大残'
                if name == '大蒜':
                    if 植物[l]['植物血'] <= 12:
                        name = '大蒜-小残'
                    if 植物[l]['植物血'] <= 6:
                        name = '大蒜-大残'
                zi = name
    if name == '海蘑菇' and '水兵' not in 秘籍:
        citouy -= 比 * 0.6
    if name == '缠绕海草':
        citouy += -比 * 0.8
    if name == '香蒲':
        citouy += -比 * 0.9
    gen = 图集[zi + hb]
    tou = 图集[name + hb]
    daxiao = 0
    if name == '阳光菇' and 植物[l]['长大'] < 200:
        daxiao = (200 - 植物[l]['长大']) / 200 * 比 / 2
        tou = 变图(tou, 比 - daxiao, 比 - daxiao)
    if name == '小喷菇' and '小喷' in 植物[l]:
        daxiao = -比 / 2 * (植物[l]['小喷'] / 15) ** 0.5
        tou = 变图(tou, 比 - daxiao, 比 - daxiao)
    if name == '忧郁蘑菇' and 植物[l]['射'] > 0 and 植物[l]['射'] < 50:
        dx = math.sin(math.pi * (植物[l]['射'] / 50)) * 比 * 0.15
        tou = 变图(tou, 比 + dx, 比 + dx)
        citoux -= dx / 2
        citouy -= dx
    toudushu = 0
    if name == '墓碑吞噬者':
        citouy += -比 * 2 / 3 + (植物[l]['滚蛋'] / 1000) ** 2 * 比 / 2
        if 植物[l]['滚蛋'] % 100 == 0 and '坟墓' in ditu[y][x] and '睡觉' not in 植物[l]:
            增粒子(ditu[y][x]['方块'] + str(ditu[y][x]['坟墓']), [x * 比 + 比 * 0.5, y * 比 + 比 * 0.5], 4)
    if name == '三叶草':
        toudushu = 植物[l]['消亡'] * 6 * 植物[l]['方向']
        sinzhi = 15
    if 植物[l]['方向'] == -1:
        gen = 反(gen)
        tou = 反(tou)
        sinzhi = -sinzhi
    if name == '樱桃炸弹' or name == '毁灭菇' or name == '火爆辣椒':
        daxiaox = (植物[l]['消亡'] / 200) ** 2 * 比
        tou = 变图(tou, 比 + daxiaox, 比 + daxiaox)
        citouy = -daxiaox + 比 * 0.1
        citoux = -daxiaox / 2
    if name == '裂荚射手':
        if 植物[l]['射'] > 0 and 植物[l]['射'] < 100:
            shedu = math.pi * (植物[l]['射'] / 100)
            shesin = (-2 / math.pi * shedu + 2) * math.sin(shedu)
            citoux += -shesin * 比 * 0.15 * 植物[l]['方向']
            citouy += shesin * 比 * 0.05
            toudushu = -shesin * 40 * 植物[l]['方向']
        if 植物[l]['副射'] > 0 and 植物[l]['副射'] < 100:
            shedu = math.pi * (植物[l]['副射'] / 100)
            shesin = (-2 / math.pi * shedu + 2) * math.sin(shedu)
            citoux += -shesin * 比 * 0.15 * -植物[l]['方向']
            citouy += shesin * 比 * 0.05
            toudushu = -shesin * 40 * -植物[l]['方向']
    if (name == '豌豆射手' or name == '海蘑菇' or name == '机枪射手' or name == '寒冰射手' or name == '双发射手' or name == '小喷菇' or name == '胆小菇' or name == '仙人掌' or name == '杨桃') and 植物[l]['射'] > 0 and 植物[l]['射'] < 100:
        shedu = math.pi * (植物[l]['射'] / 100)
        shesin = (-2 / math.pi * shedu + 2) * math.sin(shedu)
        citoux += -shesin * 比 * 0.15 * 植物[l]['方向']
        citouy += shesin * 比 * 0.05
        toudushu = -shesin * 40 * 植物[l]['方向']
    if (name == '地刺' or name == '地刺王') and 植物[l]['射'] > 0 and 植物[l]['射'] < 100:
        shedu = math.pi * 2 * (植物[l]['射'] / 100)
        citouy = math.sin(shedu) * 比 * 0.1
    if (name == '大喷菇' or name == '雷蘑菇') and 植物[l]['射'] > 0 and 植物[l]['射'] < 200:
        she = c(植物[l]['射'])
        if she >= 150:
            she = 200 - she
        if she > 50:
            she = 50
        shedu = math.pi * (she / 100)
        shesin = (-2 / math.pi * shedu + 2) * math.sin(shedu)
        citoux = shesin * 比 * 0.15 * 植物[l]['方向']
        citouy = -shesin * 比 * 0.05
        toudushu = shesin * 20 * 植物[l]['方向']
    if name == '胆小菇' and 植物[l]['胆小'] > 0:
        citouy += 植物[l]['胆小'] / 100 * 比 / 2
    genx = xx
    geny = yy + 比 * 0.3
    if name in ('大嘴花', '龙蒺藜'):
        genx -= 比 * 0.25
        geny -= 比 * 0.75
    toux = xx + citoux + daxiao / 2
    touy = yy - 比 * 0.05 + citouy + daxiao
    d = str(y + 1) + '-' + str(x)
    if d in 花盆顶:
        touy -= 花盆顶[d]
        geny -= 花盆顶[d]
    if ditu[y + 1][x]['方块'] == '水' or ditu[y][x]['方块'] == '水':
        touy += shui
        geny += shui
    if '爆了' in 植物[l] and 植物[l]['爆了'] > 0:
        touy -= math.sin(math.pi * (植物[l]['爆了'] / 250)) * 比 * 0.1
    dazui = False
    if name == '土豆地雷':
        touy += 比 * 0.5 - 植物[l]['出来'] / 200 * 比 * 0.2
        if 植物[l]['出来'] and 植物[l]['闪'] // 150 % 2 == 0:
            if 植物[l]['方向'] == -1:
                tou = 反(图集['土豆地雷-亮' + hb])
            else:
                tou = 图集['土豆地雷-亮' + hb]
    else:
        if name in 根茎叶植物:
            if name in ('大嘴花', '龙蒺藜') and (植物[l]['射'] > 0 or 植物[l]['吃'] > 0):
                dazui = True
                sbtou = 图集[name + '-上半' + hb]
                xbtou = 图集[name + '-下半' + hb]
                if 植物[l]['方向'] == -1:
                    sbtou = 反(sbtou)
                    xbtou = 反(xbtou)
                if 植物[l]['射'] > 0 and 植物[l]['射'] < 150:
                    toux += math.sin(math.pi * (植物[l]['射'] / 150)) * 比 * 植物[l]['方向']
                    touy -= math.sin(math.pi * (植物[l]['射'] / 150)) * 比 * 0.3
                    if 植物[l]['射'] > 60:
                        if 植物[l]['射'] > 60 and 植物[l]['射'] < 90:
                            toudushu = -25 * 植物[l]['方向']
                        else:
                            lzx = 植物[l]['射'] - 30
                            toudushu = math.sin(math.pi * 2 * (lzx / 120)) * 30 * 植物[l]['方向']
                            if 植物[l]['吃'] > 0:
                                if 植物[l]['方向'] == 1 and toudushu > 15:
                                    toudushu = 15
                                if 植物[l]['方向'] == -1 and toudushu < -15:
                                    toudushu = -15
                                    # !! GOTO @3318 (already emitted above)
                    else:
                        toudushu = math.sin(math.pi * 2 * (植物[l]['射'] / 120)) * 70 * 植物[l]['方向']
                    sinzhi = math.sin(math.pi * (植物[l]['射'] / 150)) * 60 * 植物[l]['方向']
                    genx += math.sin(math.pi * (植物[l]['射'] / 150)) * 比 * 植物[l]['方向']
            toux += sinzhi * 比 * 0.005
            touy += jdz(sinzhi) * 比 * 0.01
            旋转摄像显示(gen, (genx, geny + jdz(sinzhi) * 比 * 0.005), sinzhi)
        else:
            toux += sinzhi / 4 * 比 * 0.005
            touy += jdz(sinzhi) / 4 * 比 * 0.01 + 比 * 0.15
            toudushu += sinzhi / 4
            if name in 投手植物:
                tousin = 0
                if 植物[l]['射'] > 0 and 植物[l]['射'] < 200:
                    shedu = math.pi * 2 * (植物[l]['射'] / 200)
                    shesin = math.sin(shedu)
                    citoux = -shesin * 比 * 0.15 * 植物[l]['方向']
                    citouy = shesin * 比 * 0.05
                    toudushu = -shesin * 40 * 植物[l]['方向']
                    toudu = math.pi * 2 * (植物[l]['射'] / 200)
                    tousin = -math.sin(toudu) * 120 * 植物[l]['方向']
                旋转摄像显示(gen, (genx - 比 * 0.5 - 植物[l]['方向'] * 比 * 0.2 + citoux * 2, geny + citouy - 比 * 0.9), tousin + sinzhi)
            if name == '香蒲':
                tousin = 0
                if 植物[l]['射'] > 0 and 植物[l]['射'] < 100:
                    shedu = math.pi * 2 * (植物[l]['射'] / 100)
                    shesin = math.sin(shedu)
                    citoux = -shesin * 比 * 0.15 * 植物[l]['方向']
                    toudushu = -shesin * 20 * 植物[l]['方向']
                    toudu = math.pi * 2 * (植物[l]['射'] / 100)
                    tousin = -math.sin(toudu) * 60 * 植物[l]['方向']
                旋转摄像显示(gen, (genx - 植物[l]['方向'] * 比 * 0.15 + citoux * 2, geny + citouy - 比 * 0.25), tousin + sinzhi)
    if name == '火炬树桩-秃' and ditu[y][x]['方块'] != '水':
        zi = ''
        if '蓝火' in 秘籍:
            zi = '蓝'
        shu = 植物[l]['根动画'] // 25 % 3 + 1
        if 植物[l]['方向'] == -1:
            旋转摄像显示(反(图集[zi + '火炬' + str(shu)]), (toux, touy), toudushu)
        else:
            旋转摄像显示(图集[zi + '火炬' + str(shu)], (toux, touy), toudushu)
    if name == '玉米加农炮':
        toudushu -= math.sin(math.pi * (植物[l]['发射动画'] / 500)) * 90 * 植物[l]['方向']
    if name == '玉米加农炮' and (植物[l]['发射动画'] > 0 and 植物[l]['发射动画'] < 250 or 植物[l]['发射cd'] <= 100):
        tu = 图集['玉米炮']
        if 植物[l]['方向'] == -1:
            tu = 反(tu)
        if 植物[l]['发射动画'] > 0:
            xxxx = -math.sin(math.pi * (植物[l]['发射动画'] / 500)) * 比 * 0.4
            yyyy = -math.sin(math.pi * (植物[l]['发射动画'] / 500)) * 比 * 0.5
        else:
            xxxx = -(植物[l]['发射cd'] / 100) * 比 * 0.3
            yyyy = 0
        旋转摄像显示(tu, (toux + 植物[l]['方向'] * 比 * 0.3 + xxxx * 植物[l]['方向'], touy - 比 * 0.1 + yyyy), toudushu)
        if 植物[l]['发射闪闪'] < 50:
            图集['玉米炮-受伤'].set_alpha(math.sin(math.pi * (植物[l]['发射闪闪'] / 50)) * 255)
            sc = 图集['玉米炮-受伤']
            if 植物[l]['方向'] == -1:
                sc = 反(sc)
            旋转摄像显示(sc, (toux + 植物[l]['方向'] * 比 * 0.3 + xxxx * 植物[l]['方向'], touy - 比 * 0.1 + yyyy), toudushu)
    if dazui:
        xxxx = 0
        yyyy = 0
        if 植物[l]['吃'] > 0:
            toudushu = -15 * 植物[l]['方向']
            if 植物[l]['吃'] < 200:
                toudushu += math.sin(math.pi * ((200 - 植物[l]['吃']) / 400)) * 15 * 植物[l]['方向']
            else:
                xxxx = math.cos(math.pi * 2 * (植物[l]['吃'] / 200)) * 比 * 0.08
                yyyy = math.sin(math.pi * 2 * (植物[l]['吃'] / 200)) * 比 * 0.08 - 比 * 0.15
        旋转摄像显示(xbtou, (toux + xxxx, touy + yyyy), toudushu)
        旋转摄像显示(sbtou, (toux + xxxx / 4, touy + yyyy / 4), -toudushu)
        if 植物[l]['受伤'] > 0:
            tou = 图集[name + '-下半-受伤']
            if 植物[l]['方向'] == -1:
                tou = 反(tou)
            图集[name + '-下半-受伤'].set_alpha(math.sin(math.pi * (植物[l]['受伤'] / 50)) * 150)
            旋转摄像显示(tou, (toux + xxxx, touy + yyyy), toudushu)
            tou = 图集[name + '-上半-受伤']
            if 植物[l]['方向'] == -1:
                tou = 反(tou)
            图集[name + '-上半-受伤'].set_alpha(math.sin(math.pi * (植物[l]['受伤'] / 50)) * 150)
            旋转摄像显示(tou, (toux + xxxx / 4, touy + yyyy / 4), -toudushu)
        toux += xxxx
        touy += yyyy
    else:
        旋转摄像显示(tou, (toux, touy), toudushu)
    if name == '玉米加农炮':
        tu = 图集['玉米加农炮-车' + hb]
        if 植物[l]['方向'] == -1:
            tu = 反(tu)
        摄像显示(tu, (toux, touy))
    if name == '石果子' and 植物[l]['消亡'] > 4000:
        tou = 图集[name + '-黑']
        if 植物[l]['方向'] == -1:
            tou = 反(tou)
        图集[name + '-黑'].set_alpha(((植物[l]['消亡'] - 4000) / 1000) ** 5 * 255)
        if toudushu == 0:
            摄像显示(tou, (toux, touy))
        else:
            旋转摄像显示(tou, (toux, touy), toudushu)
    if not (植物[l]['受伤'] <= 0 or dazui):
        tou = 图集[name + '-受伤']
        if 植物[l]['方向'] == -1:
            tou = 反(tou)
        if daxiao != 0:
            tou = 变图(tou, 比 - daxiao, 比 - daxiao)
        图集[name + '-受伤'].set_alpha(math.sin(math.pi * (植物[l]['受伤'] / 50)) * 150)
        if toudushu == 0:
            摄像显示(tou, (toux, touy))
        else:
            旋转摄像显示(tou, (toux, touy), toudushu)
    if name == '萝卜伞' and 植物[l]['射'] > 0 and 植物[l]['射'] < 100:
        dx = math.sin(math.pi * (植物[l]['射'] / 100)) * 比 * 3
        sc = 图集['叶子伞' + hb]
        if 植物[l]['方向'] == -1:
            sc = 反(sc)
        sc = 变图(sc, dx + 比 * 1.5, dx + 比 * 1.5)
        摄像显示(sc, (toux - dx / 2, touy - dx * 2 / 3))
    if name == '向日葵' and 植物[l]['爆了'] > 0:
        图集['向日葵-生产'].set_alpha(math.sin(math.pi * (植物[l]['爆了'] / 250)) * 255)
        sc = 图集['向日葵-生产']
        if 植物[l]['方向'] == -1:
            sc = 反(sc)
        摄像显示(sc, (toux, touy))
    if name == '路灯花' and 植物[l]['爆了'] > 0:
        图集['路灯花-光疗'].set_alpha(math.sin(math.pi * (植物[l]['爆了'] / 250)) * 255)
        sc = 图集['路灯花-光疗']
        if 植物[l]['方向'] == -1:
            sc = 反(sc)
        摄像显示(sc, (toux, touy))
        ui图集['发光1'].set_alpha(math.sin(math.pi * (植物[l]['爆了'] / 250)) * 255)
        摄像显示(ui图集['发光1'], (toux - 比 * 2, touy - 比 * 2))
    if name == '双子向日葵' and 植物[l]['爆了'] > 0:
        图集['双子向日葵-生产'].set_alpha(math.sin(math.pi * (植物[l]['爆了'] / 250)) * 255)
        sc = 图集['双子向日葵-生产']
        if 植物[l]['方向'] == -1:
            sc = 反(sc)
        摄像显示(sc, (toux, touy))
    if name == '阳光菇' and 植物[l]['爆了'] > 0:
        图集['阳光菇-生产'].set_alpha(math.sin(math.pi * (植物[l]['爆了'] / 250)) * 255)
        sc = 图集['阳光菇-生产']
        if 植物[l]['长大'] < 200:
            sc = 变图(sc, 比 - daxiao, 比 - daxiao)
        if 植物[l]['方向'] == -1:
            sc = 反(sc)
        旋转摄像显示(sc, (toux, touy), toudushu)
    if name == '金盏花' and 植物[l]['爆了'] > 0:
        图集['金盏花-受伤'].set_alpha(math.sin(math.pi * (植物[l]['爆了'] / 250)) * 255)
        sc = 图集['金盏花-受伤']
        if 植物[l]['方向'] == -1:
            sc = 反(sc)
        摄像显示(sc, (toux, touy))
    if l == 目标植物 and 模式 == '我是僵尸':
        摄像显示(图集['小脑子'], (toux + 比 * 0.25, touy))

def 显示牌(name, zuobiao):
    if name in 高级植物:
        显示(ui图集['高级植物卡'], zuobiao)
    else:
        显示(ui图集['植物卡'], zuobiao)
    显示牌中植物(name, zuobiao)
    lzx = 多少阳光(name)
    lzxx = 0
    if len(str(lzx)) == 1:
        lzxx = 比 * 0.2
    if len(str(lzx)) == 2:
        lzxx = 比 * 0.1
    if len(str(lzx)) == 4:
        lzxx = -比 * 0.1
    显小字(str(lzx), [zuobiao[0] + lzxx + 比 * 0.2, zuobiao[1] + 比 * 0.95], 黑色)

def 显示牌中植物(name, zuobiao):
    yy = 0
    xx = 0
    if name in 根茎叶植物:
        yyy = 0
        namex = '根茎叶'
        if name == '三叶草':
            namex = '三叶草-根'
        if name == '龙蒺藜':
            namex = '龙蒺藜根'
            yyy -= 比 * 0.2
        if name == '大嘴花':
            namex = '大嘴根'
            if '龙蒺藜' in 秘籍:
                namex = '龙蒺藜根'
            yyy -= 比 * 0.2
        if name == '双子向日葵':
            namex = '双子根'
            xx = -比 * 0.7 / 4
            yy = -比 * 0.1
            yyy = 比 * 0.05
        显示(ui图集[namex], [zuobiao[0] + 比 * 0.15, zuobiao[1] + 比 * 0.4 + yyy])
    else:
        if name in 投手植物:
            裁剪显示(ui图集[name + '-投'], [zuobiao[0] + 比 * 0.15 - 比 * 0.1, zuobiao[1] + 比 * 0.15], [int(比 * 0.4), int(比 * 0.4), int(比), int(比)])
            yy = 比 * 0.1
        else:
            yy = 比 * 0.1
    if name in 参战僵尸图:
        xx = -比 * 0.05
        yy = 0
    if name in 大头:
        xx = -比 * 0.05
        yy = 0
        if name == '大嘴花':
            yy -= 比 * 0.05
    if name == '玉米加农炮':
        xx = -比 * 0.7 / 4 - 比 * 0.05
        yy = 0
        显示(ui图集['玉米炮'], [zuobiao[0] + 比 * 0.3 + xx, zuobiao[1] + 比 * 0.1 + yy])
    if name == '香蒲':
        显示(ui图集['香蒲尾'], [zuobiao[0] + 比 * 0.1 + xx, zuobiao[1] + 比 * 0.15 + yy])
    if name == '火炬树桩' and '蓝火' in 秘籍:
        name = '蓝火树桩'
    if name == '高坚果' and '石果' in 秘籍:
        name = '石果子'
    if name == '大嘴花' and '龙蒺藜' in 秘籍:
        name = '龙蒺藜'
    if name == '大喷菇' and '雷霆' in 秘籍:
        name = '雷蘑菇'
    显示(ui图集[name], [zuobiao[0] + 比 * 0.15 + xx, zuobiao[1] + 比 * 0.15 + yy])
    if name == '玉米加农炮':
        显示(ui图集['玉米加农炮-车'], [zuobiao[0] + 比 * 0.15 + xx, zuobiao[1] + 比 * 0.15 + yy])

def 选块归位():
    平分 = 比 * 3
    n = 0
    for l in range(len(选块)):
        if 选块[l]['淘汰']:
            continue
        n += 1
    nn = 0
    for l in range(len(选块)):
        if 选块[l]['淘汰']:
            选块[l]['目标'][1] = -比 * 6
            选块[l]['出点'][1] = c(选块[l]['位'][1])
        else:
            选块[l]['目标'][1] = 比 * 3
            选块[l]['目标'][0] = 总宽 // 2 - n * 平分 // 2 + 平分 * nn + 比 // 4
            选块[l]['出点'][0] = c(选块[l]['目标'][0])
            nn += 1
        选块[l]['时'] = 0

def 新选块(name):
    选块.append({})
    选块[-1]['出点'] = [0, 总高]
    选块[-1]['位'] = [0, 0]
    选块[-1]['目标'] = [0, 比 * 2]
    选块[-1]['时'] = 0
    选块[-1]['淘汰'] = False
    选块[-1]['名'] = name
    if name == '作者' or name == '空':
        选块[-1]['别选'] = 0
    if name in ui图集:
        选块[-1]['图'] = name
    else:
        选块[-1]['图'] = '选块'

def 反(canshu):
    return pygame.transform.flip(canshu, True, False)

def 不封顶出界(y, x):
    if x < 0 or y > len(ditu) - 1 or x > len(ditu[0]) - 1:
        return True
    return False

def 实体出界(y, x):
    if x < -2 or y > len(ditu) - 1 or x > len(ditu[0]) + 1:
        return True
    return False

def 出界(y, x):
    if y < 0 or x < 0 or y > len(ditu) - 1 or x > len(ditu[0]) - 1:
        return True
    return False

def 按时归位(chu, zhong, zongsj, sj):
    if sj <= 0:
        return c(chu)
    if sj >= zongsj:
        return c(zhong)
    xian = c(chu)
    for lzx in range(2):
        daota = zhong[lzx] - chu[lzx]
        a = 4 * daota / zongsj ** 2
        vmax = a * zongsj / 2
        if sj < zongsj // 2:
            x = vmax / 2 * sj
        else:
            sjj = sj - zongsj // 2
            v = vmax - a * sjj
            x = daota / 2 + (v + vmax) / 2 * sjj
        xian[lzx] += x
    return c(xian)

def 单归位(jiantou, yj):
    l = 0
    z = 1
    if jiantou[z] > 0:
        jiantou[z] -= yj
    else:
        if jiantou[z] < 0:
            jiantou[z] += yj
    x = jiantou[l] - jiantou[l + 2]
    t = jiantou[z] / yj
    if x < 0:
        if x < -jiantou[z] / 2 * t:
            jiantou[z] += yj * 2
    else:
        if x > 0 and x > jiantou[z] / 2 * t:
            jiantou[z] -= yj * 2
    if jdz(jiantou[l] + jiantou[z] - jiantou[l]) < jdz(jiantou[l] - jiantou[l + 2]):
        jiantou[l] += jiantou[z]
    else:
        jiantou[l] = c(jiantou[l + 2])
    jiantou[l] = int(jiantou[l])

def 归位(jiantou, yj):
    for l in range(2):
        z = l + 2
        if jiantou[z] > 0:
            jiantou[z] -= yj
        else:
            if jiantou[z] < 0:
                jiantou[z] += yj
        x = jiantou[l] - jiantou[l + 4]
        t = jiantou[z] / yj
        if x < 0:
            if x < -jiantou[z] / 2 * t:
                jiantou[z] += yj * 2
        else:
            if x > 0 and x > jiantou[z] / 2 * t:
                jiantou[z] -= yj * 2
        if jdz(jiantou[l] + jiantou[z] - jiantou[l]) < jdz(jiantou[l] - jiantou[l + 4]):
            jiantou[l] += jiantou[z]
            continue
        jiantou[l] = c(jiantou[l + 4])

def 保存(weizhi, dongxi):
    # ?? SETUP_FINALLY 40
    cd = open(weizhi, 'w')
    cd.write(json.dumps(dongxi))
    cd.close()
    # ?? POP_BLOCK None

def 播BGM(weizhi, 一遍):
    # ?? SETUP_FINALLY 74
    if 设置['音乐']:
        pygame.mixer.music.load(weizhi)
        if 一遍:
            pygame.mixer.music.play()
        else:
            pygame.mixer.music.play(-1)
        pygame.mixer.music.set_volume(0.4)
    # ?? POP_BLOCK None

def 加载音(weizhi):
    # ?? SETUP_FINALLY 16
    # ?? POP_BLOCK None
    return pygame.mixer.Sound(weizhi)

def 变图(lzx, 横, 竖):
    try:
        return pygame.transform.scale(lzx, (横, 竖)).convert_alpha()
    except:
        pass

def 加载原图(地址):
    try:
        return pygame.image.load(地址).convert_alpha()
    except:
        return pygame.image.load('图片/黑.png').convert_alpha()

def 加载图(地址, 横, 竖):
    try:
        return pygame.transform.scale(pygame.image.load(地址), (int(横), int(竖))).convert_alpha()
    except:
        return pygame.transform.scale(pygame.image.load('图片/黑.png'), (int(横), int(竖))).convert_alpha()

def 抖(fudu):
    return 随(-fudu, fudu) * bi * 10

def 渐亮():
    global 渐
    if 渐 > 0:
        if 补帧 == 0:
            j = 渐
            if j > 255:
                j = 255
            黑.set_alpha(j)
            显示(黑, [0, 0])
        渐 -= 10
        if 渐 < 0:
            渐 = 0

def 关游戏():
    global 大关
    大关 = True

def c(cs):
    return copy.deepcopy(cs)

def 随(小, 大):
    return random.randint(int(小), int(大))

def jdz(shu):
    return abs(shu)

def 裁剪显示(图片, 坐标, cj):
    # ?? SETUP_FINALLY 40
    if 补帧 == 0:
        screen.blit(图片, (坐标[0], 坐标[1]), cj)
    # ?? POP_BLOCK None

def 显示(图片, 坐标):
    if 补帧 == 0:
        screen.blit(图片, (坐标[0], 坐标[1]))

def 不显(tu, zuobiao):
    w, h = tu.get_size()
    if zuobiao[0] < 摄像机[0] - w - 比 or zuobiao[0] > 摄像机[0] + 总宽 + w or zuobiao[1] < 摄像机[1] - h - 比 or zuobiao[1] > 摄像机[1] + 总高 + h:
        return True
    return False

def 摄像裁剪显示(图片, 坐标, cj):
    if 补帧 == 0:
        screen.blit(图片, (坐标[0] - 摄像机[0] + 抖屏[1], 坐标[1] - 摄像机[1] + 抖屏[2]), cj)

def 摄像显示(图片, 坐标):
    if not (补帧 != 0 or 不显(图片, 坐标)):
        screen.blit(图片, (坐标[0] - 摄像机[0] + 抖屏[1], 坐标[1] - 摄像机[1] + 抖屏[2]))

def 画线(se, chu, mo):
    if 补帧 == 0:
        pygame.draw.line(screen, se, [chu[0], chu[1]], [mo[0], mo[1]], xianbi)

def 黑边显示(hei, 坐标):
    if 补帧 == 0:
        xx = 坐标[0] - 摄像机[0] + 抖屏[1]
        yy = 坐标[1] - 摄像机[1] + 抖屏[2]
        mox = xx
        moy = yy
        if hei == 0:
            mox += 比
        if hei == 1:
            moy += 比
            yy += 比
            mox += 比
        if hei == 2:
            moy += 比
        if hei == 3:
            xx += 比
            mox += 比
            moy += 比
        画线((0, 0, 0), [xx, yy], [mox, moy])

def 显小字(zi, zuobiao, se):
    if 补帧 == 0:
        for haozi in range(9):
            screen.blit(小font.render(zi, True, (0, 0, 0)), (zuobiao[0] + haozi % 3, zuobiao[1] + haozi // 3))
        screen.blit(小font.render(zi, True, se), (zuobiao[0] + 1, zuobiao[1] + 1))

def 显字(zi, zuobiao, se):
    if 补帧 == 0:
        for haozi in range(9):
            screen.blit(font.render(zi, True, (0, 0, 0)), (zuobiao[0] + haozi % 3, zuobiao[1] + haozi // 3))
        screen.blit(font.render(zi, True, se), (zuobiao[0] + 1, zuobiao[1] + 1))

def 走流程():
    global job, shangtime, 保底画面, 补帧
    渐亮()
    if 补帧 == 0:
        fpss.tick_busy_loop(fps)
    pygame.display.update()
    job -= 1
    jia = int((time.time() - shangtime) // 0.004)
    shangtime += jia * 0.004
    job += jia
    if job > 0:
        if job > 10:
            job = 10
        保底画面 += 1
        if 保底画面 == 5:
            补帧 = 0
            保底画面 = 0
        else:
            补帧 = job
    else:
        补帧 = 0
        保底画面 = 0

def 沉浸播音(name, zuobiao):
    if 设置['音效']:
        juli = ((zuobiao[0] - 玩家位置[0]) ** 2 + (zuobiao[1] - 玩家位置[1]) ** 2) ** 0.5
        daxiao = (比 * 36 - juli) / (比 * 36)
        if name == '入水':
            daxiao = daxiao / 2
        if name[0] == '吃':
            daxiao = daxiao / 4
        if daxiao <= 0:
            pass
        else:
            # ?? SETUP_FINALLY 186
            channel = 音效[name].play()
            if zuobiao[0] < 玩家位置[0]:
                channel.set_volume(daxiao, daxiao / 4)
            else:
                channel.set_volume(daxiao / 4, daxiao)
            # ?? POP_BLOCK None

def 播音(name):
    # ?? SETUP_FINALLY 26
    if 设置['音效']:
        音效[name].play()
    # ?? POP_BLOCK None

def 停音(name):
    # ?? SETUP_FINALLY 18
    音效[name].stop()
    # ?? POP_BLOCK None

def 渐黑():
    global 渐
    渐 = 0
    while True:
        渐 += 20
        走流程()
        if 渐 >= 250:
            break

def 数加密(shu):
    return shu * -17 + 2413

def 数解密(shu):
    shu -= 2413
    if shu % 17 != 0:
        return 0
    return int(shu // -17)

def 渐变换色(surface, se):
    # ?? SETUP_FINALLY 18
    w, h = surface.get_size()
    # ?? POP_BLOCK None
    for x in range(w):
        for y in range(h):
            a = surface.get_at((x, y))
            if a[3] <= 100:
                continue
            jb = (x - w // 2 + y - h // 2) // 2
            see = [se[0] + jb, se[1] + jb, se[2] + jb]
            for lzx in range(3):
                if see[lzx] < 0:
                    see[lzx] = 0
                    continue
                if see[lzx] <= 255:
                    continue
                see[lzx] = 255
            surface.set_at((x, y), pygame.Color(see[0], see[1], see[2], 255))
    return surface

def 不纯换色(surface, se):
    # ?? SETUP_FINALLY 18
    w, h = surface.get_size()
    # ?? POP_BLOCK None
    for x in range(w):
        for y in range(h):
            a = surface.get_at((x, y))
            if not ((a[0] > 0 or a[1] > 0 or a[2] > 0) and a[3] > 100):
                continue
            surface.set_at((x, y), pygame.Color(se[0], se[1], se[2], 255))
    return surface

def 纯换色(surface, se):
    # ?? SETUP_FINALLY 18
    w, h = surface.get_size()
    # ?? POP_BLOCK None
    for x in range(w):
        for y in range(h):
            a = surface.get_at((x, y))
            if a[3] <= 100:
                continue
            surface.set_at((x, y), pygame.Color(se[0], se[1], se[2], 255))
    return surface

def 换蓝色(surface):
    # ?? SETUP_FINALLY 18
    w, h = surface.get_size()
    # ?? POP_BLOCK None
    for x in range(w):
        for y in range(h):
            a = surface.get_at((x, y))
            if a[3] <= 100:
                continue
            surface.set_at((x, y), pygame.Color(a[2], a[1], a[0], a[3]))
    return surface

def 换金色(surface):
    # ?? SETUP_FINALLY 18
    w, h = surface.get_size()
    # ?? POP_BLOCK None
    for x in range(w):
        for y in range(h):
            a = surface.get_at((x, y))
            if not ((a[0] > 0 or a[1] > 0 or a[2] > 0) and a[3] > 100):
                continue
            bb = (a[1] + a[0]) // 2 + 80
            if bb > 255:
                bb = 255
            surface.set_at((x, y), pygame.Color(bb, bb, 0, a[3]))
    return surface

def 换黑白(surface):
    # ?? SETUP_FINALLY 18
    w, h = surface.get_size()
    # ?? POP_BLOCK None
    for x in range(w):
        for y in range(h):
            a = surface.get_at((x, y))
            if not (a[0] > 0 or a[1] > 0 or a[2] > 0):
                continue
            se = (a[0] + a[1] + a[2]) // 3 + 60
            if se > 255:
                se = 255
            surface.set_at((x, y), pygame.Color(se, se, se, a[3]))
    return surface

def 加载拟人图(l):
    拟人图集[l] = 加载图('图片/拟人-' + l + '.png', 比 * 5, 比 * 5)
    拟人图集[l + '-黑'] = 变图(纯换色(加载原图('图片/拟人-' + l + '.png'), 纯黑色), 比 * 5, 比 * 5)
    for lzx in 特色:
        if l not in 特色[lzx]:
            continue
        ts = c(特色[lzx][0])
        break
    拟人图集[l + '-特色'] = 变图(渐变换色(加载原图('图片/拟人-' + l + '.png'), ts), 比 * 5, 比 * 5)

def 加载游戏():
    global 比, xianbi, 行距, bi, plk, font, 小font, 背景图集, ui图集, 拟人图集, 图集, 近景图集, 黑, 白, 黑背景, 主界面近景
    比 = 总宽 // 20
    xianbi = int(比 / 17)
    行距 = 比 * 2 // 3
    bi = 比 / 810
    plk = 比 / 10000
    ziti = 'SimSun'
    font = pygame.font.SysFont(ziti, int(行距))
    小font = pygame.font.SysFont(ziti, int(行距) // 2)
    背景图集 = {}
    for l in ('商店',):
        背景图集[l] = 加载图('图片/' + l + '.png', 总宽, 总高)
    for l in ('主界面',):
        背景图集[l] = 加载图('图片/' + l + '.png', 比 * 3, 比 * 3)
    ui图集 = {}
    for l in ('新游戏', '花园', '继续游戏', '设置', '声明', '选块', '暗淡选块', '离开', '正常模式', '极难模式', '末日模式', '抽奖模式', '无尽模式', '我是僵尸'):
        ui图集[l] = 加载图('图片/' + l + '.png', 比 * 2.5, 比 * 5)
    for l in ('阳光板', '卡槽', '植物卡', '高级植物卡', '植物卡黑', '卡槽卡', '作战卡', '阳光卡', '秘籍', '选卡'):
        ui图集[l] = 加载图('图片/' + l + '.png', 比 * 1.5, 比 * 1.5)
    ui图集['卡亮'] = 变图(纯换色(加载原图('图片/植物卡黑.png'), 白色), 比 * 1.5, 比 * 1.5)
    ui图集['卡亮'].set_alpha(150)
    for l in ('发光1', '发光2', '发光3'):
        ui图集[l] = 加载图('图片/' + l + '.png', 比 * 5, 比 * 5)
    for l in ('铲子', '铲子槽', '轰炸'):
        ui图集[l] = 加载图('图片/' + l + '.png', 比, 比)
    ui图集['植物卡黑'].set_alpha(100)
    ui图集['按钮'] = 加载图('图片/按钮.png', 比 * 2, 比 * 2)
    ui图集['暂停'] = 加载图('图片/暂停.png', 比 * 4, 比 * 4)
    for l in ('开始干', '开始干-选中', '走啦', '走啦-选中', '返回菜单', '返回菜单-选中'):
        ui图集[l] = 加载图('图片/' + l + '.png', 比 * 3, 比)
    for l in ('旗帜', '旗帜杆', '尸首'):
        ui图集[l] = 加载图('图片/' + l + '.png', 比 / 2, 比 / 2)
    for l in ('进度条', '进度条框', '红进度条'):
        ui图集[l] = 加载图('图片/' + l + '.png', 比 * 7 / 2, 比 / 2)
    for l in ('准备1', '准备2', '准备3', '聊天框'):
        ui图集[l] = 加载图('图片/' + l + '.png', 比 * 4, 比 * 2)
    ui图集['大聊天框'] = 加载图('图片/大聊天框.png', 比 * 6, 比 * 4)
    for l in ('最后一波',):
        ui图集[l] = 加载图('图片/' + l + '.png', 比 * 8, 比 * 2)
    for l in 所有植物 + 植物补充:
        ui图集[l] = 加载图('图片/' + l + '.png', 比 * 0.7, 比 * 0.7)
    ui图集['双子向日葵'] = 加载图('图片/双子向日葵.png', 比, 比)
    ui图集['玉米加农炮'] = 加载图('图片/玉米加农炮.png', 比, 比)
    ui图集['玉米加农炮-车'] = 加载图('图片/玉米加农炮-车.png', 比, 比)
    ui图集['玉米炮'] = 加载图('图片/玉米炮.png', 比, 比)
    for l in 大头 + ['大嘴根', '龙蒺藜根']:
        ui图集[l] = 加载图('图片/' + l + '.png', 比 * 0.8, 比 * 0.8)
    for l in 参战僵尸图 + ['旗帜僵尸', '气球', '小鬼僵尸'] + boss:
        ui图集[l] = 加载图('图片/' + l + '.png', 比 * 0.8, 比 * 0.8)
    for l in 投手植物:
        ui图集[l + '-投'] = 加载图('图片/' + l + '-投.png', 比 * 1.4, 比 * 1.4)
    ui图集['选卡板'] = 加载图('图片/选卡板.png', 比 * 8.6, 比 * 8.55)
    拟人图集 = {}
    图集 = {}
    for l in ('金杯', '银杯'):
        ui图集[l] = 加载图('图片/' + l + '.png', 比 * 2, 比 * 2)
    for l in 皮肤:
        图集[l] = 加载图('图片/' + l + '.png', 比 * 2, 比 * 2)
        图集[l + '-受伤'] = 变图(纯换色(加载原图('图片/' + l + '.png'), 红色), 比 * 2, 比 * 2)
    for l in 防具:
        图集[l] = 加载图('图片/' + l + '.png', 比 * 2, 比 * 2)
        图集[l + '-受伤'] = 变图(纯换色(加载原图('图片/' + l + '.png'), 纯白色), 比 * 2, 比 * 2)
        图集[l + '-冰冻'] = 变图(不纯换色(加载原图('图片/' + l + '.png'), 蓝色), 比 * 2, 比 * 2)
    for l in 参战僵尸图 + ['小鬼僵尸'] + boss:
        if l in 大尸:
            lzx = c(大尸[l])
        else:
            lzx = 2
        图集[l] = 加载图('图片/' + l + '.png', 比 * lzx, 比 * lzx)
    for l in ('锤子1', '锤子2', '锤子3', '投篮臂', '投篮臂-空'):
        图集[l] = 加载图('图片/' + l + '.png', 比 * 3, 比 * 3)
    for l in ('灯光1', '灯光2', '灯光3', '灯光4'):
        图集[l] = 加载图('图片/' + l + '.png', 比 * 2, 比 * 10)
        图集[l].set_alpha(100)
    for l in 僵尸图 + ['狂暴报纸僵尸']:
        if l in 大尸:
            lzx = c(大尸[l])
        else:
            lzx = 2
        图集[l + '-首'] = 加载图('图片/' + l + '-首.png', 比 * lzx, 比 * lzx)
        图集[l + '-身'] = 加载图('图片/' + l + '-身.png', 比 * lzx, 比 * lzx)
        图集[l + '-首-受伤'] = 变图(纯换色(加载原图('图片/' + l + '-首.png'), 纯白色), 比 * lzx, 比 * lzx)
        图集[l + '-身-受伤'] = 变图(纯换色(加载原图('图片/' + l + '-身.png'), 纯白色), 比 * lzx, 比 * lzx)
        图集[l + '-首-灰烬'] = 变图(纯换色(加载原图('图片/' + l + '-首.png'), 纯黑色), 比 * lzx, 比 * lzx)
        图集[l + '-身-灰烬'] = 变图(纯换色(加载原图('图片/' + l + '-身.png'), 纯黑色), 比 * lzx, 比 * lzx)
        图集[l + '-首-冰冻'] = 变图(不纯换色(加载原图('图片/' + l + '-首.png'), 蓝色), 比 * lzx, 比 * lzx)
        图集[l + '-身-冰冻'] = 变图(不纯换色(加载原图('图片/' + l + '-身.png'), 蓝色), 比 * lzx, 比 * lzx)
        图集[l + '-首-魅惑'] = 变图(不纯换色(加载原图('图片/' + l + '-首.png'), 紫色), 比 * lzx, 比 * lzx)
        图集[l + '-身-魅惑'] = 变图(不纯换色(加载原图('图片/' + l + '-身.png'), 紫色), 比 * lzx, 比 * lzx)
    for l in 其它图 + 所有植物 + 植物补充 + 伤害实体 + 火图:
        图集[l] = 加载图('图片/' + l + '.png', 比, 比)
    for ll in 投掷对应:
        l = 投掷对应[ll]
        图集[l + '-抛物线'] = 加载图('图片/' + l + '.png', 比, 比)
        图集[l + '-抛物线'].set_alpha(100)
    for l in 火图 + ['火豆']:
        图集['蓝' + l] = 变图(换蓝色(加载原图('图片/' + l + '.png')), 比, 比)
    for l in 方块:
        图集[l] = 加载图('图片/' + l + '.png', 比, 比)
    for l in 投手植物:
        图集[l + '-投'] = 加载图('图片/' + l + '-投.png', 比 * 2, 比 * 2)
        图集[l + '-投空'] = 加载图('图片/' + l + '-投空.png', 比 * 2, 比 * 2)
        图集[l + '-投-黑白'] = 变图(换黑白(加载原图('图片/' + l + '-投.png')), 比 * 2, 比 * 2)
        图集[l + '-投空-黑白'] = 变图(换黑白(加载原图('图片/' + l + '-投空.png')), 比 * 2, 比 * 2)
    图集['小阳光球'] = 加载图('图片/阳光球.png', 比 * 2 / 3, 比 * 2 / 3)
    图集['小阳光环'] = 加载图('图片/阳光环.png', 比 * 2 / 3, 比 * 2 / 3)
    for l in 所有植物 + 植物补充 + ['花盆块', '睡莲块', '脑子']:
        图集[l + '-受伤'] = 变图(纯换色(加载原图('图片/' + l + '.png'), 纯白色), 比, 比)
        图集[l + '-黑白'] = 变图(换黑白(加载原图('图片/' + l + '.png')), 比, 比)
    图集['黄金脑子-黑白'] = 变图(换黑白(加载原图('图片/脑子.png')), 比, 比)
    图集['黄金脑子-受伤'] = 变图(纯换色(加载原图('图片/脑子.png'), 纯白色), 比, 比)
    图集['黄金脑子'] = 变图(换金色(加载原图('图片/脑子.png')), 比, 比)
    for l in ('玉米加农炮', '玉米加农炮-车', '玉米炮'):
        图集[l] = 加载图('图片/' + l + '.png', 比 * 2, 比 * 2)
        图集[l + '-受伤'] = 变图(纯换色(加载原图('图片/' + l + '.png'), 纯白色), 比 * 2, 比 * 2)
        图集[l + '-黑白'] = 变图(换黑白(加载原图('图片/' + l + '.png')), 比 * 2, 比 * 2)
    图集['上玉米炮'] = pygame.transform.rotate(图集['玉米炮'], 90)
    图集['下玉米炮'] = pygame.transform.rotate(图集['玉米炮'], -90)
    for l in 大头 + ['双子向日葵', '大嘴根', '龙蒺藜根', '高坚果-小残', '高坚果-大残', '南瓜头-小残', '南瓜头-大残', '叶子伞', '大嘴花-上半', '大嘴花-下半', '龙蒺藜-上半', '龙蒺藜-下半']:
        图集[l] = 加载图('图片/' + l + '.png', 比 * 1.5, 比 * 1.5)
        图集[l + '-黑白'] = 变图(换黑白(加载原图('图片/' + l + '.png')), 比 * 1.5, 比 * 1.5)
        图集[l + '-受伤'] = 变图(纯换色(加载原图('图片/' + l + '.png'), 纯白色), 比 * 1.5, 比 * 1.5)
    图集['石果子-黑'] = 变图(纯换色(加载原图('图片/石果子.png'), 纯黑色), 比 * 1.5, 比 * 1.5)
    图集['路灯花-光疗'] = 变图(纯换色(加载原图('图片/路灯花.png'), 纯黄色), 比, 比)
    图集['向日葵-生产'] = 变图(纯换色(加载原图('图片/向日葵.png'), 纯黄色), 比, 比)
    图集['双子向日葵-生产'] = 变图(纯换色(加载原图('图片/双子向日葵.png'), 纯黄色), 比 * 1.5, 比 * 1.5)
    图集['阳光菇-生产'] = 变图(纯换色(加载原图('图片/阳光菇.png'), 纯黄色), 比, 比)
    图集['里方块'] = 加载图('图片/黑.png', 比, 比)
    图集['里方块'].set_alpha(50)
    for l in ('不适宜种植', '适宜开炮', '适宜种植', '适宜铲除'):
        for lzx in range(4):
            dushu = 0
            if lzx == 1:
                dushu = -90
            if lzx == 2:
                dushu = -270
            if lzx == 3:
                dushu = -180
            图集[l + str(lzx)] = pygame.transform.rotate(加载图('图片/' + l + '.png', 比 // 2, 比 // 2), dushu)
    近景图集 = {}
    for l in 方块:
        近景图集[l] = 加载图('图片/' + l + '.png', 16, 16)
    近景图集['水'] = 加载图('图片/水.png', 16, 512)
    近景图集['水'].set_alpha(150)
    图集['尸首板'] = 加载图('图片/尸首板.png', 比 * 4, 比)
    图集['钱袋'] = 加载图('图片/钱袋.png', 比 * 2, 比 * 0.5)
    图集['小脑子'] = 加载图('图片/脑子.png', 比 * 0.5, 比 * 0.5)
    图集['爆炸'] = 加载图('图片/爆炸.png', 比 * 3, 比 * 3)
    图集['轮子'] = 加载图('图片/轮子.png', 比 * 1.5, 比 * 1.5)
    图集['小丑爆炸'] = 加载图('图片/小丑爆炸.png', 比 * 3, 比 * 3)
    图集['爆炸印'] = 加载图('图片/爆炸印.png', 比 * 4, 比 * 4)
    图集['炸雷'] = 加载图('图片/炸雷.png', 比 * 3, 比 * 3)
    图集['毁灭3'] = 加载图('图片/毁灭3.png', 比 * 2, 比 * 2)
    图集['毁灭1'] = 加载图('图片/毁灭1.png', 比 * 6, 比 * 6)
    图集['毁灭2.0'] = 加载图('图片/毁灭2.0.png', 比 * 6, 比 * 6)
    图集['毁灭2.1'] = 加载图('图片/毁灭2.1.png', 比 * 6, 比 * 6)
    图集['毁灭2.2'] = 加载图('图片/毁灭2.2.png', 比 * 6, 比 * 6)
    图集['冻住'] = 加载图('图片/冻住.png', 总宽, 总高)
    图集['核爆'] = 加载图('图片/核爆.png', 总宽, 总高)
    图集['水'] = 加载图('图片/水.png', 比, 比 * 32)
    图集['水'].set_alpha(150)
    图集['黑水'] = 加载图('图片/黑水.png', 比, 比 * 32)
    图集['黑水'].set_alpha(150)
    黑 = 加载图('图片/黑.png', 总宽, 总高)
    白 = 加载图('图片/白.png', 总宽, 总高)
    黑背景 = 加载图('图片/黑.png', 总宽, 总高)
    shui = time.localtime().tm_hour
    if shui >= 19 or shui <= 5:
        tian = '黑天'
    else:
        tian = '白天'
    主界面近景 = 生成近景('山地', tian)
