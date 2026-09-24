← [工具大開發時代](../README.md)｜[notes 索引](../../README.md)｜規範：[spec/team/](../../../spec/team/README.md)

# 第一波第 1 隊「骨架」：報告（2026-09-24）

一支團隊＝一個資料夾：`team.json` 名冊、`members/<名>/` 每個成員的 agent 家、`team/` 放信、任務單、等人回答的問題。
成員只往自己的 `team/outbox/<名>/` 放檔；開單、改狀態都是郵差（第 2 隊）叫這裡的函式做，**不問模型**。
審查在 [review-task.md](review-task.md)／[review-astra.md](review-astra.md)。

## 做了什麼

1. **共用格式**（先合進 main 的 f74cc06）：`spec/team/` 九份規範＋`examples/` 九份範例，`python3 lib/aos_team_format.py 檔…` 驗得過。
2. **`aos-team`**：
   - `init`：照名冊生家；重跑只補新成員，崩了會補完。
   - `start`／`stop`：替每個成員登記／撤銷，郵差、心跳有模組就一起。
   - `ls`：一行一個成員，列 health、手上的單、最後寄出的信。
   - `rm`：家搬到 `members/.removed/`，名冊一起改；先記下要做什麼，崩了能接著做。
3. **成員模板** `templates/{lead,worker,reviewer,coder}/`：每個家**一定附 access.json**。
   - 專案掛成 `/work/ws`：工人可寫，領隊、審查唯讀。
   - 自己的 outbox 掛成 `/work/outbox`，可寫。
   - 任務表掛成 `/work/board`，唯讀。
   - 函式 `aos_agent_init.init_from_template()`；`init --template` 旗標由第 4 隊接。
4. **任務單狀態機** `aos_team_task.py`：
   - 只有「目前的負責人、rev 對得上」的回報算數。
   - 沒過還有次數＝寄「REQUEST 修正」；次數用完才 failed。
   - judge 條目開審查子單。
   - 同一個觸發 id 重播＝回同一份後續動作。
5. **工具包 `tools/task/`**：`handoff`、`board`、`review_result`、`ask_human`。在牢裡只寫 `/work/outbox`、只讀 `/work/board`；寫完回「end this turn」，沒有等回信的工具。
6. **門房** `aos-team ask`：
   - 整句比對。
   - 命中兩條或句子有否定詞＝落穿給領隊。
   - 例句沒全過就拒跑。
   - 另有 `route test`／`save`，每次都記 `route.log`。
7. **人的指令**：`task ls/show/cancel/reassign`、`wait ls`、`answer`。都是寄申請給郵差，人也不直接改任務表。
8. **給郵差的兩支函式**：
   - `drop_new()`：投信不覆蓋。
   - `already_delivered()`：查三處（input、done 封存、intake），崩了重跑不重投。

## plan.md 的七條驗收：全過

1. 共用格式先合：f74cc06。
2. init 生三個成員，`aos-agent check` 各自沒有 bad，input 是資料夾。
3. start／stop／ls。
4. 命中 tool 規則時，不寫任何成員的 input；命中兩條或有否定詞就落穿。
5. 例句全過才准存。
6. handoff 經假郵差開出 t-0001（queued）；舊 rev 的 DONE 不改狀態。
7. wait ls／answer：答案回到發問者，待辦少一條。

②③⑥⑦ 另有真 daemon＋kernel＋bwrap 的整合測試：模型是假的，照劇本叫工具。三個成員在牢裡叫了 handoff、board、write、ask_human、review_result，單子走到 done。

## 真跑（LiteLLM deepseek-chat；郵差用 scratchpad 裡的假郵差）

```
ask: 沒有規則命中，已交給領隊 lead
郵差收到 lead 的 request {"kind": "handoff", "assignee": "worker-1", "workflow": "無", "goal": "在專案根目錄建立 hello.txt…",
                          "done_when": [{"kind": "file_exists", "path": "hello.txt"}, {"kind": "judge", …}]}
投信 【來信 post → worker-1 · REQUEST · t-0001 rev1 · 09-24 18:11】 任務 t-0001（rev1，第 1/2 次）…
hello.txt： 你好，歡迎來到這個專案！        領隊：ls、find、read、handoff（模型 4 次）
```

- **第 1 次**找到兩個問題，都修了，也都通知了調度者：
  - 領隊沒有工作流，自己編了 `worker.md` → 現在可以寫「無」。
  - 人回答後，單子停在 sent → resume 直接回 working。
- **第 2 次**：工人在牢裡寫好了 hello.txt，但要回 DONE 時 `team_say` 還不在（第 2 隊的），所以沒走到 done。等第 2 隊合進來再重跑。

## 數字

- **全測**：main（a5d557c）1593 → **1640 全綠**。
  - 這一隊的測試共 75 條，5 個檔：`test_team_format`、`test_team_init`、`test_team_route`、`test_team_task_cli`、`test_team_review_fix`。
  - 其中 28 條已在 main。
