# proto5

← [INDEX](../wf/INDEX.md)｜前一輪 [proto4-3](../proto4-3/README.md)（作業系統層）、[proto4-7](../proto4-7/README.md)（簡單 agent）｜使用者的方向草稿在 [`thinking/`](../thinking/)

proto5 從**把規範寫下來**開始：proto4-x 一路長出來的格式與約定，先一份一份寫成文件，
程式再照文件走。文件裡跟現行程式碼對不上的地方，以程式碼為準、回來改文件。

## 十分鐘上手（09-24 試玩 r1 補）

從 repo 根目錄照抄，一段一段貼進 bash／zsh。需要 Python 3.12+；第 4 段起要一個 OpenAI 相容的模型端點（這裡用本機 LM Studio 的 `google/gemma-4-e4b`，換別的就改 `llm.json`）。
工作目錄 `W` 隨你放；重來一次先 `rm -rf $W`。

**1. PATH 與 daemon。** PATH 一定要**先**含 `proto5/cli` 才開 daemon——daemon 拉的 cpu、cpu 跑的工作都繼承 daemon 開起來那一刻的環境，
之後再 `export` 沒用（漏了就 `aos-daemon stop` 重開）。daemon 是前景程式，放背景；它的 stderr 自己重導。

```sh
export PATH=$PWD/proto5/cli:$PATH
W=/tmp/aos-try; mkdir -p $W
aos-daemon --home $W/D 2>>$W/daemon.log &
```

**2. kernel：兩顆一般 cpu＋一顆專門問模型的 llm cpu。** `--env` 把 llm 設定檔的絕對路徑交給 llm cpu（模型表放 cpu 那邊，agent 只給代號）。

```sh
cat > $W/llm.json <<'EOF'
{"_metainfo": {"_type": "llm_config", "_version": 1},
 "models": {"small": {"endpoint": "http://127.0.0.1:1234/v1", "model": "google/gemma-4-e4b", "timeout_ms": 180000}}}
EOF
aos-kernel init $W/K --cpu 0 --cpu 1 --cpu llm:llm --env llm:AOS_LLM_CONFIG=$W/llm.json
aos-kernel check $W/K --daemon $W/D
aos-kernel boot $W/K --daemon $W/D
```

`check` 每行 `ok`／`warn`／`bad`；有 `bad` 先照提示修好再 boot。

**3. 跑一次、跑反覆。**

```sh
echo '{"argv": ["date"], "stdout": "once.out"}' > $W/once.json
aos-kernel add $W/K $W/once.json --once --wait-ms 10000
cat $W/once.out
cat > $W/count.json <<'EOF'
{"argv": ["sh", "-c", "echo tick >> count.txt; [ $(wc -l < count.txt) -lt 3 ] || exit 100"]}
EOF
aos-kernel add $W/K $W/count.json --name count --interval-ms 500
sleep 8
aos-kernel ls $W/K
```

兩件要記的事：
- **once 的回音不含 stdout**：`add --once` 印的 `{"code": 0, "kind": "child", …}` 只是執行狀態；`date` 印的東西在 inst 指的 `once.out` 裡。
- **CLI 成功 ≠ 工作成功**：`aos-kernel add` 退 0 只代表 kernel 收了單、回了音；工作本身成不成看回音的 `kind`、`code`、`timed_out`、`stopped`。
  反覆工作回 100＝做完（`ls` 看到 `count … done  runs 3`）；連敗 10 次會被標 `bad`，`ls` 那行會附「看 <log 路徑>」。

**4. 最小 agent：人格、一個工具、登記、投輸入、看回話。**

