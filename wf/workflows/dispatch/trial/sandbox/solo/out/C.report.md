C-01,L1,bug,3,步驟1 首次run,用絕對路徑呼叫aos時內部agent也應啟動或外層明確失敗,PATH不含build/bin時9回合皆在state.json顯示子步驟exit 127但run.log仍列turn 1至9且run exit=0,pi -p只需1個前台指令並於62秒exit 0且不再派裸aos子程序,repro/C-01.sh
C-02,L1,awkward,2,步驟1 忙碌狀態,一個狀態指令應同時顯示任務內容、模型或工具階段、已跑與剩餘回合及本回合耗時,12次採樣出現全部status值idle、thinking、tool、running、done；running連續0至40秒後又以done保留至少10秒；aos state無剩餘回合與當前耗時且完整回答現在在幹嘛最少需aos state、cat state.json、tail log.md共3指令；run.log只事後顯示turn 3: 1 insts (1 every) 25443 ms等行,pi -p只需1指令但實測62秒中前46秒也是0輸出且完成時才顯示結果,-
C-03,L1,bug,3,步驟2 Ctrl-C,Ctrl-C應停止整棵run行程並留下可辨識且可接續的中斷狀態,20秒送SIGINT後3秒aos state仍為thinking turn 19且batch/19只有insts；精確檢查有1個aos agent step孤兒；它約12秒後自行產生out並跑完至turn 27；重開run由turn 28開始且沒有上次中斷提示,pi前台20秒Ctrl-C立即exit 1且0孤兒；1個pi --continue -p指令在12秒內沿用74560-byte session,repro/C-03.sh
C-04,L1,awkward,1,步驟3 listen跟讀,不帶--once的跟讀應只顯示新內容或清楚區分重播模式,timeout 1 aos listen先從turn 1完整輸出355行17341 bytes再因持續輪詢exit 124；內容與log.md逐byte相同；listen --once也完整輸出355行但exit 0,pi隔天以1個pi --continue指令載入最近session；aos看昨天紀錄也可用1個listen --once或cat log.md,-
C-05,L1,bug,2,步驟4 talk無runner,talk應自行推進agent或立即提示必須另開run,echo 你好管入talk後等滿120秒仍exit 124且talk.log為0 bytes；state維持idle turn 36；訊息卻留在.aos/agents/ws-lm/say/1788090418004406662-3281523-0.md共6 bytes,pi -p以1個指令完成請求；本次詳細計畫62秒正常exit 0,repro/C-05.sh
C-06,L1,bug,1,步驟4 talk pi介面,不支援的--interface pi應依文件清楚說明尚未內建,timeout 120 aos talk --interface pi於0秒exit 2且唯一輸出為usage: /home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos talk,直接pi -p為1個可用指令；本次62秒產生完整計畫且exit 0,repro/C-06.sh

敘事報告

劇本 0–5 全部走完，兩個引擎都實際跨乾淨 shell。最痛的是狀態與中斷：有效 LM 任務用 `say`、`run` 共 2 個 aos 指令，等 9 回合約 43 秒；觀察又打 12 次 `state` 與 24 次 `cat`，共 36 個診斷指令、採樣 60 秒。五種 status 分散在不同檔案且快照互相落後，`running[]` 完成後仍留 done。直接 `pi -p` 只需 1 指令、62 秒，但前 46 秒也完全安靜。

LM 的 Ctrl-C 在 20 秒時只殺掉 timeout；3 秒後仍有 1 個孤兒，未完成的 turn 19 只有 insts，之後孤兒又把 turn 19–27 跑完。直接 pi 在 20 秒 Ctrl-C 後立即 exit 1、無孤兒，再用 1 個 `pi --continue -p`、12 秒便接回 74,560-byte session。

記憶兩邊都可靠。LM 換 shell 後用 `say`＋6 回合 `run`＋`listen --once` 共 3 指令、10 秒，正確列出前三次請求；`history.json` 由 16,626 增至 18,190 bytes。aos 的 pi 引擎首輪 1 回合 16 秒，換 shell 後 1 回合 3 秒也答對；pi session 位於 `~/.pi/agent/sessions/...f5483b63...jsonl`，23,849 bytes，session_id 確實沿用且無失憶警告。兩者看昨天對話都只需 1 指令，但 `listen` 會先重播全部 355 行。最後 `talk` 無 runner 時 120 秒零輸出，`--interface pi` 又只回 usage，容易讓人誤判工具已死。