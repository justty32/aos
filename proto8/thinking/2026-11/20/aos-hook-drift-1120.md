# hook 文件漂移 17 項補齊；eca 的 slash 信過兩次 before_queue 實跑屬實，使用者裁「修：只過一次」後已修

← [當天索引](README.md)｜待裁第 8 題 [10](aos-hook-plan-1120/10-待裁題.md)｜使用者已答 [13](aos-hook-plan-1120/13-使用者已答.md)｜17 項的來源 [第 1 刀紀錄](aos-hook-k1-1120.md)｜疑點來源 [調查線 05](aos-hook-iface-1120/05-B3-fsm與eca差在哪.md)

線 aos-hook-drift-1120，11-20 公司 WSL。使用者對 hook 待裁第 8 題選「派線：補文件＋查證」，之後說「開工吧」。頂層派、線隊長做。

## 結論

- 17 項全部是文件漏寫，沒有一項是程式錯；照程式與 `hook_points.json` 改了三份手抄（`06-hook.md`、self_hook 的 `_tooldef.json` 說明、知識庫 `me/self_hook.json`），**沒改程式**。
- `test_hook_points_match.py` 的已知清單清空、拿掉 `expectedFailure`：之後任何一份手抄漏了點名或欄位名就紅。
- 第二件**屬實**：eca 等回答時來的 `/compact` 信，`before_queue` 跑兩次（同一封信、同一個信名）；普通信只跑一次。第一輪只查證、沒修（commit `1bcde0265`）。
- 第二輪（下面「第三件」）：使用者裁「修：只過一次」，`midturn.py` 先認 slash 再過 hook；新測試守住四種情境各一次；改前 2 次、改後 1 次；開畫面走 socket 那條也實跑過（假的 CLI 那頭）。順手把 gdb 例子的 `BrainTimeout` 改成 `BrainFailed`。

## 第一件：17 項逐項

照使用者 11-20 的兩句寫：第 3 題「各自寫清楚就好」＝各身體分開寫、不統一；第 4 題「要」＝以宣告為準。欄位表不再各處手抄是後面的刀，這裡只把現有的字改對、沒重構。

| # | 哪份 | 少了 | 怎麼改 |
|---|---|---|---|
| 1 | `py/aos/apps/agent/docs/06-hook.md` 事件表 | `after_stop.cause` | after_stop 那列加 `cause`（九個值、照抄、空或沒給＝null、給程式比的代號不是給人看的 `reason`） |
| 2–9 | 同上 | `brain_failed` 的 `error`、`code`、`status`、`retry`、`attempt`、`wait_s`、`dropped`、`cause` | fsm 那列（事件表）寫 `error`（BudgetMissing、BrainFailed 解到 kernel 的 error 時）、`retry`／`attempt`（只有 BrainFailed）、`code`／`status`（kernel 的 error 有才帶）、`wait_s`（retry 為 true 才帶）；觸發代號補上漏掉的 `LlmKernelMissing`。eca 那列（下面「eca（縮水版）」表）寫 claude 的 `code`、`retry`、`attempt`、`dropped`、`wait_s`、`status`、`cause`，codex 只有 `name`、`reason` |
| 10 | 同上 | `on_clock.config` | on_clock 那列加「格裡寫了 `config` 才多 `config`（原樣）」 |
| 11–16 | `py/tools/agent/self_hook/_tooldef.json` 說明 | `brain_failed` 的 `retry`、`attempt`、`wait_s`、`dropped`、`status`、`cause` | brain_failed 那行改寫：error 物件、BrainFailed 的 retry／attempt／code／status／wait_s、eca claude 的 code／retry／attempt／dropped／wait_s／status／cause、eca codex 只有 name、reason |
| 17 | `knowledge/aos/me/self_hook.json` 的 events | `after_stop.cause` | after_stop 那句加 `cause` 與九個值、null 的情形、跟 `reason` 不同 |

