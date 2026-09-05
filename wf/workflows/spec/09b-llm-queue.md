# 09b LLM 世界的排隊與重啟
← [入口](README.md)

[09](09-llm-world.md) 規定請求、單元表、帳簿；本章規定 `aos llm serve` 的一輪、排隊、結果、進度、重啟與清理。編號接著 09。

## 一輪裡做什麼

`aos llm serve` 不走接力棒，一輪就是下面這幾件事，做完睡 `--every` 再來一次。

- **S-09-99** `aos daemon start` 發現 `llm_world` 那個資料夾沒有 `.aos/` 必須先 `aos init` 它再起 serve（見 [08](08-daemon.md)）；`aos llm init` 必須做同一件事，並把 `units` 寫進家的 `config.json`。〔主編補〕
- **S-09-19** 每輪先取件：合法請求要用改名把原件一字不動搬成 `.aos/llm-inflight/<id>.json`，再另寫 `.aos/requests/<id>.json`；禁止把原件改成進度物件。〔裁決 2026-09-05〕
- **S-09-83** 請求本身寫壞的（schema 不過、`prompt` 檔不在、落點指進 `.aos/`）必須搬到 `.aos/inbox/rejected/<id>.json`，並照 [07](07-call-and-delivery.md) 往 `from` 的收件匣回一則 `mail`；落點還合法就同時寫 `reason` 是 `rejected` 的狀態檔。〔主編補〕
- **S-09-20** 隊伍必須按 `priority` 小的先；同一個 `priority` 必須按 `at` 早的先。〔主編補〕
- **S-09-84** `max_parallel` 的意思必須是「這一輪最多派給這顆單元幾筆」；一輪之內做完的事對外面是原子的，「同時」只能這樣定義。〔主編補〕
- **S-09-21** 每顆處理單元這一輪派出去的必須不超過它自己的 `max_parallel`。〔裁決 2026-08-30〕
- **S-09-22** 全部加起來這一輪派出去的必須不超過 `.aos/units.json` 裡的 `max_parallel`；兩個上限取小。〔裁決 2026-08-30〕
- **S-09-23** LLM 世界自己 `.aos/config.json` 的 `max_parallel` 必須只能把上限往下限；禁止往上加。〔裁決 2026-08-30〕
- **S-09-59** 併發必須由 LLM 世界自己在它的地上數；禁止 daemon 另外替它數一次。兩邊各數一次會變成雙重限流。〔裁決 2026-09-05〕
- **S-09-24** 挑中一筆請求必須配一顆 `tier` 對得上的處理單元；沒有對得上又還沒滿的，這筆必須繼續排隊。〔主編補〕
- **S-09-85** 配不到單元的那一筆，`.aos/requests/<id>.json` 必須維持 `state` 是 `"queued"` 並在 `ext.waiting_tier` 記下在等哪個 tier；禁止只印在螢幕上，daemon 底下沒人看得到。〔主編補〕
- **S-09-86** 禁止把請求降級派給 `tier` 對不上的單元；要降級必須是請求者自己換 `tier` 重投。〔主編補〕
- **S-09-25** 每一筆派出去的請求必須跑一次 `aos llm`：stdin 進 `prompt` 那個檔的內容、stdout 出到結果落點。成敗必須看落點與狀態檔，不看退出碼。〔主編補〕
- **S-09-26** 失敗必須寫 `<result>.status.json`，`reason` 填 `backend_error`，`message` 帶後端狀態碼與回應片段，`ext.retryable` 填布林。〔主編補〕

## 一輪跑多久、怎麼停

- **S-09-91** 一輪必須同時起最多 `max_parallel` 支 `aos llm` 子行程（真的並行，各自吃自己那顆單元的 `timeout_ms`）；全部結束才算這一輪結束。〔主編補〕
- **S-09-92** 一輪開頭必須讀一次控制收件匣；等子行程時必須每 100 毫秒以內再讀一次。〔主編補〕
- **S-09-93** 收到 `stop` 必須不再派新的、等在跑的那幾支跑完，再寫 `.aos/stopped.json`（`reason` 填 `stop_requested`）退出；禁止半途砍掉已送出的請求。〔主編補〕
- **S-09-94** `aos llm serve` 停下來時必須一律寫 `.aos/stopped.json`，格式與寫法跟 `aos run` 同一套（見 [06](06-exec-and-run.md)）。〔主編補〕

## `aos llm` 要交回什麼

回話佔滿了 stdout，token 數與是哪一筆請求沒地方擠，所以另外走檔案。

