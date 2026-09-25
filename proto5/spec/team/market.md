← [team](README.md)｜公司：[company.md](company.md)｜帳戶：[cost.md §6](cost.md)｜報告：[2026-09-25-company](../../notes/2026-09-25-company/README.md)

# 市場層：幾家小公司競爭，經理人照表現撥額度

2026-09-25 第 1 版（組織設計總監）。程式：[`lib/aos_market.py`](../../lib/aos_market.py)；指令包裝 [`examples/company/market.py`](../../examples/company/market.py)。

董事長＝使用者（human），**經理人**＝調度者（Fable，不在 aos 裡）。幾家一樣的公司（[company.md](company.md)，`new --prefix c1-`…`c5-`）做同樣的單；
誰做得**好**（品管分）、**快**（秒數）、**省**（token）就多撥額度；花到 0 **倒閉**；剩兩家**合併**。
這支是經理人手上的**機械**指令：發多少照參數算，經理人可以覆寫；不叫模型。

## 1. 放哪

- **市場資料夾**（`--market`／`AOS_MARKET_HOME`，建議 `~/tmp/company-run/`）：`market.json`（參數、各家、每輪紀錄、事件）＋`archive/`（收掉的公司整個資料夾搬進來）。
- **帳戶**：財務部的 `$AOS_COST_HOME/accounts.json`（[cost.md §6](cost.md)）。一家公司一個帳戶，`root`＝公司資料夾；**配額**＝撥款加總，**已花**＝帳本裡落在公司資料夾底下的呼叫（kernel 兩池帶 `AOS_COST_HOME`，`company.py up` 會傳）。撥款、收回都是 `account_grant`（收回＝撥負的），所以 `accounts.json` 本身就是流水帳。
- 一家一個 kernel（company.md §6）：五家同跑＝五個 kernel、一個 daemon。

## 2. 參數（`market.json` 的 `params`，人用文字編輯器改）

| 鍵 | 預設 | 意思 |
|---|---|---|
| `weights` | 品質 0.6、快 0.25、省 0.15 | 排名分＝三項（各 0～100）的加權和 |
| `round_pool` | 2 美元、400 萬 token | 每輪撥出去的總額 |
| `shares` | 35／25／20／12／8 ％ | 第 1、2…名拿幾成；家數少就取前幾個、按比例放大到 100％ |
| `seed` | 1 美元、200 萬 token | 開辦費 |
| `min_quality` | 0 | 品質分低於它＝這輪不撥（0＝不設） |
| `merge_at` | 2 | 營業中剩幾家才准合併 |
| `dept_order` | mfg、qa、rd、lib、hq | 合併時先收哪個部門的人 |
| `total` | 空 | **董事給的總量** `{"usd", "tokens"}`：設了才有「總池」，撥款不能超過（§4） |
| `machine` | 人頭 100、cpu 200、llm cpu 20 | 整台機器的名額：營業中各家 `limits` 加總不能超過 |

## 3. 一輪

```text
經理人：market.py score c1 --eval <eval 結果.json>   （或 --quality 78；秒數、跳數從公司的總機單算）
        market.py rank                              看排名（不寫帳）
        market.py grant [--usd c3=0]                照排名撥這一輪；--usd／--tokens 覆寫單一家
        market.py bankrupt                          花光的倒閉
        （剩兩家）market.py merge                    合併
```

- **品質**（0～100）：`score --eval` 讀 arknights 評分器的結果檔，每人 機械 40％＋證據列 40％＋評審 20％（沒評審就前兩項各 50％）取平均；或經理人直接 `--quality`。
- **快**：這一輪（上一輪 `grant` 之後）結的總機單的平均秒數（下單→最後一封回覆），最快的一家 100，其他＝最快 ÷ 自己 ×100；沒結單＝0。跳數（回覆信數＋1）只記、不算分。
- **省**：這一輪花的 token（這輪已花 − 上輪 `grant` 時記下的已花），最省的一家 100，其他＝最省 ÷ 自己 ×100；沒結單＝0。
  注意（品管部 09-25）：並行的單 `aos-team score --task` 報的是整隊的數；市場用的是**整家公司這一輪**的 token，不照單切，所以不受影響；要照單比就得照成員切。
- **撥**：`shares` 照名次分 `round_pool`；`min_quality` 沒過的拿 0，其他人按比例放大；`--usd 名=X`／`--tokens 名=N` 覆寫。撥款記進帳戶（note「第 N 輪 第 k 名」），這一輪的排名、撥款、各家已花記進 `history`。

