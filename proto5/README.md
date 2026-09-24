# proto5

← [INDEX](../wf/INDEX.md)｜前一輪 [proto4-3](../proto4-3/README.md)（作業系統層）、[proto4-7](../proto4-7/README.md)（簡單 agent）｜使用者的方向草稿在 [`thinking/`](../thinking/)｜**上手看 [教程](tutorials/README.md)**

proto5 從**把規範寫下來**開始：proto4-x 一路長出來的格式與約定，先一份一份寫成文件，
程式再照文件走。文件裡跟現行程式碼對不上的地方，以程式碼為準、回來改文件。

## 這是什麼

一套用資料夾跑 LLM agent 的小作業系統，六支 Python 指令（`proto5/cli/`，Python 3.12 以上），模型走任何 OpenAI 相容端點。

```text
daemon（家 D）          所有 cpu 的爸爸：拉起來、死了重拉、要停就停
 ├─ cpu k   （kernel 池） 一格一格跑 aos-kernel tick——這就是 kernel 的排程
 ├─ cpu 0、1…（default 池）跑一般工作、agent 的每一格、agent 的工具
 └─ cpu llm （llm 池）    跑 aos-llm call 問模型；環境裡的 AOS_LLM_CONFIG 指到 llm.json
kernel（家 K）          不是常駐程式：帳本 K/state.json＋一格接一格的 tick，替登記的工作挑空 cpu、收結果、決定要不要再跑
agent（一個資料夾）      人格、記憶、工具、進度；登記成 kernel 的一份反覆工作 agent-<資料夾名>
```

cpu 就是「一個資料夾＋一個主人程式」：往它的 `requests/` 放一張單，它照單跑一次程式、結果寫進 `responses/`。
agent 每一格只做一小步（收輸入→問模型→跑工具→再問）就退出，問模型和跑工具都是交給 kernel 的一次性工作。

## 五分鐘看到 agent 回話

從 repo 根目錄貼進 bash／zsh（端點換成你的；下面是 LiteLLM）。這段是教程 01＋03 的濃縮，要從頭學就先 `rm -rf $HOME/aos-try` 再照[教程](tutorials/README.md)做。

```sh
W=$HOME/aos-try; mkdir -p $W
export PATH=$PWD/proto5/cli:$PATH AOS_DAEMON_HOME=$W/D AOS_KERNEL_HOME=$W/K
setsid aos-daemon boot >>$W/daemon.log 2>&1 </dev/null &
cat > $W/llm.json <<'EOF'
{"_metainfo": {"_type": "llm_config", "_version": 1},
 "models": {"default": {"endpoint": "http://localhost:4000/v1", "model": "deepseek-chat"}}}
EOF
cat > $W/kernel.json <<EOF
{"cpus": {"0": {}, "1": {}, "llm": {"pool": "llm", "envs": {"AOS_LLM_CONFIG": "$W/llm.json"}}}}
EOF
aos-kernel init --config $W/kernel.json && aos-kernel check --probe && aos-kernel boot
aos-agent init --target $W/bob && aos-agent start --target $W/bob
aos-agent say "現在幾點？請用工具查。" --target $W/bob --wait
```

最後一行約 10～20 秒印出回話。停機：`aos-agent stop --target $W/bob; aos-kernel halt; aos-daemon halt`。

## 指令一覽

家一律用 `--target DIR` 指；省略時 daemon 找 `AOS_DAEMON_HOME`、kernel 找 `AOS_KERNEL_HOME`，再沒有（agent 則一律）就用目前資料夾。每個指令 `-h` 印用法。

