# PvP74 开发者包

保留项目原生目录布局。Windows CMake 构建入口为根 CMakeLists.txt；Android 入口为 android/。生产内核在 build/typed72-integrated-v44/source，组合源为 build/typed72-match-v1。

材质系统由 src/ui/hand/texture74_*.cpp 拥有，UI 翻译后需运行 tools/pvp74_apply_hooks.py，构建自动检查接入完整性。资源清单由 tools/pvp74_resource_catalog.py 生成，完整卡面图标由 pvp74_texture_audit 的 bake 模式经生产绘制器生成。详见 AGENTS.md、更新说明-PvP74.md、PvP74_进度.md。

包内没有用户存档，材质显示覆盖与原始战斗资源分离。
