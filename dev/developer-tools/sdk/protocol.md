# 原生开发接口 v1

独立候选提供：`PvZPvPNative.exe --developer-tools <request.json绝对路径> <response.json绝对路径>`。Windows原版r1没有此接口；不能只复制工具就获得接口。新候选不修改BUILD/规则哈希/卡池哈希/联机协议，另以adapter=native-devtools.1和developer_api=1标识；兼容性必须核对完整identity。

请求外层字段：protocol=1、operation、arguments对象；除capabilities外还须提供上次capabilities响应中的完整expected identity。未知字段/操作拒绝。响应为protocol、ok、operation、identity、result或error.code/message。退出0成功；2参数/协议/版本失败；3原生游戏拒绝；6输出文件存在或写入失败。禁止覆盖已有响应、回放或同ID地图。响应原子写入，失败的.pending需人工检查，不自动覆盖。

capabilities返回操作列表、游戏导出的地图schema/调色板/地图列表/回放格式，不携带自定义插件能力。export从运行时actual_card/RULES/describe导出JSON；cards为已解析值，raw_templates仅为基础模板，context标明night/secrets；不把这些JSON当可写配置或战斗时动态资源/CD的完整枚举。map-new调用真实生成器，map-check调用原生验证、房间地图提案、构建战斗并步进2tick。map-import再使用原生MapStore保存和重读，目录必须显式给出。replay-demo仅是有真实输入的短样本，replay-check调用正式reader/Playback到终点，而非JSON摘要比较。relay-probe仅连接127.0.0.1的指定临时服务，使用真实原生主客机双向传输。

错误CLI参数数量退出2并打印用法，不进入游戏界面。输出路径由用户或调用工具明确指定；不自动寻找源码、手机、玩家存档或公网服务器。Python进程实际打开路径和子进程命令记录在paths.json；原生数据/资源根目录同时列出。物理隔离发布包验收加静态调用链核验排除了旧Python游戏依赖；未声称收集了全系统文件I/O跟踪。

输入上限：请求16MiB、回放64MiB/120000房间tick、离线回放180秒、relay验收15秒；其余地图约束由原生schema给出。未知/非法输入必须返回错误，不能静默忽略。此接口是本地文件协议，未新增网络协议。
