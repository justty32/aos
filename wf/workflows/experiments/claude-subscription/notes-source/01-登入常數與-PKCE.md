← [pi Claude 訂閱 OAuth：原始碼筆記](../notes-source.md)（分檔 1/2）｜[下一份](02-provider-與-request-auth.md)

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
