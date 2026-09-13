# pi Claude 訂閱 OAuth：原始碼筆記

調查目標是本機安裝的三個套件，版本均為 0.85.1：

- `pi-coding-agent`：`/home/lorkhan/.local/share/fnm/node-versions/v24.14.1/installation/lib/node_modules/@earendil-works/pi-coding-agent/`
- 下文 `$PI_AI`：上述目錄的 `node_modules/@earendil-works/pi-ai/dist/`
- `pi-agent-core`：上述目錄的 `node_modules/@earendil-works/pi-agent-core/`；沒有找到 Anthropic OAuth 或 transport 實作，這層只承接 agent loop。

本機套件只有已發行的 `dist`；以下行號以這份 0.85.1 JavaScript 為準。沒有讀取或抄錄任何 token 值。

## 1. 登入常數與 PKCE

`$PI_AI/auth/oauth/anthropic.js:12-20`：

```js
const CLIENT_ID = decode("OWQxYzI1MGEtZTYxYi00NGQ5LTg4ZWQtNTk0NGQxOTYyZjVl");
const AUTHORIZE_URL = "https://claude.ai/oauth/authorize";
const TOKEN_URL = "https://platform.claude.com/v1/oauth/token";
const CALLBACK_PORT = 53692;
const CALLBACK_PATH = "/callback";
const REDIRECT_URI = `http://localhost:${CALLBACK_PORT}${CALLBACK_PATH}`;
const SCOPES = "org:create_api_key user:profile user:inference user:sessions:claude_code user:mcp_servers user:file_upload";
```

base64 解出的公開 client ID 是 `9d1c250a-e61b-44d9-88ed-5944d1962f5e`。

`$PI_AI/auth/oauth/anthropic.js:188-215`：

```js
const { verifier, challenge } = await generatePKCE();
const server = await startCallbackServer(verifier);
const authParams = new URLSearchParams({
  code: "true", client_id: CLIENT_ID, response_type: "code",
  redirect_uri: REDIRECT_URI, scope: SCOPES,
  code_challenge: challenge, code_challenge_method: "S256",
  state: verifier,
});
```

特別之處：state 直接等於 PKCE verifier；callback server 也拿 verifier 當 expected state。`anthropic.js:93-121` 驗 callback path、code、state；`:216-262` 讓本機 callback 與手貼 code／redirect URL 競速。

## 2. authorization code 換 token

`$PI_AI/auth/oauth/anthropic.js:143-169`：token request 是 JSON，不是 form。

```js
headers: { "Content-Type": "application/json", Accept: "application/json" }
body: JSON.stringify({
  grant_type: "authorization_code", client_id: CLIENT_ID,
  code, state, redirect_uri: redirectUri, code_verifier: verifier,
})
```

`$PI_AI/auth/oauth/anthropic.js:174-186`：

```js
return {
  type: "oauth",
  refresh: tokenData.refresh_token,
  access: tokenData.access_token,
  expires: Date.now() + tokenData.expires_in * 1000 - 5 * 60 * 1000,
};
```

因此 `expires` 是 epoch milliseconds，且保存時就比服務端期限早五分鐘。

## 3. refresh 時點與 request

`$PI_AI/auth/resolve.js:62-87`：

```js
const DEFAULT_OAUTH_MINIMUM_VALIDITY_MS = 5 * 60 * 1000;
const expiresSoon = (credential) => Date.now() + minimumValidityMs >= credential.expires;
// ... credentials.modify(providerId, async (current) => {
return await oauth.refresh(current, refreshSignal);
```

`:65-108` 是 double-checked locking：先判斷、拿 provider credential lock、再判斷、15 秒 timeout、refresh、持久化。stored expiry 已扣五分鐘，resolver 又保留五分鐘，所以約提早十分鐘。

`$PI_AI/auth/oauth/anthropic.js:273-297`：

```js
responseBody = await postJson(TOKEN_URL, {
  grant_type: "refresh_token",
  client_id: CLIENT_ID,
  refresh_token: refreshToken,
}, signal);
return {
  type: "oauth", refresh: data.refresh_token, access: data.access_token,
  expires: Date.now() + data.expires_in * 1000 - 5 * 60 * 1000,
};
```

它要求回應帶新的 refresh token，沒有「缺少時沿用舊 token」的 fallback。

## 4. auth.json 持久化

`pi-coding-agent/dist/core/auth-storage.js:14-31`：新建 parent dir 用 `0700`，新建 auth file 用 `0600`；註解說 mode 只在 creation 套用。

`pi-coding-agent/dist/core/auth-storage.js:180-203` 驗證 OAuth credential 必須有 string `access`、string `refresh`、finite number `expires`。`:378-395` 在 lock 中讀整份 JSON、只合併指定 provider、pretty-print 寫回。

對本機 `~/.pi/agent/auth.json` 只做結構投影，看到：

```text
top-level provider keys: anthropic, lmstudio, openai-codex
anthropic keys/types: access:string, expires:integer, refresh:string, type:string
anthropic expires format: 13-digit Unix epoch milliseconds
```

沒有把 value 送到 stdout。`models.json` 只有自訂 `lmstudio` provider；`models-store.json` 的 `anthropic` 是動態模型 catalog，欄位包含 `models[]`、`checkedAt`、`lastModified`、`etag`，沒有 credential。

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
