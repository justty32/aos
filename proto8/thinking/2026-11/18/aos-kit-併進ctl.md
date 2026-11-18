aos-kit 拿掉、套 kit 併進 aos-agent ctl add／set-def 的 --kit：使用者原話、三題裁定與定下的做法（線 kit-merge-1118）。

← [11-18 日索引](README.md)

# aos-kit 併進 aos-agent ctl

## 使用者原話（逐字）

- 11-18：「aos-kit也不用了，刪掉，功能整合進現有的。」選項框選「併進 aos-agent ctl (Recommended)」。
- 11-18 晚，選項框三題：
  - kit 套上去寫到哪 →「寫進 stack (Recommended)」（照原做法）。
  - 「eca 定義也能套 kit」→ 要。
  - 「換包可以直接蓋」→ 要（已套一包時再套另一包，直接蓋過去，不用先卸）。

背景：[試驗 08](eca-claude-小試驗教學/08-不用aos-kit.md) 確認 `aos-kit add` 只是把 kit 的 `system.txt`、`tools.json` 抄進定義夾（舊檔另存 `.before-kit`），而且出廠 kit 用它裝不起來（`MakeMissing`）。

## 定下的做法

**一條指令**：`aos-agent ctl add --kit <包夾> …`、`aos-agent ctl set-def --kit <包夾> 名 定義`。包夾＝一個夾裡有 `system.txt`、`tools.json`（出廠的在 `$AOS_HOME/templates/kits/gather`、`review`；review 原本借 gather 的 tools，現在自己有一份一模一樣的，`templates/tests/kits` 比對兩份相同）。

**寫到哪**：寫成這隻 agent 在 **stack 裡自己那份**——跟 `aos-agent system set`、`tools add` 寫的是同一層，本來就是「stack 那份在＝蓋過定義那份」。**定義夾不動**，所以不用另存舊檔；同一份定義可以掛出好幾隻、各套不同的 kit。agent-fsm 每格重讀、eca 每題重讀。換定義（set-def 不帶 --kit）時那份 kit 留在 stack 裡。

**換包直接蓋**（11-18 晚裁）：stack 裡已有自己那份（上一包、`system set`、`tools add` 寫的）就蓋掉，內容一樣的不動；stderr 那行寫 `wrote`／`replaced`／`kept (same)`。原本的 `CopyExists`（要先 reset）拿掉了。

**eca 也能套**（11-18 晚裁）：照 eca 原本讀 stack 那份的規矩生效——system 附加在 CLI 自己的 system 後面（claude 身 `--append-system-prompt-file`，pi 身 `--append-system-prompt`），tools 換掉 aos 那組工具（MCP 那台）。**CLI 自帶的 Bash、Read 等工具還在，kit 的工具限制在 eca 上擋不住**；套在 eca 上時 stderr 那行會多一句說這件事。eca 的 `cli.json` 自己寫了 `tools` 鍵時，eca 根本不看 stack 那份，套了等於沒套，所以報 `KitBad`。

**拿掉 kit**：`aos-agent -t 名 system reset -y`、`aos-agent -t 名 tools reset -y`（現成指令）。

**什麼時候寫、壞了怎麼辦**：
- 先全查、什麼都還沒寫：包夾不在或缺檔＝`KitMissing`；定義沒宣告 `system`／`tools`、包裡 tools 不是 JSON 物件、eca 的 cli.json 寫了 tools＝`KitBad`。
- `ctl add` 在寄掛上信之前寫，所以要知道 stack：`-s` 給的，或沒走 kernel 時的預設 `<daemon stack>/procs/<名>`；`--stack-json`、走 kernel 又沒 `-s`＝`ArgumentsBad`。
- `set-def` 在拔掉之後、掛回之前寫；套了 kit 不印「stack 裡自己那份 tools 還疊在舊定義上」那行提醒。
- 掛不上（daemon 拒收、掛不回去）＝收回：新寫的拿掉、蓋掉的寫回原內容。逾時（`WaitFailed`／`DaemonFailed`）結果說不準、之後還可能掛上，就留著並提醒一行。

**aos-kit 各子指令的去向**：`add`→`ctl add/set-def --kit`；`make`、`check` 直接消失（`make` 本來就報 `MakeMissing`；出廠檔拼得對不對由 `templates/tests/kits` 檢查）；`ls`→看 `templates/kits/kits.json` 或 kits README 的表；aos-kit 本來就沒有還原，現在用 reset。aos-kit 本體與測試（`py/aos/apps/kit/`、`py/tests/apps/kit/`，19 檔）刪掉，`py/entries.json` 拿掉那一行。

## 留著沒動的

- 套 kit 之後跑 `aos-agent tools ls`，`tools.py` 的 check_pointer 會印一行「overrides …, not its definition's … (was the stack copied from another agent?)」——kit 的 tools.json 是指回 `$AOS_HOME/lib/packs/…`、不是指回定義那份，所以被當成別隻抄來的。這行是誤導，沒修（照現有測試，修了會撞到陣列形式的指標）。