- **穩定**：這 75 條連跑 10 次，**10/10**，含整合測試。
- **速度**（不關牢，每支跑 5 次取中位數）：

  | 指令 | 牆上時間 |
  |---|---|
  | handoff／board／ask_human | 15 ms（cpu 0.015 s） |
  | ask | 30 ms |
  | ls | 47 ms |
  | init 三人 | 60 ms |

  記憶體都在 22 MB 以下，沒有常駐程式。
- **描述字數**：

  | 工具 | 字元 |
  |---|---|
  | handoff | 1025 |
  | board | 329 |
  | review_result | 474 |
  | ask_human | 420 |
  | 合計 | 2248（約 560 token） |

## 六軸自評（1～5，不加總；S 用上面的 10 次；團隊層的 S 還沒評）

| 工具 | L | S | R | F | H | B | 最弱兩軸、怎麼補 |
|---|---|---|---|---|---|---|---|
| `aos-team init/start/stop/ls/rm` | 5 | 5 | 5 | 5 | 4 | 4 | H 要看 spec 才懂資料夾長怎樣（收尾隊寫教程）；B 會寫團隊資料夾、登記 kernel |
| 模板＋`init_from_template` | 5 | 5 | 5 | 5 | 4 | 5 | H：改了 mail_to，重跑 init 不會更新人格；S 已含兩個崩潰窗口 |
| 門房 `ask`／`route` | 5 | 5 | 5 | 5 | 4 | 3 | B：包工具在牢外跑（routes.json 等於有主機執行權，只有人寫）；H：為什麼落穿要看 route.log |
| `handoff`／`review_result` | 5 | 5 | 5 | 5 | 4 | 4 | B 只寫自己的 outbox；H 輸出是英文 |
| `board` | 5 | 5 | 5 | 5 | 4 | 5 | H：英文、縮寫（try1/3） |
| `ask_human`＋`wait`／`answer` | 5 | 5 | 5 | 5 | 5 | 4 | B 寫 outbox；問題檔只有郵差寫 |
| 狀態機＋`task` 指令 | 5 | 5 | 5 | 5 | 4 | 4 | H：要看 `task show`；B：人的指令寫 human 的 outbox |

L 軸全是 5：這一隊的東西都不叫模型。

## astra 審查

必修 10 條，**10 條都修了**，都有回歸測試（`test_team_review_fix.py`）：

| # | 問題 | 修法 |
|---|---|---|
| 1 | 去重只擋還在 input 的信 | `already_delivered()` 查三處；mail.md 寫明後續動作的信 id 要固定、封存檔不准清 |
| 2 | 審查過期了還會開 r2 | `open_review` 先照 src 找；要帶 rev／attempt，對不上就記 `stale_review` |
| 3 | 逾期通知會丟 | `due_deadlines()` 不寫檔，郵差先記事件再 step；重播回同一份通知 |
| 4 | 別人的問題、舊問題的答案會恢復錯的等待 | 問題記 `task_rev`；resume 要 `waiting_on`＝這一題、rev 相同 |
| 5 | 多掛的可寫資料夾能碰團隊控制資料 | 碰到 team.json、team/、members/、proto5 就 `AccessUnsafe`；專案裡的自訂模板 `BadTemplate` |
| 6 | init 兩個崩潰窗口補不完 | 有 marker 就續做；「工具檔在＋info.tools 有那一條」才算裝好 |
| 7 | 任何信都能推 queued → sent | 只有派工信（帶 `dispatch`）才推，要對上 rev／attempt |
| 8 | 驗收結果沒帶版本也收 | 沒帶整數 rev、attempt 就 `BadEvent` |
| 9 | 審查子單失敗，父單卡住 | 子單變 failed／cancelled 時，父單轉 blocked 等人 |
| 10 | rm 半路崩，init 會把人生回來 | 先寫 `.removing-<名>.json`；init 看到就拒跑，rm 重跑接著做 |

建議也做了三條：`kind` 型別錯改報 `UnknownKind`；改派時重新起算期限；換模板要先 rm。
沒做的一條：把整合測試移出單元測試集。它要 bwrap，第一波驗收要它，所以留著。

## 沒做的，要給別隊的

- **第 2 隊**：真郵差、`team_say`、驗收員、心跳。目前只測到假郵差這一層。
- **第 4 隊**：`aos-agent init --template` 的旗標。
- **收尾隊**：
  - 教程：plan 寫的「教程 07」已經被 cli-agents 用掉，**改成 08**。
  - 人格定稿。
  - README 加列：proto5 README 加 `aos-team`，lib README 加 8 支模組，tools README 加 `task`。

## 要你拍的

| # | 題目 | 預設 |
|---|---|---|
| 1 | 同一個 kernel 上兩支團隊不能有同名成員（kernel 用 `agent-<資料夾名>` 登記） | 寫在文件裡、名字取得不一樣；要改得動 aos-agent 的登記名 |
| 2 | 門房的包工具不關牢 | 照現在；第二波再接 aos-jail |
| 3 | `answer` 的答案不在選項裡 | 照收，印一行提醒 |
| 4 | `rm` 只搬家、不刪 | 不刪 |
| 5 | 改了名冊後重跑 init | 只更新工具設定，不動人格、記憶、access.json |
