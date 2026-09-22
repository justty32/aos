# aos-agent：把一個 agent 資料夾走一格（程式規範，**草稿**）

← [proto5 README](../README.md)｜資料夾與 `state.json` 長什麼樣在 [agent.md](agent.md)；組請求靠 [aos-llm-ask.md](aos-llm-ask.md)，問模型交 llm CPU；跑工具靠 [inst-posix.md](inst-posix.md)

> 這份是 proto5.1 做出來的版本（2026-09-22 回流，照 [23 題拍板](../notes/2026-09-22-decisions.md)）。**proto5 的程式還沒照這份實作**；能跑的實作在 [proto5.1/lib](../../proto5.1/lib/README.md)。

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

aos-agent 會在送出 LLM／工具請求或引擎連敗三次時自己往 `waits` 加條目。人要它**暫停**也可以加一條指到
不存在的檔（例如 `continue.json`），要它**繼續**就 touch 那個檔——不用另外做 `pause`／`continue`。

## 3. 走一格到底做什麼

先讀驗（[agent.md](agent.md)：`info.json`／`state.json` 每格解指示詞、指到的檔原樣讀；`state.json`
不存在＝全部預設）；讀驗不過＝這格沒走，退出碼 1、什麼都不寫。門開了（§2）就照 `state` 做**一格**：

| 現在是 | 做什麼 | 寫回 `state` | 退出碼 |
|---|---|---|---|
| `idle` | 收 `input`（[agent.md §4.1](agent.md)）：有東西就接進記憶、清掉 | `think` | 0 |
| `idle` | 沒東西 | 不變 | **101** |
| `think` | 記憶尾巴已經是帶 `tool_calls` 的 `assistant`（上次崩在寫記憶與寫 `state` 之間）→ 自癒，不問模型也不送新請求 | `act` | 0 |
| `think` | `ask-result.json` 存在：讀驗後收回；`ok:true` 的 message 接記憶、`errors` 歸零，結果 rename 成 `.done` | 有非空 `tool_calls` → `act`；否則 → `idle` | 0 |
| `think` | 結果不存在：送出請求，再向 `waits` 加字面 `"ask-result.json"`，不開 consume | 不變 | 0 |
| `think` | 收回 `ok:false`：stderr 一行 `aos-agent: engine: <白話>`、記憶不動、`errors` 加一；結果 rename 成 `.done`；第三敗的處理見下 | 留 `think` | 0 |
| `act` | 沒有 `_run: "cpu"` 的 call：記憶尾巴的每個 `tool_calls[i]` 依序按名字找工具、拿 `_meta` 當 inst 跑；`arguments` 字串原樣進 stdin、stdout 整段當結果，每個 call 接一則 `tool` 訊息。每個工具有 `_timeout_ms` 上限，沒寫＝60000 ms。找不到＝「沒有這個工具：xxx」；逾時＝「工具 xxx 逾時（60000 ms）：」＋stdout（數字用實際預算）；非零退出＝「工具 xxx 失敗（exit n）：」＋stdout；inst 解不開／跑不起來＝「工具 xxx 跑不起來：」＋一行錯誤。這些都只是給模型的結果，其他 call 照跑 | `think` | 0 |
| `act` | 有 `_run: "cpu"` 的 call：先交整批 CPU 請求並等全部結果；收回時按原始順序接整批訊息（§3.3） | 送出留 `act`；收回轉 `think` | 0 |
| `act` | 記憶尾巴不是帶 `tool_calls` 的 `assistant`（沒東西可跑）→ 不跑 | `think` | 0 |

### 3.1 llm cpu 的送出與收回

- CPU 資料夾與協議見 [llm-cpu.md](llm-cpu.md)，一次執行的行為見 [aos-llm-cpu.md](aos-llm-cpu.md)。
- 送出前只驗 CPU 的 `info.json` 身分；models 與其中的環境變數留給 CPU 自己讀解。請求＝`{"model": engine.model 的代號, "body": 已組好且不含 model 的請求, "result": agent/ask-result.json 的絕對路徑}`。CPU 查自己的 models 表，填真名後呼叫模型；連線設定與 api_key 不經 agent 請求。
- 檔名＝`<agent 資料夾名>-<epoch ns>.json`。在 CPU 共用短鎖內先檢查 requests／running／done 三處同名，有就拒收、不覆蓋；寫 `.tmp` 再 rename 到 requests，才寫 waits。HTTP 不在這把鎖內。
- 下一次門沒開＝101；結果到了，同次呼叫劃門並收回。結果完整讀驗先於門的 consume／寫回；壞 JSON 或形狀錯誤＝1、結果與 state 保留。`ok` 必須是 bool；成功需要合法 assistant message，失敗需要字串 code／msg。結果內容不解指示詞。
- 記憶尾巴帶 tool_calls 的自癒優先於收回；若完整驗過、正規化的成功結果恰等於尾巴，先封存這份已接過的結果、清 errors，避免下次重收。壞結果不擋自癒並保留到後續 think；送出不清 errors，因為還沒得到引擎成功。
- 寫入順序為請求 → waits；收回成功為記憶 → 結果 `.done` → state。沒有跨檔交易或 request id：崩在這些寫入之間仍可能重送、重複接回或漏掉狀態推進，具體窗口見 [findings](../../proto5.1/notes/findings.md)。不要把這套當成 exactly-once。

