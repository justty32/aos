# Claude 訂閱 OAuth 給 LLM endpoint 的本機原始碼調查

> **結論先講（2026-09-13，Fable 收線時補）**：pi 原生的 OAuth transport 打 API 時就已經帶 Claude Code 的身分（`User-Agent: claude-cli/…`、`x-app: cli`、system 第一段「You are Claude Code…」），跟 gotgenes/pi-anthropic-auth 差的只是後者再多塞一個假的計費 header 好被算進方案額度。Anthropic 2026 年起的條款與伺服器端封鎖見 [web-findings.md](web-findings.md)。**aos 不自己寫這種客戶端**（冒充 Anthropic 自家 CLI），原本任務書要的 `poc-messages.py` 已刪掉不入 repo。要接 Claude 只剩兩條乾淨的路：Console 開 API key 按量付費；或把 pi 本身當子行程用（`pi -p`，janet-lab 的 pi-shell 已經包好），登入與條款由 pi 那邊負責。這份調查留著當「pi 是怎麼做的」的知識。

調查日期：2026-09-13。只讀本機安裝的 pi／pi-ai 0.85.1；沒有連網，也沒有送出任何 API 請求。

## 一句話結論

pi 用 Claude Code 的公開 OAuth client 身分，對 `claude.ai` 走 PKCE 登入，拿到 Claude Pro／Max 的 OAuth access token；之後以 `Authorization: Bearer` 呼叫 `https://api.anthropic.com/v1/messages?beta=true`，同時偽裝 Claude Code 的 user-agent、`x-app`、固定 system 身分與兩個 beta 旗標，所以 Max 訂閱確實能被 pi 當成一個 Messages endpoint 使用，但這不是一般 Anthropic API key。

## 登入流程

以下 `$PI_AI` 指 pi 內附的 `node_modules/@earendil-works/pi-ai/dist`。

1. `$PI_AI/auth/oauth/anthropic.js:13-20` 定義 Claude Code client ID、authorize URL `https://claude.ai/oauth/authorize`、token URL `https://platform.claude.com/v1/oauth/token`、callback `http://localhost:53692/callback`，以及 inference、Claude Code session、profile、file upload 等 scopes。
2. `$PI_AI/auth/oauth/anthropic.js:188-215` 產生 PKCE verifier／S256 challenge；它也直接把 verifier 當 `state`。authorize query 是 `code=true`、`client_id`、`response_type=code`、`redirect_uri`、`scope`、`code_challenge`、`code_challenge_method=S256`、`state`。
3. `$PI_AI/auth/oauth/anthropic.js:80-140,216-262` 在 `127.0.0.1:53692` 等 callback；若瀏覽器在別台機器，也能貼 redirect URL 或 code。收到的 `state` 必須等於 verifier。
4. `$PI_AI/auth/oauth/anthropic.js:159-186` 對 token URL POST JSON：`grant_type=authorization_code`、`client_id`、`code`、`state`、`redirect_uri`、`code_verifier`。回應取 `access_token`、`refresh_token`、`expires_in`。
5. pi 存進 `~/.pi/agent/auth.json` 的 `anthropic` 欄位，形狀是 `{ "type": "oauth", "access": "（略）", "refresh": "（略）", "expires": 13 位整數 }`。`expires` 是 Unix epoch **毫秒**，而且已先扣掉五分鐘安全量（`anthropic.js:181-186`）。本機只檢查過 key 與型別，沒有輸出值。
6. `$PI_AI/auth/resolve.js:62-108` 在每次取 auth 時檢查；若「現在＋五分鐘」已到 stored `expires` 就 refresh。因 stored `expires` 本身已扣五分鐘，實際上約在服務端到期前十分鐘更新。更新在 credential-store lock 內重查，避免多個請求重複 refresh。
7. `$PI_AI/auth/oauth/anthropic.js:273-297` refresh 同一個 token URL，POST JSON：`grant_type=refresh_token`、`client_id`、`refresh_token`；再用新回應完整替換 access、refresh、expires。`pi-coding-agent/dist/core/auth-storage.js:378-395` 把整個 provider 欄位寫回 `auth.json`。

## 打 API 時跟一般 API key 的差異

最小可實作規格如下；（原本的 PoC 腳本已刪，見最上面。）

