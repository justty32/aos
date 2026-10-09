# budget 包 spec（第一版）

← [budget 包](README.md)｜[核心 spec](../../spec.md)｜[step 包 spec](../step/spec.md)

寫的是規則；理由在 [loop5 藍圖](../../notes/blueprint-loop5.md) §2、§3 與 [loop6 藍圖](../../notes/blueprint-loop6.md) §1、§2。路徑相對 node（任務的 cwd）；預算資料夾 `A`＝`<node>/budget/<id>/`，`<id>` 就是預算識別（英數、`_`、`-`，最多 32 字）。

## 1. 預算資料夾與檔案所有權

| 檔 | 誰寫 | 內容 |
|---|---|---|
| `A/grant.json` | 發行者（人） | grant（§2），開帳後不改 |
| `A/ledger.json` | 帳任務（`init` 開第一份） | 帳（§3）；`ledger.json.lock`／`ledger.lock` 是鎖 |
| `A/inbox/<kid>.<op>.<nonce>.json` | 包裝程式 | 給帳的請求；帳發回條後刪 |
| `A/receipts/<同名>` | 帳任務 | 回條；包裝程式讀完刪，沒人讀的孤兒帳自己掃（§9 第 3 條） |
| `A/gateway/<kid>.json` | 入口（在包裝程式／`cancel` 程序裡跑，持同名 `.lock`） | 准入意圖與終局回條（§4；也供 llmcall 的 `llm.fake` 入口寫證據） |
| `A/backend.json` | 假後端（持 `.lock`） | `{"accepted": 受理次數, "effects": {kid: 效果}}`（§5） |
| `A/error.json` | 帳任務 | 最近一筆錯誤 `{"kind","where","why","at"}`，覆寫 |
| `A/retired.json` | 人 | 退役標記（§10），寫了就不收新 K |

用 `write_json` 寫的資料夾由本包自己掃：帳任務起時掃 `A/`、`inbox/`、`receipts/`、`gateway/` 裡寫者已不在的暫存檔。

`kid`＝`sha256(JSON [budget, holder, request])` 前 20 個 hex；檔內都帶完整的 `key`。v1 不自動清帳、入口、後端的紀錄（保存到退役，§10）；`inbox/`、`receipts/` 只有在途的檔，加上帳還沒掃掉的孤兒回條。

## 2. grant 與時鐘

```json
{"v": 1, "grant": "g1", "budget": "demo", "holder": "api", "resource": "fakeapi.calls", "gateway": "fakeapi",
 "amount": 5, "clock": "completed_tock", "from": 0, "until": 100, "delegate": false}
```

- 欄位齊全、型別對（`amount`、`from`、`until` 非負整數、`from ≤ until`；`clock` 只准 `completed_tock`；`delegate` 必須是 `false`）才算讀到；`budget` 要等於資料夾名。
- **時鐘** `c`＝本 node 的 completed_tock：`.aos/round.json` 照核心判定（核心 spec §3）是 closed 取 `round`、open 取 `round−1`；不存在、讀不到、壞＝未知。帳每處理一件請求就讀一次 c，合法且大於 `clock_hw` 就推高（含拒絕、重播；這是只動 `clock_hw` 的單獨一次寫入，不動餘額與 log）；`c < clock_hw`（時鐘倒退）＝未知。
- **前置條件**（發行者／部署者守）：時鐘只往前。重建 round.json（回合歸零）＝換預算識別（新資料夾）、不移植舊 grant；帳只抓得到退到 `clock_hw` 以下的倒退（§9 第 2 條）。
- **判定** `judge(grant, holder, resource, gateway, c)` 依序：grant 讀不到／壞／雜湊跟帳記的不同＝`unknown`；`parent` 存在或 `delegate` 不是 false＝`denied`（子 grant）；holder／resource／gateway 不符＝`denied`；`c` 未知＝`unknown`；`c < from`＝`not_yet`（非終局）；`c ≥ until`＝`denied`（到期）；其餘 `ok`。

## 3. 帳