### 3.2 引擎連敗暫停與工具限時

- 收回 `ok:false` 讓 `errors` 加一，成功清零；設定讀驗／檔案 I/O 錯誤不算引擎失敗。
- 到第三次失敗：`errors` 歸零，往 waits 加 `{"$opt":"consume","$val":"continue.json"}`，stderr 另印一行 `aos-agent: stuck: 引擎連敗 3 次，touch continue.json 繼續`；本次仍退 0，下一次門未開就 101。
- 門開時依 consume 把 `continue.json` rename `.done`，第二次暫停自然要再 touch；加門前不封存檔案。新 input 不能解鎖；touch 後同次呼叫可以繼續 think。
- 工具限時用 `run_inst(inst, arguments, timeout_ms=…)`；TERM 整個 process group → 最多 2 秒寬限 → KILL。是否逾時用獨立 `timed_out` 旗標，不能猜 143／137；因此工具在 TERM handler 回 0 仍是逾時，自己 exit 143 則是一般失敗。stdout 不截斷，已收到的部分保留。

### 3.3 tool cpu：整批送出、整批收回

- 工具 `_run` 沒寫或是 `"sync"`＝同步；`"cpu"`＝交到 `info.json` 頂層 `tool_cpu` 指定的資料夾（相對 agent 家）。CPU 協議見 [tool-cpu.md](tool-cpu.md)。
- 記憶尾巴有 calls、當批尚無任何結果：先驗 tool CPU 身分，建立 `tool-results/`，所有 CPU call 各送一份請求；sync call 這格先不跑。結果絕對路徑為 `<agent>/tool-results/<i>.json`，`i` 是原始 `tool_calls` 索引。請求名為 `<agent 名>-<epoch ns>-<i>.json`，由共用 `aos_cpu.submit` 交件。
- `_meta` 在 agent 端以 agent 家／環境解成 inst，交件時去掉 inst.stdin／inst.stdout；請求外層 `stdin` 為 arguments 字串、`timeout_ms` 為工具預算。inst 解不開則 agent 直接寫 `ok:false` 結果，其他 CPU call 照送。
- 送完往 waits 加一條 `{"$opt":"all","$val":[所有 CPU 結果的絕對路徑]}`，不開 consume，state 留 act、退 0；沒全到退 101。若結果只到一部分而 waits 缺失，補回整批 all 門，不重送已有結果。
- 全到後先驗整批結果，再劃門／跑 sync。按原始 call 順序組訊息：sync 現在跑；CPU 的 `ok:true` 且 code=0 用 stdout、非零用「工具 xxx 失敗（exit n）：」＋stdout；`timed_out:true` 優先為「工具 xxx 逾時」；一般 `ok:false` 為「工具 xxx 跑不起來：」＋msg；收屍／失聯的固定結果見下段。CPU 的 `kind` 原樣驗為 child／aos，這階段顯示依退出碼。全部訊息一起寫記憶，全部結果 rename `.done`，state 轉 think。
- CPU 收屍代表未取得可靠執行結果：可能崩在認領後、執行中，或工具已完成但還沒發布結果；也可能原程序仍活著、只超過收屍期限。這些都算「結果不明」，不猜副作用、不重試。當 `ok:false` 且 `code == "Reaped"`，tool content 固定為 `json.dumps({"ok": False, "error": "結果不明：工具可能已經跑了，也可能沒有"}, ensure_ascii=False)`，不加工具名前綴。已知逾時、非零退出、壞 payload、跑不起來仍用各自的已知失敗文字。
- 同一則 assistant 叫多個 `_run: "cpu"` 工具，只保證收回的訊息順序，**不保證執行順序**。模型一次叫多個並未指定先後；有先後關係的工具別標 cpu，或合成一個工具。
- 結果不解指示詞。`ok` 必須是 bool；成功的 `timed_out` 是 bool、`code` 是整數（bool 不算）、stdout 是字串；失敗的 code／msg 是字串；壞 JSON／UTF-8 或欄位錯誤退 1，門／記憶／結果不動，也不跑 sync。收回不再要求 CPU 的 info 可讀。
- 崩在記憶已寫、結果尚未全封存／state 尚未寫：下次 act 看尾端整批 tool 訊息，確認筆數與 call id 順序吻合，封存該批剩餘的 CPU 索引結果，再轉 think，不重跑 sync。
- **限制**：沒新增請求 id、state ask／calls 或交易。交件中途崩潰可能重送；若部分結果已到而其他 call 尚未交件，補回的門可能永遠等不到；sync 已跑但記憶尚未寫也可能重跑。固定結果路徑無法辨認任意遲到舊結果。這些情境列在 findings，D 只評估對帳、不實作。

