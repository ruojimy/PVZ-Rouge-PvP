# PVZ-Rouge · 对战模式（PvP）

中文版当前为 **PvP73**（`1.6.0.73-typed.20261112`，C++ 原生版，无需 Python）。英文版仍为 PvP64（`1.6.0.0-pvp.64`）。两者规则不同，不能互相联机。

## 下载

### 中文版 — [PvP73](../../releases/tag/v1.6.0.73-pvp73)

| 附件 | 用途 |
| --- | --- |
| `PvZ-PvP-Native-20261112-pvp73-r2.zip` | Windows 玩家包；解压后运行 `PvZ-PvP-Native\PvZPvPNative.exe` |
| `PvZ-PvP-Native-20261112-pvp73-r2-Developer-Package.zip` | 完整 C++ 源码、类型化内核、PvP 规则 Python 源码、原版反编译 Python、工具、测试与构建脚本 |
| `PvZ-PvP-Native-1.6.0.73-typed.20261112-1112073-20261112-pvp73-r2.apk` | 已签名安卓包（ARM64，包名 `org.pvzrouge.pvzpvpnative`） |

本版平衡（草坪、石块、石化火炬、小鬼炮、报纸僵尸、滚桶僵尸、海盗船长、墓碑吞噬者僵尸）、新功能（合作 $10000 跳关、肆意模仿费用同步）、修复与验证范围见 [Release 说明](../../releases/tag/v1.6.0.73-pvp73)。

上一版中文 PvP64（Python 版）仍保留在 [PvP64 Release](../../releases/tag/v1.6.0.0-pvp64)，英文 Overlay 需要其中的中文开发者包。

### English edition — [PvP64 EN](../../releases/tag/v1.6.0.0-pvp64-en)

| Asset | Use |
| --- | --- |
| `PVZ-Rouge-v1.6.0.0-PvP64-EN-Release-Package.zip` | Complete player package; run `launch_pvp_en.cmd` |
| `PVZ-Rouge-v1.6.0.0-PvP64-EN-Developer-Package.zip` | Complete English developer package |
| `PVZ-Rouge-v1.6.0.0-PvP64-EN-Android.apk` | Updates the English app in place; installs alongside Chinese |
| `PVZ-Rouge-v1.6.0.0-PvP64-EN-Overlay.zip` | Apply over this release's Chinese developer package to reconstruct the English developer package; requires the exact base ZIP |

## 给其他改版作者

PvP73 开发者包包含完整源码与工具，做 PvZ 肉鸽改版时可以参考或直接取用：

| 想做的事 | 看哪里 |
| --- | --- |
| 把 Python 3.8 打包的游戏 `.pyc` 还原成源码 | 自写反编译器 `tools/pydec38.py`（区段与函数级输出） |
| 了解原版肉鸽的波次、经济、卡牌与僵尸逻辑 | `extract/original`（原版反编译）、`extract/live`（对局实际运行部分） |
| 在不改原版逻辑的前提下加对战／合作规则 | `tools/pvp72_sources`：PvP 规则的 Python 源码，以门控注入挂到原版 |
| 把 Python 游戏移植成 C++ | `tools/py2cpp.py`、`tools/pvp2cpp.py` 先翻成动态值运行时（`src/core`）上的 C++，再逐步换成类型化内核（`build/typed72-integrated-v44/source/src/sim/typed`） |
| 证明重写后行为没变 | 逐 tick、逐绘制帧对拍：`build/pvp73-tools/compare73.py`、`batch73.py`；纯血门禁 `tools/pvp73_pure_typed_gate.py` |
| 旧测试套件迁移 | `tools/run_cpp_suite.py`：Python 测试翻成 C++ 后在隔离进程中运行 |
| 出安卓包 | `android/`：SDL2 + NDK 构建与 APK 打包（签名私钥需自备） |

包内 `开发者包说明-PvP73.md` 讲目录、编译和改规则的流程。注意：大量代码是生成的，建议从生成器和说明读起；测试夹具需要原版 Python 工程中的资料，包里不含；图片、音乐、音效需从玩家包复制。

## 许可与归属

- 本项目自己编写的部分（C++ 源码、PvP 规则源码、反编译器、翻译与测试／构建工具、文档）以 [MIT 许可](LICENSE) 发布，转载或改作请保留版权声明。
- 原版肉鸽游戏的代码（含 `extract/original`、`extract/live` 中的反编译结果）与数据归原作者所有，不在 MIT 许可范围内；公开它们仅供研究与改版参考。原作者如有异议请提 Issue，会及时处理。
- 植物大战僵尸的名称、图片、音乐与音效归 PopCap Games / Electronic Arts。本项目为非商业粉丝作品。
- `third_party/` 中的 SDL2 系列、nlohmann/json、zlib 沿用各自的许可。

## 验证范围

**中文 PvP73（2026-11-12）**：翻译后的旧测试套件 2304 项通过，相对 PvP72 新增的不通过项全部是本版有意的规则变化，判定已同步更新；纯血门禁（对战 AI、合作 AI、2v2 三局真实对局）确认每帧逻辑只走类型化 C++；类型化内核与参照实现逐 tick、逐绘制帧对拍一致；PC 包逐文件哈希、无关目录启动、覆盖旧目录升级与全新安装通过；APK 签名与内容校验通过。未在真机上测试，未验证异地公网对局。

**英文 PvP64（2026-10-10）**：中文 1536 项／148 模块，英文 1545 项／149 模块；最终零失败、零错误、零跳过。中英 APK 已在 Android 35 模拟器上通过从 PvP61 升级、原数据保留、两版并存和原生战斗／回放验证。PC 与安卓中英双向主机、直连／本地中继、观战与跨语言回放均已验证。英文图鉴 845 行、PC 与触屏界面巡检 0 漏翻。环境失败与复测记录、完整范围和截图均在包内 `验证记录/最终验证20261010/`。

## 更新与兼容

中文 PvP73：

- Windows：压缩包里只有一个文件夹 `PvZ-PvP-Native`，以后升级直接解压覆盖它；首次启动会清理旧版残留文件并提示。存档在 `%APPDATA%\PVZ-PvP-Native`，首次启动会并入 `%APPDATA%\PVZ-Rouge-PvP`（PvP61–PvP64）等旧目录的存档。
- Android：与 PvP64 及更早中文版（`org.pvzrouge.pvzpvp`）是不同应用，会并存安装，不会覆盖旧版。
- 不能与 PvP72、PvP64 联机，旧版回放不能在 PvP73 播放。联机双方都请使用 PvP73。

English PvP64:

- 原版模式由游戏原引擎处理，对战使用独立规则。PC 存档位于 `%APPDATA%\PVZ-Rouge-PvP\pvp_userdata`。
- Windows 覆盖旧英文目录请运行 `更新旧英文版.cmd`；玩家数据、地图、回放与已有中继配置保留，覆盖前备份。
- Android 英文包名 `org.pvzrouge.pvzpvp.en`，可与中文版并存。

每个 Release 附有产物字节数和 SHA256，ZIP 内有逐文件 SHA256 清单。分发包不含个人存档和签名私钥。
