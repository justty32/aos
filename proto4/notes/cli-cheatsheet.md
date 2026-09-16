# proto2 ～ proto4-7 指令怎麼用（大白話版）

← [索引](2026-09-08-ideas.md)｜討論脈絡見 [§25](24-agent.md)

整理自各 proto 的 README／docs 與 CLI 原始碼（argparse／usage 字串），2026-09-14。

先講整體：這一串 proto 都在做同一件事——**「讓一堆資料夾輪流被叫醒做事」**。差別只在「怎麼叫醒」跟「資料夾裡放什麼」。

- proto2：資料夾裡放一句 shell，一個資料夾配一個一直轉的迴圈。
- proto3～4：拿 Janet 試「資料夾＝程式」的點子，只在記憶體裡玩。
- proto4-1、4-2：用 Python 再做一次，越做越像作業系統。
- **proto4-3 是現在真的在用的**：拆成「跑一次」「一直跑」「管一堆」「排程」四種小工具。
- proto4-4～4-7：站在 4-3 上面蓋的東西——逐步執行的程式、LLM、agent。

---

## proto2 — 最早的 Python 版

### 先設三個環境變數

```sh
export PATH="$PWD/proto2:$PATH"               # 讓 aos-xxx 找得到
export AOS_DAEMON_DIR=~/.aosd                 # 時鐘總管的家（放 repo 外面）
export AOS_LLM_DIR=$PWD/proto2/examples/llm   # 有設的話 aos-llm 就不用每次打 --dir
```

### 一個一個講

**`aos-exec <路徑>`** — 跑一次就走。
給檔案就直接執行那個檔；給資料夾就把 `資料夾/.aos/inst` 那一句 shell 拿去跑。

**`aos-loop [資料夾] [--steps 幾次] [--interval 幾秒] [--stop-when-empty] [--keep-inst]`** — 一直跑。
每一圈：讀 `.aos/inst`、清空它、拿去跑。程式想下一圈再被叫，就自己把新內容寫回 `.aos/inst`。
- `--steps 5`：跑 5 圈就停（不給＝跑到天荒地老）
- `--interval 2`：每圈睡 2 秒（預設 1）
- `--stop-when-empty`：inst 是空的就收工
- `--keep-inst`：不要清空 inst（daemon 就是用這個模式）

**`aos-agent exec [世界資料夾] [--home 子資料夾]`** — 讓一個 agent 走一步。
agent 是一台狀態機，每叫一次走一格：閒著→問模型→等模型→做事→再看信箱。人不用自己叫這個，時鐘會叫。

**`aos-user …`** — 人跟 agent 講話的工具。
| 你想做什麼 | 打什麼 |
|---|---|
| 從模板開一個新 agent | `aos-user new /tmp/bob --template coder --engine deepseek-flash` |
| 看有哪些模板／工具包 | `aos-user templates`、`aos-user packs` |
| 跟它說一句話 | `aos-user say /tmp/bob "幫我看看資料夾"`（不給文字就從 stdin 讀） |
| 等它回話 | `aos-user listen /tmp/bob`（`--new` 只看新的、`--once` 印完就走） |
| 像聊天室一樣對談 | `aos-user talk /tmp/bob`（打 `/quit` 離開；**要另開一個終端機跑時鐘它才會動**） |
| 看它現在怎樣 | `aos-user status /tmp/bob` |
| 幫它生個小孩 agent | `aos-user spawn /tmp/bob 小名 "人格描述" [--clock shared\|own]` |
| 開一整隊工作室 | `aos-user team new /tmp/studio --preset studio` |
| 看整隊狀況 | `team status`、`team why`（誰卡在哪）、`team tail 成員`（最近幾輪講了什麼）、`team budget`（預算，`--add` 追加）、`team stop` |
| 下訂單給工作室 | `aos-user order /tmp/studio "任務" --budget '{"tokens":200000}' --accept "驗收條件"` |

**`aos-llm …`** — LLM 資料夾的派工員。
LLM 不是誰的功能，是另一個資料夾：誰要問模型就丟一個 JSON 進它的 `requests/`，過幾格答案出現在 `results/`。
- `aos-llm exec [資料夾]`：走一格（收帳、看誰打完了、派新的出去）。時鐘會叫，人不用。
- `aos-llm ls`：看誰在跑、誰在排隊。
- `aos-llm usage [日期] [--by model|requester]`：看今天花了多少 token。
- （`aos-llm worker` 是它自己開的背景進程，別手動叫。）

**`aos-mem exec [資料夾]`** — SQLite 記憶資料夾走一格。跟 aos-llm 同一個套路。

