# 暴怒材质资源复核

当前默认绿色纯色块仍未复现，不将下面的关联修正或受损资源事务修正称为用户绿块根因。用户所见的平台、具体界面、版本与本地材质包状态尚未确定，未再次询问或据此擅自覆盖用户数据。

## 实际共享路径

独立测试源是 `src/uitools/pvp742_rage_resource_audit.cpp`，没有改写 root 新增的 UI9 项或旧原型。基线与修后都调用真实工坊、原图加载、PNG编解码、包持久化与 NativeArt 状态缓存。修后另验证实际“相关部件”浏览器出现四个编辑按钮，并逐个打开原尺寸、原像素画布。

- 原图 `icon:石化火炬-蓝火` 为128×128，59种可见颜色、9027个可见像素、2366个蓝青像素；编码/解码后RGBA完全相同。
- 实际“暴怒→原图→保存→返回→再开”，以及导出材质包后导入，像素保持相同。
- 明确构造的单层绿色旧材质包能保留其编辑内容，即使停止启用该包；这属于保留编辑文件的既有语义。该合成夹具不代表用户本地状态，也不证明默认原图会变绿。单层夹具点击原图并保存后恢复蓝色。
- 蓝火世界资源的自定义覆盖、关闭覆盖及revision失效后，NativeArt能恢复原像素；派生黑白仍为灰度。
- 将原图复制到中文名称的模拟Android私有解包根目录，真实共享 `original()` 在无桌面资源回退的情况下成功读取图标、蓝火与秃树桩，RGBA一致。没有在此PC进程执行Android JNI AssetManager或文件选择器。

证据：[基线](rage-resource-before-r1/summary.json)、[修后严格6/6](rage-resource-after-r2/summary.json)、[共享UI9/9](rage-resource-ui-after-r1/summary.json)。截图中 `synthetic-green-editor.png` 是故意导入的绿色夹具，不能当作用户绿块复现截图。

## 已确认的关联遗漏与最小修正

原清单仅把暴怒关联到完整卡面图标。组合规则检查卡牌name包含“石化火炬”，但暴怒的name是“暴怒”，只有asset包含“石化火炬-蓝火”，因此实际组件没有出现在其相关部件列表。

修改 `tools/pvp74_resource_catalog.py`，保留旧正常石化火炬关联规则，按name/asset的石化语义补入四个已经存在的实际输入：

- `world:蓝火炬1`
- `world:蓝火炬2`
- `world:蓝火炬3`
- `raw:图片/火炬树桩-秃.png`

秃树桩是 `NativeArt.petrified_torch` 原有石化调色的原图输入，不是新造的一张替代图。它仍是共享源资源，不声称本次建立了暴怒专属资源槽。

重新生成 `extract/data/texture_resources74.json` 后，4175项资源、230张可编辑卡牌、尺寸、文件映射、完整卡面、草坪/石块排除及正常石化火炬关联全部保持不变。精确差分仅上述四条cards数组各追加 `zsecret:暴怒`。3058个原图/图集文件的前后摘要一致；已审核暂存中的额外内容PNG也逐项与当前来源核对一致。没有重烘焙PNG、改战斗图集或改变战斗逻辑。

证据：[清单精确差分](rage-resource-catalog-diff/summary.json)、[额外内容PNG](rage-resource-catalog-diff/additional-content-assets-proof.json)。该目录保留原始前后清单及被保护资源摘要。

## Android与缓存边界

`src/app/main.cpp` 的正常Android升级在App初始化之前，通过AAssetManager直接读取APK，按带版本/构建run的stamp覆盖内部资源；缺文件或写入失败拒绝继续使用旧资源。`texture74_model.cpp::original` 对 `图片/` 使用 `native_image_directory`，对烘焙图标使用data目录的资源根；本轮未发现正常升级中把旧PNG读出再写回的路径。

库存和缩略图在进程中有缓存，纹理revision变化会清对应显示缓存；这不等于支持外部直接覆盖资源PNG后的无重启热更新。正常APK升级会重启进程。没有用未经观察的热替换、VPN或保存包假设解释用户现象。

## 受损或缺失原图下的编辑事务修正

另一个已确证风险位于 `src/ui/hand/texture74_model.cpp::open_resource`。原逻辑先保存旧编辑、把 `selected_key` 改成新资源，再加载新画布。若加载缺失或受损PNG失败，实际操作入口会显示错误，但旧画布已经挂在新资源身份下；继续编辑并保存可能写入错误条目。

故障注入仅将隔离夹具内暴怒 `Resource.file` 临时指向不存在的路径，未移动、删除或修改任何原始PNG。旧画布是明确创建的绿色脑光墓碑材质，并带一处未保存笔画。真实 `action(card, 暴怒)` 在旧生产实现中得到以下结果：

| 检查 | 修前 | 修后 |
| --- | --- | --- |
| 加载失败后保留旧资源键 | 否，变为暴怒键 | 是 |
| 保留旧画布像素 | 是 | 是 |
| 保留未保存标记 | 否 | 是 |
| 继续一笔并保存错误创建暴怒条目 | 是 | 否 |

修正先复制参数键（兼容直接传入 `state().selected_key` 的别名），完整构造新画布，然后保存旧编辑，最后以不分配内存的字符串/容器成员swap同时提交新身份与画布。加载失败在保存旧编辑之前发生。保存异常仍向上抛出并恢复原dirty标记。相同键重开时从尚未保存的实际图层准备新画布，保留原有先保存再重开的语义。

新增独立回归同时验证多图层名称、透明度、像素以及相同键别名重开；既有原图、保存重开、绿色旧包保留、状态滤镜、Android目录解析及四部件关联继续通过。

证据：[修前事务失败观察](rage-open-failure-before-r1/open-failure-observation.json)、[修前7/8](rage-open-failure-before-r1/summary.json)、[修后事务观察](rage-open-failure-after-r1/open-failure-observation.json)、[修后8/8](rage-open-failure-after-r1/summary.json)、[既有实际UI9/9](rage-open-failure-ui-after-r1/summary.json)。两项hooks检查和单job生产UI库/专项编译均通过；日志 `rage-open-failure-before-build-r1.log`、`rage-open-failure-after-build-r1.log`。以上只证明受控缺原图时的错挂画布路径已修复，未证明用户正常默认资源遭到了同样故障。

仍未覆盖：用户具体的失败界面及本地包、真实Android文档选择器/导出目标、同stamp人工替换资源、分配失败注入以及完整长会话。保留“默认绿色纯色块未复现”。
