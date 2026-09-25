# 網路查證：litellm、Anthropic 的態度、社群 proxy（Sonnet 查，2026-09-13）

← [README](README.md)（pi 原始碼分析在那裡）

> 每條都附來源網址。個人信箱那句是查證 agent 自己加的，跟結論無關。

# 查證報告：Claude Max 訂閱 OAuth token 拿來打自己程式的可行性

（以下每點先講結論，再列依據來源與網址；查看日期一律為 2026-09-13，若來源本身有發布日期會另外標註）

## 分檔目錄

> 2026-09-25 整理：原檔 10 KB 超過門檻，按標題逐字拆進 [`web-findings/`](web-findings/01-litellm-與官方態度.md)；本檔只留前言與目錄（原路徑保留當入口）。

| # | 檔 | 段落 | 大小 |
|---|---|---|---|
| 1 | [01-litellm-與官方態度.md](web-findings/01-litellm-與官方態度.md) | 一、litellm 支不支援用 Claude 訂閱 OAuth 打 Anthropic？；二、Anthropic 官方對「第三方拿訂閱 OAuth 打 API」的態度 | 5.7 KB |
| 2 | [02-社群現成的做法.md](web-findings/02-社群現成的做法.md) | 三、社群現成的做法（本地 proxy，最多列六個）；給決策者的三句話 | 4.2 KB |
