# proto5

← [INDEX](../wf/INDEX.md)｜前一輪 [proto4-3](../proto4-3/README.md)（作業系統層）、[proto4-7](../proto4-7/README.md)（簡單 agent）｜使用者的方向草稿在 [`thinking/`](../thinking/)

proto5 從**把規範寫下來**開始：proto4-x 一路長出來的格式與約定，先一份一份寫成文件，
程式再照文件走。文件裡跟現行程式碼對不上的地方，以程式碼為準、回來改文件。

## 十分鐘上手（09-24 試玩 r1 補；fix-r4 全文改成新指令）

從 repo 根目錄照抄，一段一段貼進 bash／zsh。需要 Python 3.12 以上（3.12 與 3.14 實測過）；第 4 段起要一個 OpenAI 相容的模型端點——任何一個都行，例：LiteLLM 的 `http://localhost:4000/v1`／`deepseek-chat`（換別的就改 `llm.json` 的 `endpoint`、`model`，要金鑰加 `api_key`）。
工作目錄 `W` 隨你放；重來一次先 `rm -rf $W`。

**三支指令怎麼指「家」**（09-24 fix-r4）：`aos-daemon`、`aos-kernel`、`aos-agent` 都用 `--target DIR`。省略時 daemon 找 `AOS_DAEMON_HOME`、kernel 找 `AOS_KERNEL_HOME`，再沒有就用**目前資料夾**；agent 沒有環境變數，省略就是目前資料夾。
下面先把兩個環境變數設好，所以 daemon、kernel 的指令都不寫 `--target`；agent 家寫 `--target $W/bob`（`cd $W/bob` 之後也可以省略）。kernel 或 daemon 報錯時，錯誤行尾巴會寫它這次用的是哪個家、從哪來的。

**1. PATH 與 daemon。** PATH 一定要**先**含 `proto5/cli` 才開 daemon——daemon 拉的 cpu、cpu 跑的工作都繼承 daemon 開起來那一刻的環境，
之後再 `export` 沒用（漏了就 `aos-daemon halt` 重開）。daemon 是前景程式，放背景；它的 stderr 自己重導。
（09-24 試玩 r3 補）用 `&` 放背景的 daemon 綁著這個終端：關掉終端、或在「每段開一個新 shell」的腳本／工具裡跑，它會跟著被收掉。要它留下來就換成 `setsid aos-daemon boot 2>>$W/daemon.log </dev/null &`（或 `nohup`）。

```sh
export PATH=$PWD/proto5/cli:$PATH
W=/tmp/aos-try; mkdir -p $W
export AOS_DAEMON_HOME=$W/D AOS_KERNEL_HOME=$W/K
aos-daemon boot 2>>$W/daemon.log &
```

**2. kernel：兩顆一般 cpu＋一顆專門問模型的 llm cpu。** kernel 的設定寫成一份 `kernel.json` 再 `init`：`cpus` 列要開哪幾顆 cpu，
`llm` 那顆標 `pool: llm`，`envs` 把 llm 設定檔的絕對路徑交給它（模型表放 cpu 那邊，agent 只給代號）。排程用的 `k` 會自動加。

```sh
cat > $W/llm.json <<'EOF'
{"_metainfo": {"_type": "llm_config", "_version": 1},
 "models": {"default": {"endpoint": "http://localhost:4000/v1", "model": "deepseek-chat"}}}
EOF
cat > $W/kernel.json <<EOF
{"cpus": {"0": {}, "1": {},
          "llm": {"pool": "llm", "envs": {"AOS_LLM_CONFIG": "$W/llm.json"}}}}
EOF
aos-kernel init --config $W/kernel.json
aos-kernel check --probe
aos-kernel boot
```

