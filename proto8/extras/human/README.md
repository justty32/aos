# proto8/extras/human — 給人用的 say／listen

← [proto8](../../README.md)｜設計與代定：[thinking 2026-10-24-say-listen](../../thinking/2026-10-24-say-listen.md)、[2026-10-30-agent-lifecycle](../../thinking/2026-10-30-agent-lifecycle.md)（A-7、A-8、第 4 步）｜測試 `proto8/tests/test_human.py`

讓人對一隻走 queue 的 agent（例：[demo/eca-claude](../../demo/README.md#eca-templates) 這種外部 coding agent）說話、看它回什麼、看它停在哪。**只碰 agent 的 stack**：說話＝寄進 `<stack>/queue/`、回答＝`<stack>/history.jsonl` 最新那則沒有 `tool_calls` 的 assistant、狀態看 aos-loop 的 `state.json`。Python、純標準庫、只在 Linux（讀 `/proc`）；寄信叫 PATH 上的 `aos-post`。

| 程式 | NAME |
|---|---|
| `bin/aos-say` | aos-say - 對一隻 agent 說一句話：寄進它 stack 的 queue |
| `bin/aos-listen` | aos-listen - 看一隻 agent 回了什麼（等最新那封的回答／跟著看） |
| `bin/aos_human.py` | 兩支共用：工作區與 stack、誰在跑、沒人在跑時的提醒；寄信、看回答、讀 stack 那幾樣在 [`proto8/lib/aos/aos_ws.py`](../../lib/aos/aos_ws.py) |

```
aos-say    [--ws WS] [--stack STACK] [話...]                       stdout 印信件名稱
aos-listen [--ws WS] [--stack STACK] [--timeout 秒]                等最新那封的回答（正規用法：aos-say 話 && aos-listen）
aos-listen [--ws WS] [--stack STACK] [--last N] [--follow]         最後 N 段；--follow＝接著跟著看（像 tail -f）
```

aos-chat 封存在 `proto8/archive/aos-chat/`（使用者 11-03 晚：瘦身候選「可以先封存，等之後我們進展到那塊的時候可以拉出來看看」）；一問一答用 `aos-say 話 && aos-listen`。fsm、aos-eca-turn 不寫 `trace.jsonl`，也沒有狀態快照指令（`aos-listen` 沒有 `--status`；使用者「trace.jsonl會無限累加...老實說我覺得這個檔案沒啥必要。」「整個拿掉。……aos-listen --status其實也是沒必要的，要看他的狀態，應該是用aos-eca status。」，[thinking 11-03 trace](../../thinking/2026-11-03-trace.md)）。

stack＝`--stack` ＞ `$AOS_STACK` ＞ `<工作區>/.stack/`（N-57）；工作區＝`--ws` ＞ `$AOS_WS` ＞ cwd（同 aos-exec）。每支開頭的說明寫了全部規則。

**agent 對話協議＝[CONVENTION P-42](../../docs/CONVENTION/02-題目stack停錯腦.md)**：

- **說**：`aos-say 話`＝`aos-post send --ordered <stack>/queue`，一封信的 body＝`{"role": "user", "content": 話}`（N-16 有順序的信箱；queue 還沒有就先建，可以先說、再跑 agent）。印的信件名稱就是 `new/` 裡那封的名字（`<12 位序號>.<尾名>`）。
- **聽**：`aos-say 話 && aos-listen`（正規用法，[thinking say-listen「11-01 晚」](../../thinking/2026-10-24-say-listen.md#11-01-晚使用者aos-say---aos-listen-才是正規用法)；不收信件名稱參數）——等**最新那封**＝queue 的 `new/`、`cur/` 裡照處理順序排最後的（`aos_ws.letter_key` 取 max：有序在前、無序在後，各照名字；aos-say 寄的都是有序＝最後寄出的、或剛被認領的，不管誰寄的）：還在就等；不見了就印 history 最新那則回答（先 say 後 listen 不會漏）。`new/`、`cur/` 都空＝答案已經到了，直接印最新那則回答；history 也沒回答＝`QuestionUnknown`；信不見了卻沒有回答＝`AnswerMissing`；沒人在跑＝提醒一次信在 queue 的哪裡、怎麼跑，繼續等。`--last N` 印最後 N 段就走、`--follow` 接著跟著看（一段＝問的話＋回答）。
- **看**：沒有快照指令；外部 coding agent 用 `aos-eca status`，aos agent 直接看 stack 的 `state.json`（aos-loop 的窗，`phase`）、`queue/`、`mailbox_warning.txt`。
- **停**：寫 `<stack>/ctl.json`（aos-loop 的窗，N-07）：`{"cmd": "pause"}` 不起下一輪、`{"cmd": "resume"}` 接著跑、`{"cmd": "stop"}` 收工（ctl 是一道指令，見 [aos-loop](../../impls/aos-loop/README.md)；起來前就在的那份不算）。

**舊協議的範本說不到**：agent-bob／ann／eve 這些 fsm 範本（11-04 起在 `proto8/tests/fixtures/`）讀工作區的 `new/`、寫 `out/`（P-11 的舊協議），say／listen 不再認它們（say 之後拿它們跑，listen 會一直等）；要用就手放 `<工作區>/new/<題名>`、`aos-exec` 跑、看 `out/`。走 queue、say／listen 說得到的範本是 [eca-claude](../../demo/README.md#eca-templates)（codex 版 eca-codex 11-04 刪了，只差 cli.json；11-03 前還有用格組起來的 agent-nia，隨 round 那套 agent 刪了）。

**外部 coding agent（claude／codex）一樣說得到**（[thinking 10-30 eca](../../thinking/2026-10-30-eca.md) P-43 草稿、C 結論 9）：它的定義跟 aos agent 同形（`_entry` 是 aos-loop、`loop.json` 叫 [`aos-eca-turn`](../../bin/aos-eca-turn)），由 aos-eca-turn 收 queue、把回答寫進 history，所以 say／listen 一行不用改、不分是誰在答。「有沒有人在跑」只看 `/proc`：直接 `aos-exec` 跑的，aos-loop 的 `AOS_STACK` 就是這個 stack；掛在 daemon 底下的，子 loop 的 `AOS_STACK` 是 daemon 的小格，`--stack $(aos-daemon-ctl where --stack 名字)` 指過去就認得（工作區沒有 `.stack` 捷徑，[thinking 11-03 stack-where](../../thinking/2026-11-03-stack-where.md)；aos-say 說「目前沒有程式在跑」時多印一行提示這個寫法）。這個 stack 是 daemon 表上留著的列時，aos-say 的提醒照它的 phase 說：`stopped`＝`aos-daemon-ctl start 名字`（eca＝`aos-eca start 名字`）；`sleeping`（daemon 收工時睡下的）＝重開 daemon（`aos-exec <daemon 資料夾>`，提醒裡印出 daemon 的 stack），它會自己醒（11-04；[thinking 11-03 procs § 8](../../thinking/2026-11-03-procs.md#8-收工時改寫成休息中sleepwake11-03-晚)）。aos-eca-turn 答失敗時錯誤一行在 stderr（掛在 daemon 底下的看 `aos-eca status`），信留在 cur/。

## 怎麼用

PATH 要有 aos-exec、aos-loop、aos-post（同 `proto8/tests/aos_bins.py`）、`proto8/bin`（aos-eca-turn、aos-tools）、claude 與這裡的 `bin/`：

```sh
R=~/repo/simple_tools/aos/proto8
export PATH=$R/impls/aos-exec/bin:$R/impls/aos-loop/bin:$R/impls/aos-post/bin:$R/bin:$R/extras/human/bin:$PATH
mkdir -p ~/code/try/say-listen/ws && cd ~/code/try/say-listen/ws

aos-say 現在幾點？                                      # 寄一封
aos-exec --ws . $R/demo/eca-claude &                    # 跑（常駐：queue 空了隔 interval_ms 再看；別的終端機也行）
aos-listen                                              # 拿最新那封的回答
aos-say 再說一次 && aos-listen                          # 正規用法：說完就等
aos-listen --last 5                                     # 最近五段一問一答
```

**停著等還是跑完就收**寫在定義裡：eca 範本的 `loop.json` 給 `aos-eca-turn --on-empty idle`＋`interval_ms`＝常駐；改 `--on-empty stop`（拿掉 `interval_ms`）＝queue 空了 loop 收工。`<stack>/state.json` 的 `phase` 看得到 `waiting`／`paused`；收工寫 `{"cmd": "stop"}` 進 `<stack>/ctl.json`。agent 失敗時 loop 會停（P-20），修好再開。
