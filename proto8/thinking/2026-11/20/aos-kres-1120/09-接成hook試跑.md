# 把資源宣稱粗化原型接成問腦總機的兩支 hook、用假腦試跑一次（線 aos-kres-try-1120）：跑起來了，換規則不用重起；hook 改的優先序這一輪不算數（實測到）；卡點是宣稱沒約定位置、帳不收宣稱、兩支 hook 的格對不起來、hook 壞了整站停

← [README](README.md)｜使用者的答案：[08-使用者已答](08-使用者已答.md)｜原型：[04-D](04-D-原型.md)、[04-D-程式](04-D-原型-程式.md)｜昨天掛 hook 的做法：[aos-htop-1119 03](../../19/aos-htop-1119/03-自訂kernel-形式與最小實測.md)

使用者 11-20 選「把原型接成 hook 試一次」（說明：「在乾淨複本上把粗化原型接成問腦總機的一支 hook，跑一次看手感。不改程式，只是試，不留成功能。」）。**只是試：repo 裡的程式、範本、條文、知識庫一行沒動；hook、規則檔、假腦都在 repo 外，不留成功能。** 只用假腦，沒叫真模型。頂層派、線隊長交。

## 先講結論

1. **跑起來了。** 請求信 body 多帶一塊 `resource`（宣稱）→ `before_verdict` hook 照規則檔算成一個 0～1 的 `cost` 或「看不懂」→ `before_reply` hook 把實際 token 與時間跟宣稱並排記一筆。使用者原話的四種宣稱結果跟原型一樣：`0.1721`、看不懂、`0.2461`、`0.2`。
2. **換規則不用重起**：跑到一半把規則檔 v1 換成 v2，下一封就照 v2（第二種從看不懂變 `0.0075`），daemon 的 pid 沒變。原因是 hook 每封信都是新起的行程、每次重讀規則檔。
3. **hook 改的優先序，這一輪不影響排位（實測到）**：兩封信同一輪進來、只有一格空，hook 把後寄的那封改成 high，結果還是先寄的那封先跑；同樣的信由寄件人自己寫 high，就是它先跑。信排著等到下一輪，hook 改的 high 才算數。
4. **每封信多花的**：一支 hook 一次約 22 ms（起 `aos-exec`＋python）；兩支都掛時，有信的那一輪中位數從 57 ms 變 77 ms。對請求者來說，問一次從約 1050 ms 變約 1080 ms，大頭是總機每 300 ms 才跑一輪，不是 hook。
5. **卡點**（「給位置和格式」今天缺的，下面有清單）：宣稱放哪沒約定；帳本不收宣稱，「說的 vs 實際」要自己用信名去對兩份檔；兩支 hook 各有各的格，後一支得知道前一支叫什麼名字才找得到宣稱；hook 自己量的時間跟帳本的不是同一個數；hook 一壞（預設），整台總機每封信都卡住，連沒帶宣稱的信也一樣。

## 做了什麼、怎麼接

- 乾淨複本：`git archive HEAD`（`c59f1443c`）抄到公司 WSL `~/.aos/scratch/aos-kres-try-1120/repo/`，在複本裡跑 `install.py`。暫存樹 `t/` 從範本 `templates/start-api` 抄出來，**只起 llm daemon（問腦總機）**，沒起 root、沒起 agent；請求用 `aos-llm ask --full`／`aos-llm send` 直接從殼裡寄（最不繞：`aos-llm` 把 stdin 的 body 原樣寄出，多的 key 也照帶）。
- 只改暫存樹裡的 `llms/def/kernel.json` 與它旁邊放的檔，總機程式沒動：

```
t/llms/def/
  kernel.json        ← 改：slots 1、reserved {}、預設 endpoint 換成 fake-counted、加兩個假腦 endpoint、加 hooks
  kres/claim         ← before_verdict：讀 body.resource，照 rules.json 粗化，寫進自己的格
  kres/actual        ← before_reply（只通知）：找 claim 記的那筆，跟實際 usage 並排記一筆
  kres/coarsen.py    ← 原型的 coarsen.py 原樣抄來（全文在 04-D-程式）
  kres/rules.json    ← 規則檔（v1 起跑；跑到一半換 v2、v3）
  kres/schema.json   ← 對外放話的 schema（示意位置；原型那份原樣，全文在 04-D-程式）
  fake_counted/_entry ← 假腦：回固定答案，usage 照字數亂編一個不是 0 的數
```