```json
{"v": 1, "budget": "demo", "grant": "g1", "grant_sha": "…", "initial": 5, "available": 4, "inflight": 1, "used": 0, "overrun": 0,
 "clock_hw": 7, "seq": 1,
 "ops": {"<kid>": {"key": {"budget", "holder", "request"}, "digest": "…", "content": {…}, "amount": 1,
                   "stage": "reserved|settled", "reserve": {"seq", "tock", "at"},
                   "settle": {"seq", "used", "overrun", "outcome", "evidence": "<入口回條 sha256>", "at"}}},
 "log": [{"seq": 1, "op": "reserve", "kid", "amount": 1, "used": null, "available": 4, "inflight": 1, "used_total": 0,
          "tock": 7, "at"}]}
```

- **開帳**（`init`）：`ledger.json` 已存在＝拒絕；grant 判定不是 ok 也照開（效期是使用時的事），但子 grant、欄位不合＝拒絕。帳任務**不自動開帳**：`ledger.json` 不存在、讀不到、壞＝不受理任何請求，記 `error.json`，請求留在 `inbox/`。
- **請求**＝`{"op": "reserve"|"settle", "key", "content": {"resource", "gateway", "amount", "payload_sha"}, "digest"}`（settle 只要 `op`、`key`）。`digest`＝content 加 key 的雜湊；attempt 等傳輸資訊不在裡面。請求檔壞＝回條 `bad`、刪請求。
- **reserve(K)**：K 已在帳上——digest 不同＝`conflict`；相同＝照帳上的階段回 `reserved`／`settled`（重播）。不在——`retired.json` 在＝`denied`（已退役）、讀不到＝`unknown`；再判定 grant（§2），不是 ok 回 `denied`／`not_yet`／`unknown`；`available < amount`＝`denied`（額度不足）；否則 `available −= amount`、`inflight += amount`、記 ops 與 log。**拒絕不入帳**（沒動餘額，重送照當下再判）。
- **settle(K)**：K 不在帳上＝`unknown`；已結算＝重播同一結果；否則帳**自己讀** `A/gateway/<kid>.json`：沒有、讀不到、不是物件或 `stage != done`＝非終局。`billing` 存在且非 `final`／`overrun`＝非終局（billing pending，不要求 used）；無 `billing`＝final（舊入口相容）。非終局一律 `unknown`、預留留著。
- **結算證據**：終局的 `used` 須是整數；`key` 須等於帳上的 key、`digest` 須等於帳上的 digest；唯一豁免 digest 的情況是 `outcome: cancelled` 且 `used: 0` 且 `digest` 欄存在且為 null（缺欄不豁免）。`0 ≤ used ≤ amount` 才結算：`inflight −= amount`、`used += u`、`available += amount − u`。`overrun` 缺＝0，須是非負整數，記在 settle 與該筆 log，帳頂 `overrun` 累計（舊帳缺＝0，第一次結算時補上，即使是 0）。任一不合＝`unknown`，不動帳（`clock_hw` 照 §2 可推進）。結算不看時鐘，log 的 tock 是 null；守恆式不含 overrun。
- **提交**：一筆轉移＝讀帳 → 改 → `write_json`（原子 rename）一次寫入餘額、ops、log、`seq`；之後才寫回條、刪請求。被殺在寫入前＝沒發生；寫入後回條前＝重開時請求還在 `inbox/`，帳從 ops 重建同一回條（不重扣）。
- **不變條件**：log 每一筆都滿足 `available + inflight + used_total = initial` 且各項 ≥ 0；每個 K 最多一筆 reserve、一筆 settle。

## 4. 入口

`run(K, content, payload)`，全程持 `gateway/<kid>.json.lock`：

1. 讀 `gateway/<kid>.json`：讀不到／壞＝`unknown`。終局（`stage: done`）＝回它（`cancelled` 不比內容；其餘 digest 不同＝`conflict`）。`intent`＝已准入：**不再查 grant 與效期**，直接到第 4 點。
2. 首次准入：讀帳（讀不到／壞＝`unknown`），以帳記的 grant 雜湊與 `clock_hw` 判定 grant（§2）：`unknown`／`not_yet` 回非終局、不寫檔；`denied`（含到期）寫終局 `{"stage": "done", "outcome": "denied", "used": 0}`。
3. 核對預留：帳上 K 要是 `reserved` 且 digest 相同，不是＝非終局 `unknown`／`conflict`、不寫檔。通過才寫 `{"stage": "intent", "admitted_tock": c}`。
4. 呼叫假後端 `accept(K, payload)`（§5，以 K 去重），寫終局 `{"stage": "done", "outcome": accepted|failed|rejected, "used", "response"}`。後端讀寫不到（`backend.json` 讀不到、鎖拿不到）＝回非終局 `{"outcome": "unknown", "stage": "intent"}`、不寫終局，intent 留著（同 K 重送時再問後端）。

