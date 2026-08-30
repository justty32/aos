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
├── every/                    生產者放的常駐指令；loop 每回合複製一份
├── turn                      loop 寫入的下一回合編號，從 1 開始
├── batch/<turn>/
│   ├── insts/                loop 匯聚出的本回合指令
│   └── out/                  loop 寫出的逐條執行結果
├── state.json                loop 寫的 running／idle 狀態與 agent 狀態鏡射
└── agents/<name>/            agent 自己寫的對話、狀態與工具往返資料
```

`inbox/` 的一個 JSON 檔就是一條只執行一次的指令；`every/` 的檔案不會被搬走，
而會在每回合以帶回合號的新 id 複製進 `insts/`。`state.json` 中的 agent 資訊來自
`agents/<name>/status.json`，loop 只原樣鏡射，不解讀內容。

## 一回合怎麼走

loop 先把 `inbox/` 搬入、把 `every/` 複製入本回合的 `insts/`；接著整批並行
fork/exec，等所有程式結束後逐條寫入 `out/`，更新 `state.json`，最後把 `turn`
加一。沒有任何指令時仍是有效的 idle 回合：狀態與回合號照樣更新。

## agent 與 LLM 在哪裡

agent 靠 `.aos/every/agent-<name>.json` 活著：loop 每回合複製一條 `step` 給它，
不是 agent 執行完再投遞下一個自己。因此只要常駐投遞檔還在，下一回合就仍會喚醒它。

`aos llm` 則是一顆能由單條指令呼叫的 CPU：prompt 從 stdin 進去，文字從 stdout
出來；它不是常駐服務，也不載入或卸載模型。在 `core/exec` 看來，它和其他被
fork/exec 的程式地位相同。

## 五個核心小專案

| 小專案 | 分工 |
|---|---|
| `core/exec` | 純函式庫的 POSIX 批次執行器 |
| `core/wire` | 純函式庫的指令、結果與 state JSON 序列化 |
| `core/loop` | 匯聚、並行執行與 loop state；提供 `run`、`deliver` |
| `core/llm` | OpenAI 相容的 LLM client；提供 `llm` |
| `core/agent` | 回合制資料夾 agent；提供 agent 操作指令 |
