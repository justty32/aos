← [pi Claude 訂閱 OAuth：原始碼筆記](../notes-source.md)（分檔 2/2）｜[上一份](01-登入常數與-PKCE.md)

## 5. provider 與 request auth

`$PI_AI/providers/anthropic.js:39-54`：

```js
return createProvider({
  id: "anthropic", name: "Anthropic",
  baseUrl: "https://api.anthropic.com",
  auth: { apiKey: anthropicApiKeyAuth(), oauth: lazyOAuth(/* ... */) },
  models: Object.values(ANTHROPIC_MODELS),
  api: anthropicMessagesApi(),
});
```

`$PI_AI/auth/oauth/anthropic.js:299-306` 把 OAuth access 暫時以 `apiKey` 欄位交給 provider transport；那只是 pi-ai 的內部 `ModelAuth` 名字，不代表 wire 上用 `x-api-key`。

`$PI_AI/api/anthropic-messages.js:688-722`：

```js
function isOAuthToken(apiKey) { return apiKey.includes(/* OAuth token prefix */); }
// OAuth: Bearer auth, Claude Code identity headers
const client = new Anthropic({
  apiKey: null, authToken: apiKey, baseURL: model.baseUrl,
  dangerouslyAllowBrowser: true,
  defaultHeaders: {
    accept: "application/json",
    "anthropic-dangerous-direct-browser-access": "true",
    "user-agent": `claude-cli/${claudeCodeVersion}`,
    "x-app": "cli",
  },
});
```

原始碼 `:40-44` 的原文註解是 `Stealth mode: Mimic Claude Code's tool naming exactly`，並固定 `claudeCodeVersion = "2.1.251"`。這是風險判斷的重要線索。

## 6. beta、system prompt、工具名

`$PI_AI/api/anthropic-messages.js:740-774`：沒有 caller override 時，OAuth 先加入：

```js
features.push("claude-code-20250219", "oauth-2025-04-20");
```

依模型／選項還可能追加 fine-grained tool streaming、interleaved thinking、server-side fallback 等 beta；本次無工具、無 thinking 的單次 PoC 只有前兩個。

`$PI_AI/api/anthropic-messages.js:776-827`：

```js
const params = {
  model: model.id, messages: converted.messages,
  max_tokens: options?.maxTokens ?? model.maxTokens,
  stream: true,
  ...(betaFeatures.length > 0 ? { betas: betaFeatures } : {}),
};
if (isOAuthToken) {
  params.system = [{
    type: "text",
    text: "You are Claude Code, Anthropic's official CLI for Claude.",
  }];
  // caller system prompt append 在後面
}
```

同檔 `:40-66,780,1023-1029,1108-1129` 把已知工具名改成 Claude Code canonical casing，回應再映回 caller 原名。

## 7. SDK 實際補的 wire 細節

pi 用 `@anthropic-ai/sdk` 0.123.0。其 `resources/beta/messages/messages.js:24-56` 對 `/v1/messages?beta=true` POST，並把 `betas` array 變成 `anthropic-beta` header。

SDK `client.js:347-375` 在 `authToken` 模式產生 `Authorization: Bearer ...`；`:823-849` 補：

```text
Accept: application/json
User-Agent（之後被 pi 的 claude-cli value 覆蓋）
X-Stainless-Retry-Count
X-Stainless-Timeout（有 timeout 時）
X-Stainless-Lang / Package-Version / OS / Arch / Runtime / Runtime-Version
anthropic-dangerous-direct-browser-access: true
anthropic-version: 2023-06-01
```

pi 的 `api/anthropic-messages.js:330-396` 建 client、build params，最後呼叫 `client.beta.messages.create(...)`。PoC 為了用標準庫簡化 response parsing，改成非 streaming JSON；URL、headers、model、system 身分與 user message 不變。

## 8. 預設模型與已知／未知能力

`pi-coding-agent/dist/core/model-resolver.js:9-20`：

```js
export const defaultModelPerProvider = {
  anthropic: "claude-opus-4-8",
  // ...
};
```

`$PI_AI/providers/data/anthropic.json:1` 的該模型是 `anthropic-messages`、base URL `https://api.anthropic.com`，支援 text/image、reasoning，catalog 宣告 1M context 與 128k max output；這是 pi catalog metadata，不是本次實際呼叫驗證。

OAuth 專用分支沒有列出功能禁用表。可從 transport 看出 Messages 內文字、圖片、thinking、tool use、cache control 都有處理，但沒有理由把這推廣到 batches、Files 或管理 API。`$PI_AI/README.md:1507-1516` 把 Anthropic Pro/Max 明列為 OAuth provider，`:1516` 說 request path 自動 refresh；沒有第三方使用條款或封帳政策文字。

## 9. LiteLLM 與安全檢查

- `command -v litellm`：未安裝。
- Python `importlib.util.find_spec("litellm")`：未安裝。
- 依任務限制不連網，所以不判斷目前 LiteLLM upstream 是否能做這種訂閱 OAuth。
- 報告與 PoC 不包含任何真 token，也刻意不放 OAuth token 的完整 prefix 字串，方便用固定字串 grep 做洩漏檢查。
