# 回答配對（reply-match-1114）：agent 的回答對得到是回哪封信，ask／listen 不再只能拿最新那則

← [2026-11-14](README.md)｜[thinking](../../README.md)｜線工具 ok-pilot（部長 head-tools；第 1 階段只設計，施工等 head-tools 核准）

## 由來

- wf/advices〈信件與溝通〉「aos-agent 沒有 ask」：11-14 ok-pilot 只做了跟 subagent 工具 op ask 同語意的 `aos-agent ask`（2ef627f1b），沒有配對信名。
- 同日投稿 `wf/temp/ok-pilot/aos-advice/回答對不到是哪封信.md`。
- head-tools 11-14 交辦本題。設計要寫清楚五件事：history 多記什麼、ask／listen 怎麼配、eca 做不做、對現有 history 讀者的影響、換樹要帶哪些檔。proto8 不留舊格式相容。

## 檔案

| 檔 | 內容 |
|---|---|
| [01-備料](reply-match-1114/01-備料.md) | 寫 history 和讀 history 兩方的現況（gpt-6.1-sol 兩隻唯讀查原始碼），加上別線的定案與前置依賴 |
| [02-fable稿](reply-match-1114/02-fable稿.md) | fable 的獨立設計，原文 |
| [03-計劃](reply-match-1114/03-計劃.md) | ok-pilot 的計劃 v2（v1 經 Argon 審後修改），含方向問題 |
| [04-Argon原文](reply-match-1114/04-Argon原文.md) | Argon 審 v1 的原文 |
| [05-採納表](reply-match-1114/05-採納表.md) | Argon 意見逐條採不採 |

## 進度

- 11-14 14:00 備料交齊；fable 稿到；03 v1 寫好，送 Argon 審。
- 11-14 14:19 Argon 審完。採納 A1～A3、A6～A15，改回 02 的 `letters.json`，落地改成「寫的一方先進」。03 v2 送 head-tools，第 6 節方向問題請轉專區。
