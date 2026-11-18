11-18 公司 WSL 把舊 aos 整個清掉、照重建步驟單從零裝一次並試跑（假腦、更新、eca），再整個清掉；寫成教學本，給之後一步一步照著教。

← [重建步驟單](../17/重建步驟單.md)｜線 `wsl-rebuild-1118`（opus）實跑；log 與腳本在公司 WSL 的 `~/.aos/scratch/wsl-rebuild-1118/`

使用者原話（11-18 傍晚）：「公司WSL的東西整個清掉，重建，然後你幫我試跑，跑完之後再整個清掉，並留下相關紀錄，我之後單開一個session對著這份紀錄，一步一步教我。」

## 先講結論

- 清掉 → 重建 → 試跑 → 再清掉，**四段都走完了**，沒有觸發任何停損。
- 步驟單的安裝六步、「關」、「再起」、更新五步**每一步都對得上**；eca 版（Claude Code 當腦）也實際問過一句、回了「好」。
- 真模型（LiteLLM／LM Studio）**沒試**：這台當下兩個端點都沒開。
- 找到幾個步驟單沒寫、初學者會卡的地方（見最後「跟步驟單對不上的地方」），最要緊的兩個：**「再起」時視窗 B 照抄 `cd llms && …` 會失敗**（人已經在 `llms/` 裡）、**關樹那行用 `&&` 串，根已經停了的話 llm kernel 那台不會被關**。

## 起點：這台現在長什麼樣（你開始學的時候）

公司 WSL（Ubuntu 24.04.4、Python 3.12.3、帳號 `guanyu`）上**完全沒有 aos**：

| 東西 | 現在 |
|---|---|
| `~/repo/aos`（程式） | 沒有（`~/repo` 是空資料夾） |
| `~/aos-home`（樹） | 沒有 |
| `~/.bashrc` 裡的 `AOS_HOME` | 沒有（跟備份 `~/.bashrc.bak-20261118` 逐字一樣） |
| `~/.local/bin/aos-*` 舊連結 | 沒有 |
| Python user site 的 `aos-proto8.pth` | 沒有 |
| 跑著的 aos 行程 | 沒有 |
| `command -v aos-exec` | 找不到 |

已經有、不用你裝的：`g++`、`gcc`、`make`、`git`、`tmux`、`bwrap`、`curl`、`python3`，`~/.local/bin/claude`（Claude Code，已登入）。

## 做完會得到什麼、大概花多久

- 得到：`~/repo/aos`（程式）、`~/aos-home`（一棵能跑的樹：根＋llm kernel＋一隻假腦 agent `ann`），問它 `hello` 會回 `FAKE ANSWER to: hello …`。
- 時間：我實跑時機器時間約 **2 分半**（clone 15 秒、`install.py` 85 秒、其餘都是幾秒）。你邊學邊打，抓 **30～45 分鐘**。

## 先懂三個詞（比喻）

- **`proto8/`＝工廠**：clone 下來的程式。`install.py` 在工廠裡把成品擺進 `bin/ lib/ include/` 三個貨架；執行時**只拿貨架上的東西**。
- **`AOS_HOME`＝工廠地址**：一台機器寫一次進 `~/.bashrc`，告訴所有指令「工廠在哪」。
- **`~/aos-home`＝你家的樹**：從工廠抄一份「起手範本」出來，裡面只放設定；跑起來後多出 `.stack/`（跑出來的帳）。

---

## 第 0 步：清舊東西（這次已清過，下次不用做）

> **這台已經清乾淨，你學的時候跳過這節。** 只有在你（或別的 agent）又用舊方法（舊的 `cmd/install.sh`、舊 `.pth`）裝過東西時才要回來做。

這次實際清掉的（清之前都先看過、記了大小）：

