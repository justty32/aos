# 通用 kernel 框架圖紙（11-12，只規劃、沒施工）：一份骨架，判官與問腦總機都收進來；加下一站、數量另指、回信二選一、三個 hook 時機，與「狀態在哪」查詢信

← [2026-11-12](../README.md)｜[thinking](../../../README.md)｜依據：[11-11 kernel](../../11/kernel/README.md)（以它的結論為準）｜條文：[C-47](../../../../docs/CONCEPTS/04-kernel.md)、[N-42](../../../../docs/NORMS/09-kernel.md)、N-63｜零件 [01](01-框架零件.md)｜判官收編 [02](02-判官收編.md)｜狀態查詢信 [03](03-狀態查詢信.md)｜問腦收進框架 [04](04-問腦併不併.md)｜施工步驟 [05](05-施工步驟.md)｜邊緣狀況 [06](06-邊緣狀況.md)｜[Argon 審查原文 07](07-Argon審查.md)

> 狀態：圖紙第二版（照 Argon 審查改過、照使用者 11-12 三句裁定更新），沒改程式、沒改條文。**現在沒有等使用者裁的方向題。** 要使用者看一眼的有兩樣：下面「問腦怎麼收」這條大的代定，與「跟既有原則的衝突」第 2 條。其餘代定都可以翻案。

## 已裁：問腦總機收進框架

使用者 11-12 收工前：「kernel先這樣就好，開工等假日。我自己也要思考一下」。

使用者 11-12：「問腦總機要收進框架」。10-16「兩隻kernel不併成一支。」被這次裁定推翻（條文由條文線改，清單在 [04](04-問腦併不併.md) 末尾）。`AOS_LLM_KERNEL` 與 `AOS_KERNEL` 仍是兩個變數。

**問腦怎麼收（代定 K-F47，工時最大的一條，可翻案）**：用 Python 把問腦總機重寫成「同一份骨架＋問腦專屬那一包 `lib/aos/kernel_llm`」，刪掉 C++ 的 `impls/aos-llm-kernel`。對外完全不變——`kernel.json` 照認、stack 裡每個檔的格式、信與回信、錯誤代號都一樣——所以現有的黑箱測試改指新程式就是驗收。問腦這部分約 35 小時，真端點與本機模型要回家驗。

| 做法 | 後果 |
|---|---|
| **Python 重寫（採用）** | 骨架真的只有一份，問腦自動有三個 hook 時機；每輪比 C++ 慢一點，信很多時要量 |
| C++ 留著、只在裡面加 hook 點 | 省約 20 小時；但收信、排隊、回信還是兩種語言各一份，骨架其實沒併 |
| C++ 留著、前面串一站框架站 | 0 小時就有 hook；但每個寄件人的額度、「寄件人走了就收掉」都會失效 |

## 使用者原文

11-11 收尾：

> 「判官這東西...我覺得應該將其吸納進我們之後的kernel框架中。不過沒關係，今天釐清了概念，後續架構規劃上就很輕鬆了。」

11-12：

> 「條文改寫也可以做。然後通用kernel可以開始出圖紙。」

> 「kernel那邊，小而獨立的可以做，只是猜.stack感覺可以留著?。」

> 「kernel設計那塊，讓argon審過，fable看他審過的結果改過，再給我看。」

11-12（kernel 兩題：猜 `./.stack` 留不留、N-42「兩支不併」）：

> 「1.留。」

> 「2.等圖紙。」

11-12（看過第一版圖紙後）：

> 「問腦總機要收進框架」

## 一段白話總結

通用 kernel 框架是一份骨架加幾個零件。骨架每跑一次做一輪：把下游的答案收回來寄給原寄件人，看收件箱裡的信，排個先後，決定每封放行、拒絕還是排隊，放行的送去該去的地方。中間五件事（收答案、驗信、排序、放不放、送去哪）是可以換的口。現在的判官變成「掛 proc 那一包」：先來先掛、照白名單與上限判、放行就轉寄給下一站；它比判官多了下一站可設定（所以站可以串起來）、上限可以另外指定去哪台 daemon 數、回信可以選直接回或先回給我。問腦總機變成「問腦那一包」：照急不急排、看格數與額度、放行就掛成 proc 去問腦、跑完把結果寄回去；對外的樣子跟現在一模一樣，只是多了 hook。兩包共用同一份骨架，所以都有三個可以插自己程式的時機——判之前、判之後、回信經過時。站跟站之間只認 aos-post 的信封，信裡裝什麼各類自理。另外加一種新的信：一般程式想看狀態時寄信問「狀態在哪」，最底的 daemon 回自己那張表的路徑，中間的站可以在回信經過時把路徑換成刪減過的版本。

