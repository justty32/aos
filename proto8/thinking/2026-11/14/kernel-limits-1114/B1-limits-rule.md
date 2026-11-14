# 圖紙 B1：kernel 站附限制與身分（limits_rule.py）——線限 11-14，照 11-13 kernel-limits-plan 段 2＋段 3 的 kernel 部分

← [線限 11-14 紀錄](../kernel-limits-1114.md)｜設計出處：[kernel-limits-plan 03 第三節](../../13/kernel-limits-plan/03-opus細化.md)、[04 段 2](../../13/kernel-limits-plan/04-施工與驗收.md)、[08 號段](../../13/kernel-limits-plan/08-群組用法.md)

施工隊照這份寫碼，不做設計決定。圖紙沒寫到、或自相矛盾＝BLOCKED，不自己定。

## 0. 範圍（只准動這些檔）

- 新增 `proto8/lib/aos/kernel/limits_rule.py`
- 改 `proto8/lib/aos/kernel/procs_rules.py`（只改 `import` 區、`load`、`dispatch` 三處）
- 新增 `proto8/lib/aos/kernel/tests/test_limits_rule.py`
- 改 `proto8/lib/aos/kernel/README.md`（只在 `## kernel.json` 鍵表加三列，並在 `## hooks` 之前加一節 `## 限制與身分（limits、users、groups）`）

其他任何檔不動。程式輸出（錯誤訊息）一律英文；註解用繁體中文；新檔第一行寫一句話說這檔做什麼（`# ...`）。

## 1. 背景（施工隊需要知道的事實）

- daemon 收的「加 proc」信：body 的 `procs_added` 是 `{名字: proc}`。proc 可以是字串、陣列（exec 型）或物件。物件的 `limits` 是 `{mem_mb, cpu_s, procs, file_mb, files: 正整數; user: 字串}`；`limits: {}`＝daemon 不限、`limits: null` 或沒寫＝用 daemon 預設。
- 掛 proc 那一包是 `procs_rules.py`：`load(cfg, cfg_dir)` 驗設定（錯丟 `round.CfgBad`）；`dispatch(ctx, name, letter, detail)` 呼叫 `letters.forward(ctx, name, letter, box)` 轉寄，轉寄寄出去的 body 是 `letter["body"]`；`dispatch` 回 `(code, msg)` 時骨架拒這封信。
- `letter["sender"]` 是信封上的寄件人字串（可能沒有）。

## 2. kernel.json 新鍵（掛 proc 那一包認）

```json
{"limits": {"default": {"cpu_s": 3600, "files": 1024},
            "max":     {"cpu_s": 7200, "files": 4096, "file_mb": 2048},
            "by_sender": {"/abs/stack/of/sol-T01": {"cpu_s": 600}}},
 "users":  {"sol-*": "sub:2001",
            "lead":  {"user": "sub:2002", "groups": ["t1"]}},
 "groups": {"t1": 60001}}
```

三個鍵都選填；值是 `null` 等同沒寫。

## 3. limits_rule.py 的介面

```python
KEYS = ("mem_mb", "cpu_s", "procs", "file_mb", "files")   # 這個順序也是 limits_clamped 的順序

def load(cfg):            # 驗 limits／users／groups；錯丟 round.CfgBad(訊息)
def active(cfg):          # cfg 裡 limits 或 users 不是 None（有寫）就 True；只寫 groups 不算
def apply(cfg, body, sender):   # 回 (新 body, None) 或 (None, (code, msg))
```

`from round import CfgBad`（跟 procs_rules.py 一樣的 import 方式）。只用標準庫（`copy`、`fnmatch`）。

### 3.1 load：驗設定（訊息逐字照下表，`<…>` 換成實際值）

