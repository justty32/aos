# proto8 討論紀錄：2026-11-14

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [proc-mental-model](proc-mental-model/README.md) | proc 新心智模型發想（線程，使用者「不急、單獨派線幫我想想」）：opus 11 個＋fable 8 個（世界線束、樂譜與演奏、可換的軸、光錐、開放系統、展開的 fsm、九軸＝束的統計量、契約、最小作用量…），每個附一句話、小圖、好想處、盲點；純發想，沒定稿、沒出待裁題 |
| [aos-brainstorm](aos-brainstorm/README.md) | aos 頭腦風暴輪（線腦，使用者「太早規劃了…先發想」）：fable 120 條＋Argon 22 條＋opus 匯總，重點題「人是外部計算單元」（人 kernel 讓人更懶、原則回收、行為量好不好懂、沉默六種、代定＝分支預測）、粗化細化與 `_metainfo`／`_index`、公開宣告 vs 私有看法；6 個可丟棄小實驗未跑；取代 11-13 any-resource-os；舊 D1～D16 不裁、自然浮現；沒出待裁題 |
| [astra-kernel-1114](astra-kernel-1114.md) | astra 當 kernel 施工（線星→ok-astra）：階段 0～2 過；階段 3 提前做，每隻 sol 分額度成立；astra 省錢 system 實驗能用、但沒比 gpt 隊省，不轉正；階段 4 不做；收線。AK14 `agents_ctl` 補 `no_wait`；AK17 修好：agent-fsm 被腦額度拒絕（`BudgetMissing`）不再停下，冷卻後重寄，範本新掛 `brain_notify` 寄 BLOCKED 信給 mom（`subagent add` 預設 `AOS_NOTIFY_BOX`），換樹清單在 AK17 節。ADV 修 wf/advices 兩條：BudgetMissing 回 `scope`、`window`、`resets_at` 等欄位，agent-fsm 冷卻等到重置、`window all` 停下；guard 唯讀查詢放行（新家 `wf/public/tools/fsm-guard`，Argon 審三輪），換樹清單在 ADV 節 |
| [misc-1114](misc-1114.md) | 線雜：eca_main 來信七項與線庚剩的（set-def 停拔掛回、睡醒提醒、改名寫法、`AOS_HOME` 那句、真 CLI 實跑）與 T45～T48；只到施工圖與暫存樹（sol 腦通過、工人掛上未派工），程式沒改，交棒 ok-misc；T46 判 bug 可修，T45／T47／T48 牽涉設計只列；真 codex 實跑卡在「不要走codex」待問 |
| [kernel-limits-1114](kernel-limits-1114.md) | kernel 限資源施工（線限）：段 2、段 3 非 C++ 部分寫成三份施工圖紙（B1 kernel 站 `limits`／`users`／`groups`、B2 `aos-share`、B3 `aos-asuser`＋aos-sandbox 認 `sub:N`），暫存樹 `~/code/limits-1114` 與接 LiteLLM 的 gpt 隊搭好；還沒派工、沒寫碼，交棒 ok-limits；實作級代定 D1～D9、坑 K-a～K-g |
| [kernel-framework-1114](kernel-framework-1114.md) | 通用 kernel 框架（線框，家機）：批 5 接線做到七成（暫存 `~/code/kf-1114/b5`，沒跑測試、沒進 main，三個設計題待正規流程）；gpt agent-fsm 施工隊暫存樹 `~/code/kf-1114/fsm` 步驟 1～6 驗過、乾跑未跑；批 10 圖紙寫好未派；codex 照「不要走codex」收掉；交棒 ok-kf |
| [quiet-1114](quiet-1114.md) | 清淨時段小工具（repo-aos 自己的免打擾）：`wf/tools/quiet.py`（開 30m／關 off／status）、`quiet_hook.py`（before_queue，清淨期間擋 new_mail、kernel_hold、放行 xiaosi 與其他訊息）、`quiet_tick.py`（到期後合併成一則 `[aos] quiet_over` 寄回）；暫存樹實測與 7 題單元測試過、kernel_gate 請求不因通知被擋而消失；已掛活樹 repo-aos（備份在 `~/.aos/saves/tree-swap/quiet-1114-083239/`），未開清淨 |
| [skyrim-agentctl](skyrim-agentctl/README.md) | skyrim agentctl／wf 借鑑調查（skyrim-agent 線）：**做完、已收線**（ok-skyrim）；借鑑清單三類（第一類三條頂層已採用、落地進 wf：寄給 xiaosi 的信三條規矩、任務書範本多四欄、wf/public/recipes.md）；修訂版經 Argon 審與三隻 sol 回程式查證（13 句現況成立 4、部分成立 9，改掉四處說錯的，如 subagent add 有 AOS_KERNEL 就經門）；隊形心得：fable eca 在活樹帶 sol／astra 的 agent-fsm 很順，但環境沒 AOS_KERNEL、kernel_gate 沒收到請求；蒐集十一份＋查證三份；沒出待裁題 |
| [gate-auto-1114](gate-auto-1114.md) | repo-aos 的 kernel_gate 先自動處理一輪請求：新 hook `lib/agent/kernel_gate/triage` 照 gate 夾的 `triage.json` 判，日常的直接放行、明顯不對的回 `GateRefused`、其他照舊 hold，每封記一行 `triage.jsonl`；站程式沒改；15 題測試與暫存樹 `~/code/gate-1114` 實測過；已換上活樹 gate（備份 `~/.aos/saves/tree-swap/gate-20261114-083348/`） |
| [commit-queue-1114](commit-queue-1114.md) | commit 排隊（使用者「commit這塊…想辦法」「交給fable規劃」）：`wf/tools/commit-request`，申請者自己拿 flock 當場做、不常駐不掛 hook；repo 外快取樹組 commit（HEAD＋點名的檔＋共用索引檔操作＋index_gen 生成物）、CAS 推 main、補回共用工作樹與 index；claim 擋衝突；fable 設計、Argon 審、採納表；暫存 clone 48/48 綠；本身是它在真 repo 的第一件 |
| [view-1114](view-1114.md) | 全景頁（線景）：兩輪規劃（小助手＋中轉信箱＋固定程序；公司部門、2D 縮放地圖、嵌套、bot 模型、普通 proc），fable 設計、Argon 審兩輪；第 0 期上線 127.0.0.1:8767（答題、說話、寄信、往來；後端 API 與前端分開）；擴充／HR／電力留接口；下一步 0.5（通知各隊、systemd、指令單）、0b 地圖、1 小助手 |
| [wait-user-rewrite-1114](wait-user-rewrite-1114.md) | WAIT_USER 舊帳 36 筆逐筆查證：37 個子項結案、其餘寄進使用者專區、2 件改列待派工 |
| [llmk2-1114](llmk2-1114.md) | 線層 ok-llmk2：llm kernel 上一層規劃——部門配額樹（配給＋排程，頁面仍叫電力）；站內照樹放行、站外 aos-llm-quota 改表報帳、Claude 本機紀錄電表先量不管；8 題方向題待拍板，只規劃 |
| [sec-1114](sec-1114.md) | 線安 ok-sec：借 Linux uid／檔案權限讓 aos 更安全，只規劃——三圈（使用者帳號／每隻 agent 一個 subuid／外來程式進沙箱）、第 0 期免 root 實測 8 項、Argon 審過定稿；第 1 期不改用法，改用法的排在公開 demo 之後；11 題待拍板 |
| [board](board-1114.md) | board-1114：布告欄＋分級＋頻道協議 comm/1 規劃 |
| [release-1114](release-1114.md) | 公開 demo 發佈版（線發 ok-release）：規劃走完（fable 設計、Argon 審、計劃 v2），使用者 ★1～★5 照推薦（核心頁雙語中文先、MIT＋CC BY 4.0、同 repo、不改歷史、頂層加 docs/ 等）；草稿 v2 給使用者看（宣傳頁 A／B 待挑、README 中英、文件 11 頁，指令照字實跑過）；待答：挑版、副標、原話逐句、docker；不 push、發佈檔還沒動 |
| [kb-1114](kb-1114.md) | 重整 aos 知識庫與 wf/（線庫 ok-kb，fable）：用各隊經驗盤點重複、過時、跟程式對不上、找不到、太長；4 隻 sol＋2 隻 Claude 蒐集中，設計與方向題未出 |
| [tree-swap-1114](tree-swap-1114.md) | 11-14 晚換樹整合步驟表（ok-kf）：各線清單（線雜、ace14088d、AK14／AK17、限 B1／B4／B5、gate triage、C′ A、三個 .env、兩條連結、aos-llm-kernel）對到一張表；釘 `246d4aa49`（含線星 ADV；乾淨複本全套綠，C++ repo 外編好）；swap.sh＋新 extras.sh（eca 定義 hooks 補 screen_linger、.env、guard 換裝附驗法、brain_notify、連結搬開）先 check 再 all、附退回；tree-swap 三支拿掉 rm（`b8ff23ada`）；暫存樹 r1、r2、r4 15 段全綠（r3 紅在 guard 驗法對 lead 的期望、已修）、換約 4 秒、退回 1 秒逐位元同；查到 `.env` 的 PATH 要 `--dotenv-override` 才生效，連結先不移；待使用者定 D0～D3（何時換、連結、brain_notify、aos-llm-kernel 先問 ok-sec）；Q10 佔位、今晚不做 |
| [wake-1114](wake-1114.md) | 線醒 ok-wake：沒開畫面時 eca claude 怎麼及時收信，實測延遲（閒 2 秒、turn 中要等 turn 完、冷卻中等冷卻完）並比較做法；主案 stdin stream-json 中途餵信，備案 socket；使用者回 build:now，施工待派 |
