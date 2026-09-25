← [team](README.md)

# 財務部：記帳、查帳、擋預算（2026-09-25）

董事給了額度（claude 一週額度的 10%、gpt 這週剩的都能用、deepseek 剩約 5 美元），財務部要答得出：到現在每個模型家族用了多少 token、多少錢；每張單、每個團隊、每個成員花多少；有沒有超預算，超了自動停。

財務部是**程式加一條規則**，不是模型團隊：記帳、加總、比上限都是純機械，不需要判斷。實作 [`lib/aos_team_cost.py`](../../lib/aos_team_cost.py)。名額（cpu 數）歸 HR 管，這裡只順手印目前開著幾個。

## 1. 帳本放哪

**一台機器一本**：環境變數 `AOS_COST_HOME`＝一個資料夾的絕對路徑（建議 `~/.aos/cost` 展開後的路徑），裡面三個檔：

| 檔 | 誰寫 | 內容 |
|---|---|---|
| `ledger.jsonl` | 程式（追加） | 一次模型呼叫一行（下表） |
| `prices.json` | 人（文字編輯器） | 價格表（§3），範本 [examples/cost/prices.json](examples/cost/prices.json) |
| `budget.json` | 人 | 全公司預算（§4），範本 [examples/cost/budget.json](examples/cost/budget.json) |
| `accounts.json` | 人或 `aos-team cost account` | 一家公司一個帳戶：配額、已花、餘額（§6） |

為什麼不放 `K/` 或各團隊資料夾：額度是整間公司的（董事只有一個錢包），一台機器上可能有好幾個 kernel、好幾支團隊，還有不經團隊的呼叫（評審、結晶、工具描述）。放一本才加得出全公司的數；要看某隊就篩 `team` 欄。

**沒設 `AOS_COST_HOME`＝不記帳**（跟 `AOS_HOPS` 一樣）。理由：測試用本機假端點，預設開會把假帳寫進真帳本。接線要做兩處：kernel 的 `llm` 池 envs（思考的呼叫在那裡跑）與 `default` 池 envs（郵差在那裡跑，擋預算要看帳），例：

```json
{"pools": {"default": {"count": 3, "envs": {"AOS_COST_HOME": "/home/me/.aos/cost"}},
           "llm": {"count": 2, "envs": {"AOS_LLM_CONFIG": "/abs/llm.json", "AOS_COST_HOME": "/home/me/.aos/cost"}}}}
```

人自己的 shell 也 export 一份，`aos-team cost`、`ls` 才看得到。

## 2. 一筆帳

```json
{"at": "2026-09-25T11:07:18.334+08:00", "team": "/abs/團隊資料夾", "member": "writer-1", "task": "t-0003",
 "model": "deepseek-chat", "alias": "default", "family": "deepseek", "prompt_tokens": 6242, "completion_tokens": 29,
 "usage_missing": false, "usd": 0.001717, "source": "think", "batch": "aw-writer-1-…", "ms": 2868}
```

- **在哪記**：所有模型呼叫都走 `aos_llm_call._post`，上面只有兩個入口，兩處都掛：
  - `aos_llm_call.call`（agent 思考，`source: think`）：知道 agent 家 → 家在 `<團隊>/members/<名>/` 底下就填 `team`、`member`；`task`＝那個成員手上沒結束、最近更新的一張單（讀 `team/tasks/*.json`）。
  - `aos_llm_ask.ask`（工具的 `--describe-with-llm`、壓縮 `--summarize`、結晶、評審…，`source: ask`）：沒有 agent 家，身分由呼叫的人用環境帶：`AOS_COST_TEAM`、`AOS_COST_MEMBER`、`AOS_COST_TASK`、`AOS_COST_SOURCE`（例：評審腳本設 `AOS_COST_SOURCE=eval-judge`）。
- **什麼時候記**：端點回了 2xx 的 JSON（就算回覆內容驗不過，端點也已經算錢了）。`usage` 沒回＝`usage_missing: true`、token 記 0。
- **寫失敗絕不擋呼叫**：任何例外都吞掉。一行一次 `write`（`O_APPEND`），多支程式同時寫不會交錯。
- `usd` 是**寫的當下**用價格表算的估值（缺價＝`null`）；查帳一律用**現在的**價格表重算（§3）。
- 跟 `<家>/log/usage.jsonl` 的關係：那份是一個 agent 的原始用量（`aos-team score` 的 R 軸讀它），會輪換；帳本是全公司財務用，不輪換、多了團隊／單號／家族／估價。兩份都記，不互相取代。

## 3. 價格表 `prices.json`

