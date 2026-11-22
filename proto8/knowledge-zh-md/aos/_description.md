# `knowledge/aos/_description.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/_description.md`，跟到正本 commit `65bb2891f`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/_description.md#/…` 對的就是它。改請改正本，再照 [README](../README.md) 的做法跟上這份。

---

**`#/aos in one page`**

# 一頁看懂 aos

aos 是什麼、你需要的八個詞，還有怎麼查更多。

aos 把 AI agent 當成一般的 Linux 程序，跑在資料夾裡。你就是其中一個 agent。你碰到的每樣東西都是資料夾或檔案；每個動作都是一次工具呼叫。

八個詞：

- **定義**：一個說明 agent 是什麼的資料夾（它的原始碼）。不要改你自己的：`self_*` 工具改的是你 stack 裡你自己那份複本。
- **stack**：一個正在跑的 agent 存放狀態的資料夾（它的記憶）。你的是 `$AOS_STACK`。
- **工作區（ws）**：你在上面工作的資料夾（你的外部記憶）。你的是 `$AOS_WS`。你給工具的路徑都相對於它。
- **daemon**：那台機器。它跑 agent，並記一張它們的表（名字、phase、原因）。你的是 `$AOS_DAEMON`。
- **proc**：daemon 底下一個正在跑的東西。正在跑的 agent 就是一個 proc。
- **kernel**：你送出請求的地方（啟動一個 proc、問腦）。它決定這個請求要不要跑、什麼時候跑。daemon 本身就是最簡單的 kernel；前面可以再擺一個 kernel 站（kernel station），它可以拒絕。見 aos/kernel.md。
- **信／信箱**：proc 之間怎麼說話。一封信是一個裝著 letter.json 的資料夾，丟進一個信箱資料夾。問腦就是寄一封信給 llm kernel。
- **工具**：一個你可以呼叫的資料夾。你用一個 JSON 物件呼叫它；它在 stdout 回覆。失敗時它印一行 `toolname: error: Code reason`。

五條規則：

1. 絕不手動改定義，也不碰別的 agent 的 stack。要改你自己，用 `self_*` 工具；要做新種類的 agent，用 `agent_def`（見 `aos/rules.md`）。
2. 用工具，不用 shell 花招。沒有合適的工具，就直說，不要自己湊。
3. 工具失敗時，讀那行錯誤。代號告訴你是哪一類問題；把它修好，再重試一次。不要一直重試同一個呼叫。
4. 路徑都相對於你的工作區，除非工具另外說明。
5. 如果某件事被拒絕（kernel 說不、預算用完了），那是一個決定，不是 bug。回報它或調整做法；不要硬來。

這些檔案描述的是哪個版本：知識資料夾裡（`aos/` 的上一層）的 `.aos-source.json` 記著它們是從 aos repo 的哪個 commit、在什麼時候抄來的；repo 可能比較新。沒有這個檔，就是版本不明的複本。

想知道更多，讀這個檔旁邊的檔案：這個資料夾裡的 `_index.json` 用一句話說每一份在講什麼。一頁是一個 `.md` 檔（文字，一個標題一節）或一個 `.json` 檔（簡短的資料）。`json_get` 和 `json_ls` 兩種都能讀：`aos/me.md#/What is in your stack` 是那個標題底下的那一節，對 `aos/me.md` 用 `json_ls` 會列出它的標題；規則在 `aos/tools/json_get.md#/JSON tools: reading markdown`。問題是關於你自己，就從 `aos/me.md` 開始；工具失敗了，就從 `aos/errors.md` 開始；有東西不能用，就從 `aos/troubleshooting.md` 開始；你是 eca 的話，就從 `aos/eca_reading.md` 開始。
