11-07 下午針對今天 aos 剛改的行為挑 8 個邊緣狀況實驗（codex sol 在 scratch 照做、Claude 設計與收尾），找到 3 個 bug、2 個要知道的行為。

實驗由 codex（gpt-6.1-sol）在 mktemp 的 scratch 資料夾跑，只用 proto8 已建好的 bin，沒改 repo、沒連網、沒叫 LLM（dummy／sh agent 代替）。「結果」欄＝假設有沒有成立（假設本身可能就是預測會壞）。修法只是建議，沒修。

## 一覽

| # | 主題 | 假設成立？ | 一句話 |
|---|---|---|---|
| E1 | daemon 重起 vs `ctl_seq` | 是 | 正常重起不會重做舊的 stop；但 state.json 被刪或壞掉時，重起會照舊 stop 馬上停 |
| E2 | 判官 `keep_ordered=true` | 是 | 正常與重起都能把回信轉回原寄件人；對照表壞掉就卡死；**另找到重送 bug** |
| E3 | 判官排隊＋凍住 | 是 | 凍 7 秒醒來，有期限的排隊信第一輪全到期，「排進隊算成功」的信照排、不報錯 |
| E4 | aos-tick 兩支同時寫 | 是 | 1000 次只剩 987、6 次 WriteFailed，讀的人會讀到空檔（＝當 0） |
| E5 | DaemonFailed／DaemonMissing | 是 | 沒設／資料夾不在＝Missing；daemon 被殺或凍住＝30 秒後 Failed，不會卡死；晚到的回信不混淆下一封 |
| E6 | tick interval 近的贏、怪值 | 是 | 1000 生效、不寫就繼承 300；0、負、字串、超 64 位元都報 CfgBad |
| E7 | tool_io null、`--help` 位置、短名 | 是 | 必填給 null 報缺；`--help` 當值或在 `--` 後都當資料；未定義短名報 FlagUnknown |
| E8 | agents ask 拿掉上限後的極大值 | **否** | `timeout_s` 給 1e9 以上直接 Python OverflowError 當掉、留下孤兒 listener |

## 逐個

### E1 重起 vs ctl_seq（是）
- 假設：stop 後再 start 會繼續跑；state.json 刪掉或寫壞，重起會重做舊 stop；daemon 沒跑時新寫的 stop，下次起來第一拍照做。
- 結果：三條都照假設。state.json 完好→`ctl_seq:101` 相同、繼續跑；刪掉或寫成 `{broken`→起來就 `stopped`、0 次執行；新 seq 102→照做停。
- 白話：這是 #15-2 代定的設計後果，不算 bug。但要知道：**state.json 壞掉＋ctl.json 留著舊 stop＝重起就停**，systemd 之類自動重起會一直起一直停。若要避免，可考慮 stop 套用後把 ctl.json 清掉或改寫成已套用（要使用者裁，屬設計題）。

### E2 判官 keep_ordered（是，另有 bug）
- 假設：正常路線回信帶原信名回到原寄件人；對照表 `judge_ordered.json` 壞掉時不會像 queue.json 那樣退回重建；沒對照的回信要看怎麼處理；判官被殺後重起對照照用。
- 結果：正常與「轉寄完、回信前殺掉重起」都對；對照表寫壞→每輪退 1、`StateBad`，回信卡在 `judge_replies/new`、寄件人收不到；沒對照的回信→印 warning、直接丟掉。
- **bug（重送）**：判官在「對照表已寫進去、但原信還沒標完成」之間被殺，重起後會再轉寄一次。原因：轉回回信時先刪對照（`proto8/lib/aos/judge/_entry` 約 218 行），之後還留在 cur 的原信被重看（約 229 行的去重靠對照），已無對照就當新信再送（完成在約 431 行）。
- 建議修法：原信先標完成再寫對照，或去重時另查「已轉寄過」紀錄（例如對照刪除時留一筆墓碑，或用原信名在 judge_replies 的回信紀錄判斷）。對照表壞掉可比照 queue.json 印 warning 後改用空表＋把 judge_replies 裡的回信留著，不整輪退 1——但這會丟對照，要不要做請使用者定。

