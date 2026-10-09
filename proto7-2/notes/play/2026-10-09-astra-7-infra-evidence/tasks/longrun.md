# 子線 longrun：全套一次＋step 450 回合＋adapt 320 回合長跑＋核心行數＋lib 歷史

你的線名 `longrun`，evidence 目錄 `proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/longrun/`。上一輪同類探針在 `proto7-2/notes/play/2026-10-04-astra-6-infra-evidence/regression/`（run_suites.py、step/）與 `.../adapt/`（long320），可複製到你的目錄改用，不要改原檔。

**注意負載**：另一隊同時在主 repo 跑全套 ×3。你這條線**一次只跑一樣重東西**（全套、step 長跑、adapt 長跑循序，不並行）。

1. 全套一次：`systemd-run --user --scope -q -p TasksMax=800 -p RuntimeMaxSec=1800 python3 proto7-2/tests/run_all.py -v`，記測試總數（unittest 尾端 Ran N）、rc、耗時、失敗／錯誤／skip 清單與原文。若有紅：單跑該案 3 次判斷是否時序不穩（decisions 檔已記 `test_diag.test_unsure_listed`、subd `test_allow_stop_writes_stopped_and_parent_does_not_restart` 在負載下偶紅——再出現就照實記次數）。§7 說預期約 400 項，記實際數。
2. step 長跑：真 daemon、step 包 CSV convert→stats→end（或等效）`restart_on_end:true`，跑到 round≥450 已關；核每個完成快照正確、attempt=1、halt／error=0、槽與工作資料夾檔名集合不長（含隱藏檔、含 tmp）、`frame.resends` 等新欄不累積。順便抽 daemon RSS／fd 數頭尾比。
3. adapt 長跑：真核心 tick/tock（或真 daemon）從 r1 再跑 320 回合，每回合核暫存器與檔名集合不變。
4. 核心行數：跑 `tests/core/test_budget.py`（D7 後只印不擋）記印出的總行／程式行；與 astra-6 的 2757／2123 比，列各 lib 檔行數變化（`git diff --stat 510dd134..HEAD -- proto7-2/lib`）。
5. 長跑額外觀察：nodes.json 是否殘留 `reaping` 鍵、paused.json 是否多出 `steps` 欄且長跑後狀態合理、`.aosd/` 檔案集合不長。
