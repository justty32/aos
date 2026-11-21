# proto8/py/aos/apps/hook — aos-hook 指令（讓任何子程式提供 hook 點），與 aos-loop 那一層的 hook 點宣告

← [cmd](../../../docs/05-commands.md)｜讀宣告的小庫：[aos.hook_point](../../hook_point.py)｜跑 hook 的引擎：[aos.hook_run](../../hook_run.py)｜設計：[aos-hook-plan-1120 的 05](../../../../thinking/2026-11/20/aos-hook-plan-1120/05-發事件指令.md)（[12 採納表](../../../../thinking/2026-11/20/aos-hook-plan-1120/12-採納表.md)為準）

| 檔 | 是什麼 |
|---|---|
| `main.py` | `aos-hook` 本體：`fire`、`points`、`check` 三個子指令、英文 `--help`；點與清單從哪來（`--points`／`--list`；`--agent DEF_DIR` 交給 [`agentlib/agent_hooks.py`](../../agentlib/agent_hooks.py) 的 `source`）。讀清單、驗格、驗型別在小庫 `aos/hook_lists.py`，經 `aos.hook_point.open` 的遙控器用 |
| [`loop_points.json`](loop_points.json) | 用 aos-loop 跑、loop.json 有接線的子程式提供的四個點：`after_start`、`after_stop`；`before_run`、`after_run`（每跑一次身體的前後；範本的 loop.json 經這支發，旗標檔在才跑） |

使用者 11-20「任何子程式，含非 Python」；施工是第 4 刀（線 aos-hook-k4-1120，使用者「先開第 4 刀」）。第 4 刀只加、沒人叫它；第 5 刀後半（線 top-1121-hook5）起，範本的 loop.json 用它發 `before_run`／`after_run`（agent 的範本經 `--agent`、procs-kernel 範本經 `--points`／`--list`，procs-kernel 連起停兩點也是）；11-21（線 top-1121-hookfire，使用者「可以」）起，agent 範本的起停（`on_start`／`on_stop` 發 `after_start`／`after_stop`）也經 `--agent` 用它，原本專發這兩點的那支小程式拿掉了。第 2 刀 2a（線 aos-hook-k2-1120）把它改成經小庫的遙控器跑、接上 `--agent`，行為沒變；第 2 刀後半（線 aos-hook-k2b-1120）把原本的 `lists.py` 拆進 `main.py` 與 `agent_hooks.source` 後刪掉（使用者 11-20「lists.py可以刪掉」），agent 一家發事件的程式（fsm 格程式、aos-eca-turn、aos-mcp）與 kernel 也都改用遙控器。

Python 寫的提供者不用起這支：直接 `aos.hook_point.open(…)` 開一個遙控器、每個點 `fire` 一行（介面寫在 [`hook_point.py`](../../hook_point.py) 檔頭；agent 一家另有 [`agentlib/agent_hooks.py`](../../agentlib/agent_hooks.py)）。

## 提供一個點＝一份宣告＋在那個時機起一次 `aos-hook fire`

宣告 `hook_points.json`（格式見[設計 01](../../../../thinking/2026-11/20/aos-hook-plan-1120/01-宣告格式.md)、小庫檔頭）寫你會發哪些點；掛 hook 的人照舊寫一份有 `hooks` 表的清單（跟 agent 的 `hooks.json` 同一種格）。

```sh
# hook_points.json 宣告了 before_save：fields {"file": …}，change {"file": "nonempty_string"}，block true
out=$(aos-hook fire --points "$HERE/hook_points.json" --list "$HERE/config.json" --stack "$STATE" \
        --field file="$f" before_save)
case $? in
  0)  f=$(printf '%s' "$out" | jq -r .data.file) ;;      # hook 改過的值拿回來
  10) echo "save skipped by a hook" >&2; exit 0 ;;       # 被攔下：你自己決定是什麼意思
  *)  exit 1 ;;                                          # 錯誤行 aos-hook 已經印了
esac
```

實跑（兩個 hook：`a_deny` 是 python，檔名 secret 開頭就退 10；`b_rename` 是 sh，回 `{"file": "<原名>.bak"}`）：

