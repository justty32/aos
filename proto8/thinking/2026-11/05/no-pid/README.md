# 2026-11-05 晚 不靠 pid 找東西：daemon 是 Linux 行程與 aos 之間唯一的橋、寄信不回＝呼叫失敗、監管樹（no-pid；使用者方向＋fable 規劃；11-06 P1～P4、P5b 已做）

← [thinking README](../../../README.md)｜日 [2026-11-05](../README.md)｜相關：[arch-refactor](../arch-refactor/README.md)（S6 照本夾 P3 做、S7／S8 排在 P1～P2 之後，見 [07](07-實作步驟.md)）、[small-thought § 第二輪](../small-thought/README.md#11-05-夜-第二輪邊緣)（沙箱誤判那題本夾解）、[kernel-daemon 08](../kernel-daemon/08-實作結果.md)（llm kernel 看問腦 proc 不碰 pid＝現成範例）、[edge-daemon](../edge-daemon/README.md)（DaemonRunning 改 flock）

隊長 11-05 晚先記使用者原話與粗盤點；之後兩個 opus 盤點員實查 Python 與 C++ 側、fable 寫規劃本體（01～07）。原話逐字照留在下；隊長那張粗盤點表併進 [01](01-盤點-py.md)。

## 使用者原文（11-05 晚，逐字）

> hmmm，其實我一直覺得，靠着pid來找東西，不太符合我們aos體系的概念。除去daemon本身與linux原生proc有所接觸，可能會透過pid來強行控制一些東西，或是弄一些linux原生的特殊機制外，其他人若有相關需求，最好都是透過daemon進行轉接。至於如何找到daemon，大多時候是透過環境變數。對了，tool那塊我突然想到，--env後面接啥？你要是跟我說接一堆xxx=yyy，那很醜，建議是限制只能接.env，除此之外也建議，工具在設計之初，最好是要考慮到環境變數可能會脫鉤這件事。

> 1.糟糕，看來這個得重構了。具體等明天吧，今天距離睡覺不到三小時，就都先聊一聊，做規劃就好。2.hmmm，其實在一些需求不大的場景，稍微覆蓋一兩個環境變數也是可以，或者改成--env-file xxx搭配--envs K=V...也不錯，兩者並存吧。

> 1.aos體系脫胎於plan9，也就是純粹的unix哲學。還記得state.json嗎？我會希望以這個爲主。寄信收信是我們aos的非同步呼叫的底層機制，寄信不回，等同於呼叫失敗，想想看，假如你平常打API呼叫某個saas服務，他沒回代表啥？有可能他在忙，有可能你的要求他不認得，也可能他掛了。詢問daemon也是一個正統管道。記住，所有牽涉到linux原生行程的機制，都以daemon爲界面，而daemon所擔任的，就是橋梁，並且盡量將各類東西暴露爲檔案。2.……我原本想說daemon不可以掛，使用者有義務讓daemon成爲最早開始執行，最晚結束的linux行程，並且他必須正常運行。後來想想，我們一大堆daemon在跑，總會有幾個daemon可能卡住，或是crash，那怎麼辦...你有啥好想法嗎。3.理想狀態是完全脫鉤，但作爲aos體系下的工具，他仍是aos函數，只要是aos函數，我們都默認他能吃aos-exec所提供的那幾個環境變數。另一方面，只靠環境變數找DAEMON，只是因爲這最方便，誰也限制不了你透過其他方式傳遞daemon位置。4.（對「所有控制都經 daemon，daemon 就成了權限閘門，判官以後也能管誰能停誰、沙箱裡的東西只要一個信箱就夠」）是的，你真聰明！

> （頂層提監管樹、state.json 分 phase 與最近反應時間、只有上層動 pid、下層靠 stack 續跑後）2.你的想法很好，我也是這麼想的！，剩下都沒問題！

> 關於root daemon，我覺得不用限制他一定要怎樣怎樣，他就是一個普通daemon，只是說因爲他頭上沒daemon了，所以使用者要保証他能正常運行。硬要說的話，以後搞不好會是弄一個linux user，然後這個linux user有一個root daemon，掛在沙盒下，並且可以透過一些手段進行使用者切換(可能搭配一隻有root權限的小程式)。大概是這樣。但也可以就只是一個普通的linux user proc，壞了就壞了。

> （已被下一句取代）其實也不用不同賬號，應該說，更往後的是我希望一個daemon就有一個賬號，然後以此去做相關linux權限設置。

> 喔不是，應該說一個agent一個賬號。

## 定下的（11-05 晚）

1. **只有 daemon 碰 pid**：fork、waitpid、kill、`/proc`、flock 防重起——daemon 本身的全留；**其他人**要找東西、判死活、控制，一律經 daemon：讀它寫的檔（`state.json`、`procs_state.json`）、往它的 ctl 信箱寄信。daemon 是橋，**盡量把東西暴露為檔案**。
2. **寄信不回＝呼叫失敗**：呼叫者只管寄信、等回信，逾時就當失敗，不去分是忙、不認得還是掛了；想知道原因，讀對方**上一層 daemon** 的 `procs_state.json`。
3. **state.json 分 `phase` 和「最近一次有反應的時間」**（`responded_at`，欄名代定）；**只在應該要有反應時才判**（ctl 信箱有信放超過 N 秒沒人收、ctl 有新指令沒採用）→ `stuck`。睡著的不會被誤判、睡著時檔案照樣不動。
   - **11-06 晚改讀**：括號裡「ctl 信箱有信放超過 N 秒沒人收」那一半作廢，只剩「ctl 有新指令沒採用」；使用者 11-06 晚：「子daemon管好自己，父daemon只看他有沒有活着，子daemon的其他東西父daemon別碰。盡量解耦合。」（[17](17-P7實作結果.md#使用者裁定11-06-晚家機)）
4. **監管樹**：每台 daemon 都是某台 daemon 底下的 proc；問誰的死活問它的上一層；使用者只顧**根 daemon**。crash＝上一層 waitpid 到、照表重起，孩子從 stack 續跑；卡住＝預設只標 `stuck` 等人處理，列上 `restart_on_stuck: true` 才自動殺掉重起。**只有上一層動 pid。**
   - **根 daemon 不做特殊規定**：就是普通 daemon，只是頭上沒人，由使用者保證它正常跑（自己交 systemd／s6，或就是普通使用者行程、壞了就壞了）。**以後**：**一個 agent 一個 Linux 帳號**、用它設 Linux 權限（使用者 11-05 晚「喔不是，應該說一個agent一個賬號。」，取代前一句的「一個daemon就有一個賬號」）；根掛在沙箱下、用一支有 root 權限的小程式切換帳號（跟 sandbox 的 `s6-setuidgid` 同一條線）；這次不做。
5. **環境變數是預設管道、不是唯一**：aos 函數默認吃得到 aos-exec 的六個；找 daemon `--daemon` ＞ `AOS_DAEMON` ＞ `./.stack`，別的傳法也可以；脫鉤是「沒給」不是「不准用別的方法給」；沒給＝`<名字>Missing`，不掃 `/proc` 猜。
6. **`--env-file FILE` 與 `--envs K=V`（可重複）並存**（補充 2 取代原文「限制只能接 .env」）：aos-tools 今晚加的 `--env K=V` 改成這兩個；`aos-agent tools add` 同形、值不給腦看；這就是「脫鉤的解藥」（[03 § 3](03-找daemon與脫鉤.md)）。
7. **遠期**：判官從「能不能掛」長成「誰能對誰做什麼」；daemon 成了權限閘門，沙箱裡的東西只要一個信箱就夠。

## 一句話結論（規劃）

盤點後**真正要改的只有 Python 側十來處（ctl 3、aos-agent 8、thought 3、eca-screen 1）加 C++ 一處（aos-llm `warn_idle`）**，其餘都是 daemon 本身、Linux 原生鎖、或 tmp 檔名／信名的唯一化，全留。改法：daemon 多暴露兩欄（`responded_at`、`daemon` 上一層）＋認一封 `ping`；Python 收成一個 ctl 模組三個口（`find_daemon`／`state`／`ask`），所有人 import 它、不碰 `/proc`；thought 子名改唯一就不用搶；回信信箱改共用＋`in_reply_to`；沙箱只要綁 daemon stack 就通。監管樹是第二波：daemon 加第三種 proc 寫法 `{"daemon": …}`、每拍對刺激與 `responded_at` 判 `stuck`、照表重起。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-盤點-py](01-盤點-py.md)、[01-盤點-cpp](01-盤點-cpp.md) | 逐處表（檔:行、為什麼要 pid、類別、留／改）；沙箱誤判根因（pid namespace，卡在 aos-agent `need_daemon`） |
| [02-轉接設計](02-轉接設計.md) | state.json 兩欄、ping、回信信箱、ctl 模組三個口、每個呼叫者改成什麼樣 |
| [03-找daemon與脫鉤](03-找daemon與脫鉤.md) | 找 daemon 規則、脫鉤時各變數的失敗樣子、`--env-file`／`--envs`、要寫進 lib 規則與 N-17／N-63 的句子 |
| [04-沙箱](04-沙箱.md) | 解掉哪些題、sandbox.json 要綁什麼、剩什麼自擔 |
| [05-監管樹](05-監管樹.md) | daemon 型 proc、stuck 判法、`restart_on_stuck`、根 daemon 交系統 |
| [06-衝突與邊緣](06-衝突與邊緣.md) | 跟 N-17／N-32／C-52／N-28／N-63／N-10 的關係、邊緣狀況三組 |
| [07-實作步驟](07-實作步驟.md) | P1～P9、跟大重構 S6／S7／S8／S10 怎麼合、派誰、驗收 |
| [08-P1實作結果](08-P1實作結果.md) | 11-06 P1 做了什麼、代定 4 條、修前重現與修後實測、新發現的邊緣 3 條 |
| [10-P3實作結果](10-P3實作結果.md) | 11-06 P3（＝大重構 S6：`py/daemon_ctl.py`、aos-daemon-ctl 薄殼與 `ping`、aos-agent 不碰 pid、共用回信信箱）做了什麼、代定 11 條、實測、新發現的邊緣 6 條、P5b 要跟著改的 |
| [11-P4實作結果](11-P4實作結果.md) | 11-06 P4（thought 子名唯一＋租約、四格對帳、`_tooldef.json` 的 `env`、lib 規則 11、knowledge 的 `DaemonMissing` 兩種意思）做了什麼、代定 10 條、真腦與假腦實測、新發現的邊緣 6 條 |
| [12-P5b條文結果](12-P5b條文結果.md) | 11-06 P5b 條文加註結果、代定、會動到使用者概念的清單、留著沒處理的 |
| [13-P5實作結果](13-P5實作結果.md) | 11-06 P5 非 C++ 半（沙箱範例 `thought-boxed` 模式 1／2、aos-sandbox README）做了什麼、代定、假腦實測、張力判斷、新發現的邊緣 |
| [14-P6實作結果](14-P6實作結果.md) | 11-06 P6 daemon 型 proc `{"daemon": X}`（整樹睡醒、退了照表重起、連 3 次快速失敗留 stopped）做了什麼、代定、三層實測、新發現的邊緣（已被 15 取代） |
| [15-P6去耦合](15-P6去耦合.md) | 11-06 使用者「不要耦合」後：子 daemon＝普通 proc、通用布林 `auto_restart`（選項框裁、名字來由）、監管樹改讀、P7 要重設計 |
| [16-P7重設計](16-P7重設計.md) | 11-06 只看公開 ctl／state 窗判 stuck、兩鐘期限、重起上限與代定 |
| [17-P7實作結果](17-P7實作結果.md) | 11-06 P7 做了什麼、可翻案代定、九案驗證與新邊緣 |
| [18-P8實作結果](18-P8實作結果.md) | 11-06 晚家機 P8：根 daemon 選用監管範例、三層試驗場、搬家食譜與 os-impl A4／A5／A9／A13／A20／B2；實跑範圍與未覆蓋項 |
| [19-P9邊緣實測](19-P9邊緣實測.md) | 11-06 晚家機 P9：06 全清單、B3 五條、git clone 第三處、10 分鐘 tick、長身體與孤兒；36 列數字及兩個 C++ bug |
| [09-P2實作結果](09-P2實作結果.md) | 11-06 P2（`responded_at`、`daemon` 欄、ping）做了什麼、代定 5 條、驗收實測、新發現的邊緣 5 條、P5b 要跟著改的條文 |

## 要使用者裁的（白話；推薦放第一）——只剩真正沒定的

1. **（11-05 晚 21:40 使用者：「aos-lock就改檔案鎖。」→ 照推薦：flock 檔、pid 三欄拿掉、`acquire --pid N` 刪）** **aos-lock 的名牌（持鎖人的 pid＋ticks＋boot_id，拿不到鎖時對 /proc 判他死了沒）要不要也去 pid？** 它是基礎層的鎖、只有 aos-post `send --ordered` 在用，不是 daemon。
   - **改成名牌旁放一個 flock 檔（學 llm-kernel 的 `sender.flock`）、持鎖期間鎖著、試鎖得到＝主人死了；pid 三欄拿掉 (Recommended)**：跟「牽涉 Linux 行程的機制都以 daemon 為界面」一致，沙箱裡也對；代價：aos-lock 改一輪、`acquire --pid N` 刪。
   - 留著：它算「Linux 原生特殊機制」那一類；代價：沙箱內外同時用有序信箱時會把外面活著的持鎖人當死的。

## fable 代定（可翻案；細節在各分檔）

1. 欄名 `responded_at`、`daemon`；stuck 門檻 N＝10 秒寫死；ping 時限 3 秒、add 等上表 30 秒（既有）。
2. ping 的 `body` 用 `{"ping": true}`、回信沿用 `{"applied": true}`；paused 的 daemon 不回（它在忙，呼叫失敗正確）。
3. 回信信箱 `$AOS_STACK/daemon_reply/`（人殼無 stack＝`$AOS_DAEMON/procs_ctl_mailbox/reply/`）；沒人領的回信 10 分鐘後由下一個讀的人收掉。
4. thought 子名 `<UTC 奈秒>.<4 位亂數>`；`_tooldef.json` 加選填 `env`（變數名陣列）。
5. 子 daemon 用第三種 proc 寫法 `{"daemon": …}`；退了照表重起、連 3 次失敗留 `stopped`；`restart_on_stuck` 連環同上限。
6. `ls`／`listen` 讀檔不寄信；`ctl` 的 pause／resume 照 N-10 直接寫子 ctl 不改。
7. 不加新錯誤代號（`DaemonMissing` 沿用）；aos-llm `warn_idle` 只印「沒回」不下判斷。
8. 第一波（P1～P5b）去 pid、第二波（P6～P9）監管樹；S6＝P3；P1、P2 排在 S7 之前。

## 排程

- 11-05 晚只規劃、不改程式（補充 1）。S6 等本夾定案（已定）後照 P3 做；S0～S5 照 arch-refactor 原計畫。
- 11-06：`--env-file`／`--envs` 改（aos-tools、aos-agent tools add）；P1→P2→P3（＝S6）→P4（已做）→P5／P5b；S7、S8 之後 P6～P9。
