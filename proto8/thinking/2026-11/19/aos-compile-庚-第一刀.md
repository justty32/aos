# 庚第一刀施工紀錄（線 compile-geng-s1-1119）：加了 agent_spec、agent-python 骨架與測試，七條驗收都過，沒動現有程式

← [11-19](README.md)｜設計稿：[aos-compile-庚](aos-compile-庚/README.md)（範圍照 [08](aos-compile-庚/08-範圍切法.md) 第一刀，行為照 03～06，裁定在 [10](aos-compile-庚/10-使用者裁定.md)）

## 先講結論

- **做了**：一支 lib `proto8/py/aos/agent_spec.py`、一個骨架 `proto8/templates/agent-python/`（`agent.py`＋它生出來的 9 份檔＋英文 README）、一支測試 `proto8/py/tests/test_agent_spec.py`（14 支），`templates/README.md` 與 `py/README.md` 各加一段。
- **沒動**：`agent_def`、`def_edit.py`、`defs`、`aos-agent ctl`、知識庫、現有範本。
- **七條驗收全過**（輸出原文在下面）；跟 tool_spec、agent_def、defs、tools_def、範本相關的既有測試也全綠。
- **調子照使用者的「好比C語言和.o之間的關係」**：重生就是直接蓋，不記指紋、不寫記號、沒有 `--force`／`--status`。
- **跟設計稿對不上的有四處**，都照最小改動處理、寫在下面，沒有一處要使用者先拍板才能用。
- **repo 的 `bin/`、`lib/` 還沒換**：建置與驗收都在 `git archive` 抄出的乾淨複本上做，沒在 `~/repo/aos` 跑 `install.py`。

## 做了什麼

| 檔 | 內容 |
|---|---|
| `py/aos/agent_spec.py` | 宣告用的小函式：`pack`、`tool`、`no`、`home`、`env`、`state`、`fsm`、`stock_fsm`、`by_hand`。寫錯不在當下丟例外，先記成 bad；`defs()` 一次算出全部內容（`{檔名: 內容}`），驗完才回；`write_defs(folder, files)` 負責寫進夾；`main` 只是一層旗標。 |
| `templates/agent-python/agent.py` | 設計稿 [04](aos-compile-庚/04-agent-py-兩個例子.md) 的最小例子。開頭那段照 `tool-python/tool.py` 抄，`import` 換成 `agent_spec as ag`。 |
| `templates/agent-python/` 其餘 9 份 | 上面那支 `agent.py --write-defs` 生出來的（`_entry`、`body.json`、`loop.json`、`fsm.json`、`interfaces.json`、`tools.json`、`llm.json`、`system.txt`、`_metainfo.json`），一起進 git。 |
| `templates/agent-python/README.md` | 英文。寫怎麼抄、怎麼重生、怎麼掛，還有每個宣告怎麼寫。三句警語：整份蓋掉、直接改 json 的下次就沒了、改格名會讓停在舊格的 agent 停下。另外寫了「在手寫夾第一次重生會蓋掉手寫的，先 `--defs` 或先 commit」。 |
| `py/tests/test_agent_spec.py` | 測宣告的形狀、32 種寫錯各丟 `SpecBad`。用子行程測：連跑兩次一字不差、沒有機器上的事、三種寫錯各一行且夾不變、蓋與不蓋的規則、`by_hand`、`_metainfo.json` 壞掉、用法。還測骨架：檔案清單，以及進 git 的生成檔跟 `agent.py` 當場重生一字不差。 |

## 自己定的實作細節

1. **錯誤行走 `aos.flags`、只印 stderr**。`agent.py` 是人在終端打的指令，不是工具，所以不像 `tool.py` 兩邊都印。
   - 程式名照 tool_spec 的取法：腳本叫 `agent.py` 就用資料夾名，否則用檔名去掉 `.py`。
   - 不給旗標時報 `ArgumentsBad`，原因後面帶 `(usage: …)`；不認得的旗標報 `FlagUnknown`；`--help` 印說明、退 0。理由見下面「對不上的地方」第 1 條。