**`aos-daemon-kernel start|stop|restart|ls [家]`** — 時鐘總管。
每個資料夾都自己開一個 `aos-loop` 很快就開不完，所以有一個常駐進程幫你開。
- `start`：背景開起來（會等第一格跑完才說「好了」）
- `stop`：把總管跟它開的時鐘一起收掉
- `ls`：看現在有哪些時鐘在轉（`--json` 出 JSON）
- `tick`／`run`／`resume`：測試用的——前景推一格、前景一直跑、把上次的時鐘接回來

**`aos-daemon register|unregister|pause|continue <資料夾>`** — 跟總管要一個時鐘。
- `register`：幫這個資料夾開一個時鐘（＝一個 `aos-loop --keep-inst`）
- `unregister`：關掉
- `pause`／`continue`：真的用 SIGSTOP 凍住／SIGCONT 放開
- `--config x.json`：幾秒一格、用誰的身份跑；`--env K=V` 塞環境變數；`--no-wait` 丟了就走不等結果

**`aos-mcp`** — 把上面這些包成一台 MCP server，給 Claude／Codex 之類當工具用。
**`aos-mcp-tools <工具清單.json>`** — 一台「只記錄你叫了什麼、不真的做」的假 MCP server，給 `claude-cli`／`codex-cli` 引擎用的。

### 從頭玩一次

```sh
aos-user new /tmp/bob --template coder      # 開一個 agent
aos-daemon-kernel start                     # 時鐘總管起來
aos-daemon register proto2/examples/llm     # LLM 資料夾要一個時鐘
aos-daemon register /tmp/bob                # agent 也要一個
aos-user talk /tmp/bob                      # 開始聊
aos-daemon pause /tmp/bob                   # 凍住它；continue 放開
aos-daemon-kernel stop                      # 玩完全收
```

不想開總管？一個終端機開一個 `aos-loop 資料夾 --keep-inst` 效果一樣。

---

## proto3、3-1、3-2 — Janet 實驗（不存磁碟、沒有真的 LLM）

只有兩個動作：

```sh
cd proto3      # 或 proto3-1、proto3-2
janet src/main.janet 8          # 同步走 8 格然後印出來看
janet src/main.janet async 5    # 每個時鐘各自跑，5 秒後收
jpm test                        # 跑測試
```

---

## proto4 — Janet，資料夾裡放的 inst 是 Janet 程式

```sh
cd proto4
jpm test
# 一次性時鐘：把幾個資料夾丟進去輪流跑
janet src/main.janet test/fx/k/a x=test/fx/k/b:2 --steps 4     # 資料夾寫法 [名字=]路徑[:每幾格跑一次]
```

也有一個常駐總管（家用 `--home` 或 `AOS_DAEMON_DIR`）：

```sh
janet src/aos-daemon.janet start                    # 背景開
janet src/aos-daemon.janet register 資料夾 名字      # 登記
janet src/aos-daemon.janet ls                       # 看
janet src/aos-daemon.janet pause 名字 / resume 名字  # 暫停／繼續
janet src/aos-daemon.janet eval '(steps)'           # 直接丟一段 Janet 給它算
janet src/aos-daemon.janet stop                     # 收工
```

---

## proto4-1 — Python，「總管自己 cd 進資料夾跑 `./.aos/inst`」

```sh
cd proto4-1
python3 aos_kernel.py 資料夾1 名字=資料夾2:3 --steps 10 --interval 1   # 一次性輪流跑

export AOS_DAEMON_DIR=~/.aosd
python3 aos_daemon.py start                     # 總管起來
python3 aos_daemon.py register 資料夾 名字 間隔   # 登記
python3 aos_daemon.py ls
python3 aos_daemon.py pause 名字 / resume 名字 / unregister 名字
python3 aos_daemon.py req '{"op":"ls"}'         # 直接丟 JSON 請求
python3 aos_daemon.py stop
```

怎麼跑那個 inst 看資料夾裡的 `.aos/config.json`（要不要餵 stdin、輸出寫哪、逾時幾秒、退出碼幾算錯）。

---

## proto4-2 — **已作廢**，留著當參考

inst 改成一份 JSON（`inst.json`），「一直跑」的東西叫 cpu。

```sh
cd proto4-2
export AOS_HOME=~/.aos-home
python3 aos.py start                           # 總管＋第一顆 cpu（跑 kernel）
python3 aos.py register /路徑 1 60             # 每 1 秒跑一次、最多跑 60 秒
python3 aos.py ls / unregister /路徑 / stop
python3 aos_cpu.py 資料夾 --interval 1 --max-runs 3   # 不開總管，單獨跑一顆 cpu
```

---

