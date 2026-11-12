# Actual original test callback window 34910 with native loop entry/exit trampolines only.
if event.type == pygame.MOUSEBUTTONUP and 选中 != -1 and '提示' not in 选块[选中]:
    播音('选中')
    选块名 = []
    name = c(选块[选中]['名'])
    if name in 设置:
        if name == '屏幕大小' or name == '全屏':
            挪动[4] = 0
            if name == '全屏':
                if 设置[name]:
                    设置['屏幕大小'] = 2
                    设置[name] = False
                else:
                    设置['屏幕大小'] = 0
                    设置[name] = True
            else:
                设置['全屏'] = False
                设置[name] += 1
                if 设置[name] == 5:
                    设置[name] = 1
            if 设置['屏幕大小'] == 0:
                总宽 = 原总宽
                总高 = 原总高
                screen = pygame.display.set_mode((总宽, 总高), pygame.FULLSCREEN)
                加载游戏()
            else:
                总宽 = 原总宽 * (5 - 设置['屏幕大小']) // 5
                总高 = 原总高 * (5 - 设置['屏幕大小']) // 5
                screen = pygame.display.set_mode((总宽, 总高))
                加载游戏()
            选块归位()
        else:
            if name in ('音乐', '音效') and 没音:
                pass
            else:
                if 设置[name]:
                    设置[name] = False
                    if name == '音乐':
                        pygame.mixer.music.set_volume(0)
                else:
                    设置[name] = True
                    if name == '音乐':
                        pygame.mixer.music.set_volume(0.4)
    if name[-1] == '式' or name == '我是僵尸':
        音乐淡出()
        播音('开始游戏')
        try:
            音效['开始游戏'].set_volume(0.2)
        except:
            pass
        关 = 1
        选块名 = ['空']
        模式 = name
    if name == '离开':
        关游戏()
    if name == '花园':
        开始方式 = '花园'
        关 = 1
        选块名 = ['空']
        音乐淡出()
    if name == '继续游戏':
        开始方式 = '继续游戏'
        for l in 数据['继续']:
            选块名.append(l)
    if name == 'WAD' or name == '空AD' or name == '↑←→':
        设置['按键'] = name
    if name == '皮肤':
        选块名 = ['返回', '疯狂戴夫', '我的世界', '结束乐队', '调查兵团']
    if name == '声明':
        选块名 = ['返回', '作者', '空', '空', '空']
    if name == '按键设置':
        选块名 = ['返回', '空AD', 'WAD', '↑←→']
    if name == '屏幕设置':
        选块名 = ['返回', '全屏', '屏幕大小']
    if name == '设置':
        选块名 = ['返回', '音效', '音乐', '屏幕设置', '粒子效果', '按键设置']
    if name == '新游戏':
        开始方式 = '新游戏'
        选块名 = ['正常模式', '未-极难模式', '未-抽奖模式', '未-末日模式', '未-我是僵尸']
        if '正常模式' in 数据['打败boss'] or 版本 == 'v-1.0.0' or 版本 == 'v233.0.0':
            选块名[1] = '极难模式'
        if '极难模式' in 数据['打败boss'] or 版本 == 'v-1.0.0' or 版本 == 'v233.0.0':
            选块名[3] = '末日模式'
        if '抽奖模式' in 数据['打败boss'] or 版本 == 'v-1.0.0' or 版本 == 'v233.0.0':
            选块名[4] = '我是僵尸'
        if len(杯子) > 0 or '继续' in 数据 and 数据['继续'] != {}:
            选块名[2] = '抽奖模式'
        if 版本 == 'v-1.0.0' or len(数据['拟人']) == len(所有植物):
            选块名.append('测试模式')
    if name == '返回':
        选块名 = ['新游戏', '设置', '声明', '离开']
        if '继续' in 数据 and 数据['继续'] != {}:
            选块名 = ['新游戏', '继续游戏', '设置', '声明', '离开']
        if len(杯子) > 0:
            选块名.append('花园')
    return
