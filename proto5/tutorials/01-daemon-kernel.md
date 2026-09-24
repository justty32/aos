← [教程索引](README.md)｜[proto5 README](../README.md)｜下一篇 [02 用 kernel 跑工作](02-kernel-jobs.md)

# 01 設定、啟動與關閉 daemon 和 kernel

**目標**：把「很久都不會變的設定」一次寫好（環境檔、模型設定 `llm.json`、kernel 設定 `kernel.json`），
用一條 `aos up` 開機、確認它健康，再用一條 `aos down` 關機；每天開機也只是 `aos up`。

**前提**：從 repo 根目錄開始；Python 3.12 以上；一個 OpenAI 相容的模型端點。下面用 LiteLLM 的
`http://localhost:4000/v1`、模型 `deepseek-chat`、不用金鑰（換別的就改 `llm.json` 的 `endpoint`、`model`，要金鑰加 `"api_key"`）。

## 1. 環境檔：放在哪、PATH 怎麼設

工作目錄 `W` 放你的家目錄底下（別放 `/tmp`：很多系統開機會清掉它，第 7 步「每天重開機」就沒東西可開了）。
把 PATH 和兩個「家」的位置寫進一個小檔，之後每開一個新終端只要 `.` 它一次。

```sh
W=$HOME/aos-try; mkdir -p $W
cat > $W/env.sh <<EOF
export PATH=$PWD/proto5/cli:\$PATH
export AOS_DAEMON_HOME=$W/D AOS_KERNEL_HOME=$W/K
W=$W
EOF
. $W/env.sh
```

`AOS_DAEMON_HOME` 是 daemon 的家、`AOS_KERNEL_HOME` 是 kernel 的家。指令（`aos`、`aos-daemon`、`aos-kernel`、`aos-agent`）
都用 `--target DIR` 指家，省略時各找自己的環境變數，再沒有就用目前資料夾。設好之後下面都不寫 `--target`。

## 2. 模型設定與池表：一次寫好

兩份檔：`llm.json` 是「代號 → 哪個端點、哪個模型」的表；`kernel.json` 是**池表**：每個池要幾顆 cpu、帶什麼環境。
cpu 不一顆顆取名字，只說「`default` 池要 2 顆、`llm` 池要 1 顆」。專門問模型的 `llm` 池用環境變數 `AOS_LLM_CONFIG` 指到 `llm.json`。

```sh
cat > $W/llm.json <<'EOF'
{"_metainfo": {"_type": "llm_config", "_version": 1},
 "models": {"default": {"endpoint": "http://localhost:4000/v1", "model": "deepseek-chat"}}}
EOF
cat > $W/kernel.json <<EOF
{"pools": {"default": {"count": 2},
           "llm": {"count": 1, "envs": {"AOS_LLM_CONFIG": "$W/llm.json"}}}}
EOF
```

- **`llm.json` 的內容隨時能改**（換 port、換模型、加代號），下一次問模型就用新的，不用重開任何東西。
- **`kernel.json` 只在第 3 步 `init` 讀一次**（抄成 `K/info.json`）。之後加減 cpu 不用改它，用 `aos-kernel cpu add／rm`（[05](05-many-agents.md)）。
- `default` 池跑一般工作和 agent 的每一格；`llm` 池跑問模型。池可以先寫 `"count": 0`，甚至不給 `--config`（一個池都沒有），之後再 `cpu add`。
- 池名 `kernel` 不能用（保留給 kernel 自己）；寫了 `init` 會拒絕。

## 3. 建 kernel 的家

```sh
aos-kernel init --config $W/kernel.json
```

你會看到：`initialized /home/you/aos-try/K`。`K/info.json` 就是你的池表，再加上幾個預設值；
`daemon` 那格自動填成 `AOS_DAEMON_HOME`（kernel 要找哪個 daemon）。

## 4. 開機前檢查

```sh
aos-kernel check --probe
```

你會看到（每行 `ok`／`warn`／`bad`）：

```text
ok   info: kernel 設定讀驗通過
ok   dirs: requests/、responses/、pools/ 都在
warn daemon: daemon 沒在跑：/home/you/aos-try/D（池 default、llm）；aos up 會開它（只開 daemon：aos-daemon boot --target /home/you/aos-try/D）
ok   path: 五支 CLI 都找得到（目前 shell 的 PATH；daemon 以開它那一刻的 PATH 為準）
ok   pools: 池：default 2、llm 1
ok   llm/llm: 模型代號：default
ok   probe/default: endpoint 通，模型清單裡有 deepseek-chat（endpoint http://localhost:4000/v1，模型 deepseek-chat）
設定檢查通過；模型連線也測過
```

`warn daemon` 是因為還沒開機，不用管：下一步的 `aos up` 會替你開 daemon。
`--probe` 真的對端點打一次；不帶它只驗設定，最後一行會寫「未測模型連線（--probe 會測）」。有 `bad` 就照那行的提示修好再往下。

## 5. 開機、看它健不健康

