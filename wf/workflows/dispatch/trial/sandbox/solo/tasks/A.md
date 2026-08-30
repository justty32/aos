# 任務 A：劇本 1（改一個函式）——lmstudio 引擎，走完整條，數指令

你的代號是 **A**。先完整讀下面的共同守則，再照劇本做。

---

<!-- COMMON -->

---

# 你的劇本（照順序做，每一步都留 log）

工作目錄：`$SOLO/A/mini`。你要在這裡當一個「想改自己程式碼的使用者」。

## 步驟 0：準備素材（不算進指令數）

```sh
mkdir -p "$SOLO/A/mini/.aos"
cp -r "$TEMPLATE/." "$SOLO/A/mini/"
cd "$SOLO/A/mini"
make 2>&1 | tail -3          # 確認素材本來就能編、測試會過
```

## 步驟 1：開機

```sh
$AOS agent init            # 不帶 --engine，預設 lmstudio
```

**觀察並記錄**：它印了什麼？（有沒有告訴你 agent 叫什麼名字、建在哪個資料夾、用哪顆 CPU、哪個模型？）
`.aos/` 裡多了什麼？`cat .aos/agents/*/engine.json`、`cat .aos/agents/*/persona.md`、`ls .aos/tools/`。
**這時候使用者知道要「另開一個視窗跑 run」嗎？有沒有任何提示？**

## 步驟 2：交代任務

```sh
$AOS state                                     # 開工前的狀態長怎樣
$AOS say "把 src/parse.cpp 裡的 parse() 改成回傳 std::optional<std::string>：找不到 '=' 時回傳 std::nullopt。src/parse.hpp 的宣告和 src/main.cpp 的呼叫端也要一起改，tests/test_parse.cpp 也要跟著改。改完跑 make 確認測試會過。"
$AOS state                                     # 說完話之後的狀態長怎樣（有沒有變？）
$AOS listen --once                             # 使用者這時候看得到自己剛說的話嗎
```

**記錄**：`say` 印了什麼？`state` 有沒有反映「有一封未讀信」？

## 步驟 3：推進世界（模擬「另一個視窗」）

```sh
timeout 1200 $AOS run . --step 15 > run1.log 2>&1 ; echo "run1 exit=$?"
tail -40 run1.log
```

**在 run 跑的同時**（可以先把 run 放背景 `&`，再輪流下指令）用另一組指令觀察：

```sh
$AOS state ; cat .aos/agents/*/status.json ; $AOS listen --once
```

問自己：**「它現在在幹嘛？在想？在跑工具？在等 LLM？還是死了？」從 `aos` 指令看得出來嗎？**
把你為了回答這個問題實際打了幾個指令、翻了哪幾個檔案記下來。

## 步驟 4：看結果、追問

```sh
$AOS listen --once > listen1.txt 2>&1 ; wc -l listen1.txt ; cat listen1.txt
git diff --stat -- src tests 2>&1 ; git diff -- src tests 2>&1 | head -60
make 2>&1 | tail -5
```

如果 15 回合還沒改完，再推：`timeout 1200 $AOS run . --step 15 >> run1.log 2>&1`。
**最多再推兩次**（總共 45 回合）。還是沒改完就記一條 `kind=cannot`，寫清楚推了幾回合、
每回合平均幾秒、log 裡看到模型在做什麼。

不管改完沒有，都要追問一次：

```sh
$AOS say "跑一下 make，把測試結果貼給我"
timeout 900 $AOS run . --step 9 >> run1.log 2>&1
$AOS listen --once | tail -30
```

**記錄**：追問一句話，實際要打幾個指令、等幾個回合才看到答案？

## 步驟 5：解釋 diff

```sh
$AOS say "用三句話解釋你剛才改了什麼"
timeout 900 $AOS run . --step 6 >> run1.log 2>&1
$AOS listen --once | tail -20
```

## 步驟 6：**pi 對照組**（必做，這是 `compare` 欄位的來源）

把素材重來一份乾淨的，直接用 pi 做**完全同一件事**，計時、數指令：

```sh
rm -rf "$SOLO/A/mini-pi" ; mkdir -p "$SOLO/A/mini-pi"
cp -r "$TEMPLATE/." "$SOLO/A/mini-pi/"
cd "$SOLO/A/mini-pi"
time (timeout 900 pi -p "把 src/parse.cpp 裡的 parse() 改成回傳 std::optional<std::string>：找不到 '=' 時回傳 std::nullopt。src/parse.hpp、src/main.cpp、tests/test_parse.cpp 都一起改。改完跑 make 確認測試會過。" > pi.log 2>&1) ; echo "pi exit=$?"
tail -30 pi.log ; make 2>&1 | tail -3
```

（`pi -p` 若不是正確的一次性用法，先跑 `pi --help` 看清楚再用；把你實際用的指令寫進報告。）

**記錄**：pi 打了幾個指令、幾秒完成、改對了沒；aos 打了幾個指令、幾個回合、幾秒、改對了沒。
這組數字是你報告裡最重要的東西。

## 步驟 7：收尾

- 每條 `kind=bug` 都寫 `$SOLO/A/repro/A-NN.sh`：從乾淨資料夾開始、只用 `$AOS` 絕對路徑、
  結尾 `echo "EXPECT: ..."` 說明應該看到什麼、`echo "ACTUAL: ..."` 印出實際看到什麼。腳本要能重跑。
- 報告寫進 `-o` 指定的檔案，**同時整份貼在最終回覆裡**。