2. **每份 json 的 `description` 怎麼寫**：
   - `interfaces.json` 的 `description` 就是 `DESCRIPTION`，因為它是整隻 agent 的宣告檔，跟 reviewer 的寫法一樣。
   - 其他幾份寫一句固定的英文，說這份檔做什麼。
   - `llm.json` 也帶 `description`。reviewer 本來就這樣寫，而 `llm_settings.py` 不看別的鍵。所以 `LLM` 裡准用 `description` 這個鍵，其餘的鍵要在 `llm_keys` 裡。
3. **輸出格式**：json 一律 `indent=2`，結尾換一行；`ensure_ascii=False`；鍵照宣告的順序；`system.txt` 照字面寫，不補換行。
4. **預設的 `interfaces.json`**：`aos-agent` 下有 `entry`、`tools`、`llm`、`llm_keys`、`history`、`system` 六鍵，`llm_keys` 那張照 `llm_settings.KEYS` 抄。照 04 的清單，**沒有** `hooks`（第三刀才做）也**沒有** `aos-observed`，要的話用 `INTERFACES` 加。
   - `INTERFACES` 的合併方式：頂層的鍵整個換掉；`aos-agent` 裡的鍵一個一個疊上去；值寫 `None` 就是把預設的那個鍵拿掉。
   - `aos-agent` 下的 `entry`、`tools`、`llm`、`system` 不准改，改了報 `SpecBad`，訊息叫人用 `ag.by_hand`，免得檔名跟生出來的檔對不上。
   - 整個 `aos-agent` 拿掉也報 `SpecBad`。
5. **`ag.by_hand` 四個宣告都能用**（SYSTEM／TOOLS／LLM／FSM）：`interfaces.json`（或 `loop.json` 的 `exec`）指到那個檔名，那份檔不生。
   - 檔名先正規化，`./tools.json` 會算成 `tools.json`。
   - 不准跟生成的檔撞名，也不准用跑起來才寫的檔名（`ctl.json`、`state.json`、`state_flux.json`、`history.jsonl`）。
   - 不查那份手寫檔在不在。它不是 lib 生的，不在的話由 `defs check` 報。
6. **`ag.pack` 查包在不在**：設了 `AOS_HOME` 就查 `$AOS_HOME/lib/packs/<名>.json`，不在就報 `SpecBad` 並列出有哪些包；沒設就只查名字的寫法。理由是 `defs check` 遇到不存在的包會報合併失敗，照「lib 先查的 ⊇ check 查的」要先擋。這只影響報不報錯，不影響生出來的內容。
7. **`ag.tool` 照 aos-tools 的 `registry.finish` 先驗**：工具名照 `NAME_RE`，`env` 是「NAME → 字串」，`env_file` 是路徑，`cache` 只能是 `False`；指示詞的 `$path` 要是字串。`ag.no` 沒搭任何 `ag.pack` 時報 `SpecBad`，因為生出 `null` 那格會被 `defs check` 擋。這兩條是獨立審查抓到後補的。
8. **`_metainfo.json` 壞掉（讀不了、不是 JSON 物件）時報 `DefBad`、一份都不寫**：代號跟 `agent_def new` 遇到同一件事時一樣。META 不准設 `summary`（那個由 `DESCRIPTION` 給）和 `lineage`（那個由 `agent_def new` 寫）。
9. **寫檔**：
   - 先讀好 `_metainfo.json`，把每份檔都寫成同夾的隱藏暫存檔（`.名.tmp-pid`），最後連著改名。改名前任何一份失敗，就把暫存檔清掉、夾裡不變。
   - 已經有的檔沿用原本的權限。
   - 資料夾不在報 `WriteFailed`，不替人建。
   - 寫完印 `wrote <路徑>`、`kept …README.md (it is already there)`，再加一句「用這份定義的 agent 什麼時候看到」（照 [07](aos-compile-庚/07-邊緣狀況.md) 二）。這幾行是畫面輸出，會帶絕對路徑；檔案內容裡沒有。
10. **骨架的 `LLM = {}`**（04 寫的是 `{"model": "luna"}`）：`luna` 是某台 kernel 的腦包名，寫死在範本裡等於綁一台機器。`agent-fsm` 範本也是 `{}`。註解寫了「`{"model": "luna"}` picks one of its brain packs」。
11. **不宣告的檔不碰，也不刪**。`HOOKS`、`FILES`、不宣告 `FSM` 的模式都沒做，第一刀 `FSM` 一定要宣告，不宣告報 `SpecBad`。`ag.main` 只收 `meta=`、`interfaces=` 兩個選填。
12. **測試放在 `py/tests/`**，照任務書與 08。另一個做法是照「範本不帶測試」放進 `templates/tests/agent-python/`；骨架夾裡沒有測試，所以兩邊都守得住，這裡照 08 寫的放。