## 零件小表

| 零件 | 做什麼 | 設定一行例子 |
|---|---|---|
| 骨架 | 一輪的大順序、鎖、hook、拒信與回信；五個口給包換 | （程式，不用設定） |
| 收信 | 每輪從 `$AOS_STACK/requests/` 拿信、逐封看 | （不用設定） |
| 規則 | `procs_*` 的白名單與同時在跑上限；寫了才判 | `"allowed": ["kid"], "max_running": 5` |
| hook 三時機 | 判決前、判決後、回信經過時，跑你指定的 aos 函數，可改可攔 | `"hooks": {"audit": {"event": "after_verdict", "handler": "hooks/audit", "async": true}}` |
| 下一站 | 放行的信（或掛信）寄去哪 | `"next": "/srv/team/kernel_b/requests"`（沒寫＝`AOS_DAEMON`） |
| 數量另指 | 去哪台 daemon 的表上數 | `"count_daemon": "/srv/team/daemon"` |
| 回信二選一 | 不動 `reply_to`（回信跳過我）／改成自己（回信先回我） | `"reply_via_me": true` |
| 排隊 | 沒格時先來先掛；寄件人可在信裡寫最多排多久 | `"queue": true`（信裡 `"queue_wait_ms": 30000`） |
| 自己跑 | 把一封信掛成 proc、收成品、逾時、重掛一次（問腦那包用） | （程式；`"timeout_ms": 120000`） |
| 問腦那一包 | 能力包、急件排序、格數、額度、帳 | 現有的問腦 `kernel.json` 原樣 |
| 狀態查詢信 | 問「狀態在哪」，最底 daemon 回表的路徑 | 信 `{"procs_state_path": true}` |

## 代定清單（照原則定的，每條可翻案）

框架本體

- **K-F1** 框架用 Python 寫，是資料夾程式 `lib/aos/kernel/`；一輪＝一次執行，由 daemon（當身體）或 loop proc 一次次叫。
- **K-F2** 拆成骨架 `round.py`、`letters.py`、`runner.py` 與掛 proc 那一包的 `procs_rules.py`、`queue_fifo.py`，手寫 kernel 的人可以只拿其中幾個用。（第二版多了 `round.py`、`runner.py`）
- **K-F3** 設定檔叫 `kernel.json`，先過 aos-directive（可寫 `$env`／`$path`），每輪重讀；`next`、`count_daemon`、hook 的 `handler` 三欄是相對路徑字串時，從 `kernel.json` 所在的資料夾轉成絕對。
- **K-F4** 判官原有的鍵名照留（`allowed`、`max_running`、`queue`、`keep_ordered`）；新鍵叫 `next`、`count_daemon`、`reply_via_me`、`hooks`。
- **K-F5** `next` 的值是下一站的信箱資料夾；沒寫＝`$AOS_DAEMON` 的 ctl 信箱。
- **K-F6** 寫了 `next` 又寫了 `max_running`，就一定要寫 `count_daemon`，不然 `CfgBad`。這是把 11-11「下一站不是 daemon 又沒寫＝設定錯」落實：框架不猜下一站是不是 daemon，因為猜不準（信箱不一定在 stack 下一層、daemon 剛起還沒表、下一站是別台 daemon 身體時會數錯台）。
- **K-F7** 算出來的轉寄目標（明寫的 `next` 或從 `AOS_DAEMON` 算的）解開捷徑後就是自己的收件箱＝`CfgBad`；兩站互指成環不偵測。
- **K-F8** `allowed`、`max_running` 都沒寫、信也沒帶期限時，站不驗 body，全部原樣轉。
- **K-F9** 掛 proc 那一包排隊只做先來先掛；要優先序、額度的寫自己的包（問腦那包就是）。
- **K-F10** `queue_wait_ms` 轉寄時原樣帶、不改數字；每站從自己收到的信封時間起算。

回信