```json
{"families": {"claude": ["claude-"], "gpt": ["chatgpt-", "gpt-"], "deepseek": ["deepseek-"], "local": ["lm-", "ollama-"]},
 "models": {"deepseek-chat": {"in": 0.27, "out": 1.1}, "claude-opus-5*": {"in": 5.0, "out": 25.0}}}
```

- `families`：模型名的前綴 → 家族（最長前綴贏，都不中＝`other`）。沒寫 `families` 用上面這份預設。
- `models`：美元／每百萬 token（`in`＝prompt、`out`＝completion）。鍵是完整模型名，或 `前綴*`（完整名優先，其次最長前綴）。
- **缺價的模型**：照記 token、不算錢；`aos-team cost` 表上金額後面加 `＋?`，最後印一行警告列出缺哪些模型、各多少 token。
- 範本的價格**全是估的**：claude 照 Anthropic API 牌價；gpt、deepseek 照公開牌價量級猜。gpt 實際走訂閱，錢數只拿來比大小，預算建議用 token 設。

## 4. 預算

全公司 `budget.json` 與團隊 `team.json` 的 `budget` 同一個形狀：

```json
{"since": "week", "claude": {"usd": 10.0}, "gpt": {"tokens": 50000000}, "deepseek": {"usd": 5.0, "since": "2026-09-25"}, "all": {"usd": 30}}
```

- `cpus`（只有 `budget.json` 用）：`{"max": 正整數, "llm_max": 正整數}`，只給 cost 表的 cpu 行當上限顯示（§5），不是花費預算。
- 其他鍵是家族名或 `all`（全部家族加總）；值 `{"usd": 數字, "tokens": 整數}` 至少一個，可另加 `since` 蓋過外層。
- `since`：`week`（本週一 0 點，預設）、`day`（今天 0 點）、`all`、`YYYY-MM-DD`（那天 0 點）。都是本機時區。
- 團隊的只算 `team`＝這個團隊資料夾（真實路徑）的帳；全公司的算全部。
- 名冊 `budget` 形狀錯＝`FormatInvalid`（`team.json.budget.deepseek.tokens 要是 ≥ 0 的整數`）；`budget.json` 壞了＝`aos-team cost budget` 報錯、`ls` 第一行說預算檔壞了，**郵差不擋**（壞檔不該讓全公司停工）。

### 超了怎麼辦

「用了 ≥ 上限」就算超。

1. **郵差不處理新的 `handoff`（開單）與 `spawn`（生新成員）申請**：原檔留在 outbox，不退件、不記紀錄；預算調高（或換週）後下一輪自己會走。人用 `aos-team ask`／`task new` 開的單也一樣擋（人要繼續就調預算）。
2. **寄信給 human**：`NEEDS-USER`，講哪一條超了、用了多少、上限多少、怎麼調。同一天同一組超額只寄一封（紀錄 id＝`budget.<日期>.<超額組合的 sha>`）。
3. **`aos-team ls` 第一行**：`財務：超預算，郵差不派新單：…`（沒超＝`財務：ok…`；沒設 `AOS_COST_HOME` 不印）。
4. **已在跑的單不砍**：信、回報、驗收、審查、改派、重試照常，做完為止。所以會超一點——超多少看手上的單多大。

## 5. 命令

```text
aos-team cost [--by family|model|team|member|task|source] [--since 今天|本週|全部|YYYY-MM-DD] [--team] [--json]
aos-team cost budget [--json]          # 每條預算用了幾成；有超的退 1
aos-team cost import 資料夾… [--dry-run]   # 回填：撈資料夾底下所有 members/<名>/log/usage*.jsonl
aos-team cost account ls｜open 名 公司資料夾｜grant 名 [--usd X] [--tokens N]   # 一家公司一個帳戶（§6）
```

- 預設 `--by family`、`--since 今天`、全公司；`--team` 只看 `--target` 那支團隊。
- 表：第一行總結（從何時起、幾次、多少 token、估多少錢），接著一組一行（次數、prompt、completion、估美元），缺價警告，最後一行 `cpu：開著 N 個（忙 M）、其中 llm cpu K 個（上限 20／llm 5，由 HR 管）`（從 `aos-kernel ls --json` 的 `counts.pools.want`、`pools.llm.want` 拿；沒設 `AOS_KERNEL_HOME` 就說看不到）。上限預設是董事 09-25 定的新創規模 20／5；擴張時在 `budget.json` 寫 `"cpus": {"max": 200, "llm_max": 25}`（董事 09-25 14:20：llm cpu 總額 20→25）。超過只在行尾標「← 超過上限」，真的擋是 HR 的事（名額、員工數都歸 HR）。
- `import`：每筆帶 `import_key`（檔的真實路徑＋那行內容的 sha1），重跑不重記；帳上已有同一次呼叫的即時紀錄（team、member、batch、prompt、completion 都同）也不記。`team` 取 `members/` 的上一層、`task` 不填（當時手上哪張單已經無從得知）。

