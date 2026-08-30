# 任務 D：劇本 4＋5——錯誤路徑指不指路、以及「多打了幾個指令」的總帳

你的代號是 **D**。先完整讀下面的共同守則，再照劇本做。

---

# 共同守則（每份任務書都適用）

你在扮演**一個坐在終端機前的使用者**，第一次用 `aos` 這個工具當 coding agent。
你的工作是**照劇本做、記下所有不順手的地方**。你**不是**來修 aos 的。

## 絕對禁止

- **不可修改 aos 原始碼**：`core/`、`app/`、`include/`、`CMakeLists.txt`、`docs/` 一個字都不能改。
- **不可重新編譯 aos**（`cmake` / `make` 在 repo 根都不要跑）。二進位已經編好了。
- **不可 load／unload LM Studio 的模型**，不可開任何 GUI，不可改 `~/.aos/`（那是使用者層設定，現在故意不存在）。
- **不可寫 `git commit` / `git push`**。
- 除了你自己的世界資料夾與報告，不要動 repo 裡其他檔案。

## 你可以寫的地方（只有這些）

- `wf/workflows/dispatch/trial/sandbox/solo/<你的代號>/**` — 你的世界、log、暫存
- `wf/workflows/dispatch/trial/sandbox/solo/<你的代號>/repro/*.sh` — 重現腳本
- `-o` 指定的報告檔

## 執行環境（寫死，不要自己找）

```sh
AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos
ROOT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254
SOLO=$ROOT/wf/workflows/dispatch/trial/sandbox/solo
TEMPLATE=$SOLO/_template          # 3 檔 C++ 小專案＋測試＋Makefile
```

**一律用 `$AOS` 這個絕對路徑呼叫**，不要 `which aos`、不要改 PATH 以外的東西
（要改 PATH 就 `export PATH="$ROOT/build/bin:$PATH"`，但指令仍寫 `$AOS`）。

- LM Studio 已經在 `http://localhost:1234/v1` 跑著，載好的模型是 `qwen/qwen3.5-9b`。**不要動它。**
- `pi` 在 PATH 裡；`DEEPSEEK_API_KEY` 已經在環境變數裡（不要印出來、不要寫進檔案）。
- `~/.aos/cpus.json` 不存在＝沒有並行上限＝呼叫不取槽。**不要建它。**

## aos 的基本形狀（給你省時間，但仍要親自驗）

- 一個資料夾 ＋ 裡面的 `.aos/` ＝ 一個「世界」。一個世界住一隻 agent。
- `$AOS agent init [--engine lmstudio|pi] [--name N] [--persona TEXT] [--provider P] [--model M] [--priority N]`
- 世界要靠 `$AOS run <folder> --step N` 推進 N 個回合；**永遠帶 `--step N`，不要用 `--step 0`（無限）**。
- `$AOS say "..."`、`$AOS listen [--once]`、`$AOS state`、`$AOS talk`
- lmstudio 引擎的工具往返是三回合一次（第 N 回合模型提出、N+1 執行、N+2 才看到結果），
  預設只裝 `cat` / `ls` / `sh` 三個工具。pi 引擎不走這條，pi 自帶 read/bash/edit/write。
- **重要**：`$AOS agent init` 會從 cwd 往上找最近的 `.aos/`。repo 根本身就是一個世界，
  所以你建世界前**必須先 `mkdir -p <world>/.aos`**，否則 agent 會被靜默建到 repo 根。
  這件事本身就是一條發現，照樣記。

## 逾時與耐心

lmstudio 是本機 9B 模型，一個回合可能 20–120 秒。所有會呼叫 LLM 的指令請包 `timeout`：
`timeout 900 $AOS run . --step 12 > run.log 2>&1`。
不要無限等；卡住就記成一條發現（`kind=awkward` 或 `bug`），附上你等了多久。

## 你要交出什麼

**最終回覆本身就是成品**（完整貼出，不要只說「已寫入檔案」），**同時**寫進 `-o` 指定的檔案。
格式如下，兩段：

### 第一段：發現表（CSV 資料列，不含表頭）

每行 9 欄，逗號分隔，**欄位內若有逗號請改用中文全形「，」**，不要用引號跳脫：

```
id,lane,kind,severity,step,expected,actual,compare,repro
```

