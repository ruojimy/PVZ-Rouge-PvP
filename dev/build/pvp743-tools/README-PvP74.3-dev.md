# PvP74.3 开发者源码与继承证据

版本为 `1.6.0.74.3-typed.20261114`。本包基于已审核的 PvP74.2 dev，覆盖本次工作区拥有的完整源码、数据、素材、生成器、生产内核与组合层，并保留此前角斗士巨人/携带小鬼/二手防具、植物空间索敌、客机前台 move 刷新和 plant2 序号恢复、allocator 的实现及精选证据。新旧文件 SHA-256 核对见 `build/pvp743-tools/source-inheritance.json` 与同名 Markdown 报告。

用户最新要求是继续完成出包，暂不实际测试。因此本轮不追加对局、循环压力或实机测试，也没有一份新完成的 74.3 全量回归。包内 74.2 的 2366 项完整回归、三模式门禁和旧性能结果均为历史证据，只适用于各自记录的构建；旧全量为 2324 PASS、30 FAIL、12 ERROR，不能称全绿，也不能冒充 74.3 已通过。已完成的本轮定向审计仍保留原输入、执行长度、构建摘要与限制。构建、源码/生成物检查和封包校验分别记录，均不等于实机验收。

完整任务与边界见 [PvP74.3 任务总清单](PvP74.3_任务总清单.md) 和 [更新说明](更新说明-PvP74.3.md)。历史 74.2 README 和原清单保存在 `docs/history/README-before-PvP74.3.md`、`docs/history/MANIFEST-PvP74.2.json`，旧资料中的“当前”“通过”以当时版本为准。

## 生产源码入口

Windows 根入口是 `CMakeLists.txt`；Android 入口是 `android/`。两平台共用生产模拟、组合层和大部分 UI，仅必要系统接口做适配。实际生产内核位于 `build/typed72-integrated-v44/source/src/sim/typed/`，早期 `src/sim/typed/` 不能单独代表正式内核。

组合层拥有源为 `build/typed72-match-v1/{match_probe.cpp,frame_layer.inc,snapshot_layer.inc}`；`tools/typed72/make_app_composition.py` 生成实际编译的 `src/sim/typed72_app/composition/` 和清单。UI 重新翻译后须应用 `tools/pvp74_apply_hooks.py` 与 `tools/pvp741_apply_hooks.py`，并运行 `--check`。材质覆盖只影响显示，不能写入模拟图集。详见 `AGENTS.md`。

全部当前测试源码仍在 `src/uitools/`、`src/cpptests/`、`tools/test/` 与 `tools/typed72/`。审计源码的 `pvp742_` 名称不代表它被移除或改成假实现；本次仍使用该稳定入口。

## Windows 构建

需要 CMake 3.20+、Visual Studio 2022 C++ 工具链及 Python。原异步夹具 AST 指纹在 Python 3.8 生成，完整历史回归应使用 3.8；Python 只用于生成/构建/测试，正式游戏不依赖 Python 解释器。

```powershell
python -I -B tools/typed72/make_app_composition.py --check
python -I -B tools/pvp74_apply_hooks.py --check
python -I -B tools/pvp741_apply_hooks.py --check
python -I -B tools/typed72/make_ai_lobby_bridge.py --check
cmake -S . -B build/dev743 -G "Visual Studio 17 2022" -A x64
cmake --build build/dev743 --config Release --target PvZPvPNative --parallel 1
```

若 CMake 选错解释器，设置 `-DPython3_EXECUTABLE=<解释器完整路径>`。`third_party/` 包含已审核的 SDL 开发依赖和根 CMake 必需的 `lib/x64` 文件；这些第三方预编译依赖不属于本项目自身编译产物。

完整运行仍需同版本授权游戏包中的 `图片/`、`音乐/`、`音效/`、`relay.json`，以及本包 `extract/data/`、`extract/assets/`、`fonts/`。根 `启动PvP.cmd` 保留本机原生入口源码，开发者须让它指向自己已核验的构建；本源码包不附项目 EXE 或用户存档。不要用测试存档覆盖用户数据。

## Android 构建

需要 Android SDK/NDK、Java/Gradle、SDL Android 头文件及对应 ABI 库。机器默认路径仅为兼容值，开发环境应显式配置：

```bash
export PVZ_ANDROID_NDK=/path/to/android-ndk
export PVZ_ANDROID_SDL_DIST=/path/to/sdl-dist
export PVZ_ANDROID_WORK=/path/to/native-work
export PVZ_NATIVE_RUN_ID=local-pvp743
bash android/build_native.sh arm64-v8a 1
```

APK 打包还需 `PVZ_ANDROID_SDK`、`PVZ_ANDROID_GRADLE`、`PVZ_ANDROID_ASSET_STAGING`；资源暂存目录须有 `fonts/cjk.ttf`。`android/build_apk.sh` 还读取 `build/Release/图片`、`音乐`、`音效`、`relay.json`，先准备同版本运行素材。字体许可证须保留。

`build_apk.sh` 接受 versionCode、versionName、ABI，并绑定同一 `PVZ_NATIVE_RUN_ID` 的原生候选。签名密钥、密码、SDK 本地配置和升级基准 APK 由开发者自行准备，本包不包含它们。本轮 Android 构建/签名/资源校验状态以发布报告为准，不意味着新增实机性能已验收。

## 来源与封包

`MANIFEST-PvP74.3.json` 逐文件记录相对来源、来源类别、字节数与 SHA-256；`SHA256SUMS.txt` 覆盖载荷和清单。`STAGING_STATUS.json` 明确当前测试边界，历史全量放在 `historical_742_only` 中。精选证据说明见 `test_results/pvp743/README-curated-evidence.md`；当前新增选入证据另有 `test_results/PVP743-EVIDENCE-SHA256SUMS.txt`，基底历史证据由总清单覆盖。

打包脚本是 `build/pvp743-tools/package_dev743.py`。默认只检查计划；`--inheritance-only` 只核对源码并生成继承报告。发布协调者冻结 UI、版本、说明和启动器后，才执行 `--record-freeze`、`--stage`、`--finalize`。`--verify-only` 逐文件重算来源和暂存哈希；任何来源变化都要求重新冻结。脚本不启动游戏或实机测试。

ZIP 每个条目强制 UTF-8 文件名标志，按实际 Unicode 名称、CRC 和逐文件 SHA-256 核对。历史文本如非 UTF-8 则原字节保留并在归档报告列明，不因终端乱码重写源码。包内排除用户存档、回放、密钥、私人设备/直播日志、缓存和本项目编译输出，保留构建必需的历史 marshal 与 AI 压缩语料；旧语料不自动成为本轮重新导出的训练集。
