# aos-agent：把一個 agent 資料夾走一格（第 2 版，**草稿**）

← [proto5 README](../README.md)｜資料夾：[agent.md](agent.md)｜問模型：[aos-llm-call.md](aos-llm-call.md)｜送件：[kernel.md §2](kernel.md)、[cpu.md §3.3](cpu.md)

> 2026-09-23 草稿，取代第 1 版。**程式還沒照這份改**：現在的 `aos_agent.py` 仍是舊版（直接往 llm cpu／tool cpu 放單）。
> 這版：問模型、跑工具**都是往 kernel `add --once` 的普通工作**；agent 只認識 kernel 一個入口。

一句話：**`aos-agent [dir]` 先看 `waits` 這道門——還在等就退出；門開了就把狀態機走一格：`idle` 收輸入、`think` 問模型、
`act` 跑工具，問跟跑都是「寫一份 inst、往 kernel 放單、等回音檔、讀結果、ack」。**
反覆叫它是 kernel 的事（agent 自己就是 kernel 裡的一個反覆行程）。

## 0. 名詞（白話）

| 詞 | 意思 |
|---|---|
| 走一格 | 叫一次 `aos-agent`，照 `state` 做一件事就退出 |
| 門 | `state.json` 的 `waits`；還有沒到的檔就這格不走，退 101 |
| 放單 | 用 `aos_client` 往 `K/requests/` 放一則 `add`（`once: true`），檔名就是這件工作的名字 |
| 回音檔 | `K/responses/<名>.json`；內容只有執行狀態（code／kind／timed_out／stopped），模型答案跟工具輸出在 agent 家自己的檔裡 |
| ack | 讀完回音後往 `K/requests/` 放一則 `ack`，kernel 才刪回音（[cpu.md §3.3](cpu.md)） |
| 工作名 | `<agent 資料夾名>-<epoch ns>-<pid>`（工具再加 `-<i>`）；inst、輸入、輸出檔都用它取名，所以看檔名就知道是哪件 |

## 1. 用法

```
aos-agent [dir]
```

`dir` 留空＝`.`，必須是 agent 家（`NotAnAgent`）。沒有別的旗標。

## 2. 門怎麼判

每次被叫、讀驗完、走格之前：

1. 逐條看 `waits`。到了的：先照 `consume` 處理（有開才 rename `.done`），再從表裡劃掉（按索引改原始 JSON）。
2. 表還有剩 → 把改過的 `waits` 寫回、退 101。
3. 表空了 → 寫回（空陣列）、照 `state` 走一格。

所以「一部分到了」的進度會留下來。人要它暫停就加一條指到不存在的檔（例如 `continue.json`）、要它繼續就 touch 那個檔。

## 3. 走一格

先讀驗（[agent.md](agent.md)：`info.json`／`state.json` 每格解指示詞、指到的檔原樣讀）；讀驗不過＝退 1、什麼都不寫。

| 現在是 | 情況 | 做什麼 | 寫回 `state` | 退出碼 |
|---|---|---|---|---|
| `idle` | `input` 有東西 | 接進記憶、rename `.done` | `think` | 0 |
| `idle` | 沒東西 | 不動 | 不變 | 101 |
| `think` | 記憶尾巴是帶 `tool_calls` 的 `assistant`（上次崩在寫記憶跟寫 state 之間） | 自癒，不問 | `act` | 0 |
| `think` | 沒有在途的問（§3.1 第 1 步） | 送出一份「問模型」工作、加門 | 不變 | 0 |
| `think` | 回音到了、跑成功 | 讀 `llm-out/<名>.json` 接記憶、`errors`＝0、ack、清工作區 | 有 `tool_calls` → `act`；否則 `idle` | 0 |
| `think` | 回音到了、跑失敗 | stderr 一行、記憶不動、`errors`＋1、ack、清工作區；第三次見 §3.4 | `think` | 0 |
| `act` | 記憶尾巴不是帶 `tool_calls` 的 `assistant` | 沒東西可跑 | `think` | 0 |
| `act` | 記憶尾巴已經接了整批 `tool` 訊息（上次崩在寫記憶跟寫 state 之間） | 自癒：ack 還沒 ack 的、清工作區 | `think` | 0 |
| `act` | 沒有在途的工具 | 每個 call 送一份工作、加一條 `all` 門 | 不變 | 0 |
| `act` | 全部回音到了 | 照原順序組 `tool` 訊息接記憶、ack 全部、清工作區 | `think` | 0 |

「有沒有在途」看 `waits` 裡有沒有指到 `K/responses/` 的條目——工作名就寫在路徑裡，不用另外記。

### 3.1 think：問一次模型

1. 取工作名 N。寫 `insts/N.json`（字面 inst、路徑全絕對）：

   ```json
   {"argv": ["aos-llm-call", "/abs/agent-bob"], "cwd": "/abs/agent-bob",
    "stdout": {"$opt": "mkdir", "$val": "/abs/agent-bob/llm-out/N.json"},
    "stderr": {"$opt": ["append", "mkdir"], "$val": "/abs/agent-bob/log/llm.err"}}
   ```

   `argv[0]` 就寫 `aos-llm-call`，靠那顆 cpu 的 PATH 找（[cpu.md §4.1](cpu.md)）；金鑰也是那顆 cpu 的環境給的。
2. `aos_client` 放單：`add`，`target`＝`/abs/agent-bob/insts/N.json`、`name`＝N、`once: true`、`pool`＝`info.llm.pool`、
   `timeout_ms`＝llm.json 那筆的 `timeout_ms` 加 5000（HTTP 逾時交給 aos-llm-call 自己，這裡只是保險）。
   `AlreadyExists`／`-32602` 等 kernel 退件＝當引擎失敗（`errors`＋1、stderr 一行）。
