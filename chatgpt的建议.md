我会给 Claude 的不是一份“功能清单”，而是一份**架构宪法（Architecture Constitution）**。

因为项目成败不在于 Claude 会不会写代码。

而在于：

> 你有没有在 Day 1 就锁定正确的产品边界。

---

# AlphaNode v1.0

## Personal Investment Memory OS

### 核心定位

AlphaNode 不是：

* 看盘软件
* 交易软件
* 券商软件
* 行情终端

AlphaNode 是：

> 一个记录、分析、优化投资决策的个人投资操作系统。

核心目标：

```text
帮助用户减少重复犯错

而不是帮助用户获取更多信息
```

---

# 一、产品原则（不可违背）

## Principle 1

Investment Memory First

所有功能必须服务于：

```text
Decision
→ Outcome
→ Reflection
→ Improvement
```

闭环。

---

## Principle 2

Local First

所有核心数据本地存储。

默认不依赖云。

```text
SQLite
Parquet
本地文件系统
```

优先。

---

## Principle 3

AI Native

AI不是聊天框。

AI是系统能力。

例如：

```text
自动复盘

自动归因

自动标签

自动模式发现
```

---

## Principle 4

No Information Overload

拒绝：

* 新闻流
* 社区
* 热榜
* 推荐股票

AlphaNode 不提供投资建议。

只分析用户自己的行为。

---

# 二、MVP范围（V1）

仅开发三个模块。

---

# Module 1

Decision Journal

投资决策日志

---

用户每次开仓必须记录：

```text
标的

方向

价格

仓位

理由

风险

目标

预期持有周期
```

---

数据结构：

```sql
decisions
```

```sql
id

symbol

action

entry_price

position_size

investment_thesis

risk_statement

target_price

holding_period

emotion_tag

created_at
```

---

情绪标签：

```text
FOMO

Conviction

Fear

Greed

MeanReversion

Momentum
```

---

# Module 2

Portfolio Memory

持仓记忆系统

---

记录：

```text
当前持仓

历史持仓

收益率

最大回撤

仓位变化
```

---

表：

```sql
positions

position_history
```

---

核心功能：

自动关联：

```text
开仓记录

平仓记录

最终收益
```

形成：

```text
Decision
→ Result
```

链路。

---

# Module 3

Reflection Engine

复盘引擎

---

每周自动分析：

```text
过去7天

过去30天

过去90天
```

---

输出：

### Top Winning Patterns

```text
盈利最多的行为模式
```

---

### Top Losing Patterns

```text
亏损最多的行为模式
```

---

### Behavioral Insights

```text
最容易犯错时间

最容易亏损场景

最佳交易环境
```

---

这是V1最重要模块。

---

# 三、技术架构

## Frontend

```text
Tauri v2

React 19

TypeScript

TailwindCSS

shadcn/ui

TanStack Query

TanStack Router
```

原因：

Claude生成质量最高。

---

## Backend Core

```text
Rust
```

职责：

```text
SQLite访问

加密

本地文件管理

数据计算
```

---

## Database

V1只允许：

```text
SQLite
```

禁止：

```text
Postgres

Redis

Timescale

MongoDB
```

---

建议：

```text
sqlx
```

---

# 四、目录结构

```text
alpha-node/

src/
├── pages/
├── components/
├── features/
│
├── journal/
├── portfolio/
├── reflection/
│
├── shared/
│
└── lib/

src-tauri/
├── commands/
├── database/
├── models/
├── services/
└── migrations/

data/
├── sqlite/
├── exports/
└── backups/
```

---

# 五、数据库设计

## decisions

```sql
CREATE TABLE decisions (
 id TEXT PRIMARY KEY,

 symbol TEXT NOT NULL,

 action TEXT NOT NULL,

 entry_price REAL,

 position_size REAL,

 thesis TEXT,

 risk_statement TEXT,

 target_price REAL,

 holding_period TEXT,

 emotion_tag TEXT,

 created_at DATETIME
);
```

---

## trades

```sql
CREATE TABLE trades (

 id TEXT PRIMARY KEY,

 decision_id TEXT,

 exit_price REAL,

 pnl REAL,

 pnl_percent REAL,

 closed_at DATETIME
);
```

---

## reflections

```sql
CREATE TABLE reflections (

 id TEXT PRIMARY KEY,

 period TEXT,

 report TEXT,

 created_at DATETIME
);
```

---

# 六、V1 UI

只做四个页面。

---

Dashboard

```text
总资产

收益率

最近交易

行为统计
```

---

Decision Journal

```text
新增决策

历史决策
```

---

Portfolio

```text
当前持仓

历史持仓
```

---

Reflection

```text
AI复盘报告
```

---

结束。

---

# 七、AI集成（V1）

不要Agent。

不要MCP。

不要Deep Research。

---

只做：

## Reflection LLM

输入：

```text
过去90天交易记录
```

输出：

```text
赚钱模式

亏钱模式

纪律问题
```

---

支持：

```text
OpenAI

Claude

Gemini

Qwen

DeepSeek
```

统一接口。

---

建议：

```text
LiteLLM
```

适配。

---

# 八、V2规划

只有V1稳定后才能开始。

---

增加：

### MCP Server

工具：

```text
get_decisions

get_positions

get_reflections
```

---

### Local AI

```text
Ollama
Qwen
DeepSeek
```

---

### Research Engine

```text
财报分析

研报生成

新闻归纳
```

---

# 九、Claude Code开发顺序

## Sprint 1

项目初始化

```text
Tauri

React

Tailwind

SQLite
```

---

## Sprint 2

Decision Journal

CRUD

---

## Sprint 3

Portfolio

收益计算

---

## Sprint 4

Reflection Engine

规则版（先不用AI）

---

## Sprint 5

接入LLM

生成复盘报告

---

## Sprint 6

导出

备份

数据恢复

---

# 最终目标

不要让 Claude 开发：

```text
股票软件
```

而要让 Claude 开发：

```text
Personal Investment Memory OS

个人投资记忆操作系统
```

这是整个项目最重要的方向约束。

如果你现在就准备启动开发，我建议下一步直接产出 **《AlphaNode_PRD_v1.md》+《AlphaNode_Architecture_v1.md》+《AlphaNode_Database_Schema_v1.sql》+《Claude_Code_Master_Spec.md》** 四份正式工程文档，让 Claude Code 按 Spec-Driven Development 直接开始生成项目骨架。这样后续 80% 的代码都能围绕统一架构自动生成，而不会越写越乱。