| 東西 | 清之前 | 怎麼清的 |
|---|---|---|
| 舊樹 `~/aos-home` | 12 MB，停著（沒有 aos 行程在跑）；裡面是 `eca_main`、`ops-agent` 兩隻 agent 的定義、它們自己寫的筆記（`ws/notes/`）、11-17 的備份 `backups/defs-1117` | 先打包一份到 `~/.aos/scratch/wsl-rebuild-1118/old-aos-home-backup.tgz`（2 MB，只有你能讀）再 `rm -rf /home/guanyu/aos-home` |
| 舊 clone `~/repo/aos` | 304 MB，HEAD `ff7f74725`；乾淨、沒 stash、沒未推的 commit（fetch 後確認那個 commit 已在 GitHub 上），落後 73 個 | `rm -rf /home/guanyu/repo/aos` |
| `~/.local/bin/aos-*` | 24 個連結，全指進 `~/repo/aos/proto8/cmd/…`、`impls/…`（舊 `cmd/install.sh` 做的） | `find /home/guanyu/.local/bin -maxdepth 1 -type l -name 'aos-*' -lname '*repo/aos*' -delete`（只刪連結；`claude`、`codex`、`uv` 等沒動） |
| `~/.local/lib/python3.12/site-packages/aos-proto8.pth` | 65 位元組，內容兩行：指 `~/repo/aos/proto8/py`、`…/lib` | 直接刪（步驟單寫 `mv` 到家目錄留著；這次照「整個清掉」刪了，內容已記在這裡） |
| `~/.bashrc` 的 aos 行 | **本來就沒有**（舊樹的 `env.sh` 自己設 `AOS_HOME`） | 不用動 |

以後要自己檢查有沒有舊東西，打這幾行，全部「沒有」就是乾淨的：

```sh
ls -l ~/.local/bin/ | grep aos-
```

```sh
ls "$(python3 -m site --user-site)"
```

```sh
grep -n AOS ~/.bashrc
```

```sh
pgrep -af aos-
```

---

## 安裝第 1 步：拿程式

**在幹嘛**：從 GitHub 把程式抄一份到 `~/repo/aos`。

```sh
git clone https://github.com/justty32/aos.git ~/repo/aos
```

**正常會看到**：

```
Cloning into '/home/guanyu/repo/aos'...
```

然後回到提示字元。確認拿到的是哪一版：

```sh
git -C ~/repo/aos log -1 --oneline
```

**出錯怎麼辦**：
- `fatal: destination path '…' already exists and is not an empty directory` → 已經有了，改打 `git -C ~/repo/aos pull`。
- 要帳號密碼 → 這個 repo 公開可讀，不該要；先確認網址沒打錯。

**我實跑**：14.5 秒，HEAD `16558491a`，103 MB。

## 安裝第 2 步：在工廠裡裝貨架（`install.py`）

**在幹嘛**：檢查工具齊不齊，編 C++、把 Python 抄進 `lib/`、在 `bin/` 生 30 支指令。

```sh
cd ~/repo/aos/proto8 && python3 install.py
```

**正常會看到**：先一張工具表（`ok`＝有、`-`＝沒有），再一行 `building cpp/ …`（這裡停最久），最後：

```
installed 30 commands into /home/guanyu/repo/aos/proto8/bin (9 C++, 21 Python entries), 543 files from py/ and 12 C++ libraries into /home/guanyu/repo/aos/proto8/lib, 15 headers into /home/guanyu/repo/aos/proto8/include, 82 entries in cpp/compile_commands.json
next: export AOS_HOME=/home/guanyu/repo/aos/proto8   (once per machine, e.g. in ~/.bashrc, then open a new window)
then: cp -r $AOS_HOME/templates/start-api ~/aos-home   (or start-eca; see templates/start-api/README.md), and in every window: cd ~/aos-home && source env.sh
```

工具表這台是：`required` 四樣（g++、gcc、make、ar）都 `ok`；`optional` 的 `s6-*`、`newuidmap`、`setfacl`、`node`、`codex`、`eca` 是 `-`。**選配的 `-` 不用管**，只是那項功能不能用。

**出錯怎麼辦**：
- `required` 那幾列有 `-` → 退 1、不裝；要先裝那個系統套件（這台不會遇到）。
- 編譯錯 → 看 `~/repo/aos/proto8/cpp/build/build.log` 的最後幾十行。
- 在 Windows 的 git bash 打 `python3` → 那是假的；一定要在 WSL 的終端機打。

**我實跑**：85.5 秒、退 0、`bin/` 30 支。我的表上 `claude` 也顯示 `-`，因為我是用非互動的殼跑的（那種殼不讀 `~/.bashrc`、PATH 上沒有 `~/.local/bin`）；**你在真的終端機打會是 `ok`**。