## 跟設計稿對不上的地方（以程式／規矩為準，最小改動）

1. **「都沒有旗標＝印用法」**（[03](aos-compile-庚/03-agent-py-長相.md) 命令列表）跟 P-44「不給參數＝ArgumentsBad、`(usage: …)` 放最後」（使用者 11-05 定的三扇門）打架。做法是報 `ArgumentsBad`，用法放在同一行，退 1：用法照樣印出來，也守住 P-44。
2. **`body.json` 的形狀**：04 寫 `{"argv": [...]}`，`agent-fsm` 範本實際是陣列 `["aos-loop", "loop.json"]`，reviewer 是帶 `description` 的物件。照 04 與 reviewer 用物件，兩種寫法程式都認，ctl add 實跑也過了。
3. **03 說 `DESCRIPTION` 生出「各份 json 的 `description`」**，04 卻說 description 是「說這份檔是做什麼的」。照 04 的說法，只有 `interfaces.json` 用 `DESCRIPTION`（見上面第 2 條）。
4. **`agent_def check` 實際查的**跟 [02](aos-compile-庚/02-現況-定義夾與agent_def.md) 寫的一致。另外查到 aos-tools 合併時還會擋工具格的 `env`、`env_file`、`cache`，02 沒寫到，lib 也照著先擋了（上面第 7 條）。

另外 `agent_spec.py` 有 391 行，超過「300 行就該考慮拆」的門檻。它是一份自成一體的 lib，第一刀先不拆；第三刀加 HOOKS、FILES 時再看要不要拆出驗證那段。

## 七條驗收（全在乾淨複本 `~/.aos/scratch/compile-geng-s1-1119/copy`，經 `run.sh`：先清掉全部 `AOS_*`，只設 `AOS_HOME`＝複本的 proto8，再 `source env.sh`）

### 1. 空夾＋骨架 `agent.py`，`--write-defs` 後 `agent_def check` 回 `{"problems": []}`

```
$ ls -A
agent.py
$ python3 agent.py --write-defs
exit=0
$ ls -A
README.md _entry _metainfo.json agent.py body.json fsm.json interfaces.json llm.json loop.json system.txt tools.json
$ agent_def {"op":"check","path":"helper"}
{"problems": []}
exit=0
```

### 2. `agent_def new` 用 `"template": "agent-python"` 抄、check 過、`lineage` 有寫

```
$ agent_def new template agent-python path mine
wrote definition /home/guanyu/.aos/scratch/compile-geng-s1-1119/t2/mine (copied from /home/guanyu/.aos/scratch/compile-geng-s1-1119/copy/proto8/templates/agent-python)
exit=0
$ agent_def check mine
{"problems": []}
exit=0
$ cat mine/_metainfo.json
{
  "summary": "Look things up in the workspace and answer by mail.",
  "lineage": {
    "template": "agent-python"
  }
}
```

### 3. 暫存樹用假腦 `ctl add`、問一句、有回、關乾淨

樹是從 `templates/start-api` 抄到 `~/.aos/scratch/compile-geng-s1-1119/tree` 的，用 `agent_def new` 抄骨架，把 `agent.py` 的 `LLM` 改成 `{"model": "fake"}` 再重生。這正是使用者以後會走的那條路。

```
$ python3 agents/helper/agent.py --write-defs
$ cat agents/helper/llm.json
{
  "description": "Brain settings of this agent: model names a brain pack of the llm kernel (none = the kernel's default).",
  "model": "fake"
}
$ aos-agent -d .stack ctl add -w . agents/helper
exit=0
$ aos-daemon-ctl -d .stack ls
_clock	running	55418	-	-	-
_sweeper	running	55419	-	-	-
helper	running	55435	-	/home/guanyu/.aos/scratch/compile-geng-s1-1119/tree	-
$ aos-agent -d .stack --target helper say hello
exit=0
$ aos-agent -d .stack --target helper listen --timeout-s 30
FAKE ANSWER to: hello (tool said: glob: error: ArgumentsBad missing pattern (required)
...)
exit=0
$ aos-daemon-ctl -d .stack shutdown
daemon at .../tree/.stack stopped (ctl seq 1); 3 procs asleep, they wake when it starts again
$ aos-daemon-ctl -d llms/stacks/llm shutdown
daemon at .../tree/llms/stacks/llm stopped (ctl seq 1); 1 procs asleep, they wake when it starts again
root exited
llm kernel exited
$ pgrep -af aos-
(none)
```

