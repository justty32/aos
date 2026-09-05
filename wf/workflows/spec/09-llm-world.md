# 09 LLM 世界
← [入口](README.md)

LLM 不是一筆指令，是另一塊地。它慢、貴、時間看外面決定，誰都不許在自己的行程裡等它。要用就往它的收件匣投一筆請求，回話落在你指定的結果落點。這份檔規定：地在哪、誰起它、請求長什麼樣、單元表放哪、帳簿記什麼、`aos llm` 的形狀。**走一輪、排隊、重啟、請求狀態在 [09b](09b-llm-queue.md)。**

## 這塊地在哪、誰看管

- **S-09-01** LLM 世界必須是一塊地：有自己的 `.aos/` 與時鐘，由 daemon 登記看管。〔裁決 2026-09-05〕
- **S-09-02** 它必須預設在 `$AOS_HOME/.aos/llm/`；要換位置必須改 `$AOS_HOME/.aos/config.json` 的 `llm_world`。〔主編補〕
- **S-09-03** `aos daemon start` 必須登記 LLM 世界並替它起一支 `aos llm serve <地>`，不是 `aos run`；登記表那筆的 `runner` 填 `"llm-serve"`（欄位在 [08](08-daemon.md)）。〔裁決 2026-09-05〕
- **S-09-72** `aos llm serve` 的旗標必須有 `--every <ms>`（預設 200）與 `--until idle|never`（預設 `never`：閒著也不停，繼續等投遞）。〔裁決 2026-09-05〕
- **S-09-73** `aos llm serve` 必須跟 `aos exec` 搶同一把 `.aos/lock`；同時只准一支在跑，不然同一筆請求會被打兩次。〔裁決 2026-09-05〕
- **S-09-74** LLM 世界禁止用接力棒與三種步：`aos llm serve` 不讀 `.aos/series.json` 與 `.aos/program/`，`main.aos.json` 可以不存在。〔裁決 2026-09-05〕
- **S-09-04** 別的地要用 LLM，必須往它的 `.aos/inbox/` 投一筆 `kind` 是 `"llm"` 的請求。〔裁決 2026-09-05〕
- **S-09-05** 禁止把 LLM 當成一筆指令直接叫；它不住在任何一塊地的行程裡。〔裁決 2026-09-05〕
- **S-09-06** 同步子地整棵樹裡禁止出現 LLM 請求；那一步借父的鐘，等不起。〔裁決 2026-09-05〕
- **S-09-07** 禁止為每一筆請求另外開一塊地。〔主編補〕

## 請求的欄位

格式見 `schemas/llm-request.schema.json`；投遞協定（三次改名、同 `id` 拒收、無效搬 `rejected/`）照 [07](07-call-and-delivery.md)。

- **S-09-09** `format_version` 必須是 `1`，`kind` 必須是 `"llm"`。〔主編補〕
- **S-09-10** `id` 必須是機器產的 32 個小寫 hex；同 `id` 再投必須拒收並回報。〔主編補〕
- **S-09-11** `from` 必須是投遞者那塊地的真實路徑；`at` 是投遞當下的時間。〔主編補〕
- **S-09-12** `prompt` 必須是指向 prompt 檔的路徑；禁止把內文塞進請求裡，大內容一律走路徑。〔主編補〕
- **S-09-08** `prompt` 與 `result` 是相對路徑時基準必須是 `from` 那塊地的根，絕對路徑照用，兩者都禁止指進任何 `.aos/`。`result` 是請求者開的明示寫入洞，只涵蓋那條路徑與它的 `.status.json`、`.usage.json`；`prompt` 是明示讀取洞，只涵蓋那一個檔。其餘的東西 LLM 世界一律禁止碰。〔主編補〕
- **S-09-75** 取件時必須把 `prompt` 與 `result` 展開成絕對路徑寫進 `.aos/requests/<id>.json`；路徑有問題時報錯必須連「基準是哪塊地」一起講。〔主編補〕
- **S-09-13** `tier` 必須只說「要多聰明」（例如 `"fast"`、`"smart"`）；禁止在請求裡指定用哪一顆處理單元。〔裁決 2026-08-30〕
- **S-09-14** `result` 必須是父指定的結果落點；回話的原文必須寫到那裡。〔裁決 2026-09-05〕
- **S-09-15** `priority` 必須是整數、投的時候填好，小的先做。〔裁決 2026-08-30〕
- **S-09-16** `max_wait_ms` 必須是這筆最多排隊多久；省略就用 `.aos/units.json` 那個。〔裁決 2026-08-30〕
- **S-09-17** `tools` 可以省略；要給就必須是字串陣列，一個工具一行，格式見 [11](11-tools-and-contacts.md)。〔裁決 2026-08-30〕
- **S-09-76** `tools` 必須當成接在 prompt 前面的純文字行；禁止送進後端請求本體的同名欄位。它跟後端那套工具呼叫（function calling）只是同名，沒有關係。〔主編補〕
- **S-09-18** `ext` 以外只要 spec 不認得的欄位就必須拒收。〔主編補〕