- `id`：`<你的代號>-01`、`-02`…（例：`A-01`）
- `lane`：固定 `L1`
- `kind`：`bug`（會壞／行為與文件不符）｜`awkward`（能做到但多餘動作／看不見狀態）｜`spec-gap`（缺件，設計上就沒有）｜`cannot`（劇本走不完）
- `severity`：`3`（擋路）｜`2`（很煩）｜`1`（小刺）
- `step`：你在哪一步遇到的（短，例：`劇本1 改函式 第3個指令`）
- `expected`：使用者本來預期什麼
- `actual`：**實測到什麼，要有具體數字／訊息原文／檔案路徑**。沒有實測證據的一律不要寫。
- `compare`：**同一件事直接用 `pi` 做要幾步**（必填，這是這次的重點欄位）
- `repro`：`repro/<id>.sh`（`kind=bug` 必填且腳本要真的能重跑）｜其他類可填 `-`

### 第二段：敘事報告

300–800 字，講：劇本走到哪、哪裡最痛、**指令數對照的實際數字**
（「aos 打了 N 個指令、等了 M 個回合、耗時 T；同一件事 pi 打了 1 個指令、耗時 T2」）。

## 品質門檻

- 每條發現都要有**實測證據**。臆測、讀 README 得出的推論一律不收。
- 一個現象只記一條。不要把同一件事拆成五條灌水。
- 你這一份**最多 15 條**。寧可少而準。

---

# 你的劇本

你關心的是：**出事的時候，錯誤訊息有沒有告訴我下一步該做什麼。**
判準很簡單——一個第一次用 aos 的人，看到那則訊息，**知不知道要打哪個指令去修**。
每一條都要**把錯誤訊息原文抄進 `actual` 欄位**（超過一行就抄最關鍵那行），並記下 exit code。

**注意**：你會 unset `DEEPSEEK_API_KEY`、指不存在的模型、指錯的 port——這些都只在**子 shell 或
`env` 前綴**裡做，**不要動 LM Studio 本身，不要建 `~/.aos/`**。

## 步驟 0：素材

```sh
mkdir -p "$SOLO/D"
cp -r "$TEMPLATE/." "$SOLO/D/plain/" 2>/dev/null || { mkdir -p "$SOLO/D/plain" ; cp -r "$TEMPLATE/." "$SOLO/D/plain/" ; }
```

## 錯誤 1：在沒有 `.aos` 的資料夾裡 say / listen / state

```sh
mkdir -p "$SOLO/D/nowhere" ; cd "$SOLO/D/nowhere"
$AOS say "hi" ; echo "exit=$?"
$AOS listen --once ; echo "exit=$?"
$AOS state ; echo "exit=$?"
$AOS run . --step 1 ; echo "exit=$?"
```

**注意陷阱**：repo 根本身是一個世界，所以 `find_folder` 會往上找到它。
**這件事對使用者的意義是什麼？**（他以為在跟這個資料夾的 agent 說話，其實話送到別的世界去了。）
用 `AOS_FOLDER` 或在 repo 外的路徑再驗一次「真的沒有任何世界」的情況：

```sh
cd /tmp ; mkdir -p aos-d-empty ; cd aos-d-empty
$AOS say "hi" ; echo "exit=$?"
$AOS state ; echo "exit=$?"
$AOS listen --once ; echo "exit=$?"
```

（`/tmp/aos-d-empty` 是唯一允許你在 repo 外碰的路徑，用完 `rm -rf` 掉。）

## 錯誤 2：世界有了，但沒有 agent

```sh
mkdir -p "$SOLO/D/noagent/.aos" ; cd "$SOLO/D/noagent"
$AOS say "hi" ; echo "exit=$?"
$AOS state ; echo "exit=$?"
$AOS listen --once ; echo "exit=$?"
```

**問**：訊息有沒有說「先跑 `aos agent init`」？

## 錯誤 3：LM Studio 連不上 / 模型不存在

**不要動 LM Studio**，用環境變數指到錯的地方：

```sh
mkdir -p "$SOLO/D/lm/.aos" ; cd "$SOLO/D/lm"
cp -r "$TEMPLATE/." . ; $AOS agent init
# 3a 端點不通
echo hi | AOS_LLM_URL=http://localhost:19999/v1 timeout 60 $AOS llm ; echo "exit=$?"
AOS_LLM_URL=http://localhost:19999/v1 timeout 120 $AOS run . --step 1 ; echo "exit=$?"
$AOS say "測試" ; AOS_LLM_URL=http://localhost:19999/v1 timeout 300 $AOS run . --step 2 ; echo "exit=$?"
$AOS state ; cat .aos/agents/*/status.json ; $AOS listen --once
# 3b 模型不存在（隊長已實測過一次：`echo hi | AOS_LLM_MODEL=no/such-model aos llm`
#    會**正常回一段答案、exit=0**——LM Studio 拿別的模型回答了，aos 沒有任何提示。
#    **不要重跑這個**（會讓 LM Studio 動到模型狀態）。直接把這條當已知事實記成一條發現，
#    `actual` 寫「隊長實測：exit=0，回了一段正常英文回覆，沒有任何『模型不存在』的提示」。）
```

