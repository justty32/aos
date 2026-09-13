# 試玩任務 r4：你是第一次碰 aos 原型的新使用者（第四輪：只驗 LLM 那層，看上一輪的修法有沒有真的解決）

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**你的角色是新來的使用者**，不是開發者。**只准讀這三個入口與它們連出去的文件**：`proto4-3/README.md`（作業系統那層）、`proto4-5/README.md`（叫 LLM 的兩層）、`proto4-6/README.md`（只看「逐步 Python」那節）。**不要去讀 `proto4/notes/`（設計筆記、前幾輪的報告都在那，不准看）、不要讀原始碼**——除非 README 讓你卡住、非讀不可，那也算一條「README 沒講清楚」的發現，要記下來。

**不要改 repo 裡任何檔案。** 你玩的東西全部放在 `/tmp/play4-<你的名字>/` 底下。**不要 git commit／push**。不要開其他 agent。跑 daemon 一律用暫存家（`AOS_DAEMON_HOME=/tmp/play4-…/home`），玩完把你開的 daemon 停掉（`aos-daemon-ctl stop`）。

**LLM 只准打本機**：LM Studio 已經開著，OpenAI 相容端點 `http://localhost:1234/v1`，模型 id `google/gemma-4-e4b`，不用 key。**不要碰 DeepSeek、不要用任何 `*_API_KEY`**（會花錢）。每個請求問短一點（一句話）。

## 要玩什麼（照順序，每步記下「我以為會怎樣 vs 實際怎樣」，並計時）

1. **從零到第一次 `aos-llm call` 拿到回答**：只看 proto4-5 README，寫 endpoints 檔、`models`、`call`。記幾分鐘、有沒有任何一步要猜。故意：模型名打錯（記它花了幾秒、有沒有花 token）、base_url 指到沒人聽的埠。
2. **LLM 排程當 kernel module**：架 OS 層（daemon → init 帶 `--module` → boot），照 README 改 `K/llm/endpoints.json`，用 `aos-kernel llm` 丟請求：一次 `--wait`、一次不等、同一個名字再丟一次（內容一樣）、同一個名字丟不一樣的內容。然後 **把 daemon 停掉再丟一張 `--wait 3`**，看它怎麼說、`K/syscalls/` 裡有沒有留下東西、daemon 重開後那張會不會跑。
3. **一支 Python 逐步程式走 `llm_submit → wait_for → 讀答案`** 三格，排進 kernel 跑完。中途 `aos-kernel ls` 看它在等的時候長什麼樣。跑完 `--reset` 再排一次，看會不會卡。
4. **問自己五個問題**（每條 1–5 分＋至少兩個具體例子，例子要帶指令或檔名）：
   ① 容易上手：從零到第一支 LLM 逐步程式跑起來，要幾步、幾個指令、幾分鐘？
   ② 容易理解：endpoint／request／module／`llm_submit` vs `llm`／`strict_model`／結果檔的三組欄位，README 一講你就懂了嗎？哪個讓你想歪？
   ③ 複雜的東西有沒有藏好：有沒有哪個你本來不該知道的細節被迫知道？
   ④ 外層的控制結構簡單但全面：`aos-llm` 兩個子命令＋`aos-kernel llm` 一個，夠不夠？哪裡重疊、哪裡缺？
   ⑤ 要背的東西少：你得記住幾個檔名、幾個旗標、幾個環境變數？

## 交出來

一份 markdown 直接回給我（不要寫進 repo），繁體中文、大白話、120 行以內：

- 開頭：一句總評 ＋ 五條各幾分。
- 中間：照 1–3 的順序寫經歷與發現，每條發現用「現象 → 我期待 → 建議」三段一行。
- 最後：**前五名最該改的**（按「改了對新手幫助最大」排），每條一句話＋預估改動大小（小／中／大）。如果你覺得已經沒有值得改的，直說。
- 附：你實際跑過的指令清單（精簡）。
