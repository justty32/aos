# 第三段之二：控制模組

← [plan 入口](README.md)｜**接在 [m3-daemon-core](m3-daemon-core.md) 之後。**｜依據：[verdicts 11 篇末「`insts` 改成物件＋控制模組裁定」](../notes/verdicts/11-tick-as-unit.md#2026-10-01最核心-daemon待統一更新-spec)｜結束碼：[aos 結束碼慣例](../notes/verdicts/11-tick-as-unit.md#aos-結束碼慣例待統一更新-spec)｜spec 正本：[B-641](../spec/settled/daemon/control.md)、格式 [P-121](../spec/settled/protocol/daemon/control.md)｜舊 spec 參考（暫緩區）：[B-612 通道](../spec/settled/deferred/daemon/channel.md#b-612tickdaemon-通道)、[P-117 通道變數](../spec/settled/deferred/protocol/daemon/channel.md)、[B-607 叫醒暫停](../spec/settled/deferred/daemon/registration.md#b-607叫醒暫停故障停格與格次序號)

**做完的樣子**：m3 的 `aos-daemon` 設定檔寫了 `"modules": {"control": {"socket": "./aos.sock"}}`，daemon 開起來就多開一個 unix socket，收四個指令，**每個都只對一項**（用 inst 字面值指名）：**叫醒**（現在跑一次，可帶兩個選項）、**暫停**、**恢復**、**看狀態**。小工具 `aos-ctl` 送指令。daemon 開 `aos-exec` 時把 socket 位置與該項 inst 放進環境變數，一路傳到 tick 的任務、再傳到下層 `aos-tick 下層` 的任務，所以**任何一層的任務跑 `aos-ctl wake` 就叫醒自己所在的頂層那一項**。沒寫 `modules.control` 時 daemon 就是 m3 原樣。

> **使用者裁定（2026-10-01，原話）**：「daemon config中，其實可以是{"insts":{"jobs/report.json":{...},"haha.json":{...}}}。然後控制模組這塊，wake的功能改一下，改成可以調設定，比如正在跑的話是否就不跑了(但仍然叫幾次都只補一次)，或是這次跑完，原本後續週期性的那次就不跑了，或是弄成單獨指令也可以。aos-ctl status應該要只能看一個項的狀態，也就是自己所在的這項。1.夠了。2.可以。3.隨便放，就一個。4.算。5.訊息模組不算在此。」追補：「應該說wake/pause/resume/status都是指向某一項inst任務」。
>
> 1～5 的意思：只收 wake／pause／resume／status 四個（不收 reload、shutdown）；能連 socket 就能做所有事、不另設權限；一個 daemon 一個 socket、路徑寫在設定裡；叫醒算控制模組的一部分；訊息模組（aos-mq）不走這條 socket。更早已定：模組設定放 `modules` 底下、有寫就開（不要 `enable_control`）；核心沒有 id，項目以 inst 字面值指名；變數 `AOS_DAEMON_SOCKET`、`AOS_DAEMON_INST`；整份設定先展開指示詞再讀；「不要用檔案，必須用 socket」「不要管上下層」「daemon 只需要管理最頂層」。

> **POC 總原則**：默認一切正常——socket 建得起來、路徑不超長、沒有兩個 daemon 用同一個 socket、客戶端照規矩送一行。不為這些寫處理，出事自然丟錯、回 1。唯一例外見步驟 3：客戶端送壞了不能讓整個 daemon 掛掉。

> **結束碼**：0＝預料之中；非 0＝要額外處理；1＝通用錯誤，本段沒有特別指定的碼，錯一律 1。

## 先講結論

- **指令都跟 node 無關**：daemon 本來就不認得 node，叫醒、暫停、恢復、看狀態做的都是「`insts` 裡鍵為 X 的那一項怎樣」，對任何 inst 一樣通用。所以 `insts` 每一項的設定物件**一個鍵都不用加**，只在 `modules.control` 寫 socket 路徑。
- **永遠只對一項**：沒有「全部叫醒」「看全部狀態」。任務要動的就是自己所在那一項（`AOS_DAEMON_INST`）；人在 shell 手打就給 inst。
- **wake 的兩個選項做成欄位，不另開指令**（理由見步驟 2 末）。

## 收哪些指令

| 指令 | 做什麼 |
|---|---|
| `wake` | 現在跑一次。正在跑就跑完補一次，叫幾次都只補一次。可帶 `skip_while_running`、`keep_schedule`（步驟 2） |
| `pause` | 不再照週期跑；正在跑的那次不殺、讓它跑完；待補的那次一併取消 |
| `resume` | 取消暫停，也救回被 `stop_on_nonzero` 停掉的項；之後立刻跑一次（建議，見待問 1） |
| `status` | 回這一項的狀態（正在跑、待補、暫停、已停、上次結束時間與碼、下次預定時間） |

暫停只放在記憶體：重開 daemon 就全部恢復。要「重開也不跑」照舊用 tick 的擋板檔（[m3 這段不做的](m3-daemon-core.md#這段不做的先怎麼擋著)）。

## 跟 m3 的介面（對照目前的 `lib/aos_daemon.py`）

控制模組跟 m3 同一支程式（`aos-daemon`），靠設定檔有沒有 `modules.control` 決定開不開。

| m3 現在的樣子 | 控制模組要它 | 要不要改 m3 |
|---|---|---|
| `load_config()` 回 `(start, items)`；`modules` 只檢查是物件、不看裡面 | 讀 `modules.control.socket`，以起點算成絕對路徑 | **要改**：多回一個值（socket 絕對路徑，沒掛＝`None`），或回整個 `modules` 由新模組自己讀（AI 隊定） |
| `insts` 是物件，鍵＝inst 字面值 | 收到 inst 字面值要找到那一項 | 小改：讀完建 `{inst: Item}`。物件鍵本來就不會重複，不用處理撞名 |
| `Item(index, inst, interval_ms, stop_on_nonzero, err_path)` | 加狀態：`running`、`pending`（待補一次）、`pending_keep`（那次補跑要不要保留排程）、`paused`、`stopped`、`last_exit`、`last_end`、`due`（下次照週期該跑的時刻） | **要改**：加欄位與一個 `threading.Condition`（狀態都在它的鎖底下改） |
| `loop()`：「`run_once` → `say` → 非 0 且要停就 `return` → `time.sleep(interval)`」 | 睡的那一下要叫得醒；暫停時一直睡；停掉的項要救得回來 | **要改**：`time.sleep` 換成 `Condition.wait(到 due 為止)`；`stop_on_nonzero` 停掉時執行緒不結束、改成一直等。規則見步驟 2。模組沒掛時沒人會叫醒它，行為跟現在一模一樣 |
| `run_once()`：`Popen([EXEC, item.inst], cwd=start, …)`，環境照 daemon 的 | 加兩個環境變數 | **要改**：模組掛著時多帶 `env=`（daemon 的環境加兩個變數）；沒掛時不傳 `env=` |
| `say()` 印 `inst=… exit=…`、`inst=… stopped` | 暫停、恢復也看得到 | 小改：多兩種行 `inst=<inst> paused`、`inst=<inst> resumed`（照 `stopped` 那行的樣子）；wake 不另印（跑了自然有 `exit=` 那行） |
| `_quit()`：SIGINT／SIGTERM 直接 `os._exit(0)` | 退出前刪 socket 檔 | 小改：模組掛著時先 `unlink` 再退出 |
| `main()`：起完每項的執行緒就 `signal.pause()` | 多起一條收連線的執行緒 | 小改 |
| `write_err()`、`err_path_for()`、`expand()`、`EXEC`、`now()` | 不用動；`now()` 也拿來寫 status 的時間 | 不改 |

檔案（建議）：伺服器端 `lib/aos_daemon_ctl.py`（收連線、解析請求、改狀態；`loop()` 的改動留在 `lib/aos_daemon.py`）；客戶端 `lib/aos_ctl.py` 與薄殼 `bin/aos-ctl`（`.gitignore` 擋 `bin/`，要 `git add -f`）；測試 `tests/test_ctl.py`。做完補 [src/py README](../src/py/README.md) 檔案表與 aos-daemon 一節（[code map](../../wf/workflows/common/code-map.md) 目前不收 proto6）。

## 步驟 1：設定檔

- **要做到**：設定檔有 `modules.control` 就開控制模組；沒有就跟 m3 一模一樣（不建 socket、不傳環境變數）。
- **設定檔**：

  ```json
  {
    "cwd": "/home/u/nodes",
    "interval_ms": 60000,
    "modules": {"control": {"socket": "./aos.sock"}},
    "insts": {
      "a": {},
      "jobs/report.json": {"interval_ms": 5000}
    }
  }
  ```

  - `modules.control`：物件；有寫＝開。整份設定照 m3 先展開指示詞，所以它也可以 `$ref` 到別的檔。
  - `socket`：必填、字串。相對路徑以 m3 的起點資料夾為準（跟 `insts` 的鍵、`exec_err_path` 同一個起點），daemon 開起來時算成絕對路徑。一個 daemon 就這一個 socket。沒寫：自然丟錯、回 1。
  - `control` 裡其他鍵一律忽略（照 m3「其他鍵一律忽略」）。
- **要使用者裁定的點**：無。
- **驗收**：
  - 沒寫 `modules.control`（或 `modules` 裡只有別的鍵）：不建 socket 檔、子程序環境裡沒有這兩個變數（除非 daemon 自己的環境就有，見步驟 4），其他照 m3。
  - `"cwd": "sub"`、`socket: "./s"`：socket 檔出現在啟動目錄底下的 `sub/s`。
  - `"control": {}`（沒寫 `socket`）：回 1。

## 步驟 2：叫得醒、停得住的週期迴圈

- **要做到**：m3 每一項的迴圈改成照狀態走；wake 的兩個選項在這裡生效。
- **先講白現在的預設**：m3 的週期是「上一次**結束**後隔 `interval_ms`」。叫醒跑的那一次也算「上一次」，所以**叫醒跑完後，週期從這次結束重新算**——原本排好的那次週期性執行不會另外跑。例：週期 60 秒、上次 0 秒結束、本來 60 秒要跑；30 秒時叫醒、31 秒跑完 → 下次是 91 秒，60 秒那次就沒了。
- **wake 的兩個選項**（請求裡多帶欄位，都是布林、預設 `false`；兩個名字與預設都是使用者 2026-10-01 定的，兩個都留在 wake 上、不拆單獨指令）：

  | 欄位 | 不帶（預設） | 帶 `true` |
  |---|---|---|
  | `skip_while_running` | 正在跑：記「跑完補一次」，叫幾次都只補一次 | 正在跑：**這次叫醒作廢**，不補。沒在跑照常立刻跑 |
  | `keep_schedule` | 叫醒跑完後週期**從這次結束重新算**（上例下次是 91 秒） | **不動原本排程**：上例 31 秒跑完後，60 秒那次照跑 |

  - `keep_schedule` 的確切意思：每項記一個「下次照週期該跑的時刻」`due`，只有**照週期跑的那次**（和不帶 `keep_schedule` 的叫醒）跑完時才改成「結束時刻＋`interval_ms`」；帶 `keep_schedule` 的那次跑完不碰 `due`。跑完時 `due` 已經過了（叫醒那次跑太久、把原本那次蓋過去），就當原本那次被它頂掉，`due` 改成這次結束＋`interval_ms`——不補跑漏掉的次數，照 m3 原則。
  - 兩個選項可以一起帶。
  - 正在跑、已記「補一次」時又叫醒：不帶 `skip_while_running` 的話還是只補這一次，那次補跑的 `keep_schedule` 照**最後一次叫醒**帶的為準；帶 `skip_while_running` 的話什麼都不改。
- **規則**（每項一把鎖、一個 Condition；指令只改狀態、喚醒那條執行緒，不自己開程序，「同一項不疊著開」照 m3）：
  - **wake**：在睡→立刻跑；在跑→看 `skip_while_running`（上表）；暫停中→跑一次、跑完照樣暫停；已停→回錯 `stopped`、不跑（後兩條見待問 1）。
  - **pause**：設 `paused`；正在跑的那次不殺，跑完不再排下一次，待補的那次一併取消。已暫停再 pause 也回成功。
  - **resume**：清掉 `paused` 與 `stopped`，然後當成一次不帶選項的 wake（立刻跑、週期從這次重新算）。沒暫停也沒停時等於 wake（待問 1）。
  - **跑完之後**：碼非 0 且 `stop_on_nonzero` → 設 `stopped`、印 `stopped`、一直等（不結束執行緒）；否則有待補就立刻再跑，沒有就等到 `due`（暫停時一直等）。
- **為什麼做成欄位、不另開指令**（使用者 2026-10-01 確認留在 wake 上）：兩個選項是兩個獨立的是／否，做成指令要四個（`wake`、`wake-skip`、`wake-keep`、`wake-skip-keep`）或另取新名字，名字還得解釋它跟 wake 差在哪；欄位不帶就是現在的 wake，舊用法一個字都不用改，`aos-ctl` 也只是多兩個旗標。
- **要使用者裁定的點**：待問 1。
- **驗收**（短週期）：
  - 週期 10 秒、假 inst 每次寫一行時間：第一行之後 0.3 秒 wake，0.2 秒內出現第二行；之後要再等約 10 秒才有第三行（週期從叫醒那次重新算）。
  - 同上但帶 `keep_schedule`：第三行在第一行之後約 10 秒出現（不是第二行之後 10 秒）。
  - 假 inst `sleep 0.5`、週期 10 秒：跑的期間 wake 5 次，結束後立刻再跑**剛好一次**，之後照週期。同樣的情況全部帶 `skip_while_running`：結束後不補跑。
  - 假 inst `sleep 2`、週期 1 秒、帶 `keep_schedule` 叫醒：叫醒那次蓋過原本的時刻，結束後不會馬上又跑一次。
  - 週期 100 ms：pause 後 1 秒內沒有新的 `exit=` 行（正在跑的那次照樣印完），有 `paused` 一行；resume 後有 `resumed`、立刻有一行、之後照週期。
  - `{"argv": ["false"]}` 帶 `stop_on_nonzero: true`：停掉後 wake 回 `stopped`、沒跑；resume 後跑一次、又停。
  - 指令不會讓同一項疊著跑（檔裡永遠沒有兩個同時在跑的記號）。
  - 模組沒掛時，m3 的 `tests/test_daemon.py` 照樣全過。

## 步驟 3：socket 與協議

- **要做到**：daemon 在 `socket` 路徑開一個 unix socket（`SOCK_STREAM`），一條執行緒收連線；**一連線一請求**：讀一行、回一行、關掉。
- **依據**：使用者「必須用 socket」；舊 spec 通道（[P-117](../spec/settled/deferred/protocol/daemon/channel.md)）只取「一行 JSON」，method、封包、憑證都不沿用。
- **請求**（一行 JSON 物件，`\n` 結尾）：**指令名當鍵、inst 字面值當值**，wake 的選項另外放欄位：

  ```text
  {"wake":"a"}
  {"wake":"jobs/report.json","skip_while_running":true,"keep_schedule":true}
  {"pause":"a"}   {"resume":"a"}   {"status":"a"}
  ```

  - 四個指令名裡剛好出現一個；值一定是字串（inst 字面值，跟設定檔 `insts` 的鍵逐字比對）。
  - 其他鍵：wake 認 `skip_while_running`、`keep_schedule`（要是布林）；其餘一律忽略（照 m3「其他鍵一律忽略」；使用者 2026-10-01 確認「socket收到看不懂的欄位就不理他」，C-07 已單列控制 socket 放寬）。
- **回應**（一行 JSON，`\n` 結尾）：

  | 狀況 | 回應 |
  |---|---|
  | wake／pause／resume 成功（含「正在跑、記補一次」「正在跑、`skip_while_running` 作廢」「本來就暫停」） | `{"ok":true}` |
  | status | `{"ok":true,"inst":"a","running":false,"pending":false,"paused":false,"stopped":false,"last_exit":0,"last_end":"2026-10-01T15:04:05+08:00","next":"2026-10-01T15:05:05+08:00"}` |
  | `insts` 裡沒有這個 inst | `{"ok":false,"error":"unknown_inst","detail":"<inst>"}` |
  | wake 一個被 `stop_on_nonzero` 停掉的項 | `{"ok":false,"error":"stopped","detail":"<inst>"}` |
  | 讀不到一行、不是 JSON 物件、指令名不是剛好一個、值或選項型別不對 | `{"ok":false,"error":"bad_request","detail":"<白話>"}` |

  - status：還沒跑完過時 `last_exit`、`last_end` 是 `null`；正在跑、暫停、已停時 `next` 是 `null`，否則就是 `due`。時間格式跟 m3 stdout 那一行一致（`now()`：本地時間、ISO 8601、帶時區、到秒）。
  - 不認得的指令名（例如 `{"kill":"a"}`）算「指令名不是剛好一個」，回 `bad_request`；不另設 `unknown_cmd`。
- **回的時機**：狀態記好那一刻就回，**不等那一項跑完**；wake 成功的意思是「收到了」，不是「跑成功了」（結果照 m3 看 stdout 那一行，或之後 status）。
- **連線**：客戶端連上、送一行、讀一行、雙方關。daemon 一次處理一條連線（只是改狀態或抄狀態，很快）；每條連線 1 秒逾時，免得一個連上不送的客戶端卡住後面的人（逾時就關掉、不回）。
- **權限**：能連就能做所有事；能不能連照 socket 檔的檔案權限（建出來照 daemon 的 umask），不另驗身分。
- **不讓 daemon 掛**：單一連線出的任何錯（壞 JSON、對面先關、逾時）只影響那一條連線，回 `bad_request` 或直接關，收連線的執行緒繼續跑。這是本段唯一的「異常處理」：外面送壞東西不該把整個 cron 打掉。
- **要使用者裁定的點**：無。
- **驗收**：
  - 用 Python 標準庫直接連 socket 送 `{"wake":"a"}`：回 `{"ok":true}`，而且 `a` 立刻跑一次。
  - `{"status":"a"}` 回 `a` 一項；跑 `sleep 0.5` 的項中途查是 `running:true`、`next:null`；欄位跟實際一致。
  - 不存在的 inst 回 `unknown_inst`；`{"kill":"a"}`、`{"wake":"a","pause":"a"}`、`{"status":null}`、`{"wake":"a","keep_schedule":"yes"}`、送 `hello` 都回 `bad_request`；之後再送正確的請求照樣成功。
  - 連上不送東西：1 秒多一點被關掉，期間別人的請求最多晚約 1 秒。

## 步驟 4：往下傳環境變數

- **要做到**：模組掛著時，daemon 開每一次 `aos-exec` 都在環境裡加 `AOS_DAEMON_SOCKET=<socket 絕對路徑>`、`AOS_DAEMON_INST=<這一項的 inst 字面值>`（蓋過 daemon 自己環境裡同名的）。
- **依據**：使用者定的兩個名字；`AOS_DAEMON_SOCKET` 沿用舊 spec [P-117](../spec/settled/deferred/protocol/daemon/channel.md)，`AOS_TICK_TOKEN`（憑證）不做。
- **一路傳下去不用寫新程式**：`aos-exec` 照 inst 的 `envs` 規則用繼承的環境；`aos-tick` 開任務時也是繼承的環境加 `AOS_*`；下層 `aos-tick 下層` 本身就是上層的一個任務，它的任務又繼承下去。所以**每一層的任務看到的都是頂層那一項的 inst**，指到的永遠是頂層（使用者「不要管上下層」「daemon 只需要管理最頂層」）。inst 或任務寫了 `envs` 清空時，那一支往下就沒有這兩個變數，是 inst 自己的選擇。
- **inst 字面值是相對路徑也沒關係**：傳下去的只是一個名字，`aos-ctl` 原樣送回，daemon 跟 `insts` 的鍵逐字比對，不在任務的工作目錄解析。
- **模組沒掛時不動環境**：daemon 自己的環境若已有這兩個變數（例如它本身是別的 daemon 底下某個任務開的），照樣傳下去、不清。照默認一切正常，不為這種套疊另寫規則。
- **要使用者裁定的點**：無。
- **驗收**：
  - 假 inst 把兩個變數寫進檔：值是 socket 絕對路徑與 inst 字面值（例如 `jobs/report.json`，不是轉過的絕對路徑）。
  - node 資料夾 `a`（inst 跑 `aos-tick`）的任務表有一項寫檔、另一項跑 `aos-tick b`，`b` 的任務也寫檔：三個檔裡的 `AOS_DAEMON_INST` 都是 `a`。

## 步驟 5：`aos-ctl` 小工具

- **要做到**：一支普通程式送四個指令，**每個都只對一項**；不另做 `aos-wake`。
- **用法**：

  ```text
  aos-ctl wake [--skip-while-running] [--keep-schedule] [<inst>]
  aos-ctl pause  [<inst>]
  aos-ctl resume [<inst>]
  aos-ctl status [<inst>]
  ```

  - 沒給 `<inst>` 一律用 `AOS_DAEMON_INST`（任務裡最常用：動自己所在的頂層項）。沒有「全部」的寫法。
  - socket **只從 `AOS_DAEMON_SOCKET` 拿**，不另設參數；人在 shell 手打就 `AOS_DAEMON_SOCKET=./aos.sock aos-ctl status a`。
  - 兩個旗標只有 wake 認，對應請求的 `skip_while_running`、`keep_schedule`；有給才送 `true`，沒給就不送那個欄位。
  - 連上、送一行、讀一行、關掉。不重試、不另設逾時（默認一切正常）。
- **輸出**：wake／pause／resume 成功時不印；status 成功時把回應那一行原樣印到 stdout（一行 JSON，要好看自己接 `jq`）。
- **結束碼**：daemon 回 `ok:true` 回 0；其餘一律 1，stderr 一行 `代碼: 說明`：
  - 沒有 `AOS_DAEMON_SOCKET`：`no_daemon:`，不連 socket。
  - 沒給 `<inst>`、也沒有 `AOS_DAEMON_INST`：`no_inst:`，不連 socket。
  - 連不上（檔不在、沒人聽、沒權限）：`connect:`。
  - daemon 回 `ok:false`：照回應的 `error` 印（`unknown_inst:`、`stopped:`、`bad_request:`）。
  - 指令名不在四個裡、多給參數、旗標給錯指令（例如 `pause --keep-schedule`）：`usage:`，不連 socket。
- **依據**：使用者「aos-ctl status應該要只能看一個項的狀態，也就是自己所在的這項」與追補「都是指向某一項inst任務」；結束碼慣例；舊 spec 的 `no_channel`（缺變數客戶端自己擋）改名 `no_daemon`。
- **要使用者裁定的點**：無。
- **驗收**：
  - daemon 開著、任務裡跑 `aos-ctl wake`：回 0，而且自己這一項跑完立刻補一次；`aos-ctl wake --skip-while-running`：回 0、不補；`aos-ctl pause`：回 0，這一項之後不再照週期跑。
  - 下層 node 的任務裡跑 `aos-ctl wake`：叫醒的是頂層那一項。
  - 任務裡跑 `aos-ctl status`：stdout 一行 JSON、`inst` 是自己那一項。
  - 給不存在的 inst：回 1、stderr `unknown_inst:`；沒 `AOS_DAEMON_SOCKET`：回 1、`no_daemon:`；沒給 inst 也沒 `AOS_DAEMON_INST`：回 1、`no_inst:`；daemon 沒開：回 1、`connect:`；`aos-ctl kill`、`aos-ctl status a b`、`aos-ctl pause --keep-schedule`：回 1、`usage:`。
- **用法上要知道**：任務每一格都無條件 `aos-ctl wake` 自己，那一項就會不停跑（每次補一次；帶 `--skip-while-running` 就不會，因為叫的時候自己正在跑）；任務 `aos-ctl pause` 自己，就要靠外面的人 `resume`。都是用法問題，不擋。

## 步驟 6：socket 檔的開與收

- **做法**（最簡單、默認一切正常下不會撞）：
  - **開**：bind 前路徑上若已有檔就先刪（上次被 `kill -9` 留下的），再 bind。默認沒有兩個 daemon 用同一個 socket，不檢查舊檔還有沒有人在聽；代價是真的開了第二個時會搶走第一個的 socket。
  - **收**：SIGINT／SIGTERM 時先 `unlink` socket 檔再 `os._exit(0)`（m3 的退出方式不變，只多這一行）。
  - 被 `kill -9` 或自己出錯退出時檔會留著；客戶端連過去得到 `connect:`、回 1；下次開 daemon 時照上一條刪掉重建。
- **要使用者裁定的點**：無。
- **驗收**：
  - SIGINT 後 socket 檔不見了；SIGTERM 一樣。
  - 先在路徑放一個普通檔（或上次 `kill -9` 留下的 socket），daemon 照樣開得起來、指令照樣通。

## 步驟 7：整段驗收

- 步驟 1～6 的驗收合成 `tests/test_ctl.py`，一條指令跑完；**不需要 root、systemd、網路**，全部用暫存資料夾、短週期、假 inst，每條幾秒內結束。
- socket 放暫存資料夾裡（unix socket 路徑上限約 108 字元，`tempfile.mkdtemp()` 放 `/tmp` 底下夠短；測試自己用短路徑，程式不檢查）。
- 測試結束自己殺掉 daemon 和留下的子程序（照 m3 步驟 7 的做法）。
- m3 的 `tests/test_daemon.py` 與原有測試（tick、exec、inst）照樣全過。

## 這段不做的

| 不做 | 這版的樣子 |
|---|---|
| 對全部項的指令（全部叫醒、看全部狀態） | 一次一項；要看多項就多叫幾次 |
| reload、shutdown | 改設定就重開；要停就送 SIGTERM（使用者：四個就夠） |
| 身分驗證、憑證（`AOS_TICK_TOKEN`）、分級權限 | 只靠 socket 檔權限，能連就能做所有事 |
| 訊息（aos-mq） | 不走這條 socket（使用者：訊息模組不算在此） |
| 控制下層 node | 指到的是頂層那一項；下層跟著上層的格跑 |
| 暫停寫進檔、重開還在 | 只在記憶體；要持久用擋板檔 |
| 等 wake 那一次跑完再回 | 收到就回 |
| 一條連線送多個請求 | 一請求一連線 |
| 每項自己設「不准別人碰」 | 都能碰；真要時照「模組鍵放進該項設定物件、沒掛時忽略」加 |

## 待問

1. **暫停中、已停時叫醒怎麼辦？resume 要不要順便跑一次？** 〔**照建議先做，使用者可改**（2026-10-01：使用者要直接開工，程式照下面建議寫；要改只動 `lib/aos_daemon_ctl.py` 的 `handle()` 與 `tests/test_ctl.py` 的 `test_wake_while_paused`、`test_stopped`）〕建議：暫停中 wake **會跑一次、跑完照樣暫停**（暫停只停「週期」，不擋人手叫）；被 `stop_on_nonzero` 停掉的項 wake **回 `stopped`、不跑**，要救用 resume；resume **一律立刻跑一次**。另一種是「暫停中 wake 也不跑」，那暫停就等於整個關掉。

## 做完了沒

**做完了**（2026-10-01，AI 隊）：步驟 1～7 都照上面做了，驗收寫進 `tests/test_ctl.py`（25 條，約 18 秒）、全過；三項檢查（全部測試、`check_ids.py --strict`、`wf-lint`）都過。待問 1 照建議先做（見上）。等使用者看。

- 程式：`lib/aos_daemon.py`（`load_setup()`、`Item` 的狀態與 `cond`、`loop()`／`_next_run()`、`run_once()` 帶 `env=`、`_quit()` 刪 socket、`main()` 開 socket）、新的 `lib/aos_daemon_ctl.py`（伺服器端）、`lib/aos_ctl.py` 與 `bin/aos-ctl`（`.gitignore` 擋 `bin/`，要 `git add -f`）。用法見 [src/py README](../src/py/README.md#控制模組與-aos-ctlm3n)。
- `load_config()` 照舊回 `(起點, [Item])`（m3 測試不用改），另加 `load_setup()` 多回 socket 絕對路徑。
- **改了一條 m3 測試**：`test_daemon.py` 的 `test_modules_ignored` 原本拿 `"control": {"socket": "./aos.sock"}` 當「核心不看的模組」並檢查不建 socket；m3n 起 `control` 有寫就開，所以那條改用不認得的模組名 `later`（意思不變：別的模組鍵照收不理）。其他 m3 測試一字未改。
- 沒照 plan 原字面做的：步驟 2 第一條「0.2 秒內出現第二行」放寬成 1 秒內（aos-exec 每次有 Python 起動時間）；週期 10 秒的驗收改成 1.5 秒量任務自己寫的時間，免得測試一條跑十幾秒。
- 收到 SIGINT／SIGTERM 時若 socket 還沒 bind 好（剛開那一瞬間），刪檔找不到就算了、照樣回 0——這是 daemon 自己開檔順序的縫，不是外面的異常。
- 測試從 444 條變 469 條。
