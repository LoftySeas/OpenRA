# 翻译源记录：OpenRA 简体中文本地化

> 用途：记录所有外部翻译源、引用版本、未决事项。
> 维护：每批工作前后更新；提交时与本文件一起审查。

## 1. 主源

### 1.1 OpenRA/OpenRA PR #22531 "Add Chinese Localization"
- **作者**：Seaear（中文作者）
- **上游 PR**：[#22531](https://github.com/OpenRA/OpenRA/pull/22531)
- **PR 头 SHA**：`96c5ebf9fa9dcb01fa8ad7a5f43a7d3db823c564`
- **基准上游**：OpenRA/OpenRA `bleed`
- **基线 SHA（执行归档时）**：`a520984d91`（本地当前 HEAD）
- **本地参考分支**：`pr-22531`（已用 `git fetch origin pull/22531/head:pr-22531` 拉到本地）
- **基于**：俄语 PR [#22517](https://github.com/OpenRA/OpenRA/pull/22517) (moxx1234)
- **PR 状态**（2026-08-23 归档时）：Open
- **PR 自述**："约 7300 行翻译内容，跨 180 个文件，LLM 辅助生成"
- **上游讨论要求**：开始大规模重复翻译前应联系 Seaear 询问是否愿意协作；本计划遵循

### 1.2 4 个提交（按时间顺序）

| SHA | 作者 | 日期 (UTC) | 说明 |
|---|---|---|---|
| `4911cf2` | moxx1234 | 2026-06-17 07:28 | feat: language selection in settings（**多语言框架原型**） |
| `7dd4b49` | moxx1234 | 2026-06-22 06:18 | feat: Add russian localization（**俄语翻译，本计划不导入**） |
| `44f26e5` | Seaear | 2026-07-12 10:41 | Add Chinese localization（**中文翻译主体**） |
| `96c5ebf` | Seaear | 2026-07-12 13:22 | Add missing line breaks and improve formatting in Chinese localization files（**中文格式修正**） |

### 1.3 文件改动统计——分两层

**层 A：PR 4 个提交自身的净贡献**（来自 `git diff 4911cf2^ 96c5ebf`）

| 类别 | 数量 | 说明 |
|---|---|---|
| `.cs` 代码 | **7** | 真正的代码改动——干净 |
| 字体 | 2 | 待审计 |
| `fluent/zh/`（中文） | 33 | 目标资源 |
| `fluent/ru/`（俄语） | 33 | **不导入** |
| 战役 `map.ftl` | 272 | 翻译，混合 zh/ru/en |
| `mod.yaml` / `chrome/*.yaml` | 21 | 框架 yaml |
| `packaging/` | 0 | 干净 |
| **PR 自身总文件数** | **~370** | （同文件多个改不重复计） |

**层 B：与当前 bleed `a520984d91` 的全部差**（`git diff bleed..pr-22531`）

总计 **546 文件 / +18431 / -2236**——比层 A 多 170+ 文件，多出的全是 **bleed 自 PR 之后自身的演变**（MapGenerator 重命名、Directory.Build.props 升级 net8→net10、CI workflow 调整、csproj 演化等），与 PR 翻译工作无关。**移植时不要把这些当作 PR 改动带进来**。

### 1.4 PR 提交中**确实存在**的非翻译内容（必须排除）

| 来源提交 | 文件 | 性质 | 风险 |
|---|---|---|---|
| `44f26e5` | `mods/ra/translate_maps.sh`（新增） | 翻译辅助脚本 | 🔴 硬编码贡献者本机路径 `/Users/sns/source/repos/OpenRA/...`——个人路径泄漏，**不应入库** |
| `7dd4b49` | `OpenRA.Game/Manifest.cs` 等少量 .cs | 框架微调 | 🟡 与 4911cf2 框架互补，不引入俄语 .ftl |
| `7dd4b49` | `mods/cnc/mod.yaml`、`mods/d2k/mod.yaml` | 注册 FluentLanguage | 🟢 必要 |

> ⚠️ 之前版本 1.4 列表中的"MapGenerator 重构""OpenRA.sln""Directory.Build.props .NET 8 降级"等，**已确认为误判**——是 bleed 自身的演变，PR 没动。已从本节移除。

### 1.5 保留改动

仅以下类别应纳入翻译工作：

- `mods/*/fluent/zh/**/*.ftl`（33 个）
- `mods/*/maps/*/zh/map.ftl`（战役中文，~90 个）
- `mods/*/mod.yaml` 中 `FluentCulture: zh` 或 `FluentMessages` 加入中文 .ftl 的部分
- 字体（待审计）
- 必要的 `FluentReference` 属性标注（自动工具加入的 [FluentReference] 等小改）

### 1.6 字体（SourceHanSansCN）来源

- 源文件名：`SourceHanSansCN-Regular.ttf`、`SourceHanSansCN-Bold.ttf`
- 路径：`mods/common/SourceHanSansCN-Regular.ttf`、`mods/common/SourceHanSansCN-Bold.ttf`
- 已知别名：思源黑体 CN（Source Han Sans CN），Adobe 与 Google 合作的开源字体
- 默认许可证：SIL Open Font License 1.1（允许随 GPL-3.0 项目再分发）
- **待办**：在阶段 2 中确认实际文件中嵌入的 OFL 声明、文件大小、SHA1、覆盖字符范围

## 2. 联系人

- **Seaear**：中文 PR 作者。开始大规模重复翻译前应先通过 PR 评论联系，说明本计划会复用并校订其贡献。

## 3. 未决问题

1. PR #22531 实际合并后是否需要拆分？**结论：必须拆分**——见 1.4 节
2. 多语言框架移植是采用 PR 的 4911cf2 实现，还是用 blead 自身的更精简实现？**待阶段 1 决定**
3. 是否需要同时支持繁体中文（zh-TW）？**当前计划不涉及**——本计划只覆盖 zh-CN
4. 战役 map.ftl 中是否需要回退某些由 LLM 生成、可能影响任务目标的中文文本？**阶段 5 人工校订时处理**
