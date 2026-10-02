# daemon 訊息模組與 `aos-mq`：每項一個信箱

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜[控制 B-641](control.md)｜[重讀設定 B-642](reload.md)｜[記住狀態 B-643](state.md)｜[收屍／cgroup B-644](cgroup.md)｜格式：[P-125](../protocol/daemon/mq.md)｜舊設計：[暫緩區 B-614](../deferred/daemon/messaging.md)

本篇只有 B-645，寫訊息模組**做什麼**。socket 上的請求與回應、`aos-mq` 的用法與錯誤代碼，寫在格式篇 [P-125](../protocol/daemon/mq.md)。

依據：[verdicts 11 篇末「2026-10-01 第十二批：cgroup 與帳號」](../../../notes/verdicts/11-tick-as-unit/14-1001-第十二批.md#2026-10-01-第十二批cgroup-與帳號)、[第十四批：aos-mq 取信](../../../notes/verdicts/11-tick-as-unit/16-1001-第十四十五批.md#2026-10-01-第十四批aos-mq-取信)、[第二十二批：廣播與頻道](../../../notes/verdicts/11-tick-as-unit/24-1001-1002-第二十二二十三批.md#2026-10-01-第二十二批廣播與頻道)、[plan m3m 模組四](../../../plan/m3m-daemon-modules/05-模組四-訊息.md#模組四訊息modulesmq)；現行程式 [訊息與 aos-mq](../../../src/py/README.md#訊息與-aos-mqm3m-模組四)（`lib/aos_daemon_mq.py`、`lib/aos_mq.py`，有出入以程式為準）。

## B-645：訊息模組與 `aos-mq`〔使用者 2026-10-01 第十二批〕

**daemon 的每一項一個信箱；任務用 `aos-mq send` 寄信給別項（〔第二十二批〕也能 `--all` 寄給全部、`--channel` 寄給訂了某頻道的項）、用 `aos-mq take` 取自己的信、`aos-mq peek` 只看不取；急件順便叫醒收件那一項。** 它是 daemon 的一個模組（[B-640](core.md)「模組」），設定檔寫了 `modules.mq` 才有。

**收件人是 daemon 的一項**（`insts` 的鍵，逐字比對），不是 node、不是資料夾；inst 是檔也收得到信。

**跨 daemon**〔使用者 2026-10-01 第二十一批：「跨daemon寄信，本質上就是把訊息傳到其他伺服器，就是收件地址加個前綴，就這樣」「所以前綴應該是socket路徑對吧」「1可以，peers先不做，aos-ctl也加--socket。」〕：收件地址＝對方 daemon 的訊息 socket 路徑（前綴）＋對方 `insts` 裡的一項。`aos-mq send --socket <對方訊息 socket> <對方的 inst>` 直接連對方的 socket 寄；寄件方自己的 socket 路徑跟著信走（`from_socket`），收件方回信就照它寄回去。daemon 不轉送、不知道信從哪個 daemon 來，收到跨 daemon 的信跟本地寄的一樣處理，只是多存一個 `from_socket`。

**廣播與頻道**〔使用者 2026-10-01 晚第二十二批：「ab都做，派agent做」「好，如你所建議」〕：

- `aos-mq send --all <JSON>`：寄給這個 daemon（給了 `--socket` 就是那個 daemon）的**每一項**。
- `aos-mq send --channel <頻道> <JSON>`：只寄給**訂了那個頻道的項**。訂閱寫在每項的設定 `"mq": {"subscribe": ["<頻道>", …]}`（沒寫＝不訂）；頻道不用事先宣告，名字逐字比對，沒人訂就是沒人收。
- 兩種都**不寄給寄件人自己**：`from` 等於那一項、而且 `from_socket` 是 null 或就是這個 daemon 的訊息 socket（跨 daemon 來的信，同名的項不算自己）。
- 沒人收也算成功；每個信箱放一份各自的信。急件（`--urgent`）照單寄的規則，收到的項各叫醒一次。
- 每封信多一欄 **`to`**＝寄的時候用的地址：單寄是收件 inst、廣播是 `"*"`、頻道是 `"#<頻道名>"`。收件方用 `take`／`peek --to` 篩。
- 寄的回應多一欄 `delivered`＝放進了幾個信箱（單寄一定是 1）。`aos-mq` 只在 `--all`／`--channel` 成功時把它印到 stdout（一行數字，沒人收是 `0`）；單寄照舊不印（使用者「好，如你所建議」）。

### socket

- daemon 另開一個 unix socket，**不走控制 socket**（使用者 m3n 裁定 5）；兩個模組各開各的、互不依賴。
- 協議照控制模組：一連線一請求、一行 JSON 來、一行 JSON 回（[B-641](control.md)）。能連 socket 就能寄給任何一項、取任何一項的信，不另外檢查權限（照 POC「能連就能做」，第十五批 1.a）。
- 壞請求、對面先關、逾時只影響那一條連線。
- 收到 SIGINT／SIGTERM 退出前刪 socket 檔（同控制模組）。

### 信箱

- **每一項一個信箱，放 daemon 記憶體、先進先出。** daemon 重開就丟，不保證送達。
- 一封信是 `{"from": <寄件 inst 或 null>, "from_socket": <寄件方的訊息 socket 絕對路徑或 null>, "to": <收件 inst、"*" 或 "#<頻道>">, "msg": <任何 JSON 值>}`（`to` 第二十二批加）。daemon 不看 `msg` 是什麼；`from`、`from_socket` 原樣存、不核對（使用者同意 M1：能連 socket 的人本來就能冒充）。`from` 只填寄件方的 inst 名字，不帶 daemon（使用者 2026-10-01 選 a）；要知道是哪個 daemon 寄的、要回信，看 `from_socket`（第二十一批）。
- **只能取自己的信箱**〔使用者 2026-10-01 第十四批：「取信改成只能取自己的信箱。然後可以選擇要取來自誰的，不選就全部。」〕：`aos-mq take` 只用 `AOS_DAEMON_INST`，不收 `<inst>`。原本 M3「誰都可以取任何一項的信」被第十四批推翻。
- **可以只取某些寄件人的**：`--from a c d` 只取 `from` 是這幾個的信，其他照原順序留在信箱；`--from` 後面什麼都不接＝取 `from` 是 `null` 的信；不給 `--from` 就全部取走、信箱清空〔使用者 2026-10-01 第十五批：「1.a,2.可以有aos-mq peek，但手打這塊我們不管。 3.--from可以多個，比如--from a c d...。不管shell手打，from是null的，那就是--from後面不接任何東西。 4.跨daemon寄信不管。」〕。
- **`aos-mq peek`** 跟 `take` 一樣只對自己的信箱、一樣可以帶 `--from`、一樣的輸出，但信不取走（第十五批）。它是給任務用的；人在 shell 手打怎麼看信，aos 不管（使用者：「手打這塊我們不管」）。
- 「只能取／看自己」只在 `aos-mq` 這一側做：**daemon 不驗身分**，直接連 socket 送 `{"take":"<別項>"}` 照樣取得到別項的信。使用者 2026-10-01 第十五批 1.a：照 POC「能連就能做」，daemon 不核對；之後設計各 socket 權限時再說。
- 寄給不在 `insts` 的項：回 `unknown_inst`，信不收。
- 不設上限（每箱幾封、單封多大）、不去重、不確認送達、不重送。

### 急件

寄的時候標 `urgent`：信放進信箱後，**照控制模組 `wake`（不帶選項）的規則叫醒收件那一項**——正在跑就跑完補一次（連寄幾封急件都只補一次）、暫停中跑一次（跑完照樣暫停）、已停不跑（信照樣收下、回成功）。不用掛控制模組也做得到；以後 `wake` 的規則改了，急件跟著改。

### 給任務的環境變數

掛了之後每次開 `aos-exec` 多放：

- `AOS_DAEMON_MQ_SOCKET`：訊息 socket 的絕對路徑。
- `AOS_DAEMON_INST`：這一項的 inst 字面值。**掛了控制或訊息任何一個就放**（使用者同意 M2），兩個都掛也是同一個值。

### `aos-mq`

```text
aos-mq send [--urgent] [--socket <對方訊息 socket>] (<收件 inst> | --all | --channel <頻道>) <JSON|->
aos-mq take [--from [<寄件 inst>…]]… [--to [<收件地址>…]]…
aos-mq peek [--from [<寄件 inst>…]]… [--to [<收件地址>…]]…
```

- socket 從 `AOS_DAEMON_MQ_SOCKET` 拿。`send` 給了 `--socket` 就改連那個 socket（跨 daemon；相對路徑以呼叫者的 cwd 為準），這時沒有 `AOS_DAEMON_MQ_SOCKET` 也能寄。
- `send`：`from` 自動填 `AOS_DAEMON_INST`（沒有就 `null`），`from_socket` 自動填自己的 `AOS_DAEMON_MQ_SOCKET`（轉成絕對路徑；沒有就 `null`）；`<JSON>` 給 `-` 就從 stdin 讀。回信：`aos-mq send --socket <from_socket> <from> …`。`<收件 inst>`、`--all`、`--channel <頻道>` 三選一（第二十二批）；`--all`／`--channel` 成功時 stdout 印一行收到的項數。
- `take`、`peek`：只對 `AOS_DAEMON_INST` 那一項的信箱（沒有就回 1、`no_inst`），不收 `--socket`（自己的信箱只在自己的 daemon；給了回 `usage`）；`--from` 只比 `from`、不看 `from_socket`（AI 隊定，可改）；`take` 取走、`peek` 不取。`--from` 後面接的參數（到下一個 `--` 開頭的參數為止）都是寄件 inst，一個都不接＝寄件人是 `null`；可以重複寫、疊加。〔第二十二批〕`--to` 同 `--from` 的寫法，比的是信的 `to`（收件 inst、`*`、`#<頻道>`）；`to` 不會是 null，所以 `--to` 不接東西什麼都比不到；`--from`、`--to` 都給＝兩個都要符合。每封一行印到 stdout，沒信什麼都不印。
- 成功回 0；其他一律回 1（[C-08](../conventions.md)），stderr 一行代碼與說明。
- 名字照使用者同意 M4：程式叫 `aos-mq`、子命令 `send`／`take`（第十五批加 `peek`）、模組鍵 `mq`。tick 側舊的 `aos-mq get`／`post`（[B-623、B-624](../deferred/mq.md)）是「讀寫 `.aos/mq/` 檔」的系統級任務，意思不一樣，照舊待實作；任務裡要收發信直接叫 `aos-mq send`／`take`，tick 核心不用改。

### 跟其他模組

- **控制模組**（[B-641](control.md)）：各開各的 socket；急件直接動那一項的狀態，不經控制 socket。
- **重讀設定**（[B-642](reload.md)）：每項的 `mq.subscribe` 照新設定（第二十二批）；還在的項信箱照留；拿掉的項連信箱一起丟，之後寄給它回 `unknown_inst`；拿掉又加回來＝新的一項，信箱從空的開始。換 socket 路徑算 `modules` 改了：不套用、警告要重開。
- **記住狀態**（[B-643](state.md)）：信不記。
- **收屍／cgroup**（[B-644](cgroup.md)）：沒關係。

### 先不做

信箱上限、寄件權限、送達確認／去重／重送、訊息格式檢查、tick 側的 `.aos/mq/` 檔案流程。〔第二十二批〕一次廣播到多個 daemon（要就每個 daemon 各 `--socket` 寄一次）、頻道萬用字元、誰能寄／訂哪個頻道的權限、「列出有哪些頻道／誰訂了」的查詢。

~~**不在規劃中**：跨 daemon 送信〔第十五批：「跨daemon寄信不管。」〕~~ 第二十一批改成現行（上面「跨 daemon」）。**peers 模組先不做**：之後可能當「暱稱 → socket 路徑」的對照表（`--peer <名字>` 等於 `--socket <路徑>`），現在任務要寄給別的 daemon 自己知道 socket 路徑就好。舊設計的 node 收件人、`node.send`／`node.take`、通道憑證、寫權授權、急件越過上層節流都在[暫緩區 B-614](../deferred/daemon/messaging.md)。

依據：使用者 2026-10-01 第十二批：訊息要做、排在 cgroup 之後，M1～M4 照建議；第十四批：只能取自己的信箱、`--from`；第十五批：不核對取信的人、`peek`、`--from` 多個與空＝null、跨 daemon 不管；第二十一批：跨 daemon 用 socket 路徑當前綴（`--socket`、`from_socket`），peers 先不做；第二十二批：廣播 `--all`、頻道 `--channel`＋`mq.subscribe`、信的 `to` 與 `--to`、`delivered`。

**驗收：**兩項 a、b；a 的任務 `aos-mq send b '{"hi":1}'` 回 0，b 的任務 `aos-mq take` 印出 `{"from":"a","from_socket":"<同一個 daemon 的訊息 socket>","msg":{"hi":1}}`，再取一次什麼都不印；先寄的先取到；`take` 給 `<inst>` 回 1、`usage:`；a、c、d、手打（null）各寄給 b，b `take --from a c` 只拿到 a、c 的、其他照順序留著，`take --from` 只拿到 null 的，`--from --from d` 疊加；`peek` 看得到、再 `take` 照樣取到；`take`／`peek` 帶 `--urgent` 回 1、`usage:`；`--urgent` 寄給週期 1 小時的 b：b 一秒內跑一次，普通信不叫醒；b 正在跑時連寄三封急件：只補跑一次、三封一次取到；急件寄給已停的項不跑、信照收；暫停的項跑一次、照樣暫停；寄給不存在的項：回 1、`unknown_inst:`；沒有 `AOS_DAEMON_MQ_SOCKET`：回 1、`no_daemon:`；壞請求只影響那一條連線；daemon 重開後信箱是空的；重讀設定時還在的項信照留、拿掉的項寄信回 `unknown_inst`、加回來信箱是空的；兩個 daemon A、B：A 的任務 `aos-mq send --socket <B 的訊息 socket> b …` 回 0，B 的 b 取到的信 `from_socket` 是 A 的訊息 socket 絕對路徑，照它 `send --socket` 回信，A 那邊取得到；`--socket` 連不上回 1、`connect:`；`take`／`peek` 給 `--socket` 回 1、`usage:`；〔第二十二批〕三項 a、b、c：a `send --all` 印 `2`、b、c 各收到 `to:"*"` 的信、a 沒收到；沒有 `AOS_DAEMON_INST` 時 `--all` 三項都收到；跨 daemon 來的 `--all` 同名的項照收；a、b 訂 `deploy`：c `--channel deploy` 印 `2`、a `--channel deploy` 只到 b、`--channel nobody` 回 0 印 `0`；`--all --urgent` 每個收件項各補跑一次；重讀改了 `subscribe` 照新的寄；`peek --to '*'`、`--to '#deploy' b.json`、`--to` 不接（空）、`--to` 配 `--from`；`<收件 inst>`／`--all`／`--channel` 給兩個或都不給、`--channel` 沒接名字或給兩次、`take`／`peek` 帶 `--all`／`--channel`：回 1、`usage:`；掛了模組時 `mq.subscribe` 格式不對：回 1；沒掛模組：每項的 `mq` 忽略、原有測試全過。測試見 `proto6/src/py/tests/test_mq.py`。
