# 試玩任務 r3：你是第一次碰 aos 原型的新使用者（第三輪：LLM 兩層 ＋ 三支逐步執行器）

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**你的角色是新來的使用者**，不是開發者。**只准讀這四個入口與它們連出去的文件**：`proto4-3/README.md`（作業系統那層）、`proto4-5/README.md`（叫 LLM 的兩層）、`proto4-6/README.md`（逐步 JSON／Python／Lua）、`proto4-4/README.md`（逐步 lisp，只在你想比較時看）。**不要去讀 `proto4/notes/`（設計筆記、前兩輪的報告都在那，不准看）、不要讀原始碼**——除非 README 讓你卡住、非讀不可，那也算一條「README 沒講清楚」的發現，要記下來。

**不要改 repo 裡任何檔案。** 你玩的東西全部放在 `/tmp/play3-<你的名字>/` 底下。**不要 git commit／push**。不要開其他 agent。`janet` 在 `~/.local/bin/janet`、`lua5.4` 在 `/usr/bin/lua5.4`。跑 daemon 一律用暫存家（`AOS_DAEMON_HOME=/tmp/play3-…/home`），玩完把你開的 daemon 停掉（`aos-daemon-ctl stop`）。

**LLM 只准打本機**：LM Studio 已經開著，OpenAI 相容端點 `http://localhost:1234/v1`，模型 id `google/gemma-4-e4b`，不用 key。**不要碰 DeepSeek、不要用任何 `*_API_KEY`**（會花錢）。每個請求問短一點（一句話），模型小、答得慢很正常，等個十幾秒沒回再算異常。

## 要玩什麼（照順序，每步記下「我以為會怎樣 vs 實際怎樣」）

1. **只看 README 把 OS 那層架起來**（daemon → init → boot → `aos-kernel ls`）。這輪不用細玩它，只記「比起沒看過的人，這段夠不夠順」。
2. **第一層：`aos-llm`**。照 README 寫一份 endpoints 檔，先 `models` 看列表，再 `call` 問一句話，把結果檔打開看。記：結果檔哪幾個欄位你看得懂、哪個看不懂、退出碼跟 README 說的一不一樣。故意弄壞兩樣：模型名寫錯、base_url 指到沒人聽的埠。
3. **第二層：LLM 排程當 kernel module**。照 README 把 module 掛進 kernel（init 時 `--module`），用 `aos-kernel llm` 丟兩個請求（一個 `--wait`、一個不等），看 `ls` 的 module 狀態列、看結果檔在哪。故意：daemon 沒在跑時丟請求；同一個 `--name` 丟兩次。
4. **三支逐步執行器各寫一支你自己的小程式**（不要抄 README 的例子），每支至少四格，然後：
   - **JSON 版**：每格是 inst 格式，其中一格用 `wait_for` 等一個你另外用 shell 慢慢寫出來的檔。
   - **Python 版**：一格用 `aos.call` 叫一個你自己做的 shell 檔（用 `args` 傳參數），一格 `aos.llm_submit` 丟給 kernel、下一格 `aos.wait_for` 等結果、再下一格把回答讀進 state。另外放一段 bytes 進 state，看狀態檔長什麼樣。
   - **Lua 版**：一格用 `aos.llm`（同步）問一句，一格用 `aos.b64` 存個 binary 進 state。
   每支先手動一格一格跑（看 `--status`），再照 README 排進 kernel 讓它自己跑完被收走。
5. **故意弄壞五樣**，每樣記「畫面上看到什麼、我知不知道下一步」：
   - Python 步驟函數丟例外；Lua 那支 `return` 的表少一格；
   - 跑到一半改程式（插一格）；
   - `wait_for` 等的檔永遠不出現，程式排在 kernel 上會怎樣、`ls` 看得出來嗎；
   - `--reset` 之後再跑。
6. **問自己五個問題**（使用者定的標準，每條 1–5 分＋至少兩個具體例子，例子要帶指令或檔名）：
   ① 容易上手：從零到第一支 LLM 逐步程式跑起來，要幾步、幾個指令？
   ② 容易理解：endpoint／request／module／`llm_submit` vs `llm`／`wait_for`／`$b64` 這些詞，README 一講你就懂了嗎？哪個讓你想歪？
   ③ 複雜的東西有沒有藏好：有沒有哪個你本來不該知道的細節被迫知道（檔案放哪、路徑基準、要等下一回合…）？
   ④ 外層的控制結構簡單但全面：三支逐步執行器＋lisp 那支，介面一不一致？哪裡重疊、哪裡缺？
   ⑤ 要背的東西少：你得記住幾個檔名、幾個旗標、幾個環境變數才能日常使用？

## 交出來

一份 markdown 直接回給我（不要寫進 repo），繁體中文、大白話、150 行以內：

- 開頭：一句總評 ＋ 五條各幾分（proto4-5 與 proto4-6 可以分開打）。
- 中間：照上面 1–5 的順序寫經歷與發現，每條發現用「現象 → 我期待 → 建議」三段一行。
- 最後：**前五名最該改的**（按「改了對新手幫助最大」排），每條一句話＋預估改動大小（小／中／大）。如果你覺得已經沒有值得改的，直說。
- 附：你實際跑過的指令清單（精簡）。
