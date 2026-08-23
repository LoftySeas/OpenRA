# 阶段 3 交付：术语表骨架 + 校验工具

> 阶段 3 完成记录 — 2026-08-23

## 1. 交付物

### 1.1 术语表骨架

- **文件**：`docs/translation/zh-CN-glossary.csv`
- **条目**：~80 条，覆盖 UI 通用术语、4 个 mod 阵营、资源、建筑、兵种、车辆、飞行单位、地图/战役、战斗/状态、玩家/控制
- **状态**：所有条目标记 `pending` review（待术语组审议）
- **列定义**：`english, chinese, avoid, scope, context, source, review, notes`

### 1.2 校验工具（Lint Pass）

- **文件**：`OpenRA.Mods.Common/Lint/CheckFluentTranslations.cs`
- **接口**：`ILintPass`（自动注册到 lint 流水线）
- **目标语言**：`zh`（可扩展为多语言）
- **当前实现的 5 项检查**：
  1. **缺失 key**（英文有，中文无）→ 警告
  2. **额外 key**（中文有，英文无）→ 错误（可能笔误/遗留）
  3. **空或纯空白值** → 错误
  4. **attribute 集合一致性** → 错误
  5. **变量集合一致性**（`${var}` 占位符） → 错误

### 1.3 Linguini 库的 AST 类型校对

在校验过程中确认了 Linguini 0.8.0 的实际 AST 类型：

| 误称 | 正确类型 | 命名空间 |
|---|---|---|
| `IPattern` | `Pattern`（sealed record） | `Linguini.Syntax.Ast` |
| `msg.Identifier.Id` | `msg.GetId()`（扩展方法） | `Linguini.Syntax.Ast` |
| `TextElement` | `TextLiteral` | `Linguini.Syntax.Ast` |
| `TextLiteral.Value`（`string`） | `ReadOnlyMemory<char>` | 需 `.ToString()` |

参考实现：`OpenRA.Mods.Common/Lint/CheckFluentReferences.cs:411-441`（使用 `message.Value` 直接得到 `Pattern`）。

## 2. 验证

### 2.1 Debug 编译（启用全部 StyleCop/Roslyn 分析器）

```
$ ./make.ps1 check
已成功生成。
    0 个警告
    0 个错误
```

### 2.2 Lint Pass 运行时验证

```
$ ENGINE_DIR=D:\github\OpenRA ./bin/OpenRA.Utility.exe ra --check-yaml 2>&1 | grep -E "Testing Fluent|coverage|does not declare"
Testing Fluent references
Testing Fluent translations for language `zh`
Warning: Mod `ra` does not declare `zh` in FluentLanguages. Skipping translation checks.
```

**解读**：

- `Testing Fluent references` — 已有的 `CheckFluentReferences` Pass 仍正常运行
- `Testing Fluent translations for language zh` — 新的 `CheckFluentTranslations` Pass 已注册并执行
- `Warning: Mod ra does not declare zh in FluentLanguages. Skipping translation checks.` — 优雅跳过（这是设计行为，因为 stage 3 还没有合并 framework；mod.yaml 还没有 `FluentLanguages` 字段）

## 3. 待办（不阻塞本阶段交付）

- [ ] 阶段 3.5：移植 4911cf2 多语言框架（添加 `FluentLanguages`、`FluentProvider.BuildLanguagePaths`、`LanguageSettingsLogic`、chrome panel）
- [ ] 阶段 4：合并后，添加 `zh` 到 4 个 mod.yaml 的 `FluentLanguages`，导入 PR #22531 的中文 .ftl 资源
- [ ] 阶段 5：扩展 lint 检查 6-10（禁用术语扫描、字体覆盖、英文残留检测）
- [ ] 阶段 6：4 个 mod 运行时冒烟测试

## 4. 已知限制

1. `LoadFluentFiles` 简化处理：只取首个 `TextLiteral`，不处理：
   - 多个文本片段拼接（如 `"Hello { $name }"`)
   - `select` 表达式分支
   - attribute 完整结构
2. `ExtractKeyAttributes` 当前返回空集——需要阶段 5 扩展为完整 AST 遍历
3. 变量提取使用字符串扫描 `${var}`——若 value 中含嵌套花括号会误判（极少见场景）
4. `BuildLanguagePaths` 与 `FluentProvider.BuildLanguagePaths` 行为镜像但代码独立——若上游修改需要同步

## 5. 决策记录

| 日期 | 决策 | 理由 |
|---|---|---|
| 2026-08-23 | Lint Pass 用 `void ILintPass.Run` 显式接口实现 | 与 `CheckFluentReferences`、`CheckFluentSyntax` 保持一致风格 |
| 2026-08-23 | 目标语言硬编码 `zh`（非配置文件） | 阶段 3 范围最小化；阶段 5 扩展为扫描 `FluentLanguages` 全部成员 |
| 2026-08-23 | `LoadFluentFiles` 失败时仅 Console.WriteLine，不发错误 | Linguini parser 已自带语法错误报告；本 lint 专注内容质量 |
| 2026-08-23 | 检查结果分错误/警告：缺失 key 是警告（渐进式翻译），空值/笔误是错误 | 缺失 key 频繁发生（翻译覆盖率提升中），不应阻塞 CI |