## 安裝第 3 步：寫下工廠地址（`AOS_HOME`）

**在幹嘛**：讓之後每個視窗都知道工廠在哪。一台機器做一次。

```sh
echo 'export AOS_HOME=~/repo/aos/proto8' >> ~/.bashrc
```

然後**關掉這個視窗、開一個新的**（或在這個視窗打 `source ~/.bashrc`）。確認：

```sh
echo $AOS_HOME
```

**正常會看到**：`/home/guanyu/repo/aos/proto8`

**出錯怎麼辦**：
- 印出空白 → 你還在舊視窗；開新視窗。
- 不小心打了兩次 → `~/.bashrc` 會有兩行一樣的，無害；想乾淨就 `nano ~/.bashrc` 刪一行。

**我實跑**：先備份 `cp -p ~/.bashrc ~/.bashrc.bak-20261118`，加完 `diff` 只多那一行（第 128 行）。注意：Ubuntu 的 `~/.bashrc` 開頭有一段「不是互動視窗就不往下讀」，所以這行**只對你開的終端機視窗有效**，對腳本、systemd 無效（systemd 範例裡要自己寫 `Environment=AOS_HOME=…`，步驟單「要知道的」有提）。

## 安裝第 4 步：抄一棵樹出來

**在幹嘛**：把起手範本（根＋llm kernel＋一隻假腦 agent `ann`）一行抄到 `~/aos-home`。

```sh
cp -r $AOS_HOME/templates/start-api ~/aos-home
```

```sh
ls ~/aos-home
```

**正常會看到**：`README.md  agents  env.sh  llms  root`（`cp` 本身不印東西）。

**出錯怎麼辦**：
- `cp: cannot stat '/templates/start-api': No such file or directory` → `AOS_HOME` 是空的，回第 3 步開新視窗。
- `~/aos-home` 已經存在 → `cp -r` 會把範本**抄進去變成 `~/aos-home/start-api`**，不是你要的；先確認 `~/aos-home` 不存在再抄。

**我實跑**：2 秒、退 0。

## 安裝第 5 步：進環境（每個視窗都要做）

**在幹嘛**：讓這個視窗找得到 aos 的指令。**之後每開一個新視窗，第一件事就是這行。**

```sh
cd ~/aos-home && source env.sh && command -v aos-exec
```

**正常會看到**：`/home/guanyu/repo/aos/proto8/bin/aos-exec`

**出錯怎麼辦**：
- `env.sh: error: EnvBad AOS_HOME is not set …` → 第 3 步沒生效（舊視窗）。
- `env.sh: error: EnvBad AOS_HOME=… is not an aos home …` → `AOS_HOME` 指錯地方。
- 什麼都沒印、退出非 0 → `aos-exec` 不在，回第 2 步重跑 `install.py`。

**我實跑**：三個視窗都印出上面那行。

## 安裝第 6 步：起樹、掛 agent、問一句（三個視窗）

**在幹嘛**：視窗 A 起「根」（整棵樹的總開關），視窗 B 起「llm kernel」（幫 agent 問腦的那台），視窗 C 把 agent 掛上去、問它一句話。

開三個終端機視窗（Windows Terminal 按 `Ctrl+Shift+T` 開新分頁、或下拉選 Ubuntu），**三個都先做第 5 步**。

**視窗 A**（起根；它會一直佔著這個視窗，正常）：

```sh
aos-tree-start root
```

看到兩行就是起來了：

```
{"at": "…", "name": "_clock", "phase": "running", "pid": 648203, …}
{"at": "…", "name": "_sweeper", "phase": "running", "pid": 648204, …}
```

**視窗 B**（起 llm kernel；也一直佔著）：

```sh
cd llms && aos-exec --stack stacks/llm def
```

看到 `"name": "_sweeper", "phase": "running"`，然後**每半秒冒一行 `{"started_at": …, "counter_runs": 1, "code": 0, …}`、一直冒**——這是正常的心跳，不是壞掉，不用管它。

**視窗 C**（掛 agent、看表、問一句）：

```sh
aos-agent -d .stack ctl add --auto-restart -w . agents/ann
```