`cancel(K)`（同一把鎖）：已終局＝回原回條（不是 cancelled 就表示取消不成）；`intent`＝向後端查 K：有效果就寫成那個終局（取消不成），沒有就寫 `cancelled`（後端呼叫只在鎖內發生，所以持鎖時查不到＝沒發生，這只對可查回的假後端成立）；沒紀錄＝寫 `cancelled`。`cancelled`、`denied`、`rejected` 的 `used` 是 0；`accepted`、`failed` 是 amount。
取消成功新寫出的 `cancelled` 終局帶齊凍結欄（blueprint-llm2 §4）：`gateway`、`call_id`＝K.request、`usage: null`、`overrun: 0`、`billing: "final"`、`raw_sha: null`；`digest` 沿用 intent 的值，沒紀錄＝null。`gateway` 取 intent 的欄，缺則取帳上 `ops[kid].content.gateway`（字串），帳讀不到／沒 K／沒欄＝`fakeapi`，不因此變 unknown。

**cancel 的前置條件**：後端對 K 可查回（有沒有效果查得到確定答案）。intent 帶 `gateway` 欄且不是 `fakeapi`（如 `llm.fake`）＝`unknown`，不查後端、不寫檔，CLI 退出 3；不可查回入口的終局只來自後端證據（§9 第 1 條）。

## 5. 假後端

`backend.json` 用 `edit_json` 一次寫入「`effects[kid]` ＋ `accepted` 計數」。同 kid 已有效果＝回原效果、不再計數。每個業務請求預留 `--amount` 單位（預設 1）；帳的 `used`／`available` 是加權成本，`accepted` 才是受理次數。payload 的 `mode`：`ok`（預設，受理、成本計 amount）、`fail`（受理後處理失敗、成本仍計 amount、outcome `failed`）、`reject`（明確拒絕、成本計 0）；ok／fail 的受理次數各加 1，reject 不加。`query(kid)` 只讀。

## 6. call 包裝程式

`aos7-budget call A --holder H --request R [--amount 1] [--resource fakeapi.calls] [--payload 檔] [--out 檔] [--patience N]`（入口固定是 `fakeapi`）：

1. 先讀 payload：不存在或不是 JSON＝退出 2；讀不到＝退出 3（`stage: payload`），不送請求。送 reserve、等回條：`denied`／`conflict`／`bad`＝退出 1；`unknown`／`not_yet`／等不到＝退出 3。`settled`（重播）讀入口回條：沒有、讀不到、不是終局＝退出 3（`stage: replay`），不以帳的 settle 補欄、不寫 `--out`；有終局才跳到第 4 點。
2. 入口 `run`：非終局＝退出 3；`conflict`＝退出 1。
3. 送 settle、等回條：`settled` 才往下；其餘＝退出 3。
4. 結果（stdout 最後一行；有 `--out` 時原子寫一份）`{"kid","key","outcome","used","response","settle"}`；`outcome: accepted` 退出 0，其餘終局退出 1。

- 0＝後端受理成功，已結算，終局結果已交付（stdout 最後一行＋有指定時的 `--out`）。
- 1＝已有終局但不成功：後端 failed／rejected、入口 denied／cancelled 已結算，或 reserve 被拒（denied／conflict／bad）、入口 conflict。
- 2＝壞輸入：參數不合、payload 不存在或不是 JSON；沒送任何請求。
- 3＝**本次呼叫未完整交付終局結果**：可能還沒預留、在途（預留或 intent 留著），或已結算但 `--out` 寫入失敗。先 `aos7-budget status A --holder H --request R` 查 K，再同 K 重送 `call`（冪等，不重扣）。

只有 0 與 1 保證有終局結果交付。

