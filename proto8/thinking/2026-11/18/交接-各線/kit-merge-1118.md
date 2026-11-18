kit-merge-1118 線 11-18 16:5x 收手時的交接：aos-kit 併進 aos-agent ctl --kit，做到一半。

# kit-merge-1118 交接

使用者 11-18 的裁定（逐字）：「aos-kit也不用了，刪掉，功能整合進現有的。」選項框選的是「併進 aos-agent ctl (Recommended)」。

## 做法（已定、已寫進程式）

- `aos-agent ctl add --kit <包夾>`、`aos-agent ctl set-def --kit <包夾> 名 定義`：把包夾裡的 `system.txt`、`tools.json` 寫成這隻 agent 在 **stack 裡自己那份**。這一層跟 `system set`、`tools add` 寫的是同一層。**定義夾不動**，所以不用另存 `.before-kit`。
- 還原：`aos-agent -t 名 system reset -y`，再 `aos-agent -t 名 tools reset -y`（兩支都是現成指令）。
- 換包：先照上面還原，再 `set-def --kit`。沒先還原會報 `CopyExists`。
- 錯誤代號：`KitMissing`（包夾不在或缺檔）、`KitBad`（定義是 eca，也就是有 cli.json；或定義沒宣告 system／tools；或 tools 不是 JSON 物件）、`CopyExists`（stack 裡已經有自己那份，而且內容不同）。內容一樣的那份就留著。
- eca 定義一律拒收。理由：eca 的 CLI 自帶 Bash 等工具，kit 限制的工具在 eca 上擋不住。
- `ctl add` 在寄出掛上信**之前**寫檔：daemon 拒收就收回；逾時（WaitFailed／DaemonFailed）結果說不準，就留著並提醒一行。所以 add 要知道 stack 在哪：用 `-s`，或沒走 kernel 時的預設 `<daemon>/procs/<名>`。給 `--stack-json`，或走 kernel 又沒給 `-s`，報 `ArgumentsBad`。
- `set-def` 先檢查完全部（kit 壞了什麼都不動），在拔掉之後、掛回之前才寫；掛不回去就收回。套了 kit 時不印 warn_own_tools 那行提醒。
- aos-kit 各子指令的去向：`add`→`ctl add/set-def --kit`；`make`、`check` 直接消失（`make` 本來就報 MakeMissing；出廠檔拼得對不對由 templates/tests/kits 檢查）；`ls`→看 `templates/kits/kits.json` 或 README 的表；aos-kit 本來就沒有還原，現在用 reset。
- kit 夾格式：一個 kit＝一個夾，裡面有 system.txt 和 tools.json。review 原本借用 gather 的 tools，現在補一份一模一樣的 `review/tools.json`（測試會比對兩份相同）。

## 動過的檔

**新增**
- `proto8/py/aos/apps/agent/ctl/kit.py`（完成）
- `proto8/py/tests/apps/agent/test_ctl_kit.py`（寫好了，**還沒跑出結果**）
- `proto8/templates/kits/review/tools.json`（完成）
- 本檔

**修改**
- `proto8/py/aos/apps/agent/ctl/add.py`（完成）：加 --kit、lay_kit()、失敗時收回
- `proto8/py/aos/apps/agent/ctl/set_def.py`（完成）：只加了 --kit 的幾段，cooldown 線的字沒動
- `proto8/py/aos/apps/agent/README.md`（完成）：ctl add／set-def 的 usage 兩行，加一條「--kit」說明
- `proto8/py/entries.json`（完成）：刪掉 aos-kit 那一行
- `wf/tools/index_gen_desc.json`（完成）：刪掉 tests/apps/kit 那個鍵
- `wf/tools/index_gen.json`（完成）：`*kits*/*.txt` 的描述從「aos-kit 的…」改成「kit（配給包）的…」
- `proto8/templates/kits/README.md`、`kits.json`、`gather/tools.json`（description 那句）（完成）
- `proto8/templates/tests/kits/test_kits.py`（完成）：加兩支測試
- `proto8/knowledge/aos/kits.json`（完成）
- `proto8/templates/README.md`（完成）：kits 那一列

**git rm**（已 rm，只屬於 aos-kit）
- `proto8/py/aos/apps/kit/`（README.md、__init__.py、add.py、main.py、recipe.py）
- `proto8/py/tests/apps/kit/`（test_kit.py、fixtures/kits、fixtures/kits-stale）

生成物（`_index.json`、`wf/knowledge/code-map/`）沒手改，等排隊的生成器重生。

## 還沒做

1. 設計稿 `proto8/thinking/2026-11/18/aos-kit-併進ctl.md`（上面「做法」一節可以直接當底稿）。程式裡的檔頭和 README 已經先連到這個檔名。
2. 試驗 08 的檔頭與教學 README 的 08 那列，各加一句「aos-kit 已於 11-18 移除，功能併進 aos-agent ctl（見 aos-kit-併進ctl.md）」。
3. 把裁定逐字記進 `cpp-py-改名/08-要裁的題.md` 的「11-18 施工當天的題」；日索引補一列。
4. 測試：改後那份沒跑完（見下）。假腦實操沒做。最後的 `grep -rn aos-kit` 也沒做：收手前看到剩下的只有生成物和 thinking。
5. 已知小雜訊：套了 kit 之後跑 `aos-agent tools ls`，會因為 tools.py 的 check_pointer 印一行「overrides …, not its definition's … (was the stack copied from another agent?)」，這是誤導。沒修，因為照現有測試，修了會撞到陣列形式的指標。要不要修，留給使用者決定。

## 要使用者裁的題

- 甲（已做）：寫進 stack，自己那份蓋過定義，定義夾不動。乙：像舊的 aos-kit 那樣就地改定義夾，舊檔另存 `.before-kit`。後果差別：甲是一隻一隻套，換定義時那份 kit 留在 stack 裡；乙是同一份定義掛出來的每一隻都改到。
- eca 定義要不要也允許套 kit（現在一律拒收）。
- 換包時要不要允許直接蓋掉 stack 裡那份（現在要先 reset）。

## 測試到哪

- WSL 暫存在 `~/.aos/scratch/kit-merge-1118/`：`base/`（git archive HEAD，已裝好）、`after/`（rsync 工作樹之後裝）。腳本有 `setup.sh base|after`、`tests.sh base|after`、`one.sh 夾 模組`。
- 改前基準 `tests.sh base` 已在背景跑（pid 記在 `tests-base.pid`），結果寫在 `logs-base/summary.txt`、`fails.txt`。收手時要停掉。
- 改後：`setup.sh after` 加 `one.sh … test_ctl_kit` 跑到一半，沒看到結果。明天的做法：重跑 `setup.sh after`，再跑 `tests.sh after`，然後拿 `fails.txt` 跟 base 那份逐支比對。