```
$ aos-hook fire --points hook_points.json --list config.json --stack state --field file=notes.txt before_save; echo "exit $?"
{"data": {"file": "notes.txt.bak"}, "changed": ["file"], "blocked": false, "hook": null, "text": ""}
exit 0
$ aos-hook fire --points hook_points.json --list config.json --stack state --field file=secret.txt before_save; echo "exit $?"
{"data": {"file": "secret.txt"}, "changed": [], "blocked": true, "hook": "a_deny", "text": "secret files are not saved\n"}
exit 10
$ aos-hook fire --points hook_points.json --list config.json --stack state before_sav; echo "exit $?"
aos-hook: error: EventUnknown no point before_sav in hook_points.json (points: before_save)
exit 1
```

C++ 不用 link 任何 hook 的東西，就是起一支程式；只看結束碼時加 `-q`：

```cpp
aos::loop::Run r = aos::loop::run_once(target({"aos-hook", "fire", "-q", "--points", here + "/hook_points.json",
                                               "--list", cfg_path, "--field", "job=" + job, "before_job"}));
if (r.code == 10) { /* blocked: skip this job */ }
else if (r.code != 0) { /* aos-hook printed its error line */ }
```

## 規矩

- **旗標**（三個子指令共用，子指令前後都收）：`--points FILE`（可重複；同名的點在兩份裡說法要一致，不一致＝`PointsBad`）、`--list FILE`（可重複；後面的同名蓋前面的、`null`＝關掉；**檔不在＝沒有 hook**，跟 agent 的 stack 那份一樣）、`--stack DIR`（hook 的小格放 `DIR/hooks/<名>/`；沒給＝`$AOS_STACK`；都沒有＝`StackMissing`，只有 `fire` 要）。
- **`--agent DEF_DIR`**（第 2 刀 2a）：一次給齊一隻 agent 的那一套，跟 `--points`／`--list` 二選一（一起給＝`ArgumentsBad`）。點＝定義夾 `interfaces.json` 的 `aos-agent.hook_points`（`hook_point.for_definition`；**今天的定義夾都還沒有這個鍵，第 3 刀才加**，沒有＝沒有點，發什麼都是 `EventUnknown … (points: none)`）；清單＝定義宣告的 `hooks` 檔，疊上 stack 裡同名那份（沒有 stack＝只有定義那份，`check`、`points` 可以這樣用）；on_clock 的格另驗 agent 自己的規矩（`every_cycles`／`every_ms` 恰好一個、正整數；`clock` 非空字串）；`fire … after_start` 先清 stack 裡各 hook 的 on_clock 狀態（`agentlib/hook_clock.clock_restart`；清不掉＝一行 warning）。不是資料夾＝`ArgumentsBad`。
- **事件資料**，後者蓋前者：stdin 的 JSON 物件（空的、是終端＝`{}`；鍵原樣傳下去）→ 宣告裡寫了 `env` 的欄位：環境變數去頭尾空白後不是空的才用（`type: int` 要是整數，不然 `ArgumentsBad`），沒設就留 stdin 給的、都沒有＝`null` → `--field NAME=VALUE`、`--field-file NAME=PATH`（讀檔去頭尾空白；檔不在＝`null`）→ `--field-default NAME=VALUE`（前面都沒給出值、或是 `null` 才用）。同一個 NAME 同時給 `--field` 與 `--field-file`＝`ArgumentsBad`；同一個旗標給兩次＝後面那個算。`--field` 給的名字不在宣告裡也照收（跟 stdin 的鍵一樣不驗）。
- **stdin 一定會被讀到底**（除非是終端）：從別的程式起 `aos-hook` 時，stdin 要嘛給 JSON、要嘛接 `/dev/null`；接著一條永遠不關的管子它會一直等。aos-daemon 底下的 aos-loop 本來就是 `/dev/null`。
- **stdout**：一行 JSON `{"data", "changed", "blocked", "hook", "text"}`（引擎 `hook_run.fire` 的回值原樣）；`-q`＝不印。
- **結束碼**：0＝照常（沒人掛也是 0）；10＝被攔下（只有宣告 `block: true` 的點會）；1＝錯，stderr 一行 `aos-hook: error: CODE reason`、stdout 不印。代號：`HookFailed`（`on_error: stop` 的 hook 失敗：退 0／10 以外的碼、逾時、起不來、回話不是 JSON 物件、改回來的值型別不對）、`HooksBad`、`PointsBad`、`EventUnknown`（宣告裡沒有這個點）、`ArgumentsBad`、`StackMissing`，以及 `FlagUnknown`、`CommandUnknown`。`on_error: continue` 的 hook 失敗＝一行 warning、照常退 0。handler 的 stderr 原樣透出。
- **跑 hook 全在引擎**（`aos.hook_run.fire`，agent 與 kernel 用的同一份）：照名字排序、前一個改的後一個看得到、退 10 攔下就停、`condition` 比宣告裡 `condition` 指的欄位、`intercept`／`async`／`timeout_ms`／`on_error` 照舊。這裡只多兩件：**改回來的值照宣告的 `change` 型別驗**（`string`、`nonempty_string`、`object`、`any`；在每個 hook 跑完的當下驗，壞值不會傳給下一個，照那個 hook 的 `on_error`），與**清單驗格時，某個點的 `entry_keys` 寫在別的點的格上＝`HooksBad`**。
- 宣告標 `not_fired_yet` 的點照樣發得動；`check` 看到有 hook 掛在這種點上只印一行 warning（aos 自己帶的宣告第 5 刀後半起沒有這種點了）。
- **旗標檔**（第 5 刀後半；設計 [06「沒人掛時怎麼做到零成本」](../../../../thinking/2026-11/20/aos-hook-plan-1120/06-loop層的點.md)、12 的 A1／B1）：點裡有 `before_run`／`after_run` 時，`fire … after_start` 與帶 stack 的 `check`（`--stack` 或 `$AOS_STACK`）照生效的清單對 stack 裡的 `hook_before_run.flag`／`hook_after_run.flag`——有 hook 掛那個點就建、沒有就刪（程式在 [`aos/hook_flags.py`](../../hook_flags.py)）；`check` 多印一行 `flags: 路徑 on|off, …`。寫不成＝`WriteFailed`。其餘子指令、別的事件都不動旗標（讀的一方去刪會跟剛掛上的一方互踩）。loop.json 的 `on_before_run_if`／`on_after_run_if` 指著這兩個檔，檔不在 aos-loop 就不起這支。agent 那邊改清單的 `aos-agent hook add／rm／reset` 也對同兩個檔。
- `points` 一個點一段：第一行 `名字  phase  condition 欄位  change 鍵 (型別)  can block`，下面每個提供者的 when／if blocked／if failed／not fired yet、每個欄位；`-j` 印合併後的 JSON（`said` 每份宣告一項）。
- `check` 只驗：宣告讀得過、每份清單的每一格對得上宣告；不跑 handler、不解 handler 的指示詞、不看 handler 的檔在不在。成功印一行 `ok: …`、退 0。
- 誰都能發事件、替別人的 stack 跑 hook：不擋（[設計 05「邊緣」](../../../../thinking/2026-11/20/aos-hook-plan-1120/05-發事件指令.md#邊緣)）；handler 裡再叫 `aos-hook fire` 是連鎖觸發，不檢測。

## 成本

每發一次＝起一支 Python（沒人掛約 36 毫秒；數字在[施工紀錄](../../../../thinking/2026-11/20/aos-hook-k4-1120.md#耗時)）；有 handler 時再加 handler 自己的。Python 寫的提供者直接 import 小庫（`aos.hook_point.open`），沒有這筆。

## 測試

`py/tests/apps/hook/test_hook_cli.py`、`test_hook_cli_agent.py`（`--agent`）（跑裝好的 `bin/aos-hook`，handler 是真的 sh 與 python3、經 aos-exec；沒有 daemon）。遙控器本身：`py/tests/test_hook_point_open.py`、`py/tests/test_agent_hooks.py`。
