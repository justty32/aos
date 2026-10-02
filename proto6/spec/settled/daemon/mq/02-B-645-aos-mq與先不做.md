← [daemon 訊息模組與 `aos-mq`：每項一個信箱](../mq.md)（分檔 2/2）｜所在段落：B-645：訊息模組與 `aos-mq`〔使用者 2026-10-01 第十二批；2026-10-02 第二十五批改成多扇門〕｜[上一份](01-B-645-信箱與socket.md)

### `aos-mq`

```text
aos-mq send <socket 路徑> <JSON|->
aos-mq take <socket 路徑>
aos-mq peek <socket 路徑>
```

- 〔第二十五批：「aos-mq take <socket...>，然後不允許指定後面的inst，一律吃環境變數」「aos-mq peek可以保留」〕三個子命令都要明寫門的路徑；任務裡通常寫 `"$AOS_DAEMON_MQ_SOCKET_1"` 這種環境變數。相對路徑以呼叫者的 cwd 為準。
- `send`：把 `<JSON>` 原樣當一封信從那扇門寄進去；給 `-` 就從 stdin 讀。不需要任何環境變數（跨 daemon 就寫對方的門）。成功什麼都不印（AI 隊定：不再印收到項數）。
- `take`、`peek`：取／看 `AOS_DAEMON_INST` 那一項全部的信（沒有就回 1、`no_inst`），不收 inst 參數；門寫這個 daemon 的哪一扇都行。每封一行印到 stdout（就是當初寄的 JSON），先寄的在前，沒信什麼都不印。`take` 取走、`peek` 不取；`peek` 是給任務用的，人在 shell 手打怎麼看信 aos 不管（第十五批）。
- 拿掉：`--urgent`、`--socket`、`--all`、`--channel`、`--from`、`--to`、`<收件 inst>`；任何 `--` 開頭的旗標都回 `usage`。
- 成功回 0；其他一律回 1（[C-08](../../conventions.md)），stderr 一行代碼與說明。
- 名字照使用者同意 M4：程式叫 `aos-mq`、子命令 `send`／`take`（第十五批加 `peek`）、模組鍵 `mq`。tick 側舊的 `aos-mq get`／`post`（[B-623、B-624](../../deferred/mq.md)）是「讀寫 `.aos/mq/` 檔」的系統級任務，意思不一樣，照舊待實作；任務裡要收發信直接叫 `aos-mq send`／`take`，tick 核心不用改。

### 跟其他模組

- **控制模組**（[B-641](../control.md)）：各開各的 socket；寄件叫醒直接動那一項的狀態，不經控制 socket。socket 權限照同一個原則（[上一份「socket 與檔案權限」](01-B-645-信箱與socket.md#socket-權限)）。
- **重讀設定**（[B-642](../reload.md)）：每一項的 `mq` 照新設定，但照**開起來時的門**核——寫了開起來時沒有的門＝重讀出錯、整份不套用（AI 隊定：`modules.mq` 改了本來就不套用，跟帳號模組照開起來時的名單核一樣）；`modules.mq` 改了（加門、拿門、換路徑）不套用、警告要重開。還在的項信箱照留；拿掉的項連信箱一起丟，之後取它的信回 `unknown_inst`；拿掉又加回來＝新的一項，信箱從空的開始。
- **記住狀態**（[B-643](../state.md)）：信不記。
- **收屍／cgroup**（[B-644](../cgroup.md)）：沒關係。
- **帳號**（[B-646](../account.md)）：socket 一律 666，誰連得到看資料夾，不再跟帳號模組綁。

### 先不做

信箱上限、送達確認／去重／重送、訊息格式檢查、tick 側的 `.aos/mq/` 檔案流程；daemon 側的寄件權限或身分核對（權限只靠資料夾）；「列出有哪些門／誰訂了」的查詢；一次寄到多扇門或多個 daemon（要就各寄一次）。**peers 模組先不做**（第二十一批）：要寄給別的 daemon，自己知道對方門的路徑就好。舊設計的 node 收件人、`node.send`／`node.take`、通道憑證、寫權授權、急件越過上層節流都在[暫緩區 B-614](../../deferred/daemon/messaging.md)。

依據：使用者 2026-10-01 第十二批：訊息要做、排在 cgroup 之後，M1～M4 照建議；第十四、十五批：只能取自己的信箱（`aos-mq` 那一側）、daemon 不核對、`peek`；第二十一批：跨 daemon 寄到對方的 socket、peers 先不做；**2026-10-02 第二十五批**：多扇門、每項訂門、信原樣、合併叫醒、`aos-mq <子命令> <socket 路徑>`、socket 一律 666 靠資料夾管權限——取代第十二批的單一 socket 與收件 inst、第十四／十五批的 `--from`、第二十一批的 `--socket`／`from_socket`、第二十二批的廣播與頻道、`--urgent`（[裁定紀錄](../../../../notes/verdicts/11-tick-as-unit/26-1002-第二十五批.md#2026-10-02-第二十五批訊息多扇門)）。

**驗收：**兩扇門 `D1`、`D2`，a 訂 `D1`、b 訂 `D1`＋`D2`、c 不訂：每項環境都有 `AOS_DAEMON_MQ_D1`、`AOS_DAEMON_MQ_D2`（絕對路徑）、`AOS_DAEMON_INST`，沒有 `AOS_DAEMON_MQ_SOCKET`；c 的任務 `aos-mq send "$AOS_DAEMON_MQ_D1" '{"hi":1}'` 回 0、不印東西，a、b 各收到一封 `{"hi":1}`（原樣、沒有多的欄位），c 沒收到；寄 `D2` 只有 b 收到；a 寄 `D1` 自己也收到；先寄的先取到；`take` 連 `D2`（b 沒寄過的門）也取得到 b 全部的信，再取一次什麼都不印；`peek` 看得到、再 `take` 照樣取到；週期 1 小時的 b：寄一封一秒內跑一次；b 正在跑時連寄三封：只補跑一次、三封一次取到；開跑前連寄幾封只跑一次；寄給已停的項不跑、信照收；暫停的項跑一次、照樣暫停；沒人訂的門寄得進、回 0；`take`／`peek` 沒有 `AOS_DAEMON_INST` 回 1、`no_inst:`；多給參數、少給路徑、`--urgent` 等任何旗標、`<JSON>` 不是 JSON：回 1、`usage:`；路徑連不上回 1、`connect:`；直接連門送 `{"take":"<別項>"}` 照樣取得到；壞請求只影響那一條連線；daemon 重開後信箱是空的；兩個 daemon：A 的任務寄到 B 的門，B 訂了那扇門的項收到；控制 socket 與每扇門的 socket 檔都是 666（沒掛帳號模組也是）；`modules.mq` 不是物件、空物件、門名有 `-`、值不是字串、兩扇門同路徑、跟控制 socket 同路徑、項的 `mq` 不是陣列或寫了沒有的門：回 1；重讀設定時改了某項的 `mq` 照新的收、寫了沒有的門整份不套用、改了 `modules.mq` 印 `reload: need restart: modules`、還在的項信照留、拿掉的項取信回 `unknown_inst`、加回來信箱是空的；沒掛模組：每項的 `mq` 忽略、原有測試全過。測試見 `proto6/src/py/tests/test_mq_send.py`、`test_mq_doors.py`。