| 情況 | CfgBad 訊息 |
|---|---|
| `limits` 不是物件也不是 null | `limits must be an object {default, max, by_sender} or null` |
| `limits` 有 default／max／by_sender 以外的鍵 `k` | `limits.<k> is not a known key (default, max, by_sender)` |
| `limits.default`／`limits.max` 不是物件 | `limits.<default 或 max> must be an object of limit keys` |
| 上面兩個物件裡有 KEYS 以外的鍵 `k` | `limits.<default 或 max>.<k> is not a limit key (mem_mb, cpu_s, procs, file_mb, files)` |
| 值不是正整數（bool 不算整數） | `limits.<default 或 max>.<k> must be a positive integer` |
| `limits.by_sender` 不是物件 | `limits.by_sender must be an object {sender: limits}` |
| `by_sender` 的某個值 | 同上兩列的檢查，位置寫成 `limits.by_sender[<sender>]`（例 `limits.by_sender[/a/b].cpu_s must be a positive integer`；不是物件＝`limits.by_sender[<sender>] must be an object of limit keys`） |
| `users` 不是物件也不是 null | `users must be an object {name pattern: user} or null` |
| `users` 的值不是非空字串、也不是物件 | `users[<pattern>] must be a user string or {"user": string, "groups": [names]}` |
| 物件形狀：沒有 `user`、`user` 不是非空字串、有 user／groups 以外的鍵、`groups` 不是字串陣列 | 同上一列 |
| user 字串以 `sub:` 開頭但後面不是 1～60000 的十進位整數（不准前導 0、正負號、空白） | `users[<pattern>]: sub:N needs N from 1 to 60000` |
| `groups` 裡的名字不在 `groups` 表 | `users[<pattern>].groups names <名字>, which is not in groups` |
| `groups` 不是物件也不是 null | `groups must be an object {name: number} or null` |
| `groups` 的值不是 60001～65536 的整數（bool 不算） | `groups.<name> must be an integer from 60001 to 65536` |

`sub:` 以外的 user 字串（帳號名）只驗非空，照原樣交給 daemon。

### 3.2 apply：改 body

1. `active(cfg)` 是 False：回 `(body, None)`，**回的是同一個物件、不複製**（這樣沒寫新鍵的站轉寄的 body 跟以前一模一樣）。
2. body 不是物件、或沒有 `procs_added`：回 `(body, None)`（同一個物件）。
3. `procs_added` 不是物件：回 `(None, ("BodyBad", "procs_added must be an object"))`。
4. 先 `copy.deepcopy(body)`，之後只改複本。`procs_added` 照原本的名字順序逐支處理（名字＝`name`、值＝`spec`）：
   - `spec` 是字串或陣列：當作 `{"exec": spec}` 處理；最後如果要加的 `limits`／`limits_clamped` 都沒有，就放回原本的字串或陣列（不包）。
   - `spec` 是物件、而且有任何一個鍵以 `$` 開頭：回 `(None, ("BodyBad", "procs_added[<name>] is written as a directive; a station with limits or users cannot check it, write the proc out in full"))`。
   - `spec` 是別的型別：回 `(None, ("BodyBad", "procs_added[<name>] must be a string, an array or an object"))`。
   - 拿掉 `spec` 裡寄件人自帶的 `limits_clamped`（不管有沒有夾）。
   - `own = spec.get("limits")`：不是物件也不是 None ＝回 `(None, ("BodyBad", "procs_added[<name>].limits must be an object or null"))`。
   - `own` 是物件時，先拿掉裡面的 `user`、`groups` 兩個鍵（寄件人自帶的身分一律丟）。
   - **起點 `lim`**：`own` 是 None、或拿掉 user／groups 後是空物件 → `lim` ＝「有效預設」的複本：`limits.default`（沒寫＝`{}`）先放，再用 `limits.by_sender[sender]`（sender 字串完全相等才算；沒對到不加）逐鍵蓋過。否則 `lim` ＝ `own`（拿掉 user／groups 後）的複本；**不跟預設合併**。
   - **夾**：`limits.max`（沒寫＝`{}`）裡的每個鍵 `k`，照 KEYS 的順序：`lim` 沒有 `k`、或 `lim[k]` 是整數（不是 bool）且大於 `max[k]` → `lim[k] = max[k]`，把 `k` 記進 `clamped`。`lim[k]` 是非整數的怪值就不動（留給 daemon 報錯）。
   - **身分**：`users` 照表的鍵順序，用 `fnmatch.fnmatchcase(name, pattern)` 找第一個對到的。對到字串＝`lim["user"] = 它`；對到物件＝`lim["user"] = 物件的 user`，`groups` 有寫而且不是空陣列＝`lim["groups"] = [groups 表[名字] for 名字 in 那個陣列]`（號碼、照陣列順序）。沒對到就不加身分。
   - **寫回**：`lim` 不是空物件＝`spec["limits"] = lim`；是空物件＝`spec` 拿掉 `limits` 鍵（讓 daemon 用它自己的預設；所以 `limits: {}` 在有開這條規則的站上等於「用預設」）。`clamped` 不是空的＝`spec["limits_clamped"] = clamped`。
5. 回 `(新 body, None)`。

`procs_started`、`procs_woken` 只是名字，不處理。

## 4. procs_rules.py 怎麼接

- import 區加 `import limits_rule`。
- `load(cfg, cfg_dir)`：最後加一行 `limits_rule.load(cfg)`。
- `dispatch`：在 `failure = letters.forward(...)` 那行之前加：