- `kernel.json` 加的那段（用 python 改進去的，結果等於）：

```json
"slots": 1, "reserved": {}, "endpoint": "fake-counted",
"endpoints": {"…原本的…": "…",
  "fake-counted":      {"exec": "fake_counted", "delay_s": 0.2, "speed": "fast", "cost": "free",
                        "summary": "trial fake brain with made-up non-zero usage (line aos-kres-try-1120)"},
  "fake-counted-slow": {"exec": "fake_counted", "delay_s": 3, "speed": "fast", "cost": "free",
                        "summary": "same, takes 3 s (to make a queue with slots 1)"}},
"hooks": {"kres_claim":  {"event": "before_verdict", "handler": "kres/claim"},
          "kres_actual": {"event": "before_reply", "handler": "kres/actual", "intercept": false}}
```

- 為什麼另寫假腦：範本的 `llm_fake` 回的 usage 永遠是 0，「說的 vs 實際」就沒得比。`fake_counted` 的 token 是「prompt 字數÷4＋12」，**是編的**，只為了有個不是 0 的數。

### `kres/claim`（before_verdict）

```python
#!/usr/bin/env python3
# Trial hook (before_verdict) for line aos-kres-try-1120: read the resource claim in body.resource (key picked for the
# trial only), coarsen it with rules.json next to this file, and keep the result in this hook's own cell ($AOS_STACK).
# Optional knob in rules.json: priority_if_cost_below = {"cost": x, "level": "high"} sets body.priority (trial only).
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from coarsen import coarsen  # noqa: E402  (copied unchanged from the aos-kres-1120 prototype)

started = time.time()
event = json.load(sys.stdin)
cell = os.environ.get("AOS_STACK") or "."
with open(os.path.join(HERE, "rules.json")) as stream:   # unreadable rules = this hook fails, on purpose
    rules = json.load(stream)
body = event.get("body") if isinstance(event.get("body"), dict) else {}
claim = body.get("resource")
result = {"none": "no resource claim in body"} if "resource" not in body else coarsen(claim, rules)
knob = rules.get("priority_if_cost_below")
set_to = None
if isinstance(knob, dict) and "cost" in result and result["cost"] < knob["cost"]:
    set_to = knob["level"]
row = {"letter": event.get("letter"), "sender": event.get("sender"), "sent_at": event.get("sent_at"),
       "seen_at": started, "rules_version": rules.get("version"), "claim": claim, "result": result,
       "priority_before": body.get("priority"), "priority_set": set_to}


def append(name, entry):
    with open(os.path.join(cell, name), "a") as out:
        out.write(json.dumps(entry) + "\n")


append("claims.jsonl", row)
if "unreadable" in result:
    append("unreadable.jsonl", {"letter": row["letter"], "rules_version": row["rules_version"],
                                "claim": claim, "why": result["unreadable"]})
if set_to is not None:
    body["priority"] = set_to
    print(json.dumps({"body": body}))
```

### `kres/actual`（before_reply，只通知）

```python
#!/usr/bin/env python3
# Trial hook (before_reply, notify only) for line aos-kres-try-1120: find what the kres_claim hook recorded for this
# letter (its cell is a sibling of mine), read the real usage in the reply, and write one "said vs actual" row.
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from coarsen import coarsen  # noqa: E402

now = time.time()
event = json.load(sys.stdin)
cell = os.environ.get("AOS_STACK") or "."
said = None
try:
    with open(os.path.join(cell, "..", "kres_claim", "claims.jsonl")) as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("letter") == event.get("letter"):
                said = row   # last one wins
except OSError:
    pass
body = event.get("body") if isinstance(event.get("body"), dict) else {}
usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
ms = None if said is None else round((now - said["seen_at"]) * 1000)
tokens = usage.get("total_tokens")
actual = {"tokens": tokens, "ms_since_claim_seen": ms}
with open(os.path.join(HERE, "rules.json")) as stream:
    rules = json.load(stream)
actual_cost = coarsen({"cost": {"token": tokens or 0}, "time_ms": ms or 0}, rules)
error = body.get("error") if isinstance(body.get("error"), dict) else None
entry = {"letter": event.get("letter"), "sender": event.get("sender"),
         "said": None if said is None else said["claim"],
         "said_cost": None if said is None else said["result"],
         "said_rules_version": None if said is None else said["rules_version"],
         "actual": actual, "actual_cost": actual_cost, "actual_rules_version": rules.get("version"),
         "reply_error": None if error is None else error.get("code")}
with open(os.path.join(cell, "said_vs_actual.jsonl"), "a") as out:
    out.write(json.dumps(entry) + "\n")
```

