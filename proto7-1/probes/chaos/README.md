# chaos 探針

**是什麼**：不用 LLM。決定性亂數（`--seed`，預設 7）同時高頻亂寫整個控制面，邊亂邊檢查不變式；另一段逐條試「一個壞輸入就弄壞基礎設施」的最小重現。

- **A 段（亂，12 秒；`--long` 60 秒）**：6 條時間線＋會被 rm -rf 再重建的 `eph`＋假子 daemon 根 `sub/`（只有 `.aosd/`，底下有 node `sub/x`）。亂源每 3～12 ms 做一件事：daemon ctl（合法／不認得的 op、壞 JSON、`[]`、同一批 pause+resume+wake、resume rounds 合法與不合法、對不存在／子 daemon 底下的 node）、tasks.json（keep/each、max_live、from_round、壞欄位、整份壞）、timeline.json（壞 interval、拿掉再寫回）、spawn（單一、batch、壞檔）、任務 ctl.json（kill/restart/壞的，對活的或已結束的）。任務本身也亂（[task.py](task.py)：立刻死、不理 SIGTERM、留孫程序、雙 fork、刪自己的 taskdir、等 tock、亂請加掛）。亂完寫回正常設定、resume 全部，再查；最後 stop --kill 查殘留。
- **B 段（最小重現）**：每條一個最小輸入，記「重現了沒」與證據。現在會壞的記成量，不放 check。
- `--poison`：A 段也混進 B2、B4 的毒輸入；`--no-a`／`--no-b` 只跑一段。

**想讓基礎設施露出**：控制面同時被亂寫時，daemon、tick、tock 的不變式守不守得住；哪一種單一壞輸入就能弄壞一條線或整個 daemon。

## 結果

A 段 seed 1～5、7、11（含一次 60 秒、一次 `--poison`）全綠。一次 12 秒約 1700 個動作，搬到 tasks-old 的任務約 650～800 個。守住的不變式：

- daemon 不退出，status.at 最長停 30～60 ms。
- 每個 node 的 round 不倒退。
- rounds.jsonl 不重號、嚴格遞增；ended 沒有重報。
- 每個唯一名字的 daemon 控制檔都恰好處理一次；ctl/ 最後清空。
- 對 `sub/…` 的 pause/resume/wake 都回 ok:false；`sub/x` 父 daemon 不跑。
- 收斂後任務 ctl.json 都執行了。
- 停機後 round.json 已關，而且等於 rounds.jsonl 最後一行。
- tasks/ 與 tasks-old/ 的 tid 不重複；rm -rf 的 node 不被建回來。
- stop --kill 約 1 秒；殘留只有 Q1 (a) 說的「任務自己負責」那幾類（已結束任務的孫程序、雙 fork、刪了自己 taskdir 的任務和它的 aos7-run）。

| 量（seed 7，12 秒） | 數字 |
|---|---|
| rounds.jsonl 缺號（有 tick 沒 tock 的回合） | 6～14（每次 21～25 次「timeline.json 拿掉再寫回」；60 秒版 57） |
| tasks/ 裡沒有 birth.json 的空殼 | 0～1（亂源對剛被搬走的任務寫 ctl.json，write_json 把資料夾建回來；之後永遠沒人處理） |
| 收斂所需 | 0.3～1.3 秒 |

**B 段**（全部重現；檔名、函式見下方「建議修法」）：

| 編號 | 一個壞輸入 | 結果 |
|---|---|---|
| B1 | 新出現的 node，`round.json` 是 `[]` | **daemon 整個退出**（rc 1，`Timeline.__init__` 的 `.get` 丟 AttributeError，`guard` 只接 OSError）。其他 node 的任務變孤兒 |
| B2 | tasks.json 一項 `"name": 5` | tick 每回合丟 TypeError（`new_tid` 的 re.sub），同 node 的好項目永遠起不來。「壞的一項只跳過那項」沒做到 |
| B3 | spawn 檔 `{"name": ["a"], ...}` | 毒丸：tick 例外，spawn 檔不刪，之後每回合都在同一處死，整條線不再起任何任務 |
| B4 | argv 有非字串（`["sleep", 5]`） | aos7-run 在 Popen 丟 TypeError（stderr 進 /dev/null），沒有 pid.json 也沒有 exit.json，**永遠算 born＝活**：keep 不再起、tock 不提前、kill 每個等 1 秒回「no pid.json」。第一次跑時探針自己的 argv 帶了數字：約 200 個幽靈任務，**stop --kill 超過 15 秒停不下來** |
| B5 | `.aosd/ctl/d.json` 是資料夾 | 每圈「處理」一次（ctl-done 寫了、rm 不掉），log 每秒灌約 50 行 |
| B6 | `round.json` 的 round 改成字串 | 下個 tick 從 1 重數，rounds.jsonl 出現重號 |
| B7 | 任務改自己 pid.json 的 pgid | kill 照 pid.json 打到別人的程序群組（被害的 `sleep` 收到 SIGTERM） |
| B8 | 回合中拿掉 timeline.json、等 node- 後放回 | 那一回合永遠沒有 tock（rounds.jsonl 缺號）；新時間線直接開下一回合 |
| B9 | `interval_ms: -5`（或 0） | 默默當 1 ms 全速跑，不記 last_error |
| B10 | `.aosd/ctl/f.json` 是 FIFO | **daemon 主迴圈卡在 open()**：status 停更，之後的控制檔（含 stop）都不處理；刪掉 FIFO 也解不開（open 已卡在那個 inode 上；SIGTERM 推測也會被 PEP 475 重試吞掉，沒實測）。時間線照跑 |

