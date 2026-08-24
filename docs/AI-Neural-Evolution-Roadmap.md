# OpenRA Neural Evolution AI Training Roadmap

## 目标

在 OpenRA 基础上开发一个类似现代 RTS 指挥官 AI 的系统：保留游戏引擎、寻路、单位控制、建造合法性和战斗执行，让机器学习负责战略决策。

核心原则：

> Neural Brain 决定做什么，OpenRA Bot Module 负责如何执行。

不要训练端到端鼠标操作 AI，而训练战略层。

---

# 总体架构

```
Game World
    |
    v
State Encoder
    |
    v
Neural Commander
    |
    +-- Economy Decision
    +-- Build Order Decision
    +-- Army Strategy
    +-- Attack / Defense Decision
    |
    v
OpenRA Existing Bot Modules
    |
    +-- ResourceMapBotModule
    +-- BaseBuilderBotModule
    +-- SquadManagerBotModule
    +-- HarvesterBotModule
```

---

# Phase 0: AI 数据接口

目标：让 OpenRA 可以记录训练数据。

新增模块：

```
OpenRA.Game/AI/NeuralBot/
    StateEncoder.cs
    ActionDecoder.cs
    NeuralBrain.cs
    FitnessCalculator.cs
```

输出状态：

```json
{
 "money":5000,
 "income":120,
 "harvester":3,
 "army_value":8000,
 "enemy_army_estimate":6000,
 "tech_level":3,
 "base_count":2,
 "map_control":0.55
}
```

---

# Phase 1: 参数进化

不要马上训练神经网络。

首先把现有 AI YAML 参数变成基因。

例如：

```
attack_time = 300
expansion_rate = 0.5
tank_ratio = 0.7
defense_weight = 0.4
risk_level = 0.6
```

算法：

- CMA-ES
- Genetic Algorithm

适应度：

```
fitness =
  win_rate * 10
  + economy_score
  + army_efficiency
  + map_control
  - idle_penalty
```

目标：先获得比原始 Normal AI 更强的策略。

---

# Phase 2: 战略神经网络

输入：

约 100~200 个聚合状态。

包括：

- 经济
- 科技
- 单位价值
- 地图控制
- 敌方威胁
- 历史观测

网络：

```
Input 128
   |
Dense 128
   |
Dense 64
   |
Output
```

输出宏观动作：

```
ATTACK
DEFEND
EXPAND
TECH
HARASS
SAVE_RESOURCE
PRODUCE_ARMY
```

不要输出单个单位移动。

---

# Phase 3: 进化训练

推荐算法：

## 第一选择

CMA-ES

适合：

- 少量参数
- 稳定优化

## 第二选择

Evolution Strategy

适合：

- 固定神经网络
- 并行模拟

## 第三选择

NEAT

适合：

- 网络结构自动发现

---

# 自博弈系统

训练环境：

```
AI Candidate
     |
     +-- Rush Bot
     +-- Turtle Bot
     +-- Normal Bot
     +-- Previous Best AI
```

每一代：

1. 生成候选 AI
2. 多地图比赛
3. 计算 Fitness
4. 保存优秀策略
5. 产生下一代

---

# 训练场景

必须包含：

- 小地图快速战
- 双矿经济战
- 防守地图
- 海战地图
- 空军地图
- 随机地图

避免 AI 过拟合。

---

# 难度系统

不要使用资源作弊。

调整：

```
reaction_delay
strategy_interval
prediction_accuracy
risk_tolerance
micro_skill
```

生成不同人格：

- Rush Commander
- Economic Commander
- Turtle Commander
- Adaptive Commander

---

# 推荐开发顺序

## Month 1

完成：

- 状态导出
- AI 对战自动化
- 战绩统计

## Month 2

完成：

- CMA-ES 优化 YAML 参数
- 自动生成 AI 性格

## Month 3-4

完成：

- Neural Commander
- 战略动作预测

## Month 5+

完成：

- 自博弈联盟
- MAP-Elites AI 人格库
- 微操模型

---

# 最终目标架构

```
             Neural Commander
                    |
      ------------------------------
      |              |              |
 Economy AI    Strategy AI    Combat AI
      |              |              |
      ------------------------------
                    |
             OpenRA Engine
```

这个方案适合个人 GPU 和 OpenRA 开源环境，可以逐步演进，不需要一次实现 AlphaStar 级系统。
