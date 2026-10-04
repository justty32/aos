# proto7-2 第六輪藍圖（loop6）：修 A6-01／A6-02、budget 缺口收口、adapt 第一版

依據：principles 3／4／5／7／8／9／10、astra-5 報告（A6-01、A6-02）與 evidence、subd README／aos7-subd、budget README／spec／程式、step spec、r6 落地順序第 3 步、r3 轉接包草案、r5 §4 骨架、r2 出處／依據、核心 spec §3／§4.5／§5.5、component-contracts。只讀 repo，Fable 2026-10-04。
現況：核心 2757／2800 總行、2123／2200 程式；322 測試全綠 ×3；A5-01 驗收過。**本輪核心零新增**（三件事都在 `modules/subd/`、`packs/budget/`、新 `packs/adapt/`）。

## 1. A6-01、A6-02

| 條 | 根因 | 歸屬 | 修法 | 驗收探針 |
|---|---|---|---|---|
| **A6-01** 合法 stop 記錄提交中斷後重開錯收 | `aos7-subd` 第 233～237 行把「允許的 stop 已完成」拆成三步（讀 status → 寫 `stopped.json` → 寫 life=stopped），而重開只看 life；三個窗口（status 已 stopped 還沒寫 stopped.json／stopped.json 寫了 life 沒寫／tmp 未 rename）裡 life 都是 `running`，被當前代沒收乾淨去回收。合法 stop 留下的任務正是契約要保留的。 | **B／subd**（前置都成立；X 觸發但恢復路徑做了破壞性動作） | **統一一個持久判定 `allowed_stop(aosd, since)`，起點與收尾都用它，不再信 life 的 `stopped`**。判定＝子根 `status.json` 讀到且 `stopped: true` **且** `ctl-done/` 有 `op: stop`、`result.ok: true`、`result.at ≥ 本代 life.since` 的回條（核心：控制檔 stop 一定留回條、SIGTERM 父 kill 不留，spec §2.3／§2.7——這就是兩者的區別）。重開第 2 步：life 不是 `stopped` 時先問 `allowed_stop`；成立＝**補完提交**（寫 `stopped.json`、life=stopped），印「被允許的 stop 停過」、退出碼 1、不回收。收尾路徑改成同一函式＋同一順序（先 stopped.json 再 life），life 的 `stopped` 降為加速用的快取。回條舊於 `since`（上一代的 stop）不算。status／回條讀不到＝不知道＝不起、不收（既有分支）。 | 三個窗口各真 SIGKILL ×3：重開 rc 1、`stopped.json` 出現、原任務 PID／starttime 不變；刪 `stopped.json` 再起＝核心 §5.4 接回、無 run 2。反例組：父 kill（SIGTERM、無回條）照收；上一代留的舊 stop 回條＋本代父 kill 照收；G3 並行 10／10 不退化。 |
| **A6-02** backend 讀不到回 1 不回 3 | `aos7_budget_gate.backend_accept` 的 `edit_json` 在 U 時丟 `aos7_fs.Unknown`，`run()` 第 4 點與 `call()` 都沒接，traceback 落到 rc 1；`backend_query` 已轉 `LedgerDown`，只漏這一條路。 | **B／budget gateway＋call** | **一個共同故障邊界**：`run()` 第 4 點 `except (Unknown, LedgerDown)` → 回非終局 `{"outcome":"unknown","stage":"intent","why"}`（intent 已持久、不寫終局）；`call()`／`cancel`／`settle` 入口再包一層 `except Unknown` → `pending(...)` rc 3（spec §6 第 2 點本來的語意）。不加 retry、不動帳。spec §4 第 4 點補一句「後端讀寫不到＝非終局，intent 留著」。 | EIO 與真 EACCES 各一：rc 3、stdout 一行 JSON、stderr 無 traceback、intent／預留仍在；恢復後同 K rc 0、`accepted` 計 1、獨立核帳過。grant／ledger／gateway 的 EIO 對照仍回 3。 |

## 2. budget 五個缺口

