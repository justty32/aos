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
- B｜V1：學徒改從事件必讀通道收單（`aos7-author send`／`intake`）。藍圖說的「回條」解讀為**收單回條**（不是發布回條）——等發布回條要等人按發布，會把單一消費者的必讀通道堵到滿
- C｜V1：收單只登記、不自動提案或發布；壞單（`invalid`／`conflict`／`ignored`）照樣 ack 免得堵住後面；輸入檔還沒放到 node 上的單算 invalid
- C｜B2：budget 部分結算（0≤用量≤預留）；cancel 遇到別的入口留下的任何非終局紀錄都回 unknown（比凍結介面的「intent」更嚴）；overrun 欄存在但 null 判 unknown；billing final 帶 overrun>0 照收
- C｜G1：假傳輸閘道 `packs/llmcall/` 完成；遠端次數只按 call ID 算；adopt 被拒印 `refused` 退出 1；billing pending 不寫 receipt.json（每次重跑重算、退出 4）；deadline 限 0～86400 秒；diff 1152 行（全新檔）照 D7 接受
- 已知限制｜G1：budget `cancel` 在 intent 寫入前取消時，寫出的取消紀錄缺 gateway／call_id 等欄（llmcall 會補預設值仍可用），要改 budget，留下一輪

## 使用者 14:20 回覆

- 使用者：**大決定都 OK**；**准許接真 AI**（本地 LiteLLM，不用 `lm-*`，盡量 gpt 系），token／輸出長度／context 全部拉到極限，跑完大段落再依消耗定限制；要持續往前推進
- B｜頂層：真 AI 先接在 llmcall 當第二種傳輸（`llm.litellm`），再讓學徒（author）用真 AI 產候選，走完一整圈：真 AI 寫草稿 → 三關檢查 → 發布 → step 跑 → 答案檢查；每次呼叫的 token 用量都記帳，跑完出一份消耗報告
- 使用者 14:30：持續推進＝定目標→依需求調整 kernel／agent 架構（擴充模組包／工具包／程式包）→持續改進；Claude 與 GPT 週額度明天下午重置，**全力衝刺、盡量多開**

## 使用者 14:40 給的目標（下一輪主線）

1. 以 `~/repo/workflows` 的架構（分層工作流：AGENTS.md 路由→WORKFLOWS／INDEX→各工作流；活狀態只列 open；膨脹即拆；kernel＋flavor 包）在 aos 上實現
2. 做出現有 coding agent 常見的東西——compact、memory、skill 等——善用既有的 aos-directives 與先前各 proto 的想法
3. 讓 AI 熟悉 aos 框架、能自我改進：自己做模組／工具／程式
- 使用者另說：「持續推進／全力衝刺」看狀況決定，**不寫進偏好檔**（已撤回 user.md 那段）
- 使用者 14:50：`~/repo/workflows` 就是我們的 `wf/`（wf/ 是它的實例）；另一套成熟的 workflows 體系在 `~/repo/moddings/skyrim`（含 agentctl）可參考；計畫回來後頂層直接開隊、不用等他
- 使用者 14:55：整體架構與給人用的接口／工具，必須考慮**人類易用性、上手速度、理解難易度**（ELI5 之後是不是仍複雜）；內部細節不要求
- 使用者 14:57：token 消耗量、並行呼叫數量、任務完成時間等也是可以優化的目標

## 續推：使用者三目標（照 [plan-2026-10-09-next](plan-2026-10-09-next.md) §4，Fable 代定）