```sh
mkdir -p $W/bob/prompts $W/bob/tools
cat > $W/bob/info.json <<'EOF'
{"_metainfo": {"_type": "llm_agent", "_version": 1},
 "llm": {"model": "small", "timeout_ms": 190000},
 "tools": ["tools/base.json"],
 "tick": {"interval_ms": 500}}
EOF
cat > $W/bob/prompts/system.json <<'EOF'
{"content": "你是繁體中文助理。要知道現在時間就呼叫 date 工具，拿到結果後用一句話回答。"}
EOF
cat > $W/bob/tools/base.json <<'EOF'
[{"type": "function",
  "function": {"name": "date", "description": "取得現在的本機日期與時間",
               "parameters": {"type": "object", "properties": {}}},
  "_meta": {"argv": ["date", "+%Y-%m-%d %H:%M:%S"]}}]
EOF
aos-kernel check $W/K --agent $W/bob
export AOS_K=$W/K
aos-agent start $W/bob
echo '"現在幾點？請用工具查。"' > $W/bob/input.tmp && mv $W/bob/input.tmp $W/bob/input.json
sleep 20
aos-agent last $W/bob
```

`start` 印 `started agent-bob`。投進 `input.json` 後它自己走 idle→think（問模型）→act（跑 date）→think→idle，本機小模型大約 10 秒；
`last` 還印 `(tool_calls: date)` 或舊回話就再等幾秒重打。收過的輸入搬進 `bob/done/`。出錯看 `bob/log/agent.err`（它會指到 `log/llm.err` 並附最後一行）。

**5. 停機（順序：agent → kernel → daemon）。**

```sh
aos-agent stop $W/bob
aos-kernel stop $W/K
aos-daemon stop --home $W/D
```

三行各印 `stopped`。`aos-kernel stop` 會等到排程停、它的 cpu 都退出才回（要舊的「放完單就走」用 `--no-wait`）。
每一步的細節在下表的規範：daemon → [daemon.md](spec/daemon.md)、kernel → [kernel.md](spec/kernel.md)、agent → [agent.md](spec/agent.md)／[aos-agent.md](spec/aos-agent.md)、模型設定 → [aos-llm-call.md](spec/aos-llm-call.md)。

## 規範

| 文件 | 講什麼 | 現況 |
|---|---|---|
| [spec/directives.md](spec/directives.md) | 指示詞機制：`$env`／`$fmt`／`$ref` 取值、`$opt`／`$val` 選項物件、先解再驗、巢狀、循環、錯誤代號。任何 aos 的 JSON 檔都能用；哪個位置認得哪些選項名由宿主規範定 | 2026-09-21 定稿；實作 [`lib/aos_directives.py`](lib/aos_directives.py) |
| [spec/inst-posix.md](spec/inst-posix.md) | inst.json 的 `posix` 呼叫格式第 1 版：七個欄位、各位置的 `$opt` 選項（append／mkdir／inherit／merge／clear）、錯誤代號、執行語意，加上 `_metainfo`（`_type`／`_version`；沒寫＝posix v1）、頂層未知 key 忽略 | 2026-09-21 定稿；實作 [`lib/aos_inst.py`](lib/aos_inst.py)（讀／驗）＋ [`lib/aos_exec.py`](lib/aos_exec.py)（執行）。proto4-3 是凍結的舊版參考 |
| [spec/aos-exec.md](spec/aos-exec.md) | aos-exec 的**命令列**：三種目標（普通檔／`.json`／資料夾）、`--dir-target`／`--timeout-ms`／`--stderr`／`--`、退出碼 2／125／原樣、125 與 2 時 stderr 印什麼。行為照 inst-posix.md 第 6 節 | 命令列走法照 proto4-3 現況整理，使用者還沒逐條拍板 |
| [spec/cpu.md](spec/cpu.md) | cpu 範式（一個家一個主人：`info`／`state`／`requests`／`responses`、JSON-RPC 信封、ack）與 exec cpu：逐件照 aos-exec 跑一次、回音寫 `responses/` | 2026-09-23 定稿；實作 [`lib/aos_home.py`](lib/aos_home.py)＋[`lib/aos_client.py`](lib/aos_client.py)＋[`lib/aos_exec_cpu.py`](lib/aos_exec_cpu.py)（`aos-cpu`） |
| [spec/kernel.md](spec/kernel.md) | kernel：替登記的工作挑空 cpu 派下去、收結果、決定要不要再跑；每次只跑一格 `aos-kernel tick`，格接格排程 | 2026-09-23 定稿；實作 [`lib/aos_kernel.py`](lib/aos_kernel.py)（`aos-kernel`） |
| [spec/daemon.md](spec/daemon.md) | daemon：所有 cpu 的父行程，只管孩子的啟動、重拉、停止；家也照 cpu 範式長 | 2026-09-23 定稿；實作 [`lib/aos_daemon.py`](lib/aos_daemon.py)（`aos-daemon`） |
| [spec/agent.md](spec/agent.md) | 一個 agent 就是一個資料夾：info.json 記人格、記憶、工具與排程設定；state.json 記三格進度、批次與恢復紀錄 | 2026-09-24 定稿第 2 版；實作 [`lib/aos_agent_home.py`](lib/aos_agent_home.py)＋[`lib/aos_agent_info.py`](lib/aos_agent_info.py) |
| [spec/aos-agent.md](spec/aos-agent.md) | `aos-agent tick／start／stop [dir]`：走一格／向 kernel 登記／撤銷排程；模型與工具都交 kernel `add --once`、收回音並 ack | 2026-09-24 定稿第 2 版；實作 [`lib/aos_agent.py`](lib/aos_agent.py) 與拆分模組（見 [lib/](lib/README.md)） |
| [spec/aos-llm-call.md](spec/aos-llm-call.md) | `aos-llm-call [AGENT_DIR]`：讀 agent 家與 `AOS_LLM_CONFIG`、組請求、打一次 HTTP、印模型回的 message | 2026-09-24 定稿第 2 版；實作 [`lib/aos_llm_call.py`](lib/aos_llm_call.py) |

