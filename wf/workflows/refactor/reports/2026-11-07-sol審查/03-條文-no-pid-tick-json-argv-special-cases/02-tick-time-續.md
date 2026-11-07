C 隊審 tick-time（續）：第 5～8 條與已核對沒問題的清單。

← [入口](../03-條文-no-pid-tick-json-argv-special-cases.md)｜上一份 [02-tick-time](02-tick-time.md)｜下一份 [03-json-argv-J7](03-json-argv-J7.md)

## tick-time（續）

### 5. 代定沒標的三處（都不是方向題）
- **類別**：代定｜**嚴重度**：品質
- **檔:行**：(a) `02-N-28.md:72`——`tick` key 形狀、展開成 `_tick`、預設檔名寫在「已定」句裡，其實是 tick-time 03 §一「代定，可翻案」；使用者定的只有「自帶、不強制、不耦合」。(b) `proto8/docs/NORMS/02-設計理念-時空.md:8`、`proto8/docs/NORMS/04-基礎設施-loop與daemon.md:9`——T5 由 aos-exec 判（規劃時傾向 loop／daemon）、「兩種都寫＝錯、不猜優先」、哪些指令算「人打的」（`aos-agent listen` 人也會打卻加了 `--timeout-ticks`）都寫成現況，來源是 tick-time 05 代定 1、3 與 03 §二。(c) `proto8/docs/CONCEPTS/02-設計理念-時空.md:22` C-44 還寫「實作排在 T1、T7」，T1、T7 已做完沒補註；兩份時空檔頭導覽「N-01～N-03」沒列 N-65。
- **commit／哪隊**：`76297cae1`、`2f4e2dc3`、`a858fe1a0`（sol 寫、opus 隊長收）
- **使用者原話**：「tick我希望能夠在daemon的設定中自帶(當然，不強制，不與daemon耦合)」（tick-time 03:7）；「與linux proc的交互這塊(daemon)」用精確時間（fs-image README:21）。誰判、擇一、哪些算人打的——沒找到原話，是推論。
- **建議**：直接修：各加一句「（tick 隊代定，可翻）」；C-44 補已實作註；檔頭加 N-65。

### 6. 附錄1 條號表 N-63 列仍寫「AOS_TICK 非 hub」「暫定待 T1／T7」；四種性質表 ② 列與 `:18` 仍寫「例外」
- **類別**：條文｜**嚴重度**：品質（冗餘兩處只修一處、做完的寫成待）
- **檔:行**：`proto8/docs/NORMS/附錄1-條號表.md:56`；`03-AOS_-變數的四種性質.md:14`、`:18` 對 `:22`「不再各算例外」
- **commit／哪隊**：`76297cae1`、`7864becd`、`c56e53751`
- **問題**：special-cases 05 第 2 處的改讀註只補在附錄2 06:23，附錄1 同一句沒改，跟使用者「歸 ② hub」相反；T1、T7 已做完。② 列仍說「例外」，K3 註說「不再各算例外」——而 `AOS_TICK` 值是檔不是資料夾這點仍是例外，K3 沒涵蓋，該講清楚「例外只剩值是檔」。
- **使用者原話**：「跟 AOS_KERNEL 同類 (Recommended)」（lift-to-norms README:19）；「統一成 K3 (Recommended)」（special-cases README 裁定 3）
- **建議**：直接修兩處。

