# 神经网络 AI · 本地训练与推理

当前研究版：**ai-nn-20261114-r1**，基于 PvP74.3 r2。已完成 Windows 原生/WSL 部署、首轮训练、三组参数比较与留出对局评测。正式游戏默认 AI 继续使用 r22，实验模型单独运行。

## 下载与运行

| 下载 | 内容 |
| --- | --- |
| [Windows 研究运行包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/ai-nn-20261114-r1/PvZ-PvP-AI-NN-20261114-r1-Windows.zip) | 已编译C++推理程序、SDL、当前语料、模型与checkpoint；解压运行“运行神经网络AI.cmd” |
| [最新完整开发者包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/ai-nn-20261114-r1/PvZ-PvP-Native-20261114-ai-nn-r1-Developer-Package.zip) | 当前全部 7533 个源/依赖/数据/精选证据文件，含生产拥有源、生成器及神经网络工具 |
| [SHA-256](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/ai-nn-20261114-r1/AI-NN-SHA256SUMS.txt) | 两个下载包的校验值 |
| [模型 JSON](../dev/test_results/ai-nn-local-20261114/training-v1/model.json) · [PyTorch checkpoint](../dev/test_results/ai-nn-local-20261114/training-v1/selected.pt) | C++前向权重和继续训练用的权重 |

运行包是无头对局研究工具，输出战绩JSON，不打开正式游戏窗口。**原生推理无需Python或PyTorch**；继续训练使用Python/PyTorch，训练脚本会解压并校验随包数据集。

在解压根目录 PowerShell 中：
```powershell
./build/ai-nn/run-research.ps1 -Mode Play -Seat plant
./build/ai-nn/run-research.ps1 -Mode Play -Seat zombie
./build/ai-nn/run-research.ps1 -Mode Evaluate -Seat plant
./build/ai-nn/run-research.ps1 -Mode Train
```

从源码构建/准备数据见 [工具说明](../dev/build/ai-nn/README.md)。所有输出写入独立研究目录，正式游戏启动入口和玩家存档沿用原契约。

## 目前学了什么

共享单位网络以敌我单位集合的求和/最大值汇总，再结合英雄、资源和策略记忆进行决策；不输入卡名或实体ID，不按数量截断单位。通过 `IPlanner` 实际注入 `Session`，每1.5秒重规划，沿用r22控制器执行。

当前模型接管植物经济目标、植物进攻/防守模式、僵尸墓碑目标数。蓄资训练样本只有默认状态，继续由r22处理；卡牌优先级、配额和其余计划也保留r22。高压/魅惑、恢复和低血等守卫有定向检查。

## 实测结果

- 当前216组开局重导出成功，补齐禁卡构造/冷数据链。
- r22基线216局 × Linux两遍/Windows一遍，共648局：每遍108植物胜、73僵尸胜、35超时，0崩溃、0 AI异常。Linux逐文件/汇总相同，Windows日志/RNG及终局字段一致。
- 72组最多600秒轨迹，采样后11004条，按整张地图划分训练/验证/测试。三组参数比较选中隐层64、学习率.003。
- 留出54组，单独替换植物：27胜，r22基线24胜；单独替换僵尸：16胜，基线13胜。配对p=.5811/.5488，**尚不能确认强于r22**；超时始终计入分母。
- 300条状态、1200个分类的C++/PyTorch前向零分类差异；Windows/Linux逐字节一致，另有三组真实模型对局跨系统一致。
- 七个探针日志已补齐生产剥离、tick清理及门禁；648局七项终点计数均为零。完整GUI长时内存仍须单独验收。

[完整训练与内存报告](../dev/docs/ai-nn/本机部署与首轮训练_20261114.md) · [基线验证JSON](../dev/test_results/ai-nn-local-20261114/baseline-validation.json) · [强度JSON](../dev/test_results/ai-nn-local-20261114/model-strength.json) · [训练曲线/混淆矩阵](../dev/test_results/ai-nn-local-20261114/training-v1/report.json)

## 待办与边界

T22继续扩大长局/受压/魅惑样本、新种子与独立卡组，并调优经济决策。T23保留框架1项断言和旧V控制器5项参照差异；GUI主/客机长期内存、安卓模型/交互验收继续开放。这里的AI语料与前向验证不代替全产品回归。[完整T01–T23清单](../待办清单.md)。

正式 r2 的PC/安卓玩家包和原始源码仍在[正式发布页](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/tag/v1.6.0.74.3-pvp743)，该标签继续固定正式交付，不移动到研究源码。