```sh
aos up
sleep 2
aos-kernel ls
```

`aos up` 一兩秒就回，印兩行：

```text
up K=/home/you/aos-try/K  daemon /home/you/aos-try/D（新開）  2 個池、3 顆 cpu
health ok
```

它替你開好 daemon（放背景、跟終端脫鉤，關掉終端也還在）、開好 kernel，等 kernel 走完第一格、池都跟 daemon 講好才回。
第二行 `health` 不是 `ok`（例如池出錯、daemon 或走格有問題）時 `aos up` 退 1，照那行說的修。`ls` 你會看到：

```text
health ok
kernel  running  seq 4  daemon alive  tick 1000ms
  tick 由 daemon 開：上一格 0 秒前
pool    2 個工作池：要 3 顆、忙 0、閒 3
  default  want 2  sent 2  busy 0  idle 2  draining 0   daemon default: running 2 pending 0 dead 0 failed 0
  llm      want 1  sent 1  busy 0  idle 1  draining 0   daemon llm: running 1 pending 0 dead 0 failed 0
proc    0 個
queue   -
```

**第一行 `health` 最要緊**：`ok` 就是正常；不是 `ok` 就照括號裡的指令做（多半是 `aos up`）。
下面依序是 kernel（`seq` 是走到第幾格）、每池一行、登記的工作（行程）、排隊的名單。

- `tick 由 daemon 開：上一格 0 秒前`：daemon 每秒替 kernel 走一格。這個數字一直變大（超過 10 秒）就是卡住了，`health` 也會說。
- 池那行：`want` 要幾顆（池表寫的）、`sent` kernel 已經跟 daemon 講好幾顆；`busy`／`idle` 忙的、閒的；`draining` 收掉中（做完手上工作就收）。
- `daemon default:` 後面是 daemon 那邊真的看到的：`running` 活著（有死了正在重拉的會寫成 `running 2（含 restarting 1）`，不是另外多的）、`pending` 等著拉、`dead`／`failed` 拉不起來。
- `aos up` 完馬上看，池那行可能寫 `sent 0`、尾巴寫「宣告已送出，下一格確認」：kernel 一格才跟 daemon 對一次帳，等一兩秒就齊。

`aos-kernel ls -v` 多印 `K`、`D` 的完整路徑；`--pool default` 只看那池、一顆一行；`--procs` 列出每個行程（預設只列出事的）；
`--json` 印欄位固定的 JSON，給程式讀（[ls 規範](../spec/kernel/cli-ls.md)）。

## 6. 關機

```sh
aos down
```

印兩行：`kernel …/K 剛停`（每個池都縮到 0、cpu 都退出了）、`daemon …/D 剛停`。約 3 秒。
再打一次 `aos down` 會印 `本來就停了`、`本來就沒在跑`，什麼都沒做。
想確認真的全停了：`aos-daemon ls` 第一行是 `daemon not running`。（別用 `pgrep -f aos` 驗：repo 路徑本身就有 `aos`，別的 session 的 daemon 也會被算進去；要用 pgrep 就篩自己的 `$W`：`pgrep -af "$W"`。）
有 agent 在跑的話，先 `aos-agent stop` 每一個（[03](03-first-agent.md)）；忘了也沒關係，下次開機它們還登記著。

`aos down` 之後 `aos-kernel ls` 第一行是 `health 停機中（aos up 或 …）`。

## 7. 每天重開機

家（`D`、`K`、agent 的家）都還在。新開一個終端：

```sh
. $HOME/aos-try/env.sh
aos up
```

一樣印 `up K=…  daemon …（新開）  2 個池、3 顆 cpu` 和 `health ok`，就好了。
**昨天照第 6 步關過，還是直接關電腦、登出，都一樣只要 `aos up`**。已經開著再跑一次 `aos up` 也不會壞（印「本來就在」，kernel 重開一次）。
`init` 不用再跑（再跑會被拒絕：`AlreadyExists`）。有 agent 的話接著 `aos-agent start` 每一個（[03](03-first-agent.md)；已登記的印 `already started`）。

## 底下在幹嘛

- **`aos up` 只是包起來的兩步**：daemon 沒在跑就開 `aos-daemon boot`（輸出寫進 `D/daemon.log`），再 `aos-kernel boot`。
  **`aos down`** 是 `aos-kernel halt` 再 `aos-daemon halt`。這四條都還在，debug 時可以自己一條條打；平常用不到。（[aos up／down 規範](../spec/daemon/up.md)）
- **daemon** 管兩件事。第一，cpu 的生死，而且按池管：kernel 跟它說「池 `default` 要 2 顆」，它就補到 2 顆；死了就重拉（越死越等久，不會狂拉）；多了就收。它不看 cpu 在做什麼。
  第二，**替 kernel 定時走一格**：每秒開一次 `aos-kernel tick`；`K/requests/` 一有新單就馬上開一格，不用等滿一秒。宣告和「替誰走格」都記在 daemon 家裡，所以 daemon 重開會照舊接上。（[daemon 的池](../spec/daemon/pools.md)、[daemon 替 kernel 開 tick](../spec/daemon/ticks.md)）
