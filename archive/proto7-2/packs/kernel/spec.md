# kernel 任務包 spec（kernel1 骨架）

← [藍圖 kernel1](../../notes/blueprint-kernel1.md)｜[意圖卡](../../notes/intents/kernel.md)｜依據 [kernel-pack](../../notes/reviews/2026-10-05/kernel-pack.md) §3～§6｜核心 [spec §5、§6、§7](../../spec.md)｜錯誤 [blueprint-errors](../../notes/blueprint-errors.md)

kernel＝替任務做決策的**普通 keep 任務**（`max_live: 1`）：每個自己的 tock 讀來源的公開事實 → 純函式規則 → 驗證 → **先存意圖再送控制** → 核對回條；被殺接續。第一版只做觀測、綁 run 的 kill 與通知。核心零改動，用既有 `ctl.json` kill 協定（核心 spec §6）。程式：`aos7_kernel_state.py`（設定、state、快照）、`aos7_kernel.py`（規則註冊、驗證、送出與核對、主迴圈、status）；規則本體在 `aos7_kernel_rules.py`。

## 1. 指令

- `aos7-kernel run [--dry-run] [--rounds N]`：keep 任務用（`$AOS7_*` 由核心給）。`--dry-run` 照當下做一次快照與規則、把會做的決定印在 stdout，**什麼檔都不寫**、不送控制，模擬的決定不進 pending；規則輸出被拒絕退 1。`--rounds N` 收到 N 個 tock 後結束（測試用）。
- `aos7-kernel status <node>`：一行白話（「監督 1 件：都在動」「監督 1 件：已寄信：…」「監督 1 件：kill bob#3 等回條」）。找 kernel 槽：tasks.json 裡 argv 含 `aos7-kernel` 的項目名（沒有就看 `kernel` 槽；tasks.json 讀不到退 3）。

退出碼照 [blueprint-errors](../../notes/blueprint-errors.md)：0 做到／1 做不到（設定雜湊不合、state 不見了）／2 你給的不對（kernel.json 不合）／3 不知道（state 讀寫故障）。stderr 一行 `aos7-kernel: 發生什麼。怎麼辦`；3 以「不確定：」開頭。`run` 收到 SIGTERM 退 0。

## 2. 設定 `<node>/kernel/kernel.json`（`<node>`＝kernel 所在 node）

```json
{"v": 1,
 "sources": [{"node": "team/bob", "slot": "brain", "kind": "brain"}],
 "targets": [{"node": "team/bob", "slot": "brain"}],
 "rules": [{"name": "supervise-brain", "no_progress_rounds": 6, "kill_after_rounds": 12, "max_kills": 3, "notify": "you"}],
 "events": false,
 "mail": {"root": "..", "from": "kernel"}}
```

- `node`＝相對空間根的 node id（同 daemon 的 node id；kernel 自己的 node 也可寫 `.`）。別的 node 要在 kernel 的 tasks 項目 `mounts` 掛上（核心 spec §4.5），沒掛＝那個來源讀成 `unknown`、那個目標送不出（pending 留著）。
- `targets` 每個都要在 `sources` 裡（同 node＋slot），否則退 2。`kind` 第一版只有 `brain`。`rules[].name` 要是已註冊的規則（`supervise-brain`、`noop`），sources 最多 10 個；node 先正規化，雜湊仍取原始內容。supervise-brain 的 no_progress_rounds、kill_after_rounds、max_kills 有寫就要是正整數（bool 不算）；補齊預設 6／12／3 後，kill_after_rounds 必須大於 no_progress_rounds，否則初始化前退 2。
- `events` 第一版只收 `false`（或不寫）。`mail` 可選：`root` 相對 kernel 的 node（aos7-up 的 house 是 `..`），`from` 是寄件名（預設 `kernel`）；不寫＝通知文字與正文留在 state 的 done。from 必須是合法名字字串。
- **設定雜湊** `config_sha`＝kernel.json 的 JSON 內容（鍵排序、緊湊）sha256 前 16 碼。啟動與每個 tock 都重讀比對；不合＝不再提交、不再送、pending 留著、退 1（改回原樣即接續；要換設定先等 pending 清空，再刪 state.json 與 decisions.json）。

## 3. state `$AOS7_TASK/state.json`（唯一恢復真相，每次整份 rename）

