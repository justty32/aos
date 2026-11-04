# kids 工具包——生小孩、管小孩

← [proto2/README](../../README.md)｜[抒發原文](../2026-09-06-world-clock-agent.md)

這一包讓 agent 自己生子 agent，然後管得動它們：看它們在幹嘛、派活給它們、暫停、收掉。

子 agent 就是父本體資料夾底下的 `kids/<名字>/`，它自己是一個完整的世界。
**鐘是 shared 還是 own，跟「誰管誰」完全沒關係**——鐘只決定它什麼時候動，
管理權是父子關係本身給的，寫在名冊裡。

## 工具清單

### spawn

- 參數：`name`（英數字／底線／減號）、`persona`（它的 system prompt）、
  `packs`（工具包名字的清單，不給就抄父的一份）、`clock`（`shared`／`own`，預設 `shared`）、
  `task`（可有可無，一段文字，生完立刻當第一封信寄給它）。
- 回：`{ok, name, path, clock, message}`。
- 什麼時候用：要一個有自己人格、自己記憶、能自己跑的幫手時用。
  `shared` 是分身——你走一格它走一格，你停它也停；`own` 是自己一個鐘，跟你脫節，
  適合長期自己跑或要跑很久的活。不確定就 `shared`。

### kids_list

- 參數：無。
- 回：一列一個小孩——`name`、`clock`、`state`（idle／llm／wait／act／collect）、
  `busy`（真做事幾格）、`step`、`unread`（它還有幾封沒讀）、`last`（它 outbox 最後一句，切短）、
  `paused`（own 的鐘被暫停了沒）。
- 什麼時候用：想知道小孩在忙什麼、做完了沒、有沒有卡住，就叫這個。派完活之後也是靠它看進度。

### kids_pause／kids_resume

- 參數：`name`。
- 回：`{ok, name, message}`。
- 什麼時候用：小孩在亂跑、或先讓它停一下別燒 token，就 `kids_pause`；要它繼續就 `kids_resume`。
  `own` 的走 `aos-daemon pause/continue <子路徑>`；`shared` 的沒有自己的鐘，
  就把父 `.aos/inst` 裡那行 `aos-exec kids/<名字>` 前面加 `#` 註解掉，resume 再拿掉。

### kids_kill

- 參數：`name`、`keep_files`（布林，預設 `true`）。
- 回：`{ok, name, kept, message}`。
- 什麼時候用：這個小孩不用了。**預設留資料夾**（`own` 的先 `aos-daemon unregister`，
  `shared` 的把父 inst 那行刪掉），它從此不會再被推，記憶還在、要看還看得到。
  `keep_files=false` 才連資料夾一起刪——不可回復，講明要刪才刪。

### kids_tell

- 參數：`name`、`text`。
- 回：`{ok, name, path}`。
- 什麼時候用：要小孩做事就寄一封信給它。**這其實就是 communication 那包的寄信**，
  只是省掉「小孩資料夾在哪」這一步：它寫進 `kids/<名字>/inbox/parent/<時間戳>.json`。
  communication 包負責一般的收發信，kids 包只是幫你把小孩的地址填好，兩包不重疊。
  子被寄信 → 它下一格 `idle` 會發現有未讀 → 自己去問 LLM，跟別人寄信給它一模一樣。

### 收小孩的回報（不是工具，是自動的）

建議：**子每寫一則 outbox，就同時往父的 `inbox/kid-<子名>/` 丟一份同樣內容的信**。
子知道父是誰（名冊那行有寫父路徑），所以這件事在子自己那格順手做掉，
不需要父去輪詢。父下一格就看到「你有新信：kid-helper 1 封」，用 communication 包讀。
這樣「小孩講話」跟「別人講話」在父眼裡是同一件事，不用多一套機制。

### 等小孩做完（不做成工具）

**不給 `kids_wait`。**一格要短，卡在那邊等會把整個鐘拖死。
模型要等就用「下一格再看」的講法：這一格先講一句「我叫 helper 去查了，等它回話」，
然後這格結束。下一格若小孩回話了，信就在信箱裡；沒回話就再等一格，
或叫 `kids_list` 看它 `busy` 有沒有在漲。這句要寫進 PROMPT，模型才不會想去 sleep。

## 管理權與從屬

