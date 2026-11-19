# 公司 WSL 的 `~/litellm-proxy/`（LiteLLM 1.109.1）11-19 起起來、三個 ChatGPT 模型非串流與串流都實打通、aos 整條線真模型回字的紀錄；附「能不能放進 repo」的盤點與兩種做法。

← [2026-11-19](README.md)｜線 `litellm-up-1119`（opus）；腳本與輸出在公司 WSL 的 `~/.aos/scratch/litellm-up-1119/`

## 先講結論

- **proxy 起來了，現在還在跑**：pid `14835`，只聽 `127.0.0.1:4000`。停：`cd ~/litellm-proxy && ./stop.sh`。log：`~/litellm-proxy/logs/proxy.log`。
- **非串流沒壞**：三個模型（luna-low、terra、sol）非串流、串流各打一次，六則全部 HTTP 200、回 `ok`。家機那邊「1.93～1.103 非串流撈不回內容」的坑，1.109.1 這三個模型沒碰到。
- **aos 整條線通**：暫存樹 → llm kernel → `llm_http`（aos 走的是**非串流**）→ proxy → `chatgpt/gpt-6-luna`，問「只回一個字 pineapple」，3 秒收到 `pineapple`。暫存樹已關乾淨。
- **登入是抄 codex 的**：`chatgpt/auth.json` 的 token 跟 `~/.codex/auth.json` 是同一份（只比對「相不相等」，沒印值）。到期 11-27 09:54，今天沒有續期。**誰先續期，另一邊就可能被登出**——見第一節。
- **起很慢（約 2 分鐘）**：不是壞，是這台 WSL 用「鏡像網路」，沒人聽的本機埠連過去會卡到逾時；litellm 開機時自己會先連一下 4000 埠，就卡在這。見第二節。

## 一、登入怎麼確認的

只看檔在不在、大小、權限、鍵名與型別；沒讀出、沒印任何值。

| 項目 | 結果 |
|---|---|
| `~/litellm-proxy/chatgpt/auth.json` | 在，3859 bytes，權限 600，11-19 08:21 寫的 |
| 鍵名 | `access_token`、`refresh_token`、`id_token`、`expires_at`（整數）、`account_id`——litellm 要的五個都有；昨天那個 `device_code_requested_at` 已經沒了 |
| `expires_at` | 2026-11-27 09:54（開測時還剩約 193 小時） |
| 跟 codex 那份比 | `access_token`、`refresh_token` 都跟 `~/.codex/auth.json` 的**相等**（腳本只印 True／False）→ 是用 `chatgpt_auth_from_codex.py` 抄過來的，不是 `./login.sh` |
| 今天有沒有續期 | 沒有：測完 `auth.json` 的修改時間沒變、log 裡沒有 refresh 字樣（token 還沒過期，本來就不會續） |

**要提醒使用者的**：兩邊現在拿同一把 refresh token。官方文件說 refresh token 只能用一次——11-27 前後 token 快過期時，**litellm 或 codex 誰先拿去換新，另一邊就可能被登出**。litellm 先換：codex 要重登（`codex login`）；codex 先換：proxy 會開始回登入錯，再跑一次 `. ~/litellm-proxy/env.sh && python3 ~/repo/llm_proxy/chatgpt_auth_from_codex.py` 就好。這條線沒跑 codex、沒重登任何東西。

## 二、起 proxy

`cd ~/litellm-proxy && ./start.sh` → `start.sh: up on http://127.0.0.1:4000 (pid 14835)`，退 0。log 只有平常的兩條 WARNING（管理網頁登入節流、`gc.freeze`），沒有錯。`/v1/models` 帶 key 回 200，三個名字：`chatgpt-gpt-6.1-sol`、`chatgpt-gpt-6.1-terra`、`chatgpt-gpt-6-luna-low`。

**為什麼要等約 2 分 10 秒**（08:23:30 起、08:25:40 才印「startup complete」）：

