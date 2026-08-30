# 任務 B：劇本 1（改一個函式）——pi 引擎，走完整條，數指令

你的代號是 **B**。先完整讀下面的共同守則，再照劇本做。

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

# 你的劇本（照順序做，每一步都留 log）

工作目錄：`$SOLO/B/mini`。和 A 同一個劇本，但 agent 的 CPU 換成 **pi**。
重點是：**「aos 包一層 pi」跟「直接用 pi」到底差在哪」**——多打了幾個指令、多等了幾回合、
看不看得見它在幹嘛、記憶跑到哪裡去了。

## 步驟 0：準備素材

```sh
mkdir -p "$SOLO/B/mini/.aos"
cp -r "$TEMPLATE/." "$SOLO/B/mini/"
cd "$SOLO/B/mini"
make 2>&1 | tail -3
```

## 步驟 1：開機（pi 引擎）

```sh
$AOS agent init --engine pi
cat .aos/agents/*/engine.json
```

**觀察**：印了什麼？`engine.json` 裡的 `provider`／`model`／`session_id` 是什麼？
文件說預設 `deepseek`／`deepseek-v4-flash`——實際是不是？
**有沒有任何地方告訴使用者「你需要 `DEEPSEEK_API_KEY`」？**（先不要 unset key，那是 D 的工作。）

## 步驟 2：交代任務

```sh
$AOS state
$AOS say "把 src/parse.cpp 裡的 parse() 改成回傳 std::optional<std::string>：找不到 '=' 時回傳 std::nullopt。src/parse.hpp 的宣告和 src/main.cpp 的呼叫端也要一起改，tests/test_parse.cpp 也要跟著改。改完跑 make 確認測試會過。"
$AOS state
$AOS listen --once
```

## 步驟 3：推進

pi 引擎一個 step 內就會做完一整串工具操作，回合數需求比 lmstudio 少很多。

```sh
timeout 900 $AOS run . --step 1 > run1.log 2>&1 ; echo "run1 exit=$?" ; cat run1.log
$AOS listen --once
git diff --stat -- src tests ; git diff -- src tests | head -60
make 2>&1 | tail -5
```

**觀察並記錄**：
- 一個 step 花了幾秒？跑的時候 `$AOS state` 看得出「正在跑 pi」嗎？（開背景 run 再打 state 試。）
- `.aos/agents/*/history.json` 裡有什麼？文件說它「只是 aos 端的鏡射」——鏡射得完整嗎？
  `$AOS listen` 看得到 pi 做了哪些工具動作，還是只有最後一段文字？
- pi 自己的 session 檔在哪？（找找 `~/.pi`、`~/.local/share/pi` 之類；**只讀不改**。）
  aos 的世界資料夾與 pi 的 session 是兩套記憶——使用者要怎麼知道？

## 步驟 4：追問兩輪

```sh
$AOS say "跑一下 make，把測試結果貼給我"
timeout 900 $AOS run . --step 1 >> run1.log 2>&1
$AOS listen --once | tail -30

$AOS say "剛才那個改動，為什麼 main.cpp 也要動？"
timeout 900 $AOS run . --step 1 >> run1.log 2>&1
$AOS listen --once | tail -30
```

**關鍵觀察**：第二次追問時，pi **記不記得**第一次做過什麼？
（`engine.json` 裡有 `session_id`——它有沒有真的被沿用？看 pi session 檔的大小／時間戳。）

## 步驟 5：工具登記表對 pi 有沒有用

```sh
ls .aos/tools/
$AOS say "列出 .aos/tools/ 裡有哪些工具，然後告訴我你自己能用哪些工具"
timeout 900 $AOS run . --step 1 >> run1.log 2>&1
$AOS listen --once | tail -25
```

**記錄**：pi 引擎看不看得到世界的工具登記表？兩套工具觀念並存，使用者怎麼分？

## 步驟 6：**pi 對照組**（必做）

```sh
rm -rf "$SOLO/B/mini-pi" ; mkdir -p "$SOLO/B/mini-pi"
cp -r "$TEMPLATE/." "$SOLO/B/mini-pi/"
cd "$SOLO/B/mini-pi"
time (timeout 900 pi -p "把 src/parse.cpp 裡的 parse() 改成回傳 std::optional<std::string>：找不到 '=' 時回傳 std::nullopt。src/parse.hpp、src/main.cpp、tests/test_parse.cpp 都一起改。改完跑 make 確認測試會過。" > pi.log 2>&1) ; echo "exit=$?"
tail -30 pi.log ; make 2>&1 | tail -3
```

再做一次追問，測「直接用 pi 的多輪對話要幾個指令」（`pi --help` 看有沒有 `--continue`／`-c` 之類）。

**這一題的核心對照**：既然 aos 的 CPU 就是 pi，**多包這一層，使用者到底多付了什麼、換到了什麼？**
用具體數字回答（指令數、秒數、看得見的狀態、記憶落在哪）。

## 步驟 7：收尾

- `kind=bug` 的寫 `$SOLO/B/repro/B-NN.sh`（乾淨資料夾起跑、絕對路徑、`EXPECT:`／`ACTUAL:` 各一行）。
- 報告寫進 `-o`，同時整份貼在最終回覆。
