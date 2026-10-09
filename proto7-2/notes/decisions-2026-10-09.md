# 2026-10-09 頂層代定清單（使用者出門時）

← [plan-2026-10-09](plan-2026-10-09.md)｜[catch-up](catch-up.md)

使用者 10-09 早上說：出門後大小決策全由頂層先做，回來問「這段時間發生了啥、你做了哪些大決定」時照本檔報告；做錯可以改回來。一行一條：級別（A＝大、B＝中、C＝小）／決定／出處或翻案位置。

## 使用者親裁（10:40）

- loop7 D1～D10 全照預設建議；D7 改「不設行數上限」（開發階段不設，整理階段再濃縮）→ [blueprint-loop7 §5](blueprint-loop7.md)
- T8 系列在家機可重試（加保護），公司 WSL 不跑。

## 頂層代定

- B｜九隊各自 worktree（`loop7/<隊>` 分支），隊長 rebase 後頂層 ff-merge＋push → plan §4
- B｜所有測試跑在 `systemd-run --user --scope -p TasksMax=800 -p RuntimeMaxSec=1200`；同時最多 3 份全套 → plan §5
- B｜`test_budget.py` 改成只印不擋（D7 的落法）→ plan §5
- C｜subd 尾項併入 M 隊、T8-02／T8-04 歸 S／B 隊收尾 → plan §3
- C｜D3 注入點歸 K4 先獨立 commit，K2／T2 等它 → plan §3
- B｜codex 新模型（gpt-6.1-sol 等）級別一律「暫定、待使用者確認」；skyrim 側 team-model 不同步 → X 隊
- C｜R 隊回歸發現只記不修（≤5 行單檔例外）→ plan §3
- B｜寫碼主力改 codex `gpt-6.1-sol`、審查 `gpt-6-astra`（取代 09-30「碰程式碼一律 Opus」）；隊長仍是 Opus 逐行審 → plan §3
- B｜隊伍遇到方向性題不停線、不記 WAIT_USER，回報頂層由頂層代定並記於本檔（照使用者 10-09 指示）

