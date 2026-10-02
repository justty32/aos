← [daemon 訊息模組與 `aos-mq`：每項一個信箱](../mq.md)（分檔 2/2）｜所在段落：B-645：訊息模組與 `aos-mq`〔使用者 2026-10-01 第十二批〕｜[上一份](01-B-645-信箱與socket.md)

### `aos-mq`

```text
aos-mq send [--urgent] [--socket <對方訊息 socket>] (<收件 inst> | --all | --channel <頻道>) <JSON|->
aos-mq take [--from [<寄件 inst>…]]… [--to [<收件地址>…]]…
aos-mq peek [--from [<寄件 inst>…]]… [--to [<收件地址>…]]…
```

- socket 從 `AOS_DAEMON_MQ_SOCKET` 拿。`send` 給了 `--socket` 就改連那個 socket（跨 daemon；相對路徑以呼叫者的 cwd 為準），這時沒有 `AOS_DAEMON_MQ_SOCKET` 也能寄。
- `send`：`from` 自動填 `AOS_DAEMON_INST`（沒有就 `null`），`from_socket` 自動填自己的 `AOS_DAEMON_MQ_SOCKET`（轉成絕對路徑；沒有就 `null`）；`<JSON>` 給 `-` 就從 stdin 讀。回信：`aos-mq send --socket <from_socket> <from> …`。`<收件 inst>`、`--all`、`--channel <頻道>` 三選一（第二十二批）；`--all`／`--channel` 成功時 stdout 印一行收到的項數。
- `take`、`peek`：只對 `AOS_DAEMON_INST` 那一項的信箱（沒有就回 1、`no_inst`），不收 `--socket`（自己的信箱只在自己的 daemon；給了回 `usage`）；`--from` 只比 `from`、不看 `from_socket`（AI 隊定，可改）；`take` 取走、`peek` 不取。`--from` 後面接的參數（到下一個 `--` 開頭的參數為止）都是寄件 inst，一個都不接＝寄件人是 `null`；可以重複寫、疊加。〔第二十二批〕`--to` 同 `--from` 的寫法，比的是信的 `to`（收件 inst、`*`、`#<頻道>`）；`to` 不會是 null，所以 `--to` 不接東西什麼都比不到；`--from`、`--to` 都給＝兩個都要符合。每封一行印到 stdout，沒信什麼都不印。
- 成功回 0；其他一律回 1（[C-08](../../conventions.md)），stderr 一行代碼與說明。
- 名字照使用者同意 M4：程式叫 `aos-mq`、子命令 `send`／`take`（第十五批加 `peek`）、模組鍵 `mq`。tick 側舊的 `aos-mq get`／`post`（[B-623、B-624](../../deferred/mq.md)）是「讀寫 `.aos/mq/` 檔」的系統級任務，意思不一樣，照舊待實作；任務裡要收發信直接叫 `aos-mq send`／`take`，tick 核心不用改。

### 跟其他模組

- **控制模組**（[B-641](../control.md)）：各開各的 socket；急件直接動那一項的狀態，不經控制 socket。
- **重讀設定**（[B-642](../reload.md)）：每項的 `mq.subscribe` 照新設定（第二十二批）；還在的項信箱照留；拿掉的項連信箱一起丟，之後寄給它回 `unknown_inst`；拿掉又加回來＝新的一項，信箱從空的開始。換 socket 路徑算 `modules` 改了：不套用、警告要重開。
- **記住狀態**（[B-643](../state.md)）：信不記。
- **收屍／cgroup**（[B-644](../cgroup.md)）：沒關係。

### 先不做

信箱上限、寄件權限、送達確認／去重／重送、訊息格式檢查、tick 側的 `.aos/mq/` 檔案流程。〔第二十二批〕一次廣播到多個 daemon（要就每個 daemon 各 `--socket` 寄一次）、頻道萬用字元、誰能寄／訂哪個頻道的權限、「列出有哪些頻道／誰訂了」的查詢。