```python
    body, bad = limits_rule.apply(ctx.cfg, letter.get("body"), letter.get("sender"))
    if bad is not None:
        return bad
    if body is not letter.get("body"):
        letter = dict(letter, body=body)
```

其他行一字不改（`ctx.admitted` 那段照舊讀 `letter.get("body")`，讀到的是新的或原本的都一樣）。

## 5. 測試 tests/test_limits_rule.py

- `unittest`，風格照同夾的 `test_kernel.py`。兩部分：
  - **單元**：`sys.path.insert(0, <kernel 夾>)` 後 `import limits_rule`，直接叫 `load`／`apply`。
  - **整站**：照 `test_kernel.py` 的 `fixture`／`post`／`kernel()` 寫法（可以從那支複製需要的幾個函式進來，不要 import 它），寄一封 `procs_added` 信進站的 `requests`、跑一輪、讀 daemon 那邊 `procs_requests/new/<信名>/letter.json` 的 `body`。
- 至少要有這些例子（每例一個 test 方法）：
  1. 沒寫 limits／users：`apply` 回的是同一個物件（`assertIs`）；整站轉出的 body 等於原 body。
  2. `default: {cpu_s: 60}`、proc 沒帶 limits → 轉出 `limits == {"cpu_s": 60}`、沒有 `limits_clamped`。
  3. `max: {cpu_s: 100}`、proc 帶 `{"cpu_s": 200}` → `limits == {"cpu_s": 100}`、`limits_clamped == ["cpu_s"]`。
  4. `max: {cpu_s: 100, files: 50}`、proc 帶 `{"files": 10}` → `{"files": 10, "cpu_s": 100}`、`limits_clamped == ["cpu_s"]`。
  5. 只寫 `users: {}`（開著規則）、proc 帶 `{"user": "root", "cpu_s": 5}` → 轉出 `{"cpu_s": 5}`、沒有 user。
  6. `users: {"sol-*": "sub:2001"}`、proc 名 `sol-T01` → `limits.user == "sub:2001"`；名 `lead` 沒對到 → 沒有 limits。
  7. users 物件形狀加 groups 表 → `limits.groups == [60001]`。
  8. by_sender 蓋過 default（sender 相等才算；另一個 sender 用 default）。
  9. 字串 proc 在有 default 時被包成 `{"exec": 原字串, "limits": …}`；沒東西可加時照原字串。
  10. `limits: {}` 在開著規則、沒有 default 時 → 轉出的 proc 沒有 `limits` 鍵。
  11. proc 物件有 `$ref` 鍵 → `BodyBad`；整站：寄件人收到拒信 `{"applied": false, "error": {"code": "BodyBad", …}}`，daemon 那邊沒信。
  12. 寄件人自帶 `limits_clamped` 被拿掉。
  13. `load` 的錯：每列表 3.1 至少挑六列各一例，比對訊息全文。
- 跑法（必須全綠）：
  `python3 -m unittest discover -s proto8/lib/aos/kernel/tests -p 'test_limits_rule.py'`
  `python3 -m unittest discover -s proto8/lib/aos/kernel/tests`（舊的六支也要全過）

## 6. README 要加的

- `## kernel.json` 鍵表加三列（放在 `reply_via_me` 那列之後、`hooks` 之前）：
  - `limits`｜`{default, max, by_sender}`：每支新 proc 的份額預設、天花板、照寄件人的預設（值是正整數，鍵同 daemon 的 `limits`）｜不改份額
  - `users`｜`{名字樣式: 帳號}`，帳號是字串（`sub:N` 或帳號名）或 `{user, groups}`｜不填身分
  - `groups`｜`{群組名: 60001～65536}`，給 `users` 的 `groups` 換號｜沒有
- 新節 `## 限制與身分（limits、users、groups）`，五到八行，照第 3.2 節講清楚：沒寫＝原樣轉寄；起點（沒帶＝預設、帶了＝只用自帶的）；夾＝max 每鍵取小、沒帶的鍵補 max、記 `limits_clamped`；寄件人自帶的 user／groups／limits_clamped 一律丟；users 照名字樣式填；`$` 開頭的指示詞寫法＝`BodyBad`；`limits: {}` 在這種站等於用預設。
- 同一節最後一段寫明（逐字）：「**跟 daemon 的配合**：今天的 aos-daemon（11-14 前）還不認 `limits_clamped`（exec 型的 proc 多一個鍵會被當成 loop 設定）、`limits.groups` 與 `user: "sub:N"`；daemon 段 1、段 3 換上之前，`max` 只在不會夾到的情況用、`users` 不要填 `sub:N`、不要用 `groups`。見 [kernel-limits-plan 04](../../../thinking/2026-11/13/kernel-limits-plan/04-施工與驗收.md)。」