順手改的（不在 17 項裡、測試抓不到，同一段的字）：

- `06-hook.md` 事件表上面加一段：欄位以各身體的宣告檔為準（連到 agent-fsm、loop、eca、mcp 四份），這張表是手抄、由 `test_hook_points_match.py` 比對。
- `06-hook.md` 的 fsm `before_queue` 補「`/compact` 信先被挑走，不過這裡」。
- `06-hook.md` 的「eca（縮水版）」表加一欄「跟 agent-fsm 不同的地方」，逐事件寫：before_queue slash 信也過、等回答時來的信也過；after_queue 失敗等回答接進 history 才報；before_tool／after_tool 只有經 aos-mcp 的工具、`id` 是 JSON-RPC id 字串、`content` 併成一段、hook 失敗＝那次呼叫回 isError、agent 不停；brain_failed 代號與欄位不同、沒有 `error`；on_clock 每輪看一次；tool_added 的時機照宣告改成「每次交給 CLI 之前」（原寫「每輪開頭」）。
- self_hook 說明：after_stop 的 `cause` 原寫「or null from an old aos-loop」改成「or null when not given」（照 hook_fire：空的或沒設＝null；proto8 不留舊版說法）；on_clock 那行補 `config`（原本只在另一行的例子裡出現，測試是假過關）。
- 知識庫 `me/self_hook.json`：before_queue 補兩種身體的差別（fsm 的 `/compact` 不過、eca 的 slash 也過）；before_tool 補 eca 只看得到經 aos-mcp 的工具、hook 失敗只讓那次呼叫變錯誤；brain_failed 的 `code` 補「kernel 有給才帶」、補一句 `LlmKernelMissing`、`SendFailed`、`ReplyBad` 只有 `name`、`reason`。

沒碰的手抄：`docs/tutorial` 裡講 hook 的只有 06 第 69 行 gdb 的例子（`brain_failed("BrainTimeout")`），跟 17 項無關；`BrainTimeout` 不是兩種身體會發的代號（fsm 是 LlmKernelMissing、SendFailed、BudgetMissing、BrainFailed、ReplyBad，eca 是 CliFailed、ReplyMissing），`py/aos/apps/gdb/README.md` 同樣寫法——例子而已、不擋什麼，屬 gdb 文件，第一輪沒改、列給頂層（第二輪已改，見第三件）。`py/docs/` 沒有 hook 專章（hook 的文件在 `py/aos/apps/agent/docs/06-hook.md`）。

## 第二件：eca 的 slash 信過兩次 before_queue

### 怎麼跑

- 樹：`git archive e1209424b`（開工時的 HEAD）抄出、在複本裡跑 `install.py` 的 `~/.aos/scratch/aos-hook-drift-1120/base/`；清掉 `AOS_*` 後只設 `AOS_HOME` 到複本。
- 身體：直接跑複本的 `bin/aos-eca-turn --on-empty idle DEF`（aos-loop 每拍叫的就是這支，一拍一次）；沒起 daemon、沒經 aos-loop。假腦＝`py/tests/apps/eca/fake_claude_stream`（PATH 最前的 `claude`），定義的 `cli.json` 寫 `{"kind": "claude", "live_mail": true}`＝沒開畫面、等回答時來的信也收（跟 `test_live_mail.py` 同一條路）。
- hook：定義的 `hooks.json` 掛一格 `before_queue`，handler 是一支 sh：把事件 JSON 追加進 `calls.jsonl`、stdout 空（不改、不攔）。
- 四種情境各跑兩次、每次新的 stack：普通信單獨一輪；`/compact` 單獨一輪；送 `SLOW:3 first` 起一輪、CLI 收到後再送普通信，然後再跑一輪；同上但後來送 `/compact`。
- 腳本 `~/.aos/scratch/aos-hook-drift-1120/repro/repro.py`、`run.sh`；輸出 `repro/r1.out`。沒叫真模型。

