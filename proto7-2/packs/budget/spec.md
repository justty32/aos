# budget 包 spec（第一版）

← [budget 包](README.md)｜[核心 spec](../../spec.md)｜[step 包 spec](../step/spec.md)

寫的是規則；理由在 [loop5 藍圖](../../notes/blueprint-loop5.md) §2、§3。路徑相對 node（任務的 cwd）；預算資料夾 `A`＝`<node>/budget/<id>/`，`<id>` 就是預算識別（英數、`_`、`-`，最多 32 字）。

## 1. 預算資料夾與檔案所有權

| 檔 | 誰寫 | 內容 |
|---|---|---|
| `A/grant.json` | 發行者（人） | grant（§2），開帳後不改 |
| `A/ledger.json` | 帳任務（`init` 開第一份） | 帳（§3）；`ledger.json.lock`／`ledger.lock` 是鎖 |
| `A/inbox/<kid>.<op>.<nonce>.json` | 包裝程式 | 給帳的請求；帳發回條後刪 |
| `A/receipts/<同名>` | 帳任務 | 回條；包裝程式讀完刪 |
| `A/gateway/<kid>.json` | 入口（在包裝程式／`cancel` 程序裡跑，持同名 `.lock`） | 准入意圖與終局回條（§4） |
| `A/backend.json` | 假後端（持 `.lock`） | `{"accepted": 受理次數, "effects": {kid: 效果}}`（§5） |
| `A/error.json` | 帳任務 | 最近一筆錯誤 `{"kind","where","why","at"}`，覆寫 |

`kid`＝`sha256(JSON [budget, holder, request])` 前 20 個 hex；檔內都帶完整的 `key`。v1 不自動清任何紀錄（藍圖 §2 保存）；`inbox/`、`receipts/` 只有在途的檔。

## 2. grant 與時鐘

```json
{"v": 1, "grant": "g1", "budget": "demo", "holder": "api", "resource": "fakeapi.calls", "gateway": "fakeapi",
 "amount": 5, "clock": "completed_tock", "from": 0, "until": 100, "delegate": false}
```

- 欄位齊全、型別對（`amount`、`from`、`until` 非負整數、`from ≤ until`；`clock` 只准 `completed_tock`；`delegate` 必須是 `false`）才算讀到；`budget` 要等於資料夾名。
- **時鐘** `c`＝本 node 的 completed_tock：`.aos/round.json` 照核心判定（核心 spec §3）是 closed 取 `round`、open 取 `round−1`；不存在、讀不到、壞＝未知。帳記住看過的最大值 `clock_hw`；`c < clock_hw`（時鐘倒退，例如 round.json 被重建）＝未知。
- **判定** `judge(grant, holder, resource, gateway, c)` 依序：grant 讀不到／壞／雜湊跟帳記的不同＝`unknown`；`parent` 存在或 `delegate` 不是 false＝`denied`（子 grant）；holder／resource／gateway 不符＝`denied`；`c` 未知＝`unknown`；`c < from`＝`not_yet`（非終局）；`c ≥ until`＝`denied`（到期）；其餘 `ok`。

## 3. 帳

```json
{"v": 1, "budget": "demo", "grant": "g1", "grant_sha": "…", "initial": 5, "available": 4, "inflight": 1, "used": 0,
 "clock_hw": 7, "seq": 1,
 "ops": {"<kid>": {"key": {"budget", "holder", "request"}, "digest": "…", "content": {…}, "amount": 1,
                   "stage": "reserved|settled", "reserve": {"seq", "tock", "at"},
                   "settle": {"seq", "used", "outcome", "evidence": "<入口回條 sha256>", "at"}}},
 "log": [{"seq": 1, "op": "reserve", "kid", "amount": 1, "used": null, "available": 4, "inflight": 1, "used_total": 0,
          "tock": 7, "at"}]}
```

- **開帳**（`init`）：`ledger.json` 已存在＝拒絕；grant 判定不是 ok 也照開（效期是使用時的事），但子 grant、欄位不合＝拒絕。帳任務**不自動開帳**：`ledger.json` 不存在、讀不到、壞＝不受理任何請求，記 `error.json`，請求留在 `inbox/`。
- **請求**＝`{"op": "reserve"|"settle", "key", "content": {"resource", "gateway", "amount", "payload_sha"}, "digest"}`（settle 只要 `op`、`key`）。`digest`＝content 加 key 的雜湊；attempt 等傳輸資訊不在裡面。請求檔壞＝回條 `bad`、刪請求。
- **reserve(K)**：K 已在帳上——digest 不同＝`conflict`；相同＝照帳上的階段回 `reserved`／`settled`（重播）。不在——判定 grant（§2），不是 ok 回 `denied`／`not_yet`／`unknown`；`available < amount`＝`denied`（額度不足）；否則 `available −= amount`、`inflight += amount`、記 ops 與 log。**拒絕不入帳**（沒動餘額，重送照當下再判）。
- **settle(K)**：K 不在帳上＝`unknown`；已結算＝重播同一結果；否則帳**自己讀** `A/gateway/<kid>.json`：不是終局（沒有、讀不到、`intent`）＝`unknown`，預留留著；終局就以回條的 `used`（0 或 amount）結算：`inflight −= amount`、`used += u`、`available += amount − u`。結算不看時鐘。
- **提交**：一筆轉移＝讀帳 → 改 → `write_json`（原子 rename）一次寫入餘額、ops、log、`seq`；之後才寫回條、刪請求。被殺在寫入前＝沒發生；寫入後回條前＝重開時請求還在 `inbox/`，帳從 ops 重建同一回條（不重扣）。
- **不變條件**：log 每一筆都滿足 `available + inflight + used_total = initial` 且各項 ≥ 0；每個 K 最多一筆 reserve、一筆 settle。

