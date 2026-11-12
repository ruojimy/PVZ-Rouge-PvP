# Old Python suite (next-pvp71/tests, 235 modules) -> C++ native build coverage map.
#   python38 tools/coverage_map.py <old_suite.json> <out.md> <out.json>
# Status is per module and strict: "已覆盖" only when that module's assertions are executed against the C++
# build. A C++ integration test that exercises the same feature without the same assertions is recorded as
# overlap ("相关 C++ 测试"), and the module stays "待迁移".
import json, sys

COVERED, TODO, NA = '已覆盖', '待迁移', '不适用'

# what the old suite executes (pvp71-suite-groups/summary.json: cpp_active_all_groups=true)
OLD_RUNTIME = 'CPython 3.8 运行 modkit/pvp 源码（+ 旧 _pvpcore C++ 加速核心 pyd，真 pygame/SDL）'

# C++ suite groups (tools/full_test.sh) and what they execute
CPP_GROUPS = {
    'check_all': 'C++ run_battle.exe（翻译后的战斗内核）逐刻输出 vs CPython 预先录制的 oracle（extract/oracle/*.jsonl，34 场景：全部 232 卡、秘籍、输入、墓碑、2v2、合作波次）；比较脚本为 Python',
    'smoke': 'C++ app_run.exe 运行翻译后的 smoke.py 驱动（主页→配置→BP→对战→结算→再来一局）',
    'evidence': 'C++ app_run.exe：smoke + 各阶段截图 + 回放保存/重放终点校验 + 固定 AI 房',
    'almanac': 'C++ app_run.exe：本地房 BP 中右键全部 232 张卡（简略/详细图鉴）渲染',
    'probe': 'C++ app_run.exe：mixer/音效/音乐/全屏切换',
    'mapedit': 'C++ app_run.exe：地图编辑器画图→保存→回读→开房使用',
    'cooplobby': 'C++ app_run.exe：主页合作入口→固定合作 AI 房→闯关→对战，AI 队友种植',
    'airoom': 'C++ app_run.exe：大厅固定 AI 房（r22）BP+对战 30 秒',
    'regex': 'C++ re 引擎 vs CPython re 的期望值（27 条）',
    'nettest': 'C++ ServerTransport/ClientTransport 同进程回环握手+双向消息',
    'netpeer_duel': '3 个 C++ 进程：主机/客机/观战，TCP 回环 BP→对战→投降→回放校验',
    'netpeer_coop': '2 个 C++ 进程：合作房队伍聊天',
    'netpeer_relay': '2 个 C++ 进程经公网中继私有房 BP→对战',
}

PACKAGING = {'56_smoke_optimized', '57_smoke_rooms', '57_visual_probe', '57_update', '66_coexist', 'test_catalog',
             'storage_inputs', '67_final_cpp_regions', 'integration'}
ORIGINAL_RUNTIME = {'legacy', 'native_bytecode_windows', 'native_gate', 'native_patch', 'native_patch_targets', 'reference',
                    'native_catalog', '68_original_optimizations'}
# not applicable as written, but the C++ build needs its own equivalent test (the feature exists there)
NEEDS_NEW = {
    '57_android_userdata': 'C++ APK：卸载重装/升级后 files/pvp_userdata 存档保留',
    '67_android_upgrade': 'C++ APK：覆盖安装同签名新版本，存档与设置保留；包内不含凭据',
    '67_android_fullscreen': 'C++ APK：沉浸式全屏、切后台/回前台后画面与输入恢复',
    'android_audio': 'C++ APK：音效/音乐播放，切后台暂停、回前台恢复',
    'android_label': 'C++ APK：启动器名称为正确 UTF-8 中文',
    'storage_inputs': 'C++ 发行包/APK 不含 keystore.env、私有存档、开发工具',
    '57_update': 'C++ 版若提供更新器，需新写覆盖安装测试（当前未提供）',
}

