# pi Claude 訂閱 OAuth：原始碼筆記

調查目標是本機安裝的三個套件，版本均為 0.85.1：

- `pi-coding-agent`：`/home/lorkhan/.local/share/fnm/node-versions/v24.14.1/installation/lib/node_modules/@earendil-works/pi-coding-agent/`
- 下文 `$PI_AI`：上述目錄的 `node_modules/@earendil-works/pi-ai/dist/`
- `pi-agent-core`：上述目錄的 `node_modules/@earendil-works/pi-agent-core/`；沒有找到 Anthropic OAuth 或 transport 實作，這層只承接 agent loop。

本機套件只有已發行的 `dist`；以下行號以這份 0.85.1 JavaScript 為準。沒有讀取或抄錄任何 token 值。

## 分檔目錄

> 2026-09-25 整理：原檔 8.6 KB 超過門檻，按標題逐字拆進 [`notes-source/`](notes-source/01-登入常數與-PKCE.md)；本檔只留前言與目錄（原路徑保留當入口）。

| # | 檔 | 段落 | 大小 |
|---|---|---|---|
| 1 | [01-登入常數與-PKCE.md](notes-source/01-登入常數與-PKCE.md) | 1. 登入常數與 PKCE；2. authorization code 換 token；3. refresh 時點與 request；4. auth.json 持久化 | 3.9 KB |
| 2 | [02-provider-與-request-auth.md](notes-source/02-provider-與-request-auth.md) | 5. provider 與 request auth；6. beta、system prompt、工具名；7. SDK 實際補的 wire 細節；8. 預設模型與已知／未知能力；9. LiteLLM 與安全檢查 | 4.3 KB |