### E3 排隊＋凍住（是）
- 假設：凍住超過期限，醒來第一輪有期限的信全到期；`--on-queued ok`（沒期限）的信照排不報錯。
- 結果：SIGSTOP 7.2 秒後 SIGCONT，三封 5～6 秒期限的信第一輪都 `applied:false, SlotMissing`；無期限那封還在 queue.json、原時間戳、沒錯誤。跟 #4、#6 裁定一致。

### E4 aos-tick 同時寫（是）
- 假設：兩支 aos-tick 同時寫同一個時鐘檔會掉數，讀的人可能讀到空檔、現在空檔當 0 → 時鐘看起來倒退。
- 結果：2×500 次，最後 987；6 次 `WriteFailed … No such file`；讀了 200 萬次裡有 6 次讀到空檔（照新規則＝0，例如 183→0）。非空的數值之間沒看到倒退。
- 白話：程式頭已寫「不支援同時 tick」，所以照規格不算錯；但暫存檔名固定（`.<檔名>`），兩支會互踩，空檔又被讀成 0，**有人誤用時錯得很安靜**。
- 建議修法：暫存檔名加 pid（`.<檔名>.<pid>`）就不會互踩、也不會出現空檔被讀到；要真的不掉數再加 `flock`。讀的那邊（讀時鐘程式）不受影響，因為 rename 本身是原子的。

### E5 DaemonFailed／DaemonMissing（是）
- 結果：沒設 AOS_DAEMON、資料夾不在→`DaemonMissing`（0.02～0.05 秒）；daemon 被 SIGKILL→30 秒後 `DaemonFailed … letter withdrawn`；被 SIGSTOP→30 秒後 `DaemonFailed … could not withdraw it; it may still be applied`；醒來後晚到的舊回信留著、不影響下一封用新 id 的請求。#28 的改法如預期。

### E6 tick interval（是）
- 結果：根 300、中層 1000→子看到 1000；中層不寫→300；0、-1、`"bad"`、2^63 都在 daemon 起來時報 `CfgBad tick.interval_ms must be a positive integer within signed 64-bit range`。#10 如預期。

### E7 null、`--help`、短名（是）
- 結果：read／stat 給 `{"path":null}` 報 `ArgumentsBad missing path (required)`；`read/stat/ls --path --help`、`aos-tick -- --help`、`aos-exec … --help`（給子的參數）都當資料；另 9 種擺法也沒跳出說明；`aos-tick -z` 報 FlagUnknown。
- 限制：目前出貨的指令裡沒有「同一個短名兩支意思不同」的實例，只用 `aos_flags` 解析介面造兩個模式驗過（`-n` 一支是 name、一支是 number，都對）。

### E8 agents ask 極大值（否，有 bug）
- 假設：極大值不是乖乖等、就是報 ArgumentsBad，不會溢位、當掉或變負。
- 結果：
  - `timeout_s` 給 1e9、2^53、2^63−1、2^64、1e308 → 全部 **Python `OverflowError` traceback**、退 1，而且**每次留下一個脫離的 listener 孤兒程序**（codex 收掉了 5 個）。1.5 正常（1.5 秒後 AnswerMissing），0 與負數報 ArgumentsBad。
  - `timeout_ticks` 給 1e9、2^53 → 乖乖等；2^63−1、2^64 → `TickBad`（加上 30 格後超過 64 位元），不是 ArgumentsBad；1e308、1.5、0、負 → ArgumentsBad。
- 白話：#36 拿掉上限後，秒數太大會在 `child.communicate(timeout=…)`（`proto8/lib/agent/agents/_entry` 約 127 行）爆掉，而且爆的時候已經把聽回信的子程序起來了，沒收。
- 建議修法：秒數先夾到平台能接受的上限（例如超過約 2^31 秒或 `threading.TIMEOUT_MAX` 就當「等很久」照最大值算，或把 >某值當不設期限），並在例外路徑收掉 listener；ticks 那邊把「加 30 後溢位」也在參數檢查時就擋成 ArgumentsBad，跟 thought 對齊。是「夾住」還是「報錯」屬設計題，請使用者選。

## 附記
- 原始報告（命令、輸出、檔案快照）在 codex 的 scratch 資料夾，沒進 repo；本檔是唯一留存。
- 跑的期間 repo 裡 `arknights-kb/` 有別的 session 在改檔，跟本實驗無關。
