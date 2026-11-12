# C++ 旧套件迁移：Codex 接手状态

## 当前测试规则（2026-11-04）

游戏最终候选 r2 的验收和包已完成，见项目根目录交接文件的最终交付记录。
用户随后明确授权临时豁免剩余6 FAIL / 12 ERROR，并要求内存允许时优先多个worker。
`run_cpp_suite.py` 和 `full_test.sh` 现在默认按物理内存/提交额度自动并行；可用
`--workers N` 设置并发上限，`--workers 1` 串行。编译仍 /MP1 / parallel1。
临时豁免只匹配 `temporary-native-waivers.json` 的18个精确ID、结果类型和详情SHA，
保留原始结果及完整分母，仅改变已授权差异的阻断判定。`--strict` 禁用豁免。
详见 README「回归与临时豁免」。下文为2026-11-02的历史记录，不作为最新测试状态。

## 历史接手状态（2026-11-02）

2026-11-02。已完成当前可编译集合的完整执行，未通过全量验收。证据根目录：`test_results/native-suite-20261102/`；最新结果为 `full-attempt8`，汇总在 `latest-status.json`。

## 已落实

- 原始文件备份在证据目录的 `prechange/`。只修改 PVZ-PvP71-Native；next-pvp71 游戏和测试源码作为只读参照。
- `oracle_diff.py` 拒绝空输出、长度不等/截断；6 个独立契约检查通过。
- `pvzunit.py` 恢复列表/元组/字典/序列类型约束、正则异常匹配。CPython 侧 12 个契约检查通过。
- C++ runner 零用例失败、class cleanup 异常计错，使用实际 pvzcore + pvzui；`--framework-selftest` 的 34 个原生正/负控制通过，覆盖断言、异常上下文、环境恢复、临时迭代对象的存活时间、缺失属性和绑定函数。
- `run_cpp_suite.py` 按模块独立进程、隔离 APPDATA/PVP_USERDATA，默认 2 worker，记录 exit、逐例结果、遗漏项、二进制 SHA256、源码指纹。报告有 FAIL/ERROR/缺失就失败，不认日志中单个 PASS。
- 原版 CPython unittest loader 实际收集全部 199 个非 Android 目标模块：2316 次执行、2139 个不同 unittest ID。已用它生成注册表，身份多重集合差异为 0；另有依赖测试模块和显式受阻模块。zombie_pea/flag_reinforcement 的 51 vs 旧 summary 28 是导入/继承重复归属，不能把执行次数当独立功能覆盖。
- 修复翻译器的：赋值目标扫描把 sys 当变量、绝对测试模块导入、classmethod 重绑定/接收类、动态 isinstance、lambda *args/**kwargs、依赖头遗漏、长字符串/代理码点编码、生成失败返回非零。测试代码保留断言；不以降低期望修失败。
- 未移植的生产模块/API明确记录受阻，或抛 NotImplementedError，不能用成功空实现代替。
- 补入实际候选扫描和 C++ 坐标筛选；直接以原 Python `_box_candidates_python` 生成 130 组参照，C++ 结果全部一致。当前坐标收集为串行 C++，不宣称原进程后端已实现。
- 补入英雄隔离监控，直接接在 C++ 静态 step/spawn 入口；6 个正反检查通过。运行器设 `PVP_HERO_GUARD=1` 并保留违规 JSONL；原测试主动撤掉日志配置的故意违规不冒充游戏故障。
- 修复实际运行时错误：`iter_list(...).items()` 返回临时对象内部引用，C++20 范围循环开始前对象已释放。英雄 32 个字段的展开实测原为 0 项，导致 spawn 后玩家全局量无法恢复。修复后展开为 32 项，spawn 前后全局快照差异为 0。`any/all/sum/map/filter/*args/set` 中同类写法一并修复，增加对应原生检查。
- 修复字典缺失属性被假装成绑定方法的问题：AI 取缺失属性后替换回调会递归调用自身。支援模块从整进程栈溢出变为完整 16 条结果，其中 14 PASS / 1 FAIL / 1 ERROR。
- 修复回放回调捕获裸 `this`、录制对象释放后仍被使用的问题；回调保持对象所有权。此前崩溃的两个模块现在完整产生 17 条结果（9 PASS / 8 ERROR），无访问冲突。生成器同时保留此规则，未声称长时间运行和循环引用内存回收已验证。
- 修复合并导入丢失其他名字（例如 `import unittest, sys`）以及测试辅助脚本重导出的绑定。13 条僵尸用例全通过；8 条缩放用例为 6 PASS / 2 FAIL，后两条实际指出骑乘图层相差 33 px，未修改期望值。

## 已有运行结果（均不是全量通过）

- batch1：293 次执行，190 PASS / 31 FAIL / 72 ERROR。
- batch2：293 次执行，247 PASS / 27 FAIL / 19 ERROR。
- full-attempt3：140 模块、1629 次执行，130 PASS / 9 FAIL / 1490 ERROR，无遗漏；开启严格模式后暴露大量原来被 no-op 掩盖的测试基础设施问题。
- full-attempt4：193 模块，230 PASS / 32 FAIL / 1945 ERROR，进程崩溃造成 16 条缺失。
- full-attempt5：193 模块，342 PASS / 41 FAIL / 1824 ERROR，16 条缺失。
- full-attempt6：193 模块，904 PASS / 784 FAIL / 511 ERROR，24 条缺失；本轮首次强制原生英雄监控，大量 FAIL 是上述玩家全局量恢复错误，保留了修复前证据。
- full-attempt7：193 模块，1549 PASS / 90 FAIL / 551 ERROR，33 条因崩溃缺失，耗时 524.972 秒。
- **full-attempt8：193 模块、2223 次已收集执行，1602 PASS / 91 FAIL / 530 ERROR / 0 SKIP，0 缺失，耗时 500.028 秒（8 分 20 秒）。** 测试期间源码和二进制均未改变。不同 unittest ID 按重复执行的最差结果统计：1443 PASS / 80 FAIL / 523 ERROR。执行次数不能当成不同功能数。
- 本轮 9 个受阻模块对应注册清单中另外 134 次未执行项；还有 32 个历史“不适用”模块待逐功能复核及 1 个 Android 待迁移模块。它们未被计为 PASS。历史 2561 例是盘点口径；实际 loader 清单另存，不能硬凑数字。
- 当前 `src/cpptests/collection-blocked.json` 中 9 个模块因缺少 integration/campaign_pool 及依赖受阻；完整差异在每轮 `collection-mismatch.json`，不从验收分母中隐去。另有旧不适用项待逐功能审查、Android 功能/设备测试未完成。

## 重要限制

- 原有 17/17 报告、34 场景对拍、模拟器手动点过均不能代替旧断言覆盖。修过判定逻辑后旧报告不能视为重新验收。
- 最新内核的 **34/34 战斗对拍通过**（`oracle-regression9.log`，进程退出 0，开启英雄监控且没有违规日志）。secrets_3 缺少的 headless 混合标志已按实际 pygame 后端常量补齐。对拍仍有 1e-9 容差、地址键/占位对象的既有忽略规则，不是逐位证明。
- 最新 PC 自动烟雾测试通过（`pc-smoke.log` / `pc-smoke.png`），覆盖建房、禁选、战斗、移动/跳跃、伤害、入水、投降和重赛。是自动化场景验证，不是人工试玩或 Android 设备验证。
- 测试专用 mock 仅实现真实可恢复的 patch.dict；patch.object/生产静态绑定尚不支持，使用时明确报错，不能假装已打补丁。
- CPython 的 generation GC 在独立 C++ 版不可用，gc_policy 明确报告 supported=false / apply=false，不伪造 freeze 或阈值行为。旧 GC 行为测试不能被计为原样等价通过。
- 仍有像素/DrawReplay/API、动态 mock、旧 Python 资源/加载器、异步测试适配等缺口，以及实际断言差异；需要按逐例结果继续补实际功能或设计可证明等价的 C++ 测试。最新完整轮已无进程崩溃造成的缺失。不能把测试适配错误全部称为游戏规则错误，也不能把它们忽略后算全量通过。
- 不覆盖 dist/PC 候选包或 APK。修改后的 runtime 需重新链接验证；没有 Android 设备复测。
- 继续时先查看最新 build-all*.log、full-attempt*/summary.json 以及正在运行的进程，避免与仍在执行的 Codex 构建同时修改同一源码。

