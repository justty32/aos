# adapt 包 spec（第一版）

← [adapt 包](README.md)｜[核心 spec](../../spec.md)｜[step 包 spec](../step/spec.md)

寫的是規則；理由在 [loop6 藍圖](../../notes/blueprint-loop6.md) §3。路徑未特別說明時都相對 node（任務的 cwd）。**空間路徑**＝相對空間根的路徑（跟 node id 同一套），只經掛載讀（核心 §4.5）。

## 1. 檔案與所有權

| 檔 | 誰寫 | 內容 |
|---|---|---|
| 來源 `<src node>/out/<fact>.json` | 發布者（原子 rename） | `{"v": 1, "seq": n, "round": 來源回合, "value": {...}, "at"}`；`round` 必填整數，`seq` 建議 |
| 鏈宣告 `adapt/<sense>.json` | 人／作者 | §2；工作中不改 |
| 暫存器 `in/<sense>.json` | adapt 任務 | §4；每個自己的回合覆寫一次 |
| 槽 `state.json` | adapt 任務 | 框架（§5）；同槽換 run 接得上（核心 §5.1），槽刪才消失 |

## 2. 鏈宣告

```json
{"sense": "temp", "src": "src/out/temp.json", "src_clock": "src/.aos/round.json",
 "max_age": 3, "patience": 2, "stall": null,
 "steps": [{"select": "value.t_dc"},
           {"scale": {"mul": 0.1, "q": 0.05, "round": 1, "as": "c"}},
           {"threshold": {"ge": 80, "as": "hot"}}],
 "need": ["c"]}
```

| 欄 | 規則 |
|---|---|
| `sense` | 必填；英數、`_`、`-`，最多 32 字；暫存器檔名 |
| `src`、`src_clock` | 必填；空間路徑（相對、不含 `..`）；`src_clock` 檔名要是 `round.json`。執行時經掛載解析（工具包 `resolver`），解析不到＝「路徑指不到」 |
| `max_age` | 非負整數或 null（預設）＝效期，**來源回合數**；null＝只報年齡、不過期 |
| `patience` | 非負整數（預設 0）或 null（＝0）＝耐性，**自己回合數** |
| `stall` | 非負整數或 null（預設）；null＝只報 `stalled`，整數＝連續停超過這麼多個自己回合翻 unknown |
| `steps` | 非空陣列；第一步一定是 `select`，`select` 只能有一個；每步恰一個種類鍵 |
| `need` | 非空字串陣列；每個都要是某一步 `as` 的產出；`ok` 時這些欄都不是 null |
| `note` | 給人看，不讀 |

**三種步**（不開運算式）：

- `{"select": "a.b.c"}`：從來源物件取一個值（點分路徑，每段非空）。路徑走不到＝`select_missing`（unknown 分支）。誤差界 0。
- `{"scale": {"mul": 數, "q": 數, "round": 整數?, "as": 名?}}`：`x ← x × mul`，有 `round` 就四捨五入到小數 `round` 位；誤差界 `err ← |mul| × err + q`。`q ≥ 0`；有 `round` 時 `q` 不得小於取整的半個單位（`0.5 × 10^-round`）。`x` 不是數字（含 bool）＝`not_number`（unknown 分支）。有 `as` 就把 `x` 放進產出。
- `{"threshold": {"ge"|"gt"|"le"|"lt": 數, "as": 名}}`：恰一個比較鍵；`as` 必填。區間 `[x − err, x + err]` 整段成立＝`true`、整段不成立＝`false`、跨過門檻＝`null`（`within_error_band`）。`x` 不變。

`as` 的名字英數與 `_`，同一條鏈不重複。檢查器（§6）只看宣告，不執行。

## 3. 時鐘與年齡

- **來源鐘** `ct`＝來源 `round.json` 的 completed_tock（核心 §3 判定：closed 取 `round`、open 取 `round − 1`；不存在、讀不到、壞＝不知道）。抄 budget 包的 8 行，不共用。
- **年齡** `age_src_rounds`＝`max(0, ct − basis.src_round)`（發布者在回合 r 的 tock 寫 `round: r`，那時 `ct` 可能還是 `r − 1`，所以取 0）。
- **效期**：`max_age` 是整數且 `age > max_age`＝`expired`，立刻 unknown（用來源的鐘，不換算成自己的回合）。來源 pause 時 `ct` 不動，年齡不長。
- **耐性**：`my_round − last_ok_my_round > patience`＝到期。`last_ok_my_round` 是最近一次「讀取成功」（§4.2）的自己回合，框架建立時＝`since`。dst pause 時沒有回合，耐性不走。
- **來源狀態** `src_state`：
  - `unknown`：`ct` 不知道。
  - `reset`：`ct` 比上回看到的小，或讀到的來源 `round` 比上一份依據的 `src_round` 小。之後一直報 `reset`，直到採用一份新依據。
  - `advancing`：`ct` 比上回大（第一次看到也算）；`stall_rounds` 歸 0。
  - `stalled`：`ct` 跟上回一樣；`stall_rounds` +1（每個自己回合最多 +1）。`stall` 是整數且 `stall_rounds > stall`＝`stalled`，立刻 unknown。

## 4. 每一圈（每個自己的 tock 一次）

### 4.1 讀

