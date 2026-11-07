11-07 下午針對今天 aos 剛改的行為挑 8 個邊緣狀況實驗（codex sol 在 scratch 照做、Claude 設計與收尾），找到 3 個 bug、2 個要知道的行為。

實驗由 codex（gpt-6.1-sol）在 mktemp 的 scratch 資料夾跑，只用 proto8 已建好的 bin，沒改 repo、沒連網、沒叫 LLM（dummy／sh agent 代替）。「結果」欄＝假設有沒有成立（假設本身可能就是預測會壞）。四題已裁並落實在 `00a0a1b14`；下表記首次實驗結果，修正與限制見後段。

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

原始實驗過程見 git 歷史 `00a0a1b14`；這裡只留結論與限制，已裁修正見下段。

### E1 重起 vs ctl_seq（是）

- 舊 state 回音同 seq 會略過，首拍新 seq 照做；**state.json 壞掉＋ctl.json 留著舊 stop＝重起就停**。systemd 自動重起會起停迴圈；已裁維持現狀，先手動清掉 ctl.json 再起。

### E2 判官 keep_ordered（是，另有 bug）

- 正常及轉寄後重起能代回原信名；`judge_ordered.json` 壞掉會每輪退 `StateBad`，回信卡住，沒有對照的回信會 warning 後丟掉。對照刪掉而原信還在 cur 的重送問題已修；仍有兩個中斷窗口，見下段代定。

### E3 排隊＋凍住（是）

- 凍住超過期限後，有期限的排隊信醒來第一輪全部 `applied:false, SlotMissing`；`--on-queued ok` 的無期限信照排，符合 #4、#6。

### E4 aos-tick 同時寫（是）

- 初測兩支各寫 500 次：最後 987、6 次 WriteFailed，200 萬次讀取有 6 次空檔（當 0）。暫存檔互踩已修；不加鎖，同時 tick 仍會掉數，規格不支援。

### E5 DaemonFailed／DaemonMissing（是）

- 沒設／資料夾不在報 `DaemonMissing`；daemon 被殺或凍住，30 秒後報 `DaemonFailed`。撤信失敗仍可能晚套用；晚到舊回信不影響下一封新 id 的請求，符合 #28。

### E6 tick interval（是）

- 根 300、中層明寫 1000，子層讀到 1000；中層不寫則繼承 300。0、負數、字串、超過 int64 都報 `CfgBad`，符合 #10。

### E7 null、`--help`、短名（是）

- 必填 path 給 null 報 `ArgumentsBad`；`--help` 當值、在 `--` 後或給子程式時都是資料；未定義短名報 `FlagUnknown`。出貨指令仍沒有「同一個短名兩支意思不同」的實例，只用解析介面驗過 `-n` 分別代表 name／number。

### E8 agents ask 極大值（否，有 bug）

- 初測極大秒數會 OverflowError 並留 listener；極大 ticks 加 30 後超 int64 報 TickBad。已改入口檢查報 ArgumentsBad 並收子程序；可接受的 1.5 秒照舊 AnswerMissing，細節見下段。

## 附記
- 原始報告（命令、輸出、檔案快照）在 codex 的 scratch 資料夾，沒進 repo；本檔是唯一留存。
- 跑的期間 repo 裡 `arknights-kb/` 有別的 session 在改檔，跟本實驗無關。

## 使用者裁定與修正（11-07）

使用者 11-07 午用選項框裁定四題；隊長定修法、codex（gpt-6.1-sol）施工，並在 mktemp scratch 重跑對應實驗。

| 題 | 原裁定 | 修了什麼 | 驗證 |
|---|---|---|---|
| E8 agents 極大值 | 直接報錯：超過平台上限報 ArgumentsBad、不執行；出錯時收掉子程序；ticks 對齊 | `agents` ask 在起子程序前檢查：`timeout_s` 最多 2,147,453 秒（poll 最多 2^31−1 毫秒，扣掉 30 秒保險）；`timeout_ticks` 最多 int64−30，並依當下時鐘／間隔再縮小，超過一律 ArgumentsBad；`agent()` 改成 finally 收子程序（kill＋wait） | 1e9、2^53、2^63−1、2^64、1e308、上限＋1 全 ArgumentsBad、0 子程序、0 殘留 listener；1.5 秒照舊 AnswerMissing；ticks 2^63−1、2^64 → ArgumentsBad，1e9 照舊接受；注入例外三種都收乾淨 |
| E1 state.json 壞掉 | 維持現狀、文件寫明 | [aos-daemon 08](../../../../impls/aos-daemon/docs/08-當機復原與已知限制.md) 補一句：先手動清掉 ctl.json 再起，否則照舊 stop 馬上停，systemd 底下會起停迴圈 | 只改文件 |
| E2 判官重送 | 原信先標完成，再寫對照（若會丟信或回信對不上，選代價最小的順序並記下） | 見下方代定：不改 forward 的順序，改成 `relay_replies` 刪對照前，原信還在 requests 的 cur 就先 done | 正常、對照已寫但原信沒 done 時被殺、轉寄後回信前被殺、回信前重起，4 條路線都是 ctl 收 1 封、寄件人收 1 封、in_reply_to 正確；原信 done 失敗時 PostFailed，原信與對照都保留 |
| E4 aos-tick 互踩 | 暫存檔名加 pid，不加鎖 | 暫存檔改 `.<檔名>.<pid>`；檔頭、help、cmd/docs/02 同步 | 2×500 次：0 次 WriteFailed；讀 200 萬次：0 次空檔、0 次倒退；最後是 987（沒加鎖，同時 tick 照舊會掉數，規格本來就不支援） |

代定（隊長）：
- **E2 順序**：如果照字面改成「先標完成，再寫對照」，判官死在兩步之間會留下沒有對照的轉寄，daemon 的回信會被當成「沒有對照」丟掉，寄件人就收不到回信。所以不改轉寄端，改在轉回回信時補收：刪對照前，原信還在 cur 就先標完成。效果符合「原信先標完成」，也不會丟回信。剩下兩個窗口本來就有，這次沒動：一是 send 進 ctl 後、寫對照前死掉（會重送）；二是轉回回信後、標完成前死掉（回信會重轉一次）。
- **E8 代號**：ticks 太大改報 ArgumentsBad；時鐘或間隔本身壞了仍報 TickBad。上限檢查用的是入口當下的時鐘。