## 程式

2026-09-24：cpu／daemon／kernel 與 agent 線已接上新架構。`aos-llm-call` 問模型一次，
`aos-agent tick／start／stop` 負責走格與 kernel 排程；模型與工具都透過 kernel 交給 exec cpu 執行。
舊 llm／tool cpu 與 aos-llm-ask 已移除。實作中的規範歧義與限制記在 [impl-findings.md](notes/2026-09-23-rearch/impl-findings.md)。

| 位置 | 講什麼 | 現況 |
|---|---|---|
| [lib/](lib/README.md) | 十八支標準庫 Python 3.12 模組。底層 directives → inst → exec；home／client 共用家與交件；exec_cpu 執行、daemon 管孩子、kernel 排程；agent 共用讀驗、批次、輸入、結果與恢復模組。逐檔 API 與測試表見 lib README | 24 個測試檔、959 條：`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test` |
| [cli/](cli/) | 六個薄入口：`aos-exec`、`aos-cpu`、`aos-daemon`、`aos-kernel`、`aos-llm-call`、`aos-agent` | agent 已接上 kernel；測試涵蓋崩潰窗口、真 daemon＋kernel＋exec cpu 整合與完整停機 |

拍板過程的任務書副本在 [notes/2026-09-21-inst-rev-rules.md](notes/2026-09-21-inst-rev-rules.md)（A～L 節）。

## 筆記

- [notes/](notes/)：任務書副本、astra 的調查報告、我的精簡總結（每份都有「要使用者拍板的」清單）。
- [notes-brief/](notes-brief/README.md)：**notes/ 的精簡版**，每份不超過 5000 字；README 尾巴有「今天要使用者拍板的題目總表」，先看這裡。
- [notes/2026-09-22-decisions.md](notes/2026-09-22-decisions.md)：**23 題的拍板紀錄**（2026-09-22），proto5.1 第 4 段與之後的回流都照這份。
- [backlog/](backlog/README.md)：先記著、之後再做的事，一件一個檔。
- [notes/2026-09-22-backflow.md](notes/2026-09-22-backflow.md)：**規範回流紀錄**：哪些從 proto5.1 搬回來、跟舊版差在哪、程式還差什麼。

## 還沒定的

由使用者口述、陸續補進來；我不代替他想（[AGENTS 鐵律 5](../AGENTS.md)）。