正常印一行 `/home/guanyu/aos-home/.stack/procs/ann`。這時視窗 A 會多一行 `"name": "ann", "phase": "running"`。

```sh
aos-daemon-ctl -d .stack ls
```

正常：

```
_clock	running	648203	-	-	-
_sweeper	running	648204	-	-	-
ann	running	648523	-	/home/guanyu/aos-home	-
# daemon: running (pid 648201)
# root daemon (no supervisor)
```

```sh
aos-agent -d .stack --target ann say hello && aos-agent -d .stack --target ann listen --timeout-s 20
```

正常（第一行是信件編號，第二行才是回答）：

```
000000000001.01794974853440039189.649144.1402039
FAKE ANSWER to: hello (tool said: 2026-11-18T04:07:39Z)
```

這時視窗 B 會冒出 `"name": "llm_…", "phase": "running"` 接著 `"phase": "done"`——那就是 agent 問腦的那一次。

**出錯怎麼辦**：
- 視窗 A 報它拒絕起來、說殼裡有別棵樹的 `AOS_*` → 你在某個 agent 的殼裡打的；開一個乾淨的新視窗重做第 5 步。
- `ls` 裡 `ann` 不是 `running` → 等兩秒再 `ls`；還不是，看 `~/aos-home/.stack/procs/ann/` 底下的 `stderr.txt`。
- `listen` 等到 20 秒逾時、沒回答 → 多半是視窗 B 沒起（llm kernel 不在，agent 問不到腦）。

**我實跑**：`add` 3 秒、`ls` 2.5 秒、問答 12 秒（第一次比較慢；後面都 5 秒）；`_clock`、`_sweeper`、`ann` 都 `running`，回 `FAKE ANSWER to: hello`。

**我實際怎麼驗的**（你不用這樣做）：我是 AI，從 Windows 經 `wsl -e bash -c '…'` 進去，而經 `wsl.exe` 丟到背景的行程會跟著那次呼叫結束而死，所以沒辦法像你一樣開三個長命的視窗。我是在**同一次呼叫裡**開一個私人的 tmux（`tmux -L wslrb1118`），開 A、B、C 三個 tmux 視窗、各跑一個互動殼（會讀 `~/.bashrc`，跟你開新視窗一樣），用 `send-keys` 把上面的指令打進去，最後關樹、收掉 tmux。你自己開三個真的終端機視窗就沒這個問題。

## 關樹

**在幹嘛**：整棵停掉。agent 是「睡下」，不是刪掉，下次起來自己醒。

在視窗 C（或任何新視窗，這行自己會進環境）：

```sh
cd ~/aos-home && source env.sh && aos-daemon-ctl -d .stack shutdown && aos-daemon-ctl -d llms/stacks/llm shutdown
```

**正常會看到**：

```
daemon at /home/guanyu/aos-home/.stack stopped (ctl seq 1); 3 procs asleep, they wake when it starts again
daemon at /home/guanyu/aos-home/llms/stacks/llm stopped (ctl seq 1); 1 procs asleep, they wake when it starts again
```

同時視窗 A、B 各印幾行 `"phase": "sleeping"`，然後**自己回到提示字元**（不用按 Ctrl-C）。

另一種關法：在視窗 A 按 `Ctrl-C`＝整棵根停；視窗 B 按 `Ctrl-C`＝llm kernel 停。

**出錯怎麼辦**：
- `aos-daemon-ctl: error: DaemonMissing no aos-daemon running at …/.stack (pid … is gone)`、退 1 → 根本來就停了。**小心**：因為兩句用 `&&` 串，第一句失敗第二句就不跑；如果 llm kernel 還開著，要另外打 `aos-daemon-ctl -d llms/stacks/llm shutdown`。

**我實跑**：1.7 秒，兩台都停；之後 `pgrep` 沒有任何 aos 行程。

## 再起（不用再 add）

**在幹嘛**：重開；上次睡下的 `ann` 會自己醒，不用再掛一次。

**視窗 A**（已經做過第 5 步、還在 `~/aos-home`）：

```sh
aos-tree-start root
```

這次一起來就是三行 `running`（`_clock`、`_sweeper`、`ann`）。

**視窗 B**——注意，你**已經在 `~/aos-home/llms` 裡了**，所以**不要**再打 `cd llms`，直接：