## 6. 帳戶：一家公司一個（09-25 追加，給「五家公司互相競爭」用）

董事要開幾家一樣的小公司競爭，經理人按表現撥額度，帳戶花到 0 就倒閉。`$AOS_COST_HOME/accounts.json`：

```json
{"accounts": {"acme": {"root": "/abs/companies/acme",
                       "grants": [{"at": "2026-09-25T12:00:00+08:00", "usd": 1.0, "tokens": 2000000, "note": "開辦費"}]}}}
```

- **帳戶認資料夾**：`root`＝那家公司的資料夾，它的團隊都放在底下；帳本 `team` 欄落在 `root` 底下（或 `team` 欄就等於帳戶名——`aos_llm_ask` 的呼叫用 `AOS_COST_TEAM=acme` 帶）就算這家的。帳本本身不用改，所以開戶前的舊帳也算得進來。
- **配額**＝`grants` 加總（`usd`、`tokens` 各自加；可以撥負的收回）；某一種從沒撥過＝不管那一種。
- **已花**＝這家開戶以來所有帳（不分時段），金額用現在的價格表算。**餘額**＝配額 − 已花。
- **倒閉**（`broke`）＝有撥過的那一種餘額 ≤ 0。倒閉的公司：郵差不處理它團隊的新開單／生成員（跟超預算同一條路，§4），寄信給 human，`ls` 第一行報；經理人再撥款就自動復活。
- 總池（claude ≤ 董事一週額度 10%、gpt 這週剩的全部、deepseek 約 5 美元）照舊用 `budget.json` 的家族預算管；帳戶管「這一家分到多少」，兩層都會擋。
- 寫 `accounts.json` 在 `.accounts.lock` 的 flock 裡做（經理人和程式可能同時撥款），暫存檔＋改名。人也可以直接用文字編輯器改。

命令：

```text
aos-team cost account open acme /abs/companies/acme
aos-team cost account grant acme --usd 1.0 --tokens 2000000 --note 開辦費
aos-team cost account ls [--json]       # 每家：營業／倒閉、配額、已花、餘額；有倒閉的退 1
```

**給程式用的接口**（`lib/aos_team_cost.py`，組織設計總監的 market 層直接 import）：

| 函式 | 做什麼 |
|---|---|
| `home(env)` | 帳本資料夾（`AOS_COST_HOME`），沒設＝None |
| `account_open(base, 名, 公司資料夾)` | 開戶；已開同 root＝不變，root 不同＝`CostError('Conflict')` |
| `account_grant(base, 名, usd=None, tokens=None, note='', op=None)` | 撥款（加配額），回那一筆；給 `op`（操作 ID）＝這個帳戶已有同一個 `op` 就不再撥（崩了重跑不重撥） |
| `account_transfer(base, 甲, 乙, usd=None, tokens=None, note='', op=…)` | 甲轉給乙：同一次讀寫裡甲撥負的、乙撥正的，不會只做一半；`op` 必填、去重同上 |
| `balances(base)` | `{名: {"root", "quota": {"usd", "tokens"}, "spent": {…}, "balance": {…}, "calls", "broke"}}` |
| `account_of(base, 團隊資料夾)` | 這支團隊歸哪個帳戶（root 最長的）；沒有＝None |
| `record(env, model=…, usage=…, source=…, agent_dir=None)` | 記一筆（通常不用自己叫，兩個模型入口已經掛了） |
| `budget_status(env, 團隊資料夾)` → `(各條, 超了的)` ／ `hold_reason(env, 團隊資料夾)` | 郵差用的「超了沒」：全公司家族預算、團隊預算、帳戶餘額三層一起看 |
| `read_ledger(base)`、`summarize(rows, by, prices)`、`load_prices(base)` | 自己做報表 |

錯誤一律 `CostError(code, msg)`（`Usage`、`NotFound`、`Conflict`、`AccountsInvalid`…）。

## 7. 看不到的

帳本只看得到**經 aos 程式呼叫 LiteLLM** 的用量。Claude Code、codex CLI 自己的用量（領隊、各隊 Opus／Fable、astra 審查）不經過這裡，記不到；LiteLLM 的 `/spend/logs` 要接資料庫才有（09-25 查過：`Database not connected`），目前沒得交叉核對。