- **K-F11** `reply_via_me` 是布林、預設 false；開了以後下游回信寄到 `$AOS_STACK/replies/`，對照記在 `forwarded.json`。
- **K-F12** 〔作廢〕原本「`keep_ordered: true` 一定要同時 `reply_via_me: true`」：兩個鍵改成各自獨立、照字面，少一條組合規則（見 K-F39）。
- **K-F13** 代回失敗（原回信箱不在、或寄不進去）一律 warning、刪列、收掉，不重試；`forwarded.json` 等不到回信的列不自動清。
- **K-F14** 開了 `reply_via_me` 的站不留原請求的 body；`forwarded.json` 多記原信封的寄件人，`before_reply` 的事件裡 `sender`＝原請求的寄件人、`reply_sender`＝回信的寄件人。

hook

- **K-F15** 三個事件叫 `before_verdict`、`after_verdict`、`before_reply`；只寫在 `kernel.json` 一份，不像 agent 有兩份疊。
- **K-F16** `before_verdict` 一封信只跑一次；`after_verdict` 新信判完一次、離開隊時再一次，繼續排的每輪不跑。
- **K-F17** 能改的：判決前改 `body`；判決後改 `verdict`（只收 pass／refuse）與 `error`（改成 refuse 沒給 `error` 就填 `HookRejected`）；回信經過時改回信的 `body`。事件裡不放 `procs_*` 專用的欄。
- **K-F18** 三個時機退 10 都是攔下：判決前＝直接拒 `HookRejected`、不跑規則與 `after_verdict`；判決後＝拒 `HookRejected`；回信經過時＝原回信不代回、改回 `HookRejected`（寫明是回信被攔）。`intercept: false` 或 `async` 的 hook 不改不攔。
- **K-F19** `condition` 只有 `after_verdict` 收（比判決結果）；另兩個不收。
- **K-F20** 掛 proc 那一包寫了 `before_reply` 的 hook 卻沒開 `reply_via_me`＝`CfgBad`。
- **K-F21** hook 自己失敗、`on_error: stop`＝這輪退 1（`HookFailed`），信留著下一輪重來。
- **K-F22** hook 的共用引擎抽到 `lib/hook_run.py`（驗格、排序、比 `condition`、寫 `event.json`、跑 handler、解回話、`on_error`），agent 的 `hooks.py` 與框架都用它（中層 lib 不能 import 高層的 `lib/agent`）。

名字

- **K-F23** `lib/aos/judge` 整支改名 `lib/aos/kernel`；`judge.json`、`judge_replies/`、`judge_ordered.json`、stderr 前綴 `judge:` 都換新名，舊名不認。
- **K-F24** 範本 `kernel/daemon-judge` 改名 `kernel/daemon-kernel`；`kernel/procs-kernel` 不改。
- **K-F25** 「判官」這個詞在現行說明文件改叫「通用 kernel 的站」（框架站）；舊記錄不改。
- **K-F26** 新錯誤代號：`HookFailed`、`HookRejected`、`KernelFailed`，通用 kernel 多一個 `LockFailed`；其餘沿用。

狀態查詢信

- **K-F27** 查詢信的 key 叫 `procs_state_path`：請求寫 `true`，回信寫那份表的絕對路徑（daemon 沒開窗＝null）；可以跟別的 key 寫在同一封；寫錯＝daemon 回 `BodyBad`。
- **K-F28** 表裡的相對路徑從那份檔所在的資料夾算；hook 換出來的刪減表要自己寫絕對路徑。要真的隔得住靠 Linux 權限。
- **K-F29** 沒設 `AOS_KERNEL` 時不寄信，照現在的找法（`AOS_DAEMON`，再來 `./.stack`）直接算路徑；指令明給 `--daemon` 也不問。猜 `./.stack` 照留——**使用者 11-12 裁：「1.留。」**
- **K-F30** 查表時設了 `AOS_KERNEL` 卻問不到＝報 `KernelFailed`，不退回去直讀 `AOS_DAEMON`。
- **K-F31** 等查詢回信預設 3 秒（同 `ping`，`--timeout-s` 可調）；人的殼沒有 `AOS_STACK` 時，回信信箱用 `$AOS_KERNEL/reply/`。
- **K-F32** 記不記：`aos-agent` 一次執行只問一次、不落檔；`on_clock` 記的是鐘檔路徑（見 K-F44）。
- **K-F33** 〔作廢〕原本要加子命令 `aos-agent ctl state-path`：`on_clock` 改用既有的 `ctl ls --json`，用不到了。
- **K-F34** `aos-daemon-ctl`、`aos-mailbox`、`aos-sweeper`、`aos-eca-screen`、`promote` 是指名 daemon 的工具，照舊直讀、不改。