```sh
aos-exec --stack stacks/llm def
```

（照第 6 步抄 `cd llms && …` 會看到 `bash: cd: llms: No such file or directory`，後面那句就不跑了。不確定自己在哪，就打完整的 `cd ~/aos-home/llms && aos-exec --stack stacks/llm def`。）

**視窗 C**：

```sh
aos-daemon-ctl -d .stack ls
```

```sh
aos-agent -d .stack --target ann say again && aos-agent -d .stack --target ann listen --timeout-s 20
```

**我實跑**：沒有 add，`ls` 三個都 `running`，回 `FAKE ANSWER to: again (…)`，5 秒；再關一次也乾淨。

---

## 更新五步（改了程式或 `git pull` 之後）

**一句話**：先停樹 → 拿新程式 → `install.py` → 看要不要重抄 → 再起。**改了 Python 也一定要 `install.py`**，不然樹跑的還是舊的。

我沒辦法改 GitHub 上的程式，所以模擬法是：在 `~/repo/aos` 本地改一行 `proto8/py/aos/apps/tree_start/main.py` 的說明字（加上 `[WSLRB-1118 TEST]`，不 commit），當作「拉到了新版」。

**更新 1：停樹**

```sh
cd ~/aos-home && source env.sh && aos-daemon-ctl -d .stack shutdown && aos-daemon-ctl -d llms/stacks/llm shutdown
```

我實跑時樹本來就停著，看到 `DaemonMissing … (pid 649824 is gone)`、退 1——步驟單說這個不用理它（但記得上面「`&&` 串」那個小心）。

**更新 2：拿新程式**

```sh
git -C ~/repo/aos pull
```

這時**樹還是跑舊的**。我實測：改完字、還沒裝，`aos-tree-start --help | head -1` 印的還是舊字。

**更新 3：重裝**

```sh
cd ~/repo/aos/proto8 && python3 install.py
```

C++ 沒改時很快。裝完 `aos-tree-start --help | head -1` 就是新字：

```
aos-tree-start - start the root of an aos tree in the foreground [WSLRB-1118 TEST], refusing an environment inherited from another tree
```

**更新 4：看樹裡的抄本要不要重抄**（手動比對）

```sh
diff -r $AOS_HOME/templates/agent-fsm ~/aos-home/agents/ann
```

```sh
diff -r $AOS_HOME/templates/daemon-root ~/aos-home/root
```

```sh
diff -r $AOS_HOME/templates/kernel/llm-kernel ~/aos-home/llms/def
```

```sh
diff $AOS_HOME/templates/start-api/env.sh ~/aos-home/env.sh
```

剛抄好的樹，正常**只會列出兩處**，這兩處是起手範本本來就改過的，**不要蓋回去**：
- `agents/ann/llm.json`：範本 `{}`、你的 `{"model": "fake"}`（假腦）。
- `root/.env`：`AOS_LLM_KERNEL` 那兩行（你的指樹裡的 `llms/stacks/llm`）。

其他兩個 `diff` 不印東西＝一樣。之後真的有新版時，commit 訊息會寫要重抄哪些；`llm.json`、`system.txt`、`.stack` 不能直接蓋。

**更新 5：再起**——照上面「再起」那節（視窗 A、B），睡下的自己醒。

**我實跑**：`install.py` 1.2 秒；裝前舊字、裝後新字；`diff -r` 只列出上面兩處；再起後 `ann` 自己醒、問 `after-update` 回 `FAKE ANSWER to: after-update`。驗完 `git -C ~/repo/aos checkout -- proto8/py/aos/apps/tree_start/main.py` 還原、再 `install.py` 一次（1.1 秒），說明字變回原樣、`git status` 乾淨。

---

## 試跑：eca 版（Claude Code 當腦）——有試，成功

**在幹嘛**：換一棵用 `templates/start-eca` 的樹，agent 的腦是 Claude Code（`claude` 指令），不用 llm kernel（只要視窗 A、C）。**會花額度**（範本設 sonnet、每次上限 0.5 美元）。

先決條件：`command -v claude` 找得到、已登入（這台都是）。

你學的時候要用 eca 版，就把第 4 步換成：

```sh
cp -r $AOS_HOME/templates/start-eca ~/aos-home
```