回答裡那段 `glob` 的錯，是假腦每次都叫第一個工具、又不帶參數造成的，跟 `agent-fsm` 範本一樣，不是這次改出來的。

### 4. 骨架進 git 的 json 跟 `agent.py` 當場重生一字不差

由 `test_agent_spec.Skeleton.test_committed_files_match_agent_py` 守：把骨架的 `agent.py` 抄到暫存夾，`--write-defs` 之後逐份比 bytes。為了證明它真的會變紅，故意把複本的 `llm.json` 改成 `{}`：

```
AssertionError: b'{\n  "description": "Brain settings of thi[85 chars]n}\n' != b'{}\n' : run python3 agent.py --write-defs in templates/agent-python
FAILED (failures=1)
```

改回去之後 14 支全綠。

### 5. 連跑兩次一字不差、輸出沒有時間、機器名、絕對路徑

```
$ diff run1.sum run2.sum
identical (10 files)
$ grep -l for: <暫存夾>, /home/guanyu, <機器名>, 2026-11-19, <AOS_HOME>
(no file has any of them)
```

`sum` 是 10 份產出檔的 sha256，兩次之間隔了 1 秒。測試裡也有同一條：`test_write_twice_is_identical_and_has_no_machine_facts`。

### 6. 三種寫錯各一行 `SpecBad`、夾裡一字不變

```
$ python3 agent.py --write-defs   # next state not in the table
helper: error: SpecBad state idle: next state 'thnik' is not one of the states (idle) (fix the declaration in agent.py)
exit=1
folder unchanged
$ python3 agent.py --write-defs   # a tool without a path
helper: error: SpecBad tool peek must have a path: a string, or ag.home("/lib/tools/...") / ag.env(VAR, PATH) (fix the declaration in agent.py)
exit=1
folder unchanged
$ python3 agent.py --write-defs   # LLM model not a string
helper: error: SpecBad LLM model must be a non-empty string: the name of a brain pack of the llm kernel, like "luna" (fix the declaration in agent.py)
exit=1
folder unchanged
```

「folder unchanged」的意思是：除了 `agent.py` 以外，夾裡每份檔的 sha256 跟改壞之前比對過，完全一樣。測試 `test_spec_bad_is_one_line_and_writes_nothing` 對 `--write-defs` 與 `--defs` 各驗一次，另外驗 stdout 是空的、stderr 只有一行。

### 7. 手改被蓋回、`lineage` 還在、已有的 `README.md` 不動、`by_hand` 的檔不動

這裡的「手改」用 `agent_def tools add` 來做，也就是設計稿 06 第 6 條那種情況。

```
$ agent_def tools add peek (a hand change through agent_def)
added peek -> .../lib/tools/base/peek_now_time (.../t7/mine/tools.json: {"$env": "AOS_HOME", "$path": "/lib/tools/base/peek_now_time"})
exit=0
$ grep -c peek mine/tools.json
2
README.md before: ca957da99a51ee07f96232d88470cf89  -
$ python3 agent.py --write-defs
wrote .../t7/mine/_entry
... (九份 wrote)
kept .../t7/mine/README.md (it is already there)
exit=0
$ grep -c peek tools.json
0
tools.json is byte-for-byte the generated one again
$ cat _metainfo.json
{
  "summary": "Look things up in the workspace and answer by mail.",
  "lineage": {
    "template": "agent-python"
  }
}
README.md after:  ca957da99a51ee07f96232d88470cf89  -
$ grep -n "^SYSTEM" agent.py
30:SYSTEM = ag.by_hand("system.txt")
$ python3 agent.py --write-defs   (SYSTEM = ag.by_hand("system.txt"))
8
exit=0
$ cat system.txt
Hand written system text.
$ agent_def check mine
{"problems": []}
exit=0
```

重生時沒報錯，stderr 是空的（測試 `test_overwrite_rules` 也驗了這點）。