## proto4-3 — **現在用的這版**（Python）

想成一台電腦：
- **aos-exec**＝執行一條指令（跑一次）
- **aos-run**＝一顆 cpu（同一條指令反覆跑）
- **aos-daemon**＝主機板（插拔 cpu 的地方）
- **aos-kernel**＝作業系統（決定哪個程式上哪顆 cpu）

先設：

```sh
export PATH="/abs/proto4-3:$PATH"
export AOS_DAEMON_HOME=~/.aos-daemon    # 主機板的家，三支工具都靠這個找
```

### aos-exec — 跑一次

```sh
aos-exec /路徑/資料夾              # 跑 資料夾/.aos/inst.json
aos-exec /路徑/inst.json          # 直接指一份 inst.json
aos-exec /路徑/script.sh -- a b   # 普通檔案：直接執行，-- 後面是參數
aos-exec … --stderr -             # 看不到錯誤？加這個，錯誤印到畫面
aos-exec … --timeout-ms 3000      # 超過 3 秒就砍
```

`inst.json` 長這樣，只有 `argv` 必填，多寫不認識的欄位會被拒絕：

```json
{"argv":["sh","-c","echo hi"], "cwd":"sub", "stdin":"in.txt", "stdout":"out.txt", "stderr":"err.txt", "exit":"code.txt", "envs":{"K":"v"}}
```

退出碼看誰的：子程式的原樣傳回；**125 代表 aos-exec 自己壞了（那次根本沒跑）**；2 是你打錯用法。

### aos-run — 一直跑

```sh
aos-run /路徑/資料夾 --interval-ms 5000     # 每 5 秒跑一次，跑到你 Ctrl-C
aos-run … --max-runs 10                    # 跑 10 次就停
aos-run … --time-limit-ms 60000            # 總共跑 1 分鐘就停
aos-run … --stop-exit 100                  # 某次退出碼是 100 就停
aos-run … --stop-on-error                  # aos-exec 自己壞掉就停（預設壞了也照跑）
aos-run … --from-start                     # 間隔從「上次開始」算，不是「上次結束」
```

按一次 Ctrl-C：跑完手上這次再退；按第二次：直接砍掉。

### aos-daemon ＋ aos-daemon-ctl — 主機板跟遙控器

```sh
setsid -f aos-daemon                                   # 主機板上電（放背景）
aos-daemon-ctl add /路徑/inst.json --interval-ms 2000  # 插一顆 cpu，後面的旗標原樣給 aos-run
aos-daemon-ctl ls                                      # 看有哪些 cpu
aos-daemon-ctl pause /路徑/inst.json                   # 凍住（等它睡著才凍，不會腰斬正在跑的）
aos-daemon-ctl resume /路徑/inst.json                  # 放開
aos-daemon-ctl restart /路徑/inst.json --interval-ms 500   # 換旗標重開
aos-daemon-ctl rm /路徑/inst.json                      # 拔掉
aos-daemon-ctl stop                                    # 主機板關機
```

注意：`add` 只收 `.json` 檔的路徑（檔案還沒出現也可以先插，出現了就自然跑起來）。daemon 掛了 aos 不管、不會自動重開——它是硬體。

### aos-kernel — 作業系統

```sh
aos-kernel-init /tmp/K --ncpu 2              # 灌一次系統：2 顆 cpu（要掛 module 就這時 --module）
aos-kernel-boot /tmp/K                       # 開機：把 kernel 放上主機板，之後它自己每回合跑一次
aos-kernel add /tmp/K /abs/my-proc.json      # 排一個程式進佇列（會幫你檢查、補絕對路徑、配名字）
aos-kernel ls /tmp/K                         # 看哪顆 cpu 上是誰、誰在排隊
aos-kernel rm /tmp/K my-proc                 # 拿掉
aos-daemon-ctl stop                          # 關機
```

init 可調的：`--interval-ms`（cpu 幾毫秒跑一次）、`--quantum`（一個程式最多霸佔 cpu 幾次就換人）、`--done-exit`（程式回這個碼＝做完，預設 100）、`--wait-exit`（回這個碼＝在等，預設 101）、`--bad-after`（連續失敗幾次就丟進 bad，預設 10）。

**程式跟 kernel 的約定：回 100＝我做完了、回 101＝我在等東西先讓位。**

---

## proto4-4 — 逐步 Janet：一次只跑程式裡的一個 form

```sh
export PATH="$HOME/.local/bin:$PATH"      # 要找得到 janet
/abs/proto4-4/aos-step prog.janet         # 跑下一個 form；全跑完了回 100
/abs/proto4-4/aos-step prog.janet --status   # 看跑到第幾個了
/abs/proto4-4/aos-step prog.janet --reset    # 從頭來
```