| # | 缺口 | v1 做法 | 歸哪 |
|---|---|---|---|
| 1 | 已准入意圖的取消只因假後端可查詢＋per-K 鎖才安全 | **契約文字**：spec §4 cancel 段加「前置：後端對 K 可查回。不可查回的後端，intent 的取消只能記 `cancel_requested`、不得寫 `cancelled`；終局只來自後端證據，否則永遠 unknown」；README gateway 卡「明確不管」已有一半，補齊。不加旗標、不改程式（v1 只有假後端）。 | spec「已知界線」 |
| 2 | 時鐘重建只在退到帳見過最高值以下才抓得到 | **小改＋文字**：`clock_hw` 改成每次帳讀到合法 `c` 就推高（含 denied／重播），不只成功 reserve（astra 已指出現狀）；spec §2 把「重建 round.json＝換 budget id、不移植 grant」寫進 grant 卡**前置條件**（本就是人要守的，照原則 9 歸誤用）。 | 程式 ~3 行＋spec |
| 3 | 儲存只增不清（inbox／receipts 孤兒、ledger 全檔重寫含 log、gateway 每 K 一檔） | **這輪建議：不做自動清理，只做兩件便宜的**。(a) 帳任務起時與每輪順手掃 `receipts/`：K 已 `settled` 且 `inbox/` 無同名請求的回條刪掉（重播由 ops 重建，安全）；(b) spec 加「保存與退役」節：成長率（每 K＝ops 1 項＋log 2 筆＋gateway 1 檔）、退役步驟（人手：`inflight==0` → 寫 `retired.json` → 帳拒收 → 搬走資料夾）。log 壓縮、容量上限等真用量出現再做（原則 9 默認正常；v1 保存契約就是「到退役」）。 | (a) 程式 ~10 行；(b) spec |
| 4 | holder 是呼叫者參數、step 無 holder 概念 | **文字**：README 接法加「holder 由部署者寫死在 steps.json argv，合作式；真偽不是 budget 的事（gateway 卡前置已寫）」。不改程式。 | README |
| 5 | step 自動重送只一次，wrapper 連死兩次 step 停住等人 | **選項＋預設**：step 步選項 `max_resends`（非負整數，預設 1＝現狀；只在 `on_unknown: resend` 且冪等時有意義，檢查器驗型別）；budget README 寫「call 冪等，可設 2～3；停住後 `aos7-step resume --resend` 不重扣」。不做無上限重試。 | step ~4 行＋兩包 README |

A6-02 修法同時關掉 astra-4 第三條意見（unknown 不永久定案）的最後一塊。五條都寫進 budget spec 新節「§9 已知界線（v1）」，一條一行。

## 3. adapt 第一版（`packs/adapt/`，通用任務包）

**一句話**：一個普通 keep 任務，每個自己的 tock 把鄰居 node 發布的**最新值**經一條確定性鏈重算一次，寫成自己 node 的三態暫存器 `in/<sense>.json`，附依據版本與出處；核心零新增（搆得到＝§4.5 mounts、自己的鐘＝tock.json、來源的鐘＝來源 round.json、三態＝`fact`；history.py 早已這樣掛別人的 `.aos`）。

### 3.1 契約卡

| 欄 | 內容 |
|---|---|
| 職責 | 把來源的一份事實檔（位準型：最新值）投影成消費端吃得下的窄格式；每次都從**固定版本的依據**重算（不吃上一跳）；標出依據版本 `basis`、出處 `src`、鏈版本、來源鐘的年齡、來源狀態；交付三態 `ok／unknown／absent`。 |
| 前置條件 | 自己是 `max_live: 1` 的 keep；來源檔經 mounts 掛進來（空間路徑，`mount_allow` 放行）、由來源用原子 rename 寫、內容是 JSON 物件（建議帶 `seq`）；來源 node 的 `.aos/round.json` 也掛得到；鏈宣告 `<node>/adapt/<sense>.json` 過了檢查器、工作中不改；`in/<sense>.json` 只有本包寫。 |
| 保證 | 暫存器要嘛完整要嘛舊版（rename）；`state: ok` 時 `value` 一定是從 `basis.sha` 那一版算出來的、鏈每步可重算且列出 `omitted`／誤差界；來源讀不到、半寫、缺欄、路徑指不到、換算查不到＝走同一條 unknown 分支，**先靠耐性撐住舊值、到期才翻 unknown**（不假造值、不丟掉 `last`）；效期用來源回合數算、耐性用自己回合數算（pause 時都不走）；來源回合倒退＝`reset`、舊依據作廢；來源慢**不是**錯（只是年齡）、來源快只是漏取樣（記 `skipped`，不補）。 |
| 明確不管 | 來源說的是不是真話；消費者拿到 unknown 之後怎麼辦；事件／窗口（只有最新值）；不可重算的（LLM）步驟；跨子 daemon 交付；來源沒帶 `seq` 時漏了幾版；掛載權限；人手改 `in/`／鏈宣告。 |

### 3.2 最小範圍與格式

