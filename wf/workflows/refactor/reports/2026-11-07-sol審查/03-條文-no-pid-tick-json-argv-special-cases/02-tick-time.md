C 隊審 tick-time 落進條文的部分（T7 `d6c38be3`、T5 `2f4e2dc3`、T6＋T8 `a858fe1a0`、lift-to-norms 補註、K 隊 K3 註、R 隊 warning 註；N-65 本條歸 B 隊）。

← [入口](../03-條文-no-pid-tick-json-argv-special-cases.md)｜上一份 [01-no-pid-P5b-續](01-no-pid-P5b-續.md)｜下一份 [02-tick-time-續](02-tick-time-續.md)

## tick-time（子 agent opus 審、隊長收攏）

時鐘這條線的核心都照使用者的話落進條文：daemon 設定自帶、選填、不耦合；沒設 `AOS_TICK` 退牆鐘；`_tick` 退了靠通用 `auto_restart` 重起；「近的贏」是使用者在 daemon-board 題 2 選的（選項正文寫「近的贏、同 `AOS_TICK` 傳法」），後來「三個時鐘留著」又確認一次，條文寫成已定是對的。旗標與欄位名四處（inst 單子、thought／agents、`aos-agent listen`、`daemon_ctl`）都是 `timeout_ticks`／`--timeout-ticks`，照 C-54、P-45 對得上。毛病集中在「設了指不到」那句寫反、一處把沒做的事標已實作、幾處代定沒標。

### 1. 四種性質表 K3 註把「設了但指不到」寫成「照退路走」，使用者裁的是「當第 0 格、不改退路」，同檔下兩行又寫對的
- **類別**：條文｜**嚴重度**：跟原話不符（照字面做會把指錯的時鐘當成沒時鐘、退牆鐘）
- **檔:行**：`proto8/docs/NORMS/10-基礎設施-定義與工作區/07-hub-型環境變數與父子交代/03-AOS_-變數的四種性質.md:22`（錯）；同檔 `:24`（對）
- **commit／哪隊**：`:22` 是 `c56e53751`（K 隊，條文合併是 sol）；`:24` 是 `3bada8a0a`（R 隊 sol）
- **問題**：`:22` 寫「設了但指不到時照退路走、印一行 `warning:`」，同段又把 `AOS_TICK` 的退路定成「沒設退牆鐘」——照字面讀，時鐘檔不在＝退牆鐘；`AOS_KERNEL` 指錯＝改寄 daemon 的 ctl 信箱。使用者裁的是時鐘檔不在＝當第 0 格、Q5 選項明寫「不改退路」只印 warning；程式也是這樣（`proto8/impls/aos-util/src/tick.cpp:70-73` 缺檔回 0）。隊長問的「沒設」跟「設了指不到」被混在一起，就混在這一行。F 隊 [06 第 1 條](../06-special-cases抽核/01-發現.md) 從程式那側也抓到同一句。
- **使用者原話**：「當第 0 格 (Recommended)」（`proto8/thinking/2026-11/05/tick-time/04-T線實作結果.md:19`）；「印 warning (Recommended)」＝「設了但指不到＝印 warning 行、不報錯、不改退路」（`proto8/thinking/2026-11/06/env-portability/README.md:32`）
- **建議**：直接修：`:22` 那半句改讀成「設了但指不到時**不改原本行為**（`AOS_TICK`＝當第 0 格；`AOS_KERNEL`＝照用那個信箱），只多印一行 `warning:`」；退路只講「沒設」。