其他

- **K-F35** 新增一支整棵鏈的假腦劇本 `extras/kernel-chain-check/check.py` 當驗收。
- **K-F36** 試驗場：總機那台在問腦切換後要換身體（回家做）；領班那台加框架站、走 `AOS_KERNEL` 是可選的跟進。
- **K-F37** 〔作廢〕原本「問腦總機在方向題裁定前不動」：使用者已裁收進框架。

第二版新增

- **K-F38** 一輪的順序：先收掉「已經轉寄過」的原信，才代回回信；防重同時比 `forwarded.json` 列的 key 與列裡的原信名。
- **K-F39** `keep_ordered: true` 時不管有沒有 `reply_to` 都記 `forwarded.json`（不等回信的列 `reply_to: null`，原信收掉就刪）；只開 `keep_ordered` 不開 `reply_via_me`＝回信的 `in_reply_to` 是新信名、對不上原信，照字面。
- **K-F40** 期限是內建規則的第一條（排在 `before_verdict` 之後）：正數已過期＝拒，有格也拒（11-07 已裁不補掛）；`0` 不算到期，只表示沒格時不排。
- **K-F41** `before_verdict` 改過、還在排隊的 body 存 `$AOS_STACK/bodies/<信名>.json`，不放進公開的 `queue.json`。
- **K-F42** `aos-agent ctl` 寄信的指令（add／rm／stop／start／sleep／wake）有 `AOS_KERNEL` 時只看自己那封的回信，不查表、不預查、不核 daemon 活不活；只有查表的指令才寄查詢信。
- **K-F43** 讀表時各列路徑一律解成絕對；`fork`、`subagent` 以自己那一列的 `stack` 為基準（不用 `who --json` 的 `daemon` 欄）、不再帶 `--daemon`，`subagents.json` 存絕對路徑（舊帳不認，要重建）。
- **K-F44** `on_clock` 的鐘寫 proc 名時，經既有的 `aos-agent ctl ls --json` 找那列、記鐘檔路徑，之後每拍直接讀鐘檔。
- **K-F45** 判決一律叫 `pass`／`refuse`／`queue`（每個包都一樣；`pass` 在掛 proc 那包是轉寄，在問腦那包是掛去跑）。
- **K-F46** 骨架只有一份 `round()`，五個可換的口：收成品、驗信、排序、放不放、去處；鎖 `requests/.flock` 歸骨架。原判官＝掛 proc 那一包。
- **K-F47** 問腦收進框架的做法：Python 重寫成 `lib/aos/kernel_llm`（專屬那一包＋自己的 `_entry`），刪掉 C++ 的 `impls/aos-llm-kernel`。
- **K-F48** 問腦的 `kernel.json`、stack 裡每個檔的格式、信與回信的形狀、錯誤代號全部不變；現有黑箱測試改指新程式當驗收。
- **K-F49** 「自己跑」做成骨架夾裡的通用零件 `runner.py`（掛 proc、收成品、逾時、重掛一次），不是問腦專用。
- **K-F50** 問腦總機的掛信去處照 `next`（沒寫＝`AOS_DAEMON`），不再看 `AOS_KERNEL`；看問腦 proc 跑完沒的表照 `count_daemon` 同一條規則（見衝突 2）。
- **K-F51** 問腦那一包三個 hook 時機都有，`before_reply` 不用開 `reply_via_me`；帳在 hook 之前記；重掛不重跑判決的 hook；收拾寄件人已走的信不跑 hook。
- **K-F52** 什麼時候認領、`queue.json` 長什麼樣、拒信的形狀歸各包：掛 proc 那包一來就認領、拒信 `{"applied": false, "error"}`；問腦那包掛上才認領、拒信 `{"error"}`，都照現有的。
- **K-F53** 問腦那包的 stderr 前綴從 `aos-llm-kernel:` 變 `kernel_llm:`；公開標頭 `aos/llm_kernel.hpp`（信的格式）搬進 `impls/aos-llm`。
- **K-F54** `aos-llm`（寄信那端）、`llm_forward`、隊 kernel 的做法都不動；11-07 kernel-nest 已裁的行為照搬。
- **K-F55** `LaunchFailed` 的判法先照搬（含讀 daemon 的 `mailbox_warning`）；改成看掛信的回信另議。