## 執行中新增
- C｜K3：R8-05 選 (b) 旗標改記待結算回合號 `owe_round`，同回合只扣一次 → `aos7_daemon_timeline.py`
- C｜K3：多個 timeline 設定同時不合法只回第一個錯；interval 上限一年（超過用預設並記錯）；錯誤訊息帶值截 60 字
- C｜K3：R8-05 用假 daemon 單元測試（真 daemon 無法穩定只讓 tock 後那次讀取失敗）
- C｜K4：worktree 改放 `../aos-wt/<隊>`；`inject("write")` 放開暫存檔前（打中不留暫存檔）
- C｜T1：行數檢查用 `ENFORCE = False` 開關關掉（不刪斷言，好改回）→ `tests/core/test_budget.py`
- C｜T1：`check_rules()` 遇 `@file` 規則在檢查時才讀檔（跟 daemon 中途換規則一致；代價：檔案中途改了可能放過漏打的規則）
- 觀察｜`test_diag.test_unsure_listed` 在多隊同時跑全套時連紅約九次、單跑全過；暫視為負載造成的時序不穩，再出現就歸 bug 線
- B｜X：新模型級別全部暫定（依據一題各跑一次）：A？gpt-6.1-sol、gpt-6-astra；B？gpt-6-sol；C？gpt-reserve、gpt-5.5；D？Haiku 5.5、gpt-6-luna → [team-model](../../wf/workflows/team-model.md)、[probe](../../wf/workflows/team-model/probe-2026-10-09.json)
- C｜X：碰程式碼仍不派 Sonnet（使用者 09-30 說過）；要兩份獨立 codex 意見時用不同 slug
- C｜T2：T8-05 用 mock `aos7_tock.fact`（藍圖選項 a），不在正式程式加注入點
- B｜K4：N-86 once 先比對「槽的 run 是否等於 launch 的 run」再看排程；改排程後不重跑，也不讓沒起成的 once 佔槽（否則同名 keep 永遠起不來）→ `aos7_tick.py`
- C｜K4：mount 讀連結出錯當「不知道」、請求留著下次再審（不刪請求）→ `aos7_mount.py`
- C｜K4：spec §5.5 C8-03 只寫原則（核心只清自己資料夾的暫存檔，槽外由寫的人跑 `sweep_tmp`），各包資料夾由各隊處理
- B｜K1：D1 落法——runner 還在起任務時 kill 回 `ok:false`／`unknown`，請求留著下次再試；若掃到對應任務已在跑則照殺，避免請求永遠卡住 → `aos7_task.py`
- B｜K1：任務環境改白名單，只給核心六個 `AOS7_*`；副作用：`AOS7_AUDIT`／`AOS7_SUBROOT` 不再傳到子 daemon 起的任務 → `aos7_task.py`
- C｜K1：R8-12 `/proc` stat 改讀原始位元組，不把怪名稱當「不知道」；K-04 清場後最多再掃 3 輪
- B｜S：R8-22 驗證成立，取縮窗——補加只准同一回合（`cur == intent_round`）；代價：存意圖後加項前被殺，重開已是下一回合就走 on_unknown（預設 stop 的步停在 unknown 等 `resume --resend`）→ `packs/step/aos7_step.py`
- C｜S：`unknown_codes` 只給 run 步（非空、不重複、1～255 整數）；重送次數記框架新欄 `resends`，`resume --resend` 歸零；直譯器只在啟動時清死暫存檔
- 觀察｜subd `test_allow_stop_writes_stopped_and_parent_does_not_restart` 全套負載下紅一次（log 空），單跑 3 次綠；同 `test_unsure_listed`，暫歸時序不穩
- C｜B：重播時入口回條拿不到一律退 3（gate 自判）；退出碼 3 文字只承諾到 `--out` 寫入失敗，不承諾 stdout → `packs/budget/`
- C｜B：不做 A8-10 (c)（fakeapi call 步保留 `fail: failed`；開了 unknown_codes 後 3 本不走 fail，改了會破三個測試）
- C｜B：帳任務只在啟動時掃一次 `gateway/` 死暫存檔（非每回合）
- B｜K2：回收意圖落在 nodes.json 頂層 `reaping` 鍵（`{id:{since,why}}`），不另開檔、不在 node 條目加 `retiring`（藍圖 c2 的變形，避免重新登記撞鍵）→ `aos7_daemon.py`
- B｜K2：磁碟上不記 pgid，重起後只靠身分掃描回收（避免殺到被重用的群組號）
- B｜K2：意圖寫檔失敗仍照殺、每圈重試寫檔（不殺不會讓當機後更好）
- C｜K2：register／unregister 寫檔失敗回 `ok:false`、不變更、可重送；paused.json 存失敗只記 log 不丟例外；讀不到的槽不算「不確定」（免得 node 永遠卡住）
- 已知限制｜K2：N-06「回合已關、steps 還沒存」之間當機，重起後多跑一回合（要動 K3 timeline 才能修）；daemon 停機時 node 被換掉偵測不到（以前就如此）
- C｜頂層：M 隊 diff 403 行超過 300 行 gate（約 330 行是測試、正式程式約 60 行），照 D7「不設上限」接受
- C｜M：history 檔名編碼 `%`→`%25`、`+`→`%2B`、`/`→`+`，`daemon-events` 改寫成 `daemon%2Devents`；舊檔名不變 → `modules/history.py`
- B｜M：D9 落法——`AOS7_AUDIT_ALLOW` 以 `:` 分隔絕對路徑，每次寫入重讀、只認 node 內的；只能豁免巢狀邊界，不能讓 node 外變合法；subd 也設在自己身上；subroot 路徑含 `:` 時不設（audit 會多報）
- C｜M：R8-25 重現後修（忙碌旗標改 per-thread）；R8-24 重現後修（兩邊都比 realpath）；once_retry birth 讀不到／非物件／沒 name 當不知道、留 pending
- 已知限制｜M：once_retry R8-26 仍有窗口（重讀 birth 到提交之間核心重用槽可能多補一次重試；契約是至少一次，寫進 README）；node id 超過約 250 bytes 時 history 檔名太長（未修、未寫文件）
- C｜I：wf code map 不另開 proto7-2 分冊，總圖加一句指向 `proto7-2/INDEX.md` 與 `tests/README.md`
- C｜I：契約卡除 2.1 外也照 spec 同步 2.2／2.3／2.5／2.6（2.5 舊句「AOS7_* 原樣傳給任務」與 K1 白名單衝突）
- 結果｜整合後全套 ×3：458 項全過，各約 230 秒；核心行數現為總行 2952、程式 2305（D7 不擋）
- C｜A：adapt `Adapter.init()` 啟動時對整個 `in/` 跑 `sweep_tmp`（只刪寫者已死的暫存檔，多任務共用安全）；範例 sensor／fan 啟動時清自己的 `out/`