視窗 A（先第 5 步）：

```sh
aos-tree-start root
```

視窗 C（先第 5 步）：

```sh
aos-agent -d .stack ctl add --auto-restart -w . agents/ann
```

```sh
aos-agent -d .stack --target ann say "Reply with exactly one character: 好" && aos-agent -d .stack --target ann listen --timeout-s 120
```

關：

```sh
cd ~/aos-home && source env.sh && aos-daemon-ctl -d .stack shutdown
```

**我實跑**：為了不跟 API 版那棵打架，我抄到 `~/aos-home-eca`（試完刪了）。`add` 3.3 秒，`ls` 三個都 `running`，問答 **11.4 秒、回 `好`**；關樹 3 秒，`3 procs asleep`，之後沒有留下我起的行程。沒跳登入、沒問授權。

## 試跑：真模型（API 版接真腦）——沒試

**原因**：當下這台 `http://localhost:4000/v1/models`（LiteLLM）與 `http://localhost:1234/v1/models`（LM Studio）都連不上；而且規矩是公司機真腦走 eca（[02-模型端點](../../../../wf/workflows/dev-env/02-模型端點.md)「公司機只用 eca 驗真腦」），上面 eca 已經驗過。

要接的時候怎麼換（沒實測）：把 `~/aos-home/agents/ann/llm.json` 的 `{"model": "fake"}` 換成 `~/aos-home/llms/def/kernel.json` 的 `endpoints` 裡的名字，端點要先開著；改完關樹再起。

## 健康檢查：跑一小撮測試

```sh
cd ~/repo/aos && export AOS_HOME=~/repo/aos/proto8 PYTHONNOUSERSITE=1 && source $AOS_HOME/env.sh && python3 -m unittest discover -s proto8/py/tests
```

**我實跑**：518 支、63 秒，**1 紅**：`test_aos_ws_reply_match … test_pre_change_aos_ws_reads_the_same`（`ImportError: cannot import name 'ws' from 'aos'`）。看起來是這支測試拿舊 commit 的檔來比，卻用新的 import 寫法去讀；跟這次重建無關，**沒查它在不在已知紅清單**。

另外：任務書給的寫法沒有 `source env.sh`，那樣跑是 5 失敗＋9 錯誤，全是 `No such file or directory: 'aos-exec'`／`'aos-json'`——**這批測試要 `bin/` 在 PATH 上**，所以要先 `source $AOS_HOME/env.sh`。

---

## 這次最後又清掉了什麼（回到「沒有 aos」）

照起來的順序收：關掉我起的所有樹（用 aos 自己的 `shutdown`；`pgrep` 確認沒有）、收掉我的 tmux（`tmux -L wslrb1118 kill-server`，連它留下的 socket 檔），然後：

```sh
rm -rf /home/guanyu/aos-home
```

```sh
rm -rf /home/guanyu/aos-home-eca
```

```sh
rm -rf /home/guanyu/repo/aos
```

```sh
sed -i '\#^export AOS_HOME=~/repo/aos/proto8$#d' ~/.bashrc
```

`diff ~/.bashrc.bak-20261118 ~/.bashrc` 逐字一樣（這台本來就沒有舊 aos 行）；備份檔留著。最後盤點＝本文開頭「起點」那張表。

**留著沒刪的**（都不是 aos 的安裝物）：
- `~/.aos/scratch/wsl-rebuild-1118/`：我的筆記、log、三支驅動腳本、舊樹打包 `old-aos-home-backup.tgz`（2 MB，權限 600）。舊樹確定不要了，你自己刪那個 tgz 就好。
- `~/.bashrc.bak-20261118`。
- 副作用：`~/.bash_history` 多了幾行我在 tmux 互動殼裡打的 aos 指令；跑 eca 時 Claude Code 照常在 `~/.claude*` 寫了它自己的 session 紀錄（不在這次能動的範圍，沒去清）。

---

## 踩到的坑（初學者容易卡的地方）

