# 任務 D：劇本 4＋5——錯誤路徑指不指路、以及「多打了幾個指令」的總帳

你的代號是 **D**。先完整讀下面的共同守則，再照劇本做。

---

<!-- COMMON -->

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
