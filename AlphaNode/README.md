# AlphaNode — Personal Investment Memory OS

> 一个跨平台（Windows / macOS / Linux / Android / iOS）的**个人投资记忆操作系统**。
> AlphaNode 不是看盘软件，也不是交易软件。它帮助你**减少重复犯错**，而不是给你更多信息。

核心闭环：**Decision → Outcome → Reflection → Improvement**

---

## 这三份建议里，我们「取其精华，去其糟粕」

| 来源 | 采纳（精华） | 舍弃（V1 不做） |
| --- | --- | --- |
| **ChatGPT / Gemini** | 架构宪法、四大产品原则、3 大核心模块（决策日志 / 持仓记忆 / 复盘引擎）、清晰的 SQLite Schema、Local-First、统一 LLM 接口 | — |
| **QWEN** | **纪律引擎**（不写 thesis + 不选情绪 → 禁止提交）、`market_context` 快照、情绪标签枚举、彩色徽章、Bloomberg 暗色终端美学 | DuckDB / LanceDB / 向量库 / MCP Server / Python Sidecar / Ollama —— 全部推迟到 V2，避免 V1 过度工程化 |

> 关键取舍：**先把「记录 + 复盘」这个闭环做扎实、做到能跑、跨全平台**，再谈 AI Agent 与本地大模型。

---

## 技术栈

- **Shell / 全平台**：Tauri v2（Rust 后端，支持 Win/Mac/Linux/Android/iOS）
- **前端**：React 19 + Vite + TypeScript + TailwindCSS + TanStack Router/Query + Recharts
- **数据库**：SQLite（`tauri-plugin-sql`，Rust 迁移，**Local-First**，无服务器）
- **AI（V1）**：统一的 OpenAI 兼容接口，支持 OpenAI / DeepSeek / Qwen / Gemini / Moonshot / 本地 Ollama

---

## 功能模块（V1）

1. **Decision Journal 决策日志** — 每笔交易先记录 **WHY**（标的/方向/价格/仓位/理由/风险/目标/情绪）。
   - 🔒 **纪律引擎**：未填写至少 15 字 thesis 且未选择情绪状态前，「Commit Decision」按钮保持禁用。
2. **Portfolio Memory 持仓记忆** — 自动把开仓决策与平仓结果连成 `Decision → Result` 链路，计算已实现盈亏、胜率、敞口。
3. **Reflection Engine 复盘引擎** — 7d/30d/90d/全部周期：
   - **规则版**（本地、确定性、零依赖）：按情绪 / 策略 / 时间维度找出盈利与亏损模式。
   - **AI 版**（可选）：把脱敏摘要发给你配置的 LLM，生成行为洞察 + 一条可执行的改进纪律。
4. **Dashboard** — 总览：已实现盈亏、胜率、按情绪分布的盈亏柱状图、最近决策。

---

## 快速开始

### 前置依赖
- [Node.js](https://nodejs.org/) ≥ 18
- [Rust](https://www.rust-lang.org/tools/install)（`rustup`）
- Tauri 系统依赖：见 https://tauri.app/start/prerequisites/

> ⚠️ 建议把本项目复制到**本地磁盘**再开发。在网络共享盘（UNC 路径）上 `cargo` 编译会非常慢甚至失败。

### 安装与运行（桌面）

```bash
cd AlphaNode
npm install

# 生成应用图标（首次必须，否则桌面打包/运行会缺图标）
npx @tauri-apps/cli icon            # 可选：在后面接一张 1024x1024 的 png 作为源图

# 启动桌面开发模式
npm run tauri:dev
```

仅调试前端 UI（浏览器，不连数据库）：

```bash
npm run dev      # 注意：SQLite 仅在 Tauri 运行时可用
```

### 打包

```bash
npm run tauri:build
```

### 移动端（Android / iOS）

```bash
# Android（需要 Android Studio + NDK）
npm run android:init
npm run android:dev

# iOS（需要 macOS + Xcode）
npm run ios:init
npm run ios:dev
```

---

## 目录结构

```
AlphaNode/
├── src/
│   ├── components/AppShell.tsx        # 侧边栏 + 移动端底部导航
│   ├── routeTree.tsx                  # TanStack Router 路由
│   ├── lib/                           # db / llm / settings
│   ├── shared/                        # types / constants / format / ui 组件
│   └── features/
│       ├── dashboard/
│       ├── journal/                   # 决策日志 + 纪律引擎弹窗
│       ├── portfolio/                 # 持仓记忆 + 平仓
│       ├── reflection/                # 复盘引擎（规则版 + LLM）
│       └── settings/                  # LLM 配置
└── src-tauri/
    ├── src/lib.rs                     # 数据库迁移（schema 在此）
    ├── capabilities/default.json      # 权限
    └── tauri.conf.json
```

---

## 数据模型

- `decisions` — 开仓决策（含 `thesis`、`emotion_tag`、`market_context` JSON 快照）
- `trades` — 平仓事件，外键关联 `decisions`，存储已实现盈亏
- `reflections` — 复盘报告（规则版 / AI 版）历史
- `settings` — 键值配置（LLM provider 等）

完整建表语句见 [src-tauri/src/lib.rs](src-tauri/src/lib.rs)。

---

## 隐私

Local-First：所有数据存储在本机 SQLite。只有当你主动点击「AI Reflection」时，才会把**脱敏后的摘要**发送给你自己配置的 LLM 服务商。

---

## V2 路线图（V1 稳定后再做）

MCP Server · 本地 AI（Ollama）· 语义记忆检索（LanceDB）· 自动抓取市场快照（VIX/IV/新闻）· 财报/研报分析。
