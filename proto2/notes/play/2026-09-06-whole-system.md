# 2026-09-06 整套試玩（codex）

## 用的模型

- LM Studio 一開始沒載模型。我載了 `qwen/qwen3.5-9b`。它會叫工具，但偶爾回空白，也很會燒 reasoning token。
- `lms load` 後 API server 沒有自己起來。我補跑 `lms server start --port 1234` 才能用。玩完有停 server，沒有 unload 模型。
- DeepSeek 用 `deepseek-v4-flash`。它也會叫工具，回答比較乾脆，兩輪工具對話約 11 秒。

## 讀 README 之後以為的樣子

1. 一個世界就是一個資料夾，裡面的檔案就是狀態。
2. daemon 給每個世界一個鐘，每格重跑 `.aos/inst`。
3. agent 是五態狀態機，跟 LLM 靠 `requests/` 和 `results/` 排隊交接。

## 玩過之後實際的樣子

1. 世界真的就是資料夾。聊天、記憶、孩子和用量都能直接翻檔案看。
2. 鐘也真的各走各的。shared 小孩掛在父的 inst，own 小孩會多一個 daemon 鐘。
3. 整套很非同步。正常時順，壞掉時要一起看 agent state、LLM 佇列、daemon 鐘和多層 log。

## 每一步的結果

### 1. 讀 README

讀完 248 行。先得到上面三句心智模型。實際玩完後，大方向沒有猜錯。

### 2. 跑測試

`bash proto2/test.sh` 回 0。63 組場景，共 246 條檢查，全是 `ok`。
開跑前和跑完後的背景程序檢查也都是空的。

### 3. 複製範例

用 `git archive HEAD proto2/examples/llm proto2/examples/agent | tar -x` 複製。
落在指定 scratchpad。repo 裡的範例沒有變。

### 4. 起 kernel 和兩個鐘

kernel 起來了，pid 是 `2342326`。`ls` 最後看到 agent 與 LLM 兩個 running 鐘。
但緊接 start 的第一個 register 說「kernel 沒在跑，請求先放著」。下一格其實有處理成功。

### 5. 聊天、工具和生小孩

問「你是誰」有正常回答。`self_status`、`sh ls -la`、`say` 都真的有 tool call。
`said.txt` 正確寫入「整套試玩到這裡」。sharedkid 與 ownkid 也都真的建好。
ownkid 讓 `ls` 從兩個鐘變三個鐘。`kids_list` 能列出兩個孩子的 state、step、busy。

### 6. 手動放 team 信

手動放 `manual-team.json`，內容有暗號「藍色雨傘」。agent 自己醒來並連叫三個信箱工具。
信最後在 `inbox/team/read/`。agent 能正確回出暗號。

### 7. pause 和 continue

pause 後送一句。5 秒前後 outbox 都是 9 份，確實沒有回。
`ls` 顯示 agent 是 `paused`。continue 後回「已恢復」。

### 8. kernel stop 再 start

stop 後三個鐘都顯示 `stopped`。start 後三個鐘都換新 pid，自己接回來。
agent 還記得暗號、sharedkid、ownkid 和 `said.txt` 那句話。

### 9. 看狀態、用量和 log

`aos-llm ls` 能看 running、queued 和各 engine 額度。`aos-llm usage` 表格也好讀。
`aos-user status` 有 step、busy、uptime、記憶大小和用量，但沒有目前 state。
daemon log 有每格摘要。成功的 LLM worker log 全是 0 bytes。

### 10. 拔掉 LLM 的鐘

unregister 後送一句。6 秒沒有回，agent 的 `state.json` 是 `wait`。
`aos-llm ls` 清楚顯示 1 個 queued，但聊天端沒有任何提示。
register 回去後自動處理，回「LLM 已接回」。

### 11. 直接丟 request

丟 `direct-ask.json` 後有結果。從 tick 704 到 722，共 18 格，約 18 秒。
content 是「直接請求成功」。總共 1,177 tokens，其中 reasoning 是 1,154。

### 12. 收尾

最後 `aos-daemon-kernel stop` 成功。三個鐘都顯示 `stopped`。
`pgrep -f` 檢查 aos-llm、aos-loop、aos-daemon-kernel、aos-agent，結果是空的。

## 壞掉的

- 重現：kernel start 後立刻 register。看到：明明 start 成功，register 卻說 kernel 沒在跑；請求又在下一格成功。猜：start 太早回傳，CLI 的存活判定有競速。
- 重現：agent 很快拿走 LLM result。看到：agent 已拿到「打不通」結果，LLM 下一格又補成 `worker died`；用量變成 2 requests、2 errors。猜：consumer 刪掉 result，比 LLM 把 running 搬 done 更快，兩邊的結果所有權打架。
- 重現：LM Studio server 沒起來時聊天。看到：agent 從 wait 回 idle，但 outbox 沒錯誤；使用者只會等到逾時。猜：wait 的 error 分支沒有把錯誤送進 outbox。
- 重現：local 模型用 spawn 生 sharedkid。看到：工具成功，小孩也建好，但 outbox 的 content 是空字串。猜：模型工具後回空白，agent 沒擋空回覆或補一次。
- 重現：先用 local，再把 agent 換成 deepseek-flash 後叫 `self_status`。看到：「today_usage.total_tokens」只報 DeepSeek 的 3,814，沒含 local 的 61,758。猜：today_usage 只取目前 endpoint，名字卻像全日總數。

## 看不懂或跟 README 不一樣的

- README 說 LM Studio 要先載模型，但只跑 `lms load` 還是不通。還要另外起 API server。
- README 說單發錯誤可看 LLM `logs/<請求>.log`。這次連線失敗那份 log 是 0 bytes，細節只在 result。
- `aos-user status` 名字像會告訴我 agent 卡在哪，實際沒有 `state` 和目前 request。要自己開 `state.json`。
- shared 小孩跟父親共用一個 clock log。兩邊的 `aos-agent: step ...` 混在一起，行上沒有名字。
- `aos-daemon-kernel ls` 在 kernel 停掉後仍印舊 pid。雖然 state 是 stopped，第一次看會懷疑 pid 還活著。
- local 的 `ls -la` 只看世界根目錄，卻自己下結論「沒有 kids」。kids 其實應該看 `agent/kids/`。這是模型判斷差，不是工具沒跑。

## 好用的

- 資料夾介面很直白。queue、結果、記憶、信和孩子都能用普通工具檢查。
- `aos-llm ls` 很有用。故意拔鐘時，一眼就看出請求排著沒人做。
- pause、continue、stop、start 都真的有效。重啟後鐘和 agent 記憶都能接回。
- 工具包流程很順。local 和 DeepSeek 都能連續叫信箱、shell、self、kids 工具。
- shared 與 own 的差別能直接從父 inst 和 daemon ls 看懂。

## 如果我是使用者，最想先修的三件

1. 先修 result 被 agent 拿走後又被判 `worker died` 的競速。它會蓋錯誤、灌水用量。
2. LLM 失敗或沒鐘時，聊天端要直接顯示「卡在哪」。不要讓人只看到一直沒回。
3. 把首次啟動收乾淨。README 補 API server，kernel start 也要等到真的可 register 再回成功。