- 這台 `C:\Users\…\.wslconfig` 寫了 `networkingMode=mirrored`（鏡像網路）。這種模式下，WSL 裡連一個**沒人聽**的 `127.0.0.1` 埠，不會馬上被拒，而是封包被吞掉、一直等到 Linux 的連線逾時（重試 6 次，約 127 秒）。這就是今早環境線看到的「4000 沒人聽時是逾時不是被拒」。
- 起的過程中看到 litellm 自己的行程對 `127.0.0.1:4000` 有一條 `SYN-SENT`（`ss -tnp`，pid 14835），也就是它開機時會先試連一下這個埠（推測是「埠有沒有被占」的檢查），結果就卡滿逾時才往下走。
- 影響：每次 `./start.sh` 都要等 2 分鐘多；`start.sh` 最多等 60 輪，這次剛好沒超時（它的 `curl` 那一下也卡了一陣）。沒改任何設定，只記下。

## 三、實測結果

每則都是同一句 `Reply with just: ok`，用 `~/.aos/scratch/litellm-up-1119/probe.py`（key 在腳本裡從檔讀、放 header，輸出前把 key 字樣換掉）。原始結果在同夾 `results.jsonl`。

| 模型名 | 非串流 | 串流 |
|---|---|---|
| `chatgpt-gpt-6-luna-low` | 200，`ok`，3.63 秒 | 200，`ok`，1.22 秒（2 段，有 `[DONE]`） |
| `chatgpt-gpt-6.1-terra` | 200，`ok`，1.32 秒 | 200，`ok`，1.19 秒（2 段，有 `[DONE]`） |
| `chatgpt-gpt-6.1-sol` | 200，`ok`，1.85 秒 | 200，`ok`，2.04 秒（2 段，有 `[DONE]`） |

- 回應的 `model` 欄都等於請求的名字。luna 非串流的 `usage`：prompt 1635、completion 5（prompt 多是 ChatGPT 後端自己加的 instructions，1624）。
- 第一則慢一點（3.6 秒）應是冷啟動。
- **沒測的**：工具呼叫（`tool_calls`）、長回答、圖片；非串流只證明「短回答撈得回來」。

## 四、aos 整條線

腳本 `~/.aos/scratch/litellm-up-1119/aos-run.sh`（先 unset 所有 `AOS_*`，只在腳本裡設 `AOS_HOME=~/repo/aos/proto8`；`LITELLM_KEY` 只給 llm kernel 那個行程，從檔讀、沒印）。照昨天紀錄第五節：

1. `cp -r $AOS_HOME/templates/start-api ~/.aos/scratch/litellm-up-1119/tree`、`source env.sh`。
2. `setsid` 起根（pid 20852）與 llm kernel（pid 20915，帶 `LITELLM_KEY`）。
3. `ctl add --auto-restart` 掛 `ann`；`aos-agent -d .stack --target ann llm set model=luna` → `model=luna`。
4. `say "Reply with exactly one word: pineapple"`、`listen --timeout-s 120` → **`pineapple`**，前後 3 秒；proxy log 同時多一條 `POST /v1/chat/completions 200`。假腦回的會是 `FAKE ANSWER to: …`，所以這是真模型回的字。
5. 兩句 shutdown 分開打：`aos-daemon-ctl -d …/tree/.stack shutdown`、`aos-daemon-ctl -d …/tree/llms/stacks/llm shutdown`，都退 0；之後兩個 pid 都不在。

aos 的 `llm_http` 送的是**非串流**請求（`/chat/completions`，body 不帶 `stream`），所以第三節的非串流結果就是 aos 實際走的路。

收尾核對：`grep -rlF` 用 master key 的內容掃暫存夾與 proxy log，找不到。暫存樹留在 `~/.aos/scratch/litellm-up-1119/tree`（停著，不佔行程）。

## 五、非串流若壞的選項

不需要：非串流沒壞，沒有要繞的東西。補一句給家機那邊參考：`~/repo/llm_proxy/docs/litellm_pin.md` 釘 1.87.5 的唯一理由（非串流 1.93～1.103 壞）在 1.109.1 已不成立——至少這三個模型、短回答是這樣；家機要不要升，是使用者「兩台版本先不統一」那題。

## 六、proxy 現況與怎麼停

- 跑著：pid `14835`（記在 `~/litellm-proxy/proxy.pid`），`127.0.0.1:4000`。
- 停：`cd ~/litellm-proxy && ./stop.sh`。
- log：`~/litellm-proxy/logs/proxy.log`。
- 注意：WSL 視窗全關、或 WSL 被關掉，它會跟著停；再起要等約 2 分鐘（第二節）。
- aos 要接：起 llm kernel 的視窗先 `export LITELLM_KEY="$(cat ~/litellm-proxy/master.key)"`，再 `llm set model=luna`（或 `terra`、`sol`）。

