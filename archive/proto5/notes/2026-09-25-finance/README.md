# 財務部成立（2026-09-25）

← [proto5 README](../../README.md)｜規格 [spec/team/cost.md](../../spec/team/cost.md)｜程式 [lib/aos_team_cost.py](../../lib/aos_team_cost.py)

董事給的額度：claude 系（LiteLLM 上 `claude-*`）不超過一週額度的 10%；gpt／codex 系這週剩的都能用；deepseek 剩約 5 美元。名額後來改成新創規模「正式員工 ≤10、cpu ≤20、llm cpu ≤5」（擴張上限 100／200／20），歸 HR 管。財務部要答得出「誰花了多少、有沒有超、超了自動停」，另外要能讓幾家公司各有帳戶、花到 0 就倒閉。

## 1. 一句話

**每次問模型記一行帳 → `aos-team cost` 加總 → 郵差派新單前看一眼超了沒**。三步都是程式，不叫模型。

## 2. 設計

| 問題 | 定案 | 為什麼 |
|---|---|---|
| 帳本放哪 | `$AOS_COST_HOME/ledger.jsonl`，一台機器一本（建議 `~/.aos/cost`）；同夾 `prices.json`、`budget.json`、`accounts.json` | 錢包只有一個（董事的）；一台機器可能有好幾個 kernel、好幾支團隊，還有不經團隊的呼叫。放一本才加得出總數，要看某隊就篩 `team` 欄 |
| 預設開不開 | 設了 `AOS_COST_HOME` 才記 | 測試用本機假端點；預設開會把假帳寫進真帳本。接線：kernel 的 `llm`、`default` 兩池 envs 各帶一份 |
| 掛在哪 | 所有呼叫都經 `aos_llm_call._post`，上面只有兩個入口，兩處都掛：`call`（agent 思考，從 agent 家推出團隊／成員／手上的單）、`ask`（工具、壓縮、結晶、評審，用 `AOS_COST_*` 環境帶身分） | 掛在入口才知道「誰在叫」 |
| 寫壞了 | 吞掉，絕不擋呼叫 | 記帳不是正事 |
| 錢怎麼算 | 查帳時用**現在的**價格表重算；缺價的模型只記 token、印警告 | 價格是估的，改了價格表舊帳要跟著變 |
| 超了怎麼辦 | 郵差把新的 `handoff`（開單）、`spawn`（生成員）申請**留在 outbox 不處理**；每天每組超額寄 human 一封 `NEEDS-USER`；`aos-team ls` 第一行報；已在跑的單不砍 | 不退件，調高預算後下一輪自己會走，人不用重送 |
| 預算三層 | 全公司家族預算（`budget.json`）、團隊預算（`team.json` 的 `budget`）、公司帳戶餘額（`accounts.json`） | 董事的額度是按家族給的；團隊上限給領隊控；帳戶給「五家公司競爭」 |

hops 本身沒有 token 數，所以沒有另造輪子：每個 agent 家本來就有 `log/usage.jsonl`（`aos-team score` 的 R 軸讀它），帳本跟它**兩份都記**——那份是單一 agent 的原始用量（會輪換），帳本多了團隊、單號、家族、估價，不輪換。

## 3. 真跑（上限 2 次，用了 2 次）

模型全走 LiteLLM `localhost:4000/v1` 的 `deepseek-chat`；團隊用例子 1（lead、worker-1、reviewer、importer-1），每次一本自己的帳。腳本 `~/tmp/finance-try/run.sh`。

| | 第 1 次 | 第 2 次（團隊 deepseek 預算 20,000 token／天） |
|---|---|---|
| t-0001（門房直接派給 importer-1） | done，約 18 秒 | done，約 20 秒 |
| 帳本 | importer-1：7 次、35,696 token、估 $0.0101，單號自動掛 t-0001 | importer-1 6 次 29,523 token（t-0001）；lead 12 次 68,740 token（單號 `-`，見下） |
| 對帳 | `score` R 軸 importer-1＝35,696 ✔；hops 的模型 HTTP 次數＝7 ✔ | `score` R 軸 lead 68,740、importer-1 29,523 ✔ |
| cpu 行 | 開著 5 個、llm cpu 2 個 | 同左 |
| 超預算 | — | `ls` 第一行「財務：超預算，郵差不派新單：本團隊 deepseek token 用了 98,263／上限 20,000」；`cost budget` 491%「← 超了」 |

第 2 次的第二句話沒命中門房規則、轉給了 lead；lead 20 秒內讀檔想了 12 次，還沒寄出開單申請，腳本就收隊了，所以真跑沒走到「郵差擋開單」。**補驗**（隊已停、不叫任何模型，`~/tmp/finance-try/hold-check.sh`）：用門房會直接開單的那句話丟一張，手動讓郵差走一輪——

- 超預算：申請留在 human 的 outbox（1 件），人收到一封 `NEEDS-USER`「財務：超預算，郵差先不處理新的開單／生成員申請…本團隊 deepseek token 用了 109,183／上限 20,000」；
- 再走一輪：不重寄（還是 1 封）；
- 預算改成 1,000 萬：下一輪自己開出 t-0002、派給 importer-1；`ls` 第一行變回「財務：ok」。

