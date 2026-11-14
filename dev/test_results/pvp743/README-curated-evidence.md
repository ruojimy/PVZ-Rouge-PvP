# PvP74.3 继承与精选证据

本包保留已审核 74.2 dev 的精选证据，并加入本次已经完成的合作人数入口、密集堆叠、实际梯带部署/客机显示、暴怒资源等报告与小型 JSON。证据目录沿用工作区路径；路径中 `pvp742` 只表示稳定工作目录，适用构建、输入、执行长度和限制以报告本身为准。

用户最新要求先出包、暂不实际测试，因此没有新增 74.3 全量回归，也不追加对局或实机测试。74.2 全量、三模式门禁和旧性能数字只对应历史构建，不能作为新版本已经通过同等验收的结论。此前全量含原有 FAIL/ERROR，不能称全绿。

完整原始日志、逐步 JSONL、大型状态、私人 getprop/logcat/直播样本不随源码包分发；链接因此可能缺少相应原始文件。新 manifest 的 `curated_evidence.omitted_document_references` 逐项说明取舍，不用占位或伪造结果替代缺失证据。测试源码与 runner 完整保留。

本机交付前后的 `userdata-before.json`、`userdata-after.json` 含用户文件路径与哈希，只留本地，打包器明确拒收；仅聚合的 `local-delivery-verification.json` 可进入开发者包。

`test_results/PVP743-EVIDENCE-SHA256SUMS.txt` 校验本次选入的文件；整个开发者包的 `SHA256SUMS.txt` 覆盖继承及新增载荷。`build/pvp743-tools/source-inheritance.json` 是源码摘要核对，不是新测试结果。任何通过结论都不能扩展到未触发的长周期机制、未复现现场或尚未进行的实机验证。