要放上 kernel：寫一份 inst.json `{"argv":["/abs/proto4-4/aos-step","prog.janet"],"cwd":"/abs/資料夾"}` 然後 `aos-kernel add`。

---

## proto4-5 — 叫 LLM

### 直接問一次（同步、會等）

```sh
aos-llm models endpoint.json                     # 先看這台服務有哪些模型
aos-llm call endpoint.json request.json result.json   # 問一次，答案寫進 result.json
printf '{"messages":[{"role":"user","content":"hi"}]}' | aos-llm call endpoint.json - -   # stdin 進、stdout 出
```

endpoint.json：`{"name":"local","kind":"openai","base_url":"http://localhost:1234/v1","model":"…"}`。有很多台就寫 `endpoints.json`、用 `endpoints.json#名字` 挑。

### 交給 kernel 排隊（不等）

```sh
aos-kernel-init K --ncpu 2 --module /abs/proto4-5/llm_cpu_module.py   # 灌系統時掛上 LLM 排程
aos-kernel-boot K
$EDITOR K/llm/endpoints.json                       # 把 model 換成 aos-llm models 看到的名字

aos-kernel llm K request.json --name hello --wait 60   # 丟單，最多等 60 秒印答案
aos-kernel llm K request.json --name hello             # 丟了就走，之後看 K/llm/results/hello.json
aos-kernel llm ls K                                    # 看排隊／跑中／做完
aos-kernel llm rm K hello                              # 撤單
```

也可以不掛 kernel、自己開一個排程家：`llm-cpu init 家`、`llm-cpu submit 家 req.json --name x`、`llm-cpu tick 家`、`llm-cpu ls 家`。

---

## proto4-6 — 逐步 JSON／Python／Lua

跟 proto4-4 同一個點子，換三種語言。程式被切成一格一格，每叫一次跑一格：

```sh
aos-step-json job.json        # job.json 是陣列，每格一份 inst.json
aos-step-py   job.py          # job.py 裡每個公開的 def xxx(state) 是一格
aos-step-lua  job.lua         # job.lua 最後 return {{name=…, fn=…}, …}
… --status                    # 看跑到哪
… --reset                     # 從頭來
… --stderr -                  # 格裡叫的子程式錯誤印到畫面
```

回 0＝這格做完、100＝全部做完、101＝在等某個檔出現、1＝這格失敗（不推進、下次重試）、2＝程式形狀不對。

---

## proto4-7 — 簡單的 agent

```sh
aos-user /tmp/bob new --name bob --system "你是簡潔的助手" --K /abs/K   # 建一個 agent
aos-kernel add /abs/K /tmp/bob/inst.json --name bob                     # 放上 kernel 讓它動

aos-user /tmp/bob say "看看資料夾裡有什麼"    # 寫信給它
aos-user /tmp/bob listen --once              # 看它回了什麼
aos-user /tmp/bob talk                       # 聊天模式
aos-user /tmp/bob status                     # 一行看它在幹嘛

aos-agent /tmp/bob             # 手動讓它走一格（平常 kernel 幫你叫）
aos-agent /tmp/bob --status
aos-agent /tmp/bob --reset     # 清狀態，不清記憶
```

agent 一格只做一件事：收信→問模型→等模型→做事／回信。等模型時回 101 把 cpu 讓出去。工具是 `tools/名字/tool.json`＋可執行的 `run`。

---

## 各版測試怎麼跑

| 哪版 | 指令 |
|---|---|
| proto2 | `bash proto2/test.sh` |
| proto3、3-1、3-2、proto4 | `cd 那個資料夾 && jpm test` |
| proto4-1、4-2、4-3、4-5、4-6、4-7 | `cd 那個資料夾 && python3 -m unittest discover -s test` |
| proto4-4 | `cd proto4-4 && for t in aos step cpu; do janet test/$t.janet; done` |

## 環境變數一覽

| 變數 | 哪版用 | 幹嘛 |
|---|---|---|
| `AOS_DAEMON_DIR` | proto2、proto4、proto4-1 | 時鐘總管的家 |
| `AOS_LLM_DIR` | proto2 | LLM 資料夾在哪 |
| `AOS_HOME` | proto4-2（作廢） | 家 |
| `AOS_DAEMON_HOME` | proto4-3 起 | 主機板的家（預設 `~/.aos-daemon`） |
| `AOS_EXEC`／`AOS_LLM`／`AOS_KERNEL` | proto4-4、4-6 | 逐步程式裡 `aos.call`／`aos.llm` 要去哪找工具 |