## 跟既有原則的衝突

**衝突 1（已裁）：N-42「兩支不併成一支」（使用者 10-16）對上「在這個框架下，我們去擴充更多功能如llm之類」（使用者 11-11）。**
使用者 11-12 裁：「問腦總機要收進框架」。N-42 那句被推翻；條文怎麼改列在 [04](04-問腦併不併.md) 末尾。

**衝突 2：N-63 的「認 `AOS_KERNEL` 的是 aos-llm-kernel 與 aos-agent」，對上代定 K-F50「問腦總機的掛信只看 `kernel.json` 的 `next`」。**
衝突在哪：現在總機只要環境裡有 `AOS_KERNEL`，就把掛問腦 proc 的信寄到那裡；框架的站（它自己就是 kernel）一律只看設定裡的 `next`。問腦收進框架後兩種規矩只能留一種。
各自後果：
- 照代定：總機跟框架站同一個規矩；繼承到給一般 proc 用的 `AOS_KERNEL` 也不會出事（小修線實跑撞過：問腦 proc 的名字被那台的白名單擋掉）。原本靠設 `AOS_KERNEL` 讓掛信過另一站的人，要改成在 `kernel.json` 寫 `next`。N-63 那句要跟著改。
- 照條文：不用改設定；但總機成了唯一一個「身為 kernel 卻看 `AOS_KERNEL`」的例外，上面那個坑照舊要靠「起 llm daemon 的殼別設 `AOS_KERNEL`」這條約定避開。

目前照代定走；要照條文的話說一聲。

（第一版的「衝突 2：數量另指的判法對上不認身份」不成立：`procs_state.json` 是公開窗，不是認身份的問題；真正的理由是猜不準。結論不變，已改寫成 K-F6 的說明。）

## 給使用者的方向題

沒有。問腦要不要收進框架已裁；猜 `./.stack` 已裁（留）。

## Argon 審查與改圖

審查原文見 [07](07-Argon審查.md)，是 Argon 的意見，不是使用者的。

