← [kernel](README.md)｜[spec 總導航](../README.md)

# 0. 名詞（白話）

跟 cpu 範式共用的詞（家、主人、交件者、request、目標、ack、偷看、link、notification…）在 [cpu.md §0](../cpu/terms.md)，
這裡只列 kernel 自己的，照正文第一次出現的順序排。（2026-09-24 proto5-2 池式納入：池、編號、宣告、巡檢、通知、`busy` 等改寫或新增。）

| 詞 | 意思 |
|---|---|
| 行程（`procs.<NAME>`） | **不是**作業系統那個行程。在 kernel 這裡是「一份登記好的工作」：記著要跑哪個 target、多久跑一次、跑到哪；真的有東西在跑是派工之後的事 |
| 派工 | 從池的排隊格挑一個輪得到的行程，把它的 `aos-exec` request 放進那池一顆閒著的 cpu（閒號從 `free` 拿） |
| 收回音 | 去 `pools/<P>/cpus/<i>/responses/` 讀那則 request 的結果，判定（§4）、更新帳本、再放 ack |
| 反覆行程 | `once: false` 的行程：跑完回佇列，隔 `interval_ms` 再跑一次，直到完成或被退件 |
| `once` | 只跑一次的行程：那次跑完把結果直接交給當初 `add` 的人，行程跟著消失 |
| 長命行程 | 開著就不退、一直待命的程式（daemon、cpu 的主人都是）。kernel **不是**：它每次只活一格的時間，記憶全放在 `K/state.json` 裡 |
| tick（一格） | kernel 的一次心跳：跑一次 `aos-kernel tick --target K --chain C --seq N`，把 §3 那十步做完就退出。「格」就是一次 tick |
| kernel cpu（`kcpu`） | 專門拿來排 tick 的那一顆 exec cpu：`kernel` 池的 0 號（`kernel/0`，家在 `K/pools/kernel/cpus/0/`）；一般工作不准進去。kernel 池的設定要重 boot 才換 |
| 池（`pool`） | 一群一模一樣的 cpu（同一份環境），在 info 的 `pools` 裡寫「要幾顆」；行程也標一個池名，只會被派到那池的 cpu 上（例如打模型的工作都排去 `llm` 池）。kernel 池以外的叫**工作池** |
| 成員編號、`P/<i>` | 池裡的 cpu 不取名，用號碼：不在 `skip` 裡的最小 `count` 個非負整數。全名 `P/<i>` |
| 宣告、scale 單 | kernel 告訴 daemon「池 P 要這幾號」的一張單；daemon 自己補、重拉、收（§3.1、§5） |
| 巡檢（`sweep`）、`recent` | 每格輪著查 `sweep` 顆忙的 cpu、加上上一格剛派的，補收漏了通知的回音 |
| 通知（`resp-`） | cpu 回完音往 `K/requests/` 丟的一張小檔，告訴 kernel「這顆有回音了」；只是提示，漏了由巡檢補 |
| 鏈／接鏈 | 一格排下一格、一格接一格串成的那一串 tick。接鏈＝這格開頭就把下一格的 request 放進 kernel cpu 的 `requests/` |
| 尾遞迴 | 借程式的講法：這格**不等**下一格跑完，只把它排上去就自己退出。所以不會越疊越深，也不會兩格同時在跑 |
| syscall | 借作業系統的講法；在這裡只是「往 `K/requests/` 放一個 JSON 檔」（`add`／`rm`／`stop`）。下一格會讀它，需要回音的回在 `K/responses/` |
| 帳本 | `K/state.json`。kernel 所有的記憶：鏈、階段、每池的宣告與閒號、忙的 cpu 手上的工作、每個行程的紀錄與計數、還沒做完的出貨。一次原子寫 |
| 出貨箱（outbox）／出貨 | 帳本裡四張「還沒做完的待辦」：送 ack（`acks`）、寫回音（`replies`）、刪 syscall 原單（`deletes`）、往別人家放單（`sends`，scale 單走這）。**出貨**＝把這些待辦做掉——放檔或刪檔，全部做完一次寫帳本拿掉。做過又重做是安全的 |
| 鏈 id（`chain`） | boot 發的一串 `<epoch ns>-<pid>`，用來認「你是哪條鏈的格」。**kernel 取的每個檔名都帶它**，所以跨 boot 名字不會重複 |
| 序號（`seq`） | 這格在鏈裡是第幾格，寫在 tick 的 args 裡；下一格就是 seq+1。只拿來取名，不拿來守門 |
| 殘格 | 舊鏈排在隊上、現在才被跑到的 tick。它 args 裡的 chain 對不上帳本的，所以什麼都不做就退出（自滅） |
| 階段（`phase`） | kernel 整體在哪：`running` 照常派工／`stopping` 不再派新的、把在途的收完／`stopped` 連鏈都不接了 |
| 狀態（`status`） | 一個行程現在在哪：`queued` 排隊中／`running` 派出去了／`done` 做完了／`bad` 被退件。後兩種只是留給人看，`rm` 能刪 |
| 佇列（`ready`／`delayed`） | 等著被派上 cpu 的行程：時間到了的在那池的 `ready`（先進先出），還沒到 `not_before` 的在 `delayed`（按時間排的堆積）；已經派出去的不在裡面 |
| `busy`、`req`／`proc` | `busy` 只記忙的 cpu；每格 `req`＝派給這顆、還沒結清的 request 檔名（可能已放、也可能剛記還沒放），`proc`＝那則是哪個行程的。**一顆 cpu 忙不忙只看 `busy` 有沒有它**，kernel 不去讀 cpu 自己的 state |
| `discard` | 那個行程已經被 `rm` 了，但工作還在 cpu 上跑；回音到了直接丟掉、不計數 |
| 在途 | 已經記進 `busy`、還沒收到回音的工作。`stopping` 要等它們全部收完才真的停 |
| 收掉中（`draining`） | 縮小時已不是成員、但手上還有工作的號；做完才真的叫 daemon 收 |
| boot | 開機：先叫 daemon 把 kernel 池縮到 0、等它確定收完，發一個新鏈 id、整份重送每池的宣告、把 kernel 池拉回 1 顆、把第 1 格放進 kernel cpu。boot 自己不跑格 |
| 完成／`done_exit` | 反覆行程的退出碼剛好是 `done_exit`（預設 100）＝它自己說「我做完了」，狀態改 `done`、不再排 |
| 退件／`bad_after` | 一直失敗就不再排它，狀態改 `bad` 給人看：連續失敗 `bad_after` 次（預設 10）。kind=aos（檔讀不到、inst 壞掉）也算一次失敗 |
| `tick_ms` | 一格睡多久。跟行程的 `interval_ms`（同一個行程兩次之間隔多久）是兩回事 |
| 冪等 | 同一步做一次跟做兩次結果一樣。崩了重跑才安全——帳本＋出貨箱就是為這個 |
| EEXIST（在這裡） | `link` 到已經存在的名字會失敗。kernel 把它當「已經放過了」的訊號，照樣往下走，不當錯誤 |
| 先放後記 | **只有接鏈**用的順序：**先**把下一格放進 kernel cpu 的 `requests/`、**再**寫帳本。崩在中間下一格照跑，鏈不會斷 |
| 先記後放 | 派工跟四類出貨的順序：**先**寫帳本、**再**動檔。崩在中間最多「記了沒做」、下一格補做，絕不會同一個行程被派到兩顆 cpu |
| `Interrupted` | 「結果不明」的錯誤回音：cpu 的上一任死在那件工作上，下一任補的（範式 §6.2）。反覆行程當一次失敗；`once` 原樣交給交件者 |
| `stopped`（回音裡的） | 這次是被強制停砍掉的：反覆行程計數不動、直接回佇列；`once` 原樣交給交件者 |
| （已拿掉）`spawn`、`restart:true` | 第 1 版 kernel 每格叫 daemon 拉每一顆 cpu。池式納入後改成宣告（scale 單），daemon 對任何退出碼都照宣告重拉 |

---
