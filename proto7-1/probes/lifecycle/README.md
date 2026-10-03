# lifecycle 探針

**是什麼**：D-3 的延伸。用五條時間線試任務生命週期上的四件事，tasks.json 本身沒有這些欄位：

- (a) 失敗後隔 N=3 回合重試，最多 M=5 次（前 2 次會失敗）。試兩種做法：`retry_self` 是 keep 任務自己數；`retry_sup` 是一個 keep 的小 kernel 讀 rounds.jsonl，再寫 `spawn/`。
- (b) `phoenix`：任務自己寫自己的 `ctl.json` restart，連續 3 代，新任務從 `restart_of` 接上一代的狀態。
- (c) `quit`：keep 任務想「別再起我」，試四種做法：rc=0 退出、寫標記檔、自己寫 ctl kill、自己把自己從 tasks.json 拿掉（兩個任務同時改）。
- (d) `crash`（interval 50 ms）：一起來就死的 keep 任務（rc=3），加上找不到程式的 keep 任務（127），跑 50 回合。

**結果**（跑了 3 次都綠，各情境數字穩定）：

- (a) 兩種做法都做得到，嘗試的回合都是 1、4、7（間隔剛好 3）。
  - 自己數：等重試的期間程序要活著空等 tock（2～3 個）。成功之後 keep 還是每回合起一個新任務，它看到 done 就退出，27 回合留下 28 個空殼資料夾。
  - 小 kernel：要整份讀 rounds.jsonl。`ended` 只有 `tid`／`code`，沒有 name，只能拆 tid 才知道是哪個任務。
- (b) 寫 ctl.json 之後，下一個 tick 就生效：在 tock R 之後寫，tick R+1 就 kill 舊的、在同一個 tick 起新的。restart_of 一路接得上，兩份不會同時活著。舊任務如果接住 SIGTERM，ended 的 code 是 0，看不出是被 restart 的，要回頭對 `ctl` 欄。
- (c) 只有改 tasks.json 有效。rc=0、標記檔、ctl kill 都擋不住 keep，29 回合各留下 29 個資料夾（D-3）。兩個任務在同一個 tock 讀—改—寫 tasks.json（讀和寫之間隔 30 ms）時，常有一個人的修改被蓋掉：被蓋掉的那個任務會被起回來，再改一次才真的停。
- (d) 沒有退避。52 回合 die、nobin 各 52 個資料夾，tasks/ 佔約 1.7 MiB 磁碟（內容只有 46 KB）。ended 每回合有 `die:3`、`nobin:127` 兩筆，code 看得到，但沒有地方累計「連續失敗幾次」。nobin 的 exit.json 帶 `error`。

**順帶**：寫探針時 `quit_edit` 有一個 bug（TypeError），每回合起一個就死一個，持續 31 回合，沒有任何東西發出聲音。這正是 (d) 的實例。
