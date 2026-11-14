# sdl_shim

类型化内核只在一处用到 SDL：`sim/typed/native_art.cpp` 的 `NativeArtStore::pixels()` 用 `SDL_SoftStretch` 做 RGBA32 精灵的最近邻缩放。无头构建在没有 SDL2 开发包的机器上用这里的两个文件代替：

- `SDL.h`：只声明那一处用到的四个函数和两个类型。
- `sdl_shim.cpp`：按 SDL 2.28–2.30 `SDL_stretch.c` 的最近邻算法（16.16 定点步进，起点偏半步）重写的整幅缩放。

**没有和真实的 SDL 二进制对比过。** 写它的环境里没有 SDL，也不能联网取源码，算法是按记忆写的。在有 SDL2 的机器上用 `-DAI_NN_SDL=system` 构建一次，跑同一批对局对比日志摘要，就能验证。

`pvz_sdl_shim_stretch_calls()` 返回本进程里这个缩放函数被调用的次数，`headless_match` 会把它打印到标准输出，用来判断一局对局有没有走到这条路径。

游戏本体不使用这个目录。
