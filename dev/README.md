# PvP74.2 开发者源码与精选证据

本目录保留项目原生布局，包含当前 Windows/Android 共用 C++ 源码、全部测试源码、生成工具、数据、素材图集、类型化生产内核和组合层拥有源。PC全量2366项与上一正式版逐项一致：2324 PASS、30 FAIL、12 ERROR，无新增非通过；不能称全绿。三模式类型化门禁通过。Android签名/库/资源已核验，同场景实机性能尚待调试端口恢复；两类群友崩溃和长期内存增长未宣称解决。

当前入口：根 `CMakeLists.txt` 构建 Windows 游戏；`android/` 构建 Android。生产内核是 `build/typed72-integrated-v44/source/src/sim/typed/`，不是早期 `src/sim/typed/`。组合层拥有源为 `build/typed72-match-v1/`，实际编译的生成结果及清单在 `src/sim/typed72_app/composition/`。参照和约定见 `AGENTS.md`。

本轮结果见 [性能与交付验收](docs/PVP742_性能与交付.md) 和 [专项验收与剩余问题](docs/PVP742_专项验收与剩余问题.md)。精选证据按文中相对路径镜像在 `test_results/`；选入的文件另有 `test_results/PVP742-EVIDENCE-SHA256SUMS.txt`。证据取舍见 [精选证据说明](test_results/pvp742/README-curated-evidence.md)，完整原始日志、大型状态及个人设备/直播采样没有随源码包分发。

历史 README 保存在 `docs/history/README-before-PvP74.2.md`。历史版本的完成情况与测试数字只对应当时构建。`build/ai-nn/` 离线语料、`docs/ai-nn/` 训练规格、开发工具迁移材料和 `extract/live/` 等必要参考输入保留；旧语料不会因源码更新自动成为 74.2 训练集。

## Windows

需要 CMake 3.20+、Visual Studio 2022 C++ 工具链及 Python 3.8（原异步夹具AST指纹在3.8生成，完整回归请用3.8；系统3.13的AST不同）。Python 只用于构建/生成/测试，正式游戏不依赖 Python 解释器。SDL 开发依赖位于 `third_party/`，包括根 CMake 所需的 `lib/x64` 文件；第三方预编译依赖不属于项目自身编译产物。

```powershell
python -I -B tools/typed72/make_app_composition.py --check
python -I -B tools/pvp74_apply_hooks.py --check
python -I -B tools/pvp741_apply_hooks.py --check
python -I -B tools/typed72/make_ai_lobby_bridge.py --check
cmake -S . -B build/dev742 -G "Visual Studio 17 2022" -A x64
cmake --build build/dev742 --config Release --target PvZPvPNative --parallel 1
```

若 CMake 选择了不合适的 Python，请配置 `-DPython3_EXECUTABLE=<解释器完整路径>`。不要因为修改了早期阶段源码就认为正式内核已改变。改组合层后用 `make_app_composition.py` 重新生成；重新翻译 UI 后应用两个 hooks，再执行检查。新审计程序和回归入口在 `src/uitools/`、`src/cpptests/`、`tools/test/` 与 `tools/typed72/`，可按同名 CMake target 构建。

运行资源需要同版本正式 PC 游戏包中的 `图片/`、`音乐/`、`音效/`、`relay.json`，不能仅靠源码启动完整游戏。将这些运行资源及本包的 `extract/data/`、`extract/assets/`、`fonts/` 放到新 EXE 可识别的运行目录中；运行目录以现有游戏资源路径约定为准。根 `启动PvP.cmd` 保留原生入口形式，开发者应指向自己验证的新构建，不能假定源码包内存在预编译 EXE。本包不附带用户存档。

## Android

Windows 与 Android 使用同一套生产内核、组合层和大部分 UI/模拟代码。Android 依赖 Android SDK/NDK、Java/Gradle、SDL Android 头文件和对应 ABI 预编译库，需由开发者环境提供。脚本中历史机器的默认路径仅是兼容默认值，使用前显式设置环境变量。

原生编译入口：

```bash
export PVZ_ANDROID_NDK=/path/to/android-ndk
export PVZ_ANDROID_SDL_DIST=/path/to/sdl-dist
export PVZ_ANDROID_WORK=/path/to/native-work
export PVZ_NATIVE_RUN_ID=local-pvp742
bash android/build_native.sh arm64-v8a 1
```

APK 打包还需要 `PVZ_ANDROID_SDK`、`PVZ_ANDROID_GRADLE` 和 `PVZ_ANDROID_ASSET_STAGING`。资源暂存目录须有 `fonts/cjk.ttf`；可从同版本授权游戏资源/APK 获得。`android/build_apk.sh` 还会读取 `build/Release/图片`、`音乐`、`音效` 和 `relay.json`，先将同版本 PC 运行资源准备到该位置。字体目录 `fonts/` 中的许可证应随分发保留。

`build_apk.sh` 接受 versionCode、versionName 和 ABI，必须绑定同一次 `PVZ_NATIVE_RUN_ID` 的已校验原生候选。签名密钥、密码环境文件、SDK 本地配置和上一个已签名 APK 由开发者自行提供；本暂存不包含它们。正式升级仍须验证包名、版本号和签名连续性，不能用测试存档覆盖用户数据。

## 来源与封包

`MANIFEST-PvP74.2.json` 逐文件记录来源类别、相对来源路径、大小和 SHA-256；`SHA256SUMS.txt` 校验载荷和该清单。`STAGING_STATUS.json` 明确未完成的发布门禁。来源分为已审核的上版 dev 基底、当前工作区拥有源和本轮新说明。

本暂存排除用户存档、回放、个人日志、原始 getprop/logcat/直播快照、密钥、Python 缓存和本工程编译输出。第三方构建依赖、必要的历史 marshal 输入以及 AI 压缩训练语料仍保留。打包脚本位于 `build/pvp742-tools/package_dev742.py`；当前只做 staging 和哈希复核，最终ZIP附本轮完整回归与精选证据；手机未实测状态会保留在说明和STAGING_STATUS中。ZIP 名称由 Python `zipfile` 以 UTF-8 写入，并按实际 Unicode 码点与清单核对；不要依据终端乱码重建文件名。旧包实查的中文文件名及其 UTF-8 标志正确，新工具额外对所有条目强制 UTF-8 标志。

完整回归请通过Python3.8运行 `tools/run_cpp_suite.py`，并准备该脚本列出的原始只读测试夹具、字节码oracle和同版本运行素材。可用 `tools/test/pvp742_regression_compare.py` 对照已有完整结果，原断言和指纹不应因解释器升级而重写。