1. **第 3 步之後忘了開新視窗**：`$AOS_HOME` 是空的，第 4 步 `cp` 會報 `cannot stat '/templates/start-api'`，第 5 步報 `EnvBad AOS_HOME is not set`。
2. **`~/aos-home` 已存在時再 `cp -r`**：會抄成 `~/aos-home/start-api`，不會覆蓋。
3. **視窗 B 一直冒 `counter_runs` 行**：正常心跳，不是壞掉。
4. **「再起」視窗 B 照抄 `cd llms && …` 會失敗**：人已經在 `llms/` 裡。
5. **關樹那行 `&&` 串**：根已經停了，第二句（llm kernel）就不跑。
6. **問答第一行是一串數字**：那是信件編號，回答在第二行。
7. **新視窗沒做第 5 步就打 aos 指令**：`command not found`。
8. **在 Windows 的 git bash 打 `python3`**：是假的；也不要在 `/mnt/c/…` 底下跑 aos（每個檔都帶執行權限，會出怪事）。
9. **跑測試沒先 `source env.sh`**：一堆 `No such file or directory: 'aos-exec'`。

## 跟步驟單對不上、建議怎麼改（只建議，步驟單沒動）

| 步驟單哪裡 | 實際 | 建議 |
|---|---|---|
| 「關」與「更新 1」那行 `… shutdown && … shutdown` | 根已停時第一句退 1，第二句不跑，llm kernel 可能還開著 | 改成兩句分開打，或中間用 `;` |
| 「關」那格「再起＝第 6 步的視窗 A、B」 | 在同一個視窗 B 照抄 `cd llms && aos-exec …` 會失敗（已在 `llms/`） | 寫成「視窗 B：`cd ~/aos-home/llms && aos-exec --stack stacks/llm def`」，或註明「同一個視窗省掉 `cd llms`」 |
| 第 6 步說明 | 沒提視窗 B 會一直冒 `counter_runs` 行 | 加一句「視窗 B 每半秒一行是正常的」 |
| 「關」的說明 | 用 `shutdown` 關時，視窗 A、B 會自己回到提示字元 | 可補一句，免得人以為還要按 Ctrl-C |
| 第 0 步 `.pth` 那格寫 `mv` 到 `~/aos-proto8.pth.old` | 留在家目錄就不算「清乾淨」 | 可補「確定不要就直接 `rm`」 |
| 第 4 步 | 目的地已存在時 `cp -r` 會抄進子夾 | 補一句「`~/aos-home` 要先不存在」 |
| 開頭「install.py 全新約 71 秒」 | 這台 85.5 秒（同時有別的線在編譯） | 寫「約 1～1.5 分鐘」 |
| 第 2 步工具表 | 在非互動殼裡跑，`claude` 會顯示 `-`（PATH 沒有 `~/.local/bin`） | 不用改；知道就好 |
| 「要知道的」只開發不起樹那段、[testing](../../../../wf/workflows/testing.md) | `proto8/py/tests` 要 `bin/` 在 PATH 上 | 跑測試的寫法補 `source $AOS_HOME/env.sh` |

## 實跑時間總表

| 步 | 結果 | 耗時 |
|---|---|---|
| 第 0 步（盤點＋清） | 清了舊樹、舊 clone、24 個連結、1 個 `.pth`；停損沒觸發 | 幾秒 |
| 1 clone | ✅ HEAD `16558491a` | 14.5 秒 |
| 2 `install.py` | ✅ 退 0、`bin/` 30 支 | 85.5 秒 |
| 3 `AOS_HOME` | ✅ 新視窗看得到 | — |
| 4 抄範本 | ✅ | 2 秒 |
| 5 進環境 | ✅ 三個視窗都找得到 `aos-exec` | — |
| 6 起樹、問一句 | ✅ `FAKE ANSWER to: hello` | add 3 秒、問答 12 秒 |
| 關 | ✅ 兩台都停 | 1.7 秒 |
| 再起 | ✅ 不 add，`ann` 自己醒、照答 | 問答 5 秒 |
| 更新五步 | ✅ 裝前舊字、裝後新字，`diff -r` 只列兩處，再起照答 | `install.py` 1.2 秒 |
| eca 版 | ✅ 回 `好` | 問答 11.4 秒 |
| 真模型 | 沒試（端點都沒開；公司機真腦走 eca） | — |
| 測試 `proto8/py/tests` | 518 支、1 紅（見上） | 63 秒 |
| 再清掉 | ✅ 回到「沒有 aos」 | 幾秒 |