lead 那 12 次單號是 `-`：它當時手上沒有單（在研究要不要開），這是對的——沒開單前的思考不屬於任何單。

## 4. 今天各家族用量估算（董事會看這張）

回填來源：`aos-team cost import` 掃 `~/tmp/w3a-try`、`~/tmp/arknights-try`、`~/tmp/arknights-eval`、`~/tmp/arknights-aos`、`~/tmp/commons-try`、`~/tmp/hr-try`、本隊兩次真跑、session 共用 scratchpad 裡今早的 team1／team2，共 49 個 `usage.jsonl`、532 筆（重跑不重記）。試用帳本在 `~/tmp/finance-try/cost/`。截至 09-25 約 12:00：

| 家族 | 今天呼叫 | prompt token | completion token | 估美元（價格表是估的） | 對董事額度 |
|---|---|---|---|---|---|
| gpt（全是 `chatgpt-gpt-6-astra`） | 196 | 5,483,913 | 27,404 | $14.12 | 走訂閱，錢數只比大小；「這週剩的都能用」，由供應商的額度擋 |
| deepseek（全是 `deepseek-chat`） | 156 | 1,094,010 | 19,424 | $0.32 | 對「剩約 5 美元」用了約 6%；本週（09-21 起）累計 $0.64 |
| claude | 0 | 0 | 0 | $0 | 經 aos 的 claude 呼叫今天是 0（見下「撈不到的」） |
| 本機（lm／ollama） | 0 | — | — | $0 | — |
| **合計** | 352 | 6,577,923 | 46,828 | **$14.44** | |

花最多的團隊：製造部 `arknights-aos/team` 97 次 $9.06、`arknights-try` 的 `20260925-110707-one` 41 次 $4.06（兩者都是 gpt-6-astra，prompt 很長：平均一問 3～4 萬 token）。其餘各隊都是 deepseek，每隊幾分錢。

**撈不到的**：

- **Claude Code、codex CLI 自己的用量**：各隊領隊與子 agent（Fable／Opus／Sonnet）、`codex exec` 審查都不經 aos，也不經 LiteLLM 的 aos 路徑，帳本看不到。董事說的「claude 一週額度」主要就花在這裡，**這個數財務部目前量不到**。
- LiteLLM 的 `/spend/logs`：回 `Database not connected`，沒有現成花費可交叉核對。
- 品管評審（arknights eval 的評審）如果是用 CLI 叫的，也不在帳上；`~/tmp/arknights-eval` 底下沒有 usage 檔。
- `import` 不知道當時的單號（`task` 空著）。

## 5. 財務部怎麼掛進公司（部門＝aos 團隊、董事＝human）

財務部**不開模型成員**，是「一本帳＋一個函式庫＋郵差裡的一條規則」，掛法：

| 問題 | 答 |
|---|---|
| 誰算帳 | 兩個模型入口自動記（不用任何人動手）；加總、比上限是 `aos_team_cost` 的函式，誰要都能叫 |
| 帳本放哪 | 一台機器一本 `$AOS_COST_HOME`（例 `/home/me/.aos/cost`）；五家公司共用一本，靠 `accounts.json` 的 `root` 分帳 |
| 其他團隊怎麼問餘額 | 人：`aos-team cost account ls`、`aos-team cost budget --target 團隊`；程式：`aos_team_cost.balances(base)`、`budget_status(env, 團隊)`；模型成員：目前沒有工具（留下一輪：給領隊一支唯讀 `balance` 工具，牢裡看不到 `$AOS_COST_HOME`，要由郵差或 wrap 出來） |
| 超額怎麼擋 | 每支團隊自己的郵差派新單前問 `hold_reason`，三層（全公司家族、團隊、帳戶）任一超了就不派、寄信給 human；已在跑的單做完 |

最小接線（每家公司、每支團隊都一樣）：

```json
// kernel.json：兩個池都帶帳本位置
{"pools": {"default": {"count": 3, "envs": {"AOS_COST_HOME": "/home/me/.aos/cost"}},
           "llm": {"count": 2, "envs": {"AOS_LLM_CONFIG": "/abs/llm.json", "AOS_COST_HOME": "/home/me/.aos/cost"}}}}
```

```json
// 某部門的 team.json（可選）：部門自己的日上限
"budget": {"since": "day", "deepseek": {"tokens": 2000000}, "claude": {"usd": 0.5}}
```

```sh
# 經理人：開五家公司的帳戶、撥開辦費、看誰倒閉
export AOS_COST_HOME=/home/me/.aos/cost
for c in a b c d e; do
  aos-team cost account open co-$c /home/me/companies/co-$c
  aos-team cost account grant co-$c --usd 1.0 --tokens 2000000 --note 開辦費
done
aos-team cost account ls
```

## 6. 代裁（我先決定了，要改說一聲）

