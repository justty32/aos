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

## 下午（照 [plan-2026-10-09-pm](plan-2026-10-09-pm.md) §6，Fable 代定）

- A｜下午主線：事件保存第一版落地（新模組 `modules/events/`，核心零改動）；LLM 作者今天只出藍圖、不接真模型；kernel 任務包與測試加速今天不排
- A｜事件保存 5 題全照 event-store 報告 §11 預設：逐件業務事件＋明示取樣的核心觀測；回看／必讀兩用途分開；先單 node 不集中；滿了必讀停收、觀測續但報缺口；第一版只承諾程序 SIGKILL 可接續（不 fsync）
- A｜依你 user-advice 的意見定硬約束：每 node 一個 `events/` 夾、活躍段 1 檔＋封存段最多 4、不每回合新檔／新夾、超過就刪最舊（必讀只停收不刪）
- B｜history.py 不動、`.aosd/log.jsonl` 只續讀不裁；step／budget／adapt 今天不接事件
- C｜once_retry R8-26 維持「至少一次」不修；astra-7 五條今天修（A9-05 只寫文件）
- B｜E0／頂層核可：事件夾分「觀測」「必讀」兩條通道，各自 1 個在寫的檔＋最多 4 個舊檔，加 state.json 與鎖，**總上限 12 檔**（不是字面的 7 檔；兩通道清理規則不同，混在一起會誤刪必讀）→ [blueprint-ev1](blueprint-ev1.md)
- C｜E0：預設每檔 1 MiB、單筆 64 KiB、等鎖 5 秒；寫一半的行直接截掉；去重只在還留著的紀錄內有效（超出即至少一次）
- 結案｜L3：上午 `test_unsure_listed` 連紅是驗證時「改壞再還原」同秒同大小，Python 沿用舊快取（非負載）；subd `allow_stop` 測試是讀 log 的時機假設錯，已改成等檔案出現。教訓記 dispatch lessons
- C｜L4：A9-02 history 升級時把含 `+`／`%` 的舊檔與 `daemon-events.jsonl` 一次改名成 `.v1` 封存、不再續寫（不丟資料、只斷連續性），夾內放 `.names-v2` 記號 → `modules/history.py`
- C｜L4：A9-03 陣列索引先去前導零再檢長度，超長回 125；前導零索引維持舊行為（照收，雖然 RFC 6901 說無效）
- B｜L1：N-06 修法——paused.json 加 `owe: {node: 開回合前的回合號}`，關回合時扣倒數與清 owe 同一次寫入；重起時回合號前進才補扣。不確定時寧可少跑不多跑 → `aos7_daemon.py`、spec §2.4
- C｜L1：A9-01 reaping 還在且沒時間線時 status 顯示 missing（含 `stop-kill` 留下的）→ spec §2.6；diff 239 行超 200 gate（多為測試），照 D7 接受
- 已知限制｜L1：回合中途才下 `resume --rounds` 時正好當機、或 daemon 被殺時舊 tick 已拿鎖還沒寫 round.json，仍可能多跑一回合（要給每回合落身分標記才能修）
- A｜A0：LLM 作者藍圖 [blueprint-llm1](blueprint-llm1.md)——第一刀是 CSV 固定工具作者（新包 `packs/author/`），只准組合可信工具、預設產出候選要人跑 `publish` 才上線；12 題照 llm-author 報告 §十預設，前 4 題第一刀照做、後 8 題等第二／三刀再核
- C｜A0：job 名改 `<rid>_<sha8>`（符合 step 命名規則）；砍在「已記意圖、還沒合併」一律回 unknown 要人手 `publish --resend`；同需求已發布版本最多 2 個
- C｜E1：保存端加公開 `store.recover()`（三個定死介面不變）；`keep_segments` 上限 4 守住 12 檔；必讀通道加 `dropped_upto`，刪段時推進；壞輸入丟 ValueError；diff 1045 行超 500 gate，照 D7 接受
- 已知限制｜E1：每個 events/ 只能有一個取樣者；剛修掉半行就被殺時壞行計數可能少 1（紀錄不受影響）；`--status` 去重只在記憶體，重起可能記兩次同一事件
- C｜E2：`publish` 多 `node=`／`config=` 關鍵字；讀者遇壞行可抵一個缺號（store 在鎖內依序寫）；讀者 CLI 先是獨立腳本 `aos7_events_read.py`；demo 的 event_id 不含 run 號（重跑可去重）；diff 603 行超 400 gate，照 D7 接受
- C｜E3：`aos7-events` 加 `read`／`pub` 子命令；長跑是範例腳本不進測試套（需真 daemon、約 40 秒）；長跑用 8 KiB 小段讓 300 回合內真的會輪替與刪段
- 結果｜E3 真 daemon 300 回合：有讀者時 events/ 最多 9 檔、無讀者時 12 檔（存 state.json 時有 1 個暫存檔瞬間到 13，spec 已寫）；舊段有刪；記憶體與開檔數不長