- **cpu** 是「一個資料夾＋一個主人程式」：有人往它的 `requests/` 放一張單，它就照單跑一次程式，把結果寫進 `responses/`。一次只跑一件。每顆的家在 `K/pools/<池>/cpus/<號>/`，號碼從 0 起。（[cpu 規範](../spec/cpu/README.md)）
- **kernel 不是一直開著的程式**。它每次只跑「一格」`aos-kernel tick`：替排隊的工作挑空的 cpu 派下去、收結果、照池表跟 daemon 講要幾顆，然後退出。
  daemon 一格接一格地開，就成了排程。它所有的記憶都在 `K/ledger.sqlite`（帳本）。（[kernel 名詞](../spec/kernel/terms.md)、[boot 做什麼](../spec/kernel/boot.md)）
- llm 池的 cpu 跟一般 cpu 是同一支程式，差別只在環境多了 `AOS_LLM_CONFIG`；問模型的工作都排到 `llm` 池。（[池表 info.json](../spec/kernel/info.md)、[llm.json 格式](../spec/aos-llm/config.md)）
- **daemon 被 kill -9（或當掉）**：它的 cpu 不會跟著死，手上那件照做（這是刻意的：孩子不綁爸爸的命）。這時 `aos-kernel ls` 的 kernel 行寫
  `running（帳本這樣寫；daemon 不在，其實沒在跑）`、池那行寫 `不明（daemon 沒在跑…）`。下一次 `aos up` 開的新 daemon **先把上一任留下的 cpu 收掉、等它們死透，才拉新的**，
  所以不會有同一個 cpu 家兩個主人；被打斷的那件回「被停掉」（`stopped`）或 `Interrupted`，不會自己重派；agent 問模型那種會自己重送，平常看不出來。`D/daemon.log` 會留一行 `Boot: … 上一任 pid N 沒正常停…`。（[daemon §6.1](../spec/daemon/lifecycle.md)）
- **環境**：daemon 拉的 cpu、cpu 跑的工作，都繼承 `aos up` 開 daemon 那一刻的環境（`aos up` 會自己在 PATH 前面補上 `proto5/cli`）。之後再 `export` 沒用，要 `aos down` 再 `aos up`。

## 常見錯誤

| 看到 | 原因與怎麼辦 |
|---|---|
| `check` 的 `path` 是 `bad` | 這個終端沒 `. $W/env.sh`。先 `.` 它；daemon 已經開著的話 `aos down`、`aos up` 重開一次 |
| `aos up` 印 `NoDaemon` | `K/info.json` 沒寫 `daemon`（手寫的家才會這樣，見 [06](06-appendix-manual-home.md)）。補上再 `aos up` |
| `aos up` 印 `ReadFailed: 讀不到 JSON …/info.json` | K 還沒建，或這個終端沒 `. $W/env.sh`（找錯地方）。先做第 3 步 |
| `ls` 第一行 `daemon 沒在跑：…`、`停機中`、`tick 沒人開` | 都是 `aos up` |
| `probe/default` 是 `bad`、`Connection refused` | 端點沒開或 `llm.json` 的 port 寫錯。改 `llm.json` 就好，不用重開 |
| `init` 印 `AlreadyExists: 拒絕覆蓋既有的家` | 家已經建過了，直接 `aos up`；要重來就 `aos down`、`rm -rf $W/K` |
| `init` 印 `FieldTypeMismatch: kernel 是保留名…` | 池表裡寫了 `kernel` 池（舊的寫法）。從 `kernel.json` 拿掉那一池再 `init` |
| `aos up` 印 `InfoVersion` | `K/info.json` 還是舊的「一顆顆列 `cpus`」格式。刪掉 `K`，照第 2 步的池表重新 `init` |
| `init` 印 `FieldTypeMismatch: cpus 是 proto5 舊格式…` | `--config` 用了舊的 `{"cpus": {…}}` 格式。照第 2 步改成 `pools` 池表再 `init` |
| `aos up` 第二行 `health` 不是 `ok`、退 1 | 照那行括號做；池出錯（如 `NameTaken`）見 [06](06-appendix-manual-home.md) 第 4 節 |
| `aos up` 印 `DaemonFailed` 或 `Timeout` | daemon 開不起來，看 `$W/D/daemon.log` 最後幾行 |
| 要把 `llm.json` 搬到別處 | 手改 `K/info.json` 裡 `llm` 池 `envs` 的路徑，下一格生效；已經活著的 cpu 不會變，要現在就全換：`aos-daemon kill --pool llm --all`（[池模板](../spec/kernel/home.md)） |
| `ls` 的 health 不是 `ok` | 照括號做；各種說法見 [health](../spec/kernel/health.md) |

## 收工

照第 6 步 `aos down`。要整個重來：關好之後 `rm -rf $HOME/aos-try`。下一篇接著用開好的 kernel，就先別關。