### `fake_counted/_entry`（假腦）

```python
#!/usr/bin/env python3
# Trial endpoint function for line aos-kres-try-1120: a fake brain that sleeps endpoint.delay_s and reports made-up but
# non-zero usage (prompt chars / 4, fixed 12 completion tokens), so "said vs actual" has something to compare.
import json
import sys
import time

args = json.load(sys.stdin)
endpoint = args.get("endpoint") or {}
request = args.get("request") or {}
time.sleep(float(endpoint.get("delay_s", 0)))
text = json.dumps(request.get("messages") or [])
prompt = max(1, len(text) // 4)
print(json.dumps({"message": {"role": "assistant", "content": "FAKE COUNTED ANSWER"},
                  "usage": {"prompt_tokens": prompt, "completion_tokens": 12, "total_tokens": prompt + 12},
                  "model": "fake-counted"}))
```

### 規則檔

- v1＝原型的 `rules.json` 原樣，v2＝原型的 `rules_v2.json` 原樣（只差 `version: 2`、`missing_part: "treat_as_zero"`），全文在 [04-D-程式](04-D-原型-程式.md)。
- v3＝v1 加一個試跑用的旋鈕，只在排位那一段用：

```json
"version": 3,
"priority_if_cost_below": {"cost": 0.05, "level": "high"},
"note": "…原句… v3 adds a trial knob: coarse cost below 0.05 gets priority high."
```

## 每封請求變成什麼（規則 v1）

| 信 | body.resource | hook 算出的 | 說明 |
|---|---|---|---|
| r0 | 沒帶 | `{"none": …}` | 照常跑，hook 只記一筆「沒帶」 |
| r1 | `{"cost":{"token":{"in":123,"out":122}},"time":122,"time_unit":"ms"}` | `0.1721` | token 245、122 ms |
| r2 | `{"cost":{"token":{"out":"/home/x/ws/out_estimate.json"}},"time_ms":1500}` | 看不懂 | `out` 是路徑，hook 沒去開；進 `unreadable.jsonl` |
| r3 | `{"cost":{"token":123,"time":"32s"}}` | `0.2461` | `"32s"` 讀成 32000 ms |
| r4 | `{"cost":0.2}` | `0.2` | 照 schema 寫，原樣收 |
| r6 | `{"cost":43}`（細化的例子） | 看不懂 | 超出 0～1、又沒有 token／time 可讀 |

- 六封都拿到假腦的回答；帶什麼宣稱、看不看得懂，**都不影響信照常跑**——hook 只記、不擋（這是本線的寫法，hook 也可以擋）。
- 細化沒做，原因：細化是「kernel 吃細的形狀，請求只給一個粗數」時才用得上，這台總機對外說它只看一個 0～1 的 `cost`，拿到細的資料沒有地方用（總機能動的只有 priority、額度、判決）；在這支 hook 裡把 43 拆成 token／time 再粗化回一個數，等於繞一圈。r6 只送來看粗化這邊怎麼對待它：看不懂。要試細化，得換一台「吃 token、time」的 kernel，hook 那條路本身沒擋。

## 說的 vs 實際

`kres_actual` 每封記一筆，用信名去對帳本 `ledger.jsonl` 同一封。v1 那幾封（假腦 0.2 秒）：

