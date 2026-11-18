# litellm proxy 接 GPT 帳號（公司 WSL）：查了什麼、裝了什麼、怎麼起、還差哪一步

← [2026-11-18](README.md)

使用者 11-18：「API真模型端點這塊，幫我弄個litellm proxy，接gpt帳號。我WSL有登入codex。對了，小心litellm的供應鏈攻擊，這塊可以上網去查查看。」線名 litellm-1118。

## 先講結論

- **裝好了**：公司 WSL 的 `~/litellm-proxy/`，litellm **1.109.1**，獨立 venv，117 個套件全部釘版加 sha256，只聽 `127.0.0.1:4000`。起、停、拒絕沒帶 key 的請求都試過。
- **還差一步要你親手做**：用 ChatGPT 帳號登入一次（瀏覽器輸入裝置碼）。litellm 讀不到 codex 現有的登入檔，硬抄也不行（理由見下面「為什麼不能沿用 codex 的登入」）。登入完之前，真模型一句都沒回過。
- **aos 這邊不用改任何 repo 檔**：start-api 範本 `kernel.json` 本來就指 `http://localhost:4000/v1`，模型名 `chatgpt-gpt-6-luna-low`、`chatgpt-gpt-6.1-terra`、`chatgpt-gpt-6.1-sol`，proxy 就照這三個名字開；起 llm kernel 的視窗先 `export LITELLM_KEY=...` 就接得上。

## 一、二、供應鏈事故與選版

拆到 [litellm-供應鏈與選版](litellm-供應鏈與選版.md)：litellm 今年被下毒兩次（3 月 `1.82.7`／`1.82.8`、10 月 `1.107.0`，都是裝了就每次開 Python 都跑的偷憑證程式），另有一串 proxy 漏洞；選 **1.109.1**，117 個套件釘版加 sha256、逐一對過 PyPI、掃過已知特徵、離線裝。

## 三、ChatGPT 帳號怎麼接

litellm 的 `chatgpt/` provider 走 ChatGPT 訂閱（不是 API key），打 `chatgpt.com/backend-api/codex`；原生是 Responses API，`/chat/completions` 由 litellm 轉接（aos 打的就是這個）。登入只有一種：**裝置碼登入**，token 存在 `CHATGPT_TOKEN_DIR` 底下的 `auth.json`；proxy 自己不能跳出登入，要先在終端機登入一次。access token 約 10 天，會自動用 refresh token 續。來源：<https://docs.litellm.ai/docs/providers/chatgpt>。

**為什麼不能沿用 codex 的登入**：

- 格式不同：codex 的 `~/.codex/auth.json` 把 token 包在 `tokens` 底下；litellm 要的是攤平的 `access_token`、`refresh_token`…，直接指過去讀不到（看的是鍵名，值沒讀）。
- 就算轉格式也不該：官方文件說 refresh token **只能用一次**。兩邊拿同一份，誰先續期，另一邊就被登出——你的 codex 可能突然要重登。
- 另一條路「codex 自己帶登入穿過 proxy」（<https://docs.litellm.ai/docs/tutorials/openai_codex_byok>）只適用 codex 當用戶端，aos 用不上。

所以 proxy 用**自己的一份**登入（同一個 ChatGPT 帳號、另一個 session）。文件說個人方案要先在 ChatGPT 的安全性設定打開「裝置碼登入」，Business／Enterprise 要管理員開。

## 四、裝在哪、怎麼起停

全部在公司 WSL `~/litellm-proxy/`（不在 repo 裡）：

