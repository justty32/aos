# 庚第三刀施工紀錄（線 geng3-1119）：agent.py 多了 HOOKS、FILES、不宣告 FSM 的 eca 模式；reviewer 寫成一支 agent.py 跟手寫的等價；沒動 agent_def、知識庫、現有範本

← [11-19](README.md)｜設計稿：[aos-compile-庚](aos-compile-庚/README.md)（範圍照 [08](aos-compile-庚/08-範圍切法.md) 第三刀，裁定 [10](aos-compile-庚/10-使用者裁定.md)）｜上一刀：[第一刀](aos-compile-庚-第一刀.md)

## 先講結論

- **做了 08 第三刀那三樣**：`HOOKS`（一張表，或 `ag.stock_hooks()`＝範本那組，或兩者疊起來）、`FILES`（原樣吐）、不宣告 `FSM` 的模式（先抄 eca-claude／eca-pi，`agent.py` 只填內容檔）。**驗收照 08**：reviewer 寫成一支 `agent.py`，生出來的 9 份 json 跟手寫的逐份等價（只差各份的 `description` 句子），範本沒換。
- **第三刀不靠第二刀**（08：「第二刀與第三刀互不相依」），第二刀一個字都沒做。
- **調子照「C 與 .o」**：沒有記帳、指紋、`--force`／`--status`；重生照舊直接蓋。
- **測試**：`test_agent_spec.py` 14 支 → 24 支，全過；相關的既有測試也全綠（下面有表）。假腦實跑：帶範本那組 hook 的 agent 掛上去、問一句有回、`after_start` 的 hook 真的跑了、關乾淨。
- **沒動**：`agent_def`、`def_edit.py`、`defs`、`aos-agent`、知識庫、四個現有範本、`agent-python` 骨架的生成檔（骨架只改了英文 README）。
- **repo 的 `bin/`、`lib/` 還沒換**：只在 `git archive` 抄出的乾淨複本裝過、測過。要生效，得由頂層在 `~/repo/aos/proto8` 跑 `install.py`。
- **要你拍板的兩題**在最後一節；都不擋現在這份能用。

## 加了什麼、改了什麼

| 檔 | 內容 |
|---|---|
| `py/aos/agent_spec_parts.py`（新） | 從 `agent_spec.py` 拆出來的零件：各份檔怎麼從宣告算出來、怎麼先驗（tools、llm、interfaces、hooks、FILES）；不宣告 FSM 時讀現有的 `interfaces.json`。第一刀紀錄說過「第三刀加 HOOKS、FILES 時再看要不要拆」，加完會到 500 行，所以拆了。 |
| `py/aos/agent_spec.py` | 加 `ag.stock_hooks(範本="agent-fsm")`。`defs` 與 `main` 多三個選填參數：`hooks=`、`files=`；`defs` 另加 `folder=`。`fsm` 改成可以不給。多一個錯誤代號 `DefBad`，是夾本身的問題（不是宣告寫錯）。391 行 → 368 行。 |
| `py/tests/test_agent_spec.py` | 加 10 支、擴 1 支（見下面「測試」）。 |
| `templates/agent-python/README.md` | 英文：`HOOKS`、`FILES` 的寫法，新加一節「Without FSM」，檔案表多兩列。 |
| `templates/README.md`、`py/README.md` | 原本 agent-python／agent_spec 那一段，各補一句第三刀加了什麼。 |

## 三樣東西怎麼用

### HOOKS

```python
HOOKS = [ag.stock_hooks(), {"timer": None,                       # 範本那組，拿掉 timer
                            "mine": {"event": "before_tool", "condition": "shell",
                                     "handler": ag.home("/lib/tools/agent/hook_noop")}}]
ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM, hooks=HOOKS)
```

- **寫法有四種**：
  - 一張表 `{名字: 格}`，格的寫法跟 `hooks.json` 一樣，原樣吐。
  - `ag.stock_hooks()`：範本那組。
  - 上面兩種排成串列：後面的同名蓋前面，值寫 `None`＝拿掉。
  - `ag.by_hand("hooks.json")`。
- **宣告了 HOOKS 會多出三樣東西**，全部照 agent-fsm 範本那份：
  - `hooks.json`；
  - `interfaces.json` 多一個 `"hooks"` 鍵，位置照 agent-fsm；
  - `loop.json` 多 `on_start`／`on_stop`。測試守著「去掉 description 之後跟 agent-fsm 的 `loop.json` 一字不差」。
