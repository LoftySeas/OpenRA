# 框架移植设计：OpenRA 多语言支持

> 目的：分析 PR #22531 `4911cf2` 提交中的多语言框架，输出最小化移植方案，回答计划第 1 阶段的设计问题。
> 适用版本：当前 OpenRA bleed `a520984d91`
> 参考实现：moxx1234 在 PR #22517 / #22531 中的 4911cf2 提交

## 1. 框架原理（PR `4911cf2` 的实现）

### 1.1 数据流

```
GameSettings.Language (string, 默认 "en")
    ↓ 读取
ModData.Languages (从 Manifest.FluentLanguages 派生的 ImmutableArray<string>)
    ↓ 显示在 UI
LanguageSettingsLogic (ChromeLogic 控件)
    ↓ 用户选完保存
GameSettings.Language = "zh"
    ↓ 重启后
ModData.ctor 调 FluentProvider.Initialize(Manifest, fs, Game.Settings.Game.Language)
    ↓
FluentProvider.BuildLanguagePaths() 把 "ra|fluent/chrome.ftl" 扩展为
    ["ra|fluent/chrome.ftl", "ra|fluent/zh/chrome.ftl"]（如果存在）
    ↓
new FluentBundle("zh", allPaths, fileSystem)
    ↓
FluentBundle.AddResourceOverriding 加载所有路径
    → 英文路径在先提供基础 key
    → 中文路径在后的同名 key 覆盖英文
    → 中文没有的 key 自然回退到英文
```

### 1.2 关键设计特性

- **英文总是完整加载作为回退**（`FluentProvider.cs:30` 的 `if (language == "en") return basePaths;` 优化 + 后续的覆盖加载）
- **缺失 key 安全回退**：`FluentBundle.TryGetMessage` 找不到 key 时返回 false，外层 `FluentProvider.GetMessage` 返回 key 字符串本身——但因为英文已加载，几乎不会触发
- **不会覆盖地图文本**：`modFluentBundle` 优先于 `mapFluentBundle`（保留现有安全边界）
- **强制重启**：`LanguageSettingsLogic` 显示 "Language changes require restart" 提示，不热切换

## 2. 关键设计决策

### 决策 1：使用 `zh` 还是 `zh-CN` 作为代码标识符？

**推荐使用 `zh`**——理由：

- PR #22531 的所有实现（`FluentLanguages`、`GameSettings.Language` 值、`fluent/zh/` 目录、PR #22517 俄语 PR 的同类实现）都使用 `zh`（ISO 639-1 二字母代码）
- 已有的 `mods/*/fluent/zh/*.ftl` 文件（Seaear 提交的实际产物）也使用 `zh` 目录
- 与 BCP 47（`zh-CN`、`zh-TW`）虽然更精确，但**会与 PR 已经贡献的资源不一致**，需要全部重命名

**例外**：仅当未来真要支持 `zh-CN` 和 `zh-TW` 区分时，再升级到 BCP 47。

### 决策 2：目录命名 `fluent/zh/` vs `fluent/zh-CN/`

**推荐 `fluent/zh/`**——同上理由。

### 决策 3：缺失语言配置的安全回退

PR 已经隐式处理：

- `ModData.Languages` 从 `Manifest.FluentLanguages` 派生，默认 `["en"]`
- `GameSettings.Language` 默认 `"en"`
- 如果用户配置文件损坏，`FluentProvider.Initialize` 接收到 "en" 也会正常工作

**不需要额外迁移代码**——`GameSettings` 的字段反射加载机制，新字段缺失会得到默认值（"en"）。

### 决策 4：地图自带翻译是否覆盖官方 UI key？

**不应改变**——`FluentProvider.cs:60-65` 已经实现 "mod 级 bundle 优先于 map 级 bundle"。这是计划强调的安全边界，PR 保留了这个不变量（只是把硬编码 "en" 换成 "en" 或 language 参数）。

### 决策 5：lint（CheckFluentReferences）用什么 culture？

PR 把 `CheckFluentReferences.cs` 改为硬编码 `"en"`——**正确**。lint 应该用**英文基线**检查 key 完整性、变量集合一致性和 Fluent 语法，**不**应该用任何具体语言版本（因为是相对基线的偏差检查）。

### 决策 6：MapPreview 用什么 culture？

PR 把 `MapPreview.cs` 也改为硬编码 `"en"`——这是**简化选择**。合理，因为：

- 地图预览可能在用户没选好语言前就显示（早期启动阶段）
- 地图自带的 map.ftl 通常是英文原版
- 显示英文地图名/介绍对所有用户一致可读

**接受此设计**。

## 3. 移植需要触及的文件

按 PR 4911cf2 的 15 个文件清单，分类如下：

### 3.1 引擎核心（5 .cs，1 lint）

| 文件 | PR 改动 | 移植难度 | 备注 |
|---|---|---|---|
| `OpenRA.Game/FluentProvider.cs` | +29/-3 | 简单 | 新增 `language` 参数 + `BuildLanguagePaths` |
| `OpenRA.Game/Manifest.cs` | +6/-4 | 简单 | `FluentCulture` → `FluentLanguages` 数组 |
| `OpenRA.Game/ModData.cs` | +6/-8 | 简单 | `Languages` 派生自 Manifest |
| `OpenRA.Game/Settings.cs` | +3/-0 | 简单 | 加 `Language` 字段 |
| `OpenRA.Game/Map/MapPreview.cs` | +1/-1 | 简单 | 硬编码 "en" |
| `OpenRA.Mods.Common/Lint/CheckFluentReferences.cs` | +2/-2 | 简单 | 硬编码 "en" |

### 3.2 新增 UI（2 文件）