## 處理單元表

- **S-09-33** 單元表的正本必須放使用者層 `$AOS_HOME/.aos/config.json` 的 `units`。〔預設 2026-09-05，G-05〕
- **S-09-34** 每一筆必須有 `name`（帳簿記的就是它）、`endpoint`、`model`、`tier`（聰明度分級）、`max_parallel`（語意見 [09b](09b-llm-queue.md)）。〔預設 2026-09-05，G-05〕
- **S-09-51** 每一筆還可以有 `timeout_ms`（這顆一次呼叫最多幾毫秒）；沒填必須當 300000。〔主編補〕
- **S-09-52** 跑一次 `aos llm` 的逾時必須用配到那顆單元的 `timeout_ms`；禁止套 run 層的預設 60000，本機模型想一次就十幾秒。〔主編補〕
- **S-09-77** `endpoint` 必須保留三個假後端 scheme：`echo:`（不打網路，原樣回）、`fail:<原因>`（一定失敗，寫 `backend_error`）、`slow:<毫秒>`（睡一下再原樣回）。實作必須支援。〔主編補〕
- **S-09-78** 自動測試禁止打真的網路；要測必須用上面那三個 scheme。〔主編補〕
- **S-09-53** daemon 起 `aos llm serve` 之前必須把 `units` 與 `max_parallel`、`max_wait_ms` 抄進 `<llm_world>/.aos/units.json`；`units` 形狀同 `config.schema.json`。〔主編補〕
- **S-09-54** LLM 世界禁止讀家的 `config.json`，只准讀自己地上的 `.aos/units.json`；它只看得到自己地盤，這是唯一的合法路。〔主編補〕
- **S-09-35** `api_key_env` 必須只寫環境變數名；金鑰本身禁止寫進設定檔或 `.aos/units.json`。〔主編補〕
- **S-09-36** 單元的位址禁止進通訊錄；通訊錄只回答 agent 住在哪。〔裁決 2026-08-30〕
- **S-09-37** 一般世界的 `.aos/config.json` 禁止出現 `units`；子地禁止繼承或覆寫別人的單元表。〔主編補〕

## 帳簿

- **S-09-38** 每一次打後端（成功失敗都算）必須在 `$AOS_HOME/.aos/ledger.jsonl` 追加一行；排隊逾時與寫壞退回的也各記一行。〔裁決 2026-09-05〕
- **S-09-39** 帳簿必須只記帳：禁止拿它做配額或排隊。〔裁決 2026-09-05〕
- **S-09-40** 帳簿必須是 jsonl、只准追加；禁止回頭改寫下的行。〔主編補〕
- **S-09-41** 一行必須有 `at`、`request_id`、`from`、`unit`、`tier`、`tokens_in`、`tokens_out`、`tokens_source`、`ms`、`outcome`。〔主編補〕
- **S-09-79** `tokens_source` 必須是 `"reported"`（後端回的）或 `"estimated"`（自己估的）；禁止把估的當真的記，也禁止拿 0 當「不知道」。〔主編補〕
- **S-09-80** `outcome` 必須是 `ok`、`backend_error`、`queue_timeout`、`rejected`、`result_unknown`、`killed` 六個之一，且必須跟狀態檔的 `reason` 對得上。〔主編補〕
- **S-09-42** 帳簿的行禁止有 `format_version`：一行不是一份文件，要改格式必須另開檔名。〔主編補〕
- **S-09-55** agent 算自己的 token 上限必須讀落點旁的 `.usage.json`（見 [09b](09b-llm-queue.md)），禁止讀家的帳簿。〔主編補〕

## `aos llm` 與 `aos llm serve`

- **S-09-43** `aos llm` 必須是普通的 unix 過濾器：stdin 進 prompt、stdout 出回話原文。〔主編補〕
- **S-09-44** 旗標必須有五個：`--unit <名>`、`--tier <名>`（只挑聰明度）、`--tools <檔>`、`--usage-out <檔>`、`--request-id <id>`；後兩個見 [09b](09b-llm-queue.md)。〔主編補〕
- **S-09-45** `aos llm` 的退出碼必須只有四種：`0` 成功、`2` 用法錯、`75` 後端或傳輸失敗、`130` 被取消。〔預設 2026-09-05，K-04〕
- **S-09-56** 這四種退出碼必須全歸「跑沒跑起來」那一軸；禁止從退出碼推「該不該重試」。〔主編補〕
- **S-09-57** 可不可重試必須寫在狀態檔的 `ext.retryable`（布林）；父只准讀狀態檔。〔主編補〕
- **S-09-81** `aos llm serve` 的退出碼必須只講這支程式有沒有跑起來；一輪裡壞了幾筆請求禁止影響它，那些一律看各自的狀態檔。〔主編補〕
- **S-09-46** 後端回的錯誤必須帶狀態碼與回應片段寫進 stderr；禁止糊成一句話。〔主編補〕
- **S-09-47** `aos llm` 禁止常駐、禁止限流；上限與排隊是 `aos llm serve` 的事。〔主編補〕
- **S-09-58** `aos llm` 與 `aos llm serve` 必須只在 LLM 世界裡被叫；別的地的工具登記表禁止登記它或任何直接打端點的程式，`aos check` 必須擋。〔主編補〕
- **S-09-82** `aos llm ask "<文字>"` 建議做成指令面的糖（見 [12](12-cli.md)）：把那句話落成 `$AOS_HOME/.aos/ask/<id>.prompt`、結果落在 `<id>.out`，兩個檔都留著。請求格式禁止為它改動。〔主編補〕

