# aos-agent：把一個 agent 資料夾走一格（程式規範，**草稿**）

← [proto5 README](../README.md)｜資料夾與 `state.json` 長什麼樣在 [agent.md](agent.md)；問模型那一步是 [aos-llm-ask.md](aos-llm-ask.md)；跑工具靠 [inst-posix.md](inst-posix.md)

> **最精簡的標準**（使用者定的）：缺的東西之後遇到了再補；不記修訂記錄。
> 這份只講「叫一次 aos-agent 到底做什麼」：先看**門**（`waits`），再走**一格**（`state`）。
> `state`／`input`／`waits`／`errors` 四格的形狀在 [agent.md §4](agent.md)，這裡不重講。

一句話：**`aos-agent [dir]` 先看 `waits` 這道門——還在等就退出；門開了就把狀態機走一格，然後退出。**
跟 aos-exec 一樣是「一次做一件事」的程式，反覆叫它是 kernel 的事。

## 1. 用法

```
aos-agent [dir]
```

- `dir` 留空＝`.`（跟 aos-exec 一樣）。`dir` 必須是 agent 資料夾（有 `info.json`、`_metainfo._type`
  是 `llm_agent`），不是＝`NotAnAgent`。
- 沒有別的旗標、沒有子命令。

## 2. 門怎麼判

每次被叫，讀驗完（§3 第一段）、走格之前，先看 `state.json` 的 `waits`（[agent.md §4.2](agent.md)）：

1. 逐條檢查。**到了的那一條**：先照 `consume` 處理（`any` 的話只 consume 真的到了的那幾個檔），再
   **從表裡劃掉**（按索引劃原始 JSON 那一條）。沒到的留著。
2. 表劃完還有剩 → 把改過的 `waits` 寫回 `state.json`（只動這格），退出碼 101，這次不走格。
3. 表空了 → 寫回（`waits` 變空陣列），接著照 `state` 走一格（§3）。

所以「一部分到了」的進度會留下來：到了的已經劃掉、consume 過，下次只等剩下的，不會重複判同一個檔。

aos-agent 會在送出 LLM 請求或引擎連敗三次時自己往 `waits` 加條目。人要它**暫停**也可以加一條指到
不存在的檔（例如 `continue.json`），要它**繼續**就 touch 那個檔——不用另外做 `pause`／`continue`。

## 3. 走一格到底做什麼

先讀驗（[agent.md](agent.md)：`info.json`／`state.json` 每格解指示詞、指到的檔原樣讀；`state.json`
不存在＝全部預設）；讀驗不過＝這格沒走，退出碼 1、什麼都不寫。門開了（§2）就照 `state` 做**一格**：

| 現在是 | 做什麼 | 寫回 `state` | 退出碼 |
|---|---|---|---|
| `idle` | 收 `input`（[agent.md §4.1](agent.md)）：有東西就接進記憶、清掉 | `think` | 0 |
| `idle` | 沒東西 | 不變 | **101** |
| `think` | 記憶尾巴已經是帶 `tool_calls` 的 `assistant`（上次崩在寫記憶與寫 `state` 之間）→ 自癒，不問模型也不送新請求 | `act` | 0 |
| `think` | `engine.cpu` 沒寫：用 [aos-llm-ask](aos-llm-ask.md) 函式庫同步問一次，message 接記憶、`errors` 歸零 | 有非空 `tool_calls` → `act`；否則 → `idle` | 0 |
| `think` | `engine.cpu` 有寫、`ask-result.json` 存在：讀驗後收回；`ok:true` 的 message 接記憶、`errors` 歸零，結果 rename 成 `.done` | 有非空 `tool_calls` → `act`；否則 → `idle` | 0 |
| `think` | `engine.cpu` 有寫、結果不存在：送出請求，再向 `waits` 加字面 `"ask-result.json"`，不開 consume | 不變 | 0 |
| `think` | 同步 `EngineFailed` 或收回 `ok:false`：stderr 一行 `aos-agent: engine: <白話>`、記憶不動、`errors` 加一；非同步結果 rename 成 `.done`；第三敗的處理見下 | 留 `think` | 0 |
| `act` | 記憶尾巴的每個 `tool_calls[i]` 依序按名字找工具、拿 `_meta` 當 inst 跑；`arguments` 字串原樣進 stdin、stdout 整段當結果，每個 call 接一則 `tool` 訊息。每個工具有 `_timeout_ms` 上限，沒寫＝60000 ms。找不到＝「沒有這個工具：xxx」；逾時＝「工具 xxx 逾時（60000 ms）：」＋stdout（數字用實際預算）；非零退出＝「工具 xxx 失敗（exit n）：」＋stdout；inst 解不開／跑不起來＝「工具 xxx 跑不起來：」＋一行錯誤。這些都只是給模型的結果，其他 call 照跑 | `think` | 0 |
| `act` | 記憶尾巴不是帶 `tool_calls` 的 `assistant`（沒東西可跑）→ 不跑 | `think` | 0 |

### 3.1 llm cpu 的送出與收回