~~**不在規劃中**：跨 daemon 送信〔第十五批：「跨daemon寄信不管。」〕~~ 第二十一批改成現行（上面「跨 daemon」）。**peers 模組先不做**：之後可能當「暱稱 → socket 路徑」的對照表（`--peer <名字>` 等於 `--socket <路徑>`），現在任務要寄給別的 daemon 自己知道 socket 路徑就好。舊設計的 node 收件人、`node.send`／`node.take`、通道憑證、寫權授權、急件越過上層節流都在[暫緩區 B-614](../../deferred/daemon/messaging.md)。

依據：使用者 2026-10-01 第十二批：訊息要做、排在 cgroup 之後，M1～M4 照建議；第十四批：只能取自己的信箱、`--from`；第十五批：不核對取信的人、`peek`、`--from` 多個與空＝null、跨 daemon 不管；第二十一批：跨 daemon 用 socket 路徑當前綴（`--socket`、`from_socket`），peers 先不做；第二十二批：廣播 `--all`、頻道 `--channel`＋`mq.subscribe`、信的 `to` 與 `--to`、`delivered`。

**驗收：**兩項 a、b；a 的任務 `aos-mq send b '{"hi":1}'` 回 0，b 的任務 `aos-mq take` 印出 `{"from":"a","from_socket":"<同一個 daemon 的訊息 socket>","msg":{"hi":1}}`，再取一次什麼都不印；先寄的先取到；`take` 給 `<inst>` 回 1、`usage:`；a、c、d、手打（null）各寄給 b，b `take --from a c` 只拿到 a、c 的、其他照順序留著，`take --from` 只拿到 null 的，`--from --from d` 疊加；`peek` 看得到、再 `take` 照樣取到；`take`／`peek` 帶 `--urgent` 回 1、`usage:`；`--urgent` 寄給週期 1 小時的 b：b 一秒內跑一次，普通信不叫醒；b 正在跑時連寄三封急件：只補跑一次、三封一次取到；急件寄給已停的項不跑、信照收；暫停的項跑一次、照樣暫停；寄給不存在的項：回 1、`unknown_inst:`；沒有 `AOS_DAEMON_MQ_SOCKET`：回 1、`no_daemon:`；壞請求只影響那一條連線；daemon 重開後信箱是空的；重讀設定時還在的項信照留、拿掉的項寄信回 `unknown_inst`、加回來信箱是空的；兩個 daemon A、B：A 的任務 `aos-mq send --socket <B 的訊息 socket> b …` 回 0，B 的 b 取到的信 `from_socket` 是 A 的訊息 socket 絕對路徑，照它 `send --socket` 回信，A 那邊取得到；`--socket` 連不上回 1、`connect:`；`take`／`peek` 給 `--socket` 回 1、`usage:`；〔第二十二批〕三項 a、b、c：a `send --all` 印 `2`、b、c 各收到 `to:"*"` 的信、a 沒收到；沒有 `AOS_DAEMON_INST` 時 `--all` 三項都收到；跨 daemon 來的 `--all` 同名的項照收；a、b 訂 `deploy`：c `--channel deploy` 印 `2`、a `--channel deploy` 只到 b、`--channel nobody` 回 0 印 `0`；`--all --urgent` 每個收件項各補跑一次；重讀改了 `subscribe` 照新的寄；`peek --to '*'`、`--to '#deploy' b.json`、`--to` 不接（空）、`--to` 配 `--from`；`<收件 inst>`／`--all`／`--channel` 給兩個或都不給、`--channel` 沒接名字或給兩次、`take`／`peek` 帶 `--all`／`--channel`：回 1、`usage:`；掛了模組時 `mq.subscribe` 格式不對：回 1；沒掛模組：每項的 `mq` 忽略、原有測試全過。測試見 `proto6/src/py/tests/test_mq.py`。
