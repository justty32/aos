# proto5

← [INDEX](../wf/INDEX.md)｜前一輪 [proto4-3](../proto4-3/README.md)（作業系統層）、[proto4-7](../proto4-7/README.md)（簡單 agent）｜使用者的方向草稿在 [`thinking/`](../thinking/)｜**上手看 [教程](tutorials/README.md)**

proto5 從**把規範寫下來**開始：proto4-x 一路長出來的格式與約定，先一份一份寫成文件，
程式再照文件走。文件裡跟現行程式碼對不上的地方，以程式碼為準、回來改文件。

## 這是什麼

一套用資料夾跑 LLM agent 的小作業系統，十一支 Python 指令（`proto5/cli/`，Python 3.12 以上），模型走任何 OpenAI 相容端點。

```text
daemon（家 D）          所有 cpu 的爸爸，按池管：池 P 要 N 顆就補到 N、死了重拉（越死越等久）、多了就收；
                        也替 kernel 每秒開一格 aos-kernel tick（有新單就馬上開）——這就是 kernel 的排程
 ├─ default 池 N 顆     default/0、default/1…：跑一般工作、agent 的每一格、agent 的工具
 └─ llm 池     N 顆     跑 aos-llm call 問模型；池的環境裡 AOS_LLM_CONFIG 指到 llm.json
kernel（家 K）          不是常駐程式：池表 K/info.json＋帳本 K/ledger.sqlite＋一格接一格的 tick，
                        替登記的工作挑空 cpu、收結果、決定要不要再跑；照池表跟 daemon 講每池要幾顆
agent（一個資料夾）      人格、記憶、工具、進度；登記成 kernel 的一份反覆工作 agent-<資料夾名>
```

cpu 就是「一個資料夾＋一個主人程式」（`aos-cpu`）：往它的 `requests/` 放一張單，它照單跑一次程式、結果寫進 `responses/`。
加減 cpu 只是改池的數字（`aos-kernel cpu add --pool default --count 4`），下一格生效、不用重開。
agent 每一格只做一小步（收輸入→問模型→跑工具→再問）就退出，問模型和跑工具都是交給 kernel 的一次性工作。

## 五分鐘看到 agent 回話

從 repo 根目錄貼進 bash／zsh（端點換成你的；下面是 LiteLLM）。這段是教程 01＋03 的濃縮，要從頭學就先 `rm -rf $HOME/aos-try` 再照[教程](tutorials/README.md)做。

```sh
W=$HOME/aos-try; mkdir -p $W
export PATH=$PWD/proto5/cli:$PATH AOS_DAEMON_HOME=$W/D AOS_KERNEL_HOME=$W/K
cat > $W/llm.json <<'EOF'
{"_metainfo": {"_type": "llm_config", "_version": 1},
 "models": {"default": {"endpoint": "http://localhost:4000/v1", "model": "deepseek-chat"}}}
EOF
cat > $W/kernel.json <<EOF
{"pools": {"default": {"count": 2}, "llm": {"count": 1, "envs": {"AOS_LLM_CONFIG": "$W/llm.json"}}}}
EOF
aos-kernel init --config $W/kernel.json && aos-kernel check --probe && aos up
aos-agent init --target $W/bob && aos-agent start --target $W/bob
aos-agent say "現在幾點？請用工具查。" --target $W/bob --wait
```