| 指令 | 一句話 | 教程 |
|---|---|---|
| `aos-daemon boot`／`halt` | 開 daemon（前景程式，自己放背景）／停 daemon 並等它退出 | [01](tutorials/01-daemon-kernel.md) |
| `aos-kernel init --config FILE` | 照一份 JSON 建 kernel 的家（cpu 表、排程預設） | [01](tutorials/01-daemon-kernel.md) |
| `aos-kernel check [--probe]` | 開機前檢查 kernel 家、daemon、PATH、llm 設定；`--probe` 真的打一次模型端點 | [01](tutorials/01-daemon-kernel.md) |
| `aos-kernel boot`／`halt` | 拉起 cpu、開始排程／停排程並等 cpu 都退出 | [01](tutorials/01-daemon-kernel.md) |
| `aos-kernel ls [-v] [--json]` | 全局：第一行 `health`，再來 cpu 表、行程表、佇列；`-v` 印完整路徑、`--json` 給程式讀 | [01](tutorials/01-daemon-kernel.md)、[05](tutorials/05-many-agents.md) |
| `aos-kernel add INST [--once]` | 登記一份工作：跑一次，或反覆跑到做完 | [02](tutorials/02-kernel-jobs.md) |
| `aos-kernel rm NAME`／`ack NAME` | 撤掉一份工作／簽收一則回音 | [02](tutorials/02-kernel-jobs.md) |
| `aos-agent init` | 生一個最小可跑的 agent 家 | [03](tutorials/03-first-agent.md) |
| `aos-agent check [--probe]` | 檢查 agent 家：設定、池、模型代號、工具 | [03](tutorials/03-first-agent.md) |
| `aos-agent start`／`stop` | 向 kernel 登記／撤銷這個 agent | [03](tutorials/03-first-agent.md) |
| `aos-agent say "…" [--wait]` | 投一則話；`--wait` 等回話印出來 | [03](tutorials/03-first-agent.md) |
| `aos-agent listen [--last [N]｜--wait [秒]｜--follow] [--show-calls｜--show-calls-full]` | 三種一定要給一種：`--last [N]` 印最後 N 則（N＞1 時每輪有標頭）｜`--wait [秒]`｜`--follow`；加 `--show-calls` 連工具呼叫一起印，`--show-calls-full` 印完整參數與回傳 | [03](tutorials/03-first-agent.md) |
| `aos-agent talk [--target DIR] [--wait 秒] [--show-calls]` | 來回聊的極簡 REPL：打一行、等回話、再打一行；`/help` 看全部 slash 指令，Ctrl-C 離開 | [03](tutorials/03-first-agent.md) |
| `aos-agent status` | 第一行 `health`，再來在哪一格、在等什麼、這次的錯 | [03](tutorials/03-first-agent.md) |
| `aos-agent pause`／`continue [--all]` | 手動暫停／解除手動暫停與連敗暫停（`--all`＝kernel 登記的全部） | [04](tutorials/04-tools-and-pause.md)、[05](tutorials/05-many-agents.md) |
| `aos-agent tools add base --target 家 [--root DIR]` | 裝內建工具包 base（read／write／edit／bash／grep／find／ls），`--root` 指工作根目錄 | [04](tutorials/04-tools-and-pause.md) |
| `aos-agent tools ls/add/rm/alias/unalias [--target 家]` | 看有哪些工具／裝或原地引用一個工具檔或資料夾／拿掉一支（不刪檔）／改名 | [04b](tutorials/04b-access-and-tool-admin.md) |
| `aos-agent access ls/set/rm/cwd/net [--target 家]` | 看／改工具被關進的牢（`access.json`）：掛哪些資料夾、起點、能不能連網 | [04b](tutorials/04b-access-and-tool-admin.md) |
| `aos-kernel tick`、`aos-agent tick` | 走一格；kernel 自己會叫，人不用打 | — |
| `aos-llm call`、`aos-cpu`、`aos-exec`、`aos-jail` | 問一次模型／cpu 主人程式／照 inst 跑一次程式／把一支程式關進沙盒跑；都是別的指令在叫，`aos-jail` 是 `aos-agent` 送件時自動用，平常不用自己叫 | — |

## 去哪讀

