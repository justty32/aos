# 2026-10-15 通用 kernel：判官是一個 agent，閘門照舊

← [討論紀錄](README.md)｜前情：[kernel 截流](2026-10-15-kernel-intercept.md)、[LLM kernel](2026-10-15-llm-kernel.md)｜規範：[N-42](../docs/NORMS/09-kernel.md)、[N-16 信箱](../docs/NORMS/05-基礎設施-窗.md)、[N-28](../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-20](../docs/NORMS/07-基礎設施-組合子.md)｜概念：[C-47、C-11、C-15、C-29](../docs/CONCEPTS/04-kernel.md)、[C-46](../docs/CONCEPTS/05-agent.md)

## 原文（10-15，照記）

「規範這塊，我們就先做兩種kernel，一個用於管理LLM呼叫，一個則是通用的管理(以agent作為判斷)，然後都基於daemon。具體機制再來規劃。」（N-42）

「kernel就是以inst/loop/daemon為基礎，能夠管理某一inst是否被執行的，一個正在執行，或是被執行的inst。」（C-47）

「都隨意」（10-15，答六個未決）

「管LLM那塊，這塊很多時候都是確定性的……這個沒啥可說的。」

## 決定（使用者 10-15 定）

- 第二種 kernel＝通用管理，**判斷交給 agent**；基於 daemon。
- 排程看呼叫樹的特性，由子葉彙總，寫在 `_metainfo`；巢狀卡死不防護（N-20 精神）。
- 六個原未決（使用者「都隨意」，照建議）：
  1. 判官不看信的 stdin 摘要；要就作者寫進 `_metainfo.summary` 一句。
  2. 判官腦先不挑：LM Studio 小模型＋嚴格 schema；判不好就退回規則。
  3. `human` 格：人正在回信就算佔格；回信落檔即釋放，`timeout_ms` 到也釋放。
  4. 拍距 `interval_ms` 2000；信少就走省判官那條。
  5. 判官不能「換隊」；只回三種話，級數仍由閘門填。
  6. 第一種先不併進第二種，兩支各自跑；跑順再併。

## 結論（AI 整理，待使用者確認）

- **管什麼**：任何被閘門包住的 inst（不限腦）。每封信只有三種結果：**現在跑**、**不跑**（附代號與白話，N-29）、沒說（＝這拍不是它）。資源種類＝`_metainfo.resource` 一個字（`llm`／`gpu`／`cpu`／`disk`／`net`／`human`），kernel 設定 `slots` 裡每種有幾格（C-10）；`human`＝人的注意力也是外部 PU（C-28、C-29），格數 1。
- **請求怎麼到**：**閘門不改**，`mailbox` 指到通用 kernel 的信箱；信的形狀同第一種。第一種是第二種的特例：判官換成規則腳本。
- **身體一拍**（daemon 底下一個 loop，照 LLM kernel 的骨架）：收殘信→過期／額度照舊→**問判官**→照答案認領、真跑、回信。判官＝設定 `judge` 一格 inst（C-15），預設是 `bob/` 式 agent。
- **判官回的 stdout**：`{"run": [id…], "reject": [{"id", "error": {code, msg}}]}`；`run` 超過空格的截掉；不認得的 id 忽略。
- **後援**：判官這拍沒給合法答案（非 0、逾時、形狀不對、`halted`）＝這拍用第一種的確定規則（級數＋aging＋先來後到）；`judge_error` 記原因（不設連錯上限，見 [原則 § 決定](2026-10-15-principles/01-原文.md#決定)）。
- **判官自己的腦不走自己**：它的 `brain` 直接指 LLM kernel 的閘門或直接叫，不指通用 kernel 的信箱（否則判官排隊等判官）。
- **跟 N-20**：判官的答案不保證可重現；kernel 重起 `cur/` 殘信照第一種回 `KernelRestarted`。
- **kernel 公告**：判官 reject 的理由將來貼公告欄；公告欄在哪、格式，使用者說晚點再說。

## 動工自定點

AI 自己定的、等使用者看：

- **一拍＝一段忙碌期**：一拍裡一封一條執行緒、各自一支子程式，誰跑完就放格、馬上再決定；沒有在跑的才結束這拍。human 格等人時，llm／cpu 照樣排得動；子程式都在 loop 起的那個行程群組裡，收工整群收。`waited_runs` 在一拍裡不長（另給 `waited_ms`）。
- **判官的輸入輸出**（使用者「剩下都隨意」）：stdin＝state 窗的子集 `queue`／`running`／`slots`／`budget`（同一份物件、不是新格式，C-48），兩種判官都這樣（[實跑](2026-10-15-judge-live.md)）；stdout 見上，同一個 id 出現兩次＝形狀不對。
- **省判官的「局面」**＝排隊名單＋在跑名單＋各資源空格；記在 state 窗，跨拍也沿用：局面沒變＝不再問；有空格則由補位跑（[judge-live § 補位](2026-10-15-judge-live.md#決定補位使用者-10-15照建議做補位)）；格全滿不問（[judge-live2](2026-10-15-judge-live2.md)）。
- **資源**：沒寫或寫了 `slots` 沒有的＝`ResourceUnknown`。`budget` 只管 `llm` 的信。
- **判官環境**：kernel 跑判官一個 key 都不碰。
- **agent 判官**：取最後一句裡第一個 `{` 到最後一個 `}`；沒用 `_tool` schema 硬約束（小模型錯就退回規則）。
- **新增的 key**：kernel 設定 `slots`（物件）、`judge`；信不加 key。