```json
{"v": 1, "config_sha": "…", "instance": "…", "rev": 7, "last_tock": 42,
 "rules": {"supervise-brain": {…規則自己的狀態…}},
 "pending": [{"id": "k-1a2b3c4d-7-0", "op": "kill", "target": {"node", "slot"}, "run": 3, "why", "basis", "sent": false, "tock": 42},
             {"id": "…", "op": "notify", "target": "you", "text": "…", "body"?, "basis", "sent": false, "tock": 42}],
 "done": [{"id", "op", "target", "run"?, "text"?, "body"?, "basis", "result", "msg", "tock", "at"}],
 "last_error": null}
```

- 初始化：`state.json` **確定不存在**、槽裡也沒有 `decisions.json`（從沒跑過）才建；`state.json` 不見而 `decisions.json` 在＝state 弄丟了，不自動初始化，退 1。`state.json` 讀不到、壞掉、`v` 不是 1 或欄位不合＝退 3，什麼都不動，不拿空 state 蓋掉。
- 決定 id＝`k-<instance 前 8 碼>-<rev>-<序號>`，提交時給定、之後不變（重送、重起都用同一個）。
- pending 在等的原因（控制衝突、讀不到、寄信失敗、沒掛載）記在那筆的 `wait`，給 status 看；`last_error` 只記規則與提交的錯（下一次提交成功就清掉）。
- pending／done 的必要欄位與 supervise-brain 的 brains／killed／notified／retries／gaps 深層型別都要合法，否則退 3、不動檔；舊規則狀態可省略新增欄位。
- `done` 保留提交時的精簡 `basis`（來源、run、信 id／title、step、since、age、completed_tock），不存整份 task.json；只留最近 20 筆；`pending` 每個目標槽最多一份 kill。state 大小只隨目標數、規則狀態、在途數長，不隨回合數或 run 數長。
- `decisions.json`（同槽）只留上一次、只給人看，**不拿來恢復**：`{"tock", "at", "decided": [...], "rejected": 原因或 null, "note"}`。

## 4. 快照（交給規則的 `snap`，一個 list）

每個來源兩項：`{"src": {"node","slot","kind"}, "file", "run", "seq", "completed_tock", "read", "value"}`。

| file | value | seq |
|---|---|---|
| `.aos/tasks/<slot>/birth.json` | birth.json 內容 | null |
| `brain/task.json` | brain 的 task.json（`{"id","step","line","stall","trail",…}`） | `step`（整數才給） |

