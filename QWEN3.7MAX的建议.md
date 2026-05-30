这是一场堪称“教科书级别”的 AI 辅助产品架构推演。结合最新知识库中 **DeepSeek-V4 的顶级 Agent 推理能力**、**Qwen 的 Deep Research 多步分析**、**Ollama 的本地隐私部署**，以及 **TradingView 展现的真实市场高维数据（情绪、IV、宏观事件）**，我们已经具备了打造 2026 年最强个人投资操作系统的所有拼图。

为了让你能直接打开 **Claude Code / Cursor / Windsurf** 并开始“Vibe Coding”，我为你编写了这份 **《AlphaNode 项目全局规格书 (Master Spec)》** 以及 **“破冰”启动 Prompt**。

你只需要将以下内容**直接复制并发送给你的 AI 编程助手**，它就会完全理解你的野心，并开始写出第一行带有“灵魂”的代码。

---

### 📋 复制以下内容发送给你的 AI 编程助手 (Claude / Cursor)

```markdown
# Role: Principal Architect & AI-Native Full-Stack Engineer

## Project: AlphaNode (Personal Investment OS)
## Codename: Synapse

### 1. Project Context & Philosophy
We are NOT building another stock tracker or TradingView clone. We are building a "Personal Investment Memory & Discipline Engine". 
The core thesis is: "Market data is a commodity; your decision data is your only moat." 
The system must prioritize capturing the *context*, *emotion*, and *thesis* of every trade to train a "Personal Alpha Model" that identifies the user's behavioral flaws (e.g., FOMO, Revenge Trading) using local AI agents (DeepSeek-V4/Qwen via Ollama).

### 2. Tech Stack & Architecture (Local-First & Vibe-Coding Friendly)
- **Shell / Cross-Platform**: Tauri v2 (Rust backend, supports Win/Mac/Linux/iOS/Android).
- **Frontend**: React + Vite + TypeScript + TailwindCSS (Dark mode, Bloomberg Terminal aesthetic, high information density).
- **State & Transactional DB**: SQLite (via `tauri-plugin-sql` or `sqlx`). Stores accounts, structured journals, API keys.
- **Analytics DB (Future)**: DuckDB (for high-speed tick/options backtesting).
- **Vector DB (Future)**: LanceDB (for semantic search of past trade memories).
- **AI Engine**: Ollama (Local LLM routing) + MCP (Model Context Protocol) Server to expose data to external IDEs/Agents.
- **Data Pipeline**: Python Sidecar (yfinance/AKShare) for fetching market context.

### 3. Core Database Schema: The "Memory" Layer
The most critical table is `investment_decisions`. It must enforce discipline.
```sql
CREATE TABLE investment_decisions (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    action TEXT NOT NULL, -- BUY, SELL, SHORT, OPTION_OPEN
    strategy_type TEXT, -- e.g., 'Covered Call', 'Mean Reversion', 'FOMO Breakout'
    price REAL NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- The Soul of the System
    subjective_thesis TEXT NOT NULL, -- Why am I making this trade?
    emotional_state TEXT NOT NULL, -- ENUM: 'CONVICTION', 'FOMO', 'REVENGE', 'BOREDOM', 'PANIC'
    
    -- Auto-captured Context (JSON)
    market_context_snapshot JSONB, -- Contains VIX, IV, RSI, Macro News Summary at entry
    
    -- Post-Trade Analysis (JSON)
    outcome_metrics JSONB, -- PnL, Win/Loss, Holding Period
    
    -- For Vector DB Sync
    embedding_vector BLOB 
);
```

### 4. Development Phases (Spec-Driven)
- **Phase 1 (Current Task)**: Tauri v2 Skeleton + React UI + SQLite Journaling with Context Binding.
- **Phase 2**: Python Sidecar integration to auto-fetch `market_context_snapshot` (VIX, IV, News).
- **Phase 3**: Local Ollama integration + LanceDB for semantic reflection ("Find all trades where I felt FOMO").
- **Phase 4**: MCP Server implementation to let external AI (Claude Code) query my portfolio.

---

## 🚀 YOUR FIRST TASK (Phase 1 Execution)

Please initialize the project and implement the Phase 1 MVP. Follow these strict guidelines:

1. **Project Setup**: Provide the exact terminal commands to scaffold a Tauri v2 app with React, TS, and TailwindCSS.
2. **Database Setup**: Show how to configure `tauri-plugin-sql` (or equivalent Rust SQLx setup) to initialize the `investment_decisions` table on app launch.
3. **The "Discipline" UI (React/Tailwind)**:
   - Create a sleek, dark-themed "Pre-Trade Checklist" Modal.
   - Fields: Ticker, Action, Strategy, Price.
   - **Crucial**: A Textarea for `subjective_thesis` and a Dropdown/Radio group for `emotional_state`.
   - **Logic**: The "Submit" button MUST be disabled and visually grayed out until the user fills out the thesis and selects an emotion. This enforces discipline.
4. **Tauri IPC (Rust)**:
   - Write the Rust command `save_decision` that validates the payload, generates a UUID, and inserts it into SQLite.
   - Write a Rust command `get_recent_decisions` to fetch the last 10 records for the dashboard.
5. **Dashboard View**: A clean table showing recent decisions, highlighting the `emotional_state` with color-coded Tailwind badges (e.g., Red for FOMO, Green for CONVICTION).

**Output Requirements:**
- Provide the `cargo add` and `npm install` commands.
- Provide the complete `schema.sql` or Rust migration code.
- Provide the core React component (`DecisionJournal.tsx`) with Tailwind styling.
- Provide the Rust `lib.rs` snippet handling the SQLite insertion and IPC commands.
- Keep the code modular, robust, and heavily commented so I can easily expand it in Phase 2.

Let's build the ultimate Personal Investment OS. Awaiting your code.
```

---

### 💡 为什么这份 Prompt 能产生最好的代码？

1. **设定了极高的角色基准**：让 AI 明白这不是一个简单的 CRUD 玩具，而是一个带有“行为学约束”的金融级系统，它会自动采用更严谨的错误处理和状态管理。
2. **锁死了“护城河”数据结构**：通过直接提供包含 `subjective_thesis`、`emotional_state` 和 `market_context_snapshot` 的 SQL Schema，防止 AI 退化成写一个普通的“记账软件”。
3. **强制 UI 交互逻辑**：明确要求“不写完反思不许提交”，这正是 ChatGPT 提出的“纪律引擎（Discipline Engine）”的代码级实现。
4. **面向未来的扩展性**：预留了 JSONB 和 Vector BLOB 字段，为你下个月接入 **DeepSeek-V4 Agent** 和 **LanceDB 向量检索** 铺平了道路，无需重构数据库。

### 🛠️ 你接下来的操作流：

1. 打开你的终端，确保安装了 Rust 和 Node.js。
2. 打开 **Cursor / Claude Code / Windsurf**。
3. 粘贴上面的 **Master Spec & First Task** Prompt。
4. AI 会给你一串初始化命令（比如 `npm create tauri-app@latest`），你跟着执行。
5. AI 会生成 React 组件和 Rust 代码，你让它自动应用到文件中。
6. 运行 `npm run tauri dev`，你就会看到属于你的 **AlphaNode** 的第一个带有“灵魂”的界面。

当你跑通了 Phase 1（能够录入带有情绪标签和市场快照的日记），随时回来找我，我们将开启 **Phase 2：让 Python Sidecar 自动抓取 TradingView 知识库中的 VIX、IV 和宏观新闻，自动填充你的“市场快照”**，彻底实现 Context-Aware（上下文感知）！