## 下午後段（13:00 起，頂層代定）

- A｜下午計畫 13:00 就做完，剩餘時間開 A1 隊照 [blueprint-llm1](blueprint-llm1.md) §9 實作 LLM 作者第一刀（`packs/author/`，用假候選、不接真模型）；另開小隊把 events spec 壓回 8 KiB 並補子命令；I2 收尾整合延到 A1 交件後
- C｜A1：需求 `inputs` 路徑相對 node；新增子命令 `aos7-author answer <rid>`（step close 前跑檢查器、結果記 verdict，author close 要求答案已驗）；退出碼多 `5`＝已發布滿 2 版
- C｜A1：新候選直接取代沒登記的舊待審候選；還有待審候選時 close 回 conflict；close 不移除表項（由人收）；表項「整項完全相等」才算相符
- 結果｜A1 第一刀 §4 六條驗收全過；100 份需求結案後 `author/` 恰 201 檔（每需求 2 檔＋1 把鎖），不隨回合增加；全套 556 項全綠

## 第三段（14:00 起，照 [plan-2026-10-09-late](plan-2026-10-09-late.md) §6，Fable 代定）

- A｜主線：LLM 作者第二刀藍圖＋**假傳輸**實作（新包 `packs/llmcall/`）、作者需求改走事件「必讀」通道；**真模型等你看過藍圖才接**
- A｜llm-author 第 7／8／9／11 題照預設在第二刀生效：沒證明上界就算軟預算；遠端結果不明不重送、保留預留額；usage 缺時照樣交候選、帳務標待結；只承諾程序中斷可接續
- B｜budget 部分結算：settle 放寬為 0≤用量≤預留；用量超過預留時結算預留額並記 overrun，不偽裝成功
- B｜wf-lint 超標的 31 份思想文件（ideas、spec 系列）不動，留你在場時整理；只清 86 條壞連結
- C｜「多跑一回合」類已知限制今天不排；adapt-llm 第三刀明天先藍圖
- C｜W1：86 條壞連結清零（約 70 條是寫成絕對路徑，改相對路徑）；目標已刪的改成純文字＋註明去向（例如 `packs/account` 已改名 budget，不改指以免變原句意思）
- 待你決定｜`proto7/user-advice.md` 還沒 commit，有 3 份文件連到它，所以在別的 clone 或 worktree 裡是壞連結。等你寫完再 commit 就好
- B｜G0／頂層核可：第二刀藍圖 [blueprint-llm2](blueprint-llm2.md)——新包 `packs/llmcall/` 當 budget 第二種入口（假傳輸 `llm.fake`），介面凍結；遲到回覆只能人手 `adopt`；llmcall 多一個退出碼 4＝內容已交付但帳未清
- B｜頂層：用量超過預留（U>R）時只記 overrun、退出 4，**不自動停新預留**（llm-author §6.5 建議停准入對帳，這條要翻就改 budget gate）
- C｜V2：事件保存兩個限制都修掉（不只寫文件）：status 去重改落 state.json 的 `status_last`（存雜湊），重起不重記；半行截掉前先存 `torn`＋`torn_cut` 記號，計數不再少 1。恢復時會自己寫一次 state.json（spec 已註明例外）
- 結果｜I2：全套 ×3 在 a1be11b4 上各 556 項全過（約 300 秒）；核心行數總行 3004、程式 2353（D7 不擋）；白話報告草稿 [report-2026-10-09](report-2026-10-09.md)，最終版由 I3 補第三段後定稿