- **沒宣告 HOOKS**：三樣都不出，跟第一刀一樣。所以骨架那幾份生成檔沒變，「骨架跟 `agent.py` 一字不差」那支測試照樣綠。
- **每一格都先驗**：直接叫 `aos/agentlib/hooks.py` 的 `validate_entry` 和 `hook_run.validate_name`，不另抄一份規矩。寫錯一樣是一行 `SpecBad`，例如：`HOOKS hook h: event must be one of before_queue, ...`。
- **`ag.stock_hooks()` 是「抄」，不是「借」**：
  - 為什麼不能借：`interfaces.json` 的 `hooks` 只收定義夾裡面的相對檔名（`declared_files.py`），沒辦法像 `stock_fsm()` 那樣直接指到範本那份。
  - 所以重生的時候，從 `$AOS_HOME/templates/<範本>/hooks.json` 讀出那張表，抄進這個夾。範本改了，下次重生就會跟著變。
  - 沒設 `AOS_HOME`、或範本沒有 `hooks.json`：報 `SpecBad`，並列出有 hook 的範本有哪幾個。
  - 生出來的 `hooks.json` 只帶一句短的 description，外加一句「Taken from templates/agent-fsm/hooks.json」。範本裡那段解釋每個 hook 的長說明沒抄過來。

### FILES

`FILES = {"ladder.json": {...}, "notes.txt": "..."}`：dict 或 list 寫成 JSON，字串照字面寫。

- 檔名只能是夾裡的一個檔：不能有 `/`，不能用 `.` 開頭。
- 有幾種檔不能寫：骨架、宣告用的檔、跑起來才寫的檔、`_metainfo.json`、`README.md`、`agent.py`、`by_hand` 指的檔；不宣告 FSM 時，`interfaces.json` 宣告的檔也不能寫。寫了報 `SpecBad`，叫人改用對應的宣告。
- 拿掉某一項之後，舊檔留在原地，照設計稿 [07](aos-compile-庚/07-邊緣狀況.md) 第五條。

### 不宣告 FSM（eca）

```python
ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM, hooks=HOOKS)      # 沒有 FSM
```

- **先決條件**：夾裡已經有骨架。用 `agent_def new` 抄 eca-claude／eca-pi，或 `cp -r`。
- **重生寫什麼**：只寫 `SYSTEM`、`TOOLS`、`LLM`、`HOOKS` 這幾份內容檔，外加 `FILES`、`_metainfo.json` 自己的鍵；`README.md` 照舊，不在才寫。
- **檔名從哪來**：照夾裡現有的 `interfaces.json` 找。`LLM` 也照它的 `llm_keys` 驗；eca 只收 `model`，寫 `temperature` 會報 `SpecBad`。
- **骨架不碰**：`interfaces.json`、`loop.json`、`_entry`、`cli.json`、`screen/` 一個 byte 都不動。`INTERFACES` 在這個模式不能用，報 `SpecBad`。
- **夾不對時**：夾裡沒有 `interfaces.json`，或它沒宣告你要寫的那份（例如宣告了 `HOOKS`，它卻沒有 `hooks`），報一行 `DefBad`，一份都不寫。`by_hand` 的檔名跟 `interfaces.json` 寫的不一樣，報 `SpecBad`。
- `--defs` 也會讀那個夾（`agent.py` 所在的夾），因為檔名要從它的 `interfaces.json` 來。

## 自己定的細節（設計稿沒寫到的）

1. **錯誤分兩種代號**：
   - `SpecBad`：宣告寫錯，訊息照舊以「fix the declaration in agent.py」結尾。
   - `DefBad`：夾本身不對，是第一刀「`_metainfo.json` 壞了」那個代號，這次多了 eca 模式的兩種情況。兩種都是一行、退 1、一份都不寫。
2. **`defs(..., folder=)` 只在不宣告 FSM 時用到**：宣告了 FSM，`defs` 照舊是純計算，不讀任何夾。在互動環境裡不給 `folder` 又不宣告 FSM，會報 `SpecBad`，叫人給夾。
3. **`ag.main` 的位置參數沒變**（`DESCRIPTION, SYSTEM, TOOLS, LLM, FSM`），只是 `FSM` 可以不給。新東西一律用關鍵字傳，之後的除錯開關也照這個加，見下面「接點」。
4. **`HOOKS` 的串列混了別的東西**（例如 `ag.pack`）、或某一項不是 dict：報 `SpecBad`，並說明 HOOKS 該怎麼寫。
5. **eca 的 `llm.json` 也帶 `description`**，照第一刀的做法。`cli_cfg.read_llm` 只看 `model`；`agent_def check` 對兩個 eca 夾都回 `{"problems": []}`，實測過。