`check` 每行 `ok`／`warn`／`bad`；有 `bad` 先照提示修好再 boot。`--probe` 會真的對 llm.json 的 endpoint 打一次（port 寫錯在這裡就抓到）；不帶它只驗設定，最後一行會寫「未測模型連線」（09-24 fix-r5）。`boot` 成功印 `booted 4 cpus`（`k` 自動加的那顆也算）。`kernel.json` 還能寫 `tick_ms`、`interval_ms`、`timeout_ms` 這些排程預設，格式就是 `K/info.json` 那幾格（kernel 規範 [§1.1](spec/kernel/home.md)、[§6](spec/kernel/cli.md)）。

**3. 跑一次、跑反覆。**

```sh
echo '{"argv": ["date"], "stdout": "once.out"}' > $W/once.json
aos-kernel add $W/once.json --once --wait-ms 10000
cat $W/once.out
cat > $W/count.json <<'EOF'
{"argv": ["sh", "-c", "echo tick >> count.txt; [ $(wc -l < count.txt) -lt 3 ] || exit 100"]}
EOF
aos-kernel add $W/count.json --name count --interval-ms 500
sleep 8
aos-kernel ls
```

兩件要記的事：
- **once 的回音不含 stdout**：`add --once` 印的 `{"code": 0, "kind": "child", …}` 只是執行狀態；`date` 印的東西在 inst 指的 `once.out` 裡。
- **CLI 成功 ≠ 工作成功**：`aos-kernel add` 退 0 只代表 kernel 收了單、回了音（`add --once` 沒帶 `--wait-ms` 時連回音都不等：只印單名與回音路徑就退 0，回音之後自己去 `K/responses/` 看）；工作本身成不成看回音的 `kind`、`code`、`timed_out`、`stopped`。
  反覆工作回 100＝做完（`ls` 看到 `count … done  runs 3`）；連敗 10 次會被標 `bad`，`ls` 那行會附「看 <log 路徑>」。

**4. 最小 agent：生家、登記、說一句、等回話。**（09-24 試玩 r2 改用 `init`＋`say --wait`）

```sh
aos-agent init --target $W/bob
aos-kernel check --agent $W/bob
aos-agent start --target $W/bob
aos-agent say "現在幾點？請用工具查。" --target $W/bob --wait
```

`init` 生出人格、一個 `date` 工具、`input/`、`log/`，`llm.model` 是代號 `default`（就是第 2 段 llm.json 裡那個）。`start` 印 `started agent-bob`（它用 `AOS_KERNEL_HOME` 找 kernel）。
`say --wait` 把話投進 `bob/input/`，等它自己走完 idle→think（問模型）→act（跑 date）→think→idle，印出回話（看模型：純文字約 5 秒、要跑工具約 10～20 秒）。
`--wait` 不帶數字最多等 300 秒，`--wait 60` 就是等 60 秒。還沒被收的話如果有好幾則，下一格會**合成一輪**一起問模型（09-24 試玩 r3 補）。
**agent 多了要多開 cpu**（09-24 fix-r5）：每個 agent 每走一格都要佔一顆 `default` 池的 cpu，工具也在那裡跑；兩、三個以上的 agent 就在 `kernel.json` 的 `cpus` 多寫幾顆（例：`"2": {}, "3": {}`），`aos-kernel halt` 後改 `K/info.json` 再 `boot`。

看回話用 `listen`（09-24 fix-r4，取代舊的 `last`），三種擇一：`--last`（預設）印最後一則就退；`--wait [秒]` 等**下一則新**回話、印出就退（等不到退 101）；`--follow` 每來一則印一則，Ctrl-C 結束。
`--last` 在 stderr 附一行時間；它取到的如果是中途叫工具的那句、或新的話還沒回，stderr 會多一行「還在處理中（tool_calls: …）」——那不是最後答案，用 `--wait` 等（09-24 fix-r5）。

```sh
aos-agent listen --target $W/bob
aos-agent say "再說一次現在幾點。" --target $W/bob
aos-agent listen --target $W/bob --wait 60
aos-agent listen --target $W/bob --follow     # 開著看，看夠了按 Ctrl-C
```