def theme(m):
    n, f, imps = m['module'][9:], set(m['flags']), ' '.join(m['imports'])
    if n in PACKAGING: return '打包/发行/工具链'
    if n in ORIGINAL_RUNTIME: return '原版字节码/补丁运行时'
    if n.startswith('multiworker') or 'native_multiworker' in imps and 'multiworker' in n: return '多进程/多 worker'
    if n in ('network', 'network_memory67', 'network_optimization', 'relay', 'room_refill', 'room_roles54',
             'spectators49', 'spectator_ui49', 'match_network', 'quit_forfeit', 'replay_transfer', 'room_requests',
             '66_latency_oct15', '67_coop_spectators', '67_coop_pool', '66_room_admission_oct16', '66_coop_own_deck_oct16',
             '57_room_requests'):
        return '联机/中继/观战'
    if 'android' in n or n in ('perf_boost', 'storage_inputs', '66_package_manual_oct15', '56_probe_checks', '67_original_touch'):
        return '安卓平台'
    if 'ai' in f and ('rv_' in imps or 'lobby_room' in imps or n.startswith('66_ai') or 'firing' in n or 'team_support' in n):
        return 'AI'
    if 'app' in f or 'pygame' in f and ('rendering' in imps or 'app' in imps): return 'UI/渲染'
    if 'replay' in n or 'audit' in n: return '回放/审计'
    return '战斗内核/规则/数值'

# explicit decisions (module suffix after test_pvp_)
NA_REASONS = {
    '56_smoke_optimized': 'CPython -O 优化运行时下断言被剥离的问题；C++ 无此运行时',
    '57_smoke_rooms': '同上：打包验收在 python -O 下仍须生效',
    '57_visual_probe': '同上：python -O 打包视觉验收',
    '56_probe_checks': 'p4a 以 PYTHONOPTIMIZE=2 运行时的诊断检查；C++ APK 无 Python',
    '57_update': 'Python 版 Windows 更新器（覆盖旧安装）；C++ 版尚无更新器，若做需新写测试',
    '66_coexist': 'Python 版 PvP65/66/67 并存与只读迁移；C++ 版存档独立（%APPDATA%/PVZ-PvP-Native），不迁移旧档',
    '67_final_cpp_regions': '旧 _pvpcore 构建产物检查（cpp_port）；C++ 版没有该构建',
    'native_bytecode_windows': '原版 marshal 字节码解码器；C++ 版已把原版函数离线翻译，运行期无字节码',
    'native_gate': '原版字节码 gate 解释路径与缓存；C++ 版无解释器（由 check_all 对拍原版行为）',
    'integration': 'Python 嵌入加载器/启动集成（3.8 pyc 加载）；C++ 版无',
    'test_catalog': '按改动影响选测试的工具本身（不碰游戏世界）',
    'multiworker_failover': '多进程 JobSystem 后端/故障切换；C++ 版单进程无 worker',
    'multiworker_history': '快路径开关 == worker 等价历史夹具；C++ 版无 worker（快路径行为由 check_all 对拍）',
    'multiworker_parity': '单/多 worker 权威一致；C++ 版无多 worker',
    'multiworker_projectiles': '多 worker 下星星伤害顺序/失效；C++ 版无 worker',
    'multiworker_schedule_jitter': 'worker 调度抖动、帧复制、pack worker 进程；C++ 版无',
    'multiworker_seam': 'C 内核 vs Python 宽相交检测一致；C++ 版只有一份实现',
    '67_dart_broadphase': '多 worker 宽相交跳过优化；C++ 版无',
    'storage_inputs': 'Python 打包输入/开发者包排除凭据（cpp_port、APK staging）；C++ 包另需新检查',
    '66_package_manual_oct15': 'Python APK 手工交接证明（旧 APK/二进制证明）；C++ APK 流程不同',
    'android_label': 'p4a 启动器标签编码；C++ APK 标签另需新检查（已列入安卓成品测试）',
    '67_android_upgrade': 'p4a 版升级保留私有数据/凭据排除；C++ APK 包名不同，需另写升级测试',
    '57_android_userdata': 'p4a 解压目录外存档；C++ APK 存档在 files/pvp_userdata（需另写设备测试）',
    '57_android_editor_probe': 'p4a 诊断探针跟随编辑器 UI；C++ APK 无该探针',
    'android_audio': 'p4a main.py 音频入口钩子；C++ APK 由 SDLActivity 管理（需另写设备测试）',
    '67_android_entry': 'p4a 原版菜单→PvP 交接；C++ APK 直接进 PvP',
    '67_android_fullscreen': 'jnius 沉浸式 API；C++ APK 用 SDL 全屏（需另写设备测试）',
    '67_original_touch': '原版单人模式触屏→键鼠映射；C++ 版不含原版单人模式',
    '68_original_optimizations': '原版模块定义/构造器的 Python 优化；C++ 版已翻译',
    'native_patch': '在隔离适配器里执行原始 1.5.0.1 补丁源码；C++ 版是翻译产物（行为由 check_all 对拍）',
    'native_patch_targets': '同上：原始补丁回调',
    'legacy': '执行发行版 pvzrouge.pyc 的原版战斗函数；C++ 版已翻译（行为由 check_all 对拍）',
    'reference': '原版 live/隔离数据提取边界（反编译工具链）',
    'native_catalog': '目录解析 vs 发行 marshal/补丁函数；C++ 版目录为提取后的数据',
}
# modules whose subject is a Python mechanism but whose *behaviour* is still a C++ requirement -> 待迁移
# (everything not in NA_REASONS is 待迁移 unless listed in COVERED_BY)
COVERED_BY = {}   # none: no old module's assertions run against the C++ build yet