### 既有測試（乾淨複本，修完審查的必修後最後一次）

| 測試 | 結果 |
|---|---|
| `py/tests/test_agent_spec.py`、`test_tool_spec.py`、`test_install.py` | Ran 35, OK |
| `py/tools/agent/agent_def/tests` | Ran 29, OK |
| `py/tools/aos/defs/tests` | Ran 19, OK |
| `py/tools/agent/tools_def/tests` | Ran 12, OK |
| `templates/tests/tool-python` | Ran 4, OK |
| `templates/tests/reviewer` | Ran 1, OK |
| `templates/tests/kits` | Ran 8, OK |
| `templates/tests/` 頂層（`test_start`、`test_paths_move`、`test_daily`…） | Ran 28, OK (skipped=2, expected failures=2) |

`templates/tests/agent-fsm` 的 21 支沒跑，因為格的程式一行都沒改。

## 獨立審查（opus，沒看過實作，拿 03～06、10 對程式）

**結論**：大方向照設計稿與定調。它也在記憶體裡重算了一遍骨架的 9 份生成檔，跟進 git 的一字不差。

**兩條必修，都修了，並各補了測試**：

1. **`ag.no` 沒搭任何 `ag.pack`**：會生出 `{"tools": {"b": null}}`，`defs check` 會報「each tool must declare a path」。改成報 `SpecBad`。
2. **`ag.tool` 的額外欄位與指示詞不驗**：`env={"A": 1}`、`env="A"`、`cache=True`、`ag.home(None)` 都會放過，但 aos-tools 合併時會擋。改成照 `registry.finish` 先驗。

**建議，採用的**：
- 寫不成 JSON 的值（集合、NaN）改報 `SpecBad`，原本會冒 traceback、或寫出 C++ 讀不了的 `NaN`。
- 工具名照 aos-tools 的 `NAME_RE`。
- `INTERFACES` 拿掉整個 `aos-agent` 改報 `SpecBad`。
- `write_defs` 的註解改準確：改名那段才失敗的話，前面幾份已經換上了，重跑一次就好。
- `by_hand` 的檔名先正規化，並擋跑起來才寫的檔名。

**建議，沒採用的**：
- LLM 調整鍵的型別先驗：`defs check` 本來就不查，`llm_settings` 執行期會報，第一刀不加。
- 畫面輸出改印相對路徑：tool_spec 也是印絕對路徑，驗收要求的是產出檔裡沒有。
- 夾名先警告：`defs check` 會報，lib 只管它生的檔。
- 骨架的 `LLM={}`：已記在「自己定的細節」第 10 條。

## 使用者怎麼試（`install.py` 之後）

repo 裡還沒裝。要用的話，先在 `~/repo/aos/proto8` 跑 `python3 install.py`，這一步要你點頭；跑了會換掉正在用的那份 `bin/`、`lib/`。裝好之後：

```sh
source $AOS_HOME/env.sh
cd <你的樹>                               # 例：從 start-api 抄出來、正在跑的那棵
echo '{"op":"new","template":"agent-python","path":"agents/helper"}' | AOS_WS=$PWD aos-exec $AOS_HOME/lib/tools/agent/agent_def
                                          # 或 cp -r $AOS_HOME/templates/agent-python agents/helper
$EDITOR agents/helper/agent.py            # 改 DESCRIPTION / SYSTEM / TOOLS / LLM（假腦試就寫 {"model": "fake"}）
python3 agents/helper/agent.py --defs     # 先看會寫什麼（不寫檔）
python3 agents/helper/agent.py --write-defs
aos-agent -d .stack ctl add -w . agents/helper
aos-agent -d .stack --target helper say hello && aos-agent -d .stack --target helper listen --timeout-s 30
```

## 沒做、留給之後的

- 第二刀（`agent_def check` 順手重生）照 08 先不排。
- 第三刀：HOOKS、FILES、不宣告 FSM 的 eca 模式、用 reviewer 重寫當驗收。
- 知識庫（第五刀）。

## 行程與環境

- 開工前 `pgrep -af aos-`：除了 pgrep 自己，沒有別的行程。
- 收尾：`(none)`。暫存樹的兩台 daemon 都用 `aos-daemon-ctl -d <絕對路徑> shutdown` 關掉，退出也確認過。
- `~/aos-home` 不存在，沒建；shell 的設定檔沒動。
