# aos 是什麼

← [文件索引](README.md)｜[使用方式](usage.md)｜[建置](build.md)

**aos 是一個「一個資料夾即一個世界」的回合制執行器：世界的持久狀態放在
`<folder>/.aos/`，每次由 `aos run` 推進一回合或多回合。**

它把投遞、執行結果與 agent 狀態都留在普通檔案裡；生產者只要投遞 JSON，loop
負責在清楚的回合邊界一次處理整批工作。

## 一個世界的版面

```text
<folder>/.aos/
├── inbox/                    生產者投遞的一次性指令；loop 每回合搬走
├── every/                    生產者放的常駐指令；loop 依到期條件複製
│   └── tick.json             心跳的常駐指令
├── tools/<name>.json         世界可用工具的逐項登記
├── contacts.json             其他 agent 世界的通訊錄
├── heartbeat/
│   ├── routines.json         固定循環的事務清單
│   ├── schedule.json         一次性行程清單
│   ├── config.json           選填的時區與錯過期限設定
│   └── log.md                有事發生的心跳記錄
├── turn                      loop 寫入的下一回合編號，從 1 開始
├── batch/<turn>/
│   ├── insts/                loop 匯聚出的本回合指令
│   └── out/                  loop 寫出的逐條執行結果
├── state.json                loop 寫的 running／idle 狀態與 agent 狀態鏡射
├── run.lock                  同一世界只允許一條 loop 的鎖
├── run.pid                   持續 loop 的 pid，供 aos stop 使用
├── run.log                   daemon loop 的 stdout／stderr
└── agents/<name>/            agent 自己寫的對話、狀態與工具往返資料
```

`inbox/` 的一個 JSON 檔就是一條只執行一次的指令；`every/` 的檔案不會被搬走，
而會在到期的回合以帶回合號的新 id 複製進 `insts/`。`state.json` 中的 agent 資訊來自
`agents/<name>/status.json`，loop 只原樣鏡射，不解讀內容。

## 一回合怎麼走

loop 先把 `inbox/` 搬入、把 `every/` 中到期的指令複製入本回合的 `insts/`；接著整批並行
fork/exec，等所有程式結束後逐條寫入 `out/`，更新 `state.json`，最後把 `turn`
加一。沒有任何指令時仍是有效的 idle 回合：狀態與回合號照樣更新。

## agent 與 LLM 在哪裡

agent 靠 `.aos/every/agent-<name>.json` 活著：loop 每回合複製一條 `step` 給它，
不是 agent 執行完再投遞下一個自己。因此只要常駐投遞檔還在，下一回合就仍會喚醒它。

`aos llm` 則是一顆能由單條指令呼叫的 CPU：prompt 從 stdin 進去，文字從 stdout
出來；它不是常駐服務，也不載入或卸載模型。在 `core/exec` 看來，它和其他被
fork/exec 的程式地位相同。

## 心跳與定期事務

`core/tick` 把定期事務接到既有 loop 上。`aos heartbeat init` 在
`.aos/every/tick.json` 放入 `aos tick`，讓 loop 定期喚醒機械式判定；`tick` 自己不呼叫
LLM，而是把到期的 argv 投進 inbox，或把 ask 訊息交給 agent。

心跳有兩張正本清單：`.aos/heartbeat/routines.json` 保存固定循環，
`.aos/heartbeat/schedule.json` 保存一次性行程。判定後更新清單，並只在有事件時追加
`log.md`。

## 世界層工具與通訊錄

`core/tool` 管世界可用的工具與世界間地址。每支工具各自登記在
`.aos/tools/<name>.json`，內容包含固定 argv 前綴、表述與參數方式；這一層只負責登記、
讀寫及探測，不負責實際執行。

`.aos/contacts.json` 保存其他 agent 世界的名字、資料夾與選填 agent 名稱。`aos say
--to <名字>` 依通訊錄跨世界投遞，`aos contact status` 則彙整自己與全隊的狀態、回合和
未讀數。`$HOME` 另有一個不必寫進通訊錄的天然 `~` 聯絡人。

## 七個核心小專案

| 小專案 | 分工 |
|---|---|
| `core/exec` | 純函式庫的 POSIX 批次執行器 |
| `core/wire` | 純函式庫的指令、結果與 state JSON 序列化 |
| `core/loop` | 匯聚、並行執行與 loop state；提供 `run`、`deliver`、`stop` |
| `core/llm` | OpenAI 相容的 LLM client；提供 `llm` |
| `core/tool` | 世界層工具登記表與 agent 通訊錄；提供 `tool`、`contact` |
| `core/agent` | 回合制資料夾 agent；提供 agent 操作與對話指令 |
| `core/tick` | 心跳判定與定期事務登記；提供 `heartbeat`、`tick`、`routine`、`schedule` |