## 範例

一筆請求（`<llm_world>/.aos/inbox/<id>.json`）：

```json
{
  "format_version": 1, "id": "7f3a1c2b9d4e5061728394a5b6c7d8e9", "kind": "llm",
  "from": "/home/u/proj/writer", "at": "2026-09-05T12:00:00.000Z",
  "prompt": "work/prompt.txt", "result": "work/reply.txt",
  "tier": "smart", "priority": 10, "max_wait_ms": 120000,
  "tools": ["ls | 逐項列表 | 不收 stdin | 可預期性高 | 列出資料夾 | 例：ls -la ."]
}
```

帳簿的一行（`$AOS_HOME/.aos/ledger.jsonl`）：

```json
{"at":"2026-09-05T12:00:04.120Z","request_id":"7f3a1c2b9d4e5061728394a5b6c7d8e9","from":"/home/u/proj/writer","unit":"local-smart","tier":"smart","tokens_in":812,"tokens_out":233,"tokens_source":"reported","ms":4103,"outcome":"ok"}
```

daemon 抄給 LLM 世界的單元表（`<llm_world>/.aos/units.json`）：

```json
{
  "format_version": 1, "max_parallel": 4, "max_wait_ms": 120000,
  "units": [
    {"name":"local-smart","endpoint":"http://127.0.0.1:1234/v1","model":"qwen3-30b","tier":"smart","max_parallel":1,"timeout_ms":300000},
    {"name":"test-echo","endpoint":"echo:","model":"none","tier":"fast","max_parallel":8,"timeout_ms":1000}
  ]
}
```

## 待使用者拍板

沒標〔預設〕的一律〔主編補〕。括號裡是原始的邊緣狀況編號。

- S-09-02 位置預設 `$AOS_HOME/.aos/llm/`。
- S-09-07 不為每筆請求開一塊地（主編裁的矛盾 #4）。
- S-09-08、S-09-75 相對路徑基準是 `from` 那塊地、禁止指進 `.aos/`、取件時展開（X3、P2）。
- S-09-09～S-09-12、S-09-18 請求的版本、id、來源、時間、prompt 走路徑，不認得的欄位就拒收。
- S-09-76 `tools` 是塞進 prompt 的文字行，不是後端的工具呼叫（P20）。
- S-09-33、S-09-34 單元表放使用者層 `units` 與它的欄位。〔預設 2026-09-05，G-05〕
- S-09-51、S-09-52 每顆多 `timeout_ms`（沒填 300000），不套 run 層的 60000（L03）。
- S-09-77、S-09-78 保留 `echo:`／`fail:`／`slow:` 三個假後端；測試禁打真網路（P18）。
- S-09-53～S-09-55 daemon 抄一份 `.aos/units.json`、它禁止讀家的設定檔（S06）、agent 的 token 上限讀 `.usage.json`（X5）。
- S-09-35、S-09-37 只記金鑰的環境變數名；一般世界不准有 `units`。
- S-09-40～S-09-42 帳簿只准追加、一行有哪些欄、行裡沒版本欄。
- S-09-79、S-09-80 `tokens_source` 分清估的與報的；`outcome` 六個值定死（P17）。
- S-09-43～S-09-47、S-09-56、S-09-57、S-09-81 `aos llm` 是過濾器、三旗標、退出碼只管跑沒跑起來（serve 也是）、可否重試寫狀態檔 `ext.retryable`（S18、P19、K-04）。
- S-09-58、S-09-82 `aos llm` 只准 LLM 世界用（B38）；`aos llm ask` 這顆糖（P22）。
- 矛盾：共同契約說每份頂層文件都要有 `format_version`，但帳簿是 jsonl。選了行裡不放版本欄（S-09-42）：一行不是一份文件，逐行放只是重複；代價是改格式得換檔名。

## 現況對照

今天的 `aos llm` 是同步等 HTTP 的一支 CLI，`aos agent` 直接連結它的函式庫 API，誰都可以叫，沒有「LLM 世界」也沒有 `aos llm serve`。並行上限靠 `cpus.json` 與世界層 `.aos/llm.json` 的 `flock` 鎖檔槽擋，等不到 exit 75。帳簿、用量檔、假後端都不存在。
