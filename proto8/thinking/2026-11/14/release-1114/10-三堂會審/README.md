# 三堂會審（11-14 16:12）

← [release-1114](../../release-1114.md)

- 原文：[fable](fable.md)、[Argon](argon.md)、[astra](astra.md)；匯總：[ok-release-fable-1 匯總 v1](匯總-v1.md)。
- 題目與材料：七題照 fable 出題稿，材料是預覽頁抽出的純文字（圖與演示看不到）。

- 依據：使用者 15:48 經全景頁（fable 轉，逐字）「好了之後再派fable, argon, astra三堂會審，不用給他們任何背景知識，就純給他們看，讓他們給意見。我總覺得有點不通順...」；之後「思考程度拉高...拉到最高」「三位都要」。
- **例外**：這次三位不讀 wf 規矩與知識庫、不給任何背景，依據是上面那句原話（平常每隻 agent 都要先讀必讀清單）。
- 出題：team/fable/cold-review-brief-v1.md 的七題照貼。材料：drafts/v3/landing.zh.html（16:03 W21 版）抽出的純文字 `page.txt`，註明圖與演示看不到。三位同一份 `prompt.txt`，各自獨立、不互看、一次性呼叫、不掛進樹。
- 三位與思考程度（都是各自最高）：
  - fable：本機代理 `claude-fable-max`（乾淨的一隻，不是 ok-release-fable-1）→ `out-fable.txt`
  - astra：本機代理 `chatgpt-gpt-6-astra-max` → `out-astra.txt`
  - Argon：`agy --model "Gemini 4 Argon (High)" --mode plan` → `out-argon.txt`
- 叫法：`ask-proxy.py`（本機代理，不帶金鑰）、agy 同 argon/ 先前的寫法。三份 scan --private 0 筆。
- 匯總：ok-release-fable-1；匯總給使用者看之前不改頁面。