| 文件 | PR 改动 | 移植难度 | 备注 |
|---|---|---|---|
| `OpenRA.Mods.Common/Widgets/Logic/Settings/LanguageSettingsLogic.cs` | 新增 +81 | 中 | **需要扩展 `LanguageNativeNames` 字典**——PR 只填了 "en" |
| `mods/common/chrome/settings-language.yaml` | 新增 +56 | 简单 | chrome 布局，直接 copy |

### 3.3 Mod 清单（4 mod.yaml）

| 文件 | PR 改动 | 移植难度 | 备注 |
|---|---|---|---|
| `mods/cnc/mod.yaml` | +4 行 | 简单 | 加 `common\|chrome/settings-language.yaml` + `FluentLanguages: en` |
| `mods/d2k/mod.yaml` | +4 行 | 简单 | 同上 |
| `mods/ra/mod.yaml` | +4 行 | 简单 | 同上 |
| `mods/ts/mod.yaml` | +4 行 | 简单 | 同上 |

### 3.4 chrome 面板注册（2 yaml）

| 文件 | PR 改动 | 移植难度 | 备注 |
|---|---|---|---|
| `mods/cnc/chrome/settings.yaml` | +1 行 | 简单 | 加 `LANGUAGE_PANEL: button-panel-language` |
| `mods/common/chrome/settings.yaml` | +1 行 | 简单 | 同上 |

### 3.5 英文 fluent 新增 key（1 ftl）

| 文件 | PR 改动 | 移植难度 | 备注 |
|---|---|---|---|
| `mods/common/fluent/chrome.ftl` | +5/-0 | 简单 | 加 4 个英文 label key（settings-language 面板文本） |

**总计：15 个文件，~+200/-15 行**——与 PR 自身的规模一致。

## 4. 移植时需要扩展的内容（PR 漏掉的）

### 4.1 `LanguageNativeNames` 字典

PR 版的 `LanguageSettingsLogic.cs:23-27`：

```csharp
static readonly Dictionary<string, string> LanguageNativeNames = new()
{
    { "en", "English" },
};
```

**加入中文时需要扩展为**：

```csharp
static readonly Dictionary<string, string> LanguageNativeNames = new()
{
    { "en", "English" },
    { "zh", "中文" },
};
```

（需要决定：是否同时列出繁体、粤语等？第一阶段只 `zh`。）

### 4.2 翻译辅助脚本 `translate_maps.sh` 不能进库

`mods/ra/translate_maps.sh` 由 44f26e5 提交引入，含硬编码个人路径 `/Users/sns/source/repos/OpenRA/...`。**移植时排除**。

## 5. 实施步骤（按提交粒度拆分）

按计划要求，每次提交只覆盖一个清晰模块：

### 提交 1：`Add selectable Fluent language infrastructure`（纯框架）

复制 4911cf2 的 15 个文件改动。**不**带任何中文资源。验证：

- `./make.cmd all` 编译通过
- 启动游戏 → 设置中应出现 "Language" 面板 → 只能选 "English" → 改回 "en" 行为不变
- 检查英文 UI 文本与原 bleed 完全一致

### 提交 2：`Add zh to LanguageNativeNames and FluentLanguages for all mods`

仅修改 5 个文件：

- `LanguageSettingsLogic.cs`（扩展字典）
- 4 个 mod.yaml（`FluentLanguages: [en, zh]`）

**不**带任何 .ftl 文件。验证：UI 出现 "English" 和 "中文" 两选项，切换后启动仍为英文（因为还没有中文资源）。

### 提交 3：`Import initial zh-CN Fluent resources from PR #22531`（仅资源）

仅 `mods/*/fluent/zh/**/*.ftl` 和 `mods/*/maps/*/zh/map.ftl`（中文版战役翻译）。**不**动任何代码。

验证：编译通过，启动游戏，UI 文本变中文；缺失 key 回退英文；map.ftl 中的战役文本显示中文。

### 提交 4：`Add zh-CN translation validation tooling`

新增 `OpenRA.Mods.Common/Lint/CheckFluentTranslations.cs`（或类似），做计划第 6 阶段定义的检查。**不**在第 1 阶段交付。

### 提交 5：`Add CJK font support`

仅字体 + mod.yaml 的 `Fonts:` 段调整。

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| PR 是基于旧 bleed，部分文件与新 bleed 有冲突 | 实际只有 7 个 .cs 改动 + 1 个 lint，API 兼容（`IReadOnlyFileSystem.Exists` 存在），`Settings.cs` 加字段、yaml 加列表项都是 append-only，预计无冲突 |
| 切换语言后没真重启导致显示异常 | UI 已显示"restart required"提示；mod data 初始化只发生一次 |
| `LanguageSettingsLogic` 字典扩展滞后 | 在合并任何中文 .ftl 前先提交字典扩展 |
| 7dd4b49（Russian）也动了 Manifest.cs | 我们的提交 1 只采用 4911cf2；如果 7dd4b49 的 Manifest.cs 改动有价值需单独评估（暂未看到） |
| MapPreview 硬编码 "en" 让中文地图名/介绍不能显示中文 | 接受此限制；非关键场景，地图可在游戏内自切换 |

## 7. 验证清单

完成提交 1 后，**纯英文行为必须与原 bleed 完全一致**：

- [ ] `./make.cmd all` 0 警告 0 错误
- [ ] `./make.ps1 test` 通过
- [ ] `./make.ps1 tests` 通过
- [ ] 启动游戏 → 设置 → 看到 "Language" 面板
- [ ] 语言下拉框只有 "English"
- [ ] 选 English → 改回默认 → UI 文本与原 bleed 完全一致
- [ ] Mod YAML 验证（每个 mod 都有 `FluentLanguages: en`）
- [ ] 删除 `FluentLanguages` 字段后，ModData.Languages 仍为 `["en"]`（默认值）