| 項目 | 第一版 |
|---|---|
| 拓撲 | 同一 daemon 根下兩個登記 node：`src`（發布者）、`dst`（消費者＋adapt 任務）；`dst` tasks.json 的 adapt 項 `mounts: {"src": "src/out", "srcclock": "src/.aos"}`。 |
| 來源檔 | `src/out/<fact>.json`＝`{"v":1, "seq": n, "round": 來源回合, "value": {...}, "at"}`（寫者用 `write_json`）；示範發布者 `examples/temp/sensor.py`：每個 tock 寫 `{"t_dc": 整數十分之一度}`。 |
| 鏈宣告 | `dst/adapt/temp.json`＝`{"sense":"temp","src":"src/out/temp.json","src_clock":"src/.aos/round.json","max_age":3,"patience":2,"stall":null,"steps":[{"select":"value.t_dc"},{"scale":{"mul":0.1,"q":0.05,"round":1}},{"threshold":{"ge":80,"as":"hot"}}],"need":["c"]}`。只准這三種步＋`need`；不開運算式（r3 不確定事第 1 條，先不碰）。 |
| 暫存器 | `dst/in/temp.json`＝`{"v":1,"sense","state":"ok|unknown|absent","value":{"c":80.1,"hot":true|false|null},"err":0.05,"basis":{"src":"src/out/temp.json","sha":"…","seq","src_round"},"chain":{"sha":"宣告雜湊"},"age_src_rounds":k,"src_state":"advancing|stalled|reset|unknown","skipped":m,"why":null,"last":{...上一份 ok 的 value+basis},"my_round":n,"at"}`。 |
| 效期 vs 耐性 | **效期** `max_age`：來源 completed_tock − `basis.src_round` > max_age ＝ 過期 → unknown（用來源的鐘，不換算，r3 共識）。**耐性** `patience`：自己連續幾回合沒有一次成功讀取 → unknown（用自己的鐘，起點 `since` 在框架建立時就寫，A4-03 教訓）。兩者都在 pause 時凍結。 |
| 來源狀態 | `src_state`：`advancing`（來源回合比上回大）、`stalled`（連續 `stall` 個自己回合沒前進；`stall: null`＝只報不翻，**預設**；設整數＝到了翻 unknown，選項）、`reset`（來源回合倒退：舊 basis 作廢，state unknown 直到新值）、`unknown`（round.json 讀不到）。v1 不讀 daemon status 分辨 paused／慢／死，寫進界線（v2 選項）。 |
| 門檻與誤差 | `scale` 的誤差界＝`|mul|×前一步誤差＋q`；`threshold` 若 `value ± err` 跨過門檻 → 該欄 `null`、`state: unknown`、`why: "within_error_band"`（astra 必要區分：79.96 不能硬判）。 |
| 框架 | 槽內 `state.json`（同槽換 run 接得上，核心 §5.1）：`{"since","last_ok_my_round","last_src_round","last_seq"}`。暫存器本身在 node 的 `in/`，活過 run 與槽刪。 |
| 消費端示範 | `examples/temp/fan.py`：普通 keep 任務，每 tock 讀 `in/temp.json`，`ok` 才寫 `out/fan.json`＝`{"on": hot, "basis": 抄 basis}`；unknown 保持上一動作、記 `held`（示範「沿用舊值的 node 必須看得到 unknown」）。 |
| 檢查器 | `aos7-adapt check <宣告>`：欄位型別、步種類、`need` 欄在最後一步產出裡、`max_age`／`patience`／`stall` 是非負整數或 null、不執行；有錯 rc 1。直譯器啟動也跑。 |
| 跟 step／budget 接 | **本輪不接、不需要改任何一邊就能接**：step 的 `wait` 條件 `{"num":"in/temp.json","key":"value.c","op":">=","value":80}` 與 `{"exists":…}` 已能吃暫存器（加一個探針證明即可）。budget 不接（adapt 不消耗資源）；之後可把 `aos7-budget status` 當一個 sense 轉給消費端。 |
| 程式 | `aos7_adapt.py`（讀宣告、鏈、鐘、暫存器、檢查器、人手 `status`）、`bin/aos7-adapt`；依賴工具包 `task_env`／`wait_tock`／`resolver`、核心 `aos7_fs`（`fact`、`write_json`、`read_round`）。completed_tock 判定抄 budget 那 8 行（之後兩包共用時再搬進工具包，不這輪）。 |

### 3.3 驗收探針（流速矩陣：`src`／`dst` interval 20ms／200ms、200ms／20ms、相同）

