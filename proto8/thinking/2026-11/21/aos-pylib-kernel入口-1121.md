編譯程式庫的 kernel 入口（`from aos.py.kernel import defs`）施工紀錄（11-21，線 top-1121-kdefs）：做了什麼、怎麼寫、驗收、替使用者做的選擇、沒做的。

← [2026-11-21](README.md)｜設計稿：[aos-pylib-plan-1120/02「kernel 以後怎麼接上」](../20/aos-pylib-plan-1120/02-去留對照與kernel接口.md#kernel-以後怎麼接上只留接口)｜使用者答案：[12 第 9 題](../20/aos-pylib-plan-1120/12-使用者已答.md#待裁第-9-題)、[初始 kernel 八題](../20/aos-init-kernel-1120/06-使用者已答.md)｜上一刀：[第 5 刀](../20/aos-pylib-k5-1120.md)

## 依據（使用者原話）

- 待裁第 9 題「編譯：kernel 以後要編譯時，寫的人從哪裡 import？」選「from aos.py.kernel import defs」（11-20）。
- 11-21：「編譯的kernel入口那塊可以派」。

設計稿只留了接口與一段示意（`defs.Kernel("Main llm kernel", knobs={"slots": 2}, hooks=[prio])`、`defs.main(k)`），寫明 kernel 本身長什麼樣等初始 kernel 八題；八題 11-20 都答了，所以照示意的名字做，其餘細節照 `templates/kernel/` 那幾份手寫夾的樣子定（下面「替使用者做的選擇」逐條）。

## 一句話

寫一支 `kernel.py` 宣告一個 kernel，`python3 kernel.py --compile` 編譯出跟 `templates/kernel/` 手寫夾同樣的定義夾；`@fn.hook` 的函數照樣抽成 `fn/<名>.py`，跟 `agent.py` 同一套。

```python
from aos.py.kernel import defs
from aos.py import fn

@fn.hook("before_verdict")
def no_night_jobs(event):
    """Refuse procs named night-something."""
    names = (event.get("body") or {}).get("procs_added") or {}
    if any(str(n).startswith("night") for n in names):
        return fn.block("no night jobs here")

kernel = defs.Kernel("Let at most two procs run at once, and no night jobs.",
                     knobs={"max_running": 2, "queue": True}, hooks=[no_night_jobs])
defs.main(kernel)          # python3 kernel.py --compile／--dry-run／--help
```

## 改了哪些檔

| 檔 | 做什麼 |
|---|---|
| `py/aos/kernel_spec.py`（新） | `defs.Kernel(說明, knobs=, hooks=, program=, body=)`、`defs.loop(every_ms=)`、`defs.daemon(every_ms=)`、`defs.main(物件)`、`defs.home`／`defs.env`（從 agent 那邊轉出）。`Kernel` 是 `spec_unit.Unit` 的子類：只寫 `_files`、`events`，命令列殼、寫檔後端、`fn/` 抽出都用現成的 |
| `py/aos/py/kernel/__init__.py`（新） | `from aos.py.kernel import defs`（轉匯出 `aos.kernel_spec`，同 `aos.py.agent` 的寫法） |
| `py/aos/py/__init__.py` | 檔頭多一行用法；`SUBMODULES` 多 `kernel`（`aos.py.kernel` 用名字叫得到） |
| `py/aos/fn_spec.py` | 檔頭一句帶上 kernel.py；`LIBRARY` 多 `aos.py.kernel.defs`、`aos.kernel_spec`（函數裡用 `defs` 照樣 SpecBad） |
| `templates/kernel/kernel-python/`（新） | 骨架：`kernel.py`＋它編出的 `_entry`、`loop.json`、`kernel.json`＋英文 README |
| `templates/kernel/README.md` | 範本表多一列 `kernel-python/` |
| `py/tests/test_kernel_spec.py`（新） | 15 項：三份手寫範本對得上、hook 分流與抽出、錯誤、命令列、骨架產物跟 `kernel.py` 一字不差、真站跑一輪 |

## 編出什麼

| `body=` | 寫的檔 | 對照的手寫範本 |
|---|---|---|
| `defs.loop(every_ms=N)` | `_entry`（`aos-loop loop.json`）、`loop.json`（四個 loop 點接 `aos-hook fire`，清單 `loop_hooks.json`）、`kernel.json` | `procs-kernel/`、start-api 的 `perm/` |
| `defs.daemon(every_ms=N)` | `_entry`（`aos-daemon --enable-logs daemon.json`）、`daemon.json`（帶 `_sweeper` 列）、`kernel.json` | `daemon-kernel/`、`llm-kernel/` |

- `program="kernel_llm"` 多一份 `interfaces.json`（`aos-ledger`，同 `llm-kernel/`）。
- `hooks=` 有給時：判前、判後、代回之前三個點進 `kernel.json` 的 `hooks`；身體是 loop 時 aos-loop 的四個點（`after_start`、`after_stop`、`before_run`、`after_run`）進 `loop_hooks.json`（四個點都沒有也寫一份空的，免得留著舊的）。身體是 daemon 時掛 loop 的點＝SpecBad（aos-daemon 不收那幾個鍵）。
- 每份 json 都帶 `description`；`kernel.json` 的 `description`＝第一個參數（兩支站程式都不管不認得的鍵，llm-kernel 範本本來就有）。`README.md` 不在才寫。其餘檔（`.env`、llm kernel 的 `endpoints/`、`fake_slow`）不碰。

## 驗收

環境：`git archive 949925842 proto8 wf` 抄到 `~/.aos/scratch/top-1121-kdefs/base`，`cp -a` 成 `new` 再只疊本線的檔，各自在複本裡 `install.py`；腳本一律先 unset 所有 `AOS_*`、`env -i PATH=<複本>/bin:… AOS_HOME=<複本>`。

1. **對得上手寫範本**：`procs-kernel`、`daemon-kernel`、`llm-kernel` 三份的 `kernel.json` 當 `knobs=` 餵進去，編出的每份檔拿掉 `description` 後跟範本逐鍵相同；唯一不同是 `_entry` 寫成物件（`{"description", "argv"}`，同 `llm-team/`），`argv` 相同。
2. **真站跑一輪**（測試 `Live`）：編出的 `kernel.json`＋抽出的 `fn/no_night_jobs.py`，真的 `aos-post` 寄兩封 `procs_added`、真的 kernel 站跑一輪：`night1` 回 `{"applied": false, "error": {"code": "HookRejected", "msg": "no night jobs here"}}`，`day1` 轉進 daemon 的 ctl 信箱。
3. **真 daemon 掛上去**（手跑一次，`live/live.py`）：暫存根 daemon 掛一列編好的站（`body=defs.loop(every_ms=150)`、上面那個函數 hook 加一個 `after_start` 函數 hook），經站寄 `procs_added`：`night1` 被拒（同上），`day1` 上了根的表；`after_start` 的函數 hook 跑了（它的小格 `hooks/mark_start/` 裡有它寫的檔：hook 的 `AOS_STACK` 是自己的小格，不是站的 stack）。收尾 `aos-daemon-ctl -d <自己的根> shutdown`，根退 0。
4. **相關夾**（base／new）：`test_agent_spec*` 80／80、`test_fn*` 44／44、`test_aos_py*` 17／17、`test_hook_point*` 36／36、`test_tool_spec` 5／5、`tool-python` 5／5、`tools_def` 12／12、`defs` 28／28、`agent_def` 32／32、`kernel` 126／126，全 OK；`test_kernel_spec` 0 → 15 OK。
5. **全套**：見下節。

## 全套

`proto8` 底下 57 個 `tests` 夾一夾一夾跑（base／new 同時跑，機器有其他線在跑）：base 1907 項、new 1922 項（多的 15＝`test_kernel_spec`）。逐夾比，除了 `py/tests` 多這 15 項，只差一處；另有兩夾兩邊同樣紅：

- `cpp/aos-loop/tests`：base 有 1 個 error（`test_cause_sigint_ignores_file` 等 SIGINT 退出逾時 10 秒，負載高時的時序），new 52 項全過；本線沒碰 aos-loop。
- 兩邊同樣紅：`templates/tests` 1 failure（`start-api/agents/ann/README.md` 跟 `agent-fsm/README.md` 不同，HEAD 949925842 別線改了範本文件、抄本沒跟上）、`frontend/tests` 5 errors（兩邊相同，跟本線無關）。

## 替使用者做的選擇

1. **類別與欄位名照設計稿示意**：`defs.Kernel`、`knobs=`、`hooks=`、`defs.main(k)`；示意裡寫「不是設計」，沒另外問。
2. **一個類別、用 `program=` 分兩種**（`"kernel"` 框架站、`"kernel_llm"` llm kernel），不分成兩個類別；值就是 `lib/tools/aos/` 底下那支程式的名字。只收這兩個，自己寫的站程式還不收。
3. **身體用宣告 `defs.loop(every_ms=)`／`defs.daemon(every_ms=)`**：`defs.loop` 跟 agent 那邊同名同意思（`loop.json` 的間隔）；設計稿形狀甲寫的 `defs.proc()` 沒用，因為兩種身體都能掛成板子上的一列，差在跑的是 aos-loop 還是 aos-daemon。
4. **不給 `body` 的預設照起手範本 start-api**：`kernel` 用 loop（同 `perm/`）、`kernel_llm` 用 daemon（同 `llm/`）。
5. **`knobs` 原樣寫進 `kernel.json`、不驗鍵**：兩支程式本來就不管不認得的鍵，鍵的意思由程式定；只擋 `description`、`hooks` 兩個（各有自己的參數）。
6. **daemon 身體一律帶 `_sweeper` 列、`--enable-logs`**，同三份範本（使用者 11-20 清道夫「算核心」）；沒有開關。
7. **loop 的四個點也收進 `hooks=`**，編譯時分到 `loop_hooks.json`；有給 `hooks=` 就寫一份（可能是空的）。
8. **骨架放 `templates/kernel/kernel-python/`**（跟 `agent-python` 對稱，但住在 kernel 夾底下），內容是什麼都不管的框架站（`knobs={}`、`body=defs.loop()`，同 start-api 的 `perm/` 出廠的 `{}`）；英文 README 照 agent-python。
9. **`aos.py.kernel` 只有 `defs`**：對活的 kernel 下指令的遙控器沒做（站沒有自己的指令）。

## 沒做的

- `defs.load`（從另一支 `kernel.py` 衍生）、`defs.extern`（某一欄編成連結）、`files=`、`_metainfo.json`：agent 那邊有、kernel 這邊先不給；手寫範本也沒有 `_metainfo.json`。
- llm kernel 的 endpoint 程式（`endpoints/litellm`、`fake_slow`）：照舊手寫放在旁邊，編譯不碰；`endpoints` 那張表照樣寫在 `knobs` 裡。
- `knobs` 的鍵不驗（見選擇 5）：寫錯的鍵編得過、站跑起來才不理它或報 `CfgBad`。
- `fn_spec` 的錯誤句還寫「agent.py」（例：「defined at the top of agent.py」），在 kernel.py 裡用到也這樣說；意思對、名字不對。
- 知識庫、`py/docs`、`templates/README.md` 沒寫（agent-python 當初也是「先只給人用」）。
- 現有四份手寫範本（procs-kernel、daemon-kernel、llm-kernel、llm-team）沒改成用 `kernel.py` 編。

## 使用者怎麼試

改的是 `py/`：活樹要在 `~/repo/aos/proto8` 跑 `install.py` 才吃到（要使用者點頭）。之後：

```sh
cp -r $AOS_HOME/templates/kernel/kernel-python perm
python3 perm/kernel.py --dry-run          # 看會寫什麼
python3 perm/kernel.py --compile          # 寫進 perm/
aos-daemon-ctl add perm                   # 掛成一列；要經過它的 agent 把 AOS_KERNEL 設成 <這列的 stack>/requests
```
