# daemon SIGKILL／重開實驗

入口順序：只讀 `README.md` → 其連結 `spec.md`，據此編寫 `probe.py` 和任務；實验完才讀 `notes/problems.md`、`notes/problems-core.md`、核心 `core.md` 比對。未讀產品原始碼。

重現：在 repo 根執行 `python3 proto7-1/notes/play/2026-10-03-astra-evidence/restart/probe.py`。脚本建立獨立 `/tmp/astra-restart-*` 根，live／paused 兩 node 都跑 500 ms 時間線和一個 keep worker；worker 每次收到不同 tock 就追加 observed.jsonl。以 JSON 控制 pause 第二條線；等待 live 第 4 回合開啟，對 daemon 送 SIGKILL，等 0.8 秒，再對同一根啟動新 daemon。第 8 回合寫 stop＋kill 控制檔。最後清理程序。

## P-08／P-04 的新證據：接續數字並不補結束被打斷的回合

分類：〔技術選型〕。S-06、S-08、S-11。既有 P-08 說 round 接著數，P-04 說 SIGKILL 會留孤兒；本次補到「重開後跳過尚未 tock 的回合」這項後果，不另重報孤兒本身。

實測舊 daemon PID 749764、重開 PID 749835。live 第 4 回合 `open:true`、`tock_at:null` 被中斷；重開直接開第 5 回合，最終 rounds 檔名為 1、2、3、5、6、7、8，沒有 4，worker 的 observed.jsonl 同樣由 3 跳到 5。第 4 回合的 open 標記被第 5 回合覆寫，也沒有額外 aborted/recovered 紀錄。若只看當前 round.json，已看不到曾留下未收尾回合；需對照 rounds 缺號與 daemon log。

正面證據：worker 始終為 worker-r1（PID 749774，runner PID 749771），沒有多啟動一份，重開後收得到 tock；paused.json 持續記住 paused，重開後 paused node 仍停在第 1 回合。正常 stop＋kill 最後 status 裡兩 node 的 live 都空。

主要證據：01-before-kill.json、02-after-kill.json、03-restarted.json、04-stopped.json、outcome.json。各 snapshot 為「相對路徑 → 原始檔案文字」的 JSON，保留全部控制與回合檔。

## S-01 邊界：status.json 是快照，不是 daemon 存活證明

分類：〔技術選型〕。S-01、S-03、S-06。

SIGKILL 0.8 秒後 `.aosd/status.json` 內容一字未變，仍是舊 pid、`stopping:false`、live phase tick、兩 worker 活著。`at` 可以提醒讀者資料可能陳舊，但只 cat 一次不能判定 daemon 活著或死了；daemon 的存活要跨到 Linux PID／`/proc`，或隔一段時間重讀來判斷。這個結果不是要求 SIGKILL 前能寫 shutdown 狀態，而是指出「可讀快照」不能獨立回答完整存活問題。README/spec 沒有 crash 後如何判定與恢复的操作範例。

本次程序操作由測試脚本完成；日常 pause、stop 全部以 spec 記載的 JSON 原子寫入完成，不需要 aos7-ctl，也不需要看程式。S-01 檔案操作介面成立，啟動和強制殺 daemon 本來就在 S-03 的 Linux 邊界。

## 對 D-1～D-4 的可用證據

本子實驗不提供 D-1、D-3 新證據。D-2：已有 worker 不列入本回合 started，即使 interval 500 ms，第 2 回合 tock 距第 1 回合 tock 僅約 35 ms（首次回合等活任務到 interval，下一回合空 tick 很快 tock），觀察到的回合脈衝不均勻。這是既有 D-2 的具體數據，非新問題。D-4：被 pause 的 node 經 daemon SIGKILL／重開仍維持 pause；若 pending 任務控制原本在等 resume，重新啟動 daemon 本身不應被當成解除 pause 的操作。本實驗沒有另外注入 paused 任務 ctl，不把後句當成已實測結果。