| 信 | 說的（粗化後） | 實際 token | hook 量的時間 | 實際照同一條公式算 | 帳本 elapsed_ms |
|---|---|---|---|---|---|
| r0 | 沒帶 | 24 | 755 ms | 0.0206 | 730 |
| r1 | 0.1721 | 24 | 745 ms | 0.0205 | 719 |
| r2 | 看不懂 | 24 | 738 ms | 0.0205 | 713 |
| r3 | 0.2461 | 24 | 735 ms | 0.0205 | 711 |
| r4 | 0.2 | 24 | 735 ms | 0.0205 | 710 |
| r6 | 看不懂 | 24 | 742 ms | 0.0205 | 718 |

一筆長這樣（原樣）：

```json
{"letter": "01795136409911306949.51606.421110", "sender": "/home/guanyu/.aos/scratch/aos-kres-try-1120",
 "said": {"cost": {"token": {"in": 123, "out": 122}}, "time": 122, "time_unit": "ms"},
 "said_cost": {"cost": 0.1721, "how": "rule v1: tokens=245 ms=122"}, "said_rules_version": 1,
 "actual": {"tokens": 24, "ms_since_claim_seen": 745}, "actual_cost": {"cost": 0.0205, "how": "rule v1: tokens=24 ms=745"},
 "actual_rules_version": 1, "reply_error": null}
```

看得到的：

- 假腦的 token 是編的，所以「說多用少」這件事本身沒意義；看的是**帳能不能對起來**——能，用信名對得上，27 封有宣稱紀錄的都對上了。
- **hook 量的時間跟帳本不是同一個數**：帳本從「掛上去」算，hook 只能從「自己看到信」算到「回信前」，中間多了排隊。不排隊時只差約 25 ms；排隊時差很多（3 秒假腦、排在別封後面那封：hook 7088 ms，帳本 3523 ms）。`before_reply` 的事件裡沒有掛上的時間，也沒有寄出時間，hook 拿不到帳本那個數，除非自己去讀 `ledger.jsonl`。
- 帳本 36 列裡有 9 列對不到宣稱：8 列是拔掉 hook 量耗時那段，1 列是 hook 壞掉、照 `continue` 放過去那封（見下面「hook 壞掉」）。

## 換規則（v1→v2）要不要重起：不用

跑完 r1～r6 之後，把 `kres/rules.json` 換成 v2（先寫暫存檔再改名），沒碰 daemon：

| 信 | 規則 | 結果 |
|---|---|---|
| r2b（同 r2） | v2 | `0.0075`（`rule v2: tokens=None ms=1500`；token 那半看不懂當 0） |
| r1b（同 r1） | v2 | `0.1721`（跟 v1 一樣） |

daemon pid 前後都是 51397。每封信的 hook 都是新起的行程、每次都重讀規則檔，所以換檔＝下一封生效。`kernel.json` 本身也是每輪重讀，拔掉、加回 hooks 也都不用重起（量耗時那段就是這樣做的）。

## 排位那件：`order` 在 hook 之前跑，hook 改的 priority 這一輪不算數——實測到

設定：`slots: 1`、不留 high 格、3 秒的假腦。規則 v3（粗化後 cost＜0.05 的信 hook 改成 high）。要讓兩封信「同一輪」進來，本線用了一個只為測試的作法：先用 `aos-llm send` 把信寄進一個假的信箱（放在總機 stack 旁邊），再一個 `mv` 把兩封一起搬進總機的 `requests/new/`。

| 情境 | 信 | 誰先跑完 |
|---|---|---|
| A. hook 決定：B（cost 0.9，先寄）、C（cost 0.01，hook 改 high）同一輪進來、有一格空 | B、C | **B +3746 ms**，C +7308 ms |
| B. 對照：同上，但 C 由寄件人自己寫 `priority: high` | B2、C2 | **C2 +3862 ms**，B2 +7391 ms |
| C. 下一輪：A3 先佔住格；B3（0.9）、C3（0.01，hook 改 high）一起進來排著 | A3、B3、C3 | A3 +3883，**C3 +7431**，B3 +10952 |

