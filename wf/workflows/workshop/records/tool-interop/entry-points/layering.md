# aos 工具協作 — 主輪：分層與已知前提

← [本檔索引](README.md)｜[本場索引](../README.md)｜[workshop](../../../README.md)

主輪畫出的整體層次：pi 的已知前提、誰在上面誰在下面、stdout→stdin 的界線，以及 coding agent 的 session 為什麼只能當快取。

---

## 主輪：aos 怎麼跟現有工具協作

### pi 與本場的已知前提

這裡的 pi 是 [`earendil-works/pi`](https://github.com/earendil-works/pi)，不是泛稱，也不是本機 PATH
上的 `agy.exe`。使用者已親口更正：**`agy.exe` 是 Gemini 的，不是 pi。**

pi 是 TypeScript／Bun 的極簡 coding agent 終端，包含多供應商 LLM API、agent runtime 與互動 CLI；
狀態在 `~/.pi/agent/`，session 按工作目錄保存。對行程整合有 `-p/--print`（可吃 stdin）、
`--mode json`（JSON lines 事件）、`--mode rpc`；可用 `--no-session`、`--session <path|id>`、continue、
resume、fork。它從 `~/.pi/agent/skills/`、`.agents/skills/`、`.pi/skills/` 找 skill，也會讀
`AGENTS.md`／`CLAUDE.md`。

更關鍵的是它**明文不做三件事**：不做 MCP，建議「CLI＋README／Skill」或 extension；不做權限
彈窗，把隔離交給 Gondolin／Docker／OpenShell；不做 sub-agent 與 plan mode。這與 aos 近幾輪收回
內建 orchestration／權限系統的方向很接近，也直接限制了 pi 的接法。

使用者原本的方向是：

> 我預期的是，**這些 coding agent 可以是入口，然後 aos 作為他們的 MCP 或 tool set**。
> 也可以讓 **aos 產出的 stdout 導向到 coding agent 的 stdin**。

四位都說方向成立，但要拆成不同 agent 的原生入口：**pi 不是 MCP 路徑；pi 走 skill＋CLI（或日後
extension），支援 MCP 的其他 agent 才走 MCP façade。**

### 誰在上面、誰在下面

四位共同畫出的層次是：

```text
使用者
  │
  ▼
coding agent（pi／Codex／Claude…）── 管對話、session、批准與既有 read/bash tools
  │  skill／CLI tool-call，或 MCP typed tool-call
  ▼
aos CLI／共用 lib ──────────────── 管 Deliver、Status、Exec 的磁碟回合語意
  │
  ▼
world folder ───────────────────── 真相：queue、.runi、kernel、request／result
```

資深工程師的句子收得最短：

> **CLI 是共同母語，skill 與 MCP 只是入口；磁碟上的 request／result 才是契約。**

這個方向同時支援兩種產品場景：

1. **coding agent 是入口。**人在 pi／其他 agent 對話，agent 依 skill 或 MCP 呼叫 status、deliver，
   視權限再 exec。這是使用者原話最直接的版本。
2. **aos 批次召喚 coding agent。**world／driver 準備 request，啟動 `pi -p`／其他 CLI，安全保存結果，
   再由 agent 的 tool-call 或 driver 推進下一步。

工程師與架構師**兩位獨立地都問**：第一個真正要做好的產品場景是哪一個？兩者可共用 CLI，
但互動批准、session、結果捕捉與 crash 責任不同。

### stdout → stdin 能成立，但不能拿 `aos exec` raw stdout 當協定

**四位獨立地都指出**：`aos exec` 會直接承接任意子指令 stdout，平行時還可能交錯；把它管進
`pi -p`，模型收到的是無 envelope 的混合文字，無法知道來源、turn、成功與否。

追問輪之後，閉環的下半段也改了：

```text
aos 的專用 request／context 輸出 ──► pi -p／其他 agent 的 stdin
                                        │
                                        └─ agent 直接 tool-call `aos deliver`
                                           （不再把 stdout 送進 ingest parser）
```

主輪提出過 `aos prompt`／`aos emit`，但追問輪研究人員明確收回整條 `prompt|pi|ingest`，其餘三位也
只收斂了 Deliver，**沒有收斂出一支新的 context exporter**。所以使用者說的 stdout→stdin 可以作為
方向，但目前只知「不能是 raw exec stdout」；究竟由 `status --json`、request file，還是日後專用
`prompt／emit` 供應上下文，仍缺答案。

### coding agent 的 session 只可當快取

**四位獨立地都先選 `--no-session` 作可攜預設**：對話歷史／request 留在 world，看得見、可搬、
可重建；pi session 若啟用，只加速續談，不能成為世界唯一真相。`--fork` 也只 fork agent 快取脈絡，
不定義 aos 子世界身分。

四位主輪都提到把 pi session 放 `W/.aos/pi` 或 `W/.aos/adapters/pi/sessions`，並使用
`--session-dir`。但本場提供的 pi 介面事實只列 `--session <path|id>`、continue、resume、fork，
**沒有列出 `--session-dir`**；四位也都標記 JSON event／RPC／session 磁碟格式是否跨版本穩定為
不確定。因此這段不能寫成可用命令：要先核對 pi 實際支援的 session 定址方式，再決定如何把綁定
記進 world。
