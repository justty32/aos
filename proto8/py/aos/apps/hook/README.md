# proto8/py/aos/apps/hook — aos-hook 指令（讓任何子程式提供 hook 點），與 aos-loop 那一層的 hook 點宣告

← [cmd](../../../docs/05-commands.md)｜**hook 總文件（整套怎麼回事）：[docs/](docs/README.md)**｜跑 hook 的引擎：[aos.hook_run](../../hook_run.py)｜讀被勾清單：[aos.hook_lists](../../hook_lists.py)｜interfaces.json 的 hooks／hookeds 與宣告：[aos.hook_point](../../hook_point.py)｜現在的樣子：[hook 新格式施工 01](../../../../thinking/2026-11/21/hook-新格式施工-1121/01-現在怎麼寫.md)（設計沿革：[aos-hook-plan-1120](../../../../thinking/2026-11/20/aos-hook-plan-1120/05-發事件指令.md)、[aos-hook-簡化-1121](../../../../thinking/2026-11/21/aos-hook-簡化-1121/07-使用者已答.md)）

| 檔 | 是什麼 |
|---|---|
| `main.py` | `aos-hook` 本體：只有 `fire` 一個子指令、英文 `--help`；清單從 `--list` 或 `--def` 的 interfaces.json 來，跑 handler 交給引擎 `aos.hook_run` |
| [`docs/`](docs/README.md) | hook 總文件：三樣東西一條流程、宣告格式、寫 handler、掛 hook、各家的點與規矩、自己發事件、限制與還沒做的 |
| [`loop_hooks.json`](loop_hooks.json) | 用 aos-loop 跑、loop.json 有接線的子程式提供的四個點的宣告：`after_start`、`after_stop`；`before_run`、`after_run`（每跑一次身體的前後）。只是參考，`aos-hook` 不讀它 |

使用者 11-20「任何子程式，含非 Python」；11-21 簡化到「第四層」：`aos-hook fire` 只做一件事——照名字一個一個起掛在那個事件上的 handler、交回各自的退出碼與 stdout。**攔不攔、改不改欄位、比不比條件、失敗怎麼算，都是發事件的程式自己決定**（使用者 11-21「發事件的程式自己決定」）；宣告「只是參考」，`aos-hook` 從不讀。範本的 loop.json 用它發 loop 的四個點。

Python 寫的提供者不用起這支：直接叫引擎 `aos.hook_run.fire(event, data, entries, stack)`（清單用 `aos.hook_lists.load` 讀；介面寫在兩支的檔頭）。agent 一家另有自己的規矩與遙控器（[`agentlib/hooks.py`](../../agentlib/hooks.py)、[`agentlib/agent_hooks.py`](../../agentlib/agent_hooks.py)），kernel 有 [`tools/aos/kernel/hooks.py`](../../../tools/aos/kernel/hooks.py)。

## 提供一個點＝在那個時機起一次 `aos-hook fire`

掛 hook 的人寫一份被勾清單（`{hook 名: 格 或 null}`，跟 agent 的 `hookeds.json` 同一種格）；想讓人知道你會發哪些點、handler 收到什麼，另寫一份宣告 `hooks.json`（硬性只要每個點的 `input`，見知識庫 `aos/cli/hook_points`），程式不讀它。

```json
{"description": "What is hooked on before_save.",
 "a_deny": {"event": "before_save", "handler": "a_deny", "timeout_ms": 5000},
 "b_rename": {"event": "before_save", "handler": "b_rename"}}
```

```sh
out=$(printf '{"file": "%s"}' "$f" | aos-hook fire --list "$HERE/hookeds.json" --stack "$STATE" before_save)
# 自己讀結果：誰退 10 就當攔下，退 0 的 stdout 拿來改（照名字順序；每個 handler 拿同一份事件）
if printf '%s' "$out" | jq -e '.hooks | any(.code == 10)' >/dev/null; then
  echo "save skipped by a hook" >&2; exit 0
fi
f=$(printf '%s' "$out" | jq -r --arg f "$f" '[.hooks[] | select(.code == 0) | .stdout | fromjson? | .file] | last // $f')
```

實跑（兩個 hook：`a_deny` 是 python，檔名 secret 開頭就印一句、退 10；`b_rename` 是 sh，回 `{"file": "<原名>.bak"}`；`c_fail` 是 sh，退 3）：

```
$ echo '{"file": "notes.txt"}' | aos-hook fire --list hookeds.json --stack state before_save; echo "exit $?"
{"event": "before_save", "hooks": [{"hook": "a_deny", "code": 0, "stdout": "", "error": null}, {"hook": "b_rename", "code": 0, "stdout": "{\"file\": \"notes.txt.bak\"}\n", "error": null}]}
exit 0
$ echo '{"file": "secret.txt"}' | aos-hook fire --list hookeds.json --stack state before_save; echo "exit $?"
{"event": "before_save", "hooks": [{"hook": "a_deny", "code": 10, "stdout": "secret files are not saved\n", "error": null}, {"hook": "b_rename", "code": 0, "stdout": "{\"file\": \"secret.txt.bak\"}\n", "error": null}]}
exit 0
$ echo '{"file": "secret.txt"}' | aos-hook fire -q --stop-on-nonzero --list hookeds.json --stack state before_save; echo "exit $?"
exit 10
$ echo '{"file": "notes.txt"}' | aos-hook fire --stop-on-nonzero --list hookeds.json --list h2.json --stack state before_save; echo "exit $?"
{"event": "before_save", "hooks": [{"hook": "a_deny", "code": 0, "stdout": "", "error": null}, {"hook": "b_rename", "code": 0, "stdout": "{\"file\": \"notes.txt.bak\"}\n", "error": null}, {"hook": "c_fail", "code": 3, "stdout": "", "error": null}]}
aos-hook: error: HookFailed hook c_fail (event before_save) exited 3
exit 3
$ echo '{"file": "notes.txt"}' | aos-hook fire --list hookeds.json --stack state before_sav; echo "exit $?"
{"event": "before_sav", "hooks": []}
exit 0
```