- A：hook 確實把 C 改成 high（`claims.jsonl` 的 `priority_set: "high"`，排著時 `bodies/<C>.json` 裡也是 high），但這一輪的順序在 hook 跑之前就排好了，B 在前、拿到唯一那格。
- B：同樣的信，high 寫在寄件人那邊，排序一開始就看得到，C2 先。
- C：信排著到下一輪，總機照 `bodies/` 裡改過的 body 排，C3 跑到 B3 前面。也就是 hook 改的 priority **從下一輪起才算數**；跟 kernel_llm README 寫的「新信第一輪的位置照改之前的 body 排」一致。
- 也看到：hook 每封信只跑一次，信排著的那幾輪不會再跑（7 封信 7 筆紀錄）。

測試作法的副作用（第一次照錯的作法做時踩到）：`aos-llm send` 把 `reply_to` 存成「相對於它寄進去的那個 stack」的路徑。第一次把假信箱放在別處，信搬進總機後回信的路就錯了，總機 log 印 `MailboxMissing … letter deleted anyway`，兩封的回信丟了（跑還是有跑、帳也記了）。第二次把假信箱放在總機 stack 的旁邊（同一層），就對了。

## 每封多花多少時間

| 量什麼 | 結果 |
|---|---|
| 空的 `python3 -c pass` | 10 ms／次 |
| 照總機的起法跑一次 `kres/claim`（`aos-exec --stack <格>/ <handler> < event.json`） | 22 ms／次 |
| 同上 `kres/actual` | 22 ms／次 |
| 總機有信那幾輪的長度，中位數：拔掉 hooks（8 封）→ 兩支都掛（8 封） | 57 ms → 77 ms |
| 從殼裡問一次（`aos-llm ask`）的牆鐘時間，同上兩組 | 約 1036～1108 ms → 約 1056～1097 ms |

一封信要經過兩支 hook（判決前一次、回信前一次），各在不同的一輪，所以每封多約 2×22 ms 的行程。問一次整整一秒，主要是總機每 300 ms 才跑一輪、信要經過好幾輪，hook 的 20 ms 在這裡面看不太出來。

## hook 壞掉時整輪怎樣

把 `rules.json` 寫壞（不是 JSON），兩支 hook 都會在讀規則時出錯。

| 設定 | 結果 |
|---|---|
| 預設 `on_error: stop` | 帶宣稱的那封等 8 秒沒回（`timeout` 收掉）；**另一封沒帶宣稱的信一樣卡住**（hook 對每封信都跑）。那段時間總機每輪都退 1（19 輪），log 每輪印一份 python 的 traceback 加 `HookFailed hook kres_claim (event before_verdict) failed: exited 1`。寄件人放棄後信被收拾掉，總機才回到退 0；信沒跑、帳沒記、hook 也沒紀錄 |
| 兩支都改 `on_error: continue` | 信照跑、拿到回答；log 兩行 `warning: hook … failed: exited 1; going on without it`；帳本有這封，hook 的兩份紀錄都沒有這封（悄悄少一筆） |

改回 v1 規則與原本的 `kernel.json`，下一封就正常，不用重起。

## 卡點清單（對照使用者的答案「給位置和格式。當然，這都是可選的，kernel自己可以選擇不給。」）

只列今天缺的與卡的，不設計、不推薦。

**位置**

1. 宣稱放 body 的哪個 key 沒有約定；本線自己挑了 `resource`。總機不擋多的 key、`aos-llm` 也原樣帶過去，所以「放得進去」沒問題，缺的是大家都放同一個地方。
2. 帳本 `ledger.jsonl` 不收宣稱。要「說的 vs 實際」，只能 hook 自己另記一份，再用信名去對帳本。
3. 兩支 hook 各有各的格（`hooks/<名字>/`），後一支要找前一支記的宣稱，得寫死前一支的名字（`../kres_claim/`）。沒有「同一封信」共用的地方。

**格式**

4. schema 放了一份在 `def/kres/schema.json`，但沒有任何東西指向它：`interfaces.json` 今天只宣告了帳本在哪，請求者不知道這台總機收不收宣稱、收什麼形狀。
5. 粗化結果（`claims.jsonl`）、看不懂的樣本（`unreadable.jsonl`）、說的 vs 實際（`said_vs_actual.jsonl`）的欄位都是本線自己定的，htop、gdb 或別的 kernel 讀不懂。
6. 「實際」用哪個數沒定：hook 拿得到回信裡的 usage，但拿不到帳本的 `elapsed_ms`（`before_reply` 事件沒有掛上時間、寄出時間），自己量的又含排隊。
7. 規則檔放哪沒定：本線放在 kernel 定義夾旁（第 3 題使用者答「先不定」）；放這裡換檔即生效，但跟定義夾混在一起。