1. 讀鏈宣告（`fact`）並跑檢查器；壞了＝這圈 unknown（`decl_bad`），暫存器名照框架記的 `sense`；框架也沒有就只記 stderr、什麼都不寫。宣告雜湊跟框架的 `chain` 不同＝`chain_changed`（unknown，不採用新鏈；改回原宣告就恢復，要換鏈：停任務、刪槽 `state.json`）。
2. 讀來源鐘（經掛載）。
3. 讀來源檔（經掛載）：`N`＝確定不存在；`OK` 且是物件、`round` 是整數＝讀到；其餘（讀不到、不是一般檔／資料夾、半寫、不是物件、缺 `round`）＝不知道。依據雜湊 `sha`＝來源物件的正規 JSON（鍵排序）的 sha256。
4. 跑鏈。

### 4.2 判

依序，先中先停：

| # | 情況 | 結果 |
|---|---|---|
| 1 | 宣告壞、鏈被改 | unknown（不撐） |
| 2 | 來源檔確定不存在 | `absent`（不撐）；`last` 留著 |
| 3 | 讀取失敗：路徑指不到、`ct` 不知道、來源檔不知道、`select_missing`、`not_number` | **耐性分支**：上一份暫存器是 `ok` 且耐性沒到期＝維持 `ok`（舊 `value`／`basis`，`why` 記這次的原因，`held`＝離上次讀取成功幾回合）；否則 unknown |
| 4 | 依據作廢：來源 `round > ct + 1`（舊鐘留下的檔），或 `sha` 等於 reset 時作廢的那一份 | unknown（`void_basis`） |
| 5 | 過期（§3） | unknown（`expired`） |
| 6 | 停太久（§3） | unknown（`stalled`） |
| 7 | `within_error_band`、`need` 欄是 null（`need_missing`） | unknown |
| 8 | 其餘 | `ok`，採用新依據 |

- 第 4～8 列都算「讀取成功」（`last_ok_my_round`＝這回合）：讀到了，只是答案是不能用；不靠耐性撐舊值。
- `reset` 那一圈：把上一份依據的 `sha` 記成作廢、`last` 標 `void: true`，耐性分支不再撐它。
- **skipped**：讀到的 `seq` 比框架的 `last_seq` 大 `k` 就加 `k − 1`（漏取樣的版數）；`seq` 不變、變小或沒帶都不加。`last_seq` 只往讀到的值更新。

### 4.3 寫

先寫框架（槽 `state.json`），再寫暫存器——被殺在兩者之間，下一圈從框架重算同一版，`skipped` 不重加。寫不進去記 stderr（`out.log`），下一圈再來。

## 5. 暫存器與框架

暫存器 `in/<sense>.json`：

```json
{"v": 1, "sense": "temp", "state": "ok|unknown|absent", "value": {"c": 80.1, "hot": true} | null, "err": {"c": 0.05},
 "basis": {"src": "src/out/temp.json", "sha": "…", "seq": 12, "src_round": 57},
 "chain": {"sha": "宣告雜湊前 16"}, "trace": [{"step": "select", "x": 801, "err": 0}, …], "omitted": [],
 "age_src_rounds": 0, "src_state": "advancing|stalled|reset|unknown", "stall_rounds": 0, "skipped": 3,
 "why": null, "detail": null, "held": 0, "last": {"value", "err", "basis", "my_round", "void"?} | null, "my_round": 63, "at": "…"}
```

- `err`＝每個數字產出欄各自的誤差界（`as` 產出時的值）；門檻產出是 bool，沒有誤差欄。`why` 是原因碼（§4.2 各列），`detail` 是給人看的說明。
- `state` 不是 `ok` 時 `value`、`err` 是 `null`（消費者讀不到欄位，不會誤用）；這圈讀到的依據仍放 `basis`、算到一半的放 `trace`，給人追。
- `last`＝最近一份 `ok` 的值與依據（採用新依據時更新）。
- `omitted`＝來源物件裡沒被選到的葉路徑（扣掉 `v`、`seq`、`round`、`at`）。

框架（槽 `state.json`）：`{"v": 1, "sense", "chain", "since", "my_round", "last_ok_my_round", "last_clock", "last_seq", "stall_rounds", "skipped", "resetting", "void_sha", "prev_state", "cur", "last"}`（`cur`＝撐舊值時用的那份 ok 內容）。讀不到或壞＝這圈暫存器寫 unknown（`frame_bad`，`last` 從現有暫存器抄），框架不動、等人刪。

## 6. 檢查器（`aos7-adapt check`）

回 `[{"level": "error", "where", "rule", "why"}]`，有 error 退出碼 1；任務每圈也跑。規則：未知欄；必填欄；型別（`sense`／`as` 名字格式、空間路徑、`src_clock` 檔名、非負整數或 null）；步種類與參數（§2）；`select` 在第一步且只一個；`scale` 的 `q` 夠蓋取整；`threshold` 恰一個比較鍵；`as` 不重複；`need` 都在產出裡。

## 7. 明確不管（誤用，不處理）

人手改暫存器、框架；工作中改鏈宣告（偵測到就 unknown，見 §4.1）；兩個 adapt 任務寫同一個 sense；來源不用原子 rename 寫（讀到半份就是 unknown 分支，不保證讀得到完整的）；來源偽造 `round`／`seq`；來源檔換成資料夾或 FIFO（落到不知道）。