## 七、「`~/litellm-proxy` 能不能放進 repo」盤點（只盤點，沒搬、沒 commit）

### 每個檔與夾

| 檔／夾 | 大小 | 能進 git？ | 說明 |
|---|---|---|---|
| `start.sh`、`stop.sh`、`login.sh` | 各 0.4～1.1 KB | 可以 | 沒有秘密；但寫死路徑（下表） |
| `env.sh` | 373 B | 可以 | 只有開關與路徑，沒有秘密 |
| `config.yaml` | 566 B | 可以 | 三個模型名，沒有秘密 |
| `requirements.in` | 24 B | 可以 | 一行 `litellm[proxy]==1.109.1` |
| `requirements.lock` | 244 KB | 可以 | 117 個套件的版本與 sha256；這份就是「安全那一半」，最值得進 git |
| `master.key` | 47 B | **絕不** | proxy 的鑰匙 |
| `chatgpt/`（`auth.json`） | 3.9 KB | **絕不** | ChatGPT 登入憑證 |
| `logs/` | 約 10 KB 起跳 | 不該 | 執行紀錄，會一直長 |
| `proxy.pid` | 幾 bytes | 不該 | 執行中才有 |
| `venv/` | **752 MB** | 不該 | 這台機器專用、可照 lock 重建 |
| `wheels/` | **174 MB**（117 個） | 不該進 git | 驗過雜湊的安裝檔，離線重裝用；要留就留在機器上，或另外放（例如壓縮檔存雲端），lock 有雜湊，重新下載也驗得出來 |

### 寫死 `~/litellm-proxy` 的地方（四處）

- `env.sh` 第 2 行：`D="$HOME/litellm-proxy"`
- `start.sh` 第 4 行、`login.sh` 第 4 行：`. "$HOME/litellm-proxy/env.sh"`
- `stop.sh` 第 4 行：`cd "$HOME/litellm-proxy"`

搬進 repo 要改成「從腳本自己的位置找」（如 `D="$(cd "$(dirname "$0")" && pwd)"`），並把**放秘密與執行狀態的夾**（`master.key`、`chatgpt/`、`logs/`、`proxy.pid`、`venv/`）跟程式分開，或至少寫進 `.gitignore`。

### 跟 `~/repo/llm_proxy` 重疊或衝突的地方

| 項目 | `llm_proxy`（家機那套） | `~/litellm-proxy` | 衝突？ |
|---|---|---|---|
| 版本 | `start_litellm.sh` 用 `uv run` 每次現拉 1.87.5，沒有雜湊 | 1.109.1，固定 venv，有雜湊 | 兩套各釘各的；`docs/litellm_pin.md` 的釘版理由這次已被推翻（第五節） |
| 埠 | `127.0.0.1:4000` | `127.0.0.1:4000` | **同一台不能同時跑兩套** |
| 模型 | `litellm.yaml` 用 `include:` 合 `models/*.yaml`，約 189 個名字；ChatGPT 在 `models/chatgpt.yaml` | 3 個名字 | 這 3 個名字 llm_proxy 都有（寫法略不同：它用 `extra_body.reasoning.effort`，這邊用 `reasoning_effort`；兩邊都標 `mode: responses`）；`include:` 在 1.109.1 讀不讀得懂**沒測** |
| master key | 沒設（註解掉） | 要 | aos 的 `llm_http` 在 `LITELLM_KEY` 沒設時不帶 key 照打，所以兩套 aos 都接得上 |
| ChatGPT 登入檔 | 預設 `~/.config/litellm/chatgpt/auth.json` | `~/litellm-proxy/chatgpt/auth.json` | 不衝突；`chatgpt_auth_from_codex.py` 本來就看 `CHATGPT_TOKEN_DIR`，使用者今天就是這樣抄過來的 |
| Claude 訂閱 | `claude_auth_from_claude_code.py` 掛 callback | 沒有 | — |
| `.gitignore` | 只擋 `__pycache__`、`*.pyc`、`/my-*.yaml` | — | 併進去要補擋 `master.key`、`chatgpt/`、`logs/`、`proxy.pid`、`venv/`、`wheels/` |

### 兩種做法

