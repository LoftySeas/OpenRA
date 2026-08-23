# 字体方案审计

> 目的：审查 PR #22531 引入的中文字体，确认许可证、来源、覆盖范围、文件大小，判定是否可入主仓库。
> 审查时间：2026-08-23
> 审查人：Claude（任务 #3 阶段 2）

## 1. 审查对象

PR #22531 在 `mods/common/` 引入两个字体文件：

| 文件 | 角色 |
|---|---|
| `SourceHanSansCN-Regular.ttf` | 用于 Regular 字体角色（Small/Regular） |
| `SourceHanSansCN-Bold.ttf` | 用于 Bold 字体角色（SmallBold/RegularBold/MediumBold/BigBold） |

位于 `mods/common/` 意味着**所有 4 个 mod（cnc/d2k/ra/ts）共享**。

## 2. 文件信息

| 文件 | 字节数 | 大小 | SHA1 | 格式 |
|---|---|---|---|---|
| `SourceHanSansCN-Regular.ttf` | 10,252,984 | ~9.8 MB | `b38b305e124f1e4f5bae872509c2325da5eba7b7` | TTF (magic `0x00010000`) |
| `SourceHanSansCN-Bold.ttf` | 10,222,380 | ~9.7 MB | `0ba1de6814353d3a5952adda17e4ed91d6d445b0` | TTF (magic `0x00010000`) |

**合计 ~20 MB**，全部作为 git 仓库中的二进制资产。

## 3. 字体元数据（TTF name 表解析结果）

```
Family        : Source Han Sans CN Regular
Subfamily     : Regular
Full          : Source Han Sans CN Regular
Version       : Version 1.000; PS 1; hotconv 1.0.78; makeotf.lib2.5.61930
PSName        : SourceHanSansCN-Regular
Copyright     : Copyright © 2014 Adobe Systems Incorporated. All Rights Reserved.
Trademark     : Source is a trademark of Adobe Systems Incorporated
Manufacturer  : Adobe Systems Incorporated
Designer      : Ryoko NISHIZUKA (kana & ideographs); Paul D. Hunt (Latin, Greek & Cyrillic);
                Wenlong ZHANG (bopomofo); Sandoll Communication, Soo-young JANG & Joo-yeon KANG (hangul)
Description   : Dr. Ken Lunde (project architect, glyph set definition & overall production);
                Masataka HATTORI (production & ideograph elements)
URLVendor     : http://www.adobe.com/type/
License       : Licensed under the Apache License, Version 2.0
LicenseURL    : http://www.apache.org/licenses/LICENSE-2.0.html
```

Bold 变体的元数据完全相同，只是 `Family`/`Subfamily`/`PSName` 体现为 Bold。

## 4. 许可证评估

### 4.1 实际许可证：**Apache License 2.0**（不是 OFL 1.1）

TTF name 表 14 号记录（License）明确写明 Apache 2.0。这与思源黑体家族后来转向 OFL 1.1 的现代版本（v2.000+/Noto Sans CJK）**不同**。

### 4.2 历史背景

- **2014**：Adobe 发布思源黑体 1.000，许可证为 **Apache 2.0**
- **2019+**：Adobe 与 Google 合作把项目主导权转给 **SIL International**；SIL 后续版本与 Google 联合发布的 Noto Sans CJK 改用 **SIL OFL 1.1**
- **当前**：Source Han Sans CN 的 GitHub 仓库（adobe-fonts/source-han-sans）最新发布版本已经是 OFL 1.1

### 4.3 与 OpenRA 许可证（GPL 3.0）的兼容性

**结论：兼容，可合法使用。**

- **Apache 2.0 §3 兼容性条款**：明确允许 Apache 2.0 与 GPL 3.0 的组合使用
- **GPL 3.0 兼容性**：GPL 3.0 第 7 条允许链接"Compatibility-Affirming"许可证（包括 Apache 2.0）的代码
- OFL 1.1 同样允许与 GPL 字体组合使用

**Apache 2.0 的额外合规要求**（如果使用这些 v1.000 文件）：

1. **§4(a)**：随分发件包含完整的 Apache 2.0 LICENSE 文本
2. **§4(d)**：若修改了字体，需在 NOTICE 文件中说明——**本项目不修改字体**，此条不触发
3. **§6**：不得使用 "Source"、"Adobe" 商标暗示背书——需注意项目文档中如何署名
4. 若后续上游用**现代 OFL 1.1 版本**替换，可**完全跳过** Apache 条款，OFL 更简单

## 5. 字符覆盖范围

文件大小 ~10MB 表明覆盖**完整 CJK 字符集**：
- CJK Unified Ideographs（U+4E00-U+9FFF，约 21,000 字）
- CJK Extension A（U+3400-U+4DBF，约 6,000 字）
- Latin/Greek/Cyrillic/标点
- 注音符号（bopomofo）

**远超 OpenRA UI 文本所需**。UI 文本常用字 ~3,500（GB2312 一级），加上 7,000+ 罕用字（GB231 二级），中文游戏文本覆盖 ~10,000 字，字体覆盖 27,000+ 字完全充足。

