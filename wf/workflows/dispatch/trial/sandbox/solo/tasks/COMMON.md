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