- **等回條的耐性**：completed_tock 比開始時多 `patience`（預設 5）回合仍沒回條＝退出 3；時鐘未知或 pause 時不到期。請求檔留著，帳之後照樣處理（同 K 冪等）。
- **共同故障邊界**：`call`、`cancel`、`settle` 途中任何讀寫不到（核心 `Unknown`、帳／後端讀不到、`OSError`）＝未知：stdout 印一行 `{"outcome": "unknown", "stage", "why"}`、退出 3、不留 traceback，不推定帳與入口的階段（可能尚未預留、在途，或已結算但 `--out` 寫入失敗）。`cancel` 退出碼：0＝取消了、1＝已有別的終局（取消不成）、3＝未知。不重試、不動帳。
- 對同 K 冪等：重跑只把沒做完的做完。step 步可標 `idempotent: true`。step 拿不到結果（包裝程式被殺、槽被收、結果沒發布）＝step 的 unknown，走步的 `on_unknown`；`resend` 時同 request 新 attempt，受 `max_resends` 限，冪等所以不重扣。拿到退出碼 3＝step 拿到結果（`ok:false`），**預設走 `fail`**；要讓 3 也走 `on_unknown`，在步上開 `unknown_codes: [3]`（step 包選項，預設空；見 [step spec](../step/spec.md)）。不開時，人手先 `status` 查 K，再 `aos7-step resume --resend` 或直接同 K 重跑 `call`。step 的 `ok:false` 不代表退款，退款只看入口回條。

## 7. 測試鉤子

`A/.crash` 寫一個點名：程式到那點就刪檔、SIGKILL（在任務裡殺整個程序群組，模擬槽被收）。點：`reserve-before-commit`、`reserve-after-commit`、`settle-before-commit`、`settle-after-commit`（帳）；`call-after-reserve`、`gateway-after-intent`、`backend-after-effect`、`gateway-after-receipt`、`call-after-settle`（包裝程式）。

## 8. 明確不管（誤用，不處理）

兩個帳任務同時跑（有 `ledger.lock` 擋，但不保證）、人手改 `ledger.json`／`gateway/`／`backend.json`、開帳後改 `grant.json`（偵測到＝未知，不前進）、不經入口直接呼叫後端、同一 node 兩個預算同名。

## 9. 已知界線（v1）

1. **取消靠後端可查回**：`cancel` 對 intent 寫 `cancelled` 只因假後端可查回且呼叫在同一把 K 鎖內；不可查回入口的 intent，cancel 回 `unknown`、不寫檔，終局只來自後端證據（§4）。
2. **時鐘倒退只在退到 `clock_hw` 以下才抓得到**：水位隨每件請求推高（§2），但兩件請求之間的倒退、或退了仍高於水位就看不出；重建時鐘換預算識別是部署者的前置條件（原則 9：誤用）。
3. **儲存只增不清**：帳（ops、log 全檔重寫）、`gateway/<kid>.json`（＋`.lock`）、`backend.json` 的效果隨 K 增長；只有孤兒回條會清——K 已結算、`inbox/` 沒同名請求、帳第一次掃到後本 node 又完成 3 回合（`ORPHAN_ROUNDS`）仍在才刪（帳任務起時與每次回合變了各掃一次；重播由 ops 重建同一回條）。log 壓縮、容量上限等真用量出現再做。
4. **holder 是呼叫者自報**：由部署者寫死在 steps.json 的 argv（合作式）；真偽不是 budget 的事（README gateway 卡前置條件）。
5. **自動重送有上限**：step 的 `max_resends`（預設 1）用完、wrapper 仍未知，step 就停住等人；不做無上限重試。
6. **overrun 只記帳、不停准入**：軟預算；停准入需對帳指令，另輪實作。
7. **billing pending 不自動補帳**：預留 R 留著直到人手處理。

## 10. 保存與退役

- **成長率**：每個 K＝帳 `ops` 一項＋`log` 兩筆（reserve、settle）＋`gateway/<kid>.json` 與它的 `.lock` 各一檔＋`backend.json` 效果一項（受理、失敗、拒絕都記；取消、denied 沒有）。`inbox/`、`receipts/` 只有在途與待掃的孤兒。
- **保存契約**：保存到預算明確退役；退役前不刪任何帳、入口、後端紀錄。
- **退役（人手）**：① 停掉所有呼叫者（step 表不再 call 這個預算）；② `aos7-budget status` 看 `inflight == 0`，不是 0 就逐一 `settle`／`cancel` 收完；③ 寫 `A/retired.json`（`{"at", "why"}`）——帳從此不收新 K（`denied`），已有 K 照樣重播；④ 停掉帳任務（tasks.json 移除 `budget-<id>` 項）；⑤ 把資料夾整個搬走封存。退役的識別不重用（同 id＝同 K，舊呼叫者重送會在新預算扣款）。
