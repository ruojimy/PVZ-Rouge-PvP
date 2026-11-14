# PvP74.3 r2 内存修复与边界

真实双进程TCP合作、铁道扩展第8天、同初始存档/种子、普通生产allocator，各300秒。Windows SDL接口驱动且桌面锁屏，不作为前台FPS验收。

|指标|r1/R5|r2/R6|
|---|---:|---:|
|房主Private初末MiB|585.35→848.15|584.79→649.86|
|房主requested-live初末MiB|237.44→379.40|237.45→248.85|
|120秒后requested-live MiB/分钟|33.08|4.40|
|120秒后Private MiB/分钟|50.35|5.61|

aliases64观察记录已剥离，实际canvas.alias保留；10000tick观察记录130000→0，完整state/native/RNG/frame/pixels相同。300秒两端退出0、安全阈值未触发、主机native_projections=0且aliases64全程0。

修后存活栈仍见输入/业务日志、文字缓存和当前快照/地图副本；不能统称泄漏，也不能全算业务历史。长期与跨局上限、历史客机10GB现场仍待验证。采样器DbgHelp会增加Private，因此上表只用普通allocator对照。
