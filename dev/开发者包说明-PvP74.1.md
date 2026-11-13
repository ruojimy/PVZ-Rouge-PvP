# PvP74.1 开发者包

保留项目原生目录布局。Windows CMake 构建入口为根 CMakeLists.txt；Android 入口为 android/。生产内核在 build/typed72-integrated-v44/source，组合源为 build/typed72-match-v1。

材质系统由 src/ui/hand/texture74_*.cpp 拥有，UI 翻译后需运行 tools/pvp74_apply_hooks.py，构建自动检查接入完整性。资源清单由 tools/pvp74_resource_catalog.py 生成，完整卡面图标由 pvp74_texture_audit 的 bake 模式经生产绘制器生成。详见 AGENTS.md、更新说明-PvP74.1.md、PvP74.1_进度.md。

UI 重新生成后还要运行 tools/pvp741_apply_hooks.py，保留共用压力控制、藤蔓平铺及渲染缓存接入。详细算法、实测及精选证据位于 docs/PVP74.1_空间优化与验收.md 和 docs/evidence/pvp741/。

运行时的图片、音乐、音效和 relay.json 使用同版本 PC 游戏包中的文件。将三类资源目录与 relay.json 放到 build/Release/，供资源清单生成和 Android 出包使用；Windows 运行时也可将生成的程序放入游戏包目录。Android 的 cjk.ttf 可从同版本 APK 的 assets/fonts/ 提取，放入一个 fonts/cjk.ttf 暂存目录并通过 PVZ_ANDROID_ASSET_STAGING 指向它。Android SDK、NDK、SDL 依赖与个人签名密钥由开发环境另行配置。

包内没有用户存档，材质显示覆盖与原始战斗资源分离。

PvP74.1 共用生产代码同时用于 Windows 与 Android。图鉴、回归约束与本轮定向验收详见 PvP74.1_进度.md。
