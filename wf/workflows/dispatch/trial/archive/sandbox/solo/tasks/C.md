# 任務 C：劇本 2＋3——狀態可見性、中斷復原、隔天回來記憶還在不在

你的代號是 **C**。先完整讀下面的共同守則，再照劇本做。

---

<!-- COMMON -->

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