- task.json 那項另帶 `title`：只讀來源 inbox/*.md 與 inbox/done/*.md，依 frontmatter id 找信、取 `# ` 標題；找不到或讀不到為 null，絕不讓快照失敗或變 unknown。`node_path` 帶實際來源路徑，供規則產生可執行的查看指令。
- `read` 四態：`ok`／`absent`（確定不存在）／`bad`（不是 JSON 或不是物件）／`unknown`（讀不到、不是一般檔、run 對不上）。**絕不折成空物件**；不是 `ok` 的 `value` 是 null。
- `run`＝來源槽 birth.json 的 `run`。讀 task.json 前後各讀一次 birth：兩次不同、讀不到或 birth 不在＝task.json 那項 `read: "unknown"`（存在但不能綁到某個 run）；task.json 確定不存在仍是 `absent`。
- `completed_tock`＝來源 node 的 round.json：關著取 `round`、開著取 `round − 1`、新空間 0、不知道 null。來源鐘停＝這個數不動。
- 只讀公開檔（birth、task.json、round.json），不呼叫 `judge_resolved` 等會收程序的判定。

## 5. 規則介面（純函式）

`rule(ctx, snap, rstate) -> (rstate2, candidates)`；`ctx = {"v": 1, "tock": 本次 tock, "config": 整份 kernel.json 再蓋上這條規則自己的欄位, "rule": 這條規則在 rules 裡的那一項}`；`rstate` 第一次是 `{}`。

candidates：`{"op": "kill", "target": {"node","slot"}, "run": 整數, "why": 字串, "basis": JSON}` 或 `{"op": "notify", "target": 收件名, "text": 一行字串, "body"?: 多行字串, "basis": JSON}`。

骨架**整份**驗證（所有規則的輸出一起）：回傳不是兩項、rstate2 不是物件或不能存成 JSON、未知 op、型別錯、kill 的 target 不在 targets、run 不是整數（bool 不算）→ 這個 tock 一件都不提交，規則狀態不變，記 `last_error` 與 decisions.json 的 `rejected`。規則丟例外同樣處理。同目標同 run 的 kill、同收件人同字的 notify 重複＝合併；同目標不同 run 的 kill＝矛盾，整份拒絕。候選的目標已有 pending 的 kill（同槽一份），或已在 pending 的通知 ≥ 10 封（新候選不計入）＝**整輪延後**：這個 tock 一件都不提交、規則狀態不存（不然規則會以為已經出過），decisions.json 的 `note` 註明，下一個 tock 重判。

supervise-brain 用來源 completed_tock 計老化（task.step 稱「步」，心跳稱「回合」）；缺檔視為閒置，未知區間不老化，恢復後重建基準。新 run 只重建計時，不清除已通知信 id 或重試次數。同一信 id 每來源只通知一次，換信才替換；標題與 line 壓平換行、最多 60 字，缺標題以 id 前 12 碼短稱呼。kill 每 run 最多一次；同一 `(id, step)` 第 n 次須停滿 `kill_after_rounds × 2^(n−1)` 回合，最多 max_kills 次（預設 3），到上限不再通知或 kill；換信或 step 改變就重置次數。每來源僅保存當前 brains、killed run、notified 信 id、retries `(id, step, count)`、gaps 讀不到旗標，不累積歷史；舊狀態從 notified 旗標與 killed 保守接續。

## 6. 執行順序與崩潰點

① 讀設定＋state ② **先核既有 pending**（不等 tock）③ 等自己的 tock（`tock.json` 的 `run` 是自己、`round` > `last_tock`；跳號只處理最新、不補；同 tock 不再提交）→ 快照 → 規則 ④ 驗證 ⑤ **一次 rename** 存規則狀態＋`last_tock`＋新 pending（寫失敗＝記憶體裡也不前進，0.2 秒後重做同一個 tock）⑥ 送 ⑦ 依回條更新（再存 state）。之後每個 tock 都先做 ②。

| 被殺在 | 重起後 |
|---|---|
| ⑤前 | 沒有新 ctl；`last_tock` 沒前進，下一個 tock 照常判。 |
| ⑤後⑥前 | ② 直接用同一 id、同一 run 補送。 |
| ⑥後⑦前（`sent` 還是 false） | ② 先找相符回條、再看 ctl.json 是不是同 id，才決定補送；不造新 id；補送也綁原 run，核心不會殺到新 run。 |
| 回條後、存 state 前 | ② 從回條恢復結果，不建新決定。 |

## 7. 送出與核對

**kill**（目標槽 `<node>/.aos/tasks/<slot>/`）依序判（先讀 ctl.json 再讀回條：核心是先寫回條再刪請求，這個順序不會把「剛處理完」看成「沒送過」）：

1. `ctl.json` 是同 id＝已送（補記 `sent`）；回條也相符且 `ok: true`＝done `ok`，否則等下回合。是別的 id（或壞檔）＝控制衝突，不覆蓋，pending 留著。讀不到＝留著。
2. `ctl.json` 不在：回條讀不到或壞掉＝留著、**不補送**（可能就是我們的回條）。`ctl-done.json` 的 `id`＋`op`＋原請求 `run` 都相符才算我們的（關聯不看 `result.run`：拒絕回條的 `result.run` 可能是新 run）；`result` 要有布林 `ok` 與字串 `msg`，不合＝留著。`ok: true` 且 `result.run`＝`<slot>#<原 run>`＝done `ok`；`ok: false` 而 msg 以 `unknown` 開頭＝done `unknown`（請求已被核心消耗、結果不確定，不重送）；其他 `ok: false`＝done `rejected`（帶 msg）。回條讀不到＝留著。
3. 目標 birth.json 的 run 確定已換（≠ 意圖的 run）或 birth 確定不存在＝done `superseded`，**不轉向新 run**。讀不到＝留著。
4. 以上都不是：寫 `ctl.json`＝`{"op": "kill", "run", "id", "by": "kernel/<自己的槽>", "why"}`，記 `sent: true`。寫失敗＝留著、不算送出。回條被別人的請求蓋掉而 run 還在＝走到這步再送同一 id，核心只會對原 run 動手。

**notify**：body 可省略，有就必須是字串；寄信正文用 body，補維護者的 state 路徑；省略時用四段白話提醒。沒設 `mail`＝done `logged`（通知文字與 body 留在 state 的 `done`，status 看得到）。有設＝用 mail 包寄 `NEEDS-USER` 給收件人，信 id＝決定 id（mail 對同 id 去重，重送不會多一封）；寄失敗＝留著下回合再寄。

kill 回 `ok` 只代表核心收掉了那個 run；keep 會不會重起、重起後好不好，kernel 不宣稱。

## 8. 不做

restart／reload、改 tasks.json、daemon 控制、動態掛載、多控制者、外部或 LLM 規則、撤回已送的 kill（同 run 恢復進度後，已提交的 kill 仍可能晚到生效，status 標「等回條」）、跨刪槽或換 node 的接續、累積歷史、events 發布。