- **S-09-95** `aos llm --usage-out <檔>` 跑完必須把 `tokens_in`、`tokens_out`、`tokens_reasoning`、`tokens_source`、`unit`、`ms` 寫成一份 json 到那個檔；成功失敗都要寫。`tokens_reasoning` 可為 `null`，`tokens_out` 不含它。〔主編補〕
- **S-09-96** `aos llm --request-id <id>` 必須只拿來填帳簿那一行的 `request_id` 與用量檔的 `request_id`；禁止讓它改動回話內容或請求本身。〔主編補〕
- **S-09-97** `aos llm serve` 派每一筆請求時必須都帶這兩個旗標；帳簿那一行與 `.usage.json` 的數字必須從 `--usage-out` 那個檔來，禁止自己猜。〔主編補〕
- **S-09-98** `--usage-out` 那個檔跟 `<結果落點>.usage.json` 禁止當成同一份：前者是 `aos llm` 交差用、留在 LLM 世界；後者由 serve 補上 `format_version` 與 `request_id` 再發布給請求者。〔主編補〕

## 成功要留下兩個檔

- **S-09-60** 成功時除了結果落點那個檔，還必須在它旁邊寫 `<結果落點>.usage.json`：`format_version`、`request_id`、`unit`、`tokens_in`、`tokens_out`、`ms`。格式見 `schemas/usage.schema.json`。〔主編補〕
- **S-09-61** `.usage.json` 必須跟結果檔一樣原子發布（暫存→fsync→改名→fsync 目錄），而且必須在結果檔發布之前先寫好；不然父看到結果就走，用量永遠慢一步。〔主編補〕
- **S-09-62** 失敗時禁止寫 `.usage.json`；那一筆的用量只留在帳簿裡。〔主編補〕

## 排隊規則

- **S-09-27** 超過上限的請求必須排隊，禁止當場退回。〔裁決 2026-08-30〕
- **S-09-28** 排隊超過 `max_wait_ms` 必須退回：寫 `<result>.status.json`，`reason` 填 `queue_timeout`。〔裁決 2026-08-30〕
- **S-09-87** `max_wait_ms` 必須從投遞物的 `at` 算起；那是唯一落在檔裡的時間戳。〔主編補〕
- **S-09-88** 寫 `queue_timeout` 狀態檔時 `message` 必須寫清楚「排了幾毫秒／上限幾毫秒」；兩邊的鐘差幾秒就會冤枉剛投進來的請求，人要一眼看得出。〔主編補〕
- **S-09-29** 退回禁止當成 LLM 世界失敗；請求者可以照原樣換一個 `id` 再投一次。〔裁決 2026-08-30〕
- **S-09-30** 處理單元掛了必須只把「還沒送出」的那些改派給同 `tier` 的另一顆。〔裁決 2026-08-30〕
- **S-09-31** 送出去以後才斷線必須當成結果不明：禁止重送。〔裁決 2026-08-30〕
- **S-09-32** 2026-08-30 那套鎖檔槽與工人的機制必須作廢；上面五條規則保留，改由 `aos llm serve` 每一輪執行。〔預設 2026-09-05，G-04〕

## 每筆請求的狀態放哪

父手上只有一筆請求，不是一塊地，所以登記表上查不到它。狀態由 LLM 世界自己維護。

- **S-09-63** LLM 世界必須為每一筆請求維護 `<llm_world>/.aos/requests/<request id>.json`，格式見 `schemas/request-state.schema.json`。〔裁決 2026-09-05〕
- **S-09-64** 進度檔必須有 `format_version`、`id`、`from`、`state`、`unit`、`prompt`、`result`、`updated_at`、`request`、`ext`；`state` 是 `queued`、`sent`、`done`、`failed` 四選一。`request` 必須是原件的相對路徑，不是原件內容。〔裁決 2026-09-05〕
- **S-09-89** 未收場的原件必須一字不動留在 `.aos/llm-inflight/<id>.json`；成功或失敗時改名搬到 `.aos/llm-done/<id>.json`，進度檔的 `request` 隨之改指新路徑。〔裁決 2026-09-05〕
- **S-09-90** LLM 世界的投遞 id 去重必須靠 `.aos/requests/` 裡有沒有同名的檔；禁止另外設一個收件匣的去重檔。〔主編補〕
- **S-09-65** `aos status --request <id>` 必須讀它並印出來（子命令見 [12](12-cli.md)）；請求者禁止直接打開 LLM 世界的檔案去看。〔裁決 2026-09-05〕
- **S-09-66** 這個檔必須只當給人看的進度；判成敗必須一律看結果落點與狀態檔，禁止拿 `state` 當憑據。〔主編補〕

## 重啟怎麼算

