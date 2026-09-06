# 要跑很久的工具——開一個新的鐘讓它自己跑

← [proto2/README](../../README.md)｜[抒發原文](../2026-09-06-world-clock-agent.md)

## 1. 問題

一格要短。一格跑多久，那個世界的 fps 就是多少。
`make`、爬一個網站、跑一整套測試，動不動幾分鐘，塞在一格裡整個鐘就停在那裡不動。
daemon 也不會來救它——它進程還活著，只是很慢。
所以長活不能在格子裡做，要**變成另一個世界，跟 daemon 要一個自己的鐘**。

## 2. 建議做法：`run_long`

一個新工具包 `jobs`，主力工具 `run_long(command, name?)`。

它做四件事，**當場回話，不等**：

1. 在自己家底下建 `jobs/<name>/`，這就是一個完整的世界。
   `name` 不給就用時間戳；名字被佔走就回錯誤（不自動加後綴，模型才知道撞名了）。
2. 把那句指令**原樣**寫進 `jobs/<name>/cmd.sh`——不進 shell 字串、不用逃脫引號。
   再寫一份 `meta.json` 記父的 home 在哪、指令是什麼、幾點開的。
3. 寫死的 `.aos/inst` 樣板（下面）＋ `aos-daemon register jobs/<name> --no-wait`。
4. 回 `{"ok": true, "name": "build-docs", "path": "jobs/build-docs"}`。

之後某一格，父在信箱看到 `jobs` 這個來源有一封新信，那就是結果。

### `.aos/inst` 實際內容

```sh
[ -e result.json ] && exit 0
timeout ${AOS_JOB_MAX:-3600} sh cmd.sh > stdout.log 2> stderr.log
aos-agent job-finish . $?
aos-daemon unregister . --no-wait
```

四行講完：

- 第一行是**擋重跑**。daemon 的鐘是 `aos-loop --keep-inst`，同一段每格都會再跑一次；
  結果已經出來了就什麼都不做，等 unregister 生效。
- 第二行真的去跑。這一格會卡幾分鐘——**沒關係，這個世界只有這件事**。
  `timeout` 是 Linux 現成的輪子，超時退 124。
- 第三行把 `exit`／輸出折成 `result.json`，順手寄一封信到父的 `inbox/jobs/`。
- 第四行自己把自己的鐘收掉。**job 自己收自己，daemon 不用懂什麼叫「做完」。**

### `result.json` 長相

```json
{
  "name": "build-docs",
  "command": "make -C docs html",
  "exit": 0,
  "seconds": 312,
  "started": "2026-09-06T14:03:11",
  "ended": "2026-09-06T14:08:23",
  "stdout_bytes": 18422,
  "stdout_tail": "…最後 2000 字…",
  "stderr_bytes": 0,
  "stderr_tail": ""
}
```

完整輸出留在旁邊的 `stdout.log`／`stderr.log`，不進信也不進記憶。

### 那封信長相

```json
{
  "from": "jobs",
  "time": "2026-09-06T14:08:23",
  "content": "job build-docs 做完了：exit 0，跑了 312 秒。\nstdout 最後幾行：\n…\n完整輸出在 jobs/build-docs/stdout.log，要看用 sh 或 job_peek。"
}
```

信要短。**信會進 prompt，log 不會。** 超時的話第一句換成「被 3600 秒逾時砍掉了（exit 124）」。

## 3. 三個沒選的做法

**直接 fork 背景進程**（`cmd &`）。零成本，但它逃出鐘的管束：
`aos-daemon-kernel ls` 看不到、pause／unregister 管不到、輸出沒地方去、
機器重開就變孤兒或整個消失。除錯的時候完全不知道它還在不在。不選。

**像 `aos-llm` 那樣自己養 worker、每格巡 `running/`。** 這招對 LLM 是對的——
同類請求很多、要排優先級、要限制一台引擎同時幾個，所以值得自己寫一套派工加巡邏。
對 agent 的雜活不值得：每個 agent 都要多背一套 pid 生死判斷，
而「有個東西一直被推、東西死了要補救」正是鐘已經在做的事。重複造。

**整包做成獨立的服務世界**（像 `llm/` 那樣一個 `jobs/` 資料夾排隊）。
等以後「同時要跑的活多到需要排隊」或「要限制同時只能跑兩個編譯」再做。
現在多一個常駐鐘、結果還要跨資料夾送回來，不划算。
升級路徑很單純：把 `jobs/` 從 home 底下搬出去變兄弟目錄，工具改成往那裡丟請求。

