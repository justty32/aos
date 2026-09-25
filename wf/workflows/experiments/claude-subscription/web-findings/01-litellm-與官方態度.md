← [網路查證：litellm、Anthropic 的態度、社群 proxy（Sonnet 查，2026-09-13）](../web-findings.md)（分檔 1/2）｜[下一份](02-社群現成的做法.md)

## 一、litellm 支不支援用 Claude 訂閱 OAuth 打 Anthropic？

**結論：litellm 官方文件上有寫這條路，技術上做得到「轉發」，但底層依賴的正是 Anthropic 現在已經明文禁止、且已經在 2026 年封鎖的那個機制，而且 litellm 自己的 issue 顯示這個轉發功能實作還有 bug，不算穩固。**

- litellm 官方文件《Using Claude Code Max Subscription》教你在 `config.yaml` 開 `forward_client_headers_to_llm_api: true`，讓 Claude Code 送來的 `Authorization: Bearer <oauth_token>`（OAuth token 前綴 `sk-ant-oat01-`）原封不動轉給 Anthropic API，provider 名稱走一般的 `anthropic/claude-...`。文件沒寫最低版本需求，也完全沒提醒這樣做是否符合 Anthropic 政策。
  來源：https://docs.litellm.ai/docs/tutorials/claude_code_max_subscription（查看日期 2026-09-13）
- 但這個功能本身有 bug：BerriAI/litellm issue #19618 指出，litellm 內部有函式會把 `Authorization` header 清掉、只轉發 `x-*` 和 `anthropic-beta` 開頭的 header，導致 OAuth token 常常沒送到、Anthropic 回「x-api-key is required」或「invalid x-api-key」錯誤；OAuth 專用的處理邏輯也曾把 token 誤塞進 `x-api-key` 而不是 `Authorization: Bearer`，格式就不對。
  來源：https://github.com/BerriAI/litellm/issues/19618（查看日期 2026-09-13）
- 另外還有 issue #13380（要求正式支援 pass-through OAuth）、issue #22398（OAuth handler 會覆寫 `anthropic-beta` header，把客戶端自己要帶的 beta flag 弄丟）、discussion #20072（社群在討論怎麼接 Claude 訂閱），都顯示這塊是「有人在拼、常出包」的狀態，不是穩定成熟的官方功能。
  來源：https://github.com/BerriAI/litellm/issues/13380 、 https://github.com/BerriAI/litellm/issues/22398 （查看日期 2026-09-13）
- 更根本的問題：即使 litellm 把轉發修好，Anthropic 伺服器端從 2026 年 1 月起就會直接拒絕第三方帶著訂閱 OAuth token 打過來的請求（見第二點），所以「litellm 支不支援」在 2026 年 9 月已經變成次要問題——就算 litellm 做對了，Anthropic 那邊也不讓過。

## 二、Anthropic 官方對「第三方拿訂閱 OAuth 打 API」的態度

**結論：現在（2026 年 9 月）是明文禁止，不是灰色地帶。Anthropic 已經在伺服器端擋掉，也已經把禁令寫進服務條款，2026 年 4 月起連「包裝 CLI 子程序」這種繞法也一併被封。**

- 2025 年 9 月起 Claude Code 的 GitHub repo 就開始有人回報「credential restriction」錯誤，是最早的徵兆。
  來源：https://github.com/anthropics/claude-code/issues/28091（查看日期 2026-09-13）
- 2026 年 1 月 9 日，Anthropic 在伺服器端上線檢查，開始直接拒絕第三方工具（例如 OpenCode）用 `/connect` 拿到的訂閱 OAuth token，錯誤訊息明講：「This credential is only authorized for use with Claude Code and cannot be used for other API requests.」
  來源：https://www.zbuild.io/resources/news/opencode-blocked-anthropic-2026（查看日期 2026-09-13）
- 有使用者在 OpenCode 的 issue 裡實測，帳號因為用 OAuth 訂閱登入第三方工具而被封，Anthropic 工程師回應「這樣用違反服務條款會被封」。這則 issue 發於 2026-01-05。
  來源：https://github.com/anomalyco/opencode/issues/6930（查看日期 2026-09-13）
- 2026 年 2 月 19 日，Anthropic 正式把這條寫進 Consumer Terms of Service，新增「Authentication and credential use」章節，明文規定：Free／Pro／Max 帳號拿到的 OAuth token，不准用在 Claude Code 和 claude.ai 以外的任何產品、工具或服務——**連 Agent SDK 都算違規**。開發者要串接 Claude 一律得用 API key（Console 或雲端供應商），不能靠訂閱 OAuth 轉嫁。
  來源：https://winbuzzer.com/2026/02/19/anthropic-bans-claude-subscription-oauth-in-third-party-apps-xcxwbn/ 、 https://www.theregister.com/2026/02/20/anthropic_clarifies_ban_third_party_claude_access/（查看日期 2026-09-13）
- 2026 年 4 月 4 日，Anthropic 進一步擋掉「包裝官方 CLI 當子程序、再對外開 API」這種繞路做法（例如 CLIProxyAPI），該工具作者在棄用公告寫：「can no longer access Claude through your subscription without paying extra」，同時 Anthropic 推出「extra usage」（訂閱帳號另外付費加量）作為官方替代方案。
  來源：https://rogs.me/2026/02/use-your-claude-max-subscription-as-an-api-with-cliproxyapi/（文章發布 2026-02-13，內文提及 4/4 生效日；查看日期 2026-09-13）
- 截至 2026 年 9 月的社群整理文章確認：禁令仍然有效，沒有鬆綁跡象；目前公認「不會被擋」的路只有三條——(1) 官方 Claude Code CLI 直接用訂閱、(2) 改用 API key 按量計費、(3) 買 Anthropic 官方的訂閱加量包（extra usage）。
  來源：https://kersai.com/anthropic-killed-third-party-claude-access-heres-every-workaround-that-still-works/（文章發布 2026-04-07；查看日期 2026-09-13）

補充：`anthropic-beta: oauth-2025-04-20` 這個 header 本身是 Anthropic API 真實存在、Claude Code OAuth 流程專用的 beta flag（另外常搭配 `claude-code-20250219`），但它是給官方 CLI 用的協定細節，不代表 Anthropic「允許」別的工具冒用；社群也回報過這個 hardcode 的 beta 值可能被伺服器端悄悄棄用或改變。
來源：https://gist.github.com/cedws/3a24b2c7569bb610e24aa90dd217d9f2 、 https://github.com/anthropics/claude-code/issues/13770（查看日期 2026-09-13）