### 結果（第 1 次；第 2 次逐項相同）

```
== plain letter alone, run 1
  before_queue calls per letter: {"hello 1": 1}
== slash letter alone, run 1
  before_queue calls per letter: {"/compact": 1}
== plain letter mid-turn, then one more turn, run 1
  before_queue calls per letter: {"SLOW:3 first": 1, "second 1": 1}
  CLI got: ["SLOW:3 first", "second 1"]
  history: [["user", "SLOW:3 first"], ["user", "second 1"], ["assistant", "FAKE: SLOW:3 first | second 1"]]
== slash letter mid-turn, then one more turn, run 1
  turn: exit 0
  turn: exit 0
  before_queue calls per letter: {"SLOW:3 first": 1, "/compact": 2}
  letters seen by the hook, in order: [["000000000001.01795146577904486923.817648.1437010", "SLOW:3 first"],
    ["000000000002.01795146578838669605.817735.1437104", "/compact"], ["000000000002.01795146578838669605.817735.1437104", "/compact"]]
  history: [["user", "SLOW:3 first"], ["assistant", "FAKE: SLOW:3 first"], ["user", "/compact"], ["assistant", "FAKE: /compact"]]
  left in queue: 0
```

| 情境 | before_queue 對那封信跑幾次 |
|---|---|
| 普通信，單獨一輪 | 1（兩次都 1） |
| `/compact`，單獨一輪 | 1（兩次都 1） |
| 普通信，等回答時來 | 1（兩次都 1，併進同一個回答） |
| `/compact`，等回答時來 | **2**（兩次都 2，同一個信名） |

### 程式位置

1. `py/aos/apps/eca/midturn.py:41`：等回答時來的信先過 `before_queue`。
2. 同檔 `:44-46`：過完才用 `slash_of` 認出是 slash，`stopped = True`、`return []`——信留在 `cur/`、這次 hook 回的 body 丟掉。
3. 下一輪 `py/aos/apps/eca/turn.py:64`：一般流程讀 `cur/` 的這封，再過一次 `before_queue`。

所以：計數、記帳型的 hook 會算兩次；第一次 hook 改的 `content` 不留（第二次拿到的是原信）；第一次就攔下（退 10）的話信直接丟、不會有第二次。單獨來的 slash 信（`turn.py:61-70`）、普通的中途信都只一次。只發生在等回答時會收中途信的路：沒畫面而 `live_mail` 開著（這次跑的），或畫面開著走收件 socket（`cli_ask.live_a2a`，同一個 `More.take`，沒另外跑）。

修法（沒做，給使用者選時參考）：`midturn.py` 先用 `slash_of` 看原信、是 slash 就不過 hook 直接停手（hook 留給下一輪那次）；兩行內的改動，會改「slash 信過 hook 的時機」，但結果跟單獨來的 slash 信一樣。

## 第三件：修成只過一次（第二輪）

### 使用者的題目與答案

頂層轉來的原話：使用者 11-20 用選項框選了「修：只過一次」，選項說明「等回答途中認出是 slash 信就不過 hook、直接留給下一輪，下一輪才過那一次」。題目本身的字頂層沒有轉來，這裡只能記到選項與說明。

### 改了什麼

