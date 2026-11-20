設計之六：loop 層通用的點——加在哪、叫什麼、帶什麼、能不能攔、暫停時觸不觸發、跟 on_clock 與起停兩個事件的關係、每圈成本多少與「沒人掛時是零」的做法。

← [05](05-發事件指令.md)｜下一份 [07 對照與衝突](07-對照與衝突.md)

鍵名、事件名是設計稿，沒寫成程式；時間是 11-20 公司 WSL 一台機器量的，只看量級。

## 結論

- **只加在 aos-loop，aos-fsm 不動**。aos-loop 每跑一次身體的前後各一個點：**`before_run`、`after_run`**。
- agent-fsm 的「一圈」本來就是「一格」（aos-fsm 一次只跑一格），所以這兩個點對 fsm 身體就是「每格前後」；eca 也是 aos-loop 跑的，自動有（一圈＝一輪）；自己寫格程式的 agent、用 aos-loop 跑的 kernel 也接得上。
- aos-loop 照舊**不認得 hook**：loop.json 多四個選填的鍵，它只是在那兩個時機跑被指定的東西、看一個檔在不在。
- **沒人掛時的成本＝每圈看兩次檔在不在，約 2 微秒**；有人掛時每個點至少約 18 毫秒（起一支 Python），加 handler 自己的。
- `before_run` 的 handler 退 10＝**跳過這一圈**（設計預設，[10](10-待裁題.md) 第 1 題）。
- 暫停中不觸發。on_clock、after_start、after_stop 照舊，不收斂。

## 為什麼是 aos-loop

| 加在 | 意思 | 誰有 | 代價 |
|---|---|---|---|
| **aos-loop（採用）** | 身體每跑一次的前後 | fsm（＝每格）、eca（＝每輪）、任何用 aos-loop 跑的 | 改一個 C++ 專案 |
| aos-fsm | 每格前後，知道格名與結束碼 | 只有 fsm 身體；eca 沒有 | 改另一個 C++ 專案；fsm 身體兩層都加就每圈重複發 |
| 兩個都加 | — | — | 兩倍的行程，多數情況講的是同一刻 |

aos-loop 不知道「現在是哪一格」。補法不動 aos-fsm：fsm 範本的 loop.json 在叫 `aos-hook fire` 時多帶 `--field-file stage=$AOS_STACK/stage.txt`（[05](05-發事件指令.md)）；是接線的範本知道自己是 fsm，不是 aos-loop 知道。

## loop.json 多的四個鍵（都選填）

| 鍵 | 寫法 | aos-loop 做什麼 |
|---|---|---|
| `on_before_run` | 同 `exec`（字串、陣列、單子） | 每次要跑身體之前跑它一次 |
| `on_after_run` | 同上 | 身體每跑完一次跑它一次 |
| `on_before_run_if` | 一個檔的路徑 | 有寫＝這個檔存在時才跑 `on_before_run`；沒寫＝每次都跑 |
| `on_after_run_if` | 同上 | 同上，管 `on_after_run` |

agent-fsm 範本的接線（eca 的不帶 `stage` 那兩個旗標，其餘相同）：

```json
"on_before_run": {"argv": ["aos-hook", "fire", "-q", "--agent", {"$env": "AOS_CD"},
                           "--field-file", {"$env": "AOS_STACK", "$path": "/stage.txt", "$prefix": "stage="},
                           "--field-default", {"$ref": "fsm.json#/start", "$prefix": "stage="}, "before_run"]},
"on_before_run_if": {"$env": "AOS_STACK", "$path": "/hook_before_run.flag"},
"on_after_run": {"argv": ["aos-hook", "fire", "-q", "--agent", {"$env": "AOS_CD"},
                          "--field-file", {"$env": "AOS_STACK", "$path": "/stage.txt", "$prefix": "next_stage="}, "after_run"]},
"on_after_run_if": {"$env": "AOS_STACK", "$path": "/hook_after_run.flag"}
```

`$path` 是字串直接接在後面，所以自己帶開頭的 `/`。`--field-default` 那行補的是第一圈：還沒有 stage 檔時，用 `fsm.json` 的起始格當 `stage`，`condition: "idle"` 第一圈才比得中。（`$ref` 加 `$prefix` 能不能這樣併用，施工時先在 aos-directive 的測試裡確認；不行就改成 `aos-hook` 多一個讀 JSON 檔某一格的旗標。）