**關鍵問題**：LLM 呼叫失敗的時候，**使用者從 `aos state` / `aos listen` 看得出來「失敗了」嗎，
還是只看到一個永遠 idle 的世界？** 錯誤訊息跑到哪去了（`run` 的 stdout？stderr？還是被吞掉）？

## 錯誤 4：pi 引擎沒有 `DEEPSEEK_API_KEY`

```sh
mkdir -p "$SOLO/D/pi/.aos" ; cd "$SOLO/D/pi"
cp -r "$TEMPLATE/." . ; $AOS agent init --engine pi
$AOS say "在這個資料夾建一個 hello.txt 內容是 hi"
env -u DEEPSEEK_API_KEY timeout 300 $AOS run . --step 1 ; echo "exit=$?"
$AOS state ; cat .aos/agents/*/status.json ; $AOS listen --once | tail -20
```

**問**：訊息有沒有講到 `DEEPSEEK_API_KEY` 這個字？有沒有講「去哪裡設」？
`agent init --engine pi` 當初有沒有提醒過？

## 錯誤 5：模型要一個不存在的工具 / 工具登記表出錯

```sh
cd "$SOLO/D/lm"
$AOS tool list ; echo "exit=$?"
$AOS tool add ; echo "exit=$?"                 # 少參數
$AOS tool remove nosuchtool ; echo "exit=$?"
$AOS tool add make make ; echo "exit=$?"       # 猜一下語法對不對；看它教不教你
$AOS tool list
```

**問**：`aos tool add` 的用法錯誤時，訊息有沒有給正確用法？
文件說模型要不存在的工具會得到 `unknown_tool` 的一行 JSON——**使用者從 `aos listen` 看得到嗎？**
試著讓它發生（`$AOS say "請用 make 工具跑一次 make"` 然後 `timeout 600 $AOS run . --step 6`），
把 listen 到的原文抄下來。**這是你唯一會大量用到 LM Studio 的一步，只做這一次。**

## 錯誤 6：`aos run` 撞在一起 / 參數錯

```sh
cd "$SOLO/D/lm"
$AOS run . --step ; echo "exit=$?"
$AOS run . --step abc ; echo "exit=$?"
$AOS run /nonexistent/path --step 1 ; echo "exit=$?"
$AOS agent init ; echo "exit=$?"               # 在已經有 agent 的世界再 init 一次
$AOS agent init --engine nosuchengine ; echo "exit=$?"
$AOS agent init --name x --model ; echo "exit=$?"
```

## 步驟 7：**指令數總帳**（劇本 5，這一段很重要）

回頭看你自己跑過的東西，填一張表（寫進報告的敘事段，也挑最痛的做成發現）：

| 使用者心裡的一句話 | aos 實際要打幾個指令 | 等幾個回合 | pi 要打幾個指令 |
|---|---|---|---|
| 「幫我改 parse() 回傳 optional」 | ? | ? | 1 |
| 「它現在在幹嘛」 | ? | — | ? |
| 「跑一下測試」 | ? | ? | ? |
| 「我剛才叫你做什麼」 | ? | ? | ? |
| 「開一個新的 agent 開始工作」 | ? | — | ? |

A / B / C 三位在跑主線劇本，你**不必**重跑改函式那條；用你自己 `$SOLO/D/lm` 世界跑一次
「幫我在 README.md 最後加一行 `# tried`」這種最小任務來量：

```sh
cd "$SOLO/D/lm"
# 從零開始計數：mkdir、init、say、開另一個視窗 run、listen、確認結果……
```

把「最小可用一輪」實際需要的指令序列**完整列出來**（一行一個指令），數出總數。
和 `pi -p "在 README.md 最後加一行 # tried"`（1 個指令）對照。

## 步驟 8：收尾

```sh
rm -rf /tmp/aos-d-empty
```

- `kind=bug` 的寫 `$SOLO/D/repro/D-NN.sh`（乾淨資料夾起跑、絕對路徑、`EXPECT:`／`ACTUAL:`）。
- 報告寫進 `-o`，同時整份貼在最終回覆。
