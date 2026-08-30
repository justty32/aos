報告已寫入 [report.txt](/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/wf/workflows/dispatch/trial/sandbox/solo/B/report.txt)。

### 第一段：發現表

```csv
B-01,L1,bug,3,劇本1 推進第1個run,以指定AOS絕對路徑呼叫即可推進agent或明確失敗,未加build/bin到PATH時外層exit=0；子程序exit=127且stderr長度0；run只印turn 1: 1 insts (1 every)，0 ms,直接pi用1個pi -p且不依賴aos是否在PATH,repro/B-01.sh
B-02,L1,awkward,1,劇本1 開機第1個指令,init後立即看見引擎設定與所需憑證名稱,agent init stdout為0行；只能再cat engine.json才看到provider=deepseek與model=deepseek-v4-flash及session_id；沒有DEEPSEEK_API_KEY提示,直接pi用1個pi -p；另打1個pi --help可看到DEEPSEEK_API_KEY,-
B-03,L1,awkward,2,劇本1 交代任務第2至4個指令,投遞後state或listen應顯示有待處理訊息,投遞前後state都為status=idle與turn=0且updated_at同為2026-08-30T11:35:38Z；listen --once輸出0行,直接pi把提示放進1個pi -p便立即執行,-
B-04,L1,awkward,1,劇本1 推進背景觀察,執行中能看見正在跑pi及目前工具或進度,背景PID仍存活時state只顯示status=thinking與detail=處理本回合及turn=2；run1.log完成前沒有工具進度,直接pi -p重導至log時也沒有終端進度且本次沉默62.313秒,-
B-05,L1,awkward,2,劇本1 檢查history與追問,世界內鏡射應完整或清楚指向完整記憶,history.json為3602 bytes且只有8則最終訊息；同session_id的~/.pi/agent/sessions/--home-lorkhan-repo-simple_tools-aos-.claude-worktrees-agent-a4b6627dc8a8b1254-wf-workflows-dispatch-trial-sandbox-solo-B-mini--/2026-08-30T11-36-46-825Z_a6e30364-ced1-4a72-97cd-e7b693937dfb.jsonl為32743 bytes及32則message並含15個toolResult；listen只有工具參數摘要沒有輸出,直接pi用1個pi -c -p續談且完整歷程只落在同一個105942-byte session檔,-
B-06,L1,awkward,2,劇本1 工具登記表,相對路徑.aos/tools應指目前B世界且工具概念單一,B世界實測只有cat.json與ls.json及sh.json三檔；pi卻cd到repo根.aos/tools後回答aos與cat及git及ls及sh五個並另稱自己實際用read與bash及edit及write；乾淨重跑則答對三檔顯示判定不穩定,直接pi的pi --help一次列出單一組內建read與bash及edit及write工具,-
B-07,L1,awkward,2,劇本1 完整操作與指令數,包裝pi後仍能用接近單一命令的操作完成工作,初次結果最少要agent init與say及run及listen共4個aos指令；全劇本實打19個aos指令且因PATH問題多1個失敗run與1個探針state,直接pi初次工作1個pi -p；追問再1個pi -c -p,-
B-08,L1,awkward,1,劇本1 pi對照計時,直接pi對照應與aos內pi使用相同provider與model,engine.json是deepseek/deepseek-v4-flash且有效step耗時17.838秒；裸pi session卻是openai-codex/gpt-5.6-sol並耗時62.313秒；另用相同DeepSeek模型實測15.529秒,顯式指定相同provider與model仍只需1個pi指令且比aos本次少2.309秒,-
```

### 第二段：敘事報告

劇本走完步驟 0–7。aos 的 pi agent 啟動後，一個有效 step 就改完四檔，`make` 為 `ok`；兩輪追問也記得前次改動，同一 pi session 從 23,711 增至 27,604 bytes。最痛的是首個 run：使用者雖照規定走 `$AOS` 絕對路徑，排程仍呼叫裸 `aos`；PATH 沒加 build/bin 時子程序 exit 127，外層卻 exit 0 且無錯誤文字。

完整 aos 劇本實打 19 個 aos 指令，等 4 個有效 pi 回合加 1 個 0 ms 失敗回合；有效 run 合計 29.891 秒。只看初次改函式，最短仍是 `init → say → run → listen` 4 個指令、1 回合、17.838 秒。直接 pi 初次只需 1 個 `pi -p`，追問再 1 個 `pi -c -p`；裸 pi 初次 62.313 秒、追問 10.394 秒，但用的是 gpt-5.6-sol，不能跟 aos 的 DeepSeek 直比。同模型直接 pi 是 1 個指令、15.529 秒，比 aos 少 2.309 秒。

包 aos 換到世界內訊息佇列、turn/state/log 與自動續用 session ID；背景 probe 至少看得到 `thinking`。代價是手動編排、PATH 陷阱、模糊狀態，以及兩套記憶和工具。history 只有最終對話，完整 toolCall/toolResult 另落在 `~/.pi/agent/sessions`；工具題還曾讀到祖先世界五個登記檔，而非 B 世界三個。不知道 session ID 對應路徑時，很難判斷真正記憶在哪。