## 驗收（乾淨複本 `~/.aos/scratch/geng3-1119/copy`，經 `run.sh`：先清掉全部 `AOS_*`，只設 `AOS_HOME`＝複本的 proto8，再 `source env.sh`）

### 1. reviewer 寫成一支 agent.py，跟手寫的等價（08 第三刀的驗收）

`agent.py` 就是設計稿 [04](aos-compile-庚/04-agent-py-兩個例子.md) 的完整例子，只多了一處：ladder 的 `description` 放進 `FILES`。全文在測試檔的 `REVIEWER` 常數裡。

```
$ python3 reviewer/agent.py --write-defs
10                       (wrote lines: 9 json + README seed)
exit=0
_entry same
body.json same
loop.json same
fsm.json same
interfaces.json same
tools.json same
llm.json same
ladder.json same         (including its description)
_metainfo.json same
$ agent_def check reviewer
{"problems": []}
```

「same」的意思：兩邊都拿掉頂層的 `description` 之後，JSON 相等。`system.txt` 是 `ag.by_hand`，原檔抄過去。測試 `Reviewer.test_same_as_the_template` 守著這一條，之後有人改了 reviewer 範本或 lib，對不上就會紅。

### 2. eca-claude、eca-pi：agent_def new 抄出來，放一支沒有 FSM 的 agent.py

```
$ agent_def new template eca-claude path eca-claude-docs
$ python3 eca-claude-docs/agent.py --write-defs     (HOOKS = [ag.stock_hooks("eca-claude"), {"timer": None}])
wrote eca-claude-docs/tools.json
wrote eca-claude-docs/llm.json
wrote eca-claude-docs/system.txt
wrote eca-claude-docs/hooks.json
wrote eca-claude-docs/_metainfo.json
kept eca-claude-docs/README.md (it is already there)
interfaces.json loop.json _entry cli.json unchanged
hooks: ['brain_notify', 'context_wrap', 'mail_notify', 'screen_linger_start', 'screen_linger_stop']
_metainfo.json: summary / cost / resource set, lineage {"template": "eca-claude"} kept
$ agent_def check eca-claude-docs
{"problems": []}
```

eca-pi 同樣的步驟，結果一樣：hooks 是 `mail_notify`、`screen_linger_start`、`screen_linger_stop`，check 過。eca 要叫真的 Claude Code／pi 才跑得起來，所以這兩隻沒掛上去跑，只做到 check。

### 3. 暫存樹、假腦：agent-python＋範本那組 hook＋一個 after_start hook＋FILES

```
$ python3 agents/helper/agent.py --write-defs
11 (wrote lines)
$ aos-agent -d .stack ctl add -w . agents/helper
exit=0
$ aos-agent -d .stack hook --target helper ls
brain_notify   brain_failed  {"$env":"AOS_HOME","$path":"/lib/tools/agent/brain_notify"}
context_wrap   on_clock      {"$env":"AOS_HOME","$path":"/lib/tools/agent/context_wrap"}
mail_notify    on_clock      {"$env":"AOS_HOME","$path":"/lib/tools/agent/mail_notify"}
started        after_start   {"$env":"AOS_HOME","$path":"/lib/tools/agent/hook_noop"}
timer          on_clock      {"$env":"AOS_HOME","$path":"/lib/tools/agent/hook_noop"}
$ aos-agent -d .stack --target helper say hello ; ... listen --timeout-s 30
FAKE ANSWER to: hello (tool said: glob: error: ArgumentsBad missing pattern (required) ...
after_start hook ran: tree/.stack/procs/helper/hooks/started/event.json
$ aos-daemon-ctl -d .stack shutdown ; aos-daemon-ctl -d llms/stacks/llm shutdown
root exited
llm kernel exited
$ pgrep -af aos-
(none)
```

`glob` 那段錯，跟第一刀一樣：假腦每次都叫第一個工具、又不帶參數。不是這次改出來的。

### 測試（乾淨複本）

| 測試 | 結果 |
|---|---|
| `py/tests/test_agent_spec.py`、`test_tool_spec.py`、`test_install.py`、`test_hook_run.py`、`test_hooks_engine.py` | Ran 66, OK（其中 agent_spec 24 支） |
| `py/tools/agent/agent_def/tests` | Ran 29, OK |
| `py/tools/aos/defs/tests` | Ran 19, OK |
| `py/tools/agent/tools_def/tests` | Ran 12, OK |
| `templates/tests/tool-python` | Ran 4, OK |
| `templates/tests/reviewer` | Ran 1, OK |
| `templates/tests/kits` | Ran 8, OK |

