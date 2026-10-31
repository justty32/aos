← [入口](../2026-10-21-ideas.md)｜涵蓋：9. 設定檔是唯一的位置參數、`$path` 改字串拼接（10-21 傍晚） › 9.3 頂層自定的細節（使用者可翻案）｜上一份 [06-9-設定檔是唯一的位置參數-$path-改字串拼](06-9-設定檔是唯一的位置參數-$path-改字串拼.md)

### 9.3 頂層自定的細節（使用者可翻案）

翻案就改 [N-45](../../docs/NORMS/06-基礎設施-命令列與指示詞.md)、[N-28](../../docs/NORMS/04-基礎設施-loop與daemon.md) 與對應的程式。

1. **設定檔指標的規則同 aos-exec 的入口路徑**（N-62）：第一個 `#` 就切、`#` 後面要是 `/`，不然＝自己的錯（不是 usage 錯）；指不到、讀不到、不是 JSON、那個位置不是物件＝自己的錯、退 1。不補 `.json`、不跳過 `#!` 行（那是 aos-exec 找入口的事）。讀設定檔放在共用的 `aos_flags.load_cfg()`。
2. **usage 錯的範圍**：沒給設定檔、多給位置參數、不認得的旗標（含 `--cfg`）、旗標缺值；`--max=abc` 這種旗標值不對是自己的錯（不是 usage）。
3. **`run`／`val` 陣列**：空陣列、元素不是字串＝自己的錯（loop／daemon 的 run）或表壞（fsm 的 val）；跟物件那條共用一句「要是 aos-exec 的目標（字串）或 [目標, 參數...]（非空字串陣列）」，物件那條多提一句「要內嵌單子寫 `loop.json#/body`」。fsm 物件 val 的訊息固定寫 `fsm.json#/states/<名>/body`。
4. **fsm 目前沒有旗標**：旗標表是空的，仍走 aos_flags（所以 `--` 結束旗標、`--cfg` 這種不認得的旗標＝usage 錯）。
5. **daemon 經 aos-exec 的做法**：小格的 `loop.json`＝子項設定＋`ctl`／`state`（沒寫才補）＋**一律蓋上** `"_exec": ["aos-loop", {"$env": "AOS_CF"}]`；起 `aos-exec -- 小格/loop.json#/_exec`——要指到 `#/_exec`、不寫 `小格/loop.json`，daemon 的環境帶別的 `AOS_ENTRY` 時才挑得到。子項自己寫的 `_exec` 會被蓋掉。aos-exec 是 exec 成 aos-loop（argv 陣列那條），pid 與啟動時間不變，接回（adopt）照舊。
6. **daemon 子項的相對路徑**：子 loop 經 aos-exec 起之後 cwd 是小格，所以 **daemon 寫小格時把子項 `run` 的目標（字串本身、陣列的第一個元素）照 daemon 的 cwd 轉成絕對路徑**，其他 key 不動、不驗（寫錯由子 loop 自己退 1）。[計畫](../2026-10-21-plan.md) D3「子項 `run` 相對路徑從 daemon 的 cwd 算」照舊成立。
7. **daemon 子項名字不能帶 `#`**（小格路徑會交給 aos-exec，`#` 會被當成指標的開頭），也不能帶 `/`、不能 `.` 開頭。
8. **`$path` 的邊緣**：`$path` 是空字串＝不接（值原樣）；只有 `#`＝照規則直接接（`/x/a.json#`，交給用的人去報錯）；基底是空字串或 `/`＝照規則接成 `/a`（去掉結尾的 `/` 後是空的，中間仍補一個 `/`）；`$path` 是 `/`＝基底後面接一個 `/`；`$path` 結尾的 `/` 不動。基底結尾、`$path` 開頭的連續好幾個 `/` 都去掉。
9. **demo**：bob、cathy 的 `_exec`＝`exec aos-loop loop.json`；ann 的 `_exec`＝`exec aos-exec loop.json`、`loop.json` 帶 `_exec`；daemon 的 `_exec`＝`exec aos-daemon daemon.json`；`fsm.json` 的 `_exec` 是 `["aos-fsm", {"$env": "AOS_CF"}]`。daemon.json 內容不用改（子項 run 由 daemon 轉絕對）。大 JSON 指標的寫法只在測試裡用（`test_loop.py` 的 `test_aos_exec_big_json_pointer`）。
