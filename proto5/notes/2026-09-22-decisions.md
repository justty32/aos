# 23 題拍板紀錄（2026-09-22，使用者決策）

對照 [notes-brief/README.md](../notes-brief/README.md) 的題目表與 [proto5.1 findings-brief](../../proto5.1/notes/findings-brief.md)。
使用者看完 findings-brief 後逐題拍板；這份是唯一的決策來源，之後 proto5.1 第 4 段照這份改、proto5 規範照這份回流。
以後想到「先記著、之後再做」的事，放 [backlog/](../backlog/README.md)。

## 一、改變原方案的（6 題）

| 題 | 決定 | 白話 |
|---|---|---|
| **llm cpu 1** | **agent 只寫模型代號＋參數；endpoint／真實 model 名／api_key／timeout 全放 llm cpu 家的 `models` 表** | agent 本來就不該知道呼叫細節，只要說「我要哪個模型、temperature 多少」。壞掉換 url 之類的事以後由 llm cpu 處理（backlog）。 |
| **llm cpu 5** | **作廢：一律經 cpu，同步模式拿掉** | engine 只有一種長相。測試與小 agent 也搭一個 llm cpu 家，測試裡叫一次 tick 就好。 |
| **daemon/kernel 4** | **不用槽鎖與交接意圖。aos-run 即時寫 `run.json`（busy／目標／次數／退出碼／耗時）、間歇讀 `ctl.json`（stop／hold）；kernel 隨時換目標檔，只在「把 X 排去別顆」之前看其他 cpu 的 run.json 是不是還在跑 X** | aos-run「先寫 busy 再讀目標」、kernel「先換目標檔再看 run.json」，兩個順序一搭就沒漏洞；不用等 aos-run 閒下來，所以不飢餓。kernel 只跟 daemon 指定的檔講話。 |
| **daemon/kernel 5** | **砍到底改成可選，預設不開**：aos-run `--kill-tree`；daemon add 請求與 kernel config 各一格 `kill_tree` 往下傳 | 砍程序危險，而且有些東西 aos 停了也該繼續跑。不開時工具本來就在另一個 session，自然活下去。 |
| **逾時 3** | **連敗暫停的 waits 那條開 `consume`，不封存舊 continue.json** | 第二次暫停失效是 bug，用最簡單的方式修。fail 狀態之類的另案（backlog）。 |
| **act 6** | 統一回「結果不明」tool 訊息、不重試 | 照建議。 |

## 二、照建議接受的（17 題）

act 1～5、daemon/kernel 1～3、6、llm cpu 2～4、6、逾時 1、2、4、5。其中：

- **act 5**：接受並行、不保證同批 cpu 工具的執行順序，規範寫明「這是模型一次叫多個又不給順序的問題」；以後可能提供特殊工具讓模型指定順序（backlog）。
- **llm cpu 3**：接受一把 flock 短鎖；cpu 實作再精簡的事之後在 proto5-2 試（backlog）。
- **llm cpu 6**：先不加請求身分；「寫完請求、還沒加 waits 就崩」這種邊緣情況記進 backlog。

## 三、接下來的順序（使用者定）

1. proto5.1 第 4 段：把上面六個改變做進去（[proto5.1/notes/stage4-task.md](../../proto5.1/notes/stage4-task.md)）。
2. 開 fable agent 重審 proto5.1 全部：有沒有更好的做法、有沒有沒注意到的坑。
3. 都好了再收斂回 proto5：**先只更新 spec／notes，不動程式**。