3. `waits` 加一條字面 `"<K>/responses/N.json"`（不開 consume），寫回。
4. 下一次門開：讀回音（先查原單再查回音是 `aos_client` 的事）。**成功**＝`result` 且 `kind=child`、`code=0`、`timed_out=false`、`stopped=false`
   → 讀 `llm-out/N.json` 那一行 JSON 當 assistant message（照 agent.md §3.2 驗，不合＝`MessageInvalid`、退 1、不 ack），
   接記憶、`errors`＝0。其他（`error`、`kind=aos`、非 0、逾時、被停）＝引擎失敗。
5. 寫記憶 → ack → 刪 `insts/N.json`、`llm-out/N.json` → 寫 state。

### 3.2 act：跑工具

記憶尾巴那則 `assistant` 的每個 `tool_calls[i]`：

1. 按 `function.name` 找工具；找不到＝這個 call 不送，回音時直接給模型「沒有這個工具：xxx」。
2. 工作名 `N-i`。`arguments` 字串原樣寫成 `tool-in/N-i.json`。`_meta` 先以 agent 家為中心 `aos_inst.load_obj` 解成字面 inst、
   路徑全絕對，再補 `stdin`＝`tool-in/N-i.json`、`stdout`＝`tool-out/N-i.json`（mkdir），寫成 `insts/N-i.json`。
3. 放單：`add`，`target`＝那份 inst、`name`＝`N-i`、`once: true`、`pool`＝`info.tool_pool`、`timeout_ms`＝`_timeout_ms`。
   放單失敗的 call 當「跑不起來」，其他照送。
4. `waits` 加一條 `{"$opt": "all", "$val": [所有送出去的回音檔路徑]}`，寫回。
5. 全到了：照 i 的順序組每個 call 的 `tool` 訊息（`tool_call_id` 對應）：

   | 回音 | `content` |
   |---|---|
   | `result`、`code=0`、沒逾時沒被停 | `tool-out/N-i.json` 整份文字 |
   | `timed_out=true` | 「工具 xxx 逾時（N ms）：」＋已有的 stdout |
   | `code≠0`（child） | 「工具 xxx 失敗（exit n）：」＋stdout |
   | `kind=aos`、`error` 非 Interrupted | 「工具 xxx 跑不起來：」＋一行原因 |
   | `error.data.code=Interrupted`、或 `stopped=true` | 固定 `{"ok": false, "error": "結果不明：工具可能已經跑了，也可能沒有"}` 的 JSON 字串 |
   | 沒送（找不到工具、放單失敗） | 「沒有這個工具：xxx」／「工具 xxx 跑不起來：」＋原因 |

6. 全部訊息一起寫記憶 → ack 全部 → 刪這批的 inst／in／out → 寫 state。
   同一則 assistant 叫多個工具，只保證接回的順序，**不保證執行順序**（kernel 可能派到不同 cpu 平行跑）。

### 3.3 寫入順序與自癒

- 一格只寫：`state.json`（原始 JSON 只動 `state`／`waits`／`errors`）、記憶檔、`input`／`consume` 的 rename、工作區的檔、K 的 request／ack。
- **先寫記憶、再 ack、再寫 state**。崩在記憶之後：下次靠記憶尾巴自癒（表裡兩列）；崩在 ack 之前：回音還在，自癒那列會補 ack
  （ack 指到已經不在的回音是 no-op，多送無害）。崩在放單之後、寫 waits 之前：下次 `think`／`act` 看到沒有在途就會再送一份——
  第一份會跑完、沒人收、回音留在 K 到 boot 才清。這是接受的（跟 [cpu.md §10-4](cpu.md) 同一種責任）。
- 回音、`llm-out`、`tool-out` 原樣讀、不解指示詞。

### 3.4 引擎連敗暫停

`errors` 到 3：歸零、`waits` 加 `{"$opt": "consume", "$val": "continue.json"}`、stderr 一行
`aos-agent: stuck: 引擎連敗 3 次，touch continue.json 繼續`；本次退 0，之後門沒開就 101。
設定讀驗、檔案 I/O 錯不算引擎失敗；工具失敗也不算（那是給模型看的結果）。

## 4. 退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 這格做了事（換格、送單、收回、引擎失敗但會重試） |
| 101 | 在等（門沒開、`idle` 沒輸入） |
| 1 | 讀驗錯（agent.md §5 的代號；stderr 一行 `aos-agent: <代號>: <白話>`，什麼都不寫）；寫檔中途失敗 `aos-agent: io: <白話>`（可能寫了一半，下次自癒） |
| 2 | 用法錯 |

## 5. 這份沒管的

agent 怎麼被放進 kernel（就是 `aos-kernel add <agent>/tick.json`，那份 inst 的 argv 是 `aos-agent /abs/agent-bob`；
`interval_ms` 決定它多久醒一次）；誰丟輸入、誰讀回話；記憶太長；同一個 agent 同時跑兩份（沒有鎖，別這樣）。

## 6. 我自己選的（等你確認）

1. **問跟跑都走 kernel `add --once`**，沒有同步工具；agent 不認識任何 cpu。
2. **工作名寫在 `waits` 的路徑裡**，state 不加 `ask`／`calls` 這種欄位；在途與否看 `waits`。
3. **inst 由 agent 產生、路徑全絕對、放 `insts/`**；`_meta` 在 agent 端解好，kernel／cpu 不用知道 agent 家。
4. **think 的 `timeout_ms`＝模型 timeout＋5 秒**，只是保險。
5. **順序：記憶 → ack → state**；崩在放單與加門之間會重送一份，接受。
6. **「結果不明」的固定文字沿用**（`Interrupted` 跟 `stopped:true` 都算）。
7. **工作區檔案用完就刪**，不留 `.done`。