- **S-09-48** daemon 重啟後 LLM 世界的收件匣必須還在；沒處理完的請求必須下一輪照收。〔主編補〕
- **S-09-49** 重啟必須靠 `.aos/requests/` 的狀態與 `request` 指到的原件認出排隊中與已送出；禁止掃收件匣猜。〔主編補〕
- **S-09-67** 重啟時所有 `sent` 的請求必須改成 `failed`，並在請求者的落點旁寫 `<result>.status.json`，`reason` 填 `result_unknown`、`ext.retryable` 填 `false`。〔主編補〕
- **S-09-68** 禁止任何一方自動重發：LLM 世界不重送，agent 也禁止自己判斷要不要再問一次；重發必須是父腳本 `on_fail` 那一步明寫的決定。〔主編補〕
- **S-09-50** 結果、用量與錯誤必須只靠結果落點、`.usage.json` 與狀態檔回到請求者；收下之後才失敗的禁止回信。只有 S-09-83 那種「根本沒收下」的才回信。〔主編補〕

## 舊紀錄什麼時候清

- **S-09-69** `.aos/requests/` 裡 `done` 與 `failed` 的紀錄及其 `.aos/llm-done/` 原件，必須從 `updated_at` 起一起保留 `reap_after_ms`，之後由 LLM 世界自己刪。〔主編補〕
- **S-09-70** `queued` 與 `sent` 的紀錄及其 `.aos/llm-inflight/` 原件禁止清；壽命由 LLM 世界負責，跟父地的清理無關。〔主編補〕
- **S-09-71** LLM 世界禁止刪請求者地上的任何東西，包括結果落點、`.usage.json` 與狀態檔。〔主編補〕

## 範例

一筆請求的狀態（`request` 指向一字不動的投遞物原件）：

```json
{
  "format_version": 1, "id": "7f3a1c2b9d4e5061728394a5b6c7d8e9",
  "from": "/home/u/proj/writer", "state": "queued", "unit": null,
  "updated_at": "2026-09-05T12:00:00.480Z",
  "prompt": "/home/u/proj/writer/work/prompt.txt",
  "result": "/home/u/proj/writer/work/reply.txt",
  "request": "llm-inflight/7f3a1c2b9d4e5061728394a5b6c7d8e9.json",
  "ext": { "waiting_tier": "smart" }
}
```

成功時寫在落點旁的用量（`/home/u/proj/writer/work/reply.txt.usage.json`）：

```json
{
  "format_version": 1, "request_id": "7f3a1c2b9d4e5061728394a5b6c7d8e9",
  "unit": "local-smart", "tokens_in": 812, "tokens_out": 233, "ms": 4103
}
```

## 待使用者拍板

- S-09-19 原件改名進 `llm-inflight/`，進度另寫 `requests/`。〔裁決 2026-09-05〕｜S-09-24～S-09-26 配同 `tier` 的單元、每筆跑一次 `aos llm`、失敗寫 `backend_error`。〔主編補〕
- S-09-83 請求寫壞＝搬 `rejected/` ＋回信＋`reason: rejected`（P19）。〔主編補〕
- S-09-20 排隊次序：先 `priority`、同分再比 `at`。〔主編補〕
- S-09-84 `max_parallel`＝一輪派幾筆，兩個上限取小（P17）。〔主編補〕
- S-09-59 併發只由 LLM 世界自己數，daemon 不數。〔裁決 2026-09-05〕
- S-09-85、S-09-86 配不到 tier 就記 `ext.waiting_tier` 繼續等，禁止悄悄降級。〔主編補〕
- S-09-60～62 成功先寫 `.usage.json`，失敗不寫；S-09-87／88 排隊從 `at` 算，逾時訊息寫毫秒。〔主編補〕
- S-09-32 舊排隊機制作廢、五條規則保留。〔預設 2026-09-05，G-04〕
- S-09-63～65 每筆一份進度、`request` 指原件；S-09-89 收場把原件改名進 `llm-done/`。〔裁決 2026-09-05〕｜S-09-66、90 進度不當成敗憑據、據此去重。〔主編補〕
- S-09-48～50 重啟靠進度認人、收下後失敗不回信；S-09-67／68 把 `sent` 標 `failed`，不自動重發。〔主編補〕
- S-09-69～S-09-71 `done`／`failed` 保留 `reap_after_ms` 後自己刪；`queued`／`sent` 不清；不碰請求者地上的檔（B47）。〔主編補〕
- S-09-91～S-09-94 一輪＝同時起最多 `max_parallel` 支子行程跑完為止；一輪開頭與等待中讀控制收件匣；`stop` 等在跑的結束再寫 `stopped.json`。
- S-09-95～98 `--usage-out` 拆出思考 token；`--request-id`、serve 每筆都帶、兩份用量檔不同。〔主編補〕
- S-09-99 `llm_world` 沒有 `.aos/` 時由 `aos daemon start` 或 `aos llm init` 先 `aos init` 它。

## 現況對照

今天沒有請求這個東西，也就沒有請求狀態、用量檔、保留期，`aos llm serve` 也不存在。今天 `aos llm` 排不到槽就 exit 75 當場退回，等於沒有隊伍；被殺掉的呼叫不留痕跡，重啟後沒人知道哪一筆已經送到後端過。