**可選（「kernel自己可以選擇不給」）**

8. 今天「不給」是自動成立的：沒掛這種 hook 的 kernel 就是不看 `resource`、信照跑。但請求者分不出「這台不看宣稱」和「這台看了、看不懂」。
9. 掛了之後是全有全無：hook 對每封信都跑（沒帶宣稱也一樣），預設一壞整台停；改成 `continue` 又會悄悄少記。

**順手看到的事實**

10. 事件檔 `event.json` 每封都寫整份 body（含 prompt）；這支 hook 只要 `resource`，看到的卻是整封信（昨天 aos-htop-1119 也記過）。
11. 寄件人 `sender` 是信封上自報的路徑：從殼裡直接 `aos-llm` 寄、沒有 `AOS_STACK` 時，就是當下的工作目錄（本線一次從 Windows 的目錄下指令，記成 `/mnt/c/…`）。帳本與 hook 的 `sender` 一致（同一個來源），所以對得上；但要準確對同一封，靠的是信名。
12. 總機自己拒掉的信（`BudgetMissing`、`LetterBad`…）照 README 不跑 `before_reply`，會只有宣稱、沒有實際（本線沒實測這一條）。
13. hook 改的 priority 這一輪不算數（上面情境 A）；「便宜的先」這類規則，偏偏在「剛進來就有空格」那一刻沒效。

## 想自己試的話

全部在公司 WSL，暫存夾 `~/.aos/scratch/aos-kres-try-1120/`（複本已裝好、樹 `t/` 已建好；daemon 已收掉）。腳本開頭都先清掉 `AOS_*`。

```sh
S=~/.aos/scratch/aos-kres-try-1120
# 再起總機（樹已在，up.sh 會拒絕重建）
cd $S/t/llms && . $S/env.sh && setsid aos-exec --stack stacks/llm def > $S/llm.log 2>&1 < /dev/null &
bash $S/ask.sh x1 '{"cost":{"token":123,"time":"32s"}}'   # 寄一封帶宣稱的
bash $S/show.sh                                           # 看兩支 hook 的紀錄與帳本對照
bash $S/table.sh                                          # 一封一行的說的 vs 實際
# 改規則：直接編 $S/t/llms/def/kres/rules.json，下一封就生效
bash $S/prio.sh     # 排位那三個情境（會把規則換成 v3，跑完換回 v1）
bash $S/broken.sh   # hook 壞掉的兩種設定（跑完還原）
bash $S/down.sh     # 收掉
```

要從頭在新夾重來：把 `env.sh`、`mk.sh`、`up.sh` 裡的 `S=` 改成新夾，跑 `mk.sh`、`up.sh`。

## 本線替使用者定的示意與選擇

- 宣稱放在 body 的 `resource` 這個 key——示意。
- 規則檔、schema 放在 kernel 定義夾的 `kres/` 底下——示意位置。
- hook 只記不擋（看不懂也照跑）；v3 的「cost＜0.05 改 high」旋鈕只為排位那段實驗。
- 「實際時間」用 hook 自己量的（從判決前看到信到回信前），「實際 cost」拿同一條粗化公式去算實際用量——都是本線的做法。
- 另寫一個會回非 0 token 的假腦，token 數是編的。
- 細化沒做（理由在上面）。
- 測試時把 `slots` 改 1、拿掉 high 保留格，用「先寄進旁邊的假信箱再一起搬進去」湊出同一輪兩封。

## 暫存夾裡本線留下、沒用上的東西（沒刪）

`prio_v1_broken_staging.sh`（第一版排位腳本，假信箱放錯位置那版）、`replies2/`、`timing/`、`t/llms/stacks/stage/`、`recvtest.sh`、`where.sh`、`nohook.sh` 量完後留下的 `kernel.with-hooks.json`、`kernel.before-broken.json`。