## 4. 入口

`run(K, content, payload)`，全程持 `gateway/<kid>.json.lock`：

1. 讀 `gateway/<kid>.json`：讀不到／壞＝`unknown`。終局（`stage: done`）＝回它（`cancelled` 不比內容；其餘 digest 不同＝`conflict`）。`intent`＝已准入：**不再查 grant 與效期**，直接到第 4 點。
2. 首次准入：讀帳（讀不到／壞＝`unknown`），以帳記的 grant 雜湊與 `clock_hw` 判定 grant（§2）：`unknown`／`not_yet` 回非終局、不寫檔；`denied`（含到期）寫終局 `{"stage": "done", "outcome": "denied", "used": 0}`。
3. 核對預留：帳上 K 要是 `reserved` 且 digest 相同，不是＝非終局 `unknown`／`conflict`、不寫檔。通過才寫 `{"stage": "intent", "admitted_tock": c}`。
4. 呼叫假後端 `accept(K, payload)`（§5，以 K 去重），寫終局 `{"stage": "done", "outcome": accepted|failed|rejected, "used", "response"}`。

`cancel(K)`（同一把鎖）：已終局＝回原回條（不是 cancelled 就表示取消不成）；`intent`＝向後端查 K：有效果就寫成那個終局（取消不成），沒有就寫 `cancelled`（後端呼叫只在鎖內發生，所以持鎖時查不到＝沒發生，這只對可查回的假後端成立）；沒紀錄＝寫 `cancelled`。`cancelled`、`denied`、`rejected` 的 `used` 是 0；`accepted`、`failed` 是 amount。

## 5. 假後端

`backend.json` 用 `edit_json` 一次寫入「`effects[kid]` ＋ `accepted` 計數」。同 kid 已有效果＝回原效果、不再計數。payload 的 `mode`：`ok`（預設，受理、計 1）、`fail`（受理後處理失敗、計 1、outcome `failed`）、`reject`（明確拒絕、計 0）。`query(kid)` 只讀。

## 6. call 包裝程式

`aos7-budget call A --holder H --request R [--amount 1] [--resource fakeapi.calls] [--payload 檔] [--out 檔] [--patience N]`（入口固定是 `fakeapi`）：

1. 送 reserve、等回條：`denied`／`conflict`／`bad`＝退出 1；`unknown`／`not_yet`／等不到＝退出 3。`settled`（重播）跳到第 4 點讀入口回條。
2. 入口 `run`：非終局＝退出 3（預留留著）；`conflict`＝退出 1。
3. 送 settle、等回條：`settled` 才往下；其餘＝退出 3。
4. 結果（stdout 最後一行；有 `--out` 時原子寫一份）`{"kid","key","outcome","used","response","settle"}`；`outcome: accepted` 退出 0，其餘終局退出 1。

- **等回條的耐性**：completed_tock 比開始時多 `patience`（預設 5）回合仍沒回條＝退出 3；時鐘未知或 pause 時不到期。請求檔留著，帳之後照樣處理（同 K 冪等）。
- 對同 K 冪等：重跑只把沒做完的做完。step 步可標 `idempotent: true`、`on_unknown: resend`；step 的 `ok:false` 不代表退款，退款只看入口回條。

## 7. 測試鉤子

`A/.crash` 寫一個點名：程式到那點就刪檔、SIGKILL（在任務裡殺整個程序群組，模擬槽被收）。點：`reserve-before-commit`、`reserve-after-commit`、`settle-before-commit`、`settle-after-commit`（帳）；`call-after-reserve`、`gateway-after-intent`、`backend-after-effect`、`gateway-after-receipt`、`call-after-settle`（包裝程式）。

## 8. 明確不管（誤用，不處理）

兩個帳任務同時跑（有 `ledger.lock` 擋，但不保證）、人手改 `ledger.json`／`gateway/`／`backend.json`、開帳後改 `grant.json`（偵測到＝未知，不前進）、不經入口直接呼叫後端、同一 node 兩個預算同名。
