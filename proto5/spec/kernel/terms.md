← [kernel](README.md)｜[spec 總導航](../README.md)

# 0. 名詞（白話）

跟 cpu 範式共用的詞（家、主人、交件者、request、目標、ack、偷看、link、notification…）在 [cpu.md §0](../cpu/terms.md)，
這裡只列 kernel 自己的，照正文第一次出現的順序排。

| 詞 | 意思 |
|---|---|
| 行程（`procs.<NAME>`） | **不是**作業系統那個行程。在 kernel 這裡是「一份登記好的工作」：記著要跑哪個 target、多久跑一次、跑到哪；真的有東西在跑是派工之後的事 |
| 派工 | 從佇列挑一個輪得到的行程，把它的 `aos-exec` request 放進某顆閒著的 cpu |
| 收回音 | 去 `cpus/<name>/responses/` 讀那則 request 的結果，判定（§4）、更新帳本、再放 ack |
| 反覆行程 | `once: false` 的行程：跑完回佇列，隔 `interval_ms` 再跑一次，直到完成或被退件 |
| `once` | 只跑一次的行程：那次跑完把結果直接交給當初 `add` 的人，行程跟著消失 |
| 長命行程 | 開著就不退、一直待命的程式（daemon、cpu 的主人都是）。kernel **不是**：它每次只活一格的時間，記憶全放在 `K/state.json` 裡 |
| tick（一格） | kernel 的一次心跳：跑一次 `aos-kernel tick --target K --chain C --seq N`，把 §3 那十步做完就退出。「格」就是一次 tick |
| kernel cpu（`kcpu`） | 專門拿來排 tick 的那一顆 exec cpu，boot 時從 `info.cpus` 裡 pool 標 `kernel` 的挑出來、名字釘進帳本；一般工作不准進去。要換得重 boot |
| 池（`pool`） | 給 cpu 貼的一個字串標籤；行程也標一個，只會被派到標籤相同的 cpu 上（例如打模型的工作都排去 `llm` 那顆） |
| 鏈／接鏈 | 一格排下一格、一格接一格串成的那一串 tick。接鏈＝這格開頭就把下一格的 request 放進 kernel cpu 的 `requests/` |
| 尾遞迴 | 借程式的講法：這格**不等**下一格跑完，只把它排上去就自己退出。所以不會越疊越深，也不會兩格同時在跑 |
| syscall | 借作業系統的講法；在這裡只是「往 `K/requests/` 放一個 JSON 檔」（`add`／`rm`／`stop`）。下一格會讀它，需要回音的回在 `K/responses/` |
| 帳本 | `K/state.json`。kernel 所有的記憶：鏈、階段、每顆 cpu 手上的工作、每個行程的紀錄與計數、還沒做完的出貨。一次原子寫 |
| 出貨箱（outbox）／出貨 | 帳本裡四張「還沒做完的待辦」：送 ack（`acks`）、寫回音（`replies`）、送 stop（`stops`）、刪 syscall 原單（`deletes`）。**出貨**＝把這些待辦做掉——前三種是放檔、最後一種是刪檔，每做完一筆才從帳本拿掉。做過又重做是安全的 |
| 鏈 id（`chain`） | boot 發的一串 `<epoch ns>-<pid>`，用來認「你是哪條鏈的格」。**kernel 取的每個檔名都帶它**，所以跨 boot 名字不會重複 |
| 序號（`seq`） | 這格在鏈裡是第幾格，寫在 tick 的 args 裡；下一格就是 seq+1。只拿來取名，不拿來守門 |
| 殘格 | 舊鏈排在隊上、現在才被跑到的 tick。它 args 裡的 chain 對不上帳本的，所以什麼都不做就退出（自滅） |
| 階段（`phase`） | kernel 整體在哪：`running` 照常派工／`stopping` 不再派新的、把在途的收完／`stopped` 連鏈都不接了 |
| 狀態（`status`） | 一個行程現在在哪：`queued` 排隊中／`running` 派出去了／`done` 做完了／`bad` 被退件。後兩種只是留給人看，`rm` 能刪 |
| 佇列（`queue`） | 等著被派上 cpu 的行程名單；已經派出去的不在裡面 |
| `req`／`proc` | `req`＝派給這顆 cpu、還沒結清的 request 檔名（可能已放、也可能剛記還沒放）；`proc`＝那則是哪個行程的。**一顆 cpu 忙不忙只看 `req` 是不是 `null`**，kernel 不去讀 cpu 自己的 state |
| `discard` | 那個行程已經被 `rm` 了，但工作還在 cpu 上跑；回音到了直接丟掉、不計數 |
| 在途 | 已經記了 `req`、還沒收到回音的工作。`stopping` 要等它們全部收完才真的停 |
| boot | 開機：先叫 daemon 把舊的 kernel cpu 收掉、等它從孩子表消失，發一個新鏈 id、拉起所有 cpu、把第 1 格放進 kernel cpu。boot 自己不跑格 |
| 完成／`done_exit` | 反覆行程的退出碼剛好是 `done_exit`（預設 100）＝它自己說「我做完了」，狀態改 `done`、不再排 |
| 退件／`bad_after` | 一直失敗就不再排它，狀態改 `bad` 給人看：連續失敗 `bad_after` 次（預設 10）。kind=aos（檔讀不到、inst 壞掉）也算一次失敗 |
| `tick_ms` | 一格睡多久。跟行程的 `interval_ms`（同一個行程兩次之間隔多久）是兩回事 |
| 冪等 | 同一步做一次跟做兩次結果一樣。崩了重跑才安全——帳本＋出貨箱就是為這個 |
| EEXIST（在這裡） | `link` 到已經存在的名字會失敗。kernel 把它當「已經放過了」的訊號，照樣往下走，不當錯誤 |
| 先放後記 | **只有接鏈**用的順序：**先**把下一格放進 kernel cpu 的 `requests/`、**再**寫帳本。崩在中間下一格照跑，鏈不會斷 |
| 先記後放 | 派工跟四類出貨的順序：**先**寫帳本、**再**動檔。崩在中間最多「記了沒做」、下一格補做，絕不會同一個行程被派到兩顆 cpu |
| `Interrupted` | 「結果不明」的錯誤回音：cpu 的上一任死在那件工作上，下一任補的（範式 §6.2）。反覆行程當一次失敗；`once` 原樣交給交件者 |
| `stopped`（回音裡的） | 這次是被強制停砍掉的：反覆行程計數不動、直接回佇列；`once` 原樣交給交件者 |
| `spawn` | 叫 daemon「把這份 inst 拉起來當孩子」。同名同目標已經活著就回它的 pid、不重拉，所以逾時後重送是安全的 |
| `restart:true` | 拉起來時交代 daemon：這孩子非 0 退出、又沒被主動叫停，就自己再拉一次，kernel 不用管 |

---
