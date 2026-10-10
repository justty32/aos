# LLM 作者第二刀藍圖（llm2）：單次呼叫閘道＋token 部分結算（假傳輸）

依據：[llm-author][a] §6／§7／§9／§10、[llm1 藍圖](blueprint-llm1.md) §5／§7、[budget spec](../packs/budget/spec.md) §3／§4、第三段計畫（plan-2026-10-09-late，已封存） §4、[代定清單](decisions-2026-10-09.md) 第三段。G0 隊 10-09。細項與驗收走 [items json](blueprint-llm2-items.json)。

## 1. 一句話

新包 `packs/llmcall/` 當 budget 的第二種入口（`gateway: "llm.fake"`）：固定 call ID＋請求雜湊 → reserve R → intent → 假傳輸送一次 → **先存原始回覆與 usage** → 寫入口終局（U）→ settle U → 回條。budget 只放寬 settle。一端點一計量、非串流、無隱藏重試；intent 後無回覆＝unknown。

## 2. 硬約束

- 核心、step、author、adapt 零改動；G1 只讀 import `aos7_budget`，不改 budget。真模型不接。
- 識別三分（[a] §6.1）：K.request＝`call_id`（呼叫者給、英數 `_-`、≤64）；`logical` 只記；attempt 不進 K。同 call_id 異請求雜湊＝conflict。
- 每 call 固定 3 檔＋1 鎖 `<node>/llmcall/<budget>/<call_id>/`：`request.json`、`raw.json`、`receipt.json`、`request.json.lock`（整次 call／adopt 持有，拿不到＝退出 3；鎖序：call 鎖 → K 鎖）；入口證據沿用 budget 的 `budget/<id>/gateway/<kid>.json`（同一把 `.lock`）。保存到預算退役，未結算不清（第 11 題）。
- 恢復只看本地證據，**不查假遠端**（模擬不可查回的 provider）；`fake-remote.json` 只給測試數送出次數。

## 3. 流程與恢復

| 證據 | 動作 |
|---|---|
| 有 receipt | 重印，退出碼同原條 |
| 有 raw | 不送；入口已 done 就沿用，否則由 raw 重算（done.at＝raw.at）、settle、回條 |
| 入口 done、無 raw | 照 done（denied／cancelled）settle 0 |
| 入口 intent、無 raw | unknown 退出 3；不重送、R 留著（第 8 題） |
| 無入口紀錄 | 核 grant＋預留 → 寫 intent → 送一次 |

計量：`meter: "fake.total_tokens/1"`，U＝`usage.total_tokens`（非負整數），不加總其他欄；缺或非整數＝usage 未知。無已證上界＝`bound: "soft"`（第 7 題，v1 全軟）。U>R：入口 `used=R`、`overrun=U−R`、`billing: "overrun"`；usage 缺：不寫 `used`、`billing: "pending"`，不送 settle，R 留著，候選照交（第 9 題）。

## 4. 凍結介面

**回條**（`receipt.json`＝stdout 最後一行；`--out` 另存）：

```json
{"v":1,"call_id":"csv1-c1","logical":"author/csv1","kid":"3f2a…","key":{"budget":"llm","holder":"author","request":"csv1-c1"},
 "req_sha":"9b1e…","meter":"fake.total_tokens/1","bound":"soft","reserve":1000,
 "outcome":"answered","usage":{"total_tokens":623,"prompt_tokens":400,"completion_tokens":223},
 "used":623,"overrun":0,"billing":"final","raw_sha":"c0d4…","text":"{\"v\":1,\"mode\":\"keep\",…}",
 "settle":{"seq":4,"used":623,"overrun":0,"outcome":"answered","evidence":"77ab…","at":"2026-10-09T15:20:01"}}
```

- `outcome`：`answered`／`failed`／`rejected`／`denied`／`cancelled`。`usage`：原樣或 `null`。`used`：結算量（0≤used≤reserve）或 `null`（pending）。`overrun`：≥0。`billing`：`final`／`pending`／`overrun`。`settle`：帳回條或 `null`（pending）。`text`：模型原文，不解析（候選驗證是作者的事）。
- 退出碼：0＝answered＋final；1＝終局不成功（failed／rejected／denied／cancelled、reserve 拒、conflict）且 final；2＝壞輸入，未送任何請求；3＝未交付（在途、intent 無回覆、帳未回）；4＝已交付內容但帳未清（pending 或 overrun）。