def overlap(m):
    n, t, f = m['module'][9:], theme(m), set(m['flags'])
    o = []
    if t == '战斗内核/规则/数值' or 'battle' in f: o.append('check_all')
    if t == 'UI/渲染': o += ['smoke', 'evidence']
    if 'almanac' in ' '.join(m['imports']) or n in ('71002',): o.append('almanac')
    if t == '联机/中继/观战': o += ['nettest', 'netpeer_duel'] + (['netpeer_relay'] if 'relay' in n or 'relay' in ' '.join(m['imports']) else [])
    if 'spectator' in n: o.append('netpeer_duel(观战)')
    if 'replay' in n or 'replay' in f: o.append('evidence(回放)')
    if t == 'AI' or n in ('fixed_room',): o += ['airoom', 'evidence(固定AI房)']
    if 'coop' in n or 'pve' in n: o.append('cooplobby')
    if 'map' in n: o.append('mapedit')
    if 'audio' in n: o.append('probe')
    out = []
    for x in o:
        if x not in out: out.append(x)
    return out

def migrate_hint(m, t):
    n = m['module'][9:]
    if t == '安卓平台':
        return '改写为 C++ APK 设备测试（模拟器/真机）'
    if t == '联机/中继/观战':
        return 'pvp2cpp 翻译测试模块 + C++ unittest 外壳；本地中继服务器夹具仍用 Python server/（被测为 C++ 客户端）' if ('server' in m['flags'] or 'relay' in n) else 'pvp2cpp 翻译测试模块 + C++ unittest 外壳，在 C++ 进程内跑真实回环'
    if t == 'UI/渲染':
        return 'pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致'
    return 'pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核'