最後一行約 10～20 秒印出回話（`check` 那行的 `warn daemon` 是還沒開機，不用管）。停機：`aos-agent stop --target $W/bob; aos down`。
隔天重開：新終端 `export` 同樣三個變數之後 `aos up` 就好（[教程 01 第 7 步](tutorials/01-daemon-kernel.md#7-每天重開機)）。

## 指令一覽

家一律用 `--target DIR` 指；省略時 daemon 找 `AOS_DAEMON_HOME`、kernel 找 `AOS_KERNEL_HOME`，再沒有（agent 則一律）就用目前資料夾。每個指令 `-h` 印用法。

| 指令 | 一句話 | 教程 |
|---|---|---|
| `aos up` | 開機：daemon 沒在跑就開（放背景），再開 kernel，等它走完第一格，最後印一行 `health`（不是 `ok` 就退 1）；每天開機也是它，開著再跑一次也不壞 | [01](tutorials/01-daemon-kernel.md) |
| `aos down [--keep-daemon]` | 關機：先停 kernel（每池縮到 0、等 cpu 都退出），daemon 沒別的 kernel 要用就一起停 | [01](tutorials/01-daemon-kernel.md) |
| `aos-daemon boot`／`halt` | debug 用（平常 `aos up`／`down` 會叫它）：開 daemon（前景程式）／停 daemon 並等它退出 | [01](tutorials/01-daemon-kernel.md) |
| `aos-daemon ls [--pool P]` | 看 daemon 這邊每池活幾顆、忙幾顆、重拉中幾顆；`--pool` 一顆一行（偷看檔案，不放單） | [05](tutorials/05-many-agents.md) |
| `aos-daemon scale --pool P --count N [--force]` | 直接改 daemon 那邊池的顆數；kernel 的池要 `--force`（只給救急，平常用 `aos-kernel cpu add／rm`） | [05](tutorials/05-many-agents.md) |
| `aos-daemon kill --pool P NAME…｜--all` | 把某幾顆砍掉重來（宣告不變，砍完再拉）；取消跑到一半的單子只能靠它 | [07](tutorials/07-cli-agents.md) |
| `aos-kernel init [--config FILE]` | 照一份 JSON 建 kernel 的家：kernel 參數＋池表（每池幾顆、環境）；不給＝一個池都沒有；池名 `kernel` 是保留名 | [01](tutorials/01-daemon-kernel.md)、[06](tutorials/06-appendix-manual-home.md) |
| `aos-kernel check [--probe]` | 開機前檢查 kernel 家、daemon、PATH、llm 設定；`--probe` 真的打一次模型端點 | [01](tutorials/01-daemon-kernel.md) |
| `aos-kernel boot`／`halt` | debug 用（平常 `aos up`／`down` 會叫它）：寫帳本、請 daemon 開始替它走格／停排程、每池縮到 0 並等 cpu 都退出 | [01](tutorials/01-daemon-kernel.md) |
| `aos-kernel cpu add --pool P [--count N] [--env K=V]` | 加池或加顆數；下一格生效，不用重開 | [05](tutorials/05-many-agents.md) |
| `aos-kernel cpu rm P/<i>`／`cpu rm --pool P --count N` | 永久退休某一號／收最大的 N 號；手上工作做完才收 | [05](tutorials/05-many-agents.md) |
| `aos-kernel cpu ls [--pool P] [--json]` | 一池一行：要幾顆、講好幾顆、忙／閒／收掉中、daemon 那邊的數字；`--pool` 一顆一行 | [05](tutorials/05-many-agents.md) |
| `aos-kernel ls [--pool P] [--procs] [-v] [--json]` | 全局：第一行 `health`，再來每池一行、行程（預設只列出事的，`--procs` 全列）、佇列；`--pool` 只看一池、`-v` 印完整路徑、`--json` 給程式讀 | [01](tutorials/01-daemon-kernel.md)、[05](tutorials/05-many-agents.md) |
| `aos-kernel proc NAME [--json]` | 只看一個行程：帳本裡那筆、在哪顆 cpu 上跑；沒有這個行程退 1（給程式讀帳本用） | [spec](spec/kernel/cli.md) |
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
| `aos-agent tools new NAME`／`test NAME\|DIR`／`wrap-py FILE.py` | 造工具（不需要 agent 家）：生工具包骨架／照工具檔的描述自動跑正例、型別錯、缺參數（預設關牢）／把有型別註解的 Python 函式包成工具包、印拒收表；wrap-py 加 `--describe-with-llm` 請模型替沒 docstring 的函式寫描述（只寫提案檔），人看過再 `--describe 提案檔` 產包 | [spec/aos-agent/tools-dev.md](spec/aos-agent/tools-dev.md)、[tools-llm.md](spec/aos-agent/tools-llm.md) |
| `aos-agent tools wrap-cli CMD [--help-file F] [--describe-with-llm｜--spec F]` | 把一支命令列指令包成工具包：有 argparse 的 `.py` 靜態讀，其他解 `--help` 文字；解不出來的行列出來、不猜。`--describe-with-llm` 請模型整理參數表（只寫提案檔），人看過再 `--spec` 產包 | [spec/aos-agent/tools-wrapcli.md](spec/aos-agent/tools-wrapcli.md) |
| `aos-agent access ls/set/rm/cwd/net [--target 家]` | 看／改工具被關進的牢（`access.json`）：掛哪些資料夾、起點、能不能連網 | [04b](tutorials/04b-access-and-tool-admin.md) |
| `aos-agent context [--by-round] [--json]` | 送給模型的東西多大（人格、記憶、工具，token 粗估＋上一次端點回報的真數字）；`talk` 的 `/context` 同一份 | [spec/aos-agent/cli-memory.md](spec/aos-agent/cli-memory.md) |
| `aos-agent compact [--keep-rounds N] [--max-tokens X] [--dry-run] [--prune-archive] [--summarize [--model A]]` | 機械壓縮記憶，原文存 `prompts/archive/`；`info.json` 的 `compact` 開自動（預設開、上限 32000）；`--summarize` 讓模型把封存摘要濃縮成幾句（只有人跑時；檢查不過退回機械版） | [spec/aos-agent/cli-memory.md](spec/aos-agent/cli-memory.md) |
| `aos-agent events [--last N] [--usage]` | 事件紀錄（每批起訖、成敗、毫秒）與 token 用量；滿了自動輪換 | [spec/aos-agent/cli-memory.md](spec/aos-agent/cli-memory.md) |
| `aos-agent history --archive [SHA] [--grep 字]` | 看壓縮前封存的原文 | [spec/aos-agent/cli-memory.md](spec/aos-agent/cli-memory.md) |
| `aos-agent notes ls／show KEY` | 看 `note` 工具寫的長期筆記 | [spec/aos-agent/cli-memory.md](spec/aos-agent/cli-memory.md) |
| `aos-agent init --template NAME` | 照團隊成員模板生家（人格、工具包、`access.json` 一起裝） | [spec/aos-agent/cli-memory.md](spec/aos-agent/cli-memory.md) |
| `aos-json get／set／del／append／merge` | 人用的 JSON Pointer 改檔；`--expect-sha` 防互蓋、`--check-directives` 先過指示詞才寫 | [spec/aos-agent/tools-files.md](spec/aos-agent/tools-files.md) |
| `aos-directives ls／show／set／add／rm／export／import／versions／revert／resolve／check` | 人格（system prompt）按標題分節編輯、存版本可還原；另可解／驗一份 aos JSON 檔的指示詞 | [spec/aos-agent/tools-files.md](spec/aos-agent/tools-files.md) |
| `aos-team init [--config FILE]／start／stop／ls／rm` | 照名冊建團隊資料夾與每個成員的家（模板）、替成員向 kernel 登記／撤銷、列隊（health、手上的單、最後一封信）、拆隊 | [spec/team/](spec/team/README.md) |
| `aos-team ask "一句話"`／`route test [--file F]`／`route save F`／`route try "一句話"` | 門房：整句句型比對，命中就不叫模型直接做；沒命中、命中兩條或有否定詞就落穿給領隊；`route try` 只看會怎麼判、什麼都不做 | [spec/team/route.md](spec/team/route.md) |
| `aos-team task ls／show／cancel／reassign` | 人看任務單；取消、改派都是寄申請給郵差 | [spec/team/tasks.md](spec/team/tasks.md) |
| `aos-team wait ls`／`answer Q "…"` | 人看等他回答的問題、回答一題（寄申請給郵差） | [spec/team/ask.md](spec/team/ask.md) |
| `aos-team mail [--task t-0001] [--follow]` | 一封信一行，看團隊的信件往來；等你回答的題目也一題一行（`ASK q-0001`，答完先顯示答案）；`--task` 連落穿給領隊的那封一起列 | [spec/team/mail.md](spec/team/mail.md) |
| `aos-team post`（kernel 反覆叫）／`beat`（kernel 反覆叫，同上） | 郵差兼書記走一輪：投信、收驗收結果、看停滯、同步 SESSION-LOG／WAIT_USER；心跳走一輪：照 `routines.json` 算誰到期、以開單派出 | [spec/team/post.md](spec/team/post.md)、[beat.md](spec/team/beat.md) |
| `aos-team verify t-0001 [--again]` | 照任務單 `done_when` 跑固定檢查器，回過／不過／檢查器壞三種；`--again` 給檢查器壞、人修好之後重交。`cmd_ok`（跑 `team.json` 白名單裡的專案指令）與 wf-lint 關在牢裡、專案唯讀 | [spec/team/verify.md](spec/team/verify.md)、[wall.md](spec/team/wall.md) |
| `aos-team routine ls／add／rm` | 心跳的例行事務：新增、看、刪一條到期就派工的例行 | [spec/team/beat.md](spec/team/beat.md) |
| `aos-team spawn ls`／`approve Q` | 領隊申請生新成員（`spawn_member`）：預設開、預設不用人批（名冊可各自改成要批）；`ls` 看等你批的、`approve` 批准生 | [spec/team/spawn.md](spec/team/spawn.md) |
| `aos-team tool ls`／`approve Q` | 工人寫的工具草稿（`tool_draft`）：郵差先在牢裡跑過例子，過了才開題，這條一定要人批 | [spec/team/toolsmith.md](spec/team/toolsmith.md) |
| `aos-team crystal [--min N] [--out F] [--suggest-with-llm]` | 固化建議：從 `route.log` 找常落穿給領隊、領隊每次都開同一種單的句型，產候選門房規則（只寫提案檔；人 `route test --file F` → `route save F` 才生效） | [spec/team/crystal.md](spec/team/crystal.md) |
| `company.py new／up／down／status／order／mail／answer`（`examples/company/`） | 一間公司＝幾支團隊＋一家一個 kernel＋機械總機；`status` 印「正式 N/10、cpu N/20、llm cpu N/5」 | [spec/team/company.md](spec/team/company.md) |
| `market.py open／score／rank／grant／bankrupt／close／pool／slots／merge`（`examples/company/`） | 幾家公司競爭：排名撥額度、總池、倒閉回收、合併 | [spec/team/market.md](spec/team/market.md) |
| `aos-team score` | 把六軸表（`axes.md` 團隊欄）能自動量的部分讀紀錄填好，只讀、不叫模型、不寫檔 | [spec/team/score.md](spec/team/score.md) |
| `aos-team hr ls／set／trial／trials／salary／cap` | HR：薪資表（每個位子最低用得起哪顆模型，有試用證據才填）、換模型試用＋調薪、正式員工／臨時工、名額（新創：正式 10 人、cpu 20／llm cpu 5；擴張後 100／200／20） | [spec/team/hr.md](spec/team/hr.md) |
| `aos-kernel tick`、`aos-agent tick` | 走一格；kernel 自己會叫，人不用打 | — |
| `aos-cpu` | cpu 的主人程式：顧一個 cpu 家、照單跑程式；daemon 拉起來的每個孩子就是它，平常不用自己叫 | [01](tutorials/01-daemon-kernel.md) |
| `aos-llm call`、`aos-exec`、`aos-jail` | 問一次模型／照 inst 跑一次程式／把一支程式關進沙盒跑；都是別的指令在叫，`aos-jail` 是 `aos-agent` 送件時自動用，平常不用自己叫 | — |

## 去哪讀

- **[tutorials/](tutorials/README.md)**：八篇照抄就能跑的教程（另有 04b、06 兩篇附錄），從開機到管一堆 agent；第 07 篇讓 Claude Code／Codex 當 cpu 跑單子，第 08 篇用名冊生一支小團隊。
- **[spec/](spec/README.md)**：每個指令、每種檔案的規範（下表）；給使用者的精簡版是 [agent 家](spec/agent/essentials.md)、[aos-agent 指令](spec/aos-agent/essentials.md) 兩份「使用者只需要懂的」。
- **[lib/](lib/README.md)**：程式模組與測試（下面「程式」）。
- **[notes/](notes/README.md)**：任務書、審查、試玩紀錄（下面「筆記」）。
- **[examples/](examples/)**：真的拿來用的樣板——[arknights](examples/arknights/README.md)（補人物隊）、[commons](examples/commons/README.md)（圖書館員隊）、[company](examples/company/README.md)（**用 aos 團隊蓋一間公司**：部門＝團隊、董事＝human、機械總機搬跨部門的信；`company.py`、市場層 `market.py`）。
- **[playbook/](playbook/README.md)**：跨隊沉澱——經驗（`lessons.md`）、團隊組織架構（`teams/`）、工作流架構（`workflows/`）、可複用工具索引；每隊收尾都回來加一條。

## 規範

一份規範一個資料夾，入口是資料夾裡的 README（定位、已拍板的前提、各節在哪個檔）；總導航 [spec/README.md](spec/README.md)。文中「§3」這類節號照舊，到該資料夾 README 查。

| 文件 | 講什麼 | 現況 |
|---|---|---|
| [spec/directives/](spec/directives/README.md) | 指示詞機制：`$env`／`$fmt`／`$ref` 取值、`$opt`／`$val` 選項物件、先解再驗、巢狀、循環、錯誤代號。任何 aos 的 JSON 檔都能用；哪個位置認得哪些選項名由宿主規範定 | 2026-09-21 定稿；實作 [`lib/aos_directives.py`](lib/aos_directives.py) |
| [spec/inst-posix/](spec/inst-posix/README.md) | inst.json 的 `posix` 呼叫格式第 1 版：七個欄位、各位置的 `$opt` 選項（append／mkdir／inherit／merge／clear）、錯誤代號、執行語意，加上 `_metainfo`（`_type`／`_version`；沒寫＝posix v1）、頂層未知 key 忽略 | 2026-09-21 定稿；實作 [`lib/aos_inst.py`](lib/aos_inst.py)（讀／驗）＋ [`lib/aos_exec.py`](lib/aos_exec.py)（執行）。proto4-3 是凍結的舊版參考 |
| [spec/aos-exec/](spec/aos-exec/README.md) | aos-exec 的**命令列**：三種目標（普通檔／`.json`／資料夾）、`--dir-target`／`--timeout-ms`／`--stderr`／`--`、退出碼 2／125／原樣、125 與 2 時 stderr 印什麼。行為照 inst-posix.md 第 6 節 | 命令列走法照 proto4-3 現況整理，使用者還沒逐條拍板 |
| [spec/cpu/](spec/cpu/README.md) | cpu 範式（一個家一個主人：`info`／`state`／`requests`／`responses`、JSON-RPC 信封、ack）與 exec cpu：逐件照 aos-exec 跑一次、回音寫 `responses/` | 2026-09-23 定稿；實作 [`lib/aos_home.py`](lib/aos_home.py)＋[`lib/aos_client.py`](lib/aos_client.py)＋[`lib/aos_exec_cpu.py`](lib/aos_exec_cpu.py)（`aos-cpu`） |
| [spec/kernel/](spec/kernel/README.md) | kernel：替登記的工作挑空 cpu 派下去、收結果、決定要不要再跑；每次只跑一格 `aos-kernel tick`（09-24 one-boot 起由 daemon 開，帳本 `K/ledger.sqlite`），格接格排程。cpu 按池管（`info.json` 第 2 版池表，09-24 由 proto5-2 納入） | 2026-09-23 定稿；實作 [`lib/aos_kernel.py`](lib/aos_kernel.py)（`aos-kernel`；09-24 拆成 `aos_kernel_*.py` 幾支） |
| [spec/daemon/](spec/daemon/README.md) | daemon：所有 cpu 的父行程，按池宣告管孩子的啟動、重拉（退避）、收掉；09-24 one-boot 起也替 kernel 定時開 tick；家也照 cpu 範式長；`aos up`／`aos down` 見 [up.md](spec/daemon/up.md) | 2026-09-23 定稿；實作 [`lib/aos_daemon.py`](lib/aos_daemon.py)（`aos-daemon`） |
| [spec/agent/](spec/agent/README.md) | 一個 agent 就是一個資料夾：info.json 記人格、記憶、工具與排程設定；state.json 記三格進度、批次與恢復紀錄；（09-24 第 4 隊補）事件紀錄 [events.md](spec/agent/events.md)、記憶壓縮 [compact.md](spec/agent/compact.md) | 2026-09-24 定稿第 2 版；實作 [`lib/aos_agent_home.py`](lib/aos_agent_home.py)＋[`lib/aos_agent_info.py`](lib/aos_agent_info.py) |
| [spec/aos-agent/](spec/aos-agent/README.md) | `aos-agent tick／start／stop [--target DIR]`：走一格／向 kernel 登記／撤銷排程；模型與工具都交 kernel `add --once`、收回音並 ack。日常的 `init`／`say`／`listen`／`status`／`pause`／`continue`／`check`／`tools add`／`talk` 在 §1（09-24 試玩 r2 補；fix-r4 改 `--target`、`listen`、`pause`、tick 鎖；advice-r1 加 `check`；tools-base 加 `tools add`（tools.md §1.8）；talk 加 `talk`（cli-talk-repl.md §1.9）；tool-era T3 補人用 JSON／人格編輯 [tools-files.md](spec/aos-agent/tools-files.md)；T4 補記憶 [cli-memory.md](spec/aos-agent/cli-memory.md)） | 2026-09-24 定稿第 2 版；實作 [`lib/aos_agent.py`](lib/aos_agent.py) 與拆分模組（見 [lib/](lib/README.md)） |
| [spec/aos-llm/](spec/aos-llm/README.md) | `aos-llm call [AGENT_DIR]`（09-24 fix-r4 由 `aos-llm-call` 改名）：讀 agent 家與 `AOS_LLM_CONFIG`、組請求、打一次 HTTP、印模型回的 message | 2026-09-24 定稿第 2 版；實作 [`lib/aos_llm_call.py`](lib/aos_llm_call.py) |
| [spec/team/](spec/team/README.md) | 一支 agent 團隊的資料夾、名冊、信、任務單與問人：三種會想的成員（領隊、工人、審查）＋四個機械員（門房、郵差兼書記、驗收員、心跳），機械員不問模型 | 2026-09-24 第 1 版；實作 [`lib/aos_team*.py`](lib/README.md)＋[`cli/aos-team`](cli/aos-team) |

## 程式

2026-09-24：cpu／daemon／kernel 與 agent 線已接上新架構；同日把 [proto5-2](../proto5-2/README.md) 的池式 daemon／kernel 納入（kernel 只說「池 P 要 N 顆」、daemon 自己補齊，`aos-kernel cpu add／rm／ls`）。`aos-llm call` 問模型一次，
`aos-agent tick／start／stop／init／say／listen／status／pause／continue` 負責走格、kernel 排程與日常操作；模型與工具都透過 kernel 交給 exec cpu 執行。
舊 llm／tool cpu 與 aos-llm-ask 已移除。審查與實作紀錄在 [rearch 筆記](notes/2026-09-23-rearch/README.md)。

| 位置 | 講什麼 | 現況 |
|---|---|---|
| [lib/](lib/README.md) | 七十支標準庫 Python 3.12 以上模組。底層 directives → inst → exec；home／client 共用家與交件；exec_cpu 執行、daemon 管孩子、kernel 排程；agent 共用讀驗、批次、輸入、結果與恢復模組；tool-era T3 補人用 aos-directives／aos-json，T1 補 aos-team 骨架，T2 補郵差／驗收／心跳，T4 補記憶（events／context／compact／notes），第二波 A 隊補造工具與 `wf_fill`，第二波 B 隊補牆接線與 `cmd_ok`，第二波 C 隊補申請類（lock／persona）與 `_pool`，第三波 W3-2 隊補「多問一次模型」的四個選項（wrap-cli、描述、compact 濃縮、crystal），第三波 W3-1 隊補領隊生成員與工人造工具（spawn／toolsmith）。逐檔 API 與測試表見 lib README | 96 個測試檔、2665 條：`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test` |
| [cli/](cli/) | 十一個薄入口：`aos`（09-24 one-boot，`aos up`／`aos down` 一條開機、一條停機）、`aos-exec`、`aos-cpu`、`aos-daemon`、`aos-kernel`、`aos-llm`（09-24 fix-r4 由 `aos-llm-call` 改名）、`aos-agent`、`aos-jail`（09-24 access-impl，aos-agent 自動用）、`aos-directives`／`aos-json`（09-24 tool-era T3，人用）、`aos-team`（09-24 tool-era T1，團隊分派） | agent 已接上 kernel；測試涵蓋崩潰窗口、真 daemon＋kernel＋exec cpu 整合與完整停機 |
| [templates/](templates/) | `aos-agent init --template` 生家用的成員模板：`lead`／`worker`／`reviewer`／`coder`，加第二波 A 隊的 `importer`（導入工人：只裝導入用得到的 10 支工具，工具表約 worker 的一半）共五個（人格、工具包、`access.json` 一定附；`notes: true` 的多掛 `/work/notes`） | 09-24 tool-era T1；`init_from_template()` 在 [`lib/aos_agent_init.py`](lib/aos_agent_init.py) |
| [templates/cli-agents/](templates/cli-agents/README.md) | Claude Code／Codex 當普通 cpu 的範本（階 0，不是程式）：另一個 kernel 家的設定、`claude -p` 與 `codex exec` 唯讀審查的單子、接著聊的分岔版 | 09-24 stage0；用法見[教程 07](tutorials/07-cli-agents.md) |
| [tools/](tools/README.md) | `aos-agent tools add` 裝的工具包，現在六包：`base`（read／write／edit／bash／grep／find／ls，仿 pi）、`files`（json_edit／md_section）、`wf`（wf_doc／wf_init／wf_fill／wf_lint／wf_residue／wf_table）、`notes`（長期筆記 `note`）、`team`（`team_say` 寄信）、`task`（`handoff`／`board`／`review_result`／`ask_human`／`compact_me`，給團隊成員用） | 09-24 tools-base；tool-era T1／T2／T3／T4 陸續補，第二波 A 隊加 wf_fill 與造工具指令（[tools-dev](spec/aos-agent/tools-dev.md)）；每支工具怎麼用、錯誤長怎樣見 [tools/README.md](tools/README.md) |

拍板過程的任務書副本在 [notes/2026-09-21-inst-rev-rules.md](notes/2026-09-21-inst-rev-rules.md)（A～L 節）。

## 筆記

- [notes/](notes/README.md)：**先看索引**——任務書副本、astra 的調查／審查報告、我的精簡總結、重架構與試玩紀錄，按日期分組。
- [notes-brief/](notes-brief/README.md)：**notes/ 的精簡版**，每份不超過 5000 字；README 尾巴有「今天要使用者拍板的題目總表」，先看這裡。
- [notes/2026-09-22-decisions.md](notes/2026-09-22-decisions.md)：**23 題的拍板紀錄**（2026-09-22），proto5.1 第 4 段與之後的回流都照這份。
- ~~backlog/~~：2026-09-24 agent 線定稿後六個檔逐一判掉、資料夾拿掉，見 [backlog-cleanup](notes/2026-09-24-backlog-cleanup.md)。
- [notes/2026-09-22-backflow.md](notes/2026-09-22-backflow.md)：**規範回流紀錄**：哪些從 proto5.1 搬回來、跟舊版差在哪、程式還差什麼。

## 還沒定的

由使用者口述、陸續補進來；我不代替他想（[AGENTS 鐵律 5](../AGENTS.md)）。