不順就 `aos-agent status --target $W/bob`：第一行 `health` 一句話說正不正常（`ok`／`沒登記`／`手動暫停`／`連敗暫停`／`kernel 家有問題`，括號裡是該打的指令；09-24 fix-r5 再加三種會自己好的：`重試中（連敗 N/3）`、`恢復中（llm cpu dead，daemon 重拉中）`、`已解除暫停，等下一次成功`），`error` 是**這次**卡住的原因（沒卡住印「（無）」，舊錯另列一行、開頭標「（已恢復）」），再往下是在哪一格、在等什麼、kernel 那邊的狀態（09-24 試玩 r3 改）。
問模型連敗 3 次它會暫停，修好原因後 `aos-agent continue --target $W/bob`；`continue` 之後先標「已解除暫停，等下一次成功」，真的問成功了才標「已恢復」。
llm.json 是所有 agent 共用的，它一壞，正在說話的 agent 會一起暫停：修好後 `aos-agent continue --all` 一次解開全部（它看 `AOS_KERNEL_HOME` 帳本裡登記的 agent；`aos-kernel ls` 的 agent 行也會標出誰在暫停）（09-24 fix-r5）。
想讓它先停手（還登記著，但每格什麼都不做）就 `aos-agent pause --target $W/bob`；這時 `say` 照收、提示「continue 後才會處理」，`continue` 同時解手動暫停和連敗暫停（09-24 fix-r4）。
沒 `start` 就 `say`：話照樣投進去，stdout 會說「已投入，start 後會處理，不要再說一次」——`start` 之後它就會回，別再說一次（不然同一句會進記憶兩次）；`--wait` 則立刻退 101，不乾等（09-24 試玩 r3 補；fix-r5 改）。
`say --wait`／`listen --wait` 開始等之前先看一次：kernel 家壞了、daemon 沒在跑、手動暫停、連敗暫停、被判 bad，都立刻退 101 並印原因（09-24 fix-r5）。

**5. 停機（順序：agent → kernel → daemon）。** 要接著做第 6 段就先跳過這段，最後再停。

```sh
aos-agent stop --target $W/bob
aos-kernel halt
aos-daemon halt
```

第一行印 `stopped agent-bob`，後兩行各印 `stopped`。`aos-kernel halt` 會等到排程停、它的 cpu 都退出才回（要舊的「放完單就走」用 `--no-wait`）。
**daemon 掛了**（09-24 試玩 r2 補）：cpu 全跟著死，重開 daemon（第 1 段那行）再 `aos-kernel boot`；`aos-kernel ls`／`check` 看到 cpu `missing` 也會提示這行。

**每天重開機**（09-24 試玩 r3 補）。關機、登出或關掉終端後 daemon 和 cpu 都沒了，家（`D`、`K`、agent 家）還在，照這個順序開回來：

```sh
export PATH=$PWD/proto5/cli:$PATH
W=/tmp/aos-try; export AOS_DAEMON_HOME=$W/D AOS_KERNEL_HOME=$W/K
setsid aos-daemon boot 2>>$W/daemon.log </dev/null &
aos-kernel boot
aos-agent start --target $W/bob        # 有幾個家就 start 幾個
aos-kernel check --agent $W/bob
aos-kernel ls                          # 第一行 health ok 就是正常
```

