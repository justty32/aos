# proto5.1 重審（fable，2026-09-22）

← [proto5.1 README](../README.md)｜前提：[23 題拍板](../../proto5/notes/2026-09-22-decisions.md)｜對照：[findings #1～#44](findings.md)、[stage4-report](stage4-report.md)

## 1. 一句話總評

骨架站得住：「runner 先寫 busy 再讀目標、kernel 先撤槽再看 run.json」的防重疊推論我重推一遍是成立的，佇列短鎖＋inode 核對丟遲到回覆也對；但有兩個真實使用一定會撞到的坑——**daemon 死了 runner 不會死、重啟後同一個 agent 跑兩份**，以及**一份壞請求就讓整顆共用 CPU 永遠停擺、連帶 agent 永遠等**——回流 proto5 前要補；其餘是可拿掉的欄位、幾處規範措辭與三種不一樣的錯誤回音長相。

## 2. 必須處理的坑（依嚴重度）

**R1 daemon 非正常退出 → runner 變孤兒 → 重啟後同一槽兩支 runner，同一個 agent 家被兩個 aos-agent 交錯寫。**
- 在哪：`aos_daemon.py:193`（runner 用 `start_new_session=True` 起，daemon 死它不死）；`aos_kernel.py:410-418`（daemon 表裡沒 entry 就直接 add 新 runner）；`aos_kernel.py:428`（判 daemon 在不在只看 state.json 的 `pid` 欄，不驗活）；daemon-home.md 只寫「不收養」。
- 怎麼觸發：daemon 跑前景，關終端／SSH 斷線就吃 SIGHUP 死掉；或 kill -9、OOM、Python 例外。之後使用者照常 `aos-daemon`＋`aos-kernel boot`。
- 後果（實測）：kill -9 daemon 後 kernel runner 與 CPU runner 都活著、照舊每秒跑；重啟＋boot 後 `cpus/0.json` 上 **兩支 aos-run 同時跑**；`ctl stop` 只收得掉新的兩支。agent.md 明寫「同一個 agent 不要同時跑兩份」，這裡就會兩份，state.json／history 用固定 `.tmp` 名互撞。
- 最小修法：aos-run 帶 `--home` 時記下啟動時的 `os.getppid()`，每圈比對，變了就當收到第一次 TERM（做完本次就停）——不用掃 pid、不怕 pid 重用，幾行。雙保險：daemon 啟動時掃 `runners/*/run.json` 的 `pid` 還活著就拒絕起（AlreadyRunning），run.json 的 `pid` 欄就有用處了。

**R2 一份壞請求（或壞的 running 檔、或結果寫不進去）讓整顆共用 CPU 永遠停擺，連收屍都停；kernel 十次退 1 後把 CPU 行程退件，之後所有靠這顆 CPU 的 agent 永遠 101。**
- 在哪：`aos_cpu.py:156`（認領前 `_request` 讀驗失敗直接把 AgentError 丟出 tick）、`:134`（收屍同樣）、`:139/:177`（`_write_result` 的 OSError 沒接，結果目錄不在就炸）；llm-cpu.md §2「壞 payload 在認領前退 1、原檔保留」；kernel `bad_after=10`。
- 怎麼觸發：requests/ 或 running/ 有一份 JSON 壞掉、`model` 不是字串、人手放錯檔、舊版 agent 送的格式；或 agent 家被刪掉而請求還在 running（reap 想寫結果寫不進去）。
- 後果（實測）：a.json 壞 → 每次 tick 丟 EngineInvalid，排在後面的 b.json 永遠不被認領；把 a 搬到 running 也一樣（收屍停擺）。沒有任何 timeout 會救：agent 等結果沒上限（拍板「waits 期限這輪不做」），收屍要有人 tick，而 tick 的行程已被 kernel 搬進 `procs/bad/`。
- 最小修法：鎖內讀驗失敗的檔搬到 `bad/<name>.json`（或 rename `.bad`）並印一行 stderr，繼續處理下一份，tick 最後照樣退 1 讓人看到。結果寫不進去（OSError）也照樣把請求搬 done 不留 running。順手可統一成一條規則：**能讀出 result 路徑的壞 payload 一律認領後寫 `ok:false`**（tool cpu 已經這樣，findings #20），llm 的 `_validate` 搬進 execute，`tick` 的 `validate` 參數就能拿掉。

**R3 `hold` 搭 `--interval-ms 0` 是忙迴圈：100% CPU、run.json 每圈重寫。**
- 在哪：`aos_run.py:106-108`（`save(held=True)` 後 `_sleep(0)` 立刻回來 `continue`）；aos-run.md「hold：每個 interval 再看一次」在 interval 0 時等於沒間隔。
- 怎麼觸發：測試與 stage4 都用 interval 0；有人寫 `{"op":"hold"}`。
- 後果（實測）：aos-run 102% CPU，0.2 秒內 run.json 換了 10 次 mtime。
- 最小修法：hold 期間固定睡 50 ms 再看（跟 `_sleep` 的步進一樣）；`held` 只在由 false 變 true 時寫一次。

**R4 aos-run 被 KILL 但子程式在別的 session 活著；kernel 看 entry 不見就重建 runner，與孤兒子程式重疊。**
- 在哪：`aos_daemon.py:224`（只 KILL runner group）；`aos_kernel.py:410-418`。
- 觸發：非 kill_tree 下子程式不理 TERM、runner 撐到 10 秒被 KILL 後又 add；或 OOM 專挑 aos-run。發生率低。
- 後果：舊 run.json 停在 `busy:true`，但 entry 沒了就不擋任何人。
- 最小修法：規範明寫這在保證外；真要擋，run.json 多一格 `child` pid，kernel 重建前 `kill(child,0)` 還活就不排。

## 3. 建議更好的做法

**R5 run.json 加一格 `last_target`。**〔回流前〕現在：kernel 只在 busy=false 且 target 對得上時才算一次結果，interval 小就整段漏看（findings #41）。建議：runner 完成時同時寫 `last_target`，kernel 用 `last_target` 對帳，busy 時也能算。代價：一格欄位＋kernel 三行；不動拍板的順序推論。

**R6 daemon 閒著也每 20 ms 重寫 state.json。**〔回流前〕現在：`aos_daemon.py:293` 主迴圈無條件 `save()`（實測 0.5 秒 20 次 mtime）；`add`／`reap` 本來就各自存。建議：主迴圈那行拿掉，只在變動時寫。代價：零。

**R7 kernel 每格把所有排隊中的 `procs/*.json` 重解、重寫。**〔回流前〕現在：`aos_kernel.py:365` 對每個未指派行程 `_write(path, raw)`，一秒一次，人手正在編輯的檔會被蓋。建議：add 時固化一次；tick 只讀驗，內容跟固化後相同就不寫。代價：多一個相等比較。

**R8 三種失敗回音長相統一。**〔回流前〕現在：CPU 結果 `{"ok":false,"error":"..."}`、daemon `{"ok":false,"result":{"code","msg"}}`、kernel syscall `{"ok":false,"code","msg"}`。建議：一律 `{"ok":false,"code":"代號","msg":"白話"}`；CPU 結果多個 `code`（`Reaped`／`UnknownModel`…），agent 就不必用「error 字串精確等於某句中文」來認結果不明（`aos_agent.py:243`）。代價：agent 兩行、spec 三處。

**R9 三個家長相對齊。**〔回流前〕現在：agent／cpu／kernel 有 `info.json`＋`_metainfo`，daemon 家靠「有 requests/done 兩個目錄」認；kernel 找 daemon 靠環境變數 `AOS_DAEMON_HOME`，K 裡不記，換個 shell 跑 `aos-kernel ls` 就對到 `~/.aos-daemon`；kernel rm syscall 用 `pid` 放的是 NAME，state `cpus.N.pid` 也是 NAME，而 run.json 的 `pid` 是 Linux pid。建議：daemon 家也給 `info.json {"_metainfo":{"_type":"daemon"}}`；boot 時把 daemon 家寫進 K/info.json 一格 `daemon`；kernel 的 `pid` 改名 `name`。代價：三個小改。

**R10 CPU 收到 TERM 主動寫 `ok:false`「被中止」。**〔backlog〕現在：stop 第二次 TERM 砍掉 CPU，running 留著，agent 要等下次有人 tick 且滿 timeout+30 秒才醒。建議：CPU 裝 TERM handler，鎖內寫失敗結果再搬 done。代價：多一條路徑，語意仍是「結果不明」。

**R11 工作 CPU 與 kernel tick 的 interval 分開。**〔backlog〕現在：一格 `interval_ms` 共用，預設 1 秒，一次「問→工具→答」14.9 秒全是輪詢延遲。建議：`work_interval_ms` 給工作 CPU（100 ms 級）。代價：一格；要先做 R5 才不會漏看。

**R12 idle.json 用 `["true"]` 代替 `python -c pass`。**〔backlog〕每顆閒置 CPU 每秒起一個直譯器。代價：依賴 PATH。

**R13 收屍用 running 檔 mtime 對系統時鐘（`aos_cpu.py:136`）。**〔backlog〕NTP 跳時／睡眠喚醒會提早或延後收屍；先寫進規範限制即可。

## 4. 規範與程式不一致

- **R14** cpu-queue.md §2「三處同名拒收 `ReadFailed`」；程式 `aos_cpu.py:101` 丟 `FileExistsError`（OSError），agent 顯示成 `io: 檔案操作失敗`，不是 AgentError。
- **R15** cpu-queue.md §2「result 父目錄須已存在」；`submit` 沒驗，到 execute／收屍才炸（見 R2）。
- **R16** aos-kernel.md 步驟 3「daemon 不在時報錯」；程式只看 state.json 的 `pid` 是否為 0，daemon 被 kill -9 後照常 tick（見 R1）。規範應寫成「只看最後快照的 pid 欄」。
- **R17** kernel `remove()` 逾時回 `NotRunning`（`aos_kernel.py:254`），daemon ctl 逾時回 `ReadFailed`；同一件事兩個代號。
- **R18** llm-cpu.md §2「壞 payload 在認領前退 1、原檔保留」沒寫後果是整顆 CPU 停擺（R2）；aos-run.md「hold 每個 interval 再看一次」在 0 時語意變忙迴圈（R3）。
- **R19** agent.md 開頭「← [proto5 README](../README.md)」文字寫 proto5、連結指 proto5.1。
- **R20** kernel-home.md 寫了 `since`，程式只寫不讀、`ls` 也不印（見 R23）。
- **R21** aos-daemon.md 說「ctl ls 直接讀 state，不交件」，但 daemon 仍接受檔案 `{"op":"ls"}`（`aos_daemon.py:248`），規範表格也列它；兩種說法都合法。

## 5. 可以拿掉的東西（KISS）

- **R22** `aos_run.py:96,104,122,125,128` 的 `reason` 變數：算了沒人用。
- **R23** kernel state 的 `since`、`bad_exit`（`aos_kernel.py:22,278,405`）：只寫不讀不印。
- **R24** `aos_llm_cpu.queue_lock` 相容別名（`aos_llm_cpu.py:13`）；`aos-llm-ask --dry-run`（有沒有給都一樣）。
- **R25** daemon 檔案請求的 `ls` op（R21）。
- **R26** tool 請求裡 inst 的 `stdin`／`stdout` 串流格：CPU 驗了它們是絕對路徑，然後用管線接管、根本不用（`aos_tool_cpu.py:47-52`）。
- **R27** `aos_cpu.tick` 的 `validate` 參數（配合 R2 統一成 execute 內寫 ok:false 後就沒必要）。
- 反過來**少了**的：R1 的 ppid 檢查、R2 的 `bad/`、R9 的 daemon 身分檔與 K 記 daemon 家。

## 6. 跑過的驗證

- `python3 -m unittest discover -s test -p test_cpu.py`：14/14 綠（`-m unittest test.test_cpu` 會 import 失敗，要用 discover）。
- 壞請求腳本：a.json（model=5）＋b.json（未知代號），tick 三次都丟 `EngineInvalid`，b 永不處理；a 搬進 running 後收屍也停 → R2。
- 孤兒腳本：K＋daemon，`kill -9` daemon 後兩支 aos-run 仍在；重啟＋boot 後 `cpus/0.json` 上 2 支；`ctl stop` 後舊兩支仍在（手動 pkill）→ R1。
- daemon 閒置 0.5 秒取樣 20 次 state.json mtime 全不同 → R6。
- `aos-run --interval-ms 0 --home R`＋`ctl.json {"op":"hold"}`：0.2 秒內 run.json 10 個 mtime、102% CPU → R3。
- 沒改其他檔案、沒 commit。
