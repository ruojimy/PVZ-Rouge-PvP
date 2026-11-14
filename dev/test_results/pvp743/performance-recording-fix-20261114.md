# 性能记录按钮崩溃修复（2026-11-14）

## 已复现的原因

原发布库在 SDL MOUSEBUTTONDOWN/UP 真实事件队列中点击“开始基础记录”或“开始详细记录”，均在点击当帧报 `TypeError: unsupported operand type(s) for -: num and absent`。第一现场位于 `AppProfiler::m_mark` 的 CPU 时间相减，由 `Application::m_render` 调用。

`Application.step` 在处理事件之前捕获本帧 profiler 并执行 begin；按钮在事件处理中才创建新 profiler。随后 render 重新获取新 profiler 并 mark，但新对象的 cpu_last 尚未由 begin 初始化。帧开始前直接调用 action 的旧测试无法覆盖此顺序，故此前直接调用成功不代表按钮正常。

拥有的 Python 源也存在同一初始化顺序；本次没有证据表明该特定崩溃来自 map.at 或丢失了原 Python 的 except。没有修改全局字典/数值异常语义。

## 修改

`tools/pvp72_sources/performance.py` 增加 frame_open 生命周期：构造及关闭时为 false，begin 完成后为 true，mark/end 只操作已开启帧，end 消费该帧，close 在 finally 中解绑。通过 pvp2cpp 重新生成 `src/ui/gen/pm_performance.{h,cpp}`。点击当帧不会被伪装为完整采样帧。

新增 `src/uitools/pvp743_profile_lifecycle_audit.cpp`，经过原 SDL 队列、Application.handle_events/step/render，覆盖两种初始模式、首次完整帧计数、切换模式、同帧两次启动、导出、停止、重启。正式构建文件未替换，内存问题仍在调查。

## 已完成验证

- 修复前真实按钮：基础和详细均复现 TypeError，原始记录在 performance-start-investigation/click-*-before。
- 原生回归：两组流程均通过；新对象点击帧 frame_count=0，下一完整帧=1，JSON 可解析。
- 真实双进程 TCP 合作：两种初始模式 × 主客机共4个生命周期流程均完成，双方完成标记存在、退出码0、没有强制终止。包括持续5秒后的自动导出。
- 检查12份导出 JSON：均可解析，浮点有限；主机有真实 native tick 增量，客机按显示采样记录。
- pvp74 / pvp741 hooks --check 通过，构建 pvzui 通过。
- 测试使用隔离 userdata。当前桌面锁屏，使用接口驱动的 Windows SDL，不声称前台人工/安卓真机验收。

合作流程原始证据：performance-start-investigation/results-coop-click-after-r2.json 及两个 coop-click-*-after-r2 目录。修复前入口直接调用的 host 两项因端口0未建房，不计合作覆盖；早期合作 r1 一端先退导致另一端未完成的流程不计通过。

## 回调自环补充修复

进一步加入 std::weak_ptr 检查后，原记录器替换时两组流程均失败：replaced profiler retained a self cycle。构造函数把绑定自身的 `_gc_event` 存入 `_gc_hook`，Python 可用循环回收，但当前原生对象的该绑定回调会保持自身存活。

现仅在绑定实际battle时创建回调，unbind移除全局回调并清空实例中的回调引用。带对象销毁断言的正式 CMake audit 两组均通过：模式切换、停止与再次停止后旧记录器 weak_ptr 均过期。此问题能影响开关记录的内存释放，但不能解释R5完全没有记录器时的房主增长。

额外构建并运行现有 pvp741_combat_audit 17/17、pvp742_performance_audit 6/6 均通过。它们是针对性回归，不是全量产品回归/安卓真机验收。