## 建議修法（最簡單、不碰核心語意）

1. **B10、B5（同時順手解 tasks.json／ctl.json／spawn 是 FIFO 時 tick 卡到動作逾時）**：`aos7_fs.read_json` 改成 `os.open(path, O_RDONLY | O_NONBLOCK)`，`fstat` 不是一般檔就回 default。`Daemon.handle_ctl` 只處理 `os.path.isfile` 的名字；非一般檔改名到 `ctl-done/<名>.bad`（rename 對資料夾、FIFO 都行），回條記 `ok: false, "not a regular file"`。
   測試：ctl/ 放 FIFO 與資料夾各一個，1 秒內 status 還在動、後面的 pause 生效、log 該名字只出現一次。
2. **B1**：`Timeline.__init__` 讀 round 照 `disk_round` 的寫法（不是 dict、或 round 不是 int 就當 0）。另外 `Daemon.guard` 也接 `Exception`：記 `io-error`（或新的 `ev: "error"`）然後下一圈再試，主迴圈不因一個 node 的壞檔退出。
   測試：新 node 的 round.json 是 `[]`，daemon 活著，那條線從第 1 回合起。
3. **B2、B3、B4（同一個修法）**：`aos7_tick` 抽一個 `validate(item)`，tasks.json 與 spawn 都用：
   - name 有寫就要是非空字串；
   - argv 要是**字串**陣列（不含 NUL）；
   - 沒有 argv 時 inst 要是字串；
   - mounts 交給 `aos7_mount.check`。

   spawn 迴圈每個項目各自 `try`，壞的記在 `tasks_error`（例如 `spawn x.json: name 要是字串`），**檔照刪**。保險起見，`start_task` 用 `item_name(item)` 而不是 `item.get("name")`；`aos7_run.main` 把 build_argv＋Popen 的 `except OSError` 放寬成 `except (OSError, TypeError, ValueError)`，照樣寫 exit.json code 127。
   測試：(a) tasks.json `[{"name":5,…}, good]` → good 起、tasks_error 有一條；(b) spawn `{"name":["a"]}` → 檔刪掉、錯有記、同 node 的 keep 照起；(c) birth.json 直接寫 `argv: ["sleep", 5]`（繞過 tick 驗證）→ 很快有 exit.json code 127、不算活。
4. **B8**：`Timeline._loop` 開頭（或 `__init__`）看到 round.json `open: true`，先跑一次 tock 把它關掉（`AOS7_INCOMPLETE=gone`，總結標 `incomplete: "gone"`）再 tick。tock 本來就會對 `open: false` 回 skipped，重複也安全。
   測試：回合中拿掉 timeline.json、等 node- 後放回，rounds.jsonl 不缺號，那一行有 `incomplete`。
5. **B6**：tick 讀 round.json 的 round 不是 int 時，改讀 rounds.jsonl 最後一行（`tail_jsonl`）的 round。都沒有才從 0 開始，並記 `tasks_error`／last_error「round.json 壞了，從 N 接」。
6. **B9**：`Timeline.interval` 把 `ms < 0` 也當壞值（用預設、記 last_error）。0 要不要合法（「盡快」），看下面。
7. **空殼資料夾**（A 段）：可以不修；或在 `list_tasks` 的消費端忽略。要修就讓 tock 把 `tasks/` 底下沒有 birth.json、又超過 N 回合的資料夾也搬到 tasks-old。

## 〔要使用者決定〕

- **B7 任務能不能指揮 kill 打誰。** pid.json 放在任務自己寫得到的 taskdir 裡，kill 照它的 pgid 送訊號。改了 pgid 的任務，kill 就打到別的程序群組，包括 daemon 自己（daemon 起在自己的 session，pgid＝pid）。權限是核心列為「之後再說」的事，所以列出來。
  - (a) 照現在：spec 寫明「pid.json 由 aos7-run 寫，任務改它後果自負」。
  - (b) kill 前驗證：pgid 群組裡至少有一個程序的環境變數 `AOS7_TID`＋`AOS7_NODE` 是這個任務，不合就拒絕（`ok: false, "pid.json 不像這個任務"`）。成本是每次 kill 多掃一次 /proc，探針等級可接受。
  - (c) pid 不放 taskdir，改放 daemon 自己的 `.aosd/pids/<node>/<tid>.json`（任務碰不到）。改動較大，也碰到 Q1「不靠任務能刪的目錄」。
- **`interval_ms: 0` 合不合法**（B9 的延伸）。現在 0 與負數都變 1 ms，等於「每回合一結束就馬上下一回合」。
  - (a) 0 合法，意思是「不等」；負數算壞值。
  - (b) 0 與負數都算壞值（用預設 1000）。

## 修補之後（10-03）

B1～B10 都照上面「建議修法」修了（B7 選 (b)：kill 前驗證 pgid 屬於這個任務；`interval_ms: 0` 選 (a)：合法，負數算壞值）。細節在 infra-needs N-56～N-63，測試在 `tests/test_wave2.py`。probe.py 的 B 段改成 check「修補後不再重現」，全綠。A 段的 rounds.jsonl 缺號也跟著變 0（B8 修好的效果）。空殼資料夾那條沒修。
