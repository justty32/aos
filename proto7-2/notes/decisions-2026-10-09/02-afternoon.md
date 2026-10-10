# 2026-10-09 頂層代定清單：下午到 14:40

← [10-09 代定清單](../decisions-2026-10-09.md)｜上一份 [上午](01-morning.md)｜下一份 [續推：使用者三目標](03-push.md)

## 下午（照 plan-2026-10-09-pm §6，Fable 代定）

- A｜下午主線：事件保存第一版落地（新模組 `modules/events/`，核心零改動）；LLM 作者今天只出藍圖、不接真模型；kernel 任務包與測試加速今天不排
- A｜事件保存 5 題全照 event-store 報告 §11 預設：逐件業務事件＋明示取樣的核心觀測；回看／必讀兩用途分開；先單 node 不集中；滿了必讀停收、觀測續但報缺口；第一版只承諾程序 SIGKILL 可接續（不 fsync）
- A｜依你 user-advice 的意見定硬約束：每 node 一個 `events/` 夾、活躍段 1 檔＋封存段最多 4、不每回合新檔／新夾、超過就刪最舊（必讀只停收不刪）
- B｜history.py 不動、`.aosd/log.jsonl` 只續讀不裁；step／budget／adapt 今天不接事件
- C｜once_retry R8-26 維持「至少一次」不修；astra-7 五條今天修（A9-05 只寫文件）
- B｜E0／頂層核可：事件夾分「觀測」「必讀」兩條通道，各自 1 個在寫的檔＋最多 4 個舊檔，加 state.json 與鎖，**總上限 12 檔**（不是字面的 7 檔；兩通道清理規則不同，混在一起會誤刪必讀）→ [blueprint-ev1](../blueprint-ev1.md)
- C｜E0：預設每檔 1 MiB、單筆 64 KiB、等鎖 5 秒；寫一半的行直接截掉；去重只在還留著的紀錄內有效（超出即至少一次）
- 結案｜L3：上午 `test_unsure_listed` 連紅是驗證時「改壞再還原」同秒同大小，Python 沿用舊快取（非負載）；subd `allow_stop` 測試是讀 log 的時機假設錯，已改成等檔案出現。教訓記 dispatch lessons
- C｜L4：A9-02 history 升級時把含 `+`／`%` 的舊檔與 `daemon-events.jsonl` 一次改名成 `.v1` 封存、不再續寫（不丟資料、只斷連續性），夾內放 `.names-v2` 記號 → `modules/history.py`
- C｜L4：A9-03 陣列索引先去前導零再檢長度，超長回 125；前導零索引維持舊行為（照收，雖然 RFC 6901 說無效）
- B｜L1：N-06 修法——paused.json 加 `owe: {node: 開回合前的回合號}`，關回合時扣倒數與清 owe 同一次寫入；重起時回合號前進才補扣。不確定時寧可少跑不多跑 → `aos7_daemon.py`、spec §2.4
- C｜L1：A9-01 reaping 還在且沒時間線時 status 顯示 missing（含 `stop-kill` 留下的）→ spec §2.6；diff 239 行超 200 gate（多為測試），照 D7 接受
- 已知限制｜L1：回合中途才下 `resume --rounds` 時正好當機、或 daemon 被殺時舊 tick 已拿鎖還沒寫 round.json，仍可能多跑一回合（要給每回合落身分標記才能修）
- A｜A0：LLM 作者藍圖 [blueprint-llm1](../blueprint-llm1.md)——第一刀是 CSV 固定工具作者（新包 `packs/author/`），只准組合可信工具、預設產出候選要人跑 `publish` 才上線；12 題照 llm-author 報告 §十預設，前 4 題第一刀照做、後 8 題等第二／三刀再核
- C｜A0：job 名改 `<rid>_<sha8>`（符合 step 命名規則）；砍在「已記意圖、還沒合併」一律回 unknown 要人手 `publish --resend`；同需求已發布版本最多 2 個
- C｜E1：保存端加公開 `store.recover()`（三個定死介面不變）；`keep_segments` 上限 4 守住 12 檔；必讀通道加 `dropped_upto`，刪段時推進；壞輸入丟 ValueError；diff 1045 行超 500 gate，照 D7 接受
- 已知限制｜E1：每個 events/ 只能有一個取樣者；剛修掉半行就被殺時壞行計數可能少 1（紀錄不受影響）；`--status` 去重只在記憶體，重起可能記兩次同一事件
- C｜E2：`publish` 多 `node=`／`config=` 關鍵字；讀者遇壞行可抵一個缺號（store 在鎖內依序寫）；讀者 CLI 先是獨立腳本 `aos7_events_read.py`；demo 的 event_id 不含 run 號（重跑可去重）；diff 603 行超 400 gate，照 D7 接受
- C｜E3：`aos7-events` 加 `read`／`pub` 子命令；長跑是範例腳本不進測試套（需真 daemon、約 40 秒）；長跑用 8 KiB 小段讓 300 回合內真的會輪替與刪段
- 結果｜E3 真 daemon 300 回合：有讀者時 events/ 最多 9 檔、無讀者時 12 檔（存 state.json 時有 1 個暫存檔瞬間到 13，spec 已寫）；舊段有刪；記憶體與開檔數不長