- 昨天照第 5 段停過 agent 才要 `start`；沒停就關機的，登記還留在 kernel 帳本，`start` 印 `already started agent-bob`、退 0（09-24 fix-r5；寫成 `set -e` 的開機腳本也不會斷）。
- `aos-kernel ls` 第一行 `health` 分得出「停住」跟「正常忙碌」：`ok`、`daemon 沒在跑`、`K 家缺目錄（跑 aos-kernel check）`、`cpu missing（跑 boot）`、`tick 停住`、`停機中`；（09-24 fix-r5）`恢復中（… cpu dead，daemon 重拉中）` 會自己好；kernel 沒事時還會講 agent：`agent 暫停中：…（aos-agent continue --all）`、`重試中：…`、`已解除暫停，等下一次成功：…`。不是 `ok` 就照括號裡的指令做。
- 三種壞法各一個指令：daemon 掛了 → 重開 daemon＋`boot`；kernel 家壞了（`health` 說缺目錄或停住）→ `aos-kernel check` 照提示修；agent 暫停 → 修好原因後 `aos-agent continue --target $W/bob`。
- （09-24 fix-r4）從舊版升上來的：**換版前**用舊版的指令停（`aos-kernel stop $W/K`、`aos-daemon stop --home $W/D`，舊版還沒有 `halt`），換版後照這段重開；舊鏈排好的下一格是舊指令格式，不重 `boot` 會停住。agent 家的舊 `tick.json` 在 `start` 時自動改寫。

**6. 自己寫一支工具。**（09-24 試玩 r2 補）工具就是一支程式：**stdin 收模型給的 arguments（JSON 字串）、stdout 印的東西原樣給模型看**。
`_meta.argv[0]` 含 `/` 就是**相對 agent 家**的路徑、要有執行位；工具的 cwd 也是 agent 家。放進 `tools/` 下一格就生效，不用重 start。

```sh
mkdir -p $W/bob/tools/bin
cat > $W/bob/tools/bin/add <<'EOF'
#!/usr/bin/env python3
import json, sys
args = json.load(sys.stdin)
print(args["a"] + args["b"])
EOF
chmod +x $W/bob/tools/bin/add
cat > $W/bob/tools/add.json <<'EOF'
[{"type": "function",
  "function": {"name": "add", "description": "把兩個整數加起來",
               "parameters": {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                              "required": ["a", "b"]}},
  "_meta": {"argv": ["tools/bin/add"]}}]
EOF
aos-kernel check --agent $W/bob
aos-agent say "請用 add 工具算 1234 加 4321，只回數字。" --target $W/bob --wait
```

工具壞了（JSON 寫錯、沒執行位）`check --agent` 會指出來；跑起來失敗時模型看得到 `exit 126／127` 的說明（寫進記憶裡那則 tool 訊息，`listen --follow` 或看 `prompts/history.json`）。**`log/agent.err` 不會有這一行**：工具失敗是給模型看的結果，不算 agent 自己的錯（09-24 fix-r5 對回實際行為）。完整格式在 [agent.md §3.3](spec/agent/info.md)。做完回第 5 段停機。

**附：不用 `init` 的手動做法。** 家就是一個資料夾，`init` 只是替你寫好這三份。這種家的輸入投 `input.json`，要原子地投：先寫暫存檔再 `mv`。

```sh
mkdir -p $W/amy/prompts $W/amy/tools
cat > $W/amy/info.json <<'EOF'
{"_metainfo": {"_type": "llm_agent", "_version": 1},
 "llm": {"model": "default", "timeout_ms": 190000},
 "tools": ["tools/base.json"],
 "tick": {"interval_ms": 500}}
EOF
cat > $W/amy/prompts/system.json <<'EOF'
{"content": "你是繁體中文助理。要知道現在時間就呼叫 date 工具，拿到結果後用一句話回答。"}
EOF
cat > $W/amy/tools/base.json <<'EOF'
[{"type": "function",
  "function": {"name": "date", "description": "取得現在的本機日期與時間",
               "parameters": {"type": "object", "properties": {}}},
  "_meta": {"argv": ["date", "+%Y-%m-%d %H:%M:%S"]}}]
EOF
aos-agent start --target $W/amy
echo '"現在幾點？請用工具查。"' > $W/amy/input.tmp && mv $W/amy/input.tmp $W/amy/input.json
sleep 20
aos-agent listen --target $W/amy
aos-agent stop --target $W/amy
```