### 3.4 寫檔與原有自癒

- 模型要求每個 call 的 tool 訊息緊接在 assistant 後。CPU call 等齊之後與 sync 一起按原始順序整批接上，這之前不進 think。
- `idle` 收輸入的順序是：全部讀完驗完 → 寫記憶 → rename `.done` → 寫 `state`；壞訊息（`MessageInvalid`）就整格不寫。
- 一格只寫：`state.json`（原始 JSON 只動 `state`／`waits`／`errors`）、記憶檔（整份重寫）、`input`／`waits`
  指到的檔（rename）、CPU 請求與 `ask-result.json`／`tool-results/<i>.json`（收回 rename）；都先 `.tmp` 再 rename。**先寫記憶、再寫 `state`**：崩在中間依記憶尾巴修復狀態；副作用與跨檔窗口見 findings。
  表裡 `think`／`act` 各多的那一列就是「重做」時看記憶尾巴自己對回來，不會把帶 `tool_calls` 的
  `assistant` 再拿去問一次（模型那邊會拒絕）。
- `think` 回來的 `message` 原樣接；只有 `content` 是 `null` 又沒有 `tool_calls` 時補成 `""`（不然下次
  讀驗過不了 [agent.md §3.2](agent.md)）。
- 跑工具是 import proto5.1 的 aos_exec／aos_inst，不是開 `aos-exec` 子進程（inst 在記憶體、stdin 要塞
  字串、stdout 要收回來——函式庫層要補一個入口）。
- `$env` 讀的是 aos-agent 自己的環境；`$ref` 相對路徑以 agent 資料夾為中心。
- 同一個 agent **不要同時跑兩份**（沒有鎖）。

## 4. 退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 這格做了事（換了格、送出或收回模型請求、跑了工具、或引擎失敗但會重試） |
| 101 | 在等（`waits` 沒到、`idle` 沒輸入） |
| 1 | 讀驗錯誤（[agent.md §5](agent.md)、[agent.md §3](agent.md)、[directives.md §6](directives.md) 的代號）：stderr 一行 `aos-agent: <代號>: <白話>`，什麼都不寫。寫檔／rename 中途失敗也是 1：`aos-agent: io: <白話>`，這種可能已經寫了一部分（下一次靠自癒對回來） |
| 2 | 用法錯（旗標不認得、`dir` 不存在） |

## 5. 之後會有、現在不做的

- **送出即收據的背景工具**：另加一個 `async` 選項——`act` 啟動它就馬上接一則收據當 `tool` 訊息，工具跑在別的
  cpu／thread，跑完把結果寫進 `input`（當 `user` 訊息回來；順序沒限制，因為不是 `tool` 訊息）。
- **整格硬上限與 waits 期限**：這輪不做；工具每次 60 秒與引擎連敗三次暫停已在 §3。HTTP 的 timeout 仍是 socket 逾時，不是整次呼叫總上限。
- 誰把輸入丟進 `input`、誰去讀回話（aos-user 之類的外部工具）；反覆叫、放進 kernel；鎖；記憶太長。

## 我自己選的、使用者可以推翻的

1. `waits` 是動態表：aos-agent 也能加；要「永遠等某個檔」的靜態門先不做。
2. `think` 直接看 `tool_calls` 決定去 `act` 還是 `idle`；`act` 對 CPU call 分送收兩格，全部結果到齊才接記憶。
3. 先寫記憶再寫 `state`；`think`／`act` 進場先看記憶尾巴自癒。
