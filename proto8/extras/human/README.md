# proto8/extras/human — 給人用的 say／listen／chat

← [proto8](../../README.md)｜設計與代定：[thinking 2026-10-24-say-listen](../../thinking/2026-10-24-say-listen.md)、[2026-10-30-agent-lifecycle](../../thinking/2026-10-30-agent-lifecycle.md)（A-7、A-8、第 4 步）｜測試 `proto8/tests/test_human.py`

讓人對一隻 aos agent（範本 [demo/agent-nia](../../demo/README.md) 這種走 queue 的）說話、看它回什麼、看它停在哪。**只碰 agent 的 stack**：說話＝寄進 `<stack>/queue/`、回答＝`<stack>/history.jsonl` 最新那則沒有 `tool_calls` 的 assistant、狀態看 aos-loop 的 `state.json`。Python、純標準庫、只在 Linux（讀 `/proc`）；寄信叫 PATH 上的 `aos-post`。

| 程式 | NAME |
|---|---|
| `bin/aos-say` | aos-say - 對一隻 agent 說一句話：寄進它 stack 的 queue |
| `bin/aos-listen` | aos-listen - 看一隻 agent 回了什麼（等一封的回答／跟著看／快照） |
| `bin/aos-chat` | aos-chat - 跟一隻 agent 一問一答（say＋listen 串起來，可以替你跑 agent） |
| `bin/aos_human.py` | 三支共用：工作區與 stack、誰在跑、trace 短行、快照；寄信、看回答、讀 stack 那幾樣在 [`proto8/lib/aos/aos_ws.py`](../../lib/aos/aos_ws.py)（跟 aos-ai 共用） |

```
aos-say    [--ws WS] [--stack STACK] [話...]                       stdout 印信號
aos-listen [--ws WS] [--stack STACK] [--timeout 秒] [--trace] 信號  等這封的回答
aos-listen [--ws WS] [--stack STACK] [--last N] [--trace] [--follow] 跟著看（像 tail -f）
aos-listen [--ws WS] [--stack STACK] --status                      誰在跑、loop 的 phase、最後一格、queue 幾封
aos-chat   [--ws WS] [--stack STACK] [--trace] [agent 資料夾]      /status /run /trace /help /quit
```

stack＝`--stack` ＞ `$AOS_STACK` ＞ `<工作區>/.stack/`（N-57）；工作區＝`--ws` ＞ `$AOS_WS` ＞ cwd（同 aos-exec）。每支開頭的說明寫了全部規則。

**agent 對話協議＝[CONVENTION P-42](../../docs/CONVENTION/02-題目stack停錯腦.md)**（10-30；之前是 P-11～P-14 的工作區信箱）：

- **說**：`aos-say 話`＝`aos-post send --ordered <stack>/queue`，一封信的 body＝`{"role": "user", "content": 話}`（N-16 有順序的信箱；queue 還沒有就先建，可以先說、再跑 agent）。印的信號就是 `new/` 裡那封的名字（`<12 位序號>.<信號>`）。
- **聽**：`aos-listen 信號`——信還在 `queue/new/` 或 `cur/` 就等；不見了就印 history 最新那則回答（先 say 後 listen 不會漏）。queue 沒這封、history 也沒回答＝`QuestionUnknown`；等的時候看到過、信不見了卻沒有回答＝`AnswerMissing`。`--follow`／`--last N` 直接跟 history（一段＝問的話＋回答）。
- **看**：`aos-listen --status` 印誰在服務（只靠 `/proc` 掃 `AOS_STACK`／`AOS_WS`）、**aos-loop `state.json` 的 `phase`**（看得出 `paused`）、認領中的信（`current.txt`）、queue 各格幾封、trace 最後一格（fsm〔含 aos-round〕寫 `state`、eca turn 與 10-30 前的舊 round 寫 `unit`；失敗＝「停在 X 那格、結束碼 N」）、history 幾則。
- **停**：寫 `<stack>/ctl.json`（aos-loop 的窗，N-07）：`{"paused": true}` 不起下一輪、`{"stopped": true}` 收工。

**舊協議的範本說不到**：agent-bob／ann／dan、topdown 這些 fsm 範本讀工作區的 `new/`、寫 `out/`（P-11 的 10-30 改口標「舊協議」），say／listen 不再認它們；要用就手放 `<工作區>/new/<題名>`、`aos-exec` 跑、看 `out/`。agent-dan 有搬到 queue 的版本 [agent-dan-q](../../demo/README.md#agent-dan-q)（10-30），say／listen 說得到。

**外部 coding agent（claude／codex）一樣說得到**（[thinking 10-30 eca](../../thinking/2026-10-30-eca.md) P-43 草稿、C 結論 9）：它的定義跟 aos agent 同形（`_entry` 是 aos-loop、一格 turn＝[`lib/eca/turn`](../../lib/eca/turn/turn.py)），由 turn 格收 queue、把回答寫進 history，所以 say／listen／chat 一行不用改、不分是誰在答。「有沒有人在跑」只看 `/proc`（10-30 刪了 stack 裡 `server.txt` 自己報名那招，eca 衝突 6）：直接 `aos-exec` 跑的，aos-loop 的 `AOS_STACK` 就是這個 stack；掛在 daemon 底下的，子 loop 的 `AOS_STACK` 是 daemon 的小格、工作區的 `.stack` 是指過去的 symlink（`aos-daemon-ctl add --ws`），也認得。turn 答某封失敗時在 `trace.jsonl` 留 `question`、`error`，listen 會說出來。

## 怎麼用

PATH 要有 aos-exec、aos-loop、aos-post（同 demo/run.sh）、`proto8/bin`（agent-nia 要 aos-parts、aos-tools）與這裡的 `bin/`：

```sh
R=~/repo/simple_tools/aos/proto8
export PATH=$R/impls/aos-exec/bin:$R/impls/aos-loop/bin:$R/impls/aos-post/bin:$R/bin:$R/extras/human/bin:$PATH
mkdir -p ~/code/try/say-listen/ws && cd ~/code/try/say-listen/ws

aos-chat $R/demo/agent-nia                              # 一問一答，chat 每句之後替你跑一次 agent（假腦）

# 或分開：
N=$(aos-say 現在幾點？)                                 # 寄一封
aos-exec --ws . $R/demo/agent-nia                       # 跑（別的終端機也行；queue 空了自己停）
aos-listen "$N"                                         # 拿這封的回答
aos-listen --last 5                                     # 最近五段一問一答
aos-listen --status                                     # 快照
```

**要 agent 一直在**（不用每次跑）：把 agent-nia 改成「停著等」的定義——`parts.json` 的 round 給 `"env": {"ROUND_ON_EMPTY": "idle"}`、`loop.json` 拿掉 `max`、加 `"interval_ms": 300`（[demo/README agent-nia 段](../../demo/README.md)「兩種定義」）。`aos-exec --ws ~/code/try/say-listen/ws <那份 agent>` 開著，另一個終端機 `aos-chat`（不給 agent）就行；`aos-listen --status` 看得到 `loop     phase waiting`／`paused`。agent 失敗時 loop 會停（P-20），修好再開。