def main():
    mods = json.load(open(sys.argv[1], encoding='utf-8'))
    rows = []
    for m in mods:
        n = m['module'][9:]
        t = theme(m)
        if n in COVERED_BY:
            st, why = COVERED, COVERED_BY[n]
        elif n in NA_REASONS:
            st, why = NA, NA_REASONS[n]
        elif t == '多进程/多 worker':
            st, why = NA, 'C++ 版单进程无多 worker'
        else:
            st, why = TODO, migrate_hint(m, t)
        rows.append(dict(module=m['module'], tests=m['tests'], theme=t, status=st, reason=why,
                         overlap=overlap(m) if st != NA else [], doc=m['doc'],
                         old_runtime=OLD_RUNTIME, cpp_runtime='（尚无：该模块断言未在 C++ 上执行）' if st == TODO else ('—' if st == NA else 'C++')))
    json.dump(rows, open(sys.argv[3], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    tot = lambda pred: (sum(1 for r in rows if pred(r)), sum(r['tests'] for r in rows if pred(r)))
    L = []
    L.append('# 旧 Python 全量测试 → 纯 C++ 版 覆盖对照\n')
    L.append('生成：`tools/old_suite_inventory.py` + `tools/coverage_map.py`。旧套件 = `next-pvp71/tests/test_pvp_*.py`'
             '（pvp71 基线 232 模块 / 2548 例，现有 235 模块 / 2561 例；另有旧 C++ 闸门 cpp-gate）。\n')
    L.append('**判定口径（严格）**：「已覆盖」= 该模块的断言已经在 C++ 构建上执行并通过；只有相同功能的 C++ 集成测试、但没有执行同样断言的，'
             '一律记「待迁移」，并在「相关 C++ 测试」列注明重叠部分；「不适用」= 被测对象是 C++ 版不存在的 Python/打包/多进程机制，附原因。\n')
    L.append('## 汇总\n')
    L.append('| 状态 | 模块 | 用例 |\n|---|---|---|')
    for st in (COVERED, TODO, NA):
        c, k = tot(lambda r, st=st: r['status'] == st)
        L.append('| %s | %d | %d |' % (st, c, k))
    c, k = tot(lambda r: True)
    L.append('| 合计 | %d | %d |\n' % (c, k))
    L.append('| 主题 | 模块 | 用例 | 其中待迁移用例 | 其中不适用用例 |\n|---|---|---|---|---|')
    for t in sorted({r['theme'] for r in rows}, key=lambda t: -tot(lambda r, t=t: r['theme'] == t)[1]):
        c, k = tot(lambda r, t=t: r['theme'] == t)
        L.append('| %s | %d | %d | %d | %d |' % (t, c, k, tot(lambda r, t=t: r['theme'] == t and r['status'] == TODO)[1],
                                               tot(lambda r, t=t: r['theme'] == t and r['status'] == NA)[1]))
    L.append('\n## 实际执行的是 Python 还是 C++\n')
    L.append('- **旧套件（2561 例）**：%s。它们验证的是 Python 发行版，**没有一条调用纯 C++ 版**。' % OLD_RUNTIME)
    L.append('- **C++ 套件（tools/full_test.sh，17 组）**：')
    for k, v in CPP_GROUPS.items():
        L.append('  - `%s`：%s' % (k, v))
    L.append('  - 其中只有 `check_all` 的参照数据与 `regex` 的期望值来自 CPython；被测对象全部是 C++ 二进制。')
    L.append('\n## 不适用、但 C++ 版需新写等价测试\n')
    L.append('| 旧模块 | C++ 版要新写的测试 |\n|---|---|')
    for k, v in NEEDS_NEW.items():
        L.append('| %s | %s |' % (k, v))
    L.append('\n另：`perf_boost`（安卓性能申请 ADPF/绑大核，11 例）在 C++ APK 中**功能尚未移植**，记为待迁移（先移植功能再迁测试）。')
    L.append('\n## 迁移方案\n')
    L.append('1. **翻译测试模块**：用现有 pvp2cpp 把 `tests/test_pvp_*.py` 翻成 C++（被测模块已是翻译代码，导入关系一致），配一个 C++ unittest 外壳'
             '（TestCase / assert* / setUp / tearDown / subTest / skip、临时目录、APPDATA 隔离），生成 `cpp_tests.exe`，按模块分组并行，'
             '输出与旧套件同格式的 Ran/OK/FAIL。每个旧断言都在 C++ 上执行后，对应模块才从「待迁移」改为「已覆盖」。')
    L.append('2. **翻译测试时要补的运行期能力**：unittest.mock（patch、MagicMock）、tempfile、subprocess（联机测试起本地中继 server/*.py 作为 Python 夹具，'
             '被测仍是 C++ 客户端）、pygame 像素读取与事件注入的完整兼容、importlib.reload 等。')
    L.append('3. **安卓成品测试**（测 APK 本身，不能拿 PC 结果代替）：模拟器 x86_64 与真机 arm64 各跑一遍：首次安装解压→起名→主页→本地对战→教学关卡→'
             '联机直连/中继→回放→地图编辑器→切后台恢复→覆盖安装保留存档→长时间运行的内存/帧率，留设备日志与截图。')
    L.append('4. 上面两项都通过之前，现有 `dist/PvZ-PvP-Native`（PC）和 APK 只算**候选包**，不算全量验收通过。')
    L.append('\n## 逐模块清单\n')
    L.append('| 旧模块 | 用例 | 主题 | 状态 | 原因 / 迁移方式 | 相关 C++ 测试（仅功能重叠，非断言等价） | 旧测试说明 |\n|---|---|---|---|---|---|---|')
    order = {TODO: 0, NA: 1, COVERED: 2}
    for r in sorted(rows, key=lambda r: (order[r['status']], r['theme'], r['module'])):
        L.append('| %s | %d | %s | %s | %s | %s | %s |' % (r['module'][9:], r['tests'], r['theme'], r['status'], r['reason'],
                                                         ', '.join(r['overlap']) or '—', r['doc'].replace('|', '/')))
    open(sys.argv[2], 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('written', sys.argv[2])
    for st in (COVERED, TODO, NA):
        print(st, tot(lambda r, st=st: r['status'] == st))

main()