- **父對子**：可以改它的人格（`system-prompt.json`）、看它的記憶（`prompts.json`）、
  看它的 outbox、寄信、暫停、殺掉。理由很簡單——那是父資料夾底下的檔案，權限就在那裡。
  但工具包先只開「看」跟「寄信」跟「暫停／殺」，**改人格、改記憶先不做工具**，
  要改就用 shell 包自己去寫檔（少一個誤傷自己小孩的介面）。
- **子對父**：子可以回報「我做不到」——它就寫 outbox 說一句，那句會變成父的信。
  子**不能**拒絕被暫停、被殺（那是檔案跟訊號層的事，不經過它同意）。
  子也不能反過來改父的人格；子要跟父講話只有寄信一條路。
- **孫子（A-6）**：子預設抄父的工具包，所以子也有 `spawn`，孫子自然存在。
  建議：**限深度，預設 2 層**（父→子→孫，孫不能再生）。名冊記一個 `depth`，
  spawn 時超過就直接回一句「你已經在第 N 層，不能再生了」。要放寬就改設定檔一個數字。
  理由是三層以上目前沒有人看得懂在跑什麼，燒 token 也不好追。
- 以上跟鐘無關。`own` 的小孩時間脫節、父停它照跑，但父照樣看得到它、寄得到信、殺得掉它。

## 資料夾長相

`<父 home>/kids/<名字>/` 就是一個完整的世界資料夾（跟現在 `spawn()` 生出來的一樣）：
`.aos/inst`（`aos-agent exec .`）、`system-prompt.json`、`prompts.json`、`tools.json`、
`llm.json`（指到跟父同一個 LLM）、`state.json`、以及它跑起來後自己長的
`inbox/`、`outbox/`、`kids/`。

名冊：建議加 `<父 home>/kids.json`，一列一個小孩——
`{"name", "clock", "created", "depth", "parent", "alive", "task"}`。
理由：`kids_list` 現在得靠掃資料夾猜，猜不出 clock 是哪種、被 pause 了沒、是不是已經 kill 掉。
名冊是唯一真相，資料夾只是身體。父自己的 `state.json` 不要塞這些，它已經夠擠了。

git（A-7）：小孩全部在 `kids/` 這個固定名字底下，所以範例 agent 的 `.gitignore`
加 `kids/` 跟 `kids.json` 兩行就擋乾淨了，不用再一個一個追。

## 跟現有東西怎麼接

- `proto2/packs/kids.py`：現在只有 `spawn`／`kids_list`，把上面其他工具補進去，PROMPT 補「不要等，下一格再看」。
- `proto2/aos_agent.py`：`spawn()` 加寫 `kids.json`、加 `depth` 檢查、`task` 就呼叫 `put_mail`；
  `Ctx` 加 `kids_conf()`／`kid_home()`／`kill_kid()`／`pause_kid()`；
  outbox 那段加一句「順手往父的 `inbox/kid-<我>/` 也丟一份」。
- `proto2/examples/agent/.gitignore`：加 `kids/`、`kids.json`。
- `proto2/README.md`：「子世界」那節重寫成 kids 包的說法。

## 現在故意不做

- 改子的人格／記憶的工具（要改用 shell）。
- 子把自己的小孩過繼給別人、換父。
- 父死掉時小孩怎麼辦（孤兒鐘現在會繼續跑）。
- kill 掉的小孩名字能不能重用。
- 名冊跟真實資料夾對不上時的修復（人自己去看）。
- 子對父的權限限制（子現在寫得動父的檔，只是沒工具）。
- 深度以外的配額（一個父最多幾個小孩、總共幾個）。

## 要拍板

1. **深度限 2 層**（孫不能再生）夠不夠？建議：夠，先這樣，設定檔留一個數字好改。
2. **子的回話自動變父的信**（子寫 outbox 時順手丟一份到父 `inbox/kid-<名>/`）要不要做？建議：要，這是 A-8 最省的答案。
3. **kill 預設留資料夾**、講明才刪，可以嗎？建議：可以，刪掉的記憶找不回來。
4. **加 `kids.json` 名冊**還是繼續掃資料夾？建議：加，clock／paused／depth 掃不出來。
5. **shared 的暫停用「註解掉 inst 那行」**這招夠不夠土？建議：夠，crude 就是這一版的風格。