| 檔 | 是什麼 |
|---|---|
| `venv/` | 獨立 venv（uv 建、Python 3.12） |
| `requirements.in`／`requirements.lock` | 要什麼／釘死的 117 個套件與雜湊 |
| `wheels/` | 驗過雜湊的 wheel（174 MB；要重裝可離線用） |
| `config.yaml` | 三個模型名對到 `chatgpt/gpt-6-luna`（effort low）、`gpt-6.1-terra`、`gpt-6.1-sol` |
| `env.sh` | 關遙測 `LITELLM_TELEMETRY_DISABLED`、不去網路抓價目表 `LITELLM_LOCAL_MODEL_COST_MAP`、關管理網頁 `DISABLE_ADMIN_UI`、關 API 文件頁 `NO_DOCS`；`CHATGPT_TOKEN_DIR` 指 `chatgpt/` |
| `master.key` | proxy 的鑰匙，自己產生、權限 600，沒印過 |
| `chatgpt/` | 登入後放 `auth.json`（權限 700 的夾） |
| `start.sh`／`stop.sh`／`login.sh` | 起（背景、記 pid 在 `proxy.pid`、log 寫 `logs/proxy.log`）／照 pid 停／第一次登入 |

**你要親手做的**（在公司 WSL 開一個終端機）：

```sh
cd ~/litellm-proxy
./login.sh        # 會印一個網址和一組碼：用瀏覽器開網址、登入 ChatGPT、輸入那組碼；印 ok 就好
./start.sh        # 起 proxy；要它一直在，就留著這個 WSL 視窗別全關（wsl 視窗都關了它會跟著停）
./stop.sh         # 要停的時候
```

## 五、aos 怎麼指過去

在起 **llm kernel** 的那個視窗（步驟單的視窗 B），`source env.sh` 之後、起 kernel 之前多一行：

```sh
export LITELLM_KEY="$(cat ~/litellm-proxy/master.key)"
cd llms && aos-exec --stack stacks/llm def
```

然後換 agent 的腦：`aos-agent -d .stack --target ann llm set model=luna`（或 `terra`、`sol`；這些是 `llms/def/kernel.json` 裡 `endpoints` 的名字）。

## 六、驗了什麼、沒驗什麼

驗了（11-18，公司 WSL，暫存複本 `~/.aos/scratch/litellm-1118/`，不是活樹）：

- proxy 起得來、只聽 `127.0.0.1:4000`；沒帶 key 打 `/v1/models` 回 401，帶 key 列得出三個模型名；`stop.sh` 照 pid 停乾淨，埠放掉。
- log 裡找不到 master key；暫存樹裡的檔也找不到。
- **aos 整條線通到 proxy**：暫存複本 `install.py`、抄 start-api、起根與 llm kernel、`llm set model=luna`、`say` 一句；請求經 llm kernel → `llm_http`（帶 `LITELLM_KEY`）→ proxy，proxy 認了 key、轉給 `chatgpt/gpt-6-luna`，在「還沒登入」那步回 HTTP 400。agent 收到 `EndpointFailed`。

沒驗：

- **真模型回字**：要等你跑完 `./login.sh`。登入後最小的試法：`./start.sh` 後照第五節起 start-api，問一句。
- 工具呼叫（tool_calls）經 chat completions 轉 Responses 這段，換真模型才看得到。
- 長駐（開機自動起、wsl 視窗全關後還在）：沒做，現在是手動 `start.sh`。
- `terra`、`sol` 兩個名字只確認 proxy 有開，沒打過；三個模型在你的方案能不能用，以登入後實打為準（codex 的模型清單裡有 `gpt-6-luna`、`gpt-6.1-terra`、`gpt-6.1-sol`）。

順手看到的邊緣狀況（沒改，攤給你）：

- 端點回 400 時，`aos-agent listen` 等滿 90 秒只說 `AnswerMissing … not answered yet`，沒帶 proxy 回的理由；理由在 agent stack 的 `stderr.txt`（`BrainFailed`、`EndpointFailed HTTP 400 …`）。agent 跟著重起一次（`--auto-restart`）。
- 步驟單的「視窗 B」`aos-exec --stack stacks/llm def` 是前景指令；寫腳本一次跑完時要丟背景，不然卡住。
