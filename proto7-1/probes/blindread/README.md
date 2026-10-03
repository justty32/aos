# 探針 blindread：S-01 盲讀（真模型）

← [probes](../README.md)｜出處：[namespace](../namespace/README.md) 的「盲讀清單」、[其他 OS 報告 §14 實驗一](../../notes/research/2026-10-03-other-os-borrow.md)｜S-01：一個 LLM 只靠讀檔，就能看懂並操作這一層

**是什麼**：先用 namespace 探針的程式造一個世界：mock 模型服務、服務卡、回條、reviewer 換了四代。造到第 4 步、a-job5 還在舊服務 model-a 上 hold 著時，pause 所有 node，複製兩份。

- **card 版**：原樣。現任 reviewer 的 `mnt/model` 指到 model-a2、`mnt/model-prev` 指到 model-a，兩邊各有服務卡 `service.json`。
- **hardcoded 版**：同一個世界，但拿掉了服務卡、掛載點、birth.json 的 mounts，以及 reload 回條的 diff。路徑寫死在 `proj-a/reviewer.cfg.json`。

模型扮 proj-a 的 reviewer，提示裡只告訴它自己的任務資料夾。它只有 `read_file` 一個工具，沒有操作卡、沒有說明文件。要回答五題（[questions.json](questions.json)），標準答案在 [answers.json](answers.json)：

| 題 | 問什麼 | 標準答案 |
|---|---|---|
| q1 在哪送件 | 新請求寫進哪個資料夾 | `services/model-a2/clients/reviewer/requests`，寫掛載點下的路徑也算對，評分比實際位置 |
| q2 誰付錢 | a-job6 算在哪個 charge context | `cc-proj-a` |
| q3 完成了沒 | a-job5、a-job6 的狀態 | a-job5 pending、a-job6 settled |
| q4 能不能重送 | a-job5 該不該改送 model-a2 | no：它在 model-a 上在途，改送會做兩次 |
| q5 哪份工具生效 | 主要服務、只收尾的舊服務 | 主要 model-a2，舊的 model-a |

- 離線版（run_all）約 1 秒，驗這些：
  - 題目與答案檔都在；
  - 答案跟造出來的世界對得上；
  - hardcoded 版確實沒有服務卡與掛載點；
  - 照稿腦只讀 8 個檔（3.7 KB）就五題全對；
  - 評分器會扣錯。
- `--real` 才打模型：每個模型 × 兩版各一次，紀錄在 `runs/`（`<版>-<模型>-rep?.json` 與 transcript）。

## 結果（真模型 125 次呼叫，上限 150）

兩輪；rep1 每次上限 20 次呼叫，rep2 是 14 次。

| 模型 | card rep1 | card rep2 | hardcoded rep1 | hardcoded rep2 |
|---|---|---|---|---|
| deepseek-chat | 5/5（9 次呼叫、讀 33 次） | 5/5（8、31） | 5/5（14、54） | 5/5（14、53） |
| claude-haiku-4.5 | 4/5（8、24） | 4/5（9、25） | 4/5（9、19） | 0/5（14 次用完沒交答案） |
| chatgpt-gpt-6-luna-low | 5/5（11、22） | 5/5（10、33） | 5/5（10、34） | 5/5（9、31） |

- **只靠讀檔，五題答得出來**：12 次裡 10 次 ≥ 4/5。q1、q2、q3、q5 除了沒交答案那次，全部答對。
  - card 版 6 次都讀了兩張服務卡；q1 只有一次寫掛載點下的路徑，其餘都寫實際位置。
  - hardcoded 版每次都先找到 `reviewer.cfg.json`。
- **card 版讀得比較少，但分數沒差**：
  - deepseek：card 8～9 次呼叫、讀 31～33 次；hardcoded 14 次呼叫、讀 53～54 次，還去翻了 `.aosd`。
  - luna 兩版差不多。
  - haiku 在 hardcoded 版一個檔一個檔翻，有一次 14 次呼叫用完還沒答。
  - 這五題用的都是自我描述的資料檔（請求、回條、checkpoint、reviewer-status），寫死路徑的世界只要有一個 cfg 指路，答案一樣找得到。服務卡多的是 `charging`、`dedup`、`completion` 這類語意，這五題剛好沒有一題非靠它不可。
- **錯的都是 q4（haiku 3 次）**，兩種錯法：
  - rep1 兩次都讀到 `reviewer.jsonl` 裡上一代 reviewer 留下的舊事件「a-job5 unknown：送去的服務現在沒掛著」，當成現況，結論是「該改送 model-a2」。其實現任 reviewer 的 `reviewer-status.json` 是 ok、pending，而且 model-prev 已經掛上。這跟 N-69「把舊 last_error 當現況」是同一類錯。
  - rep2 事實全讀對（a-job5 在 model-a pending、主服務已換），推論卻是「主服務換了，就改送過去」。檔裡沒有一句話說「在途請求屬於送去的那個服務，換服務不重送」：服務卡的 `dedup` 只寫「同一個 request_id 只執行一次」，沒寫範圍只在本服務內；這條規則只寫在 reviewer.py 的程式註解裡，模型讀不到。

## 逼出的 daemon／tick 需求

**沒有。** 五題都是任務層的協定（服務卡、請求、回條、checkpoint），daemon／tick 只提供了 birth.json 的 mounts、ctl-done 的 diff 與資料夾結構，模型都讀得懂。錯誤落在任務層，給寫服務卡與 reviewer 的人：

- 服務卡的 `dedup` 要寫清楚範圍，例如 `dedup_scope: "service"`，加上「在途請求換服務不重送」。
- reviewer 的流水帳要記「unknown 已解除」（掛上 model-prev 之後），或讓狀態檔標出它是現任的。