`test_agent_spec.py` 新加的：
- `test_spec_bad` 多 21 種寫錯：hook 的事件、名字、handler、on_clock 專用鍵；HOOKS 形狀；`stock_hooks` 名字；`INTERFACES` 改 hooks；FILES 搶檔、子夾、隱藏檔、內容型別；沒 FSM 又給 INTERFACES 或不給夾。
- 新的幾支：`test_hooks_and_files`、`test_hooks_loop_matches_agent_fsm_template`、`test_no_hooks_no_hooks_key`、`test_by_hand_hooks`、`test_stock_hooks_needs_a_home_with_the_template`。
- `NoFsm` 四支：兩個 eca 範本抄出來填、沒骨架報 `DefBad`、沒宣告 hooks 檔報 `DefBad`、檔名與 `llm_keys` 照 `interfaces.json`。
- `Reviewer` 一支。

## 跟除錯那條線（aos-gdb-1119）的接點

只記、不做。依據是 [11](aos-compile-庚/11-跟除錯那條線的接點.md) 與 gdb 線的 [06-使用者回應](aos-gdb-1119/06-使用者回應.md)。

- **「編譯時加個選項，選了就添加一些除錯用的觸發器」**（使用者 11-19，gdb 06 第 6 條）：HOOKS 本來就是「一層一層疊上去」的串列，除錯開關只要在最上面多疊一層除錯用的 hook 就好，不必改現在的寫法。`loop.json` 的 `on_start`／`on_stop` 和 `interfaces.json` 的 `hooks` 鍵，也已經跟著 HOOKS 一起出。開關本身照設計稿留給第四刀：加成 `defs`／`main` 的一個關鍵字參數，現有參數的意思不動（`agent_spec.py` 檔頭寫了這句）。
- **在互動環境裡用**：`ag.defs(...)`、`ag.write_defs(...)` 照舊可以單獨叫。eca 模式的 `defs` 要給 `folder=`。
- **重生蓋不到 stack 那份**：重生只蓋定義夾的 `hooks.json`。用 `aos-agent hook add`／`self_hook` 加在 stack 那份的不受影響，跟 gdb 06 那張「加法寫在哪」的表一致。執行時才裝的斷點 hook，跟庚不會打架。
- **格這一層沒有 hook 掛點**（gdb 05-續問號 a）：庚不管。`FSM` 照舊整份蓋。

## 沒做、留給之後的

- 第二刀（`agent_def check` 順手重生）：照 08 先不排。（使用者 11-19 後來裁定劃掉，見 [10](aos-compile-庚/10-使用者裁定.md) 末節）
- 第四刀（行號對照、除錯開關）、第五刀（知識庫、己）。
- eca 版的骨架（`_entry`、`loop.json`、`cli.json`、`screen/`）不歸 `agent.py` 生，照設計稿「骨架照舊抄」，所以 eca 版還是要先 `agent_def new` 一次。
- eca 版沒用真的 Claude Code／pi 跑過（不叫真模型），只做到 `agent_def check`。

## 順手看到的（不是這一刀的事，沒動）

- `agent_def check` 對一個只有 `agent.py` 和 `system.txt`、還沒生成的夾，也回 `{"problems": []}`。驗收 1 第一次跑時，生成那步因為腳本自己的錯沒成功，check 照樣回了這句。看起來是沒有 `interfaces.json` 的夾不被當成 agent 檢查。照設計稿 02「check 只查五樣」，這不是新發現，只是提醒：**「check 過」不代表重生成功了**，要看 `--write-defs` 自己的結束碼。

## 要你拍板的題（不擋現在能用）

**一、`agent-python` 骨架要不要預設帶範本那組 hook？**（**已裁：a，不帶**，使用者 11-19「其他兩題維持現狀」，見 [10](aos-compile-庚/10-使用者裁定.md) 末節）

骨架現在沒有 hook，所以沒有 `mail_notify`（新信進來時提醒腦）、`brain_notify`（腦失敗時寄 BLOCKED 信）、`context_wrap`（脈絡快滿時提醒）。agent-fsm 範本三個都有。

| 選項 | 後果 |
|---|---|
| a. 不帶（現在這樣） | 骨架最小，跟第一刀一樣；要的人自己加一行 `HOOKS = ag.stock_hooks()` |
| b. 帶 | 抄骨架就有 agent-fsm 那四個 hook。骨架進 git 的生成檔會多一份 `hooks.json`，`loop.json`、`interfaces.json` 也會跟著變 |

**二、`ag.stock_hooks()` 現在是「重生時抄進來」，要不要改成「借」？**（**已裁：a，抄**，同上）