## 下午後段（13:00 起，頂層代定）

- A｜下午計畫 13:00 就做完，剩餘時間開 A1 隊照 [blueprint-llm1](../blueprint-llm1.md) §9 實作 LLM 作者第一刀（`packs/author/`，用假候選、不接真模型）；另開小隊把 events spec 壓回 8 KiB 並補子命令；I2 收尾整合延到 A1 交件後
- C｜A1：需求 `inputs` 路徑相對 node；新增子命令 `aos7-author answer <rid>`（step close 前跑檢查器、結果記 verdict，author close 要求答案已驗）；退出碼多 `5`＝已發布滿 2 版
- C｜A1：新候選直接取代沒登記的舊待審候選；還有待審候選時 close 回 conflict；close 不移除表項（由人收）；表項「整項完全相等」才算相符
- 結果｜A1 第一刀 §4 六條驗收全過；100 份需求結案後 `author/` 恰 201 檔（每需求 2 檔＋1 把鎖），不隨回合增加；全套 556 項全綠

## 第三段（14:00 起，照 plan-2026-10-09-late §6，Fable 代定）

- A｜主線：LLM 作者第二刀藍圖＋**假傳輸**實作（新包 `packs/llmcall/`）、作者需求改走事件「必讀」通道；**真模型等你看過藍圖才接**
- A｜llm-author 第 7／8／9／11 題照預設在第二刀生效：沒證明上界就算軟預算；遠端結果不明不重送、保留預留額；usage 缺時照樣交候選、帳務標待結；只承諾程序中斷可接續
- B｜budget 部分結算：settle 放寬為 0≤用量≤預留；用量超過預留時結算預留額並記 overrun，不偽裝成功
- B｜wf-lint 超標的 31 份思想文件（ideas、spec 系列）不動，留你在場時整理；只清 86 條壞連結
- C｜「多跑一回合」類已知限制今天不排；adapt-llm 第三刀明天先藍圖
- C｜W1：86 條壞連結清零（約 70 條是寫成絕對路徑，改相對路徑）；目標已刪的改成純文字＋註明去向（例如 `packs/account` 已改名 budget，不改指以免變原句意思）
- 待你決定｜`proto7/user-advice.md` 還沒 commit，有 3 份文件連到它，所以在別的 clone 或 worktree 裡是壞連結。等你寫完再 commit 就好
- B｜G0／頂層核可：第二刀藍圖 [blueprint-llm2](../blueprint-llm2.md)——新包 `packs/llmcall/` 當 budget 第二種入口（假傳輸 `llm.fake`），介面凍結；遲到回覆只能人手 `adopt`；llmcall 多一個退出碼 4＝內容已交付但帳未清
- B｜頂層：用量超過預留（U>R）時只記 overrun、退出 4，**不自動停新預留**（llm-author §6.5 建議停准入對帳，這條要翻就改 budget gate）
- C｜V2：事件保存兩個限制都修掉（不只寫文件）：status 去重改落 state.json 的 `status_last`（存雜湊），重起不重記；半行截掉前先存 `torn`＋`torn_cut` 記號，計數不再少 1。恢復時會自己寫一次 state.json（spec 已註明例外）
- 結果｜I2：全套 ×3 在 a1be11b4 上各 556 項全過（約 300 秒）；核心行數總行 3004、程式 2353（D7 不擋）；白話報告草稿 [report-2026-10-09](../report-2026-10-09.md)，最終版由 I3 補第三段後定稿
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
