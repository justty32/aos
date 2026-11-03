# 任務 B：劇本 1（改一個函式）——pi 引擎，走完整條，數指令

你的代號是 **B**。先完整讀下面的共同守則，再照劇本做。

---

<!-- COMMON -->

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