- `py/aos/apps/eca/midturn.py` 的 `More.take`：讀到信先用 `slash_of` 看**原信**，是 slash 就停手、不過 hook、信留在 `cur/`；下一輪 `turn.py:64` 過那唯一一次。原本 hook 之後的 `slash_of` 檢查留著：hook 把普通信改成 slash 時照舊停手（這種極少見的情況下一輪會再過一次 hook，見「替使用者做的選擇」）。檔頭說明補一句。
- 新測試 `py/tests/apps/eca/test_slash_hook_once.py`（4 支）：普通信單獨、slash 單獨、普通信中途、slash 中途，各只過一次。放到沒修的複本上，slash 中途那支紅（`{'/compact': 2}`）；修過的全綠。
- `06-hook.md` eca 表的 before_queue 那格補「每封只過一次（等回答時來的 slash 信當下不過、留到下一輪才過）」。第一輪加的字沒有寫「過兩次」，不用改。
- 教學 `docs/tutorial/06-接著開發-3-除錯與腳本.md:69`、`py/aos/apps/gdb/README.md:66` 的 `brain_failed("BrainTimeout")` 改成 `brain_failed("BrainFailed")`（兩種身體都不會發 BrainTimeout）。gdb README 原本被 aos-kinit-tpl-1120 claim 著，等它放了才 claim、才改。

### 改前改後實跑

複本：`git archive 7327f47bc`（第二輪開工時的 HEAD）抄兩份，`base2` 只有 HEAD，`mine2` 再蓋上本線第二輪四個檔，各自跑 `install.py`。repro 同第二件（`repro.py`），每種跑兩次：

| 情境 | 改前（base2） | 改後（mine2） |
|---|---|---|
| 普通信，單獨一輪 | 1、1 | 1、1 |
| `/compact`，單獨一輪 | 1、1 | 1、1 |
| 普通信，等回答時來 | 1、1 | 1、1 |
| `/compact`，等回答時來，再跑一輪 | **2、2** | **1、1** |

```
base2: == slash letter mid-turn, then one more turn, run 1
         before_queue calls per letter: {"SLOW:3 first": 1, "/compact": 2}
mine2: == slash letter mid-turn, then one more turn, run 1
         before_queue calls per letter: {"SLOW:3 first": 1, "/compact": 1}
```

### 開畫面走 socket（live_a2a）那條

- 實跑了，方法跟上面不同：`repro/sockrun.py` 在同一個行程裡直接叫真的 `cli_ask.live_a2a` 和真的 `midturn.More`，給它一條真的 Unix socket。
- CLI 那頭是假的：一個 socket 伺服器，收到信封就照 `cli_a2a` 的格式寫回執、寫 `turns.jsonl`，並在第一批之後往 queue 寄一封中途信。
- 沒起 tmux 畫面：小格的 `alive()` 換成永遠 true。
- `Handoff` 換成只會收信（`aos-post done`）的小替身，所以 history 沒接。
- 只數「等回答這段」的次數。下一輪走的是 `turn.py:64`，跟上表同一段，沒在 socket 這邊另跑。

```
base2: == sock-slash (late letter '/compact')   before_queue calls while waiting: 1 ["/compact"]   left in queue cur/: 1
mine2: == sock-slash (late letter '/compact')   before_queue calls while waiting: 0 []             left in queue cur/: 1
both:  == sock-plain (late letter 'second')     before_queue calls while waiting: 1 ["second"]     handed over mid-turn: ["second"]
```

改前：等回答時多過一次，下一輪再過一次，合計 2 次。改後：等回答時 0 次、信留給下一輪，合計 1 次。普通中途信兩邊都是 1 次，而且都投出去了。

### 測試（改前改後，同一份 HEAD）

| 夾 | base2 | mine2 |
|---|---|---|
| `py/tests` | 690 支 OK（skipped 1） | 690 支 OK（skipped 1） |
| `py/tests/apps/eca` | 223 支 OK | 227 支 OK（多的 4 支是新測試） |
| `py/tests/apps/agent` | 213 支 OK（skipped 3） | 213 支 OK（skipped 3） |
| 新測試放在 base2 上 | 4 支、slash 中途那支紅 | 4 支 OK |

base2 上那份新測試檔跑完後移到 `~/.aos/scratch/aos-hook-drift-1120/base2-newtest.py.moved`（沒刪），所以三夾比對時 base2 不含它。

## 測試（第一輪）