C++ 不用 link 任何 hook 的東西，就是起一支程式；只看結束碼時加 `-q --stop-on-nonzero`：

```cpp
aos::loop::Run r = aos::loop::run_once(target({"aos-hook", "fire", "-q", "--stop-on-nonzero",
                                               "--list", cfg_path, "--stack", state, "before_job"}));
if (r.code == 10) { /* a hook said no: skip this job */ }
else if (r.code != 0) { /* a hook failed; aos-hook printed its error line */ }
```

## 規矩

- **旗標**（子指令前後都收）：清單從哪來二選一（一起給＝`ArgumentsBad`）——`--list FILE`（可重複；後面的同名蓋前面的、`null`＝關掉；**檔不在＝沒有 hook**）或 `--def DIR`（`DIR/interfaces.json` 最外層的 `hookeds`：檔名、指示詞或它們的陣列；每個相對檔名再疊上 stack 裡同名那份；不是資料夾＝`ArgumentsBad`，interfaces.json 壞＝`InterfaceBad`）。`--stack DIR`（handler 的工作夾放 `DIR/hookeds/<名>/`；沒給＝`$AOS_STACK`；都沒有＝`StackMissing`）。`--stop-on-nonzero`、`-q`／`--quiet`（stdout 不印）。
- **事件資料只有 stdin 的 JSON 物件**（空的、是終端＝`{}`；不是 JSON 物件＝`ArgumentsBad`）。每個 handler 收到同一份，加上 `event`、`hook`、`stack` 三鍵，存成 `STACK/hookeds/<名>/event.json` 從 stdin 給它；它自己的 `AOS_STACK` 是那個夾、自己一個行程群組；stderr 原樣透出。loop 的 handler 要的東西自己讀環境變數 `AOS_LOOP_*` 與 `<stack>/stage.txt`。
- **stdin 一定會被讀到底**（除非是終端）：從別的程式起 `aos-hook` 時，stdin 要嘛給 JSON、要嘛接 `/dev/null`；接著一條永遠不關的管子它會一直等。aos-daemon 底下的 aos-loop 本來就是 `/dev/null`。
- **怎麼跑**：照名字排序、一個跑完才起下一個；`timeout_ms`（預設 60000，0＝不限）到了整群 TERM、2 秒後 KILL。引擎只看格裡的 `event`、`handler`、`timeout_ms`，其餘鍵（agent 的 `condition`、on_clock 的鍵…）原樣留給發事件那一家，這裡不看。
- **stdout**：一行 JSON `{"event": EVENT, "hooks": [{"hook": 名, "code": 退出碼, "stdout": "…", "error": null}, …]}`；逾時或起不來的那個 `code` 是 `null`、`error` 是原因（stderr 另一行 warning）。沒人掛＝`"hooks": []`。
- **結束碼**：0＝跑完了（不管 handler 退什麼；沒人掛也是 0）。`--stop-on-nonzero`＝第一個退非 0 的就停、用它的碼退出：10 不印錯誤行（N-43 的「不」）；其他碼印 `aos-hook: error: HookFailed hook NAME (event EVENT) exited N`；逾時／起不來＝退 1、`HookFailed`。1＝錯，stderr 一行 `aos-hook: error: CODE reason`、stdout 不印：`ArgumentsBad`、`HooksBad`、`InterfaceBad`、`StackMissing`、`HookFailed`，以及 `FlagUnknown`、`CommandUnknown`。
- **範本與編譯出的 loop.json**：`on_start`／`on_stop` 一律接 `aos-hook fire -q --stop-on-nonzero --def $AOS_CD after_start|after_stop`；`on_before_run`／`on_after_run` 只在編譯時有 hook 掛那兩點才寫進去，手寫範本預設不接。handler 的退出碼因此原樣給 aos-loop：`before_run` 退 10＝跳過這圈；其他非 0（四個點都一樣，`after_run` 退 10 也算）＝loop 收工。
- 誰都能發事件、替別人的 stack 跑 hook：不擋（[設計 05「邊緣」](../../../../thinking/2026-11/20/aos-hook-plan-1120/05-發事件指令.md#邊緣)）；handler 裡再叫 `aos-hook fire` 是連鎖觸發，不檢測。

## 成本

每發一次＝起一支 Python（沒人掛約 36 毫秒；數字在[施工紀錄](../../../../thinking/2026-11/20/aos-hook-k4-1120.md#耗時)）；有 handler 時再加 handler 自己的。Python 寫的提供者直接 import 引擎（`aos.hook_run`），沒有這筆。

## 測試

`py/tests/apps/hook/`（跑裝好的 `bin/aos-hook`，handler 是真的 sh 與 python3、經 aos-exec；沒有 daemon）。引擎與清單：`py/tests/test_hook_run.py`；agent 一家：`py/tests/test_agent_hooks.py`。