- CPU 資料夾與協議見 [llm-cpu.md](llm-cpu.md)，一次執行的行為見 [aos-llm-cpu.md](aos-llm-cpu.md)。
- 送出前驗 CPU 的 `info.json`。請求＝`{"engine": 已解好的整包引擎, "body": 已組好的請求, "result": agent/ask-result.json 的絕對路徑}`，含已解好的 api_key；CPU 不再解指示詞、不讀 agent 設定。
- 檔名＝`<agent 資料夾名>-<epoch ns>.json`。在 CPU 共用短鎖內先檢查 requests／running／done 三處同名，有就拒收、不覆蓋；寫 `.tmp` 再 rename 到 requests，才寫 waits。HTTP 不在這把鎖內。
- 下一次門沒開＝101；結果到了，同次呼叫劃門並收回。結果完整讀驗先於門的 consume／寫回；壞 JSON 或形狀錯誤＝1、結果與 state 保留。`ok` 必須是 bool；成功需要合法 assistant message，失敗需要字串 error。結果內容不解指示詞。
- 記憶尾巴帶 tool_calls 的自癒優先於收回；若完整驗過、正規化的成功結果恰等於尾巴，先封存這份已接過的結果、清 errors，避免下次重收。壞結果不擋自癒並保留到後續 think；送出不清 errors，因為還沒得到引擎成功。
- 寫入順序為請求 → waits；收回成功為記憶 → 結果 `.done` → state。沒有跨檔交易或 request id：崩在這些寫入之間仍可能重送、重複接回或漏掉狀態推進，具體窗口見 [findings](../notes/findings.md)。不要把這套當成 exactly-once。

### 3.2 引擎連敗暫停與工具限時

- 同步引擎失敗與非同步 `ok:false` 都讓 `errors` 加一，成功清零；設定讀驗／檔案 I/O 錯誤不算引擎失敗。
- 到第三次失敗：`errors` 歸零，往 waits 加字面 `"continue.json"`，stderr 另印一行 `aos-agent: stuck: 引擎連敗 3 次，touch continue.json 繼續`；本次仍退 0，下一次門未開就 101。
- 加這道門前若舊 `continue.json` 已存在，先 rename `.done`，確保第二輪暫停仍要新的 touch。新 input 不能解鎖；touch 後同次呼叫可以繼續 think。
- 工具限時用 `run_inst(inst, arguments, timeout_ms=…)`；TERM 整個 process group → 最多 2 秒寬限 → KILL。是否逾時用獨立 `timed_out` 旗標，不能猜 143／137；因此工具在 TERM handler 回 0 仍是逾時，自己 exit 143 則是一般失敗。stdout 不截斷，已收到的部分保留。

### 3.3 寫檔與原有自癒

- **為什麼 `act` 不用等**：模型那邊的硬規定是一則 `assistant` 帶了 `tool_calls`，下一次問之前每個 call
  都要有一則 `tool` 訊息緊接在後面。`act` 一格內全部跑完接上，就永遠不會違反。
- `idle` 收輸入的順序是：全部讀完驗完 → 寫記憶 → rename `.done` → 寫 `state`；壞訊息（`MessageInvalid`）就整格不寫。
- 一格只寫：`state.json`（原始 JSON 只動 `state`／`waits`／`errors`）、記憶檔（整份重寫）、`input`／`waits`
  指到的檔（rename）、CPU 請求與 `ask-result.json`（收回 rename）；都先 `.tmp` 再 rename。**先寫記憶、再寫 `state`**：崩在中間頂多重做一格——
  表裡 `think`／`act` 各多的那一列就是「重做」時看記憶尾巴自己對回來，不會把帶 `tool_calls` 的
  `assistant` 再拿去問一次（模型那邊會拒絕）。
- `think` 回來的 `message` 原樣接；只有 `content` 是 `null` 又沒有 `tool_calls` 時補成 `""`（不然下次
  讀驗過不了 [aos-llm-ask.md §2.2](aos-llm-ask.md)）。
- 跑工具是 import proto5.1 的 aos_exec／aos_inst，不是開 `aos-exec` 子進程（inst 在記憶體、stdin 要塞
  字串、stdout 要收回來——函式庫層要補一個入口）。
- `$env` 讀的是 aos-agent 自己的環境；`$ref` 相對路徑以 agent 資料夾為中心。
- 同一個 agent **不要同時跑兩份**（沒有鎖）。

## 4. 退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 這格做了事（換了格、問了模型、跑了工具、或引擎失敗但會重試） |
| 101 | 在等（`waits` 沒到、`idle` 沒輸入） |
| 1 | 讀驗錯誤（[agent.md §5](agent.md)、[aos-llm-ask.md §2](aos-llm-ask.md)、[directives.md §6](directives.md) 的代號）：stderr 一行 `aos-agent: <代號>: <白話>`，什麼都不寫。寫檔／rename 中途失敗也是 1：`aos-agent: io: <白話>`，這種可能已經寫了一部分（下一次靠自癒對回來） |
| 2 | 用法錯（旗標不認得、`dir` 不存在） |

## 5. 之後會有、現在不做的

- **非同步工具**：工具檔多一個 `async` 選項——`act` 啟動它就馬上接一則收據當 `tool` 訊息，工具跑在別的
  cpu／thread，跑完把結果寫進 `input`（當 `user` 訊息回來；順序沒限制，因為不是 `tool` 訊息）。
- **整格硬上限與 waits 期限**：這輪不做；工具每次 60 秒與引擎連敗三次暫停已在 §3。HTTP 的 timeout 仍是 socket 逾時，不是整次呼叫總上限。
- 誰把輸入丟進 `input`、誰去讀回話（aos-user 之類的外部工具）；反覆叫、放進 kernel；鎖；記憶太長。

## 我自己選的、使用者可以推翻的

1. `waits` 是動態表：aos-agent 也能加；要「永遠等某個檔」的靜態門先不做。
2. `think` 直接看 `tool_calls` 決定去 `act` 還是 `idle`；`act` 一格內跑完所有 call。
3. 先寫記憶再寫 `state`；`think`／`act` 進場先看記憶尾巴自癒。
