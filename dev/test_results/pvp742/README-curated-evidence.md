# PvP74.2 精选证据

本目录只镜像开发者说明和两份 PvP74.2 验收文档引用的摘要、专项 assessment、精选小型 JSON，以及少量固定输入诊断文本。路径与工作区保持一致，便于按文档相对链接核对。

独立摘要不会自动构成完整原始输入、完整长时状态、日志或实机验收。完整的大型 state、逐操作 JSONL、原始 getprop/logcat、直播/玩家进程快照和个人设备信息未随包分发。文档中指向这些原始文件的链接可能在源码包中缺失；对应取舍在根 MANIFEST-PvP74.2.json 的 `curated_evidence.omitted_document_references` 中列出。为避免伪造原证据，没有把缺失原始文件替换成占位结果。

`test_results/PVP742-EVIDENCE-SHA256SUMS.txt` 校验所有选入的证据，包根 SHA256SUMS 也覆盖它们。测试源、runner 和拥有源仍完整包含在源码目录中。本包已收录最终全量r4、逐项对照及typed gate；Android实机结果仍未取得，以具体报告中的版本、EXE 摘要、输入、运行长度及明确限制为准，不把摘要里的“通过”扩展到未测试情形。