- A｜目標 1 落法：每個 aos 上的 agent node 有自己的 `wf/`（照 workflows 模板原樣），prompt 每回合從這棵樹組、只讀要的那層；aos 補上 workflows 沒有的引擎（tick＝heartbeat、events 必讀＝必達信、學徒 job＝交接書）；向 skyrim/agentctl 借 ROSTER、BRIEF、handoffs 等
- A｜目標 2：記憶＝node 上的檔不是模型視窗；prompt 用 aos_directives 組裝；compact＝摘要替換舊段、open 項永不摘；skill＝SKILL.md 資料夾＋一行索引給模型挑
- A｜目標 3：學徒擴到寫 aos 工具包／模組包，三關改為 lint＋大小＋領地、跑測試、astra 審；只發布到 `apprentice/` 分支，merge 永遠是人／頂層；學徒不准寫 lib/ 與別的包
- B｜人類面門檻：第一次跑 ≤10 分鐘、對外指令 ≤3、新概念 ≤5；新手試用者打分 <7 要回改
- B｜真 AI 只用 LiteLLM 的 `chatgpt-gpt-6-sol/-astra/-luna/gpt-reserve`（沒有 6.1-sol），預設 `chatgpt-gpt-6-sol-high`，一律走 llmcall；效率四指標由 `aos7-metrics` 量，本輪只排優化項
- C｜移到之後候選：adapt-llm 第三刀、消耗事件、回合身分、budget hold、kernel 任務包
- 使用者 15:10：「持續改進」＝做一做 → 回頭看做好的東西 OK 不 OK → 回頭修改，或乾脆重造
- B｜頂層落法：每一波進 main 後排一輪「回頭審」（astra 審設計＋新手試用者實際上手），結論分三種：OK／修改／重造；重造不算浪費，照常開隊
- C｜B3：budget cancel 寫的取消紀錄補齊凍結欄位；看不出是哪個入口時記 `fakeapi`（保持 cancel 原退出碼）；cancel 遇到既有結果寫的 accepted／failed 紀錄仍是舊形狀（不在這次範圍）
- B｜W0／頂層核可：[blueprint-wfnode](blueprint-wfnode.md) 凍結 F1～F10（node 骨架用 wf-init 照模板原樣產、根只留 AGENTS.md／CLAUDE.md／.claude/、信名與終局照 PROTOCOL、routines 機器表走 wf-table json、大輸出 ref:// 可逆折疊、學徒只發布 apprentice/）
- C｜W0：信件狀態照模板 PROTOCOL 的六種（計畫寫「五狀態」是誤記）；mail 與學徒先分 node 各自獨佔必讀通道；prompt token「曲線平」＝頭尾 30 回合平均差 ≤5%
- B｜R1：真 AI 接上（llmcall 第二種傳輸 `llm.litellm`，依請求內容挑傳輸）；預設上限拉滿（不設 max_tokens、逾時 24 小時、學徒每次預留 100 萬 token）；模型輸出原樣使用不修 JSON
- 結果｜R1：學徒用真 AI 跑 12 圈（sol／astra／luna 各型）全過三關、答案全對；每次約 2.5～2.7k token（其中 proxy 自帶約 1.6k）、2.4～10.9 秒；12 圈共 30,739 token → [real-ai 報告](play/2026-10-09-real-ai/README.md)。CSV 題太簡單比不出模型差異
- 建議限制（**未生效**，等跑完大段落再定）：每次預留約 8000 token、逾時 120 秒、每單 5 萬 token、仍不設 max_tokens
- C｜H1：定時例行 `modules/routines/`——最多一次（被殺那期不重跑）；錯過很久只跑 1 次不補跑；`add` 會自動在 node 裝一個 `routines` keep 任務；對外指令 3 個（add／ls／rm）
- C｜頂層：routines 在 wf/ 留兩個固定 `.lock` 檔可接受（數量固定、不隨回合增加，不違反「垃圾要能清」）
- C｜P1：組提示包 `packs/prompt/`——對外 2 指令（render／expand）；讀檔用 `$opt` 的 file／tail／latest（latest 依檔名排序、結果固定）；大段折成 `ref://` 可逆；渲染不出整份就退出 3、不輸出半份；diff 777 行（程式 239）照收
- C｜S1：技能包 `modules/skills/`——對外 3 指令（index／pick／mount）；pick 一律走 llmcall（所以第一次跑要先開帳）；外部 skill 只能讀、不掛進任務（不複製外部 skill 進 repo）；llmcall 退出 4 時仍採用答案
- 結果｜S1：真 AI（chatgpt-gpt-6-sol-high）題庫 10 題選對 10；每題約 2576 token、3.2 秒；同 node 重跑 0 次新呼叫。Sonnet 新手試用約 3 分鐘上手，打分 7～9
- 使用者 15:00：**Sonnet 不夠笨**，當新手試用者不準 → 頂層改派最笨的：Claude 端用 Haiku、codex 端用 `gpt-6-luna`（推理 low）；S1 的 Sonnet 新手打分不算數，U 隊重試
- C｜W1：`modules/wfnode/`（init／state／check）；預設 flavor dev,heartbeat,multi-agent；模板 multi-agent 把 inbox/、tools/ 放 node 根，照模板不搬（頂層核可，F2 以模板為準）；模板中沒有已知事實的佔位寫成「（未定：原文）」不亂猜；init 自動處理 5 段已知的導入決策（只在首次導入且原文完全相同時）
- C｜T9：真傳輸 7 種故障（逾時／5xx／壞 JSON／usage 缺／截斷／斷線／遲到）各 ≥3 個變形全過，llmcall 程式沒找到 bug；假 LiteLLM 伺服器放在 `packs/llmcall/tests/`；「回覆比期限晚幾毫秒仍被收下」視為排程誤差，不改
- C｜頂層：llmcall 連 `localhost` 時應繞過系統 proxy 設定（T9 發現：設了 http_proxy 的機器可能把本機呼叫送進 proxy）→ 排進下一波小修
- 結果｜E1：`aos7-metrics job <資料夾>` 一個指令量四指標；R1 基線每單平均 2562 token（proxy 自帶 1644＝64%、我們的提示 721、模型回答 197）、收單到完成平均 9.5 秒（模型 5.3 秒、之後等下一回合 4.1 秒）、重試 0 → [metrics-baseline](play/2026-10-09-real-ai/metrics-baseline.md)
- 待你決定｜優化第 1 名是砍掉或快取 litellm proxy 每次自帶的 1644 token（省最多 64%），要改你的 LiteLLM 設定，我沒動
- C｜C2：壓縮包 `modules/compact/`（now／forget／watch）——open 項逐字保留、檔長降 ≥60%；段落切換用字元相似度 <0.2 判斷（不另花 AI 呼叫，門檻暫定）；SESSION-LOG 的現役段不摘，實際主要整理 `notes/journal.jsonl`；diff 超 gate 照收
- 結果｜C2 真 AI 一次：65 則→6 則、8968→2149 bytes（降 76%）、open 5 條全留、5429 token、約 12 秒
- B｜A4：學徒寫 aos 工具／模組的三關檢查器 `packs/author/checkers/`（brief／check／publish）——第 1 關：領地、有測試、每檔 ≤8 KiB、連結不壞；第 2 關：在 bwrap 沙盒（無網路、無 /home、只有暫存樹可寫）跑學徒自己的測試；第 3 關：astra 審。publish 只建 `apprentice/<rid>_<sha8>` 分支，不碰 HEAD 與工作樹
- C｜A4：題 1 做成新包 `packs/usage/`、題 2 做成新模組 `modules/llmdiag/`（學徒不准改別的包）；答案檢查用固定答案（隱藏或隨機題目留下一輪）
- B｜X1：信箱 `modules/mail/`——日常 3 指令（send／read／done），另 3 個進階（audit／roster／team）暫不算入「≤3」，交新手試用判斷是否仍複雜；同分鐘同名信不拒收、改加序號（拒收會掉信）；發給團隊信箱的 REQUEST 暫不收（沒人負責確認）
- 結果｜U 隊：10 個模組新手試用**全部沒過**（Haiku／luna 只看 README，取較差分數 5.2～6.8，門檻 7）；兩位都判「ELI5 後仍複雜」→ [newbie 總表](play/2026-10-09-newbie/README.md)
- B｜頂層：照「做完回頭審→修或重造」開回改隊：README 改就能過的（compact、prompt、wfnode、metrics、mail）與要改第一次跑流程的（skills、routines、events；llmcall 等小修隊、author 等 A5 交件後再改）；每隊改完用同兩位新手重試到 ≥7 才算完成
- B｜頂層：另開一隊「整體第一次體驗」設計：新手第一次跑就要碰 daemon、帳（budget）、回合等底層概念是共同病根，研究能否給一個共用的「一鍵起 node」入口把這些藏起來
- C｜NP：llmcall 打 localhost／127.0.0.1／::1 時一律直連、不走環境 proxy（其他主機照舊）
- A｜第一次體驗設計 [blueprint-firstrun](blueprint-firstrun.md)：加共用入口 `aos7-up`（新模組 `modules/up/`，核心不動），一行起 node 並自動裝好工作簿、帳、技能、例行與 daemon；前景跑、每秒印一行、Ctrl-C 收乾淨。新人只學 5 個詞（node、心跳、工作簿、信、技能）與 3 個指令（`aos7-up <node>`、`ask`、`status`）
- B｜firstrun：預設假 AI，真 AI 只靠 `--model`（不自動花錢）；帳、回合、預留、ack、退出碼在 QUICKSTART 與各包開頭三行一律不出現；brain 一回合最多處理一封信、AI 回不來回 BLOCKED 不重試；人的信箱名固定 `you`
- C｜routines 回改：第一次跑改用 `ls --run`（不用開 daemon）；新手重試第 1 輪過關 7.4 分（Haiku 7.4／luna 8.8）、約 6 分鐘、3 指令、4 概念
- C｜prompt 回改：新範例讓第一次跑就看得到「收起來」（省九成 token）；README 概念 11→3，其餘收進進階；新手第 2 輪過關（Haiku 7.8／luna 8.4）
- C｜mail 回改：README 縮成一頁（3 指令、4 概念），其餘移到 ADVANCED.md；send 預設 REQUEST、done 預設 DONE；audit 移出日常。新手三輪最後 7.6 分、3 指令；概念數 Haiku 數 6（把請求／完成拆開又算了信箱）、luna 數 4。**頂層判過**：照 README 實際列的 4 個算，Haiku 前後兩輪自己也數過 4；剩下「已辦結／已歸檔／完成」三種字眼不一致，留給套三行頭時統一
- C｜metrics 回改：預設輸出改成一行白話（每格有標籤和單位），細節移到 `--detail`；`--overhead` 預設 0。新手三輪分數都 ≥7（最後 7.6），1 指令、約 6 分鐘
- B｜頂層定「概念數」怎麼算（通則）：**只算第一次跑需要懂的**（README 分隔線「第一次用到這裡就夠了」以上）。新手讀進進階段或把每個輸出欄位各算一個，不計入。據此 metrics、mail 判過。要讓新手不讀到分隔線以下，交給 F3 的三行頭模板處理
- 使用者 16:10 建議：**架構保持簡潔；錯誤路徑要統合；副作用與外部影響盡量少、只留必要的**；新模組或功能先讓 Fable 擬定「意圖」再開始
- B｜頂層落法：①之後每個新模組／功能先由 Fable 寫一張意圖卡（要解決什麼、必要的副作用、明確不做什麼）再開隊；②開一隊 Fable 回頭審今天所有新模組：逐個補意圖卡、列出多餘的副作用（例如 routines `add` 會自動改 tasks.json、skills pick 要先開帳）、提出統一的錯誤路徑（各包退出碼與錯誤訊息格式目前各說各話），再依結果開修改隊
- C｜wfnode 回改：init 只印「裝好了／有幾處空格／下一步」；check 成功說「資料夾沒壞」並寫明不管空格；state 不給句子就印最新續行點。新手第 1 輪過關 7.4（Haiku 7.4／luna 8.8）、3 指令、4 概念
- C｜compact 回改：第一次跑不用 `--force`（示範檔本來就超過門檻）；預覽與實跑印同一句原因；README 概念 5→4，其餘移到進階。新手第 1 輪過關 7.6（Haiku 7.6／luna 8.4）
- C｜events 回改：第一次跑不用 daemon、路徑自動帶；`pub` 可省 `--event-id`（自動產生）與 `--node`（取上一層資料夾名）；公開介面語意不變。新手三輪最後 Haiku 6.7／luna 8.6，**未過**
- B｜頂層定（改慣例）：**README 只留「這是什麼＋第一次跑＋一行連結」，進階段與契約卡一律搬到同資料夾的 ADVANCED.md**（mail 已這樣做）。包格式規定「契約卡在 README」改為「契約卡在 ADVANCED.md，README 連過去」。events 先照這條再改一輪
- C｜F3：QUICKSTART（2.7 KB，5 詞 3 指令，帳／回合／ack／退出碼零出現）與三行頭模板進 main；實跑等 aos7-up 進 main。前景每秒改印「心跳 N」（不印回合）。頂層把 modules/README「包的格式」改成新慣例
- C｜skills 回改：沒開帳時 pick 自動改本機關鍵字挑（不問 AI、不花錢），印一行提示；有帳或給 `--budget` 才問 AI。新手第 1 輪過關 7.4（Haiku 7.4／luna 8.6）、約 3 分鐘、4 概念
- C｜events 第 4 輪：README 照新慣例只留五個詞＋第一次跑，其餘搬 ADVANCED.md；Haiku 7.4／luna 8.8 分數過。概念數照「只算 README 列的」為 5，**頂層判過**（Haiku 數 9 是把輸出欄位和自動帶的值都算進去）
- C｜頂層：events 剩兩個介面卡點要修，排進架構回頭審的第二波：加 `aos7-events ack` 子命令（`read --ack` 照舊可用）、不帶子命令的 `--help` 只列給人用的指令（取樣器選項移到進階）
- A｜架構回頭審（Fable）：12 張意圖卡 [intents/](intents/README.md)；**全 aos 統一退出碼只留 5 個**：0 做到了／1 做不到（知道為什麼）／2 你給的不對／3 不知道（證據留著、再跑會接續）／4 做到了但帳沒清（只 llmcall 用）；錯誤訊息一律 stderr 一行「指令名: 發生什麼。怎麼辦」，機器看的 JSON 欄位一個不改 → [blueprint-errors](blueprint-errors.md)
- A｜**跨包副作用一律歸 aos7-up**：各包不再順手動別包的檔（routines add 不再改 tasks.json、mail send 不在對方 node 建 events 夾、skills pick 不碰帳的鎖檔）
- B｜要改數字的只有 author（5＝滿→1 等）、三關檢查器、events（滿 3→1）；llmcall／budget 凍結介面零衝突；不做共用錯誤函式庫
- C｜F2：AI 的「腦」brain 進 main——每回合讀一封信→組提示→問 AI→回信→記續行點；`brain/` 只留 3 個檔、不累積紀錄；`model` 為空或 "fake" 都當假 AI。假 AI 1 回合回信約 800 token；真 AI（chatgpt-gpt-6-sol-high）1 回合回 DONE、2952 token、4 秒
- C｜F2：真 AI 一開始以為自己有工具（回「我先確認工作區…」），提示詞加「你沒有工具，資料都附在下面，直接回答」後正常
- C｜ER0：統一錯誤規則的一致性測試 `tests/core/test_error_path.py`＋清單 `tests/error_path.json` 進 main；各包改完在清單自己那列拿掉 skip、補一個「不確定」案；核心 tick 用法錯退 1 視為相容；prompt 的 JSON 回條留在 stderr 照藍圖
- C｜ER-prompt-metrics：prompt 出錯時 stderr 第一行照舊是 JSON、第二行加一句人話；metrics 錯誤改統一一行格式；兩包 README 只留新手部分、其餘搬 ADVANCED.md。新手重試 prompt 7.4／8.8、metrics 8.0／8.8
- 結果｜A5 學徒（目標 3 第一個實證）：真 AI 學徒寫出 **2 個 aos 新元件並過三關合進來**——工具包 `packs/usage/`（看 token 用量）、模組 `modules/llmdiag/`（診斷 LLM 線路）；人工只修 1 次（把索引列搬進表格）。23 次真 AI 呼叫、23.6 萬 token；16 份候選有 10 份被三關擋下
- 結果｜A5 自我改進：題 2 帶踩坑筆記比不帶少重問 1 次、少 15% token，但失敗原因都是 proxy 問題、筆記擋不住，**判定沒有足夠證據算「自我改進」**
- 發現｜A5：經 LiteLLM 時 `chatgpt-gpt-6-sol-high` 11 次有 4 次只回一行開場白、卻計費 5～6 千輸出 token（astra 沒這問題）→ 下一輪查
- C｜A5：學徒的 3 個沒合進來的 `apprentice/` 比較分支留著，刪不刪等你（刪分支算不可逆）
- C｜ER-wfnode：照統一錯誤規則改完，一致性檢查真的跑在 wfnode 上並通過；lint 沒跑完、讀寫出錯改退 3（不知道），`--flavor` 打錯改退 2；README 只留新手部分。新手重試 7.4／9.2
- C｜ER-mail：寄請求只在對方已有 events/ 時才發必讀提醒（不替別人建夾）；read 不再掃整個郵局、不拿別人的鎖（看自己寄出未辦完的改用 `audit <我>`）；讀寫錯誤改退 3、撞名被拒改退 1；新信箱提示仍印在 stderr（防打錯名）。新手重試 8.4／9.0
- B｜F1：一鍵入口 `aos7-up` 進 main——一行起 node、每秒印「心跳 N」、Ctrl-C 收乾淨；`status` 六行；假 AI 一圈 1 秒回信、1104 token。up 自己裝 routines 任務與 events 夾（跨包副作用歸 up）；假 AI 也要開帳（llmcall 需要）；已建好的 node 不准在假／真 AI 間切換（要換就另起一個）；`stop` 停整間房子的心跳、不刪檔。新手 Haiku 7／8／6、luna 8／9／8
- 發現｜F1：重跑 `wfnode init` 會把信裡的 `{{user}}` 改成「（未定：user）」→ 交 wfnode 修
- C｜ER-routines：`add` 不再改 tasks.json（aos7-up 已自己裝 routines 任務）；`rm` 遇到沒清單的 node 不再建資料夾；格式錯改退 2、`ls --run` 遇鎖忙改退 3。新手 Haiku 7／luna 8
- 觀察｜llmcall `test_in_process_drip` 在全套負載下偶發失敗一次、單跑全過；再出現就查
- C｜ER-compact：不需整理時不再寫狀態檔；發事件改成可選（compact.json 的 `events`，預設關，發不出也不影響結果）；意外錯誤改退 3；README 只留新手部分。真 AI 壓縮 73%。新手 Haiku 7.6／luna 9.0
- C｜wfnode 小修：重跑 init 不再改任何既有檔（含 inbox 信件）；init／check 不掃 inbox/；模板檔裡剩下的 `{{` 改成列出位置請人手補（不再自動補）
- 結果｜QS 新人從零上手（只看 QUICKSTART）：第 2 輪過關，Haiku 7.6／luna 8.6，兩位都說「ELI5 之後不複雜」；每人約 6～10 分鐘、3 個指令。概念數 Haiku 數 8（輸出裡有英文 DONE、token 被算進去）→ [firstrun 試用](play/2026-10-10-firstrun/README.md)
- B｜頂層：開 ER-up 隊，照 QS 回報改 aos7-up 的輸出：status 全清提示改成刪整個房子；DONE／token 換成中文白話；`--help` 只列 3 個指令（退出碼、-d、stop 搬到 ADVANCED）；`--model` 提示指向 ADVANCED
- C｜ER-events：新增 `aos7-events ack`；`--help` 只列 pub／read／ack；ack 不再對沒 state 的夾建鎖檔；`pub` 不再自動建 events 夾（要 `--create`）；滿了改退 1、不確定改退 3、read 拼錯路徑改退 1（原本假裝空帳本）。新手 Haiku 7／luna 8
- C｜ER-author：三關檢查器指令名定為 `aos7-gates`；三關預設離線規則審（要 astra 審得明講，不自動花錢）；`publish` 沒給 `--repo` 不建分支、只說會建在哪；索引列改插進表格內；學徒／審查／learn 三種 AI 呼叫分開標記；被拒的候選退 1。新手 Haiku 7／luna 9
- C｜ER-llmcall-budget：帳任務沒在跑時，llmcall／budget 1 秒內退 1、什麼都不寫（原本會一直等）；錯誤訊息直接附可複製的起帳指令；回條與 JSON 一個欄位都沒改。新手 Haiku 7／8／7、luna 10／10／9
- 觀察｜up 模組兩個計時測試在全套負載下偶發失敗一次、單跑全過；和 llmcall `test_in_process_drip` 同類，再出現就一起查
- 發現｜proxy 截斷根因查到 → [litellm-truncation](play/2026-10-09-real-ai/litellm-truncation.md)：sol 的回答其實都有回來，但後端把「開場白」和「答案」拆成兩段，LiteLLM 轉成兩個 choice，**aos 只讀第一個**（`packs/llmcall/aos7_llmcall_litellm.py` 與 `core/llm/src/llm.cpp`）。另外 proxy 每次自帶的 1.6k 是寫死的 Codex 系統提示，讓模型以為自己在 Codex 裡、想先看檔
- B｜頂層：開修補隊——讀「最後一個非空的 choice」並在收據記 choice 數；所有要 JSON 的呼叫在提示尾端固定加「你沒有任何工具，不要開場白，第一個字元就是 {」（重放 4/4 有效）
- 待你決定｜LiteLLM 設定：啟動 proxy 前設 `CHATGPT_DEFAULT_INSTRUCTIONS` 換掉 Codex 系統提示（每次省約 1.4k token、模型不再誤以為在 Codex 裡；風險是後端可能擋、astra 的快取會失效）。這是你的設定，我沒動
- C｜ER-up：status／stop 的全清提示改成列出房子裡每樣東西（有別的 node 時不叫人刪整間）；ask 回信不再帶英文 DONE、用量改「讀寫約 N 字」；`--help` 只列 3 個指令；起好時不再提 `--model`（ADVANCED 寫清模型名從哪查）。新人從零（只看 QUICKSTART）第 3 輪 Haiku 7.0／luna 8.8，概念 5、指令 3
- C｜頂層：QUICKSTART 的「aos 資料夾」補一句「就是你 git clone 下來的那個」（Haiku 最後的卡點）
- C｜ER-skills：pick 不再在帳夾建鎖檔（只讀試鎖）；帳沒在跑退 1 並附起帳指令；`.pick/log.jsonl` 只留 50 行、請求檔用完即刪；bank.py 暫存夾必清。新手 Haiku 7／luna 9。**統一錯誤規則全部 12 個模組完成**
- C｜頂層：保留「沒開帳時本機關鍵字挑」，意圖卡改成這個說法（原卡寫「不用 AI 就不挑」，與已上線行為相衝）

## r4（約 18:00 起，照 [plan-2026-10-09-r4](plan-2026-10-09-r4.md) §5，Fable 代定）

- A｜r4 主線：回頭審第二輪（找重複功能與殘留副作用，修或重造）＋brain 多回合（一封信跨回合、會 compact／skill／發進度信、被殺接回）＋12 封信長任務真跑＋學徒三連題拿「自我改進」真證據＋效率前三名＋astra-9 全日回歸
- B｜重複功能原則：量尺類只留一個（usage 被 metrics 涵蓋就併入、llmdiag 對 diag 同理；events `read --ack` 留一輪後移除），由回頭審證據定
- B｜brain 多回合：AI 仍沒工具；每 5 回合發一次進度信，連續 3 回合沒進展就發「要你決定」停下；compact 只在超門檻時呼叫、可關
- C｜學徒三連題固定 sol-high、不合進 main；proxy 修好前不跑。效率：不動你的 LiteLLM 設定、只用核心既有 wake、模型升級鏈只寫在 ADVANCED
- C｜真 AI 呼叫上限：學徒三連題 ≤200、長任務 ≤100、效率各 ≤60、回歸 ≤200
- 待你決定｜舊 worktree：loop7～10 已合進 main 的由頂層照整合隊清單刪；`apprentice/*` 分支與 `_check_main` 等你（刪分支不可逆）
- C｜MC：llmcall 與 C++ 核心 llm client 改取「最後一個非空的 choice」；學徒／審查／learn／brain 提示補「不要開場白，第一個字就是…」。真 AI 重放 6 次全部拿到完整答案（修前同樣請求只拿到開場白）。choice 數與略過的開場白只記在 raw.json（回條凍結不加欄）；第一個 choice 為 null 但後面有答案改判答到
- 結果｜EF1：MC 修好後重量 12 圈：proxy 每次仍自帶 1644 token（其中 Codex 系統提示 1620），占每單 63%；所有回覆都是單一 choice、`{` 開頭、全過三關 → [proxy-overhead](play/2026-10-09-real-ai/proxy-overhead.md)
- 待你決定｜同上一條 LiteLLM 設定：設 `CHATGPT_DEFAULT_INSTRUCTIONS` 為一句短句，這題每單預估從約 2606 降到約 1000 token（−62%）；說明頁寫了怎麼設、風險、怎麼驗與怎麼還原。你同意後 EF1 會再跑 12 圈補「改後」數字
