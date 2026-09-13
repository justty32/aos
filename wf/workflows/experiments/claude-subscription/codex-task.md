# 任務書：研究 pi coding agent 怎麼用 Claude 訂閱帳號登入拿到可用的 LLM endpoint

你在 repo `/home/lorkhan/repo/simple_tools/aos`。這是**研究＋寫報告＋寫一支不執行的 PoC 腳本**，不是改專案。**只准新增 `wf/workflows/experiments/claude-subscription/` 這個資料夾底下的檔案**，其他路徑一律不碰。**不要 git commit、不要 push。** 不要開其他 agent。你**沒有網路**，只讀本機的原始碼。

## 絕對規則（比任務本身重要）

- `~/.pi/agent/auth.json` 裡有使用者的 token。**你可以讀它的結構（key 名、型別、`expires` 是什麼格式），但 `access`／`refresh`／`key` 的值一個字元都不准印到任何地方**——不准印到終端、不准寫進報告、不准寫進腳本、不准放進測試。要示意就寫 `sk-ant-oat01-…（略）`。
- PoC 腳本**只寫、不跑**。真的打 Anthropic 的 API 是使用者自己決定要不要做的事。

## 背景（使用者原話）

> 再幫我開一條線，去研究一下 pi coding agent 是怎麼用 claude subscribe account login 的方式，取得訂閱套餐方案的 llm endpoint api 的，不然像我這種訂閱每月 200 美的，都用不了 api。或是 litellm 能行？調查結果和相關實作看你要放在哪裡都可以。不然我們現在都只有環境變數中的 DEEPSEEK_API_KEY 可以用。

目的：aos 之後要做「LLM cpu」（一支程式收 LLM 呼叫請求、排隊、分發給 endpoint）。現在能用的 endpoint 只有本機 LM Studio（`localhost:1234`）與 DeepSeek（`DEEPSEEK_API_KEY`）。使用者想知道 Claude 訂閱（Max 200 美）能不能像 pi 那樣拿來用。

## 原始碼在哪（全部在本機）

- pi 版本 0.85.1，裝在 `/home/lorkhan/.local/share/fnm/node-versions/v24.14.1/installation/lib/node_modules/@earendil-works/pi-coding-agent/`。
- 它依賴的 `@earendil-works/pi-ai`（LLM 供應商層，OAuth 應該在這）在同一個 `node_modules/@earendil-works/pi-ai/`；`pi-agent-core` 也看一下。
- 從 `grep -rn -i 'oauth\|anthropic.*login\|claude.ai\|console.anthropic\|refresh_token\|client_id' --include='*.js' --include='*.ts' <pi-ai 的 dist 或 src>` 開始。找：登入流程（authorize URL、client_id、PKCE、redirect、code 怎麼換 token）、refresh 怎麼做、打 Messages API 時帶哪些 header（`Authorization: Bearer`？`anthropic-beta`？`anthropic-version`？有沒有特別的 user-agent 或 system prompt 前綴）、endpoint 是哪個 host、模型 id 怎麼給。
- `~/.pi/agent/auth.json` 的結構（只看 key）；`~/.pi/agent/models.json`／`models-store.json` 看 anthropic 供應商的設定長怎樣（一樣不印任何 key）。

## 要交出來的東西

### 1. `wf/workflows/experiments/claude-subscription/README.md`（大白話、繁體中文、200 行以內）

段落：

1. **一句話結論**：pi 是怎麼做到的（例如「它用 Claude Code 的 OAuth client_id 走 PKCE 登入 claude.ai，拿到 `sk-ant-oat01-…` 的 access token，之後打 `api.anthropic.com/v1/messages` 時帶 `Authorization: Bearer` 與某個 `anthropic-beta` header」——**以你讀到的原始碼為準**，不要照我這句寫）。
2. **登入流程**（一步一步，帶檔名＋行號）：authorize URL、參數、code 換 token 的 endpoint 與 body、回來的欄位、存到 auth.json 的形狀、`expires` 的單位、refresh 什麼時候觸發、怎麼 refresh。
3. **打 API 時的差異**（跟一般 API key 比）：header 列表、endpoint、有沒有必須帶的 system prompt／beta 旗標、模型 id、有沒有不能用的功能。**這段是 aos 之後要接的關鍵，要寫得能照著實作。**
4. **這條路的風險**（照實寫，不要淡化也不要嚇人）：這是用 Claude Code 的 client 身分打 API，Anthropic 的服務條款對第三方工具用訂閱 OAuth 的態度、被封的可能、token 放在明文檔的問題。你沒有網路，這段寫你從原始碼裡看到的線索（例如程式裡有沒有偽裝 user-agent、有沒有註解提到風險）＋「要使用者自己上網確認」。
5. **litellm 能不能**：你沒網路，只寫「本機沒裝 litellm；這題另一條線查」。
6. **接進 aos 的建議**（三到五條）：最簡單的是什麼（例如一支小 proxy 讀 pi 的 auth.json、幫忙 refresh、對外開 OpenAI 相容的 `/v1/chat/completions`，這樣 LM Studio／DeepSeek／Claude 三個對 LLM cpu 長一樣）；還是直接在 LLM cpu 裡多一種 endpoint 型別。**只建議，不做決定。**

### 2. `wf/workflows/experiments/claude-subscription/poc-messages.py`（只寫不跑）

一支 Python 3 標準庫腳本（`urllib`，不裝東西）：讀 `~/.pi/agent/auth.json` 的 `anthropic` 那筆 → 若過期就照 pi 的方式 refresh（把新 token 寫回同一個檔，寫之前備份）→ 打一次 Messages API，模型用 pi 預設的那顆（從原始碼找），prompt 固定 `Say hi in one word.`，印回應的文字與 usage，**任何錯誤都把 HTTP 狀態碼與回應 body 印出來**（這是使用者要看的診斷資訊）。header 完全照 pi 的原始碼帶。頂上寫清楚：`# 只在你自己決定要試時執行；這是用你的 Claude 訂閱身分打 API`。

### 3. `wf/workflows/experiments/claude-subscription/notes-source.md`

你讀原始碼時的原始筆記：檔名、行號、關鍵程式碼片段（**片段裡若含 client_id 這種公開常數可以寫，token 不行**）。給之後要實作的人省時間。

## 回報（十行以內，大白話）

- 一句話結論。
- 三個檔各多少行。
- 你不確定的地方（原始碼裡看不出來的）。
- 有沒有任何地方可能印到 token（應該是「沒有」，並說你怎麼確認的：例如 `grep -rn 'sk-ant-oat' wf/workflows/experiments/claude-subscription/` 為空）。