1. 帳本一台機器一本、放 `AOS_COST_HOME`（不放 `K/`、不放各團隊）。理由見 §2。
2. 沒設 `AOS_COST_HOME` 不記帳。代價是忘了接線就漏記——所以 `ls` 第一行會說「財務：ok／超預算」，沒這行就代表沒在記。
3. 金額查帳時用現在的價格重算；帳上另存寫入當下的估值留底。
4. 超預算只擋 `handoff`、`spawn` 兩種申請，信、回報、驗收、重試、改派都照走（「已在跑的單做完不砍」）。人自己開的單也擋（要繼續就調預算）。
5. 預算檔壞了不擋（只在 `ls` 報）：壞檔不該讓全公司停工。
6. 價格表：claude 照 Anthropic API 牌價（Fable 10/50、Opus 5/25、Sonnet 5 2/10、Sonnet 4.x 3/15、Haiku 1/5 美元每百萬 token）；gpt-6-astra 猜 2.5/15、其他 gpt 猜 1.25/10；deepseek-chat 0.27/1.10。全部標「估的」。
7. 全公司預算範本先填 claude $10／週（等你給真數字）、deepseek $5 從 09-25 起；gpt 不設。
8. cpu 行上限預設 20／5（新創），`budget.json` 的 `cpus` 可改成擴張值 200／20；只顯示，擋名額是 HR 的事。
9. 公司帳戶用「資料夾歸屬」分帳（帳本不用加欄位，開戶前的帳也算得到）；倒閉＝有撥過的那一種餘額 ≤ 0。

## 7. 留下一輪

- **模型成員看不到餘額**：給領隊一支唯讀 `balance` 工具（牢裡看不到帳本，要郵差代答或 wrap）。
- **成員層預算**（`team.json` 的 members 上各設上限）：今天只做到團隊、全公司、帳戶三層。
- **單張單的上限**（一張單花超過 N 就停）：現在只能看 `--by task`，不會自動擋。
- **正式帳本位置**：試用帳本在 `~/tmp/finance-try/cost/`，還沒搬到 `~/.aos/cost`，各隊的 kernel 也還沒接線（等你拍題 1）。
- `playbook/company.md` 的「財務」列還寫「尚未成立」：我沒動（不在我能改的範圍），請 playbook 的維護者改成「已成立：一本帳＋`aos-team cost`＋郵差一條規則」。
- codex 唯讀審查：時間不夠，沒做。
- 舊原型的記帳設計 [proto2/notes/tools/cost-metering.md](../../../proto2/notes/tools/cost-metering.md) 沒逐條對過採不採（收尾才看到）。

## 8. 要你拍的題

1. **正式帳本放哪、要不要現在全機接線？** 選項：(a) `~/.aos/cost`，之後各隊 kernel.json 都帶上；(b) 先只在試跑用。**預設 (a)**。
2. **claude 的「一週額度 10%」換成多少？** 財務部只看得到經 aos 的 claude 呼叫；你的訂閱週額度絕對數我不知道。選項：(a) 給一個美元等值（例如 $10）；(b) 給 token 數；(c) 只算 aos 裡的、Claude Code 自己的不管。**預設先用 $10、只算 aos 裡的**。
3. **超預算時人自己開的單要不要也擋？** 選項：(a) 擋（現在這樣，你要繼續就調預算）；(b) human 開的單放行。**預設 (a)**。

## 9. 沉澱

**① 經驗（已寫進 [playbook/lessons.md](../../playbook/lessons.md)「財務部」段）**

1. 記帳要掛在「所有呼叫都經過的那一層的入口」，不是最底層：入口才知道誰在叫。
2. 會污染真資料的記錄功能要「明確打開才記」，再用一個顯眼的地方（`ls` 第一行）讓人看得出有沒有在記。
3. 擋預算擋「開新工作」、不擋「做到一半」，而且用「留著不處理」而不是退件——調高後自己會走。

**② 團隊組織架構：財務部是程式＋一條規則，不是模型團隊**

記帳、加總、比上限沒有一步需要判斷，全是算術；叫模型來做只會更慢、更貴、還可能算錯，而且財務部自己也要花錢。真正需要判斷的只有兩件事——「額度給多少」「超了要不要加碼」——那是董事和經理人（人）的事。所以財務部＝一本帳（`ledger.jsonl`）＋一個函式庫（`aos_team_cost`）＋郵差裡的一條規則（`budget_hold`）＋一個給人看的命令（`aos-team cost`）。

**③ 工作流架構**：記帳 → 查帳 → 擋預算，三步都純機械。寫成樣板 [playbook/workflows/finance-ledger.md](../../playbook/workflows/finance-ledger.md)（含照抄時的四個判斷：漏斗口在哪、一本還是多本、擋在哪、預設開還是關）。

**④ 可複用工具**

- `aos-team cost`（分組表、`budget`、`account`、`import`）本身。
- `aos-team cost import`：任何有 `members/<名>/log/usage*.jsonl` 的舊試跑都能事後補帳，重跑不重記——別隊收尾報告要算「這段花了多少」可以直接用。
- `aos_team_cost.balances()`／`account_grant()`：組織設計總監的 market 層直接 import（接口見 [cost.md](../../spec/team/cost.md) §6）。