收過的輸入搬進 `amy/done/`（`init` 的家是 `bob/input/done/`）。

每一步的細節在下表的規範：daemon → [daemon.md](spec/daemon/README.md)、kernel → [kernel.md](spec/kernel/README.md)、agent → [agent.md](spec/agent/README.md)／[aos-agent.md](spec/aos-agent/README.md)（兩份都有「使用者只需要懂的」：[agent](spec/agent/essentials.md)、[aos-agent](spec/aos-agent/essentials.md)）、模型設定 → [aos-llm.md](spec/aos-llm/README.md)。

## 規範

一份規範一個資料夾，入口是資料夾裡的 README（定位、已拍板的前提、各節在哪個檔）；總導航 [spec/README.md](spec/README.md)。文中「§3」這類節號照舊，到該資料夾 README 查。

| 文件 | 講什麼 | 現況 |
|---|---|---|
| [spec/directives/](spec/directives/README.md) | 指示詞機制：`$env`／`$fmt`／`$ref` 取值、`$opt`／`$val` 選項物件、先解再驗、巢狀、循環、錯誤代號。任何 aos 的 JSON 檔都能用；哪個位置認得哪些選項名由宿主規範定 | 2026-09-21 定稿；實作 [`lib/aos_directives.py`](lib/aos_directives.py) |
| [spec/inst-posix/](spec/inst-posix/README.md) | inst.json 的 `posix` 呼叫格式第 1 版：七個欄位、各位置的 `$opt` 選項（append／mkdir／inherit／merge／clear）、錯誤代號、執行語意，加上 `_metainfo`（`_type`／`_version`；沒寫＝posix v1）、頂層未知 key 忽略 | 2026-09-21 定稿；實作 [`lib/aos_inst.py`](lib/aos_inst.py)（讀／驗）＋ [`lib/aos_exec.py`](lib/aos_exec.py)（執行）。proto4-3 是凍結的舊版參考 |
| [spec/aos-exec/](spec/aos-exec/README.md) | aos-exec 的**命令列**：三種目標（普通檔／`.json`／資料夾）、`--dir-target`／`--timeout-ms`／`--stderr`／`--`、退出碼 2／125／原樣、125 與 2 時 stderr 印什麼。行為照 inst-posix.md 第 6 節 | 命令列走法照 proto4-3 現況整理，使用者還沒逐條拍板 |
| [spec/cpu/](spec/cpu/README.md) | cpu 範式（一個家一個主人：`info`／`state`／`requests`／`responses`、JSON-RPC 信封、ack）與 exec cpu：逐件照 aos-exec 跑一次、回音寫 `responses/` | 2026-09-23 定稿；實作 [`lib/aos_home.py`](lib/aos_home.py)＋[`lib/aos_client.py`](lib/aos_client.py)＋[`lib/aos_exec_cpu.py`](lib/aos_exec_cpu.py)（`aos-cpu`） |
| [spec/kernel/](spec/kernel/README.md) | kernel：替登記的工作挑空 cpu 派下去、收結果、決定要不要再跑；每次只跑一格 `aos-kernel tick`，格接格排程 | 2026-09-23 定稿；實作 [`lib/aos_kernel.py`](lib/aos_kernel.py)（`aos-kernel`；09-24 拆成 `aos_kernel_*.py` 幾支） |
| [spec/daemon/](spec/daemon/README.md) | daemon：所有 cpu 的父行程，只管孩子的啟動、重拉、停止；家也照 cpu 範式長 | 2026-09-23 定稿；實作 [`lib/aos_daemon.py`](lib/aos_daemon.py)（`aos-daemon`） |
| [spec/agent/](spec/agent/README.md) | 一個 agent 就是一個資料夾：info.json 記人格、記憶、工具與排程設定；state.json 記三格進度、批次與恢復紀錄 | 2026-09-24 定稿第 2 版；實作 [`lib/aos_agent_home.py`](lib/aos_agent_home.py)＋[`lib/aos_agent_info.py`](lib/aos_agent_info.py) |
| [spec/aos-agent/](spec/aos-agent/README.md) | `aos-agent tick／start／stop [--target DIR]`：走一格／向 kernel 登記／撤銷排程；模型與工具都交 kernel `add --once`、收回音並 ack。日常的 `init`／`say`／`listen`／`status`／`pause`／`continue` 在 §1（09-24 試玩 r2 補；fix-r4 改 `--target`、`listen`、`pause`、tick 鎖） | 2026-09-24 定稿第 2 版；實作 [`lib/aos_agent.py`](lib/aos_agent.py) 與拆分模組（見 [lib/](lib/README.md)） |
| [spec/aos-llm/](spec/aos-llm/README.md) | `aos-llm call [AGENT_DIR]`（09-24 fix-r4 由 `aos-llm-call` 改名）：讀 agent 家與 `AOS_LLM_CONFIG`、組請求、打一次 HTTP、印模型回的 message | 2026-09-24 定稿第 2 版；實作 [`lib/aos_llm_call.py`](lib/aos_llm_call.py) |