| 情境 | 期望 |
|---|---|
| 來源快（20 vs 200） | 每個 dst 回合 `src_round` 前進 >1、`skipped` 累加、`state: ok`、`age ≤ 1`；不報錯、不補。 |
| 來源慢（200 vs 20） | 連續多個 dst 回合值與 `basis.sha` 相同、`age` 仍 ≤ 1、**不翻 unknown**（慢不是壞）；`max_age` 用來源鐘所以不會因 dst 快而過期。 |
| 來源被 pause | 來源鐘凍結 → `age` 不長；`stall: null` 時 state 維持、`src_state: stalled`；`stall: 3` 時第 4 個 dst 回合翻 unknown、`last` 仍在；resume 後 ≤ 2 個 dst 回合回 `ok`、`advancing`。 |
| 來源 daemon kill -9 重開 | 回合接續（核心 §3）、最多短暫 unknown（round.json open／不知道由 patience 撐住）、無 `reset`。 |
| 來源 node 重建（round 從 1） | `src_state: reset`、state unknown、舊 basis 作廢；新值到才 ok 且 basis.src_round 是新鐘。 |
| 讀到半寫／壞檔／EIO | 來源檔 tmp 內容截斷、或注入 U：第 1～patience 回合 state 仍 ok（舊 basis）、`why` 記錄；超過翻 unknown、`last` 保留；修好後下一回合 ok。 |
| dst 被 pause | dst 沒回合 → 耐性不走、暫存器不動；resume 後照常。 |
| adapt 任務被殺（keep 重起） | 新 run 從槽內 state.json 接 `since`／`last_seq`，`skipped` 不重算、不重複寫同一版。 |
| 門檻邊界 | `t_dc=800`→`hot:true`；`799`→`hot:null`＋unknown（誤差 0.05 跨 80）；`790`→false。 |
| step 消費 | step `wait` 的 `num` 條件讀 `in/temp.json`，值到就走 `then`，unknown 時（欄位缺）不成立、耐性照步算。 |
| 長跑 | 300 個 dst 回合後 `in/`、`adapt/`、槽內檔數不變（暫存器覆寫）。 |

### 3.4 要核心動嗎

不動。三個候選都答不過三問：(1) 「來源 paused」直接讀 daemon status 是任務可做的事（掛 `.aosd`），不是核心出口；(2) 來源回合內 adapt 與消費者誰先醒沒保證（r3 F 的問題）——消費者改等 `in/<sense>.json` 的 `my_round` 而不是 tock，包內解；(3) 想要「漏了幾版」精確數要來源帶 `seq`，是發布者慣例不是核心欄位。

## 4. 本輪範圍、順序、驗收

| 線 | 目錄 | 內容 | 量 |
|---|---|---|---|
| A | `modules/subd/` | A6-01：`allowed_stop` 判定、重開補完提交、收尾改同函式；README 規則與契約卡各改一句；測試 +4（三窗口＋父 kill 反例） | 小 |
| B | `packs/budget/`（+`packs/step/` 4 行） | A6-02 共同故障邊界；缺口 2 `clock_hw`、缺口 3(a) 孤兒回條掃、缺口 5 `max_resends`；spec §9 已知界線＋保存與退役節、§2／§4 文字；README 接法句；測試 +5（EIO／EACCES、hw 推高、孤兒掃、max_resends、retired 拒收若做） | 中 |
| C | `packs/adapt/`（新） | README（契約卡）、spec、程式、檢查器、`examples/temp/`（sensor／fan／宣告）、測試 +10～12（3.3 矩陣）；core-contracts 2.7 連結表加一列、modules／packs 總覽加一列 | 大 |

三線**可完全並行**（無共用檔）；整合者最後同步：proto7-2 README 測試表、modules/README 總覽、problems.md 加 A6-01／A6-02 各一列、play README astra-5 列「後續」填 commit、code map、SESSION-LOG。順序建議 A → B → C 收，因 A 最小且是唯一會殺任務的 B；C 先做契約卡與檢查器再做鏈（原則 10）。

**驗收條件**
- 全套從 repo 根 `python3 proto7-2/tests/run_all.py` ×3 皆綠，預期 322 → 約 342。
- 核心 `tests/core/test_budget.py` 綠且總行**維持 2757／2800、2123／2200**（零新增；`git diff --stat proto7-2/lib/` 為空）。
- A6-01：三窗口 ×3 全保留、父 kill 反例照收、G3 並行 10／10；A6-02：EIO＋真 EACCES rc 3、恢復後同 K 一次效果、獨立核帳器（astra-5 `audit.py`）對新快照全過。
- budget：astra-5 50 案可重跑腳本結果不退化；`clock_hw` 在 denied 後也推高；孤兒回條被掃且重播回條一致。
- adapt：3.3 矩陣各至少一案、流速三組都跑；300 回合檔數不長；step `num` 條件吃得到暫存器。
- 文件：budget spec §9 五條一行一條；subd README 第 13～14 行與契約卡「被允許的 stop」句改成「以核心停止事實（status＋stop 回條）判定，提交中斷可補完」；adapt README 四欄契約卡＋界線（不分辨 paused／慢／死、不做事件、不接 LLM）；contracts 2.7 表加 budget、adapt 兩列（現表漏 budget）。
- 回歸（astra-6）：A6-01／A6-02 探針改跑已修版；adapt 流速矩陣外加「鏈宣告工作中被改」「來源檔換成資料夾」（預期 M／unknown 不崩）；新問題先標組件／類別，M 不進 bug 節。

**真兩難（已做成選項＋預設）**：`stall`（預設 null 只報不翻）；`max_resends`（預設 1）；缺口 3 清理（預設只掃孤兒回條，不壓縮 log）。