| 項目 | Claude 訂閱 OAuth | 一般 Anthropic API key |
|---|---|---|
| URL | `POST https://api.anthropic.com/v1/messages?beta=true` | 同一 Messages host；SDK 的 beta method 也走此 path |
| 認證 | `Authorization: Bearer <access>`，不可再送 `x-api-key` | `X-Api-Key: <key>` |
| 必要版本／beta | `anthropic-version: 2023-06-01`；`anthropic-beta: claude-code-20250219,oauth-2025-04-20` | 版本 header 仍有；沒有 OAuth 的兩個 beta |
| Claude Code 身分 | `User-Agent: claude-cli/2.1.251`、`x-app: cli`、`anthropic-dangerous-direct-browser-access: true` | pi user-agent；沒有 `x-app` |
| system | 第一段必須是 `You are Claude Code, Anthropic's official CLI for Claude.`；呼叫者自己的 system prompt 接在後面 | 只送呼叫者的 system prompt |
| 模型 | pi 0.85.1 的 Anthropic 預設是 `claude-opus-4-8`（`pi-coding-agent/dist/core/model-resolver.js:9-20`） | 同一模型 id 格式 |

來源核心在 `$PI_AI/api/anthropic-messages.js:40-66,688-760,776-827`。OAuth 另外會把已知工具名正規化成 Claude Code 的大小寫（例如 `read` → `Read`，同檔 `:40-66,780,1023-1029,1108-1129`）。pi 實際透過 Anthropic JS SDK 0.123.0，SDK 還補 `Content-Type: application/json`、`Accept: application/json`、`X-Stainless-*` 診斷 headers 與 `anthropic-version`；這些不是秘密或額外授權。

原始碼沒有列出「訂閱 OAuth 禁用哪些 Messages 功能」。它確實支援文字、圖片、thinking、tool use、prompt cache；但本次只追到 `/v1/messages`，不能據此宣稱 batches、Files API、管理 API 或任意模型都能用。OAuth scopes 雖包含 file upload，也不等於每個 endpoint 都已獲准。實作時要把 4xx body 原樣（先遮密）留下，才能分辨模型、額度、beta 或權限限制。

## 這條路的風險

- 這不是官方「把 Max 變成通用 API credits」的介面。pi 自己把 OAuth 標成 Claude Pro／Max 支援，但本機原始碼沒有附 Anthropic 服務條款或第三方工具政策；使用前要由使用者上網確認最新條款。
- `$PI_AI/api/anthropic-messages.js:40` 直接寫 `Stealth mode: Mimic Claude Code's tool naming exactly`，`:707-720` 又寫 `Claude Code identity headers`，並把 user-agent 改成 Claude CLI。這是明確的身分模擬線索，不宜把它包裝成穩定、受保證的公開 API。
- 能不能被限流、撤銷 token、停用訂閱或封帳號，原始碼無法回答。可能性不能說是零；真正風險要查當下官方條款與執法說明。
- `auth.json` 是明文 token。pi 建檔時用 `0600`（`pi-coding-agent/dist/core/auth-storage.js:14-31`），但同檔也註明 mode 只在建立時套用；備份、同步、log、錯誤訊息與其他同帳號程式都要防外洩。PoC 會遮掉錯誤 body 中疑似憑證，refresh 寫回前另做 `0600` 備份。
- PoC 沒有重做 pi 的跨行程 lock；若要親自執行，先關掉 pi，避免兩邊同時旋轉 refresh token。

## LiteLLM 能不能

本機沒裝 LiteLLM；這題另一條線查。本次無網路，不能可靠判斷目前版本是否原生支援這組 Claude 訂閱 OAuth 身分與 refresh 流程。

## 接進 aos 的建議

- 最小路徑：先做一支本機小 proxy，獨占讀寫 pi 的 `auth.json`、負責 refresh，再對 LLM cpu 提供 OpenAI 相容的 `/v1/chat/completions`；LM Studio、DeepSeek、Claude 對上層便可長一樣。
- 若不想依賴 pi 的私有檔案格式，就把 OAuth credential store 與 refresh 搬進 LLM cpu，新增 `anthropic-subscription` endpoint 型別；但 headers、system 身分與 beta 要一起版本化，不能只換 Authorization。
- 無論走哪條，都把 refresh 串行化、原子寫檔、備份權限、錯誤 body 遮密、429 backoff 與 endpoint 健康狀態列入第一版。
- 先讓使用者手動跑這支單次 PoC，確認帳號、模型與條款風險可接受，再決定 proxy 或內建；本報告不替使用者做產品方向決定。