- **[tutorials/](tutorials/README.md)**：五篇照抄就能跑的教程＋附錄，從開機到管一堆 agent；第 07 篇讓 Claude Code／Codex 當 cpu 跑單子。
- **[spec/](spec/README.md)**：每個指令、每種檔案的規範（下表）；給使用者的精簡版是 [agent 家](spec/agent/essentials.md)、[aos-agent 指令](spec/aos-agent/essentials.md) 兩份「使用者只需要懂的」。
- **[lib/](lib/README.md)**：程式模組與測試（下面「程式」）。
- **[notes/](notes/README.md)**：任務書、審查、試玩紀錄（下面「筆記」）。

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
| [spec/aos-agent/](spec/aos-agent/README.md) | `aos-agent tick／start／stop [--target DIR]`：走一格／向 kernel 登記／撤銷排程；模型與工具都交 kernel `add --once`、收回音並 ack。日常的 `init`／`say`／`listen`／`status`／`pause`／`continue`／`check`／`tools add`／`talk` 在 §1（09-24 試玩 r2 補；fix-r4 改 `--target`、`listen`、`pause`、tick 鎖；advice-r1 加 `check`；tools-base 加 `tools add`（tools.md §1.8）；talk 加 `talk`（cli-talk-repl.md §1.9）） | 2026-09-24 定稿第 2 版；實作 [`lib/aos_agent.py`](lib/aos_agent.py) 與拆分模組（見 [lib/](lib/README.md)） |
| [spec/aos-llm/](spec/aos-llm/README.md) | `aos-llm call [AGENT_DIR]`（09-24 fix-r4 由 `aos-llm-call` 改名）：讀 agent 家與 `AOS_LLM_CONFIG`、組請求、打一次 HTTP、印模型回的 message | 2026-09-24 定稿第 2 版；實作 [`lib/aos_llm_call.py`](lib/aos_llm_call.py) |

## 程式

2026-09-24：cpu／daemon／kernel 與 agent 線已接上新架構。`aos-llm call` 問模型一次，
`aos-agent tick／start／stop／init／say／listen／status／pause／continue` 負責走格、kernel 排程與日常操作；模型與工具都透過 kernel 交給 exec cpu 執行。
舊 llm／tool cpu 與 aos-llm-ask 已移除。審查與實作紀錄在 [rearch 筆記](notes/2026-09-23-rearch/README.md)。

| 位置 | 講什麼 | 現況 |
|---|---|---|
| [lib/](lib/README.md) | 三十八支標準庫 Python 3.12 以上模組。底層 directives → inst → exec；home／client 共用家與交件；exec_cpu 執行、daemon 管孩子、kernel 排程；agent 共用讀驗、批次、輸入、結果與恢復模組。逐檔 API 與測試表見 lib README | 46 個測試檔、1512 條：`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test` |
| [cli/](cli/) | 七個薄入口：`aos-exec`、`aos-cpu`、`aos-daemon`、`aos-kernel`、`aos-llm`（09-24 fix-r4 由 `aos-llm-call` 改名）、`aos-agent`、`aos-jail`（09-24 access-impl，aos-agent 自動用） | agent 已接上 kernel；測試涵蓋崩潰窗口、真 daemon＋kernel＋exec cpu 整合與完整停機 |
| [templates/cli-agents/](templates/cli-agents/README.md) | Claude Code／Codex 當普通 cpu 的範本（階 0，不是程式）：另一個 kernel 家的設定、`claude -p` 與 `codex exec` 唯讀審查的單子、接著聊的分岔版 | 09-24 stage0；用法見[教程 07](tutorials/07-cli-agents.md) |
| [tools/](tools/README.md) | `aos-agent tools add` 裝的工具包：內建 `base`（read／write／edit／bash／grep／find／ls，仿 pi） | 09-24 tools-base；每支工具怎麼用、錯誤長怎樣見 [tools/README.md](tools/README.md) |

拍板過程的任務書副本在 [notes/2026-09-21-inst-rev-rules.md](notes/2026-09-21-inst-rev-rules.md)（A～L 節）。

## 筆記

- [notes/](notes/README.md)：**先看索引**——任務書副本、astra 的調查／審查報告、我的精簡總結、重架構與試玩紀錄，按日期分組。
- [notes-brief/](notes-brief/README.md)：**notes/ 的精簡版**，每份不超過 5000 字；README 尾巴有「今天要使用者拍板的題目總表」，先看這裡。
- [notes/2026-09-22-decisions.md](notes/2026-09-22-decisions.md)：**23 題的拍板紀錄**（2026-09-22），proto5.1 第 4 段與之後的回流都照這份。
- ~~backlog/~~：2026-09-24 agent 線定稿後六個檔逐一判掉、資料夾拿掉，見 [backlog-cleanup](notes/2026-09-24-backlog-cleanup.md)。
- [notes/2026-09-22-backflow.md](notes/2026-09-22-backflow.md)：**規範回流紀錄**：哪些從 proto5.1 搬回來、跟舊版差在哪、程式還差什麼。

## 還沒定的

由使用者口述、陸續補進來；我不代替他想（[AGENTS 鐵律 5](../AGENTS.md)）。