## 继续工作

1. 以 `full-attempt8/coverage-accounting.json`、逐例 JSON 和 `latest-status.json` 定位剩余 91 FAIL / 530 ERROR，不使用早期全量报告代替。
2. 对 9 个受阻模块、历史“不适用”项和 Android 功能逐条确认产品范围及等价验证方案。当前不能宣称旧 2561 条已等价覆盖。
3. 优先处理生产行为失败和真实 API 缺口；Python 专用加载器/字节码/猴子补丁需要测试接口适配，不能给一个成功空实现。
4. 候选扫描、回放持有关系及其他带相互引用的对象还需长时间/多次重赛内存验证；没有新的性能倍数测量。
5. 通过对应验收后，才重建正式 PC 包和 APK，再进行设备验证；当前候选包保持原样。

复现当前完整执行（使用新的输出目录）：

```powershell
& 'C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\modkit\tools\python38-embed\python.exe' tools/run_cpp_suite.py --out test_results/<new-run> --workers 2 --timeout 600
```

重新生成测试时，先用 `collect_reference_tests.py` 收集原 unittest 身份，再给 `gen_cpp_tests.py --reference-collection <manifest>`；不能只靠 AST 估算测试集合。生产生成文件里本次补入的 step/spawn 监控和回放回调所有权规则也已写进生成器。