### 7. 搬家食譜建議「只在樹根開 tick」，跟使用者選的「範本預設帶 `tick: true`」「三個時鐘留著」方向相反
- **類別**：條文（程式文件）｜**嚴重度**：跟原話不符（輕）
- **檔:行**：`proto8/cmd/aos-agent/docs/04-搬家/01-六段食譜.md:63`；思路源頭 `tick-time/05-T5T6T8與試驗場.md:37`
- **commit／哪隊**：`57e55e650`（P8，P 隊）；05:37 是 tick 隊推薦
- **問題**：板子比喻條文（`proto8/docs/CONCEPTS/附錄1-續-板子比喻.md:13`）只寫「tick＝板載晶振」、沒寫「只有根帶鐘」，所以條文本身不矛盾；「只有根帶鐘」是 tick 隊 05 的讀法，使用者看完選「留著」等於沒採，但 P 隊同晚照這讀法寫了食譜。HANDOFF 已記、沒修。
- **使用者原話**：「範本（試驗場、`templates/`、`kernel/` 的 daemon.json）預設帶 `tick: true`」（`daemon-board/04-凍住後要能遷移-續.md:21`，使用者「兩題都按照推薦。」）；「領班的鐘＝留著、總機的鐘＝留著」（tick-time 05:39）
- **建議**：直接修食譜：「範本預設帶 `tick: true`，每台一個鐘、近的贏；要凍住整個世界讓根 sleep，不是只停根的 `_tick`；各子樹 tick 不能互比」。板子比喻可加一行「子 daemon 自帶 tick＝子板自己的晶振」。

### 8. 兩處小的
- `proto8/knowledge/aos/world.md:27`「The daemon advances it」——讓時鐘走的是 `_tick` 那列 proc，daemon 不碰時鐘（N-28:72）；agent 讀了會把 `_tick` 被 pause 當成 daemon 壞了。品質；直接修。（`5159cc1c3` 夾帶，內容 tick 隊寫）
- inst 單子收 `timeout_ticks: null`＝沒寫（`proto8/impls/aos-exec/src/inst/fields.cpp:95-102`），thought／agents 收到 `null` 卻報 `ArgumentsBad`（`proto8/lib/agent/thought/_entry:214-218`、`agents/_entry:446-450`）——腦常把選填欄填 `null`；跟 A 區 01 第 3 條（`tool_io` 對 `null`）同根。品質；建議 thought／agents 把 `null` 當沒給。

### 已核對沒問題的（tick-time）
- N-28:34-35 `_tick` 例外：原句「照 daemon 型規則重起」留著、加 P6 改讀成 `auto_restart`，跟 N1「照推薦」＋P6「不要耦合」一致；程式 `daemon.cpp:62-63` 寫 `auto_restart: true`。N-28:72「程式預設不帶、不強制」照原話。
- N-01 改讀（`02-設計理念-時空.md:8`）：「內部看 tick；對人、對外、對 Linux proc 用牆鐘」照 fs-image 原話；T5、T6 已實作註對程式。
- 「近的贏」：N-28:73 寫成已定，出處 daemon-board 題 2；special-cases K4 沒問過使用者，但條文也沒把 K4 寫成通則。HANDOFF 說「T 隊又當方向題丟上來」指的是 05:37 那題（拿掉領班的鐘），條文沒受影響。
- 欄位名對照：inst `timeout_ticks`（兩個都給＝`EntryBad`）、thought／agents `timeout_ticks`（＝`ArgumentsBad`；agents 上限 1700 是代定 4、條文沒寫）、`aos-agent listen --timeout-ticks`、`daemon_ctl.ask(timeout_ticks=)`、人打的 `--timeout-s` 照舊——全對；P-44:8「時間旗標帶單位後綴」已涵蓋。
- C-54 R6 tick 欄名（`C-54-命名方法/01-R1～R7.md:22`）照「照命名法 (Recommended)」，列的欄名都照 R6。
- 板子比喻 tick 行、CONVENTION 佈局「範本帶 `tick: true`」（`01-一-aos-保證的與二-佈局.md:40`；`kernel/llm-kernel`、`kernel/daemon-judge` 確實有）、NORMS 附錄1 N-65 列、附錄2 06:23 改讀註、四種性質表 ④ `AOS_TICK_INTERVAL`「使用者特許」「1000 暫定」、`AOS_TICK_INTERVAL` 沒設＝1000 三份程式一致、`TickBad` 退 1、沒設 `AOS_TICK` 不印 warning、人 export 的 `AOS_TICK` 被 daemon 蓋掉（近的贏）——都對。
- 沒實跑程式；N-65 本條沒審，只順帶指出 N-65 ①「沒有就退牆鐘」沒分「沒設」跟「設了檔不在」（B 隊）。
