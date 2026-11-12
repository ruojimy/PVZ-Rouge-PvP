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
                                    if xx == 0:
                                        # goto @2278
                                        pass
                                    if xx == 4:
                                        # goto @2278
                                        pass
                                    ditu[y][x]['方块'] = '木箱'
                                else:
                                    # !! GOTO @2260 (already emitted above)
                                    pass
                    if yq == 4:
                        for yy in range(2):
                            y = 12 + yy
                            for xx in range(6):
                                if xx == 5 and yy == 0:
                                    continue
                                x = xx + lzx * 12 + 1
                                ditu[y][x]['方块'] = '木箱'
                                # !! GOTO @2382 (already emitted above)
                    if yq == 3:
                        for yy in range(2):
                            y = 12 + yy
                            for xx in range(6):
                                if xx == 5 and yy == 0:
                                    continue
                                x = 11 - xx + lzx * 12
                                ditu[y][x]['方块'] = '木箱'
                                # !! GOTO @2486 (already emitted above)
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
                        if chang == 6:
                            continue
                        break
                    if chux + chang >= len(ditu[0]) - 8:
                        chang = 5
                        if chux + chang >= len(ditu[0]) - 8:
                            # goto @4260
                            pass
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
                                            if ceng <= 0:
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
                        if chang == 6:
                            # !! GOTO @2978 (already emitted above)
                            pass
                        break
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
                                if not tizi:
                                    # goto @4254
                                    pass
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
                                    if ditu[y][x]['里方块'] != '空':
                                        # goto @4254
                                        pass
                                    del ditu[y][x]['里方块']
                                else:
                                    ditu[y][x]['方块'] = name
    return ditu

def 多少阳光(name):