| 編號 | Argon 說什麼 | 採納 | 理由 | 改在哪 |
|---|---|---|---|---|
| A1 | 一輪先代回再防重，重起時會把同一封轉第二次；防重沒比原信名；有序信沒 `reply_to` 不記表 | 採納 | 是真的洞 | 01 一輪的順序、下一站、回信；06 #14；K-F38、K-F39 |
| A2 | `queue_wait_ms: 0` 被當過期誤殺；到期拒信跳過 hook；排著的信每輪重跑 `after_verdict`；建議過期但有格就放行 | 部分採納 | 前三點採（`0` 不算到期本來就是判官現有行為，寫明）；「過期但有格就放行」不採——11-07 已裁過期的不補掛 | 01 一輪的順序、規則；06 #23、#23a；K-F16、K-F40 |
| A3 | 相對路徑的普通字串 aos-directive 不會轉，範例的 handler 會找不到 | 採納 | 對 | 01 設定檔；K-F3 |
| A4 | 換過表之後 `who -j` 的 `daemon` 會是中間站的資料夾，fork／subagent 會放錯地方 | 採納 | 對；改成路徑一律絕對、以自己那列的 `stack` 為基準 | 03 工具、要改的地方 #3、#4；06 #30b；K-F43 |
| A5 | `before_reply` 不知道原寄件人是誰；鏈劇本驗不出刪減 | 採納 | 對；欄名用 `sender`／`reply_sender`，不另造縮寫 `orig_` | 01 回信、hook 表；05 劇本加 `other`；K-F14 |
| A6 | 代回寄不出去無限重試、每輪重跑 hook | 採納 | 錯誤路徑收斂成一條 | 01 回信；06 #4；K-F13 |
| A7 | `before_reply` 退 10 被偷偷當 0；沒寫 `intercept: false`／`async` 與攔下後跑不跑規則 | 採納 | 已裁三個時機都照契約；攔回信改回 `HookRejected` | 01 hook 表；06 #8a；K-F18 |
| A8 | 衝突 2 的理由不準（結論對）；自指檢查漏了沒寫 `next` 的情況 | 採納 | 對 | 01 數量另指、下一站；README 衝突；06 #26；K-F6、K-F7 |
| A9 | 事件裡的 `names` 是 `procs_*` 專用；改判 refuse 沒 `error` 填什麼；改過的 body 不該進公開窗 | 採納 | 對；body 另存 `bodies/` | 01 hook 表、排隊；02；K-F17、K-F41 |
| A10 | 03 自相矛盾（問不到就報錯 vs 只看回信）；`event.json` 會漏原路徑；3 秒在長鏈不夠 | 採納 | 矛盾用 B2 解；另兩點補註 | 03 中間站、工具；06 #30a、#31、#31a |
| A11 | 不併時可在 C++ 總機前串一站就有 hook；猜 `./.stack` 該列給使用者確認 | 部分採納 | 兩點都被使用者的裁定蓋過：問腦已裁收進框架（串一站還會讓寄件人額度失效，記在 06 #46 當已知後果）；`./.stack` 已裁「1.留。」，步驟表不再動 N-63 那條 | 04；05 步 11；06 #46；K-F29 |
| A12 | 步 2 的 `rg` 驗收在文件步之前必敗；步 2、3 切開重工；步 5 並行前提不一致 | 採納 | 對 | 05：合併成一步、`rg` 範圍分兩段、前提寫明 |
| B1 | `on_clock` 記鐘檔路徑，用既有的 `ctl ls --json`，不加子命令 | 採納 | 少一個子命令、`hooks.py` 不用自己會讀表 | 03；K-F32、K-F33 作廢、K-F44 |
| B2 | 寄信的指令有 `AOS_KERNEL` 時只看回信，不另外查表 | 採納 | 合「背後是黑盒子」，手寫 kernel 不答查詢信也能用 | 03 工具；05 步 5；K-F42 |
| B3 | `keep_ordered` 自動開代回，拿掉組合的 `CfgBad` | 部分採納 | 拿掉 `CfgBad`、兩鍵各自照字面；不採「自動開」——預設值跟著另一個鍵變是暗規則 | 01 回信；02；K-F12 作廢、K-F39 |
| B4 | `hook_run.py` 把驗格、排序、`condition`、`event.json`、`on_error` 一起收 | 採納 | 不然同一份契約寫兩次 | 01 資料夾；02；05 步 1、步 3；K-F22 |

## 不在範圍

- 寄信（mailbox）與時鐘算不算資源、要不要過 kernel：使用者沒回，照通則不追問、不設計。
- 沙箱與權限：以 Linux 為保底，不另設計權限系統。
- 「`AOS_KERNEL`、`AOS_DAEMON` 兩個都沒設就報錯」不做；猜 `./.stack` 留著（使用者 11-12 已裁）。

## 分檔目錄

| 分檔 | 內容 |
|---|---|
| [01-框架零件](01-框架零件.md) | 形式、資料夾、骨架與五個口、`kernel.json`、一輪的順序、各零件的行為／錯誤代號／對應判官哪段 |
| [02-判官收編](02-判官收編.md) | 判官功能逐項對零件、改名清單、要重建什麼、遷移步驟、範本與試驗場怎麼跟著改 |
| [03-狀態查詢信](03-狀態查詢信.md) | 信的形狀、daemon 怎麼答、中間站怎麼轉與刪減、工具怎麼先問再讀、小修線 9 處逐處改不改 |
| [04-問腦收進框架](04-問腦併不併.md) | 裁定、怎麼收、資料夾與設定例子、一輪的順序、現有功能逐項對到哪、要改的條文清單 |
| [05-施工步驟](05-施工步驟.md) | 十四步的表（工時、動到的夾、怎麼驗、先後、公司或回家、誰做）、可並行的、整棵鏈劇本 |
| [06-邊緣狀況](06-邊緣狀況.md) | 邊緣狀況與現有原則下的自然答案（含問腦收進後的 12 條） |
| [07-Argon審查](07-Argon審查.md) | Argon 對第一版的審查原文（不是使用者的意見） |