**甲、併進 llm_proxy 當一個子夾**（例如 `llm_proxy/locked-1.109.1/`）

- 要動：搬 7 個可進 git 的檔進子夾；改上面四處寫死的路徑；秘密與狀態夾留在 `~/litellm-proxy`（或子夾裡但 `.gitignore` 擋掉）；llm_proxy 的 `.gitignore` 補六項；README 寫清楚「兩種起法、同時只能起一種」。
- 後果：一個 repo、一個 `main`，兩台 `git pull` 都拿得到；家機不跑就沒影響。repo 裡會有兩套起法、兩份模型清單，日後要記得只改對的那份。若之後決定兩台統一到 1.109.1，可以逐步把子夾的 venv＋lock 做法收回頂層、刪掉 `uv run` 那條。

**乙、在 llm_proxy 開分支**

- 要動：開一個分支，在分支上把 `start_litellm.sh` 換成 venv＋lock 的起法（或加入這些檔），同樣要改路徑、補 `.gitignore`；公司機 checkout 那個分支。
- 後果：兩台跑不同分支，`main` 上的改動（例如家機加新模型）要一直合進分支，日久會分岔；別的 agent 在公司機看到的是分支、在家機看到的是 `main`，容易搞錯。另外 aos 這邊的規矩是「只有一個 `main`、不開分支」（[規矩卡](../../../../wf/workflows/common/rules-card.md)），llm_proxy 自己的文件沒寫這條，但使用者的習慣是這樣。

**推薦甲**：秘密本來就要排除，子夾不改到家機的起法，也不違反「只有一個 main」。真正的方向題是「兩台要不要統一到 1.109.1」——若要統一，連子夾都不用，直接在 llm_proxy 的 `main` 把版本升上去、換成 venv＋lock 的裝法（要先在 1.109.1 測 `include:` 與 189 個名字的設定）。這題留給使用者。

## 八、現在還在跑的行程

- **litellm proxy**：pid `14835`，照任務留著給使用者用。停：`~/litellm-proxy/stop.sh`。
- 這條線的 aos 根（20852）與 llm kernel（20915）都已 shutdown，收尾核對不在。別條線（`aos-gdb-1119`）的行程沒碰。

## 九、併進 llm_proxy（線 `llmproxy-merge-1119`）

- **使用者 11-19**：問「話說這個litellm_proxy不能放入repo/嗎？合併進llm_proxy，或是弄個分支。」頂層建議甲（子夾）後，他回「好，併進llm_proxy當子夾」。
- **位置**：`~/repo/llm_proxy/pinned_1.109.1/`。抄（不是搬）進 7 個檔：`start.sh`、`stop.sh`、`login.sh`、`env.sh`、`config.yaml`、`requirements.in`、`requirements.lock`；另寫子夾的 `README.md` 與 `.gitignore`（擋 `master.key`、`chatgpt/`、`logs/`、`proxy.pid`、`venv/`、`wheels/`，`git check-ignore` 六項都擋到）。根 `README.md`、`wf/INDEX.md`、`wf/workflows/common/code-map.md` 各加一行指過去。
- **路徑**：四處寫死的 `~/litellm-proxy` 改成以腳本所在夾為準。新增兩個可選變數：`LITELLM_PINNED_REUSE` 指到已裝好的一份（借它的 `venv/`、`master.key`、`chatgpt/`，`logs/` 與 `proxy.pid` 仍寫在子夾），`LITELLM_PINNED_PORT` 換埠。（這台後來不用這個變數，直接把東西搬進子夾，見下面「已切換」。）`start.sh` 等待上限從 60 輪改 180 輪。
- **驗證**：四支 `bash -n` 過；抄到暫存夾、`LITELLM_PINNED_REUSE=~/litellm-proxy LITELLM_PINNED_PORT=4010` 起，4 秒就 `up`（這次沒卡兩分鐘），`/v1/models` 不帶 key 401、帶 key 200 三個名字，自己的 `stop.sh` 收掉、pid 不在；沒 venv 時會清楚報錯退 1。`~/litellm-proxy/chatgpt/auth.json` 修改時間沒變。repo 裡搜不到 master key 的內容。
- **llm_proxy 的 commit**：llm_proxy 自己的規矩寫「commit 由使用者決定」，所以先停在工作樹；使用者在選項框選「commit，不 push」後交到本地 `main`：`bf9f5ec`（子夾＋根三處導覽），切換後再一筆 `432f9a8`（照實裝改 README 的安裝步驟）。沒 push。

