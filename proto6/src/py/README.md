# proto6/src/py

← [proto6 plan](../../plan/README.md)

inst 與 `aos-exec` 直接從 proto5 複製（proto5 `470f5a04`，即 `git log -1 --format=%h -- proto5/lib proto5/cli`），不重寫。說明文件看 proto5 的 [lib/docs/exec.md](../../../proto5/lib/docs/exec.md)、[directives.md](../../../proto5/lib/docs/directives.md)。

| 這裡 | 來源 | 內容改了什麼 |
|---|---|---|
| `bin/aos-exec` | `proto5/cli/aos-exec` | 沒改（它本來就找 `../lib`）。repo 的 `.gitignore` 擋 `bin/`，這檔是 `git add -f` 進來的 |
| `lib/aos_directives.py`、`aos_directives_base.py`、`aos_directives_options.py` | `proto5/lib/aos_directives.py` | 內容沒改；超過 300 行照職責拆三份（母模組留解析本體並 re-export；`_base`＝錯誤、文件、Context 等型別，`_options`＝`$opt` 選項物件），對外 import 不變 |
| `lib/aos_exec.py`、`aos_exec_run.py`、`aos_exec_spawn.py` | `proto5/lib/` 同名檔 | 改動 2、改動 3、改動 4 |
| `lib/aos_exec_wait.py` | 從 `aos_exec_run.py` 拆出 | 內容沒改：等與砍（`terminate()`、cpu 專用 `_wait_full()`、送訊號給 process group）；`aos_exec_run` re-export |
| `lib/aos_dirname.py` | 新寫 | 改動 3：`AOS_DIRNAME`，aos-exec 與 aos-tick 共用 |
| `lib/aos_inst.py` | `proto5/lib/aos_inst.py` | 沒改（改動 1 已撤回，2026-10-01） |
| `tests/test_inst_*.py`、`test_directives_*.py`（與 `_directives_util.py`） | `proto5/lib/test/test_inst.py`、`test_directives.py` | 沒改；超過 300 行照類別拆成多檔（測試名、類別名、內容不變） |
| `tests/test_exec_targets.py`、`test_exec_opts.py`、`test_exec_status.py`（原 `test_exec.py` 照類別拆）、`test_exec_full.py` | `proto5/lib/test/` 同名檔 | 跟著改動 2、3、4 改，另加一條「頂層 `user` 忽略」（標「proto6 改／新增」） |
| `tests/test_exec_spawn.py` | `proto5/lib/test/` 同名檔 | 只加改動 3 的一條（標「proto6 新增」） |
| `tests/_util.py` | `proto5/lib/test/_util.py` | 只改 `LIB`、`EXEC` 兩行路徑 |
| `tests/_*_util.py` | 從各測試檔拆出 | 測試檔超過 300 行照類別拆成 `test_<原名>_<主題>.py` 時，多檔共用的基底類別與小工具（`TickCase`、`DaemonCase`、`CtlCase`…）放這裡；開頭 `_` 不會被 discover 當測試檔 |
| ~~`tests/test_user.py`~~ | ~~新寫~~ | 2026-10-01 跟改動 1 一起刪掉 |
| `bin/aos-daemon`、`lib/aos_daemon.py`、`tests/test_daemon_config.py`、`test_daemon_run.py`（原 `test_daemon.py`） | 新寫 | 第三段最核心 daemon，見下面 [aos-daemon](docs/daemon.md#aos-daemon第三段最核心-daemon) |
| `lib/aos_daemon_config.py`、`aos_daemon_output.py`、`aos_daemon_run.py`、`aos_daemon_kill.py` | 從 `aos_daemon.py` 拆出 | 設定檔與 `Item`、stdout 與 aos-exec 輸出、每一項的迴圈、kill／restart 送訊號；母模組留共用狀態與 `main()` 並 re-export，見 [aos-daemon 的函式表](docs/daemon.md#aos-daemon第三段最核心-daemon) |
| `lib/aos_daemon_ctl.py`、`bin/aos-ctl`、`lib/aos_ctl.py`、`tests/test_ctl_loop.py`、`test_ctl_protocol.py`（原 `test_ctl.py`） | 新寫 | daemon 的控制模組與送指令的小工具，見下面 [控制模組與 aos-ctl](docs/ctl.md#控制模組與-aos-ctlm3n)。`bin/aos-ctl` 一樣被 `.gitignore` 擋，要 `git add -f` |
| `lib/aos_daemon_reload.py`、`lib/aos_daemon_state.py`、`tests/test_daemon_reload.py`、`tests/test_daemon_state.py` | 新寫 | daemon 的重讀設定、記住狀態兩個模組，見下面 [重讀設定與記住狀態](docs/reload-state.md#重讀設定與記住狀態m3m) |

現在跟 proto5 不同的只剩改動 2（資料夾目標找 inst 的位置）、改動 3（那個位置的 `.aos` 照 `AOS_DIRNAME`）與改動 4（用法錯回 1）。

各段全文按主題拆在 [`docs/`](docs/)（每份頂端一行導航），這裡每段只留標題、一兩句摘要與連結：

| 分檔 | 涵蓋的段 |
|---|---|
| [docs/changes.md](docs/changes.md) | 改動 1（撤回）、改動 2：資料夾目標怎麼找 inst、改動 3：`AOS_DIRNAME`、改動 4：結束碼慣例 |
| [docs/tick.md](docs/tick.md) | aos-tick（第一段 tick 核心）：目標、工作資料夾與環境變數、檔表、任務表預設與展開、互斥、結束碼、結束碼紀錄、review 導讀 |
| [docs/hooks.md](docs/hooks.md) | hooks：外掛掛點（m1h）、tick 模組 `modules["tasks-blocked"]`（B-636） |
| [docs/daemon.md](docs/daemon.md) | aos-daemon（第三段最核心 daemon） |
| [docs/ctl.md](docs/ctl.md) | 控制模組與 aos-ctl（m3n） |
| [docs/reload-state.md](docs/reload-state.md) | 重讀設定與記住狀態（m3m 模組一、三） |
| [docs/cgroup.md](docs/cgroup.md) | 收屍／cgroup（m3m 模組二） |
| [docs/mq.md](docs/mq.md) | 訊息與 aos-mq（m3m 模組四） |
| [docs/account.md](docs/account.md) | 帳號（m3m 模組五） |
| [docs/daemon-run.md](docs/daemon-run.md) | daemon 跑 daemon：輸出上限、鎖檔、kill／restart（第十九批） |

## ~~改動 1：認得頂層 `user`~~（2026-10-01 撤回）

2026-10-01 撤回：`lib/aos_inst.py` 換回 proto5 原檔，頂層 `user` 照不認得的鍵忽略。全文見 [docs/changes.md](docs/changes.md#改動-1認得頂層-user2026-10-01-撤回)。

## 改動 2：資料夾目標怎麼找 inst

資料夾目標先找 `xxx/.aos/inst.json`、再找 `xxx/inst.json`；拿掉 proto5 的 `--dir-target`。全文見 [docs/changes.md](docs/changes.md#改動-2資料夾目標怎麼找-inst)。

## 改動 3：`AOS_DIRNAME`（2026-10-01）

環境變數 `AOS_DIRNAME` 決定狀態資料夾的名字（沒設＝`.aos`、空字串＝資料夾本身），判斷只在 `lib/aos_dirname.py`。全文見 [docs/changes.md](docs/changes.md#改動-3aos_dirname2026-10-01)。

## 改動 4：結束碼慣例，用法錯回 1（2026-10-01）

aos-exec 的用法錯由 proto5 的 2 改 1，附 aos-exec 現在的結束碼表。全文見 [docs/changes.md](docs/changes.md#改動-4結束碼慣例用法錯回-12026-10-01)。

## aos-tick（第一段 tick 核心，新寫）

照 plan 第一段新寫的 `aos-tick [<目標>]`：目標怎麼認、給任務的環境變數、`lib/aos_tick*.py` 檔表、任務表的頂層預設與開格整份展開、同資料夾互斥、結束碼與結束碼紀錄 `tick/current/`。全文見 [docs/tick.md](docs/tick.md)。

### review 導讀

讀程式的順序（`aos_dirname` → `aos_tick.run_tick()` → record → table → run → 測試）、plan 步驟對到哪個函式、我自己做的判斷。全文見 [docs/tick.md](docs/tick.md#review-導讀)。

## hooks：外掛掛點（m1h）

任務表頂層的 `hooks`（`before_all`、`after_task.<id>`、`after_every_task`、`after_all` 四個掛點），spec 正本 B-635。全文見 [docs/hooks.md](docs/hooks.md#hooks外掛掛點m1h)。

## tick 模組 `modules["tasks-blocked"]`（B-636）

任務表 `modules["tasks-blocked"]`：某一項之前看到 `tick/tasks-blocked` 時先依序跑的 `insts`，跑完再看一次決定放行或擋下。全文見 [docs/hooks.md](docs/hooks.md#tick-模組-modulestasks-blockedb-636)。

## aos-daemon（第三段最核心 daemon）

「一個叫 `aos-exec` 的 cron」：讀設定檔裡的 inst 清單，每項照自己的週期叫一次 `aos-exec <inst 字面值>`。全文見 [docs/daemon.md](docs/daemon.md#aos-daemon第三段最核心-daemon)。

## 控制模組與 aos-ctl（m3n）

設定檔寫 `modules.control` 就掛上的控制模組（一行 JSON 進出的 socket：`wake`／`pause`／`resume`／`status`）與送指令的小工具 `aos-ctl`。全文見 [docs/ctl.md](docs/ctl.md#控制模組與-aos-ctlm3n)。

## 重讀設定與記住狀態（m3m）

m3m 模組一（重讀設定）、三（記住狀態），各自有寫才掛。全文見 [docs/reload-state.md](docs/reload-state.md#重讀設定與記住狀態m3m)。

## 收屍／cgroup（m3m 模組二）

`lib/aos_daemon_cgroup.py`（spec B-644、格式 P-124），設定檔寫 `modules.cgroup` 才掛。全文見 [docs/cgroup.md](docs/cgroup.md#收屍cgroupm3m-模組二)。

## 訊息與 aos-mq（m3m 模組四）

`lib/aos_daemon_mq.py`、`lib/aos_mq.py`、`bin/aos-mq`，設定檔寫 `modules.mq` 才掛。全文見 [docs/mq.md](docs/mq.md#訊息與-aos-mqm3m-模組四)。

## 帳號（m3m 模組五）

`lib/aos_daemon_account.py`（主程式側）與 `lib/aos_daemon_root.py`＋`bin/aos-daemon-root`（root 端，spec B-646、格式 P-126），設定檔寫 `modules.account` 才掛。全文見 [docs/account.md](docs/account.md#帳號m3m-模組五)。

## daemon 跑 daemon：輸出上限、鎖檔、kill／restart（第十九批）

上層 daemon 把下層 daemon 當一項跑時要的三件事：輸出上限、鎖檔、kill 與 restart。全文見 [docs/daemon-run.md](docs/daemon-run.md#daemon-跑-daemon輸出上限鎖檔killrestart第十九批)。

## 跑測試

```sh
cd proto6/src/py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=lib python3 -m unittest discover -s tests
```
