# budget 任務包（grant／帳／入口）第一版

> 包名原為 account，因與 Linux account 的定義重疊改稱 **budget**（一份預算＝一個 `<node>/budget/<id>/`）；藍圖裡的 account 字樣即指本包。

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)｜細部規則：[spec.md](spec.md)｜依據：[loop5 藍圖](../../notes/blueprint-loop5.md) §2～§4、[r1 綜合](../../../proto7/notes/thinking/2026-10-04-r1-synthesis.md)、[astra-4 意見](../../notes/play/2026-10-04-astra-4-infra-evidence/contracts/summary.md#account-草稿意見不算發現)｜接法：[step 包](../step/README.md)

**一份固定的使用權（grant）＋一個單一寫者的帳（ledger）＋一個資源入口（gateway），用「預留 → 准入 → 結算」把一種整數資源的每次使用記成精確帳。** 通用任務包（原則 5、8）：把 LLM 換成 cron 仍成立；不帶 LLM、不帶分配算法；daemon／tick／step 零改動，核心不知道這個包。

| 項目 | 內容 |
|---|---|
| 分類 | 通用任務包（`layer: kernel`），單 node |
| 第一版範圍 | 單 node、一個預算、一種整數消耗資源、一個入口、一份不可再分的 grant（`delegate: false`）。沒有 split、跨 node、動態配額、LLM |
| 示範資源 | **假 API 加權成本**（`fakeapi.calls`）：每個業務請求預留 `--amount` 單位（預設 1）；帳的 `used`／`available` 是加權成本單位，`backend.json` 的 `accepted` 才是受理次數；明確拒絕計 0，已受理後失敗仍計 amount |
| 接法 | ① 帳：普通 keep 任務 `{"name": "budget-<id>", "mode": "keep", "argv": ["python3", "<proto7-2>/packs/budget/bin/aos7-budget", "ledger", "budget/<id>"]}`（`max_live` 預設 1）<br>② 使用：step 的普通 `run` 步呼叫 `aos7-budget call budget/<id> --holder H --request ${request}`（包裝程式內部 reserve → run → settle）<br>holder 由部署者寫死在 steps.json 的 argv（合作式；真偽不是 budget 的事，見 gateway 卡前置條件）<br>call 對同 K 冪等：步可標 `idempotent: true`。step 拿不到結果（包裝程式被殺、槽被收、結果沒發布）＝step 的 unknown，走步的 `on_unknown`；`resend` 時同 request 新 attempt，受 `max_resends` 限，冪等所以不重扣。拿到退出碼 3＝step 拿到結果（`ok:false`），**預設走 `fail`**；要讓 3 也走 `on_unknown`，在步上開 `unknown_codes: [3]`（step 包選項，預設空；見 [step spec](../step/spec.md)）。不開時，人手先 `status` 查 K，再 `aos7-step resume --resend` 或直接同 K 重跑 `call`。 |
| 時鐘 | 本 node 的 **completed_tock**（round.json closed 取 round、open 取 round−1；沒有合法值＝未知）；效期 `from ≤ c < until` |
| 保存 | 全在 `<node>/budget/<id>/`，活過 once 槽刪除與 step close；v1 只掃孤兒回條，其餘保存到預算明確退役（成長率與退役步驟見 spec §10） |
| 依賴 | 核心 `aos7_fs`（`fact`、`write_json`、`edit_json`、`locked`、`read_round`、`sweep_tmp`）；不依賴 step（step 只是呼叫者） |
| 程式 | `aos7_budget.py`（grant、時鐘、帳、CLI）、`aos7_budget_gate.py`（入口、假後端、call 包裝程式）、`bin/aos7-budget` |
| 範例 | `examples/fakeapi/`（grant＋步驟表：呼叫假 API 一次；call 步開 `unknown_codes: [3]`，退出 3 也同 request 重送） |
| 測試 | `tests/`（`python3 proto7-2/tests/run_all.py packs/budget/tests`；全套預設就收） |

## 第一次跑（示範 fakeapi，已實跑）

`grant.json` 放在 `<node>/budget/<id>/`，**`grant.budget` 必須等於資料夾名 `<id>`**（不同時 `init` 拒絕、退出 1）。人手指令都在 **node 目錄**下執行，路徑寫 `budget/<id>`。`<proto7-2>` 換成原型目錄的絕對路徑。

```sh
P=<proto7-2>
mkdir -p <root>/<node>/budget/demo && cp $P/packs/budget/examples/fakeapi/grant.json <root>/<node>/budget/demo/
python3 $P/bin/aos7-ctl daemon <root> register <node>
python3 $P/bin/aos7-ctl add <root>/<node> '{"name": "budget-demo", "mode": "keep", "argv": ["python3", "<proto7-2>/packs/budget/bin/aos7-budget", "ledger", "budget/demo"]}'
python3 $P/bin/aos7-daemon <root> &
cd <root>/<node>
python3 $P/packs/budget/bin/aos7-budget init budget/demo     # {"ok": true, ...}（daemon 沒起也能開帳）
python3 $P/packs/budget/bin/aos7-budget call budget/demo --holder api --request r1 --payload $P/packs/budget/examples/fakeapi/payload.json
                                                             # outcome accepted、used 1、退出 0；同 K 再跑拿同一份、不再扣
python3 $P/packs/budget/bin/aos7-budget status budget/demo   # initial 3、available 2、inflight 0、used 1
python3 $P/bin/aos7-ctl daemon <root> stop --kill
```

`call` 要等帳任務起來、經過回合才拿得到回條。經 step 呼叫的接法見 `examples/fakeapi/steps.json`（`@BUDGET@` 換成 `bin/aos7-budget` 的絕對路徑）。

## 三個組件（契約卡，細節在 spec.md）

**grant：使用權（`grant.json`，判斷在 `aos7_budget.judge`）**
- 職責：判斷誰可在指定預算、資源、入口與效期內使用多少資源。
- 前置條件：發行者寫一份唯讀、固定內容的 `grant.json`（預算、持有人、資源、入口、額度、時鐘、`from`／`until`、`delegate: false`）；帳開帳時記下它的雜湊，之後不改。時鐘只往前：重建 round.json（回合歸零）＝換預算識別、不移植舊 grant。
- 保證：判定回 **准許（`ok`）／拒絕（`denied`）／未知（`unknown`）／尚未生效（`not_yet`，還沒到 `from`，非終局）**（spec §2），`not_yet` 不存成永久拒絕；讀不到、壞掉、內容被改、時鐘讀不到或倒退＝未知，不當「沒有限制」也不當「已過期」；`delegate` 不是 false 或帶 `parent` 的子 grant＝拒絕（開帳也拒）；效期是半開 `from ≤ c < until`，到期只擋**新的**預留與首次准入。
- 明確不管：量測資源、即時餘額（帳的事）、供應或完成期限、惡意繞過（合作式，同核心 §11）；grant 再分（v1 不實作、不宣稱支援）。

**ledger：帳（`ledger.json`，寫者是 `aos7-budget ledger` 這個 keep 任務）**
- 職責：處理 reserve／settle，保存可用、在途、已用，以及每個業務鍵的預留、結算與去重證據。
- 前置條件：同一預算只有一個帳任務（keep、`max_live: 1`；另拿 `ledger.lock` 防舊代殘留雙寫）；帳要先 `aos7-budget init` 開好（帳不存在不自動開）；持有人經 `inbox/` 送請求；settle 的證據由帳自己讀入口紀錄，不信請求方報的量。
- 保證：每筆轉移把餘額、操作結果、去重紀錄與轉移記錄**同一次原子寫入**，之後才發回條；回條沒寫就被殺，重開從帳重建同一回條、不再扣款；每次持久轉移滿足「可用＋在途＋已用＝初始額度」且各項非負；同 K 重播不重扣；入口回條不是終局（沒有、半寫、intent）＝預留留著；入口 key／digest 綁定預留（cancelled、used 0、digest null 只豁免 digest），以 `0 ≤ used ≤ amount` 結算、退回未用額度；`overrun` 非負整數（缺＝0）記在 settle／log 與帳頂累計。billing 存在且非 final／overrun＝非終局、預留留著；無 billing＝final（舊入口相容）。帳讀不到／壞掉＝不受理任何請求（不當空帳）。
- 明確不管：把 step `ok:false`、`never_started`、逾時、取樣的 `usage.json` 當未支用證明；跨 node 一致性；拒絕的預留（額度不足、不符、到期）不入帳，只回條。

**gateway：入口（`aos7_budget_gate.run`／`cancel`，紀錄在 `gateway/<kid>.json`）＋假後端**
- 職責：首次准入前核對資格與預留、准入後呼叫後端、保存支用證據（終局回條）；也處理取消。
- 前置條件：合作式部署（請求人自報的 holder 對應 grant 持有人，不提供 OS 隔離）；呼叫前已有同 K、同內容的預留；同 K 的准入、恢復、取消都在 `gateway/<kid>.json.lock` 下互斥；後端呼叫只經入口。
- 保證：首次准入前查 grant 與效期，未知不放行、不存成永久拒絕；呼叫後端前先持久記准入意圖（intent）；已准入者恢復不再查效期，只向後端查回／重播同 K；終局回條（accepted／failed／rejected／denied／cancelled）寫了就固定，重送同 K 拿同一份；取消與支用互斥，留下 K 已取消的終局紀錄，晚到的 run(K) 也不會執行。假後端把「K 的效果＋受理計數」同次原子提交、以 K 去重，所以同 K 後端效果最多一次，效果完成、回條未寫也查得回。
- 明確不管：呼叫者自報的 holder 是否真為本人；替任意外部 API 保證只發生一次（本保證只對這個可查回的假後端成立）；不可查回的後端的取消（intent 帶 gateway 且非 fakeapi＝unknown、不寫檔、CLI 退出 3；終局只來自後端證據，spec §4、§9）；支用成功不等於工作產物成功。

**call 包裝程式（接 step 的那一層，不是第四個組件）**：`aos7-budget call` 以業務鍵 `K = (budget_id, holder, request)` 依序做 reserve → gateway run → settle。對同 K 冪等，step 步可標 `idempotent: true`；attempt、`slot#run` 只當追查資訊，不是新扣款鍵。退出碼：

- 0＝後端受理成功，已結算，終局結果已交付（stdout 最後一行＋有指定時的 `--out`）。
- 1＝已有終局但不成功：後端 failed／rejected、入口 denied／cancelled 已結算，或 reserve 被拒（denied／conflict／bad）、入口 conflict。
- 2＝壞輸入：參數不合、payload 不存在或不是 JSON；沒送任何請求。
- 3＝**本次呼叫未完整交付終局結果**：可能還沒預留、在途（預留或 intent 留著），或已結算但 `--out` 寫入失敗。先 `aos7-budget status A --holder H --request R` 查 K，再同 K 重送 `call`（冪等，不重扣）。

只有 0 與 1 保證有終局結果交付。

## 人手指令

- `aos7-budget init budget/<id>`：照 `grant.json` 開帳（帳已存在、grant 不合或是子 grant＝拒絕）。
- `aos7-budget status budget/<id> [--holder H --request R]`：印餘額，或某個 K 的階段、預留、入口證據與結算結果。
- `aos7-budget cancel budget/<id> --holder H --request R`：取消 K（已有支用就回原終局、不取消；退出 0 取消了／1 取消不成／3 未知）；取消成功（入口終局 `cancelled`）之後 `settle` 或同 K 重跑 `call` 才按 used＝0 結算；取消不成就照原終局的 used 結算（`accepted`／`failed` 是 amount），不能假定退款（spec §4）。
- 退役：`inflight == 0` 後寫 `budget/<id>/retired.json`，帳不收新 K；步驟見 spec §10。
- `aos7-budget settle budget/<id> --holder H --request R`：只送結算（入口證據已終局才會結）。

## 界線

- 預留到結算之間 step 失敗、槽被刪、結果沒發布、`close`：帳與入口仍認得 K，同 K 重跑 `call` 只把沒做完的做完；新工作 inst 產生新 request 才是新交易。
- call 回 3 可能尚未結算，也可能已結算但 `--out` 寫入失敗；先查 K 再同 K 重送，**不自動退款**。step `ok:false` 不代表退款，退款只看入口回條。
- overrun 只記帳、不停准入（軟預算；停准入需對帳指令，另輪）；billing pending 不自動補帳，R 留著直到人手處理。其他已知界線見 spec §9。
- 時鐘只有本 node 的 completed_tock：pause 不前進；daemon 重開接續原回合；重建時鐘（round.json 歸零）須換預算識別、不移植舊 grant（帳偵測到時鐘倒退＝未知）。
