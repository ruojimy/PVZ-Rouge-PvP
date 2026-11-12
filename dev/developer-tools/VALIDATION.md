# 端到端验收

阶段：final；证据批次：packed1。此批次all_passed=True，28项检查。确切运行产物SHA256：1fb0fd2cb2f7dd12011c0f81b86385ac1ade1a5493aad19e5edb1e9bf76fd0c2。

环境：独立解压Windows游戏＋独立扩展＋Python3.13.14标准库。中文/空格短路径，从无关cwd调用；游戏旁无src/modkit/reverse_engineered/AI/tests。检查22份实际Python路径记录，无旧源码导入。原生文件I/O未作全系统跟踪，不将声明根目录当作完整I/O审计。

验证：解析后的232项卡牌及规则/哈希；昼夜/秘籍上下文；原生地图保存/重读/房间接受/战斗2tick；真实输入回放另进程播放至30tick并校验终点；独立relay和原生主客机双向传输；候选与正式r1均1250native tick、native_checks、再战成功；两个构建的真实短诊断；APK身份/CRC/ELF和PC版本一致；接口/版本/地图/回放非法输入拒绝。具体逐项结果在validation/results.json。

游戏受影响阶段门禁18/18，技能格式14/14。包审计要求显式允许清单、每文件长度/SHA、清单自身校验和、ZIP逐文件回读；最终ZIP还必须独立解压并从解压后的脚本重跑，确切外层SHA及这次结果随包旁的verification.json交付。

未验证：Android设备与新开发接口APK、Linux服务安装、公网容量/真人联机、所有卡牌组合/长回放、人工编辑器与长期性能。原始旧套件30FAIL/12ERROR不是本次已修复。旧4项自定义内容skills及AI/完整构建/完整测试共7项仅源码指南，不计入端到端通过。

诊断每构建仅1秒/2单位用于证明管线，不能推出性能提升。APK签名未由本工具验证；现有SDL库4KiB ELF的限制如实保留。失败尝试保存在工程的独立批次中，没有用成功结果覆盖。