## 程式

2026-09-24：cpu／daemon／kernel 與 agent 線已接上新架構。`aos-llm call` 問模型一次，
`aos-agent tick／start／stop／init／say／listen／status／pause／continue` 負責走格、kernel 排程與日常操作；模型與工具都透過 kernel 交給 exec cpu 執行。
舊 llm／tool cpu 與 aos-llm-ask 已移除。審查與實作紀錄在 [rearch 筆記](notes/2026-09-23-rearch/README.md)。

| 位置 | 講什麼 | 現況 |
|---|---|---|
| [lib/](lib/README.md) | 二十九支標準庫 Python 3.12 以上模組。底層 directives → inst → exec；home／client 共用家與交件；exec_cpu 執行、daemon 管孩子、kernel 排程；agent 共用讀驗、批次、輸入、結果與恢復模組。逐檔 API 與測試表見 lib README | 32 個測試檔、1133 條：`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test` |
| [cli/](cli/) | 六個薄入口：`aos-exec`、`aos-cpu`、`aos-daemon`、`aos-kernel`、`aos-llm`（09-24 fix-r4 由 `aos-llm-call` 改名）、`aos-agent` | agent 已接上 kernel；測試涵蓋崩潰窗口、真 daemon＋kernel＋exec cpu 整合與完整停機 |

拍板過程的任務書副本在 [notes/2026-09-21-inst-rev-rules.md](notes/2026-09-21-inst-rev-rules.md)（A～L 節）。

## 筆記

- [notes/](notes/README.md)：**先看索引**——任務書副本、astra 的調查／審查報告、我的精簡總結、重架構與試玩紀錄，按日期分組。
- [notes-brief/](notes-brief/README.md)：**notes/ 的精簡版**，每份不超過 5000 字；README 尾巴有「今天要使用者拍板的題目總表」，先看這裡。
- [notes/2026-09-22-decisions.md](notes/2026-09-22-decisions.md)：**23 題的拍板紀錄**（2026-09-22），proto5.1 第 4 段與之後的回流都照這份。
- ~~backlog/~~：2026-09-24 agent 線定稿後六個檔逐一判掉、資料夾拿掉，見 [backlog-cleanup](notes/2026-09-24-backlog-cleanup.md)。
- [notes/2026-09-22-backflow.md](notes/2026-09-22-backflow.md)：**規範回流紀錄**：哪些從 proto5.1 搬回來、跟舊版差在哪、程式還差什麼。

## 還沒定的

由使用者口述、陸續補進來；我不代替他想（[AGENTS 鐵律 5](../AGENTS.md)）。