**入口終局**（`gateway/<kid>.json`，帳讀）：`{"stage":"done","kid","key","digest","gateway":"llm.fake","call_id","outcome","used","usage","overrun","billing","raw_sha","at"}`；intent＝`{"stage":"intent","kid","key","digest","gateway":"llm.fake","call_id","admitted_tock","at"}`。

**CLI**：`aos7-llmcall call budget/<id> --holder H --call C --request req.json --reserve R [--logical L] [--deadline 60] [--patience 5] [--out f]`；`status … --holder H --call C`；`adopt … --holder H --call C --raw f`（人手把遲到回覆接回同 call，只在 intent 無 raw 時收；檔＝`{"call_id","req_sha","reply":{status,billed,body,usage}}`，call_id／req_sha 須與 request.json 同，否則退出 1 不寫）。

**budget 新語意**（B2）：settle 收 `0≤used≤amount`；`gateway_terminal` 先認 done 與 `billing`，`billing` 存在且非 `final`／`overrun`＝unknown 留 R（不要求 used），再驗 used；入口 `key` 須等於帳上 key、`digest` 須等於帳上 digest（唯一豁免：`cancelled` 且 used 0 且 digest null）；記 `settle.overrun`、帳頂 `overrun` 累計；模組常數 `PARTIAL_SETTLE = True`；`cancel` 遇 `gateway` 非 `fakeapi` 的 intent＝unknown、不寫檔。舊入口紀錄無 `billing`＝final。

## 5. 分線（領地互不重疊）

| 線 | 領地 | done |
|---|---|---|
| B2 15:05–16:15 | `packs/budget/` 的 `aos7_budget.py`、`aos7_budget_gate.py`（只動 cancel）、`spec.md`、`README.md`、新 `tests/test_budget_partial.py` | B2-1～6 全綠、舊 budget 測試不改仍綠 |
| G1 15:05–16:30 | 新 `packs/llmcall/`：`aos7_llmcall.py`、`aos7_llmcall_fake.py`、`bin/aos7-llmcall`、`spec.md`、`README.md`、`examples/fake/`、`tests/test_llmcall.py`；`INDEX.md` 一列 | F-01～F-04 全綠、零 skip |

G1 在 B2 進 main 前只跑 U＝R 案（舊帳收 used＝amount）；U≠R、overrun、cancel 守門案以 `skipUnless(getattr(aos7_budget,"PARTIAL_SETTLE",False))` 標，16:15 rebase 後必須全跑、零 skip 才交。

## 6. 驗收（寫死，案名照 items）

- F-01～F-04 各崩潰點 SIGKILL ×3 後同 call 重跑：`fake-remote.json` 的 `sends[C]`≤1、帳上 K 一筆 reserve 最多一筆 settle、不另造 call_id、未知不退款。
- 部分結算：初始 1000、R 300、U 120 → available 880、inflight 0、used 120；每筆 log 守恆且非負。
- 兩 call 搶最後額度：恰一個 reserved、另一個 denied 退出 1、守恆。

## 7. 第二刀代定（照 [a] §10 預設，今天生效）

- **第 7 題**：一端點一計量 `fake.total_tokens/1`；無已證上界＝軟預算，回條 `bound:"soft"`，不宣稱硬上限。
- **第 8 題**：intent 後無回覆＝unknown、R 留著、不自動重送；新生成＝新 call_id 新預留，由呼叫者明記。
- **第 9 題**：usage 缺仍交 `text`、`billing:"pending"`、R 留著、退出 4。
- **第 11 題**：只驗程序中斷（SIGKILL）；未結算／pending 資料不清；斷電持久性不承諾。

## 8. 不做

真模型、串流、多端點／多計量、價格帳、自動重送、可查回 provider、llmcall 自己的 cancel、overrun 後自動凍結預算、pending 自動補帳、作者換真 call、adapt-llm（第三刀）。

## 9. 隊長代定（好反悔）

① 包名照計畫 `packs/llmcall/`。② llmcall 寫在 budget 的 `gateway/` 下當第二種入口，帳只有一條證據路徑。③ U>R 只記帳＋退出 4，不自動停准入（軟預算下停准入需對帳指令，另輪）。④ 遲到回覆走人手 `adopt`，不讓程序自己輪詢遠端。⑤ 傳輸在 K 鎖內呼叫；budget `cancel` 會等鎖，llm 的 intent 一律回 unknown。⑥ 新退出碼 4 只屬 llmcall，budget 0～3 不變。

[a]: reviews/2026-10-05/llm-author.md
