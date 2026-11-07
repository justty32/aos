# 2026-11-07 把 arknights 敘事庫歸納進 aos 的知識庫體系，藉此大量實跑 aos、挖不足再優化（arknights-kb，長線）

← [thinking README](../../../README.md)｜日 [2026-11-07](../README.md)｜前情：[agent-knowledge](../../05/agent-knowledge/README.md)（`memory` 工具、`knowledge/aos`）、[knowledge-write](../../05/knowledge-write/README.md)（K7：`memory_write`、多庫捷徑，已裁、未實作）、[small-thought](../../05/small-thought/README.md)（`thought` 工具）｜使用者建議：[user-advice](../../../../user-advice/README.md)

本夾照 [user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)：只放使用者原文（整理版、原句全保留）、決定、結論。使用者不在時的代定另列 [代定清單](代定清單.md)（每條：決定了什麼、為什麼、怎麼翻案），挖到的 aos 不足列 [不足清單](不足清單.md)。

## 使用者原文（11-07 上午，整理版，原句全保留）

> 我出門吃早午餐，一兩個小時後回來，能做繼續做。

**試驗場與 gpt**：

> playground那邊準備好，可以讓gpt隨意嘗試，litellm proxy我開好了，盡量用gpt系模型。讓gpt多嘗試各種用法與邊緣情況，你可以派隊伍去做，一次嘗試多個，畢竟我們一個daemon下可以掛多個daemon和多個agent，然後共享一個llm kernel。

**分工**：

> 當然，系統設計，與架構規劃仍要由claude系去做。

**目標**：

> 啊，漫無目的的嘗試也不好，我這邊給個目標：~/repo/narratives/arknights那塊，幫我歸納進我們的aos資料庫體系。慢慢做，一邊做一邊看有沒有不足的，就再規劃與優化。

**隊伍**：

> 隊伍內可以有fable成員從旁規劃，opus成員負責審查。

**效能**：

> 記得開監控，系統效能這塊不要把我電腦搞crash了，但我也沒在做其他事，所以80%以內都還好。

**優化方向（確定性）**：

> 可以參考user-advice內的，優化目標就是確定性，我這邊給幾個建議：shell工具一開始可以隨意開放，後面改成謹慎，最後改成全部都有專屬工具。git是很好的東西與重要概念。讓agent專精特定領域，領域越是狹小，能夠變成工具的地方就越多，所需的llm model就越是不用那麼高級，token也能省下來。

**規模與嵌套**：

> agent可以成千上萬個，反正可以sleep，交給llm kernel的thinking請求也有排程，並且thinking請求還可以經過一些額外關口，比如一個隊伍使用一個llm_kernel，然後這個llm_kernel負責排程與將請求轉交給另一個llm_kernel，直到轉交給實際打API的llm_kernel，一切都可以嵌套。對，工具也是，工具可以是開一個agent做事，或是將請求交給專精此道的kernel，所以才說會有成千上萬個agent。就好比LLM的神經元，不是每個區域都會被激活。

> 好了，說了有點多，總之去做吧

**追加（11-07 上午，經頂層轉述，逐字）**：

> 記得留下記錄，以及這趟過程中的得失。過程中可以隨意擴充工具，或agent定義。或者說，我期待看到你們自我演化出一大堆定義(原始碼)，當然，最好是帶上一些說明文件讓我好懂。

## 已定（使用者說的）

- 目標：把 `~/repo/narratives/arknights` 歸納進 aos 的資料庫（知識庫）體系；慢慢做，邊做邊找不足、再規劃與優化。
- 系統設計與架構規劃由 Claude 系做（fable 從旁規劃、opus 審查）；gpt 系照圖施工、雜活，aos 裡跑的 agent 的腦盡量用 gpt 系。
- 優化目標＝確定性：shell 工具先開放 → 再謹慎 → 最後全部專屬工具；git 是重要概念；agent 專精窄領域，越窄越能工具化、模型越便宜、token 越省。
- 規模：agent 可以成千上萬（可 sleep）；llm kernel 可嵌套轉交（隊伍 kernel → … → 實打 API 的 kernel）；工具也可以是開 agent 或轉交給專精的 kernel。
- 效能：開監控，80% 以內都可以。
- 留紀錄與得失；放手擴充工具與 agent 定義，期待系統自我演化出大量定義（原始碼），每批附讓使用者好懂的說明文件。

## 決定與結論

（隨進度補；每段只寫結論，細節在分檔。）

- **第 0 輪盤點（11-07 上午）**：語料的 `lore/` 已是一套中文詞條庫（5390 檔、約 361 萬漢字、連結完整），`corpus/` 是 1.1 GB 原文（不進 git）；aos 這邊 `memory` 只能讀、`memory_write` 沒做、節點名只收英數、kernel 嵌套轉交要靠自寫的轉交函數且 token 帳會斷。試驗場 `~/code/playground-ak/` 已能讓 gpt 腦叫工具。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-盤點-語料](01-盤點-語料.md) | arknights 敘事庫長什麼樣（codex 寫，事實與數字） |
| [01-盤點-aos](01-盤點-aos.md) | aos 現有知識庫／agent／kernel 能力與試驗場實跑 |
| [交棒](交棒.md) | 隨時可接手的進度與下一步 |
| [代定清單](代定清單.md) | 使用者不在時隊長代定的事（可翻案） |
| [不足清單](不足清單.md) | 實跑挖到的 aos 不足，排優先 |
| [得失](得失.md) | 每輪做了什麼、得到什麼、失去／踩到什麼、下輪怎麼改 |