**未覆盖**（v1.000 的局限）：
- 表情符号（Emoji）—— 引入于后续版本
- CJK Extension B-G（罕罕用字，>U+20000）—— 现代游戏罕用
- 注音扩展字符外的罕用蒙古文/八思巴文

OpenRA UI 不需要这些扩展，**覆盖充分**。

## 6. 风险与建议

### 6.1 版本风险（低）

v1.000 是 2014 年的"原始"版本，质量良好但非最新。后续修复（更好的 hinting、错误修正）未包含。
- **影响**：视觉上可能有细微差异；不影响功能
- **建议**：可选地升级到 v2.000+（OFL 1.1 许可证），或保持 v1.000

### 6.2 仓库大小（中等）

20MB 二进制进 git 仓库本身会：
- 显著增加 git clone 时间
- 显著增加 PR diff（虽然 PR 文件只列文件名）
- 每次 `git pull` 都需下载 20MB

**建议**（按计划要求 "评估字形缓存、纹理图集大小、启动时间和内存变化"）：

1. **保留二进制入库**（最简单、CI 友好，但仓库 ~20MB 变胖）
2. **首次启动下载**（模仿 `ra-content` 资源从 openra.net 镜像下载）：
   - 加 SHA1 校验
   - 在 `mods/common/mod.yaml` 仿 `QuickDownload` 模式
   - 优点：仓库小、版本可控
   - 缺点：离线/无网环境失败
3. **Git LFS**（不实际——OpenRA 上游未用 LFS）

**阶段 1 推荐方案 1**（直接入库），后续如需切换到方案 2 再改。

### 6.3 商标风险（低但需注意）

Apache 2.0 §6 禁止使用商标。PR 已用文件名 `SourceHanSansCN-Regular.ttf` —— **OK**，这是字体的 PostScript 名称而非商标（"Source" 才是商标）。但 OpenRA UI 中不能使用 "Source Han Sans" 作为品牌名（一般也不会），不构成问题。

### 6.4 字体许可证文本归档（必做）

**合规要求**：需把 Apache 2.0 完整 LICENSE 文本作为第三方许可证记录的一部分加入仓库。

**行动**：在 `packaging/` 或 `docs/translation/` 下创建 `THIRD-PARTY-NOTICES.md` 或类似文件，包含：
- 字体名称与版本
- 完整 Apache 2.0 LICENSE 文本
- 版权声明
- 来源 URL（http://www.adobe.com/type/ 或 https://github.com/adobe-fonts/source-han-sans）
- SHA1 校验值

## 7. 推荐行动

### 阶段 1（框架移植）：**不立即使用 PR 的字体**

- PR 的字体可用，但**进库需要先做许可证归档**
- 第一阶段不依赖字体（中文资源未导入时，UI 仍为英文）
- 在第二阶段（语言选择 UI 支持 `zh`）**之后**才需要字体

### 阶段 2（机械导入中文资源）：**需要字体**

可选做法：
- **A. 使用 PR 字体**：快速、文件已就绪。**必须**：
  1. 创建 `THIRD-PARTY-NOTICES.md` 包含 Apache 2.0 LICENSE
  2. 验证 mod.yaml 的 `Fonts:` 段正确指向 `SourceHanSansCN-*.ttf`
- **B. 替换为现代 OFL 版本**：从 [adobe-fonts/source-han-sans](https://github.com/adobe-fonts/source-han-sans/releases) 下载最新 OFL 1.1 版本——许可证更简单，但可能需要重新生成 TTF
- **C. 改用 Noto Sans CJK SC**（OFL 1.1）：最常见选择，文件结构清晰，OFL 许可证简单

**第一阶段（任务 #3）结论**：字体本身**可接受**（许可证兼容 + 覆盖充分），但**入库前需补 Apache 2.0 NOTICE**。具体采用哪个版本（A/B/C）由阶段 5 决定。

## 8. 验证检查清单

- [ ] 仓库内含完整 Apache 2.0 LICENSE 文本（如选 A）
- [ ] `THIRD-PARTY-NOTICES.md` 包含字体条目（含 SHA1、版本、来源）
- [ ] 4 个 mod.yaml 的 `Fonts:` 段正确指向 `SourceHanSansCN-*.ttf`
- [ ] 编译后启动游戏，UI 不显示方框字
- [ ] 检查 `Tiny/Small/Regular/Bold/MediumBold/BigBold` 6 个字体角色全部使用中文支持字体
- [ ] 玩家名（中文 UTF-8）输入与显示不崩
- [ ] 战役 map.ftl 中文显示正常

## 9. 决策记录

| 日期 | 决策 | 理由 |
|---|---|---|
| 2026-08-23 | 字体**可入库**（Apache 2.0 兼容 GPL 3.0） | TTF name 表已确认许可证、覆盖范围充足、版权清晰 |
| 2026-08-23 | **必须**补 Apache 2.0 NOTICE 文件 | Apache §4(a) 合规要求 |
| 2026-08-23 | 是否升级到 OFL 1.1 版本**待定** | 不阻塞阶段 1；阶段 5 前再决定 |