## 4. 配套工具（同一包）

- `jobs_list()` — 掃 `jobs/*/`，一列一個：`name`、`state`（`running`／`done`／`cancelled`）、
  `exit`、跑了幾秒、`command` 切短。有 `result.json` 就是 done，沒有就是 running。
- `job_peek(name, lines?)` — `stdout.log`／`stderr.log` 的**最後 N 行**（預設 20）。
  中途想知道進度就用它。不給整份，怕塞爆記憶。
- `job_cancel(name)` — 先 `aos-daemon unregister jobs/<name>`（kernel 對那個鐘的
  process group 送 SIGTERM，**指令自己是 loop 的子孫，一起被收掉**，不用另外記 pid），
  再補一份 `result.json` 寫 `"exit": null, "cancelled": true`，這樣 `jobs_list` 不會永遠顯示 running。
- **超時誰數？job 自己數。** `timeout` 那行就是全部。
  不建議在 daemon 的 config 加 `max_seconds`——daemon 只認得「進程活著沒」，
  它分不出「跑很久的正常活」跟「卡死」，硬加只會誤殺。要調就 `run_long` 多一個
  `max_seconds` 參數（預設 3600），寫進 inst 那個環境變數。

## 5. 「原本以為很快、結果卡住的一格」

現在 `sh` 工具已經有 60 秒 `TIMEOUT`。建議就停在這個最土的規則上：

- **超時就回錯誤，順便教模型下一步。** 訊息改成一句：
  「跑超過 60 秒被砍掉了。這種要跑很久的，改用 `run_long`，它會另開一個鐘去跑，做完寄信給你。」
- **不做自動 fork。** 一句 shell 跑到一半被搬去背景，狀態不明、輸出對半切，
  而且搬過去的那半也逃出了鐘。得不償失。
- 每一包自己數自己的秒數，這是唯一的保險——一格卡住的時候，鐘本身是不會來救的。

## 6. 跟現有東西怎麼接

- 新增 `proto2/packs/jobs.py`：`run_long`／`jobs_list`／`job_peek`／`job_cancel` ＋ PROMPT
  （PROMPT 要寫「叫完不要等，這一格先講一句話就結束，下一格去信箱看」）。
- `proto2/aos_agent.py`：`Ctx` 加 `jobs_dir()`／`start_job()`；寄信直接用現成的 `put_mail`。
- `proto2/aos-agent`：加一個子命令 `job-finish <dir> <exit>`——折 `result.json`、
  讀 `meta.json` 找到父的 home、`put_mail(home, "jobs", 摘要)`。
  不另外做 PATH 上的新指令，`aos-agent` 已經在 PATH 裡了。
- 新資料夾 `<home>/jobs/<name>/`；範例 agent 的 `.gitignore` 加一行 `jobs/`。
- `README.md` 加一節。
- **daemon 完全不改。** 不加 `once`、不加「跑完自動下架」——
  下架這件事 job 自己最後一行就做完了，daemon 不需要多懂一個概念。

## 7. 現在故意不做

- 鐘被砍或機器重開後，`supervise` 會把 job 的鐘重開，`result.json` 還沒寫就**整句從頭再跑一次**
  （不會兩份同時跑，但不是冪等的指令會出事）。
- job 之間的併發上限（一次開十個就真的十個一起跑）、優先級、排隊。
- job 生 job（`jobs/x/` 底下再長一層）。
- 做完的 job 資料夾誰清、`stdout.log` 長到幾 GB。
- 跑到一半要跟 job 講話、送輸入進去（stdin 直接關掉）。
- job 換身份跑（`--config` 的 `user` 沒接上來）。
- 父被 kill 掉之後 job 還在跑（信會寄進一個沒人看的信箱）。
- 同一微秒兩個 `run_long` 撞名字。
- 結果檔的原子寫（`result.json` 目前不是先寫 `.tmp` 再 rename）。

## 8. 要拍板

1. **job 自己 unregister 自己，daemon 不加 `once`**——可以嗎？建議：可以，少一個概念。
2. **結果走信箱（`inbox/jobs/`），不是回工具的返回值**——同意嗎？建議：同意，一格回不了。
3. **超時預設 3600 秒、由 job 自己 `timeout` 數**——夠嗎？建議：夠，daemon 不該管這個。
4. **`jobs/` 放在 agent home 底下，跟 `kids/` 平輩**——還是該是獨立服務世界？建議：先放家裡。
5. **`sh` 超時只回一句話叫模型改用 `run_long`，不自動搬**——可以嗎？建議：可以，自動搬太黑。
