← [cpu](README.md)｜[spec 總導航](../README.md)

# 0. 名詞（白話）

照正文第一次出現的順序排；跟實作有關的（fd、訊號）放後面。

| 詞 | 意思 |
|---|---|
| 家 | 一個 cpu 的資料夾（下面的 `C/`）。kernel 的家 `K/`、daemon 的家 `D/` 也是家；`K/pools/kernel/cpus/0/` 是 kernel 專用那顆 cpu 的家，跟 `K/` 是兩個家 |
| 主人（行程） | 管這個家的執行與狀態的那支行程：exec cpu 的主人就是 `aos-cpu C`。啟動前人寫 `info.json` 是初始化，不算主人的事 |
| 外人 | 主人以外的行程：kernel、agent、人用 shell |
| 交件者／收件者 | 交件者＝送出 request 的那個程式；它同時就是那則回音的收件者。本文統一叫交件者 |
| request／response | 一則 JSON-RPC 請求／回音（§3）。工作 request 說「跑這個目標」，response 說跑得怎樣；`ack`、`stop` 也是 request，只是不用回音 |
| 目標（target） | aos-exec 的 `xxx`：普通檔、`.json` inst、資料夾三種（[aos-exec 三種目標](../aos-exec/README.md)）。request 裡放的是目標路徑，不是 inst 內容 |
| inst | 一份 `inst.json`：說要跑什麼程式、cwd、環境、串流怎麼接（[inst-posix](../inst-posix/README.md)）。cpu 不碰它的內容，交給 aos-exec |
| ack | 交件者讀完並記下回音後，再放一則「我拿走了」的通知（§3.3）；主人收到才刪回音 |
| 偷看 | 直接讀別人家的 `state.json`、`requests/`、`responses/`，不放單、不改任何檔 |
| 原子 | 一步做完、別人看不到「做到一半」。`rename`、`link`、`mkdir` 都是 |
| `.tmp` 再 rename | 先寫同目錄暫存檔、寫完 `rename` 蓋過去；讀的人永遠不會讀到半份 |
| `link` | 硬連結；目標已存在就失敗（EEXIST）。拿它做「有就失敗」的放單（§3.1） |
| base／cwd | base 是 inst 裡相對路徑的起點，aos-exec 定：`.json` 目標是檔所在的資料夾、資料夾目標是那個資料夾自己；cwd 是程式跑起來的工作目錄。關係在 aos-exec 三種目標那張表 |
| 指示詞、中心 | JSON 裡 `$env`／`$ref`／`$fmt` 那套（[directives](../directives/README.md)）；「中心是 C」＝解 `$ref` 時相對路徑從 cpu 的家算起 |
| JSON-RPC 2.0 | 一種「請求／回音」的 JSON 信封格式（§3）；request 有 `method`／`params`，response 有 `result` 或 `error` |
| notification | JSON-RPC 裡**沒有 `id`** 的 request＝不用回音（`id: null` 不算沒有） |
| epoch ns | 1970 年到現在的奈秒數（`time.time_ns()`），檔名慣例用的。kernel 的 `not_before`、daemon 的 `since` 用的是 epoch **秒**（帶小數），同一個起點、差十億倍 |
| 旗標 | 程式裡的一個布林。訊號 handler 只能安全地做「把它設成 true」這件事，真正的動作由主迴圈看到旗標才做 |
| 控制 pipe、fd 0／fd 1 | 父行程開給孩子的管子：fd 0 父寫子讀、fd 1 子寫父讀。主人啟動時會把它們搬到別的號碼（§6.1） |
| `go` | 父行程在控制 pipe 上寫的第一行：「我登記好你了，開工吧」。等不到（EOF）＝父行程在登記前就死了，孩子什麼都不碰就退（§6.1） |
| EOF | 管子所有寫端都關了。父行程死了、且沒把寫端漏給別人，孩子就讀到 EOF |
| close-on-exec | 一個 fd 標了這個，跑別的程式（exec）時會自動關掉，孩子拿不到 |
| process group | 子程式跟它自己生的孫子被歸成一組，訊號可以一次發給整組；孫子自己脫離這組就管不到 |
| TERM／KILL | 兩種訊號：TERM 是「請你結束」（程式可以先收尾）；KILL 是直接砍掉、擋不了 |

---