### 2. N-67 ② 寫「跨樹信的毫秒 deadline 在 T4」並標已實作，但 T4 隊長代定「不改格式」，信裡期限仍是秒或 ISO 字串
- **類別**：程式現況／代定｜**嚴重度**：跟原話不符（也是「沒做卻寫成現況」）
- **檔:行**：`proto8/docs/NORMS/10-基礎設施-定義與工作區/09-N-67.md:7`
- **commit／哪隊**：`7864becd`（lift-to-norms 第二輪）＋`a858fe1a0` 的已實作註（tick 隊，sol 寫、opus 收）
- **問題**：使用者在 daemon-board 題 1 選的字面是「信裡用毫秒」；T4 隊長代定 4 把它讀成「跨樹用牆鐘、不用 tick」，所以 `priority.deadline` 照舊收 ISO 8601 或 epoch 秒。這個讀法可能就是使用者的意思，但它翻掉了原話字面，而 N-67 ② 還寫「已實作」，讀的人會以為信裡已是毫秒。
- **使用者原話**：「1「信裡用毫秒」」（`proto8/thinking/2026-11/06/daemon-board/README.md:30`）；選項正文「① 信裡跨樹的期限一律毫秒（第②類「對外」）」（`daemon-board/02-能帶來什麼-續.md:24`）
- **建議**：擺給使用者：A（推薦）照代定讀——「毫秒」＝「用牆鐘、不用 tick」，格式不改，N-67 ② 加註「T4 沒改格式（代定 4，可翻）」；B 照字面改成 epoch 毫秒，要再動 llm kernel 跟寄信端。

### 3. 時鐘剛起、第一格還沒寫時，每個行程都印「指不到」warning——正常狀態被印成異常
- **類別**：設計｜**嚴重度**：品質（該考慮沒考慮的狀況）
- **檔:行**：`03-AOS_-變數的四種性質.md:24`；程式 `proto8/impls/aos-util/src/tick.cpp:23-30`、`proto8/impls/aos-daemon/src/daemon/daemon.cpp:70`（daemon 只 `setenv`、不建檔）
- **commit／哪隊**：`3bada8a0a`（R 隊 sol，warning）＋`d6c38be3`（T 隊 sol，展開不建檔）
- **問題**：開了 `tick: true` 的 daemon 起來頭一秒，時鐘檔還沒寫，每個讀時鐘的程式（連 daemon 自己）都印 `AOS_TICK points to a missing file`；tick-time 05:32 實測每次起領班都印，試驗場 README 只好寫「正常」。比喻：新電子鐘插電頭一秒螢幕空白，就讓每個房間響一次警報。
- **使用者原話**：沒找到原話講「剛起」；Q5 只裁「設了指不到印 warning」。這是推論。
- **建議**：細節題、不用問：daemon 展開 `tick` 時若時鐘檔不在就先原子寫一個 `0`，「檔不在」就只剩真的指錯。

### 4. `tick.interval_ms` 明寫 1000 時不往下傳，會破掉「近的贏」；這條判準是推薦旁附的，條文卻掛在使用者原話旁
- **類別**：設計／條文｜**嚴重度**：品質（要使用者點頭）
- **檔:行**：`proto8/docs/NORMS/04-基礎設施-loop與daemon/02-N-28.md:73`；`03-AOS_-變數的四種性質.md:20`；程式 `proto8/impls/aos-daemon/src/daemon/daemon.cpp:71`（`interval != 1000` 才 setenv）
- **commit／哪隊**：`76297cae1`（條文）、`d6c38be3`（T7，sol）
- **問題**：使用者選的選項正文是「有 `tick` key 就一併把 `AOS_TICK_INTERVAL` 設成 `interval_ms`、近的贏」；「＝1000 就不設」是 fable 寫在推薦旁的判準。上一層設 300、子 daemon 明寫 1000 時，子樹讀到的仍是 300，退牆鐘換算差三倍。tick-time 04 邊緣 9 攤過、條文沒提。
- **使用者原話**：「2「設，近的贏」」（`daemon-board/README.md:30`）
- **建議**：A（推薦）明寫了 `interval_ms` 就設、不論是不是 1000；B 維持、條文加一句「明寫 1000 不往下傳」。不論哪個，N-28:73 把「≠1000 才設」標成推薦判準。

（第 5 條起、欄位名對照與已核對清單在 [02-tick-time-續](02-tick-time-續.md)。）