| 選項 | 後果 |
|---|---|
| a. 抄（現在這樣） | 不改任何現有程式。範本的 hook 改了，要重生才跟上；夾裡看得到完整的那張表 |
| b. 借 | 要讓 `interfaces.json` 的 `hooks` 能指到夾外（改 `declared_files.py` 與它的使用者），範圍超出庚。好處是範本一改，所有借的人當場跟上 |

## 使用者怎麼親手試（頂層在 repo 跑過 `install.py` 之後）

```sh
source $AOS_HOME/env.sh && cd <你的樹>
# 有狀態機＋範本那組 hook：
echo '{"op":"new","template":"agent-python","path":"agents/helper"}' | AOS_WS=$PWD aos-exec $AOS_HOME/lib/tools/agent/agent_def
#   在 agents/helper/agent.py 最後一行前加：HOOKS = ag.stock_hooks()，最後一行改成 ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM, hooks=HOOKS)
python3 agents/helper/agent.py --write-defs && aos-agent -d .stack ctl add -w . agents/helper && aos-agent -d .stack hook --target helper ls
# eca 版（沒有 FSM）：
echo '{"op":"new","template":"eca-claude","path":"agents/docs"}' | AOS_WS=$PWD aos-exec $AOS_HOME/lib/tools/agent/agent_def
#   在 agents/docs/ 放一支 agent.py（開頭照 templates/agent-python/agent.py 那段），最後一行 ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM, hooks=ag.stock_hooks("eca-claude"))
python3 agents/docs/agent.py --defs        # 先看會寫哪幾份（只有內容檔）
python3 agents/docs/agent.py --write-defs
```

## 行程與環境

- 開工前 `pgrep -af aos-`：只有 pgrep 自己。收尾：`(none)`。
- 暫存樹的兩台 daemon（root、llm kernel）都用 `aos-daemon-ctl -d <絕對路徑> shutdown` 關掉，也確認它們退出了。
- `~/aos-home` 不存在，沒建；shell 的設定檔沒動。
- 暫存都在 `~/.aos/scratch/geng3-1119/`（`copy/` 乾淨複本、`t1/`、`tree/`、`acc1.sh`、`acc2.sh`、輸出檔），留著沒刪。

## 事後補六個小洞（線 geng-patch-1119）

照 [12 Argon 審](aos-compile-庚/12-Argon審與採納.md)第 1 類，六個先各自在乾淨複本重現到了，再各補一行到幾行；不重構、不加功能，「C 與 .o」不變（重生直接蓋、不記帳、沒有 `--force`／`--status`）。

| # | 洞 | 怎麼補 |
|---|---|---|
| ① | `META = {1: "a"}` 冒 `TypeError` | 驗 `META` 時一起查鍵都是字串，不是報一行 `SpecBad META keys must be strings` |
| ② | `ag.by_hand("agent.py")` 沒擋 | `_names` 的 `made` 加 `"agent.py"`：`SYSTEM`／`TOOLS`／`LLM`／`FSM`／`HOOKS` 用它都報 `SpecBad` |
| ③ | 改名先換索引檔 | `write_defs` 改名照 `RENAME_LAST` 排：內容檔（含 `fsm.json`、`FILES`、`README.md`）先，再 `loop.json`、`body.json`、`interfaces.json`、`_entry`，`_metainfo.json` 最後 |
| ④ | 清暫存檔刪一份失敗就停 | 每份各自 `try: os.unlink … except OSError: pass`（原本那個錯照丟） |
| ⑤ | 讀 `_metainfo.json` 的 `OSError` 報成 `DefBad` | 照 12 建議的第一條改程式、不改註解：只有讀不懂（`ValueError`，含不是 utf-8）報 `DefBad`；讀不到照丟，`main` 報 `WriteFailed`，一樣什麼都沒寫 |
| ⑥ | `INTERFACES` 改 `entry` 時叫人用 `by_hand` | `entry` 另一句：`entry is body.json, the skeleton agent.py writes; it cannot be changed`；`tools`／`llm`／`system`／`hooks` 照舊 |

測試：`test_agent_spec.py` 24 支 → 27 支（`test_holes_from_argon_review` 管 ①②⑥、`test_rename_order_and_cleanup` 管 ③④、`test_unreadable_metainfo_is_write_failed_and_writes_nothing` 管 ⑤），在 `git archive` 乾淨複本疊上改動、清掉 `AOS_*` 跑，全過（`templates/agent-python` 生成檔與 `agent.py` 對得上那支也綠）。repo 的 `bin/`、`lib/` 沒換，要生效得由頂層跑 `install.py`。暫存在 `~/.aos/scratch/geng-patch-1119/`。