## 一圈裡的順序與每個結束碼的意思

```
讀 ctl → 暫停中？是：睡，回頂端（兩個點都不發）
       → 還沒到時間？是：睡，回頂端
       → on_before_run_if 的檔在嗎（沒寫當作在）→ 跑 on_before_run（這段期間表上仍是 waiting）
              跑的期間 loop 收到訊號＝照「收到訊號」收工（不算 hook 失敗），身體不跑
              10＝跳過這一圈：不跑身體、不算一次、不發 after_run；下一次的時間設成現在加 interval_ms、表上寫 waiting，回頂端
              其他非 0、起不來＝當成這一圈失敗，loop 收工（跟身體失敗同一條路，on_stop 照跑）
              0＝**先再讀一次 ctl**：這時有人下了 stop 或 pause，就照它（回頂端），身體不跑；沒有才往下
       → 次數加一、表上寫 running → 跑身體
              身體起不來（loop 自己的錯）＝照舊收工，不發 after_run
       → 這一圈 loop 沒收到訊號，而且 on_after_run_if 的檔在 → 跑 on_after_run
              0＝照身體的結果往下
              非 0：身體本來就要收工（退 10 或失敗）＝照身體的結果收工，多印一行 warning；身體是 0＝loop 以這個碼收工
```

- 給這兩格的環境變數：`AOS_LOOP_RUNS`（**before 給的是「這一次會是第幾次」＝已跑次數加一，after 給的是同一個數**）；`on_after_run` 另有 `AOS_LOOP_RUN_CODE`、`AOS_LOOP_RUN_SIGNAL`（沒被訊號結束＝空字串，不是 0）、`AOS_LOOP_RUN_MS`。跑完就還原，不留給身體與 `on_stop`。
- 身體失敗時那行 `RunFailed` 照舊在身體一結束就印，在 `on_after_run` 之前。
- **扣在 `before_run` 之後才下的 stop／pause 會生效**（上圖「先再讀一次 ctl」）：這比今天扣在 before_tool 上「永遠停不了」好。代價是放行後若被 pause，再 resume 時 `before_run` 會為同一圈再發一次。
- **期限**：不吃 `on_timeout_ms`（那是起停兩格的 5 秒）；跟 `exec` 一樣，要限時就在單子裡寫 `timeout_ms`。理由：gdb 把 agent 扣在 `before_run` 時會等很久；每個 hook 自己本來就有 `timeout_ms`。
- **失敗就收工**是照 C-90「hook 自己失敗時預設跟著停」；`on_error: continue` 的 hook 失敗時 `aos-hook` 只印警告、退 0，loop 照跑。這跟 11-11 定的 `on_start`／`on_stop`「只當一行 warning」不同，是 [07](07-對照與衝突.md) 衝突第 2 條。
- **aos-daemon**（它繼承 aos-loop 的骨架）不收這四個鍵，寫了就是設定錯：不讓任何 hook 跳過或拖住管理員的一圈。（它今天收 `on_start`／`on_stop`，那兩個照舊。）
- **沒有 `exec` 的 loop**（沒有身體可夾）：兩個點都不跑。

## 事件帶什麼

宣告全文在 [02](02-現有的點改寫成宣告.md) 的 loop 那份。`before_run`：`counter_runs`、`stage`（要跑的那一格；可以用 `condition` 比，例：只在 act 之前）。`after_run`：`counter_runs`、`code`、`signal`、`elapsed_ms`、`next_stage`（表現在停在哪一格）；**不收 `condition`**——身體跑完時格已經換了，拿下一格去比「剛跑完哪一格」會比錯。eca 與沒有格的身體，`stage`、`next_stage` 都是 null。

## 沒人掛時怎麼做到零成本

兩個旗標檔 `$AOS_STACK/hook_before_run.flag`、`hook_after_run.flag`：**有人掛那個點才存在**。aos-loop 每圈只做一次「檔在不在」。

| 誰對旗標（照清單算一次：該有就建、不該有就刪） | 什麼時候 |
|---|---|
| `aos-agent hook add／rm／reset`、`self_hook`、gdb 下斷點與刪斷點 | 改完清單立刻 |
| `aos-hook fire --agent … after_start` | 每次起來 |
| `aos-hook check --agent` | 人手動叫 |