### 11-19 已切換：proxy 現在從 repo 子夾起

使用者問「~/litellm-proxy啥時能刪掉？」，頂層說明要先切換、proxy 會斷幾分鐘後，他回「現在應該沒人在用proxy，排吧」。

- **現在跑的**：`~/repo/llm_proxy/pinned_1.109.1/` 起的 proxy，pid `33494`（記在子夾的 `proxy.pid`），`127.0.0.1:4000`。停：`cd ~/repo/llm_proxy/pinned_1.109.1 && ./stop.sh`；起：同夾 `./start.sh`（約 2 分 20 秒才回 `up`，鏡像網路的逾時，見第二節）。log：子夾 `logs/proxy.log`。aos 接：`export LITELLM_KEY="$(cat ~/repo/llm_proxy/pinned_1.109.1/master.key)"`。
- **怎麼切的**：先把 `wheels/`（117 個、174 MB）搬進子夾，照子夾 README 用 `python3.12 -m venv venv` 加 `pip install --no-index --find-links wheels --require-hashes -r requirements.lock` 離線對雜湊重建 venv：117 個全裝上、litellm `1.109.1`。再用舊夾 `./stop.sh` 停 pid `14835`（停後 4000 沒人聽），把 `master.key`、`chatgpt/` 搬進子夾（權限 600／700 沒變，沒開沒讀），`git check-ignore` 確認四樣都擋住。子夾 `./start.sh` 不帶任何變數起：08:36:44 起、08:39:07 `up`；`/v1/models` 不帶 key 401、帶 key 200。斷線約 3 分鐘。
- **實測**：三個模型非串流各一次「Reply with just: ok」：luna-low 200 `ok` 1.85 秒、terra 200 `ok` 1.31 秒、sol 200 `ok` 1.84 秒。aos 整條線（`~/.aos/scratch/llmproxy-merge-1119/aos-run.sh`，照第四節，key 改從子夾讀）：`llm set model=luna` 後問 pineapple，3 秒回 `pineapple`；兩句 shutdown 都退 0，根與 llm kernel 的 pid 都不在。暫存夾與 proxy log 搜不到 master key。
- **README 照實裝改了**：`uv venv` 預設不帶 pip 不能照寫法跑，改成只寫 `python3.12 -m venv`；已有 `wheels/` 就跳過 `pip download`；補一行確認版本。
- **舊夾 `~/litellm-proxy/` 剩**：`venv/`（752 MB）、`logs/`（16 KB，11-18～11-19 早的 log）、舊腳本與設定 7 個檔（共約 250 KB，路徑寫死的舊版）。秘密已經不在了（`master.key`、`chatgpt/` 已搬走）。**現在刪不影響正在跑的 proxy**：它的 venv、key、登入都在子夾；刪掉的只是舊 log 和退路（舊 `start.sh` 現在本來就起不來，key 搬走了）。刪不刪等使用者說。
- **還寫著舊路徑的**：活的設定或腳本——沒有（aos 的範本與 kernel.json 只寫 `localhost:4000`；rc 檔、`~/.config`、`~/.local/bin`、crontab 都沒提到）。現行文件：`wf/workflows/dev-env/01-跨機與外部工具.md` 的 LiteLLM 那列原寫「公司那台未確認；不用 api_key」，已改成新位置；`02-模型端點.md` 補一句公司機要帶 key。歷史紀錄（不改，寫的是當時位置，以這一節為準）：本檔第一～八節、`19/公司WSL-環境-1119.md`、`19/README.md`、`18/litellm-proxy-接gpt帳號.md`、`18/litellm-供應鏈與選版.md`、`18/沙箱隔離-實機檢查.md`、`18/交接-各線/使用者原話-1118下午.md`、`18/README.md`、`18/_index.json`、`wf/progress.json` 的舊述。
- 11-19 上午使用者說「刪掉」，頂層已刪除 ~/litellm-proxy（刪前確認跑著的 proxy 工作目錄在 ~/repo/llm_proxy/pinned_1.109.1、沒開著舊夾的檔、舊夾已無 master.key 與登入檔；刪後 /v1/models 仍回 200）。
