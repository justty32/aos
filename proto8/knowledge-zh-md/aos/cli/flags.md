# `knowledge/aos/cli/flags.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/flags.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/flags.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Help and flag placement`**

# 說明與旗標位置

旗標可以放哪裡、哪些指令不一樣、說明的層級，還有短名。

**`#/A flag goes after its level`**

# 旗標放在它那一層的後面

一個指令有好幾層：程式本身、它的子指令、動作（`aos-agent`、`ctl`、`stop`）。一個旗標屬於某一層，可以放在那一層名字之後的任何地方，也可以放在後面的名字和參數之後。下面這幾行意思一樣：

```sh
aos-agent -d /srv/d ctl stop bob
aos-agent ctl stop bob -d /srv/d
aos-agent ctl stop -t bob
aos-tools add tools/clock --name now
```

每個 aos 指令都是這樣，`aos/cli/parts/` 裡的零件也是（`aos-json get FILE#/a --str`、`aos-eca-turn /abs/def --one`）。例外的情況是字會原樣往下傳：`aos-exec FOLDER ARGS` 裡資料夾後面的全部都交給那個資料夾的程式；`aos-sandbox CONFIG PROG ...` 把 PROG 和它的參數往下傳；`aos-mcp-launch SERVER_FILE` 不收旗標；`aos-json set`、`append` 和 `merge` 的旗標要放在 FILE 前面，因為值可以是任何字（`aos-json set --str FILE#/a -x`）。參數後面的字如果看起來像負數（`-3`）或含有空白，就仍然當參數。

**`#/Naming the agent in aos-agent`**

# 在 aos-agent 裡指定 agent

`aos-agent ctl` 的 start / stop / sleep / wake / pause / resume / where 可以用 `-t NAME` 或最後一個參數指定 agent。say、listen、chat、open、close、watch、tools、llm、system、history、hook、goal 和 `ctl state` 只收 `-t`（state 的其他字是部件名）。`ctl add / rm / set-def / ls / who` 不收 `-t`。給了兩個不同的名字 = `ArgumentsBad`。

沒有 `-t` 也沒有 `$AOS_AGENT`（空的算沒設）：aos-agent 會看目前的資料夾，先看 `./.stack`，再看 `./`。一個資料夾要有 `stderr.txt`（daemon 會在它啟動的每個 proc 的 stack 裡寫這個檔），而且它的真實路徑是 daemon 的表上某一列的 `stack`，才算數；那一列的名字就是目標。`./.stack` 不存在或沒有 `stderr.txt`（例如樹根，那裡的 `.stack` 是 daemon 自己的）= 改試 `./`。有 `stderr.txt` 但不在任何一列上 = `InstanceMissing`。兩個都不是 = `TargetMissing`。只有 stack 資料夾本身算，裡面的資料夾不算，定義夾也絕對不算。也沒有 `-d` 和 `$AOS_DAEMON` 時：daemon 是那個 stack 往上兩層的資料夾（預設的配置 `<daemon stack>/procs/NAME`）；那個資料夾必須有 `procs_state.json` 而且列著這個 stack，不然就是 `DaemonMissing`。有 `-t` 時也一樣（在 ann 的 stack 裡，`-t bob` 指的是同一個 daemon 上的 bob）。用 `-s` 掛在別處的 stack 需要 `-d`。樹根的 `./.stack` 絕不會被當成 daemon。這是給知道這個資料夾是某個 agent 的 stack 的人用的捷徑；stack 裡沒有任何東西說明它屬於哪個 daemon。

```sh
cd /abs/tree/.stack/procs/ann && aos-agent say hello   # target = ann, daemon = /abs/tree/.stack
```

**`#/Text ends flag reading`**

# 文字會結束旗標的讀取

原樣往下傳的文字會結束旗標的讀取：`aos-agent say WORDS`、`history summarize RANGE TEXT`（或 `summarize -n K TEXT`）、`history set LINE JSON`、`goal set TEXT`、`aos-mailbox send WHAT`、`aos-clock-register add NAME TEXT` 從第一個字起全部都是文字，所以旗標要放在它前面。`--` 之後沒有東西是旗標：`aos-daemon-ctl add tools/job -- --verbose`、`aos-agent say -t bob -- -hello`。

**`#/Help levels`**

# 說明的層級

先跑 `aos-agent --help`，再跑 `aos-agent tools --help`，再跑 `aos-agent tools add --help`。每個只印它自己那一層。看說明不需要活著的 daemon 或目標。有子指令的指令都一樣：`aos-post send --help`、`aos-json set --help`。

指令裡沒人認得的旗標會得到 `FlagUnknown`。沒給子指令會得到 `ArgumentsBad`（`aos-post: error: ArgumentsBad missing subcommand`）；不認得的子指令會得到 `CommandUnknown`。

**`#/Short names`**

# 短名

常見的預設短名有：`-h --help`、`-d --daemon`、`-t --target`、`-j --json`、`-n --name`、`-w --ws`、`-s --stack`、`-f --follow`、`-y --yes`。每個指令自己定義短名，意思可能不一樣（aos-mailbox 的 `-s` 是你自己的 stack；aos-clock-register 的 `-c` 是時鐘）。只在那個指令的說明有列出時才用短名。`--file`、`--detach` 和 `--timeout-s` 沒有短名。`-s`/`-w` 不是 `ctl where` 裡那些開關的別名，也不是 `ctl who` 裡路徑的別名。

要分開寫成不同的字：`-t bob`。`-tbob` 和 `-jf` 是不認得的旗標。