照規則 6：`git archive HEAD` 抄出兩份乾淨複本、各自 `install.py`、清 `AOS_*`、逐夾跑 unittest（`py/tests`、`py/tests/apps/*`、`py/tools/**/tests`、`templates/tests/*`、`templates/tests`、`templates/kernel`、`cpp/**/tests`）。

兩份都從 `e1209424b` 抄出（`mine`＝再蓋上本線四個檔），各 79 夾。暫存在 `~/.aos/scratch/aos-hook-drift-1120/`（`suite-base.txt`、`suite-mine.txt`、`logs-*`、`rerun-*.log`）。

| | 基準 `base` | `mine` |
|---|---|---|
| `py/tests` | 665 支 OK（skipped 1、expected failures 1） | 665 支 OK（skipped 1）：`test_hand_copies_match_fully` 從預期失敗變成真的過 |
| 第一輪兩邊不同的四夾 | `apps/agent`、`apps/eca`、`box_check` 各 1 支紅 | `apps/gdb` 1 支紅（`test_gdb_live` 的 step） |
| 那四夾單獨重跑（兩份接著跑、不並行） | 全 OK | 全 OK，支數同基準 |
| `py/tools/aos/kernel/tests` | 1 支紅（`test_kernel_route` test_06） | 同一支紅：基準就紅，跟本線無關 |
| `templates/kernel/tests`、`templates/tests/image-move-check` | 0 支、退 5 | 同（不是 unittest） |
| 其餘 | 全 OK | 逐夾支數與結果同基準 |

第一輪兩份並行跑、機器上同時有別線的活樹與測試，四夾的紅是負載下的 live 測試（經 kernel 加 parent、pi 的 live_mail、acceptance、gdb step），重跑都綠。

## 替使用者做的選擇

- 17 項以外，同一段裡測試抓不到、但跟程式不符的字也一起改了（上面「順手改的」）；都是照程式與宣告，沒有新說法。
- `test_hook_points_match.py` 保留 `KNOWN_GAPS`（改成空的 `frozenset()`）與兩支比對已知清單的測試，之後真有要暫時放過的漂移還能用；`test_hand_copies_match_fully` 拿掉 `expectedFailure`，現在跟 `test_no_new_gaps` 等價。
- 第二件沒起 daemon／aos-loop 的整隻 agent，只跑身體 `aos-eca-turn`（loop 每拍叫的那支）：要數的是 hook 被叫幾次，跟外面有沒有 loop 無關；假腦路走 `live_mail`（沒開畫面也會收中途信）而不是開 tmux 畫面的 socket 路。
- gdb 例子的 `BrainTimeout` 第一輪沒改，第二輪照頂層轉來的指示改成 `BrainFailed`（選它是因為 agent-fsm 的 kernel 錯誤都走這個代號）。
- 第二輪：hook 之後的 `slash_of` 檢查留著。hook 把普通信改成 slash 時照舊停手，所以這種情況下一輪會再過一次 hook。要做到嚴格只過一次，就得把 hook 改過的信存起來帶到下一輪，是更大的改動；這情況要 hook 刻意把字改成 slash 指令，所以沒做。
- 第二輪：socket 路的實跑用的是真的 `live_a2a`、`More`、socket，假的 CLI 那頭；沒起 tmux 畫面、沒真 claude。

## 跟別線

- claim 了 `06-hook.md`、self_hook `_tooldef.json`、知識庫 `me/self_hook.json`、`test_hook_points_match.py`、本紀錄；開工時沒有別線 claim 這幾份。
- 教學沒有要改的字，沒碰 aos-pylib-k3-1120 的章。
- 交件時工作樹裡有 aos-hook-k2-1120 沒交的改動（`hooks.py`、`hook_point.py` 等）；本線測試只在 `e1209424b` 的複本上跑過，k2 若改了宣告或 EVENTS，`test_hook_points_match.py` 現在沒有已知清單可以放過，漏寫的手抄會直接紅（這正是要的）。
