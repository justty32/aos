← [kernel](README.md)｜[spec 總導航](../README.md)

# 0. 名詞（白話）

跟 cpu 範式共用的詞（家、主人、交件者、request、目標、ack、偷看、link、notification…）在 [cpu.md §0](../cpu/terms.md)，
這裡只列 kernel 自己的，照正文第一次出現的順序排。（2026-09-24 proto5-2 池式納入：池、編號、宣告、巡檢、通知、`busy` 等改寫或新增。2026-09-24 one-boot：kernel cpu、鏈、殘格、尾遞迴、先放後記拿掉；帳本、tick、boot 改寫；表尾加 tick 鎖、提交點、開 tick 的 daemon、`aos up`／`aos down`。）

| 詞 | 意思 |
|---|---|
| 行程（`procs.<NAME>`） | **不是**作業系統那個行程。在 kernel 這裡是「一份登記好的工作」：記著要跑哪個 target、多久跑一次、跑到哪；真的有東西在跑是派工之後的事 |
| 派工 | 從池的排隊格挑一個輪得到的行程，把它的 `aos-exec` request 放進那池一顆閒著的 cpu（閒號從 `free` 拿） |
| 收回音 | 去 `pools/<P>/cpus/<i>/responses/` 讀那則 request 的結果，判定（§4）、更新帳本、再放 ack |
| 反覆行程 | `once: false` 的行程：跑完回佇列，隔 `interval_ms` 再跑一次，直到完成或被退件 |
| `once` | 只跑一次的行程：那次跑完把結果直接交給當初 `add` 的人，行程跟著消失 |
| 長命行程 | 開著就不退、一直待命的程式（daemon、cpu 的主人都是）。kernel **不是**：它每次只活一格的時間，記憶全放在帳本 `K/ledger.sqlite` 裡 |
| tick（一格） | kernel 的一次心跳：daemon 開一次 `aos-kernel tick --target K`，把 §3 那些步驟做完就退出。「格」就是一次 tick。同時只准一格 |
| （已拿掉）kernel cpu（`kcpu`）、kernel 池 | 第 2 版專門排 tick 的那一顆 exec cpu（`kernel/0`）。2026-09-24 one-boot 拿掉：tick 改由 daemon 開。`kernel` 這個池名還是保留名，一般池不准叫它 |
| 池（`pool`） | 一群一模一樣的 cpu（同一份環境），在 info 的 `pools` 裡寫「要幾顆」；行程也標一個池名，只會被派到那池的 cpu 上（例如打模型的工作都排去 `llm` 池）。池都是跑工作的，所以也叫**工作池**（one-boot 起沒有 kernel 池了） |
| 成員編號、`P/<i>` | 池裡的 cpu 不取名，用號碼：不在 `skip` 裡的最小 `count` 個非負整數。全名 `P/<i>` |
| 宣告、scale 單 | kernel 告訴 daemon「池 P 要這幾號」的一張單；daemon 自己補、重拉、收（§3.1、§5） |
| 巡檢（`sweep`）、`recent` | 每格輪著查 `sweep` 顆忙的 cpu、加上上一格剛派的，補收漏了通知的回音 |
| 通知（`resp-`） | cpu 回完音往 `K/requests/` 丟的一張小檔，告訴 kernel「這顆有回音了」；只是提示，漏了由巡檢補 |
| （已拿掉）鏈／接鏈、尾遞迴 | 第 2 版「一格開頭先把下一格排進 kernel cpu」的做法。one-boot 起一格由 daemon 開，一格不再排下一格 |
| syscall | 借作業系統的講法；在這裡只是「往 `K/requests/` 放一個 JSON 檔」（`add`／`rm`／`stop`）。下一格會讀它，需要回音的回在 `K/responses/` |
| 帳本 | `K/ledger.sqlite`（sqlite 檔，第 3 版）。kernel 所有的記憶：boot 編號、階段、每池的宣告與閒號、忙的 cpu 手上的工作、每個行程的紀錄與計數、還沒做完的出貨。存一次＝一筆交易、只寫變了的列 |
| 出貨箱（outbox）／出貨 | 帳本裡四張「還沒做完的待辦」：送 ack（`acks`）、寫回音（`replies`）、刪 syscall 原單（`deletes`）、往別人家放單（`sends`，scale 單、撤登記的 `tick` 單走這）。**出貨**＝把這些待辦做掉——放檔或刪檔，全部做完一次寫帳本拿掉。做過又重做是安全的 |
| boot 編號（`chain`） | boot 發的一串 `<epoch ns>-<pid>`。名字沿用第 2 版的「鏈 id」，現在只是「這次 boot 的編號」。**kernel 取的每個檔名都帶它**，所以跨 boot 名字不會重複 |
| 序號（`seq`） | 這格是這次 boot 以來第幾格：帳本 `last_seq`＋1。只拿來取名，不拿來守門 |
| （已拿掉）殘格 | 第 2 版舊鏈排在 kernel cpu 上的格。舊 kernel cpu 裡還排著的舊格帶 `--chain`／`--seq`，one-boot 的 tick 看到就退 0、什麼都不做 |
| 階段（`phase`） | kernel 整體在哪：`running` 照常派工／`stopping` 不再派新的、把在途的收完／`stopped` 停好了，daemon 也不再開 tick |
| 狀態（`status`） | 一個行程現在在哪：`queued` 排隊中／`running` 派出去了／`done` 做完了／`bad` 被退件。後兩種只是留給人看，`rm` 能刪 |
| 佇列（`ready`／`delayed`） | 等著被派上 cpu 的行程：時間到了的在那池的 `ready`（先進先出），還沒到 `not_before` 的在 `delayed`（按時間排的堆積）；已經派出去的不在裡面 |
| `busy`、`req`／`proc` | `busy` 只記忙的 cpu；每格 `req`＝派給這顆、還沒結清的 request 檔名（可能已放、也可能剛記還沒放），`proc`＝那則是哪個行程的。**一顆 cpu 忙不忙只看 `busy` 有沒有它**，kernel 不去讀 cpu 自己的 state |
| `discard` | 那個行程已經被 `rm` 了，但工作還在 cpu 上跑；回音到了直接丟掉、不計數 |
| 在途 | 已經記進 `busy`、還沒收到回音的工作。`stopping` 要等它們全部收完才真的停 |
| 收掉中（`draining`） | 縮小時已不是成員、但手上還有工作的號；做完才真的叫 daemon 收 |
| boot | 開機：驗、拿 tick 鎖、寫帳本（新 boot 編號、每池下一格整份重送宣告）、向 daemon 登記「請替我開 tick」。boot 自己不跑格。平常用 `aos up` |
| 完成／`done_exit` | 反覆行程的退出碼剛好是 `done_exit`（預設 100）＝它自己說「我做完了」，狀態改 `done`、不再排 |
| 退件／`bad_after` | 一直失敗就不再排它，狀態改 `bad` 給人看：連續失敗 `bad_after` 次（預設 10）。kind=aos（檔讀不到、inst 壞掉）也算一次失敗 |
| `tick_ms` | daemon 開兩格之間隔多久（從上一格開始算）。跟行程的 `interval_ms`（同一個行程兩次之間隔多久）是兩回事 |
| 冪等 | 同一步做一次跟做兩次結果一樣。崩了重跑才安全——帳本＋出貨箱就是為這個 |
| EEXIST（在這裡） | `link` 到已經存在的名字會失敗。kernel 把它當「已經放過了」的訊號，照樣往下走，不當錯誤 |
| （已拿掉）先放後記 | 第 2 版只有接鏈用的順序。one-boot 沒有鏈了，所有動檔都是下面的「先記後放」 |
| 先記後放 | 派工跟四類出貨的順序：**先**寫帳本、**再**動檔。崩在中間最多「記了沒做」、下一格補做，絕不會同一個行程被派到兩顆 cpu |
| `Interrupted` | 「結果不明」的錯誤回音：cpu 的上一任死在那件工作上，下一任補的（範式 §6.2）。反覆行程當一次失敗；`once` 原樣交給交件者 |
| `stopped`（回音裡的） | 這次是被強制停砍掉的：反覆行程計數不動、直接回佇列；`once` 原樣交給交件者 |
| （已拿掉）`spawn`、`restart:true` | 第 1 版 kernel 每格叫 daemon 拉每一顆 cpu。池式納入後改成宣告（scale 單），daemon 對任何退出碼都照宣告重拉 |
| tick 鎖（`K/.tick.lock`） | 一把檔案鎖（flock）。tick 一開始拿，拿不到＝別的一格在跑，退 75；boot 寫帳本時也拿。行程死了（含 kill -9）鎖自己消失 |
| 提交點（A／B／C） | 一格裡存帳本的三個時機：A 第 4 步出貨完、B 第 5～9 步決定完、C 第 10 步出貨完。每次一筆交易（§1.2） |
| 開 tick 的 daemon（`ticker`） | 替這個 kernel 定時開 tick 的那個 daemon 家：info 頂層的 `daemon`。boot 向它登記、停好那格向它撤登記（[daemon §10](../daemon/ticks.md)） |
| `aos up`／`aos down` | 一條指令開機（daemon 沒在跑就開、再 boot）、一條指令停機（kernel halt、再停沒別人要用的 daemon）（[daemon §11](../daemon/up.md)） |

---
