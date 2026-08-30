# 任務 C：劇本 2＋3——狀態可見性、中斷復原、隔天回來記憶還在不在

你的代號是 **C**。先完整讀下面的共同守則，再照劇本做。

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

你關心的不是「改得對不對」，而是**「我看不看得出來它在幹嘛、死了沒、記不記得我」**。
兩個引擎都要試（lmstudio 與 pi 各一個世界）。

## 步驟 0：兩個世界

```sh
mkdir -p "$SOLO/C/ws-lm/.aos" "$SOLO/C/ws-pi/.aos"
cp -r "$TEMPLATE/." "$SOLO/C/ws-lm/"
cp -r "$TEMPLATE/." "$SOLO/C/ws-pi/"
cd "$SOLO/C/ws-lm" && $AOS agent init
cd "$SOLO/C/ws-pi" && $AOS agent init --engine pi
```

## 步驟 1：三種「正在忙」看不看得見

在 `ws-lm` 丟一個夠久的任務，把 `run` 放背景，然後**每 5 秒**打一次狀態指令，記下**每一個時間點
`aos` 告訴你什麼**：

```sh
cd "$SOLO/C/ws-lm"
$AOS say "讀 src/parse.cpp 和 src/parse.hpp，然後寫一份詳細的重構計畫給我"
( timeout 900 $AOS run . --step 9 > run.log 2>&1 ; echo "run exit=$?" >> run.log ) &
RUNPID=$!
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  echo "=== t=$((i*5))s ==="
  $AOS state
  echo "-- status.json:" ; cat .aos/agents/*/status.json
  echo "-- state.json phase:" ; cat .aos/state.json
  sleep 5
done
wait $RUNPID ; cat run.log
```

**要回答的問題**（每一個都要有實測證據）：
1. 「等 LLM 回應中」看得出來嗎？`status` 欄位實際出現過哪幾個值？把出現過的值全部列出來。
2. 「正在跑工具」看得出來嗎？（`state.json` 的 `running[]` 有沒有東西、停留多久）
3. 已經跑了幾回合、還要跑幾回合、這回合花多久——`aos` 有沒有任何指令告訴你？
4. **有沒有一個指令能同時回答「它在幹嘛」**，還是要打 2–3 個、外加自己 `cat` `.aos/` 裡的檔案？
   把「回答『它現在在幹嘛』實際需要的最少指令數」寫成一個數字。
5. `run` 的 stdout 印的是 `turn N: M insts`——這行對使用者說明了什麼？夠不夠？

## 步驟 2：Ctrl-C 中斷與殘留

```sh
cd "$SOLO/C/ws-lm"
$AOS say "再幫我看一次 src/main.cpp，寫一份詳細分析"
( timeout 900 $AOS run . --step 9 > run2.log 2>&1 ) &
RUNPID=$!
sleep 20
kill -INT $RUNPID          # 模擬使用者按 Ctrl-C
sleep 3
echo "== 中斷後 =="
$AOS state
cat .aos/turn
find .aos/batch -maxdepth 3 2>/dev/null | sort | head -40
cat .aos/agents/*/status.json
ps aux | grep -c "[a]os agent step"
```

**要回答**：
- 中斷後 `aos state` 說什麼？它說的是真的嗎（真的有東西在跑嗎）？
- `.aos/` 殘留了什麼？`batch/<turn>/insts/` 有沒有搬走但沒跑完的指令？`turn` 有沒有加？
- **重開 `run` 會不會把中斷那回合補跑**？測：`timeout 600 $AOS run . --step 3 > run3.log 2>&1 ; cat run3.log`
  ——那條被中斷的指令有沒有結果（`.aos/batch/*/out/`）？
- 有沒有任何指令告訴使用者「上次跑到一半死了」？
- **有沒有孤兒行程留下來？**（`ps` 那行的數字）

## 步驟 3：換一個 shell 回來，記憶還在不在

lmstudio 世界：

```sh
cd "$SOLO/C/ws-lm"
env -i HOME="$HOME" PATH="$PATH" bash -c 'cd '"$SOLO"'/C/ws-lm && '"$AOS"' say "剛才我請你做了什麼？" && timeout 900 '"$AOS"' run . --step 6 > run4.log 2>&1 ; '"$AOS"' listen --once | tail -20'
```

pi 世界（同一件事）：

```sh
cd "$SOLO/C/ws-pi"
$AOS say "把 parse() 的失敗表示法改成 std::optional"
timeout 900 $AOS run . --step 1 > pirun1.log 2>&1
env -i HOME="$HOME" PATH="$PATH" DEEPSEEK_API_KEY="$DEEPSEEK_API_KEY" bash -c 'cd '"$SOLO"'/C/ws-pi && '"$AOS"' say "剛才我請你做了什麼？" && timeout 900 '"$AOS"' run . --step 1 > pirun2.log 2>&1 ; '"$AOS"' listen --once | tail -20'
```

**要回答**：
- 兩個引擎的記憶各自存在哪個檔案？（`history.json` vs pi session）大小、有沒有真的被沿用。
- 換 shell 後記憶還在嗎？**哪一個引擎會失憶？** 有沒有任何警告？
- `listen` 不帶 `--once` 是 200ms 輪詢的跟讀；它是「從頭印」還是「只印新的」？
  **使用者隔天回來想看昨天的對話要怎麼看？**（試 `listen --once`、`cat .aos/agents/*/log.md`，數指令。）

## 步驟 4：`aos talk` 到底能不能用

```sh
cd "$SOLO/C/ws-lm"
echo "你好" | timeout 120 $AOS talk ; echo "talk exit=$?"
timeout 120 $AOS talk --interface pi < /dev/null ; echo "talk-pi exit=$?"
```

**記錄**：`talk` 在沒有另一個 `run` 推進的情況下會怎樣？會不會永遠卡住？
文件說 `--interface pi` 「CLI 會清楚回報它尚未內建」——實際訊息是什麼？

## 步驟 5：pi 對照（`compare` 欄位）

同樣三件事，直接用 pi 做要幾步：
- 「它現在在幹嘛」→ pi 前台跑的時候你看得到什麼？（跑一個 `pi -p "..."` 觀察它的輸出）
- 「Ctrl-C 之後」→ pi 被 Ctrl-C 之後留下什麼、能不能接續（`pi --help` 找 resume/continue）？
- 「隔天回來看昨天的對話」→ pi 要幾個指令？

每條發現的 `compare` 欄位都要有這種具體對照。

## 步驟 6：收尾

- `kind=bug` 的寫 `$SOLO/C/repro/C-NN.sh`（乾淨資料夾起跑、絕對路徑、`EXPECT:`／`ACTUAL:`）。
- 報告寫進 `-o`，同時整份貼在最終回覆。