## 4. 總池（董事 09-25 追加）

- **錢**＝`total` − 各家已花（連收掉的）− 營業中各家手上沒花的配額（餘額 > 0 的部分）。等於「董事給的 − 已經撥出去還收不回來的」。
- **名額**＝`machine` − 營業中各家的 `limits`（人頭、cpu、llm cpu）加總。
- `open` 的開辦費、`grant` 的每輪撥款都從總池出：總池不夠，`open` 拒絕（`PoolEmpty`／`NoSlots`），`grant` 照比例縮到剛好發完（`history` 記 `capped`）。
- 公司收掉時，**它手上沒花完的配額**（任一種 > 0 的）撥負的收回、**它的名額**（`limits`）不再算營業中——兩樣都回到總池，經理人拿去撥給別家：
  - **倒閉**（`bankrupt`，某一種餘額 ≤ 0）：歸零的那一種沒得收；另一種還有剩就收回。**只是歸零倒閉的，回收的通常只有名額。**
  - **裁撤**（`close 名`，經理人決定收掉一家還沒花光的）：兩種剩多少收多少。
  - `bankrupt`／`close` 都回傳並記進 `events`：`recycled`（收回多少錢）、`slots`（放出幾個名額）、`freed`（放出的成員名，前綴可以再用）。
- 名額撥給別家：`slots 名 --llm-cpu 1`（`limits.llm_cpu`、`pools.llm` +1）、`--cpu 1`（`limits.cpu`、`pools.default` +1）、`--regular 1`；不能超過那家的 `limits_max`。只改 `company.json`，kernel 開著要 `aos-kernel cpu add` 或下次 `up` 才真的多開。
- `pool` 印總池兩行。

**五家同跑的 llm cpu**：機器頂 20，每家新創預設 5 → 五家要 25，第五家 `open` 會 `NoSlots`。樣板的做法是 `company.py new --llm-cpu 4`（五家各 4），這題留給董事拍（報告的問題清單）。

## 5. 倒閉、合併的細節

**倒閉**：停（`company.py down`：撤總機、各部門 `aos-team stop`、`aos down`）→ 公司資料夾整個搬進 `archive/<名>-bankrupt-<時間>/` → 市場標 `bankrupt`。帳本、帳戶不刪（財務要查）。
財務部那邊：帳戶倒閉後郵差本來就不再派新單（cost.md §4），就算經理人還沒跑 `bankrupt`，那家也不會繼續花大錢；已在跑的單做完為止。

**合併**（營業中剩 `merge_at` 家；`--force` 硬來）：排名高的併掉排名低的（`--into` 可指定），`--dry-run` 先看計畫：

1. 同部門的**經理（`template: lead`）只留併入方的**：被併方的經理裁掉（家跟著封存；筆記 `notes.json` 抄一份到併入方 `team/notes/_merged/<舊名>/` 備查）。
2. 其餘成員照 `dept_order` 併進併入方**同一個部門的團隊**，改名 `<併入方前綴><原職位>-<被併方名>`（`c2-mfg-writer1` → `c1-mfg-writer1-c2`）；`mail_to` 是那部門的經理＋human，經理的 `mail_to` 也加上他。
3. 併入方的正式名額（`limits.regular` − 現有正式）還有＝**正式**；滿了＝**臨時工**（名冊那一列寫 `employment: temp`，不算人頭）。被併方本來就是臨時工的仍是臨時工。
4. 併入方沒有那個部門的團隊＝那些人裁掉。
5. **跨任務記憶帶過去**：`team/notes/<舊名>/notes.json` 抄到新名底下；對話紀錄（家的 `prompts/`）留在被併方的封存，不搬（家裡有絕對路徑）。
6. 帳：被併方的餘額撥給併入方（併入方 +、被併方 −），被併方標 `merged`、停、封存；它的名額回總池。
7. 併入方 kernel 開著：動到的部門 `aos-team init`＋`start`，新成員開工。

## 6. 沒做的

- 真的五家同跑（只做過一家真跑；市場層用假帳本測）。
- 品質分只接 arknights 評分器；別的產品線要自己的 `quality_from_eval`。
- `slots` 不會自己 `aos-kernel cpu add`；倒閉不會自己把名額撥給誰（經理人撥）。
- 合併只合兩家；三家以上一次併要跑兩次。