- **讀清單與發事件都不動旗標**（`hooks.open`、`fire` 是純讀）：一邊「發現沒人掛就刪」、另一邊「剛掛上就建」會互相踩（刪掉別人剛建的旗標，新掛的 hook 第一圈漏發）。對旗標的只有上表三種時機。
- 手改 `hooks.json` 的：要重起，或跑一次 `aos-hook check --agent`。
- 旗標在、其實沒人掛（例如手改清單拿掉了）：每圈白起一支 `aos-hook`（約 18 ms），不會出錯；下次有人對旗標時消失。
- 不寫 `_if` 的人（自己接線的 loop）＝每圈都跑，付全額。

## 效能數字

量法：`~/.aos/scratch/aos-hook-plan-1120/measure.py`，純 Python 的 `subprocess.run` 各跑 100～200 次取中位數；**沒有起任何 aos 行程**，所以 `aos-exec` 那一層是估的。

| 起一個行程 | 中位數 |
|---|---|
| `/bin/true` | 0.36 ms |
| `sh -c :` | 0.47 ms |
| `python3 -c pass` | 10.8 ms |
| `python3` 加上引擎要的 import（json、subprocess…） | 18.0 ms |
| Python 再起一支 Python（＝發事件的指令＋一個最小的 handler） | 28.5 ms |
| 看一個檔在不在 | 0.84 微秒 |
| 讀加解 5 個小 JSON | 32 微秒 |

| 情況（agent 的 loop 一圈間隔 300 ms） | 每圈多出來的 |
|---|---|
| 沒人掛、有旗標檔 | 約 2 微秒 |
| 沒人掛、沒寫 `_if` | 兩個點各起一支 `aos-hook`：約 36 ms |
| 掛了 `before_run`，一個 Python handler | 約 30～37 ms（指令 18＋handler 11～18；`aos-exec` 估 1 ms 內） |
| 前後都掛 | 約 60～75 ms |
| `condition` 沒比中（例：只要 act，現在是 idle） | 仍要約 18 ms：比 `condition` 是在指令起來之後 |

對照：aos-compile-base-1120 量的「函數抽成獨立檔的 handler 每次約 15 ms、回頭跑 agent.py 約 76 ms」（[08 原型](../aos-compile-base-1120/08-B-原型.md)）。閒著的 fsm agent 每 300 ms 就跑一格 idle，所以**掛了 `before_run` 的 agent 閒著時每秒約多 3 個行程**。要定時做事仍該用 on_clock（在格程式的行程裡比時鐘，到了才起 handler）；要每圈都看才用 `before_run`。再往下省（常駐一支、同行程叫函數）是 [10](10-待裁題.md) 第 9 題，本設計不做。

## 跟現有的關係

| 現有的 | 關係 | 收不收斂 |
|---|---|---|
| after_start、after_stop | 同一層；四個點寫在同一份宣告（[02](02-現有的點改寫成宣告.md)） | 名字與行為不動 |
| on_clock | 數的是時鐘格數，在身體的行程裡檢查，沒到不起行程 | 不收：搬到 `before_run` 上面會變成每圈起一支行程 |
| 九種語意事件 | 並存（他選的）；loop 不知道信與工具，取代不了 | — |
| gdb 的暫停、單步 | 暫停中的 agent loop 不跑身體，兩個點都不發；扣在 `before_run` 上時 loop 等著，放行後先讀 ctl 才決定跑不跑身體 | — |

## 邊緣

- **一直被跳過**：`before_run` 每圈都退 10，agent 活著但什麼都不做，表上是 waiting。`aos-hook` 的警告不會有（攔下不是錯）。看得見的地方：handler 自己留紀錄；loop 的 log 不寫被跳過的圈（預設；要寫是多一行 log 的事）。
- **`max`（最多跑幾次）**：被跳過的不算。
- **身體退 10（正常收工）那一圈**：after_run 照發，然後才 on_stop。
- **整夾抄走的定義**：loop.json 沒有這四個鍵就沒有這兩個點；掛了也不會發。`aos-hook check --agent` 與 `hook add` 能不能看出「宣告有、loop.json 沒接」——設計預設不查（要讀 loop.json，是 aos-loop 那一層的檔），只在文件寫明。
